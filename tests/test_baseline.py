import csv
import json
import subprocess
import sys
import pytest
from scripts.baseline import load_inputs, messages_for
from server.app import ROOT


def test_ablation_inputs_do_not_leak(tmp_path):
    audio = tmp_path / 'audio.wav'
    audio.touch()
    row = {'id':'a','audio':'audio.wav','draft':'초안만의고유문구'}
    text = messages_for(row, 'text-only', tmp_path)
    assert '초안만의고유문구' in json.dumps(text, ensure_ascii=False)
    assert not any(c['type'] == 'audio' for m in text for c in m['content'])
    audio_only = messages_for(row, 'audio-only', tmp_path)
    assert '초안만의고유문구' not in json.dumps(audio_only, ensure_ascii=False)
    both = messages_for(row, 'audio-draft', tmp_path)
    assert '초안만의고유문구' in json.dumps(both, ensure_ascii=False)
    assert any(c['type'] == 'audio' for m in both for c in m['content'])


def test_audio_mode_rejects_text_fixture():
    row = load_inputs(ROOT / 'examples/demo-inputs.json')[0]
    with pytest.raises(ValueError, match='requires real audio'):
        messages_for(row, 'audio-draft', ROOT)


def test_private_manifest_rejected_as_model_input():
    with pytest.raises(ValueError, match='only id, audio, draft'):
        load_inputs(ROOT / 'examples/demo-references.json')


def test_copy_cli_to_local_scorer_matches_web_fixture(tmp_path):
    output = tmp_path / 'copy.csv'
    subprocess.run([sys.executable, '-m', 'scripts.baseline', '--inputs', 'examples/demo-inputs.json',
                    '--output', str(output)], cwd=ROOT, check=True)
    with output.open() as f:
        predictions = list(csv.DictReader(f))
    public = load_inputs(ROOT / 'examples/demo-inputs.json')
    assert [r['prediction'] for r in predictions] == [r['draft'] for r in public]
    result = subprocess.run([sys.executable, '-m', 'scripts.evaluate', '--references', 'examples/demo-references.json',
                             '--predictions', str(output)], cwd=ROOT, check=True, text=True, capture_output=True)
    score = json.loads(result.stdout)
    assert score['macro_cer'] == pytest.approx(200/31)
    assert score['cer_improvement_pp'] == 0
    assert score['restoration_rate'] == 0
    assert output.with_suffix('.run.json').exists()
