import hashlib
import base64
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from scripts.build_course_submission_v2 import build
from server.scoring import parse_submission
from server.scoring_v2 import score,validate_manifest

ROOT=Path(__file__).resolve().parent.parent


def test_v2_public_assets_hashes_scores_and_source_overlap():
    folder=ROOT/'web/data-v2'
    receipt=json.loads((folder/'receipt.json').read_text())
    for name,expected in receipt['files'].items():
        assert hashlib.sha256((folder/name).read_bytes()).hexdigest()==expected
    assert receipt['private_row_export'] is False
    assert (folder/'eval.json').read_bytes()==(ROOT/'datasets/tye-ko-asr-v2/eval/references.json').read_bytes()
    refs=validate_manifest(json.loads((folder/'eval.json').read_text()))
    copied=score(parse_submission((folder/'eval-copy.csv').read_bytes()),refs)
    baseline=json.loads((folder/'baselines.json').read_text())
    by_key={(r['baseline'],r['split']):r['metrics'] for r in baseline['entries']}
    assert by_key['Copy draft','eval']==copied and len(refs)==409
    for split in ('eval','test'):
        for label,source in [('Whisper audio-only','whisper-turbo'),('Qwen audio-only','qwen-omni')]:
            assert by_key[label,split]['sources'][source]['cer']==by_key['Copy draft',split]['sources'][source]['cer']


@pytest.mark.skipif(not shutil.which('node'),reason='Node required')
def test_full_real_asr_eval_browser_matches_python():
    manifest=json.loads((ROOT/'web/data-v2/eval.json').read_text())
    for key in ('draft','reference'):
        predictions={r['id']:r[key] for r in manifest['items']}
        result=subprocess.run(['node','-e', '''
const fs=require('node:fs'),s=require('./web/scorer-v2.js'),p=JSON.parse(fs.readFileSync(0,'utf8'));
process.stdout.write(JSON.stringify(s.score(new Map(Object.entries(p.predictions)),p.manifest)));
'''],input=json.dumps({'manifest':manifest,'predictions':predictions}),text=True,
            capture_output=True,check=True,cwd=ROOT)
        assert json.loads(result.stdout)==score(predictions,manifest['items'])


def test_v2_single_html_contains_public_grader_without_runtime_dependencies(tmp_path):
    target=tmp_path/'v2.html'
    result=build(target)
    html=target.read_text()
    assert result['private_test_rows']==result['external_runtime_assets']==0
    assert not re.search(r'<script\b[^>]*\bsrc=',html)
    assert 'window.TYE_V2_EMBEDDED=' in html and 'public-eval-worker-v2.js' in html
    assert 'apiBase: ""' in html
    assert 'tye-ko-asr-v2-eval' in html
    audio = re.findall(r'<audio\b[^>]*\bsrc="data:audio/wav;base64,([^"]+)"', html)
    examples = json.loads((ROOT/'web/assets/examples-v2/examples.json').read_text())['items']
    assert len(audio) == len(examples) == 2
    for encoded, example in zip(audio, examples):
        assert hashlib.sha256(base64.b64decode(encoded)).hexdigest() == example['sha256']


def test_workshop_audio_examples_are_unmodified_public_eval_records():
    examples = json.loads((ROOT/'web/assets/examples-v2/examples.json').read_text())
    refs = json.loads((ROOT/'web/data-v2/eval.json').read_text())
    audio_hashes = json.loads((ROOT/'datasets/tye-ko-asr-v2/eval/audio-checksums.json').read_text())
    by_id = {row['id']: row for row in refs['items']}
    for example in examples['items']:
        # Membership prevents a Test sample from becoming a website demonstration.
        original = by_id[example['id']]
        for key in ('draft', 'reference', 'source'):
            assert example[key] == original[key]
        assert hashlib.sha256((ROOT/'web'/example['audio']).read_bytes()).hexdigest() == example['sha256']
        assert example['sha256'] == audio_hashes[example['id']]
