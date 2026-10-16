"""Build a local, audio-first listening worksheet. Never uploads recordings.

Test worksheets are written beside private gold, never inside test/ inputs.
The worksheet records human work; generating it is NOT a completed review.
"""
import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

from scripts.build_dataset import digest
from server.scoring import normalize
from server.scoring_v2 import aligned_slots, condition, validate_manifest

TEMPLATE = r'''<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Trust Your Ears — Listening review</title><style>
body{font:17px/1.7 Georgia,"Times New Roman",serif;color:#222;background:#fff;margin:36px auto;padding:0 20px;max-width:920px}h1{font-size:29px;border-bottom:2px solid #183b5b}h2{font-size:21px}a{color:#163d70}label{display:block;margin:10px 0}textarea{display:block;box-sizing:border-box;width:100%;min-height:80px;font:16px/1.6 sans-serif}input,select,button{font:16px sans-serif;padding:5px}button{margin:8px 8px 8px 0}audio{width:100%}pre{white-space:pre-wrap;font:16px/1.7 sans-serif;border-left:3px solid #bbb;padding:10px}#status{padding:8px;border:1px solid #aaa}.muted{color:#555}fieldset{margin:16px 0}output{white-space:pre-wrap}
</style></head><body><h1>Trust Your Ears: 음성 청취 검수</h1>
<p>이 파일은 검수 도구입니다. 자동 검사만 통과한 후보이며 사람이 검수한 데이터로 표시하면 안 됩니다.</p>
<ol><li>정답과 초안을 열기 전에 음성만 듣고 들린 내용을 적습니다. 불명료하면 해당 부분을 [불명료]로 표시합니다.</li>
<li>‘원문·초안 확인’을 눌러 비교한 뒤 원천 전사의 정확성, 표기 차이와 실제 인식 오류를 구분합니다.</li>
<li>검수 결과를 저장하고 JSON을 내려받습니다. 저장한 문장만 검수 완료로 기록됩니다.</li></ol>
<p class="muted">앞의 최대 60개는 생성기·자동 오류 유형별 우선 검수 순서입니다. 전체 분포를 추정하는 표본이 아닙니다. 나머지 문장도 모두 검수할 수 있습니다. 분할이나 평가 문장은 이 순서로 변경되지 않습니다.</p>
<label>검수자 <input id="reviewer" autocomplete="name"></label>
<label>문장 <select id="utterance"></select></label><p id="identity"></p><audio id="player" controls preload="none"></audio>
<label>먼저 들린 내용 <textarea id="heard"></textarea></label><button id="reveal">원문·초안 확인</button>
<section id="texts" hidden><h2>원천 전사</h2><pre id="reference"></pre><h2>실제 ASR 초안</h2><pre id="draft"></pre><p id="source"></p>
<label>원천 전사 <select id="referenceStatus"><option value="">선택</option><option value="matches_audio">음성과 일치</option><option value="source_transcript_issue">원천 전사 오류 의심</option><option value="unclear_audio">음성으로 확정하기 어려움</option></select></label>
<label>초안 오류 판단 <select id="errorStatus"><option value="">선택</option><option value="genuine_asr_error">실제 ASR 오류</option><option value="notation_only">숫자·철자 등 표기 차이만 있음</option><option value="error_and_notation">실제 오류와 표기 차이 모두 있음</option><option value="correct_draft">초안이 맞음</option><option value="uncertain">판단 보류</option></select></label>
<label>초안만 봐서는 판단이 어렵고 음성이 필요한가? <select id="audioNeeded"><option value="">선택</option><option value="yes">필요함</option><option value="no">문맥만으로도 가능해 보임</option><option value="uncertain">판단 보류</option></select></label>
<label>근거·문제 구간·표기 제안 <textarea id="notes"></textarea></label><button id="save">이 문장 검수 저장</button></section>
<p><button id="previous">이전</button><button id="next">다음</button><button id="download">저장한 검수 JSON 내려받기</button></p>
<p id="status" role="status"></p><p class="muted">결과는 이 브라우저에 임시 보관됩니다. 브라우저 데이터를 지우기 전에 JSON을 내려받으세요. 서버 전송은 없습니다. 도구는 작성자의 청취 여부나 독립성을 자동 인증하지 않습니다.</p>
<script id="review-data" type="application/json">__PAYLOAD__</script><script>
const data=JSON.parse(document.getElementById('review-data').textContent), $=id=>document.getElementById(id);
const storageKey='tye-listening:'+data.reference_sha256;
let saved={}, index=0, revealed=false;
try{saved=JSON.parse(localStorage.getItem(storageKey)||'{}')}catch(e){}
for(const [i,row] of data.items.entries()) {const option=document.createElement('option');option.value=i;option.textContent=`${i+1}. ${row.id}`;$('utterance').append(option)}
function status(message=''){ $('status').textContent=`저장 ${Object.keys(saved).length} / ${data.items.length}문장 · ${message}`; }
function show(){const row=data.items[index], prior=saved[row.id];revealed=false;$('utterance').value=index;$('identity').textContent=`${data.dataset} / ${data.split} / ${row.id}`;$('player').src=row.audio;$('heard').value=prior?.heard_text_before_reveal||'';$('heard').disabled=false;$('texts').hidden=true;for(const id of ['referenceStatus','errorStatus','audioNeeded','notes']) $(id).value='';if(prior&& !$('reviewer').value)$('reviewer').value=prior.reviewer;status(prior?'이 문장은 저장된 검수 기록이 있습니다.':'아직 검수하지 않은 문장입니다.');}
$('reveal').onclick=()=>{if(!$('heard').value.trim()){status('먼저 들린 내용을 적어주세요.');return}const row=data.items[index];revealed=true;$('heard').disabled=true;$('reference').textContent=row.reference;$('draft').textContent=row.draft||'[빈 ASR 출력]';$('source').textContent='초안 생성기: '+row.source;$('texts').hidden=false;const prior=saved[row.id];if(prior)for(const [id,key]of [['referenceStatus','reference_status'],['errorStatus','error_status'],['audioNeeded','audio_needed'],['notes','notes']])$(id).value=prior[key]||'';};
$('save').onclick=()=>{if(!revealed||!$('reviewer').value.trim()||!$('referenceStatus').value||!$('errorStatus').value||!$('audioNeeded').value){status('청취 내용, 검수자와 모든 판단 항목을 입력해 주세요.');return}const row=data.items[index];saved[row.id]={id:row.id,reviewer:$('reviewer').value.trim(),heard_text_before_reveal:$('heard').value,reference_status:$('referenceStatus').value,error_status:$('errorStatus').value,audio_needed:$('audioNeeded').value,notes:$('notes').value,reviewed_at:new Date().toISOString(),independence:'self_reported_audio_first'};try{localStorage.setItem(storageKey,JSON.stringify(saved))}catch(e){}status('이 문장 검수를 저장했습니다. JSON으로도 내려받으세요.');};
$('utterance').onchange=()=>{index=Number($('utterance').value);show()};$('previous').onclick=()=>{index=Math.max(0,index-1);show()};$('next').onclick=()=>{index=Math.min(data.items.length-1,index+1);show()};
$('download').onclick=()=>{const result={dataset:data.dataset,split:data.split,reference_sha256:data.reference_sha256,input_sha256:data.input_sha256,reviewed_utterances:Object.keys(saved).length,total_utterances:data.items.length,all_reviewed:Object.keys(saved).length===data.items.length,review_type:'human_entered_not_automatically_verified',items:Object.values(saved)};const url=URL.createObjectURL(new Blob([JSON.stringify(result,null,2)+'\n'],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download=`${data.dataset}-${data.split}-listening-review.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};show();
</script></body></html>'''


