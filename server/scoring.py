"""Korean CER and aligned entity diagnostics. Public, deterministic protocol."""
import csv
import io
import itertools
import unicodedata
from collections import defaultdict

VERSION = "ko-cer-v1"
MAX_ROWS = 20000
MAX_CELLS = 15_000_000
# Only typographic punctuation is ignored. Numeric separators/signs are preserved.
IGNORED = set(',!?;:"\'“”‘’()[]{}<>，！？。…·')
CONTEXTS = ("helpful", "partially_wrong", "misleading", "irrelevant", "no_context")


def normalize(text):
    text = "".join(c for c in unicodedata.normalize("NFC", text).lower() if not c.isspace())
    out = []
    for i, char in enumerate(text):
        if char in IGNORED:
            continue
        if char == '.' and not (i > 0 and i + 1 < len(text) and text[i-1].isdigit() and text[i+1].isdigit()):
            continue
        out.append(char)
    return ''.join(out)


def words(text):
    """Secondary, spacing-sensitive eojeol WER; no number expansion."""
    return [value for word in text.split() if (value := normalize(word))]


def distance(a, b):
    previous = list(range(len(b) + 1))
    for i, left in enumerate(a, 1):
        current = [i]
        for j, right in enumerate(b, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j-1] + (left != right)))
        previous = current
    return previous[-1]


def aligned_spans(reference, hypothesis, spans):
    """Minimum edit alignment: diagonal, deletion, insertion tie priority.

    Insertions at a target's right boundary belong to that target; insertions
    at its left boundary do not. This conservative rule is fixed for v1.
    """
    matrix = [list(range(len(hypothesis) + 1))]
    for i, left in enumerate(reference, 1):
        row = [i]
        for j, right in enumerate(hypothesis, 1):
            row.append(min(row[-1] + 1, matrix[-1][j] + 1, matrix[-1][j-1] + (left != right)))
        matrix.append(row)
    aligned = [''] * len(reference)
    inserted = [''] * (len(reference) + 1)
    i, j = len(reference), len(hypothesis)
    while i or j:
        if i and j and matrix[i][j] == matrix[i-1][j-1] + (reference[i-1] != hypothesis[j-1]):
            aligned[i-1] = hypothesis[j-1]
            i, j = i-1, j-1
        elif i and matrix[i][j] == matrix[i-1][j] + 1:
            i -= 1
        else:
            inserted[i] = hypothesis[j-1] + inserted[i]
            j -= 1
    return [''.join(aligned[k] + inserted[k+1] for k in range(start, end)) for start, end in spans]


def variants(row):
    """Approved aliases affect entity diagnostics only, never primary CER."""
    entities = row.get('entities', [])
    choices = [[e['text'], *e.get('aliases', [])] for e in entities]
    for selected in itertools.product(*choices):
        parts, spans, cursor, size = [], [], 0, 0
        for entity, alias in zip(entities, selected):
            prefix = normalize(row['reference'][cursor:entity['start']])
            value = normalize(alias)
            parts.extend([prefix, value])
            size += len(prefix)
            spans.append((size, size + len(value)))
            size += len(value)
            cursor = entity['end']
        parts.append(normalize(row['reference'][cursor:]))
        yield ''.join(parts), spans, [normalize(a) for a in selected]


def validate_references(refs):
    if not isinstance(refs, list) or not refs or len(refs) > MAX_ROWS:
        raise ValueError('Invalid reference manifest.')
    ids = set()
    for row in refs:
        if not isinstance(row, dict):
            raise ValueError('Invalid reference row.')
        ident, text = row.get('id'), row.get('reference')
        if not isinstance(ident, str) or not ident or len(ident) > 120 or ident != ident.strip() or ident in ids:
            raise ValueError('Reference IDs must be nonempty and unique.')
        ids.add(ident)
        if not isinstance(text, str) or text != unicodedata.normalize('NFC', text) or not 0 < len(normalize(text)) <= 1000:
            raise ValueError('References require NFC text with 1–1000 normalized characters.')
        if not isinstance(row.get('condition'), str) or not row['condition'].strip():
            raise ValueError('Each reference needs a condition.')
        if row.get('context', row['condition']) not in CONTEXTS:
            raise ValueError('Each row needs a supported context type.')
        entities = row.get('entities', [])
        if not isinstance(entities, list) or len(entities) > 4:
            raise ValueError('At most four entities per utterance are supported.')
        last, combinations = 0, 1
        for e in entities:
            if not isinstance(e, dict):
                raise ValueError('Invalid entity annotation.')
            start, end = e.get('start'), e.get('end')
            if type(start) is not int or type(end) is not int or not last <= start < end <= len(text) or text[start:end] != e.get('text') or not normalize(e['text']):
                raise ValueError('Entity spans must be sorted, disjoint and match reference text.')
            last = end
            aliases, wrong = e.get('aliases', []), e.get('wrong', [])
            if not isinstance(aliases, list) or not isinstance(wrong, list) or any(not isinstance(a, str) or not normalize(a) or len(a) > 100 for a in aliases + wrong):
                raise ValueError('Invalid entity aliases or distractors.')
            accepted = {normalize(e['text']), *(normalize(a) for a in aliases)}
            if accepted & {normalize(a) for a in wrong}:
                raise ValueError('An accepted alias cannot also be a wrong entity.')
            combinations *= 1 + len(aliases)
        if combinations > 16:
            raise ValueError('At most 16 alias combinations per utterance are supported.')
        if row.get('context', row['condition']) == 'partially_wrong' and entities:
            if not any(e.get('wrong') for e in entities) or not any(not e.get('wrong') for e in entities):
                raise ValueError('Partially wrong annotations need both corrupted and uncorrupted target entities.')


