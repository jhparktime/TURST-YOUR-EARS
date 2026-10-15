"""Verify browser scores against the authoritative Python implementation."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from server.scoring import score, normalize, parse_submission

ROOT = Path(__file__).resolve().parent.parent


def browser(payload):
    result = subprocess.run(['node', '-e', '''
const fs=require('node:fs'); const s=require('./web/scorer.js');
const p=JSON.parse(fs.readFileSync(0,'utf8'));
let out;
if(p.op==='normalize') out=p.texts.map(s.normalize);
else if(p.op==='csv') out=Object.fromEntries(s.parseCSV(p.csv));
else out=s.score(new Map(Object.entries(p.predictions)),p.manifest);
process.stdout.write(JSON.stringify(out));
'''], input=json.dumps(payload, ensure_ascii=False), text=True,
        capture_output=True, cwd=ROOT, check=True)
    return json.loads(result.stdout)


pytestmark = pytest.mark.skipif(not shutil.which('node'), reason='Node required for browser parity')


def test_normalization_matches_korean_unicode_and_numbers():
    texts = ['가 나, 다!', '3.14 3 . 14', '세 시', '3시', 'ABC', 'İ',
             '².³', '①.②', '😀.가', '\x1c 가\x85나\ufeff다', '가\u200b나']
    assert browser({'op':'normalize', 'texts':texts}) == [normalize(s) for s in texts]


@pytest.mark.parametrize('csv_text', [
    '\ufeffid,prediction\r\na,"가, 나"\r\nb,"줄\n바꿈"\r\nc,\r\n',
    'id,prediction\na,"그가 ""안녕""이라고"\nb,따옴"표\n\n',
    'id,prediction\n a ,가\n',
])
def test_csv_quotes_bom_newlines_and_empty_predictions(csv_text):
    assert browser({'op':'csv','csv':csv_text}) == parse_submission(csv_text.encode())


def compare(predictions, manifest):
    expected = score(predictions, manifest['items'])
    actual = browser({'predictions':predictions,'manifest':manifest})
    # Same operation order intentionally gives exact pooled ratios, including null denominators.
    assert actual == expected


def test_fixture_copy_gold_deletions_and_insertions():
    manifest = json.loads((ROOT / 'examples/demo-references.json').read_text())
    for key in ('draft', 'reference'):
        compare({r['id']:r[key] for r in manifest['items']}, manifest)
    compare({r['id']:'' for r in manifest['items']}, manifest)
    compare({r['id']:'추가' + r['draft'] + '추가' for r in manifest['items']}, manifest)


def test_full_public_eval_copy_and_transcript_changes():
    manifest = json.loads((ROOT / 'datasets/tye-ko-merged-v1/eval/references.json').read_text())
    compare({r['id']:r['draft'] for r in manifest['items']}, manifest)
    compare({r['id']:r['reference'][:-1] + '추가' for r in manifest['items']}, manifest)


@pytest.mark.parametrize('csv_text', ['\nid,prediction\na,가\n', 'id,prediction\na,가\na,나\n',
                                    'id,prediction\na,"닫히지 않은 따옴표'])
def test_malformed_submissions_rejected_by_both(csv_text):
    with pytest.raises(ValueError):
        parse_submission(csv_text.encode())
    with pytest.raises(subprocess.CalledProcessError):
        browser({'op':'csv','csv':csv_text})
