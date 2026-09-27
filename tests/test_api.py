import json
import pytest
from fastapi.testclient import TestClient
from server.app import ROOT, create_app, connect, token_hash


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('DAILY_LIMIT', '2')
    monkeypatch.setenv('SUBMISSIONS_OPEN', '1')
    return TestClient(create_app(data_dir=tmp_path, demo=True))


def post(client, body=None, key='demo-team-key'):
    body = body if body is not None else (ROOT / 'web/assets/sample-submission.csv').read_bytes()
    return client.post('/api/submissions', headers={'Authorization': f'Bearer {key}'}, files={'file': ('test.csv', body, 'text/csv')})


def test_end_to_end(client):
    assert client.get('/api/health').json()['mode'] == 'sandbox'
    response = post(client)
    assert response.status_code == 200
    data = response.json()
    assert data['macro_wer'] == pytest.approx(100/12)
    assert data['conditions']['misleading']['wer'] == 25
    assert 'reference' not in data
    assert post(client).json()['reused'] is True
    history = client.get('/api/submissions', headers={'Authorization': 'Bearer demo-team-key'}).json()
    assert len(history['entries']) == 1
    assert len(client.get('/api/leaderboard').json()['entries']) == 1
    # Neither private manifests nor the toy reference are exposed by static mounting.
    for path in ['/examples/demo-references.json', '/private-data/scores.sqlite3', '/server/app.py']:
        assert client.get(path).status_code == 404


def test_auth_invalid_rows_quota(client):
    assert post(client, key='bad').status_code == 401
    assert post(client, b'id,prediction\nbad,hello').status_code == 422
    assert post(client).status_code == 200
    body = (ROOT / 'web/assets/sample-submission.csv').read_bytes()
    assert post(client, body.replace(b'marina', b'marine')).status_code == 200
    assert post(client, body.replace(b'marina', b'marino')).status_code == 429
    assert post(client).status_code == 200  # Idempotent retries remain possible.


def test_close_and_size(client, monkeypatch):
    assert post(client, b'x' * (2 * 1024 * 1024 + 1)).status_code == 413
    monkeypatch.setenv('SUBMISSIONS_OPEN', '0')
    assert post(client).status_code == 403


def test_team_isolation(tmp_path, monkeypatch):
    client = TestClient(create_app(data_dir=tmp_path, demo=True))
    with connect(tmp_path / 'scores.sqlite3') as db:
        db.execute('INSERT INTO teams VALUES (?, ?, ?)', ('other', '<script>alert(1)</script>', token_hash('other-key')))
    post(client)
    other = client.get('/api/submissions', headers={'Authorization': 'Bearer other-key'}).json()
    assert other['entries'] == []


def test_production_requires_references(tmp_path, monkeypatch):
    monkeypatch.delenv('REFERENCE_PATH', raising=False)
    with pytest.raises(RuntimeError): create_app(data_dir=tmp_path, demo=False)


def test_references_version_isolates_scores(tmp_path):
    path = tmp_path / 'refs.json'
    data = json.loads((ROOT / 'examples/demo-references.json').read_text())
    path.write_text(json.dumps(data))
    a = TestClient(create_app(data_dir=tmp_path, reference_path=path, demo=True))
    post(a)
    data['items'][0]['reference'] = 'a different reference'
    path.write_text(json.dumps(data))
    b = TestClient(create_app(data_dir=tmp_path, reference_path=path, demo=True))
    assert b.get('/api/leaderboard').json()['entries'] == []


def test_sandbox_key_cannot_authenticate_production(tmp_path):
    sandbox = TestClient(create_app(data_dir=tmp_path, demo=True))
    assert post(sandbox).status_code == 200
    production = TestClient(create_app(data_dir=tmp_path, demo=False, reference_path=ROOT / 'examples/demo-references.json'))
    assert post(production).status_code == 401
