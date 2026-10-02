"""Optional real Postgres integration; CI supplies a disposable service."""
import json
import os
import uuid
import pytest
from fastapi.testclient import TestClient
from server.app import ROOT, create_app


@pytest.mark.skipif(not os.getenv('TEST_POSTGRES_URL'), reason='TEST_POSTGRES_URL not configured')
def test_postgres_score_survives_app_restart(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_URL', os.environ['TEST_POSTGRES_URL'])
    manifest = json.loads((ROOT / 'examples/demo-references.json').read_text())
    manifest['name'] = 'db-test-' + str(uuid.uuid4())
    path = tmp_path / 'references.json'
    path.write_text(json.dumps(manifest))
    client = TestClient(create_app(data_dir=tmp_path, reference_path=path, demo=True))
    headers = {'Authorization': 'Bearer demo-team-key'}
    body = (ROOT / 'web/assets/sample-submission.csv').read_bytes()
    result = client.post('/api/submissions', headers=headers, files={'file': ('a.csv', body, 'text/csv')})
    assert result.status_code == 200, result.text
    assert result.json()['macro_cer'] == pytest.approx(100/62)
    restarted = TestClient(create_app(data_dir=tmp_path / 'different-disk', reference_path=path, demo=True))
    assert restarted.get('/api/leaderboard').json()['entries'][0]['macro_cer'] == pytest.approx(100/62)
    duplicate = restarted.post('/api/submissions', headers=headers, files={'file': ('a.csv', body, 'text/csv')})
    assert duplicate.json()['reused'] is True
    assert len(restarted.get('/api/submissions', headers=headers).json()['entries']) == 1
