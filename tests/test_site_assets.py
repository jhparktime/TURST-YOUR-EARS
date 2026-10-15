import hashlib
import json
import re
from pathlib import Path

from server.scoring import score, parse_submission, validate_manifest

ROOT = Path(__file__).resolve().parent.parent


def test_site_eval_is_exactly_the_canonical_public_split():
    expected = (ROOT / 'datasets/tye-ko-merged-v1/eval/references.json').read_bytes()
    actual = (ROOT / 'web/data/eval.json').read_bytes()
    assert actual == expected
    refs = validate_manifest(json.loads(actual))
    predictions = parse_submission((ROOT / 'web/data/eval-copy.csv').read_bytes())
    result = score(predictions, refs)
    baseline = json.loads((ROOT / 'web/data/baselines.json').read_text())
    copy = next(e for e in baseline['entries'] if e['baseline'] == 'Copy draft' and e['split'] == 'eval')
    assert copy['metrics'] == result
    assert len(refs) == 409


def test_benchmark_export_is_aggregates_only_and_assets_are_sealed():
    receipt = json.loads((ROOT / 'web/data/receipt.json').read_text())
    assert receipt['private_row_export'] is False
    for name, digest in receipt['files'].items():
        assert hashlib.sha256((ROOT / 'web/data' / name).read_bytes()).hexdigest() == digest
    baseline = json.loads((ROOT / 'web/data/baselines.json').read_text())
    def check(value):
        if isinstance(value, dict):
            assert not {'reference','draft','edits','source_id','prediction','audio','id'} & value.keys()
            for child in value.values(): check(child)
        elif isinstance(value, list):
            for child in value: check(child)
    check(baseline)
    assert baseline['dataset'] == 'tye-ko-merged-v1'


def test_private_server_configuration_matches_the_new_reference_version():
    source = (ROOT / 'web/config.js').read_text()
    metadata = json.loads((ROOT / 'datasets/tye-ko-merged-v1/metadata.json').read_text())
    configured = re.search(r'expectedReferenceVersion:\s*"([a-f0-9]+)"', source)[1]
    assert configured == metadata['splits']['test']['references_sha256'][:12]
    assert 'expectedDataset: "tye-ko-merged-v1-test"' in source
