import csv
import io
import json

from fastapi.testclient import TestClient

from server.app import create_app


def test_v2_ranking_uses_micro_cer_and_survives_restart(tmp_path, monkeypatch):
    monkeypatch.delenv('DATABASE_URL', raising=False)
    manifest = {'name':'v2-ranking-fixture','protocol':'ko-correction-v2','items':[
        {'id':'long','reference':'가'*100,'draft':'가'*100,'source':'a'},
        {'id':'short','reference':'나','draft':'나','source':'b'}]}
    ref = tmp_path / 'refs.json'
    ref.write_text(json.dumps(manifest))
    client = TestClient(create_app(data_dir=tmp_path/'db',reference_path=ref,demo=True))
    assert client.get('/api/health').json()['primary_metric'] == 'micro_cer'
    results = []
    for predictions in [{'long':'다'+'가'*99,'short':'다'}, {'long':'다'*3+'가'*97,'short':'나'}]:
        stream = io.StringIO()
        writer = csv.writer(stream)
        writer.writerow(['id','prediction'])
        writer.writerows(predictions.items())
        response = client.post('/api/submissions',headers={'Authorization':'Bearer demo-team-key'},
            files={'file':('predictions.csv',stream.getvalue().encode(),'text/csv')})
        assert response.status_code == 200
        results.append(response.json())
    assert results[0]['micro_cer'] < results[1]['micro_cer']
    assert results[0]['macro_cer'] > results[1]['macro_cer']
    restarted = TestClient(create_app(data_dir=tmp_path/'db',reference_path=ref,demo=True))
    best = restarted.get('/api/leaderboard').json()['entries'][0]
    assert best['submission_id'] == results[0]['id']
    assert best['scorer'] == 'ko-correction-v2' and best['rank'] == 1
    assert restarted.get('/test-references.json').status_code == 404
