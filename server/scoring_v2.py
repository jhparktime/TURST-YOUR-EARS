"""Real-ASR correction protocol, independent from frozen synthetic v1.

Primary: pooled normalized character error rate (micro CER). Macro CER is
the mean of utterance CERs, NOT v1's mean over three synthetic conditions.
Slot diagnostics use deterministic reference-anchored Levenshtein alignments;
they describe string changes and do not certify acoustic/semantic correctness.
"""
from collections import defaultdict
import unicodedata

from .scoring import MAX_CELLS, MAX_ROWS, distance, normalize, parse_submission, rate, words

VERSION = 'ko-correction-v2'
PRIMARY_METRIC = 'micro_cer'
CONDITIONS = ('clean', 'substitution', 'deletion', 'insertion', 'mixed')


def aligned_slots(reference, hypothesis):
    """Separate L character slots and L+1 gaps. Ties: diagonal, delete, insert.

    A reference→hypothesis deletion leaves a character slot empty; insertion
    strings live at their reference gap. Repeated strings may admit multiple
    optimal alignments; the same deterministic rule is used for every system.
    """
    matrix = [list(range(len(hypothesis) + 1))]
    for i, left in enumerate(reference, 1):
        row = [i]
        for j, right in enumerate(hypothesis, 1):
            row.append(min(row[-1] + 1, matrix[-1][j] + 1,
                           matrix[-1][j-1] + (left != right)))
        matrix.append(row)
    chars, gaps = [''] * len(reference), [''] * (len(reference) + 1)
    i, j = len(reference), len(hypothesis)
    while i or j:
        if i and j and matrix[i][j] == matrix[i-1][j-1] + (reference[i-1] != hypothesis[j-1]):
            chars[i-1] = hypothesis[j-1]
            i, j = i-1, j-1
        elif i and matrix[i][j] == matrix[i-1][j] + 1:
            i -= 1
        else:
            gaps[i] = hypothesis[j-1] + gaps[i]
            j -= 1
    operations = {'substitutions': sum(bool(c) and c != r for c, r in zip(chars, reference)),
                  'deletions': sum(not c for c in chars),
                  'insertions': sum(map(len, gaps))}
    return {'characters': chars, 'gaps': gaps, 'errors': matrix[-1][-1], **operations}


def condition(aligned):
    kinds = [name for name, key in [('substitution', 'substitutions'), ('deletion', 'deletions'),
                                   ('insertion', 'insertions')] if aligned[key]]
    return kinds[0] if len(kinds) == 1 else 'mixed' if kinds else 'clean'


def validate_references(refs):
    if not isinstance(refs, list) or not refs or len(refs) > MAX_ROWS:
        raise ValueError('Invalid v2 reference manifest.')
    seen = set()
    for row in refs:
        if not isinstance(row, dict) or set(row) != {'id', 'reference', 'draft', 'source'}:
            raise ValueError('V2 references require exactly id, reference, draft, source.')
        ident = row['id']
        if not isinstance(ident, str) or not 0 < len(ident) <= 120 or ident != ident.strip() or ident in seen:
            raise ValueError('Reference IDs must be nonempty and unique.')
        seen.add(ident)
        for key in ('reference', 'draft'):
            text = row[key]
            if not isinstance(text, str) or text != unicodedata.normalize('NFC', text) or len(text) > 4000:
                raise ValueError('Reference and draft must be bounded NFC text.')
            length = len(normalize(text))
            if length > 1000 or (key == 'reference' and not length):
                raise ValueError('Reference requires 1–1000 scored characters; draft may be empty.')
        if not isinstance(row['source'], str) or not 0 < len(row['source']) <= 80:
            raise ValueError('A nonempty drafter source label is required.')
    return refs


def validate_manifest(manifest):
    if not isinstance(manifest, dict) or manifest.get('protocol') != VERSION:
        raise ValueError('Manifest protocol must be ' + VERSION)
    if not isinstance(manifest.get('name'), str) or not manifest['name'].strip():
        raise ValueError('Manifest needs a dataset name.')
    refs = validate_references(manifest.get('items'))
    score({r['id']: r['draft'] for r in refs}, refs)
    return refs


def counter():
    return dict(errors=0, draft_errors=0, characters=0, word_errors=0, words=0,
                utterances=0, cer_sum=0.0, draft_cer_sum=0.0, restored_slots=0,
                error_slot_total=0, changed_slots=0, harmed=0, preserved_total=0,
                inserted_clean_gaps=0, clean_gap_total=0, clean_changed=0,
                clean_total=0, substitutions=0, deletions=0, insertions=0,
                draft_substitutions=0, draft_deletions=0, draft_insertions=0)


