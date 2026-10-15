"""Korean audio-grounded transcript correction: deterministic public protocol."""
import csv
import io
import unicodedata
from collections import defaultdict

VERSION = "ko-correction-v1"
CONDITIONS = ("clean", "single", "multiple")
MAX_ROWS = 20000
# Bounded total dynamic-programming work for a four-hour test submission.
MAX_CELLS = 40_000_000
IGNORED = set(',!?;:"\'“”‘’()[]{}<>，！？。…·')


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


def alignment(reference, hypothesis):
    """Return output attached to each reference character, plus leading insertion.

    Ties: diagonal, deletion, insertion. Insertions belong to the character on
    their left; leading insertions are separate. All strings are normalized.
    """
    matrix = [list(range(len(hypothesis) + 1))]
    for i, left in enumerate(reference, 1):
        row = [i]
        for j, right in enumerate(hypothesis, 1):
            row.append(min(row[-1] + 1, matrix[-1][j] + 1,
                           matrix[-1][j-1] + (left != right)))
        matrix.append(row)
    chars, inserted = [''] * len(reference), [''] * (len(reference) + 1)
    i, j = len(reference), len(hypothesis)
    while i or j:
        if i and j and matrix[i][j] == matrix[i-1][j-1] + (reference[i-1] != hypothesis[j-1]):
            chars[i-1] = hypothesis[j-1]
            i, j = i-1, j-1
        elif i and matrix[i][j] == matrix[i-1][j] + 1:
            i -= 1
        else:
            inserted[i] = hypothesis[j-1] + inserted[i]
            j -= 1
    return [c + inserted[k+1] for k, c in enumerate(chars)], inserted[0], matrix[-1][-1]


def corruption(row):
    """Validate substitutions and return their normalized reference spans.

    Require normalization to compose across edit boundaries. This rejects such
    ambiguous edits as a boundary that creates/removes a decimal point.
    """
    text, edits = row['reference'], row.get('edits')
    if not isinstance(edits, list) or len(edits) > 4:
        raise ValueError('Each row requires an edits list with at most four substitutions.')
    pieces, norm_parts, spans, cursor, size = [], [], [], 0, 0
    for edit in edits:
        if not isinstance(edit, dict):
            raise ValueError('Invalid substitution annotation.')
        start, end, replacement = edit.get('start'), edit.get('end'), edit.get('replacement')
        if type(start) is not int or type(end) is not int or not cursor <= start < end <= len(text):
            raise ValueError('Edit spans must be sorted, disjoint NFC reference offsets.')
        if not isinstance(replacement, str) or replacement != unicodedata.normalize('NFC', replacement) or not 0 < len(replacement) <= 100:
            raise ValueError('Replacement requires 1–100 NFC characters.')
        prefix, target = normalize(text[cursor:start]), normalize(text[start:end])
        if not target or not normalize(replacement) or target == normalize(replacement):
            raise ValueError('Each substitution must change scored characters.')
        if spans and not prefix:
            raise ValueError('Substitutions must have an unchanged scored character between them.')
        size += len(prefix)
        spans.append((size, size + len(target)))
        size += len(target)
        pieces.extend([text[cursor:start], replacement])
        norm_parts.extend([prefix, target])
        cursor = end
    pieces.append(text[cursor:])
    norm_parts.append(normalize(text[cursor:]))
    if ''.join(pieces) != row['draft']:
        raise ValueError('Applying edits to reference must exactly reconstruct draft.')
    if ''.join(norm_parts) != normalize(text):
        raise ValueError('Ambiguous normalization at edit boundary.')
    # Check unchanged characters also remain unchanged after draft normalization.
    draft_parts, cursor = [], 0
    for edit in edits:
        draft_parts.extend([normalize(text[cursor:edit['start']]), normalize(edit['replacement'])])
        cursor = edit['end']
    draft_parts.append(normalize(text[cursor:]))
    if ''.join(draft_parts) != normalize(row['draft']):
        raise ValueError('Ambiguous normalization at draft edit boundary.')
    return spans


def validate_references(refs):
    if not isinstance(refs, list) or not refs or len(refs) > MAX_ROWS:
        raise ValueError('Invalid reference manifest.')
    ids = set()
    for row in refs:
        if not isinstance(row, dict):
            raise ValueError('Invalid reference row.')
        ident = row.get('id')
        if not isinstance(ident, str) or not ident or len(ident) > 120 or ident != ident.strip() or ident in ids:
            raise ValueError('Reference IDs must be nonempty and unique.')
        ids.add(ident)
        for key in ('reference', 'draft'):
            value = row.get(key)
            if not isinstance(value, str) or value != unicodedata.normalize('NFC', value) or not 0 < len(normalize(value)) <= 1000 or len(value) > 4000:
                raise ValueError('Reference and draft require NFC text with 1–1000 scored characters and at most 4000 raw characters.')
        spans = corruption(row)
        expected = 'clean' if not spans else 'single' if len(spans) == 1 else 'multiple'
        if row.get('condition') != expected:
            raise ValueError('Condition must match substitution count: clean=0, single=1, multiple=2–4.')
        if 'entities' in row or 'context' in row:
            raise ValueError('Legacy context annotations are not part of this protocol.')


