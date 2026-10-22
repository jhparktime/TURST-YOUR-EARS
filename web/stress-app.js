(() => {
  const $ = id => document.getElementById(id);
  const originals = new Map([...document.querySelectorAll('[data-t]')].map(n => [n,n.textContent]));
  const en = {
    subtitle:'Public Eval audio stress probe',back:'Return to actual-ASR v2',questionTitle:'Research question',
    question:'Does combining audio and a draft become more useful as audio quality changes? We also compare unnecessary edits to originally correct drafts.',
    scope:'Public development experiment only. The private Test and official ranking are unchanged. Compare five measured baselines across three audio conditions and score your own predictions.',
    pairing:'There are 409 distinct original recordings, totaling one hour. Each unchanged draft and reference is paired with three audio views: original, synthetic Gaussian noise at 5 dB, and 20% erasure of 20 ms packets. The 1,227 views contain the same 131 correct drafts and 278 erroneous drafts per condition.',
    limitation:'Drafts were generated from the original audio before corruption, so they may contain more information than the damaged audio. This differs from conventional post-processing where drafts come from the same noisy audio. Synthetic noise is not representative field noise, and not every damaged utterance is assumed recoverable by listening alone.',
    spec:'Construction and interpretation rules',download:'Download stress-track audio, drafts and references',copy:'1,227-row Copy CSV',
    benchmarks:'Measurements by audio condition',condition:'Audio condition',repair:'Slot restoration ↑',harm:'Harmful edits ↓',
    reuse:'Copy and Text-only use identical predictions across the three conditions because their drafts are unchanged. Original-audio outputs are reused only after input hashes and completion records match. Corrupted audio requires new inference.',
    gradeTitle:'Grade the public probe in this page',gradeText:'Select a UTF-8 CSV (id,prediction) containing all 1,227 variant IDs exactly once. The CSV stays in your browser. Scores are reported per condition and do not enter the official Test ranking.',
    csv:'Prediction CSV · maximum 2 MiB',grade:'Grade public probe',save:'Save full JSON',export:'The full JSON also separates originally correct drafts from erroneous drafts.',footer:'Public development probe · repeated measurements on 409 originals',
    loading:'Loading public references…',ready:'Ready: 1,227 views, 409 distinct originals.',choose:'Select a prediction CSV.',large:'The CSV exceeds 2 MiB.',scoring:'Scoring inside your browser…',done:'Scoring complete.',failed:'Scoring failed. Check the CSV and try again.',complete:'completed',pending:'pending',notCompleted:'Not completed'
  };
  const ko = {loading:'공개 정답을 불러오는 중입니다…',ready:'준비 완료: 변형 1,227개, 서로 다른 원본 409개입니다.',choose:'예측 CSV를 선택하세요.',large:'CSV가 2 MiB를 넘습니다.',scoring:'브라우저 안에서 채점 중입니다…',done:'채점이 끝났습니다.',failed:'채점에 실패했습니다. CSV를 확인하세요.',complete:'완료',pending:'미완료',notCompleted:'미완료'};
  let language='ko',manifest,pairing,baselines,lastResult,busy=false,state='loading',error='';
  const t = key => (language==='en'?en:ko)[key] || key;
  const pct = x => x===null || x===undefined ? 'N/A' : x.toFixed(2)+'%';
  function row(target,values){const r=document.createElement('tr');for(const value of values){const c=document.createElement('td');c.textContent=value;r.append(c)}target.append(r)}
  function render(){
    document.documentElement.lang=language;
    for(const [node,text]of originals)node.textContent=language==='en'?en[node.dataset.t]||text:text;
    $('language').textContent=language==='ko'?'English':'한국어';
    $('status').textContent=error||t(state);
    if(baselines){$('benchmarkStatus').textContent=`${baselines.entries.length} ${t('complete')} / ${baselines.pending.length} ${t('pending')}`;
      $('baselineRows').replaceChildren();const condition=$('condition').value;
      for(const entry of baselines.entries.filter(r=>r.condition===condition)){const m=entry.metrics;row($('baselineRows'),[entry.baseline,pct(m.micro_cer),pct(m.slot_restoration_rate),pct(m.harmful_edit_rate),pct(m.clean_change_rate)])}
      for(const entry of baselines.pending.filter(r=>r.condition===condition))row($('baselineRows'),[entry.baseline,t('notCompleted'),'—','—','—']);}
    $('result').hidden=!lastResult;
    if(lastResult){$('resultRows').replaceChildren();for(const [condition,value]of Object.entries(lastResult.by_condition)){const m=value.all;row($('resultRows'),[condition,pct(m.micro_cer),pct(m.slot_restoration_rate),pct(m.harmful_edit_rate),pct(m.clean_change_rate)])}}
  }
  $('language').onclick=()=>{language=language==='ko'?'en':'ko';render()};$('condition').onchange=render;
  $('grade').onclick=async()=>{
    if(busy)return;const file=$('file').files[0];if(!file){error=t('choose');render();return}if(file.size>2*1024*1024){error=t('large');render();return}
    busy=true;state='scoring';error='';lastResult=null;$('save').disabled=true;$('grade').disabled=true;render();
    let worker,timer;
    try{lastResult=await new Promise((resolve,reject)=>{worker=new Worker('public-stress-worker.js');timer=setTimeout(()=>reject(new Error(t('failed'))),60000);worker.onmessage=({data})=>data.error?reject(new Error(data.error)):resolve(data.result);worker.onerror=()=>reject(new Error(t('failed')));file.arrayBuffer().then(csv=>worker.postMessage({csv,manifest,pairing},[csv])).catch(reject)});state='done';$('save').disabled=false}
    catch(e){error=e.message}finally{clearTimeout(timer);worker?.terminate();busy=false;$('grade').disabled=false;render()}
  };
  $('save').onclick=()=>{if(!lastResult)return;const u=URL.createObjectURL(new Blob([JSON.stringify(lastResult,null,2)+'\n'],{type:'application/json'}));const a=document.createElement('a');a.href=u;a.download='tye-public-eval-stress-v1.scores.json';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000)};
  render();Promise.all(['eval.json','pair-index.json','baselines.json'].map(async name=>{const r=await fetch('data-stress/'+name);if(!r.ok)throw new Error(t('failed'));return r.json()})).then(values=>{[manifest,pairing,baselines]=values;if(manifest.name!=='tye-public-eval-stress-v1-eval'||manifest.items.length!==1227||pairing.items.length!==1227)throw new Error(t('failed'));state='ready';$('grade').disabled=false;render()}).catch(e=>{error=e.message;render()});
})();