def metrics(bucket):
    return {**bucket, 'cer': rate(bucket['errors'], bucket['characters']),
            'draft_cer': rate(bucket['draft_errors'], bucket['characters']),
            'macro_cer': bucket['cer_sum'] / bucket['utterances'],
            'draft_macro_cer': bucket['draft_cer_sum'] / bucket['utterances'],
            'cer_improvement_pp': rate(bucket['draft_errors'] - bucket['errors'], bucket['characters']),
            'wer': rate(bucket['word_errors'], bucket['words']),
            'slot_restoration_rate': rate(bucket['restored_slots'], bucket['error_slot_total']),
            'correction_precision': rate(bucket['restored_slots'], bucket['changed_slots']),
            'correction_f1': rate(2 * bucket['restored_slots'], bucket['changed_slots'] + bucket['error_slot_total']),
            'harmful_edit_rate': rate(bucket['harmed'], bucket['preserved_total']),
            'unwanted_insertion_rate': rate(bucket['inserted_clean_gaps'], bucket['clean_gap_total']),
            'clean_change_rate': rate(bucket['clean_changed'], bucket['clean_total'])}


def score(predictions, references):
    refs = validate_references(references)
    if set(predictions) != {r['id'] for r in refs}:
        raise ValueError('Submission IDs must exactly match this evaluation set (no missing or extra IDs).')
    groups, sources, total, cells = defaultdict(counter), defaultdict(counter), counter(), 0
    for row in refs:
        prediction = predictions[row['id']]
        if not isinstance(prediction, str) or len(prediction) > 4000:
            raise ValueError('Prediction must be a string of at most 4000 characters.')
        reference, draft, hypothesis = map(normalize, (row['reference'], row['draft'], prediction))
        rw, hw = words(row['reference']), words(prediction)
        cells += (len(reference)+1)*(len(draft)+1) + (len(reference)+1)*(len(hypothesis)+1)
        cells += (len(rw)+1)*(len(hw)+1)
        if cells > MAX_CELLS:
            raise ValueError('Submission exceeds the scorer computation limit. Contact the organizers.')
        before, after = aligned_slots(reference, draft), aligned_slots(reference, hypothesis)
        value = counter()
        value.update(errors=after['errors'], draft_errors=before['errors'],
                     characters=len(reference), word_errors=distance(rw, hw), words=len(rw),
                     utterances=1, cer_sum=100 * after['errors'] / len(reference),
                     draft_cer_sum=100 * before['errors'] / len(reference))
        for channel, targets in [('characters', reference), ('gaps', [''] * (len(reference)+1))]:
            for target, old, new in zip(targets, before[channel], after[channel]):
                dirty = old != target
                value['error_slot_total'] += dirty
                value['restored_slots'] += dirty and new == target
                value['changed_slots'] += old != new
                if not dirty:
                    if channel == 'characters':
                        value['preserved_total'] += 1
                        value['harmed'] += new != target
                    else:
                        value['clean_gap_total'] += 1
                        value['inserted_clean_gaps'] += bool(new)
        if not before['errors']:
            value['clean_total'] = 1
            value['clean_changed'] = int(hypothesis != reference)
        for key in ('substitutions', 'deletions', 'insertions'):
            value[key], value['draft_' + key] = after[key], before[key]
        for bucket in (groups[condition(before)], sources[row['source']], total):
            for key, count in value.items():
                bucket[key] += count
    aggregate = metrics(total)
    conditions = {key: metrics(groups[key]) for key in CONDITIONS if key in groups}
    return {'scorer': VERSION, 'primary_metric': PRIMARY_METRIC,
            'micro_cer': aggregate['cer'], 'micro_wer': aggregate['wer'],
            **{key: aggregate[key] for key in ('macro_cer', 'draft_macro_cer', 'cer_improvement_pp',
                'slot_restoration_rate', 'restored_slots', 'error_slot_total', 'changed_slots',
                'correction_precision', 'correction_f1', 'harmful_edit_rate', 'harmed',
                'preserved_total', 'unwanted_insertion_rate', 'inserted_clean_gaps',
                'clean_gap_total', 'clean_change_rate', 'clean_changed', 'clean_total')},
            'draft_micro_cer': aggregate['draft_cer'], 'worst_cer': max(c['cer'] for c in conditions.values()),
            'conditions': conditions, 'sources': {key: metrics(value) for key, value in sorted(sources.items())},
            'utterances': len(refs), 'counts': {key: total[key] for key in ('errors', 'draft_errors',
                'characters', 'substitutions', 'deletions', 'insertions', 'draft_substitutions',
                'draft_deletions', 'draft_insertions')}}