def validate_manifest(manifest):
    if not isinstance(manifest, dict) or manifest.get('protocol') != VERSION:
        raise ValueError('Manifest protocol must be ' + VERSION)
    if not isinstance(manifest.get('name'), str) or not manifest['name'].strip():
        raise ValueError('Manifest needs a dataset name.')
    validate_references(manifest.get('items'))
    declared = manifest.get('conditions')
    if not isinstance(declared, list) or any(not isinstance(x, str) for x in declared) or len(declared) != len(set(declared)) or set(declared) != {r['condition'] for r in manifest['items']}:
        raise ValueError('Declared conditions must match the manifest rows.')
    if set(declared) != set(CONDITIONS):
        raise ValueError('A leaderboard manifest requires clean, single and multiple conditions.')
    # Reject ambiguous annotations and oversized releases before opening submissions.
    score({r['id']: r['draft'] for r in manifest['items']}, manifest['items'])
    return manifest['items']


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
        prediction = predictions[row['id']]
        if not isinstance(prediction, str) or len(prediction) > 4000:
            raise ValueError('Prediction must be a string of at most 4000 characters.')
        reference, hypothesis, draft = normalize(row['reference']), normalize(prediction), normalize(row['draft'])
        rw, hw = words(row['reference']), words(prediction)
        cells += (len(reference)+1)*(len(hypothesis)+1)
        cells += (len(reference)+1)*(len(draft)+1) + (len(rw)+1)*(len(hw)+1)
        if cells > MAX_CELLS:
            raise ValueError('Submission exceeds the scorer computation limit. Contact the organizers.')
        prepared.append((row, reference, hypothesis, draft, rw, hw, corruption(row)))
    groups = defaultdict(lambda: dict(errors=0, draft_errors=0, characters=0, word_errors=0, words=0,
        utterances=0, restored=0, edit_total=0, harmed=0, preserved_total=0,
        clean_changed=0, clean_total=0))
    for row, reference, hypothesis, draft, rw, hw, spans in prepared:
        bucket = groups[row['condition']]
        draft_aligned, draft_leading, draft_errors = alignment(reference, draft)
        # The frozen reference→draft alignment must agree with the recorded
        # corruption. Otherwise repeated text can falsely credit an unedited draft.
        covered = {i for start, end in spans for i in range(start, end)}
        bad = any(draft_aligned[i] != char for i, char in enumerate(reference) if i not in covered)
        for (start, end), edit in zip(spans, row['edits']):
            found = (draft_leading if start == 0 else '') + ''.join(draft_aligned[start:end])
            bad |= found != normalize(edit['replacement'])
        bad |= bool(draft_leading) and (not spans or spans[0][0] != 0)
        if bad:
            raise ValueError('Ambiguous reference-to-draft alignment; revise the corruption spans or exclude the sample.')
        aligned, leading, errors = alignment(reference, hypothesis)
        bucket['errors'] += errors
        bucket['draft_errors'] += draft_errors
        bucket['characters'] += len(reference)
        bucket['word_errors'] += distance(rw, hw)
        bucket['words'] += len(rw)
        bucket['utterances'] += 1
        corrupted = set()
        for start, end in spans:
            value = ''.join(aligned[start:end])
            if start == 0:
                value = leading + value
            bucket['restored'] += value == reference[start:end]
            bucket['edit_total'] += 1
            corrupted.update(range(start, end))
        for index, char in enumerate(reference):
            if index not in corrupted:
                bucket['preserved_total'] += 1
                value = (leading if index == 0 else '') + aligned[index]
                bucket['harmed'] += value != char
        if not spans:
            bucket['clean_total'] += 1
            bucket['clean_changed'] += hypothesis != reference
    def metrics(b):
        return {**b, 'cer': rate(b['errors'], b['characters']),
                'draft_cer': rate(b['draft_errors'], b['characters']),
                'cer_improvement_pp': rate(b['draft_errors'] - b['errors'], b['characters']),
                'wer': rate(b['word_errors'], b['words']),
                'restoration_rate': rate(b['restored'], b['edit_total']),
                'harmful_edit_rate': rate(b['harmed'], b['preserved_total']),
                'clean_change_rate': rate(b['clean_changed'], b['clean_total'])}
    conditions = {k: metrics(groups[k]) for k in CONDITIONS if k in groups}
    totals = {key: sum(b[key] for b in groups.values()) for key in next(iter(groups.values()))}
    aggregate = metrics(totals)
    macro = sum(b['cer'] for b in conditions.values()) / len(conditions)
    draft_macro = sum(b['draft_cer'] for b in conditions.values()) / len(conditions)
    return {'scorer': VERSION, 'primary_metric': 'macro_cer', 'macro_cer': macro,
            'draft_macro_cer': draft_macro, 'cer_improvement_pp': draft_macro - macro,
            'micro_cer': aggregate['cer'], 'micro_wer': aggregate['wer'],
            'worst_cer': max(b['cer'] for b in conditions.values()),
            **{key: aggregate[key] for key in ('restoration_rate', 'restored', 'edit_total',
               'harmful_edit_rate', 'harmed', 'preserved_total', 'clean_change_rate', 'clean_changed', 'clean_total')},
            'conditions': conditions, 'utterances': len(references)}
