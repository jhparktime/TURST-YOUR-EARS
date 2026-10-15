"""Development-only probe of synthetic-error shortcuts, never an official test.

Filter already generated ASR text using only a public draft. References are read
after all candidate outputs have been produced. No private split is supported.
"""
import argparse
import csv
import difflib
import json
import re
import unicodedata
from pathlib import Path

from scripts.baseline import load_inputs
from scripts.build_dataset import digest, write_json
from server.scoring import distance, normalize, parse_submission, score, validate_manifest

CONFIGS = ((0, 0), (1, 1), (1, 2), (2, 2), (2, 3))


def hangul_only(text):
    return bool(text) and all('\uac00' <= char <= '\ud7a3' for char in text)


def selective_draft(draft, asr, max_changed_syllables, max_jamo_distance):
    tokens = list(re.finditer(r'\S+', draft))
    left = [normalize(token.group()) for token in tokens]
    right = [normalize(token) for token in asr.split()]
    replacements = []
    for tag, start, end, a_start, a_end in difflib.SequenceMatcher(
            None, left, right, autojunk=False).get_opcodes():
        if tag != 'replace' or end - start != a_end - a_start:
            continue
        for index, proposed in zip(range(start, end), right[a_start:a_end]):
            current = left[index]
            if not (hangul_only(current) and hangul_only(proposed)) or len(current) != len(proposed):
                continue
            changes = sum(a != b for a, b in zip(current, proposed))
            if not 0 < changes <= max_changed_syllables:
                continue
            if distance(unicodedata.normalize('NFD', current),
                        unicodedata.normalize('NFD', proposed)) > max_jamo_distance:
                continue
            raw = tokens[index].group()
            # Keep punctuation and whitespace from the draft. Only Hangul
            # syllables are replaced; numbers and Latin strings never qualify.
            if sum('\uac00' <= c <= '\ud7a3' for c in raw) != len(proposed):
                continue
            chars = iter(proposed)
            replacement = ''.join(next(chars) if '\uac00' <= c <= '\ud7a3' else c for c in raw)
            replacements.append((tokens[index].start(), tokens[index].end(), replacement))
    for start, end, replacement in reversed(replacements):
        draft = draft[:start] + replacement + draft[end:]
    return draft, len(replacements)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--public', type=Path, required=True)
    parser.add_argument('--asr-predictions', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    metadata = json.loads((args.public / 'metadata.json').read_text())
    if metadata['name'] != 'tye-ko-merged-v1':
        raise ValueError('This diagnostic is limited to merged-v1 public eval.')
    input_path = args.public / 'eval/inputs.json'
    if digest(input_path) != metadata['splits']['eval']['inputs_sha256']:
        raise ValueError('Public inputs differ from frozen metadata.')
    rows = load_inputs(input_path)
    asr = parse_submission(args.asr_predictions.read_bytes())
    if len(rows) != 409 or set(asr) != {row['id'] for row in rows}:
        raise ValueError('Require exactly all 409 public eval inputs and predictions.')
    args.output.mkdir(parents=True, exist_ok=True)
    candidates = []
    for syllables, jamo in CONFIGS:
        predictions, accepted = {}, 0
        for row in rows:
            value, count = selective_draft(row['draft'], asr[row['id']], syllables, jamo)
            predictions[row['id']] = value
            accepted += count
        path = args.output / f'syllables-{syllables}-jamo-{jamo}.csv'
        with path.open('w', encoding='utf-8', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(['id', 'prediction'])
            writer.writerows(predictions.items())
        candidates.append({'max_changed_syllables': syllables, 'max_jamo_distance': jamo,
                           'accepted_word_changes': accepted, 'csv': path.name,
                           'csv_sha256': digest(path)})

    # All predictions above are fixed before any reference labels are opened.
    reference_path = args.public / 'eval/references.json'
    manifest = json.loads(reference_path.read_text())
    if manifest['name'] != 'tye-ko-merged-v1-eval':
        raise ValueError('Only the public eval reference manifest is allowed.')
    if digest(reference_path) != metadata['splits']['eval']['references_sha256']:
        raise ValueError('Public references differ from frozen metadata.')
    refs = validate_manifest(manifest)
    for candidate in candidates:
        candidate['metrics'] = score(parse_submission((args.output / candidate['csv']).read_bytes()), refs)
    report = {'dataset': metadata['name'], 'split': 'eval', 'utterances': len(rows),
        'scope': 'development_only_synthetic_shortcut_diagnostic',
        'private_test_read': False, 'official_baseline': False,
        'input_sha256': digest(input_path), 'asr_predictions_sha256': digest(args.asr_predictions),
        'reference_sha256': digest(reference_path), 'implementation_sha256': digest(Path(__file__)),
        'selection_warning': 'All candidates are reported. Public-eval comparisons do not prove held-out generalization or novelty.',
        'candidates': candidates}
    write_json(args.output / 'report.json', report)
    print(json.dumps([{key: candidate[key] for key in ('max_changed_syllables', 'max_jamo_distance',
        'accepted_word_changes')} | {key: candidate['metrics'][key] for key in ('macro_cer',
        'restoration_rate', 'harmful_edit_rate')} for candidate in candidates], ensure_ascii=False))


if __name__ == '__main__':
    main()
