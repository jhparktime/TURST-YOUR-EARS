import csv
import json
import subprocess
import sys
import pytest
from scripts.baseline import load_inputs, messages_for, model_predictions
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


def test_simple_model_runner_keeps_capped_and_empty_outputs_without_retry(monkeypatch, tmp_path):
    from contextlib import nullcontext
    from types import SimpleNamespace
    from unittest.mock import MagicMock, Mock

    class Batch(dict):
        def to(self, *args):
            return self

    generated = MagicMock()
    generated.__getitem__.side_effect = [SimpleNamespace(shape=(1, 2)), SimpleNamespace(shape=(1, 1))]
    model = MagicMock()
    model.generate.return_value = generated
    processor = MagicMock()
    processor.return_value = Batch(input_ids=SimpleNamespace(shape=(1, 3)))
    processor.batch_decode.side_effect = [['  한도에 걸린 실제 출력  '], ['']]
    monkeypatch.setitem(sys.modules, 'torch', SimpleNamespace(
        manual_seed=Mock(), inference_mode=nullcontext))
    monkeypatch.setitem(sys.modules, 'transformers', SimpleNamespace(
        Qwen2_5OmniForConditionalGeneration=SimpleNamespace(from_pretrained=Mock(return_value=model)),
        Qwen2_5OmniProcessor=SimpleNamespace(from_pretrained=Mock(return_value=processor))))
    monkeypatch.setitem(sys.modules, 'qwen_omni_utils', SimpleNamespace(
        process_mm_info=Mock(return_value=(None, None, None))))
    args = SimpleNamespace(seed=0, model=str(tmp_path), revision=None,
        inputs=tmp_path/'inputs.json', mode='text-only', max_new_tokens=2)
    rows = [{'id':ident, 'audio':'unused.wav', 'draft':'복사해서는 안 되는 초안'} for ident in ['capped', 'empty']]
    diagnostics = []
    assert model_predictions(rows, args, diagnostics=diagnostics) == ['한도에 걸린 실제 출력', '']
    assert model.generate.call_count == 2
    assert diagnostics == [
        {'id':'capped', 'new_tokens':2, 'at_token_limit':True, 'empty_output':False},
        {'id':'empty', 'new_tokens':1, 'at_token_limit':False, 'empty_output':True}]
    assert all(call.kwargs['thinker_max_new_tokens'] == 2 for call in model.generate.call_args_list)