def build(public, private, split):
    root = (private if split == 'test' else public) / split
    ref_path = private / 'test-references.json' if split == 'test' else root / 'references.json'
    manifest = json.loads(ref_path.read_text())
    refs = validate_manifest(manifest)
    inputs = {r['id']:r for r in json.loads((root / 'inputs.json').read_text())['items']}
    buckets = defaultdict(list)
    for row in refs:
        label = condition(aligned_slots(normalize(row['reference']),normalize(row['draft'])))
        buckets[(row['source'],label)].append(row)
    for bucket in buckets.values():
        bucket.sort(key=lambda r:hashlib.sha256(('listening-v2:'+r['id']).encode()).hexdigest())
    ordered = []
    for turn in range(max(map(len,buckets.values()))):
        for key in sorted(buckets):
            if turn < len(buckets[key]):
                ordered.append(buckets[key][turn])
    items = [dict(row,audio=('test/' if split == 'test' else '')+inputs[row['id']]['audio']) for row in ordered]
    payload = {'dataset':'tye-ko-asr-v2','split':split,'reference_sha256':digest(ref_path),
               'input_sha256':digest(root/'inputs.json'),'items':items}
    safe = json.dumps(payload,ensure_ascii=False).replace('<','\\u003c').replace('\u2028','\\u2028').replace('\u2029','\\u2029')
    target = private / 'test-review.html' if split == 'test' else root / 'review.html'
    target.write_text(TEMPLATE.replace('__PAYLOAD__',safe))
    if split == 'test':
        target.chmod(0o600)
    print(json.dumps({'split':split,'worksheet':str(target),'utterances':len(items),'human_review_completed':False}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--public',type=Path,required=True)
    parser.add_argument('--private',type=Path,required=True)
    parser.add_argument('--split',choices=('train','eval','test'),required=True)
    args = parser.parse_args()
    build(args.public,args.private,args.split)
