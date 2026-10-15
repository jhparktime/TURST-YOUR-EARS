import csv
import io
import json
import shutil
from pathlib import Path

import pytest

from scripts.build_dataset import digest
from scripts.build_submission_assets import public_eval_snapshot
from server.scoring import validate_manifest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def snapshot(tmp_path):
    public = tmp_path / 'public'
    (public / 'eval').mkdir(parents=True)
    for name in ('inputs.json', 'references.json'):
        shutil.copyfile(ROOT / 'datasets/tye-ko-merged-v1/eval' / name, public / 'eval' / name)
    refs = validate_manifest(json.loads((public / 'eval/references.json').read_text()))
    omni = tmp_path / 'omni/full'
    omni.mkdir(parents=True)
    folder = omni.parent / 'completed-public-eval'
    folder.mkdir()
    # Copy predictions are a controlled fixture, not a claimed Qwen result.
    shutil.copyfile(ROOT / 'web/data/eval-copy.csv', folder / 'text-only.csv')
    shutil.copyfile(ROOT / 'datasets/tye-ko-merged-v1/eval/copy-draft.scores.json',
                    folder / 'text-only.scores.json')
    proof = json.loads((ROOT / 'docs/measurements/qwen-text-only-eval.json').read_text())['provenance']
    proof['predictions_sha256'] = digest(folder / 'text-only.csv')
    (folder / 'text-only.receipt.json').write_text(json.dumps(proof))
    contract = {k: v for k, v in proof['contract'].items() if k not in ('mode', 'prompt')}
    (omni / 'status.json').write_text(json.dumps({'contract': contract, 'modes': ['text-only']}))
    return omni, public, refs, folder, proof


def test_complete_eval_can_be_published_before_private_run_finishes(snapshot):
    omni, public, refs, folder, _ = snapshot
    assert public_eval_snapshot(omni, 'text-only', public, refs) == (
        folder / 'text-only.scores.json', folder / 'text-only.csv')
    assert public_eval_snapshot(omni, 'audio-draft', public, refs) is None


@pytest.mark.parametrize('fault', ['prefix', 'input', 'settings', 'metric', 'private_export'])
def test_snapshot_rejects_incomplete_changed_or_unverifiable_results(snapshot, fault):
    omni, public, refs, folder, proof = snapshot
    if fault == 'prefix':
        path = folder / 'text-only.csv'
        rows = list(csv.reader(io.StringIO(path.read_text())))
        with path.open('w', newline='') as stream:
            csv.writer(stream).writerows(rows[:-1])
        proof['predictions_sha256'] = digest(path)
    elif fault == 'input':
        proof['contract']['input_manifests_sha256']['eval'] = 'changed'
    elif fault == 'settings':
        proof['contract']['max_new_tokens'] = 128
    elif fault == 'metric':
        path = folder / 'text-only.scores.json'
        metrics = json.loads(path.read_text())
        metrics['macro_cer'] = 0
        path.write_text(json.dumps(metrics))
    else:
        proof['private_predictions_exported'] = True
    (folder / 'text-only.receipt.json').write_text(json.dumps(proof))
    with pytest.raises(ValueError):
        public_eval_snapshot(omni, 'text-only', public, refs)
