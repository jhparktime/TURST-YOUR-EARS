/* Explicit sharing: local scoring never publishes a participant's CSV. */
(()=>{
  const $=id=>document.getElementById(id), config=window.CHALLENGE_CONFIG_V2||{};
  const version=config.publicManifestSha256, boardURL=config.publicBoardUrl;
  let board=null, boardState='loading', file=null, packet='', store=null, storageFailed=false;
  try{store=TYEPublicResults.historyStore(localStorage,version)}catch{storageFailed=true}
  const strings={
    loading:['공동 기록을 불러오는 중입니다…','Loading shared records…'],
    unavailable:['공동 기록을 불러오지 못했습니다. 개인 채점은 계속 사용할 수 있습니다. 새로고침 버튼으로 다시 확인하세요.','Shared records could not be loaded. Local scoring is still available; use Refresh to retry.'],
    empty:['아직 등록된 참가 결과가 없습니다. 첫 결과를 등록해 보세요.','No participant results yet. Register the first result.'],
    noHistory:['저장된 개인 기록이 없습니다. CSV 또는 Copy 예제를 채점해 보세요.','No local history yet. Score a CSV or try Copy.'],
    storageFailed:['브라우저 저장소를 사용할 수 없어 개인 기록을 저장하지 못했습니다. 결과 JSON을 내려받아 보관하세요.','Browser storage is unavailable. Download your result JSON to keep a copy.'],
    saved:['최근 20개 채점 기록을 이 브라우저에 보관합니다. 공동 순위에는 별도 등록이 필요합니다.','The latest 20 results are saved in this browser. Shared ranking requires separate registration.'],
    ready:['묶음을 만들었습니다. 아래 내용을 복사한 뒤 GitHub 양식의 Result package 칸에 붙여 넣고 제출하세요.','Package ready. Copy it below, open the GitHub form, paste it into Result package and submit.'],
    fields:['팀명·방법·공개 HTTPS 코드 링크를 모두 입력하세요.','Enter a team name, method and public HTTPS code link.'],
    consent:['공개되는 항목을 확인하고 동의란을 선택하세요.','Read the sharing notice and check the consent box.'],
    size:['공유 묶음은 압축 후 60,000자 이하여야 합니다. 웹 채점 CSV의 최대 크기는 2 MiB입니다.','The compressed package must be at most 60,000 characters. Local scoring accepts CSVs up to 2 MiB.'],
    unsupported:['이 브라우저에서 묶음을 만들지 못했습니다. 최신 브라우저에서 다시 시도해 주세요.','Could not build the package in this browser. Try a current browser.'],
    copied:['복사했습니다. GitHub 양식에 붙여 넣어 제출하세요.','Copied. Paste it into the GitHub form and submit.'],
    copyManual:['자동 복사를 사용할 수 없습니다. 아래 묶음을 직접 선택해 복사하세요.','Clipboard unavailable. Select and copy the package below.'],
    accepted:['등록','Accepted'],duplicate:['동일 파일','Duplicate'],rejected:['반려','Rejected'],
    historyMore:['최근 제출 50건을 표시합니다. 전체 이력은 원본 JSON에 보관됩니다.','Showing the latest 50 submissions; the source JSON retains the full history.'],
    csvAgain:['공동 등록하려면 CSV 또는 Copy 예제를 먼저 채점하세요.','Score a CSV or the Copy example before preparing a shared submission.']
  };
  const en=()=>document.documentElement.lang==='en';
  const t=key=>strings[key]?.[en()?1:0]||key;
  const date=value=>new Date(value).toLocaleString(en()?'en-GB':'ko-KR',{timeZone:'Asia/Seoul',hour12:false})+' KST';
  function cell(row,text){const td=document.createElement('td');td.textContent=text;row.append(td);return td}
  function link(parent,text,url){const a=document.createElement('a');a.textContent=text;a.href=url;a.target='_blank';a.rel='noopener noreferrer';parent.append(a)}
  function render(){
    $('localHistoryRows').replaceChildren();
    const local=store?.read()||[];
    for(const item of local.slice().reverse()){const tr=document.createElement('tr');cell(tr,date(item.at));cell(tr,item.name);cell(tr,item.metrics.micro_cer.toFixed(4)+'%');cell(tr,Number.isFinite(item.metrics.harmful_edit_rate)?item.metrics.harmful_edit_rate.toFixed(2)+'%':'N/A');$('localHistoryRows').append(tr)}
    $('localHistoryStatus').textContent=t(storageFailed?'storageFailed':local.length?'saved':'noHistory');
    $('sharedStatus').textContent=boardState!=='ready'?t(boardState):board.entries.length?
      (en()?`${board.entries.length} teams · ${board.history.filter(r=>r.status==='accepted').length} accepted submissions · Updated ${date(board.updated_at)}`:`${board.entries.length}팀 · 유효 제출 ${board.history.filter(r=>r.status==='accepted').length}건 · 갱신 ${date(board.updated_at)}`):t('empty');
    $('sharedHistoryRows').replaceChildren();
    for(const item of (board?.history||[]).slice(-50).reverse()){
      const tr=document.createElement('tr');link(cell(tr,''),'#'+item.issue,`https://github.com/jhparktime/TURST-YOUR-EARS/issues/${item.issue}`);
      cell(tr,date(item.submitted_at));cell(tr,(item.team||'—')+' · @'+item.github_login);if(item.code_url)link(cell(tr,''),item.method,item.code_url);else cell(tr,item.method||'—');cell(tr,t(item.status)+(item.reason?' · '+item.reason:''));cell(tr,item.metrics?item.metrics.micro_cer.toFixed(4)+'%':'—');$('sharedHistoryRows').append(tr)
    }
    $('prepareShared').disabled=!file;
    $('sharedPackageHint').textContent=file?'':t('csvAgain');
    if($('sharedPackage').value) $('shareFeedback').textContent=t('ready');
  }
  function validateBoard(value){
    if(value?.schema!=='tye-public-board-v1'||value.manifest_sha256!==version||!Array.isArray(value.entries)||!Array.isArray(value.history))throw new Error('version');
    for(const row of value.entries)if(row.status!=='accepted'||!Number.isFinite(row.metrics?.micro_cer)||row.metrics.micro_cer<0||row.metrics.utterances!==409)throw new Error('metrics');
    return value;
  }
  async function refresh(){
    $('refreshShared').disabled=true;boardState='loading';render();
    try{const response=await fetch(boardURL+'?v='+Math.floor(Date.now()/60000),{cache:'no-store'});if(!response.ok)throw new Error('load');board=validateBoard(await response.json());boardState='ready'}catch{boardState='unavailable'}
    finally{$('refreshShared').disabled=false;render();document.dispatchEvent(new Event('tye:community'))}
  }
  function invalidate(){packet='';$('sharedPackage').value='';$('copySharedPackage').disabled=true;$('openSharedForm').hidden=true;$('shareFeedback').textContent=''}
  for(const id of ['sharedTeam','sharedMethod','sharedCode','sharedConsent'])$(id).addEventListener('input',invalidate);
  $('prepareShared').onclick=async()=>{
    invalidate();$('prepareShared').disabled=true;
    try{packet=await TYEPublicResults.makePackage(file,{team:$('sharedTeam').value,method:$('sharedMethod').value,code_url:$('sharedCode').value,version,consent:$('sharedConsent').checked});$('sharedPackage').value=packet;$('copySharedPackage').disabled=false;$('openSharedForm').hidden=false;$('shareFeedback').textContent=t('ready')}
    catch(error){$('shareFeedback').textContent=t(strings[error.message]?error.message:'unsupported')}
    finally{$('prepareShared').disabled=!file}
  };
  $('copySharedPackage').onclick=async()=>{if(!packet)return;try{await navigator.clipboard.writeText(packet);$('shareFeedback').textContent=t('copied')}catch{$('shareFeedback').textContent=t('copyManual')}};
  $('refreshShared').onclick=refresh;
  document.addEventListener('tye:render',render);
  window.TYECommunity={
    entries(){return (board?.entries||[]).map(row=>({baseline:row.team+' · @'+row.github_login+' / '+row.method,split:'eval',metrics:row.metrics,shared:true,issue:row.issue}))},
    reset(){file=null;invalidate();render()},
    record(metrics,context){
      file=context.file;invalidate();
      try{if(!store)throw new Error('storage');store.append(metrics,context.kind,context.name);storageFailed=false}catch{storageFailed=true}
      if(context.kind==='demo'&&!$('sharedMethod').value){$('sharedMethod').value='Copy draft';$('sharedCode').value='https://github.com/jhparktime/TURST-YOUR-EARS'}
      render();
    }
  };
  render();refresh();
})();
