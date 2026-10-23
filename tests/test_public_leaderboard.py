import base64
import copy
import gzip
import hashlib
import json
from pathlib import Path

import pytest

from scripts import public_leaderboard as board

ROOT=Path(__file__).resolve().parent.parent
CSV=(ROOT/'web/data-v2/eval-copy.csv').read_bytes()


def package(raw_csv=CSV,**changes):
    value=dict(format=board.FORMAT,manifest_sha256=board.manifest_hash(),team='team03',
        method='Copy draft',code_url='https://github.com/jhparktime/TURST-YOUR-EARS',consent=True,
        encoding='gzip+base64',csv_sha256=hashlib.sha256(raw_csv).hexdigest(),csv=base64.b64encode(gzip.compress(raw_csv)).decode())
    value.update(changes)
    return '### Result package\n\n```json\n'+json.dumps(value,ensure_ascii=False)+'\n```'


def issue(number=1,body=None,github_id=10,login='participant',date='2026-10-23T00:00:00Z'):
    return dict(number=number,body=package() if body is None else body,user=dict(id=github_id,login=login),created_at=date)


def test_recomputes_csv_ignoring_forged_client_score_and_keeps_best():
    value=board.empty_board()
    board.ingest(value,issue(body=package(micro_cer=0,github_id=999)))
    assert value['entries'][0]['github_id']==10
    assert value['entries'][0]['metrics']['micro_cer']==pytest.approx(11.766335975170426)
    assert value['entries'][0]['metrics']['utterances']==409
    before=copy.deepcopy(value)
    assert board.ingest(value,issue()) is False and value==before
    board.ingest(value,issue(2))
    assert value['history'][-1]['status']=='duplicate'
    assert len(value['entries'])==1 and value['entries'][0]['submissions']==1


@pytest.mark.parametrize('changes',[
    {'consent':False},{'manifest_sha256':'a'*64},{'csv_sha256':'0'*64},
    {'encoding':'pickle'},{'code_url':'javascript:alert(1)'},{'code_url':'https://user:pass@example.org'},
    {'team':'x\nrun this'},{'csv':'not gzip'},
])
def test_rejects_untrusted_or_mismatched_packages(changes):
    value=board.empty_board();board.ingest(value,issue(body=package(**changes)))
    assert value['history'][0]['status']=='rejected'
    assert value['entries']==[]


def test_rejects_decompression_bomb_and_missing_ids():
    with pytest.raises(ValueError,match='size or checksum'):
        board.unpack(package(b'a'*(board.MAX_CSV+1)))
    value=board.empty_board();board.ingest(value,issue(body=package(b'id,prediction\nwrong-id,hello\n')))
    assert value['history'][0]['status']=='rejected'
    assert 'IDs must exactly match' in value['history'][0]['reason']


def test_quota_is_new_valid_csv_per_account_per_kst_day_and_duplicates_are_free(monkeypatch):
    real_score=board.score
    measured=real_score({'r':'가'},[dict(id='r',reference='가',draft='나',source='x')])
    monkeypatch.setattr(board,'score',lambda *_:measured)
    value=board.empty_board()
    # Different harmless trailing blank lines change the file hash but retain valid CSVs.
    for n in range(1,7):board.ingest(value,issue(n,body=package(CSV+b'\n'*n),date='2026-10-23T14:59:00Z'))
    assert [r['status'] for r in value['history']]==['accepted']*5+['rejected']
    board.ingest(value,issue(7,body=package(CSV+b'\n'),date='2026-10-23T14:59:00Z'))
    assert value['history'][-1]['status']=='duplicate'
    board.ingest(value,issue(8,body=package(CSV+b'\n'*8),date='2026-10-23T15:00:00Z'))
    assert value['history'][-1]['status']=='accepted'
    assert value['history'][-1]['day_kst']=='2026-10-24'


def test_identity_and_team_name_are_bound_and_ties_are_raw(monkeypatch):
    metrics=dict(micro_cer=1.001,utterances=409)
    for key in board.SUMMARY_KEYS:metrics.setdefault(key,None)
    monkeypatch.setattr(board,'score',lambda *_:dict(metrics))
    value=board.empty_board();board.ingest(value,issue())
    board.ingest(value,issue(2,body=package(team='renamed')))
    board.ingest(value,issue(3,github_id=11,login='other'))
    assert [r['status'] for r in value['history']]==['accepted','rejected','rejected']
    board.ingest(value,issue(4,body=package(team='second'),github_id=11,login='other'))
    metrics['micro_cer']=1.002
    board.ingest(value,issue(5,body=package(team='third'),github_id=12,login='third'))
    assert [r['rank'] for r in value['entries']]==[1,1,3]
    assert value['entries'][0]['metrics']['micro_cer']!=value['entries'][-1]['metrics']['micro_cer']
