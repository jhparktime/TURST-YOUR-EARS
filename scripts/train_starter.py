"""CPU-only, train-only token correction starter. No Eval references at inference."""
import argparse
from collections import Counter, defaultdict
import csv
from difflib import SequenceMatcher
import hashlib
import json
from pathlib import Path
import re
import unicodedata

from scripts.baseline import load_inputs

TOKEN = re.compile(r'[가-힣A-Za-z0-9]+')


def tokens(text):
    return TOKEN.findall(unicodedata.normalize('NFC', text))


def fit(inputs, references, min_support=1, min_confidence=0.9):
    if min_support < 1 or not 0 < min_confidence <= 1:
        raise ValueError('Invalid support or confidence.')
    data = json.loads(references.read_text(encoding='utf-8'))
    public = json.loads(inputs.read_text(encoding='utf-8'))
    if data.get('name') != 'tye-ko-asr-v2-train' or public.get('name') != 'tye-ko-asr-v2-train':
        raise ValueError('Fit accepts the Train split only; never fit on Eval or Test references.')
    rows = load_inputs(inputs)
    gold = {row['id']: row for row in data['items']}
    if len(gold) != len(data['items']) or set(gold) != {r['id'] for r in rows}:
        raise ValueError('Train input and reference IDs differ.')
    exposure, edits = Counter(), defaultdict(Counter)
    for row in rows:
        target = gold[row['id']]
        if target['draft'] != row['draft']:
            raise ValueError('Train draft mismatch.')
        before, after = tokens(row['draft']), tokens(target['reference'])
        exposure.update(before)
        for tag, a, b, c, d in SequenceMatcher(None, before, after, autojunk=False).get_opcodes():
            if tag == 'replace' and b-a == d-c:
                for old, new in zip(before[a:b], after[c:d]):
                    if old != new:
                        edits[old][new] += 1
    rules = {}
    for old, choices in sorted(edits.items()):
        new, count = sorted(choices.items(), key=lambda pair: (-pair[1], pair[0]))[0]
        if (len(old) >= 2 and len(new) >= 2 and count >= min_support
                and count / exposure[old] >= min_confidence
                and SequenceMatcher(None, old, new, autojunk=False).ratio() >= 0.5):
            rules[old] = {'replacement': new, 'support': count, 'exposure': exposure[old]}
    return {'format': 'tye-token-starter-v1', 'training_split': 'train',
            'training_rows': len(rows), 'training_sha256': hashlib.sha256(references.read_bytes()).hexdigest(),
            'min_support': min_support, 'min_confidence': min_confidence, 'rules': rules}


def correct(draft, model):
    # Replace whole lexical tokens in one pass; preserve all other characters.
    return TOKEN.sub(lambda match: model['rules'].get(match[0], {}).get('replacement', match[0]),
                     unicodedata.normalize('NFC', draft))


def predict(inputs, model_path, output):
    model = json.loads(model_path.read_text(encoding='utf-8'))
    if model.get('format') != 'tye-token-starter-v1':
        raise ValueError('Unsupported model format.')
    rows = load_inputs(inputs)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['id', 'prediction'])
        writer.writerows((r['id'], correct(r['draft'], model)) for r in rows)
    return {'rows': len(rows), 'rules': len(model['rules']), 'output': str(output)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    train = sub.add_parser('fit')
    train.add_argument('--inputs', type=Path, required=True)
    train.add_argument('--references', type=Path, required=True)
    train.add_argument('--model', type=Path, required=True)
    train.add_argument('--min-support', type=int, default=1)
    train.add_argument('--min-confidence', type=float, default=0.9)
    inference = sub.add_parser('predict')
    inference.add_argument('--inputs', type=Path, required=True)
    inference.add_argument('--model', type=Path, required=True)
    inference.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.action == 'fit':
        model = fit(args.inputs, args.references, args.min_support, args.min_confidence)
        args.model.parent.mkdir(parents=True, exist_ok=True)
        args.model.write_text(json.dumps(model, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        print(json.dumps({'training_rows': model['training_rows'], 'rules': len(model['rules'])}))
    else:
        print(json.dumps(predict(args.inputs, args.model, args.output)))


if __name__ == '__main__':
    main()