def parse_submission(data):
    try:
        reader = csv.DictReader(io.StringIO(data.decode('utf-8-sig'), newline=''), strict=True)
        if reader.fieldnames != ['id', 'prediction']:
            raise ValueError('CSV header must be exactly: id,prediction.')
        rows = {}
        for row in reader:
            if None in row or row.get('prediction') is None:
                raise ValueError('Every row must have exactly two CSV fields.')
            ident = row['id'].strip()
            if not ident or ident in rows:
                raise ValueError('IDs must be non-empty and unique.')
            if len(ident) > 120 or len(row['prediction']) > 4000:
                raise ValueError('An ID or prediction exceeds the size limit.')
            rows[ident] = row['prediction']
            if len(rows) > MAX_ROWS:
                raise ValueError('Too many rows.')
        if not rows:
            raise ValueError('The submission is empty.')
        return rows
    except (UnicodeDecodeError, csv.Error) as exc:
        raise ValueError('Upload a valid UTF-8 CSV file.') from exc


def rate(numerator, denominator):
    return 100 * numerator / denominator if denominator else None


def score(predictions, references):
    validate_references(references)
    if set(predictions) != {r['id'] for r in references}:
        raise ValueError('Submission IDs must exactly match this evaluation set (no missing or extra IDs).')
    prepared, cells = [], 0
    for row in references:
        hypothesis = normalize(predictions[row['id']])
        reference = normalize(row['reference'])
        rw, hw = words(row['reference']), words(predictions[row['id']])
        options = list(variants(row)) if row.get('entities') else []
        # Include a second matrix for backtracking the best alias variant.
        cells += (len(reference)+1)*(len(hypothesis)+1) + (len(rw)+1)*(len(hw)+1)
        cells += sum((len(v[0])+1)*(len(hypothesis)+1) for v in options)
        if options:
            cells += max((len(v[0])+1)*(len(hypothesis)+1) for v in options)
        if cells > MAX_CELLS:
            raise ValueError('Submission exceeds the scorer computation limit. Contact the organizers.')
        prepared.append((row, reference, hypothesis, rw, hw, options))
    groups = defaultdict(lambda: dict(errors=0, characters=0, word_errors=0, words=0, utterances=0,
                                      entity_correct=0, entity_total=0, wrong_adopted=0, wrong_total=0,
                                      mixed_correct=0, mixed_total=0))
    for row, reference, hypothesis, rw, hw, options in prepared:
        bucket = groups[row['condition']]
        bucket['errors'] += distance(reference, hypothesis)
        bucket['characters'] += len(reference)
        bucket['word_errors'] += distance(rw, hw)
        bucket['words'] += len(rw)
        bucket['utterances'] += 1
        if options:
            # Stable candidate order breaks alias ties; primary spelling comes first.
            chosen = min(options, key=lambda v: distance(v[0], hypothesis))
            found = aligned_spans(chosen[0], hypothesis, chosen[1])
            correct = [value == expected for value, expected in zip(found, chosen[2])]
            bucket['entity_correct'] += sum(correct)
            bucket['entity_total'] += len(correct)
            for value, entity in zip(found, row['entities']):
                if entity.get('wrong'):
                    bucket['wrong_total'] += 1
                    bucket['wrong_adopted'] += value in {normalize(w) for w in entity['wrong']}
            if row.get('context', row['condition']) == 'partially_wrong':
                bucket['mixed_total'] += 1
                bucket['mixed_correct'] += all(correct)
    def metrics(b):
        return {**b, 'cer': rate(b['errors'], b['characters']), 'wer': rate(b['word_errors'], b['words']),
                'entity_accuracy': rate(b['entity_correct'], b['entity_total']),
                'wrong_context_rate': rate(b['wrong_adopted'], b['wrong_total']),
                'mixed_accuracy': rate(b['mixed_correct'], b['mixed_total'])}
    context_by_group = {row['condition']: row.get('context', row['condition']) for row in references}
    ordered = sorted(groups, key=lambda k: (CONTEXTS.index(context_by_group[k]), k))
    conditions = {k: metrics(groups[k]) for k in ordered}
    ranked = sorted({row['condition'] for row in references if row.get('context', row['condition']) != 'no_context'})
    if not ranked:
        raise ValueError('At least one contextual condition is required for ranking.')
    totals = {key: sum(groups[name][key] for name in ranked) for key in next(iter(groups.values()))}
    aggregate = metrics(totals)
    return {'scorer': VERSION, 'primary_metric': 'macro_cer',
            'macro_cer': sum(conditions[k]['cer'] for k in ranked) / len(ranked),
            'micro_cer': aggregate['cer'], 'micro_wer': aggregate['wer'],
            'worst_cer': max(conditions[k]['cer'] for k in ranked),
            'entity_accuracy': aggregate['entity_accuracy'], 'entity_total': aggregate['entity_total'],
            'wrong_context_rate': aggregate['wrong_context_rate'], 'wrong_total': aggregate['wrong_total'],
            'mixed_accuracy': aggregate['mixed_accuracy'], 'mixed_total': aggregate['mixed_total'],
            'conditions': conditions, 'utterances': len(references)}
