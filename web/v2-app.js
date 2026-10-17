/* Plain workshop page. Public evaluation is local; private grading needs a verified API. */
(() => {
  const $ = id => document.getElementById(id);
  const english = {
    subtitle:'Korean Audio-grounded Transcript Correction Challenge',version:'Actual ASR errors · v2 candidate, not listening-reviewed',
    overview:'Challenge',data:'Dataset',evaluation:'Evaluation',baselines:'Benchmarks',submit:'Web evaluation',official:'Private Test',archive:'Synthetic v1 archive',
    overviewTitle:'Challenge overview',task:'Given Korean speech and a draft produced by a real speech recognizer, return a complete transcript matching the utterance. Correct recognition errors while preserving text that was already right.',
    candidate:'This is a v2 candidate. Automated integrity checks passed; independent listening review has not been performed. Benchmark difficulty and the necessity of audio have not been established.',
    research:'Research question: can audio-grounded decisions reduce real Korean ASR errors while avoiding unnecessary corrections?',
    stressLink:'Public Eval audio stress probe',
    stressDescription:'We keep the drafts of the same 409 recordings and vary audio quality to compare input combination and unnecessary edits. This is public development; the private Test is unchanged. The probe page reports model completion status and results by audio condition.',
    pipelineNav:'Pipeline',methodNav:'Method',referencesNav:'References',pipelineTitle:'Pipeline',
    pipelineSource:'Obtain original Korean audio and transcripts, then check speaker, session, exact-transcript and audio separation across splits.',
    pipelineDraft:'Whisper and Qwen generate drafts from audio alone. A fixed rule assigns the generator to each recording without consulting references or error rates.',
    pipelineCorrection:'The participant model receives audio and a draft and returns a complete corrected transcript. Reference transcripts are not model inputs.',
    pipelineScore:'Develop on public Eval and evaluate on private Test. The same scoring code measures character errors and damage to originally correct text.',
    methodTitle:'Baseline & Method',methodIntro:'Copying the draft and retranscribing audio provide reference points. We vary the inputs to the same Qwen model to assess the value of combining a draft with audio. These baselines use no additional training.',
    methodInput:'Model input',methodRole:'Comparison purpose',inputDraft:'Transcript draft',inputAudio:'Audio',inputBoth:'Audio + transcript draft',
    roleCopy:'Retain the draft without editing',roleWhisper:'Retranscribe with large-v3-turbo',roleAudio:'Transcribe with the same Qwen model, without a draft',roleText:'Correct the draft without audio',roleBoth:'Correct differences from the spoken utterance',
    methodSettings:'The three Qwen2.5-Omni-3B conditions use the same checkpoint, greedy generation, seed 0 and a 512-new-token limit. Empty and token-limited outputs are scored as produced. Reproduction code records model revisions and full prompts.',
    methodPrompts:'Input construction and prompts',methodRunner:'Qwen inference code',referencesTitle:'References',
    referencesIntro:'Source data, model and related ASR error-correction research. Combining audio with a draft is an input format also studied in prior work.',
    referenceData:' — source Korean read speech, CC BY 4.0',referenceModel:' — model for audio and text input comparisons',referencePaper:' — EMNLP 2025 Industry Track, Chinese ASR error-correction benchmark',
    spec:'Dataset, evaluation and listening-review specification',code:'Baseline and reproduction code',dataTitle:'Dataset',
    dataText:'Original recordings and source transcripts are retained. Drafts are actual audio-only outputs from Whisper large-v3-turbo and Qwen2.5-Omni-3B, assigned in equal proportions by a fixed rule. Recordings are not selected for high recognition error.',
    samples:'Recordings',duration:'Audio duration',access:'Reference access',
    dataSplit:'Existing speaker, session, exact-transcript and audio separation is retained. The source is Zeroth Korean public read speech (CC-BY-4.0), not spontaneous conversation or newly recorded speech.',
    download:'Download the unreviewed candidate dataset',copyDownload:'Public Eval Copy CSV',
    review:'The participant ZIP includes Train/Eval audio, drafts, references and an audio-first listening worksheet. Test references and review sheets are organizer-only. Numeric spelling, source-transcript errors and unclear speech require human review.',
    evalTitle:'Evaluation protocol',
    primary:'The ranking metric is Micro CER: total substitutions, deletions and insertions divided by total reference characters. Secondary Macro CER is the mean of utterance CERs. This differs from v1’s condition average; v1 and v2 scores are not comparable.',
    normalization:'Text is NFC-normalized and lowercased. Whitespace and specified punctuation are ignored; decimal points between digits remain. “3시” and “세 시” are scored as different forms. Secondary WER uses whitespace-delimited Korean eojeol.',
    metricRepair:'Error-slot restoration, correction precision and correction F1 measure repairs of incorrect character positions and insertion gaps.',
    metricHarm:'Harmful edits, unwanted insertions and Clean changes measure preservation of originally correct text.',
    metricGroups:'Results are reported by draft-error type and draft generator. Slot metrics use deterministic text alignment and do not certify acoustic correctness.',
    scorerLink:'Python evaluator',browserLink:'Browser evaluator',benchmarkTitle:'Baseline measurements',
    comparison:'Copy retains the distributed draft. Audio-only receives speech; Text-only and Audio+draft receive the new real-ASR draft. Incomplete experiments have no numeric score.',
    overlap:'An Audio-only recognizer that also generated the draft equals Copy on its own source subset. This is not independent correction success. Source-stratified CER is shown below.',
    splitLabel:'Displayed split',improvement:'Gain ↑',restoration:'Slot repair ↑',harm:'Harmful edits ↓',insertion:'Unwanted insertions ↓',sourceDetails:'CER by draft generator',
    benchmarkLimits:'Input conditions use the same Qwen checkpoint. Whisper versus Qwen changes both model and input. Exposure to the public source corpus during pretraining cannot be ruled out.',allMetrics:'All metrics, condition counts and denominators',
    publicTitle:'Public Eval — in-browser scoring',publicText:'Select a UTF-8 CSV covering all 409 public Eval IDs exactly once. The header must be id,prediction. Scoring runs in your browser; your CSV is not sent to a server.',
    csvLabel:'Prediction CSV (maximum 2 MiB)',scoreButton:'Score public Eval',saveButton:'Save all metrics as JSON',
    privateTitle:'Private Test — official submissions',privateClosed:'The private Test grading service is not connected. Official submissions and participant rankings are not open.',
    keyLabel:'Team key',privateCsv:'Test prediction CSV',privateButton:'Official submission',rank:'Rank',team:'Team',
    footer:'A Speech Recognition course Challenge project.',
    loading:'Loading public evaluation data…',ready:'Ready: 409 public Eval recordings.',loadFailed:'Could not load the evaluation data. Reload this page.',
    chooseFile:'Select a prediction CSV first.',tooLarge:'Maximum submission size is 2 MiB.',scoring:'Scoring in your browser…',
    scored:'Public Eval scoring completed.',pending:'Not completed',completed:'complete',pendingWord:'pending',public:'Public',private:'Private',
    privateOpen:'Official submissions are open for the verified v2 Test.',privateMismatch:'The configured service does not match this v2 Test. Contact the organizers.',
    privateScoring:'Submitting to the private grading service…',privateDone:'Submission scored.',noTeams:'No official participant submissions.',
    needKey:'Enter your organizer-issued team key.',failure:'Evaluation failed. Check your file and try again.',
    metric:'Metric',value:'Value',condition:'Draft-error type',n:'Recordings',restorationName:'Error-slot restoration',
    harmName:'Harmful edit rate',insertionName:'Unwanted insertion rate',cleanName:'Clean change rate',precisionName:'Correction precision',f1Name:'Correction F1',
    details:'All metrics and denominators',clean:'Clean',substitution:'Substitution only',deletion:'Deletion only',insertionOnly:'Insertion only',mixed:'Mixed',
  };
  const korean = {loading:'공개 평가 데이터를 불러오는 중입니다…',ready:'공개 Eval 409개 채점 준비가 됐습니다.',loadFailed:'평가 데이터를 불러오지 못했습니다. 페이지를 새로고침해 주세요.',
    chooseFile:'예측 CSV를 먼저 선택해 주세요.',tooLarge:'제출 파일은 최대 2 MiB입니다.',scoring:'브라우저에서 채점 중입니다…',scored:'공개 Eval 채점이 끝났습니다.',
    pending:'미완료',completed:'완료',pendingWord:'미완료',public:'공개',private:'비공개',privateOpen:'검증된 v2 Test의 공식 접수가 열렸습니다.',
    privateMismatch:'연결된 서비스가 이 v2 Test와 일치하지 않습니다. 운영자에게 문의해 주세요.',privateScoring:'비공개 채점 서비스에 제출하고 있습니다…',privateDone:'제출 채점이 끝났습니다.',
    noTeams:'공식 참가자 제출 기록이 없습니다.',needKey:'운영자가 발급한 팀 키를 입력해 주세요.',failure:'채점하지 못했습니다. 파일을 확인해 주세요.',
    metric:'지표',value:'값',condition:'초안 오류 유형',n:'녹음 수',restorationName:'오류 슬롯 복원률',harmName:'정상 문자 훼손률',insertionName:'불필요 삽입률',
    cleanName:'Clean 변경률',precisionName:'교정 정밀도',f1Name:'교정 F1',details:'전체 지표와 분자·분모',clean:'정상',substitution:'치환만',deletion:'누락만',insertionOnly:'삽입만',mixed:'혼합'};
  const originals = new Map([...document.querySelectorAll('[data-t]')].map(node => [node,node.textContent]));
  for(const [node,original]of originals)if(!(node.dataset.t in korean))korean[node.dataset.t]=original;
  let language='ko',manifest,metadata,baselines,lastResult,busy=false,privateState='privateClosed';
  let publicState='loading',publicError='';
  try{if(localStorage.getItem('tye-v2-language')==='en')language='en'}catch(e){}
  const t = key => language==='en' ? english[key]||key : korean[key]||english[key]||key;
  const percent = v => v === null || v === undefined ? 'N/A' : Number(v).toFixed(2)+'%';
  const cell = (row,value,numeric=false) => {const c=document.createElement('td');c.textContent=value;if(numeric)c.className='num';row.append(c);return c};
  function rowFor(body,values){const row=document.createElement('tr');values.forEach((value,i)=>cell(row,value,i>0));body.append(row);return row}
  function duration(seconds){const total=Math.round(seconds),h=Math.floor(total/3600),m=Math.floor(total%3600/60),s=total%60;return language==='en'?`${h}h ${m}m ${s}s`:`${h}시간 ${m}분 ${s}초`}
  function renderData(){if(!metadata)return;$('dataRows').replaceChildren();for(const split of ['train','eval','test']){const value=metadata.splits[split];rowFor($('dataRows'),[split,value.utterances,duration(value.duration_seconds),t(split==='test'?'private':'public'),percent(value.draft_micro_cer)])}}
  function renderBenchmarks(){if(!baselines)return;const split=$('benchmarkSplit').value;$('benchmarkRows').replaceChildren();$('sourceRows').replaceChildren();$('benchmarkStatus').textContent=`${baselines.entries.length} ${t('completed')} / ${baselines.pending.length} ${t('pendingWord')}`;
    for(const entry of baselines.entries.filter(e=>e.split===split)){const m=entry.metrics;rowFor($('benchmarkRows'),[entry.baseline,percent(m.micro_cer),percent(m.micro_wer),Number(m.cer_improvement_pp).toFixed(2)+(language==='en'?' pp':'%p'),percent(m.slot_restoration_rate),percent(m.harmful_edit_rate),percent(m.unwanted_insertion_rate)]);
      for(const [source,value]of Object.entries(m.sources))rowFor($('sourceRows'),[entry.baseline,source,value.utterances,percent(value.draft_cer),percent(value.cer)]);
    }
    for(const entry of baselines.pending.filter(e=>e.split===split)){const row=document.createElement('tr');cell(row,entry.baseline);const c=cell(row,t('pending'));c.colSpan=6;$('benchmarkRows').append(row)}
  }
  function metricTable(parent,values){const table=document.createElement('table');const head=table.createTHead().insertRow();for(const label of [t('metric'),t('value')]){const c=document.createElement('th');c.textContent=label;head.append(c)}const body=table.createTBody();for(const value of values)rowFor(body,value);parent.append(table)}
  function renderResult(){const box=$('publicResult');box.hidden=!lastResult;$('saveScores').disabled=!lastResult;box.replaceChildren();if(!lastResult)return;metricTable(box,[['Micro CER',percent(lastResult.micro_cer)],['Utterance Macro CER',percent(lastResult.macro_cer)],['WER',percent(lastResult.micro_wer)],
      [t('restorationName'),percent(lastResult.slot_restoration_rate)],[t('precisionName'),percent(lastResult.correction_precision)],[t('f1Name'),percent(lastResult.correction_f1)],
      [t('harmName'),percent(lastResult.harmful_edit_rate)],[t('insertionName'),percent(lastResult.unwanted_insertion_rate)],[t('cleanName'),percent(lastResult.clean_change_rate)]]);
    const table=document.createElement('table');const head=table.createTHead().insertRow();for(const text of [t('condition'),'N','Draft CER','Output CER']){const c=document.createElement('th');c.textContent=text;head.append(c)}const body=table.createTBody();for(const [key,value]of Object.entries(lastResult.conditions))rowFor(body,[t(key==='insertion'?'insertionOnly':key),value.utterances,percent(value.draft_cer),percent(value.cer)]);box.append(table);
    const details=document.createElement('details'),summary=document.createElement('summary'),pre=document.createElement('pre');summary.textContent=t('details');pre.textContent=JSON.stringify(lastResult,null,2);details.append(summary,pre);box.append(details);
  }
  function render(){document.documentElement.lang=language;for(const [node,original]of originals)node.textContent=language==='en'?english[node.dataset.t]||original:original;$('language').textContent=language==='ko'?'English':'한국어';$('language').setAttribute('aria-label',language==='ko'?'Switch to English':'한국어로 전환');$('publicStatus').textContent=publicError||t(publicState);$('privateStatus').textContent=t(privateState);renderData();renderBenchmarks();renderResult()}
  $('language').onclick=()=>{language=language==='ko'?'en':'ko';try{localStorage.setItem('tye-v2-language',language)}catch(e){}render()};$('benchmarkSplit').onchange=renderBenchmarks;
  function scorePublic(file){return new Promise((resolve,reject)=>{let url='public-eval-worker-v2.js',owned=false;if(window.TYE_V2_EMBEDDED){url=URL.createObjectURL(new Blob([window.TYE_V2_EMBEDDED.scorer+'\n'+window.TYE_V2_EMBEDDED.scorer_v2+'\n'+window.TYE_V2_EMBEDDED.worker],{type:'text/javascript'}));owned=true}const worker=new Worker(url);const close=()=>{clearTimeout(timer);worker.terminate();if(owned)URL.revokeObjectURL(url)};const timer=setTimeout(()=>{close();reject(new Error(t('failure')))},60000);worker.onmessage=({data})=>{close();data.error?reject(new Error(data.error)):resolve(data.result)};worker.onerror=()=>{close();reject(new Error(t('failure')))};file.arrayBuffer().then(csv=>worker.postMessage({csv,manifest},[csv])).catch(e=>{close();reject(e)})})}
  $('publicFile').onchange=()=>{lastResult=null;publicError='';publicState=manifest?'ready':'loading';render()};
  $('publicScore').onclick=async()=>{if(busy)return;lastResult=null;const file=$('publicFile').files[0];if(!file){publicError=t('chooseFile');render();return}if(file.size>2*1024*1024){publicError=t('tooLarge');render();return}busy=true;publicState='scoring';publicError='';$('publicScore').disabled=true;$('publicFile').disabled=true;render();try{lastResult=await scorePublic(file);publicState='scored';$('saveScores').disabled=false}catch(e){publicError=e.message}finally{busy=false;$('publicScore').disabled=false;$('publicFile').disabled=false;render()}};
  $('saveScores').onclick=()=>{if(!lastResult)return;const url=URL.createObjectURL(new Blob([JSON.stringify(lastResult,null,2)+'\n'],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='tye-ko-asr-v2-public-eval.scores.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};
  const config=window.CHALLENGE_CONFIG_V2||{},apiBase=(config.apiBase||'').replace(/\/$/,'');
  async function privateHealth(){const response=await fetch(apiBase+'/api/health');if(!response.ok)throw new Error(t('privateClosed'));const value=await response.json();if(value.mode!=='evaluation'||value.dataset!==(config.expectedDataset||'tye-ko-asr-v2-test')||value.scorer!=='ko-correction-v2'||value.primary_metric!=='micro_cer'||value.samples!==1750||value.dataset_version!==metadata.splits.test.references_sha256.slice(0,12))throw new Error(t('privateMismatch'));return value}
  async function leaderboard(){const response=await fetch(apiBase+'/api/leaderboard');if(!response.ok)return;const value=await response.json();$('officialRows').replaceChildren();for(const entry of value.entries||[])rowFor($('officialRows'),[entry.rank,entry.team,percent(entry.micro_cer)]);if(!value.entries?.length){const row=document.createElement('tr'),c=cell(row,t('noTeams'));c.colSpan=3;$('officialRows').append(row)}}
  $('privateForm').onsubmit=async event=>{event.preventDefault();if(!apiBase)return;const key=$('teamKey').value.trim(),file=$('privateFile').files[0];if(!key){$('privateResult').textContent=t('needKey');return}if(!file||file.size>2*1024*1024){$('privateResult').textContent=t(file?'tooLarge':'chooseFile');return}$('privateSubmit').disabled=true;$('privateResult').textContent=t('privateScoring');try{if(!(await privateHealth()).submission_open)throw new Error(t('privateClosed'));const body=new FormData();body.append('file',file);const response=await fetch(apiBase+'/api/submissions',{method:'POST',headers:{Authorization:'Bearer '+key},body});const value=await response.json();if(!response.ok)throw new Error(typeof value.detail==='string'?value.detail:t('failure'));$('privateResult').textContent=t('privateDone')+'\n'+JSON.stringify(value,null,2);await leaderboard()}catch(e){$('privateResult').textContent=e.message}finally{$('privateSubmit').disabled=privateState!=='privateOpen'}};
  async function read(name){if(window.TYE_V2_EMBEDDED)return window.TYE_V2_EMBEDDED[name];const file={manifest:'eval.json',metadata:'metadata.json',baselines:'baselines.json'}[name];const response=await fetch('data-v2/'+file);if(!response.ok)throw new Error(t('loadFailed'));return response.json()}
  render();Promise.all([read('manifest'),read('metadata'),read('baselines')]).then(async values=>{[manifest,metadata,baselines]=values;if(manifest.protocol!=='ko-correction-v2'||manifest.items.length!==409||metadata.name!=='tye-ko-asr-v2'||baselines.protocol!=='ko-correction-v2')throw new Error(t('loadFailed'));publicState='ready';$('publicScore').disabled=false;if(window.TYE_V2_EMBEDDED?.copy_csv)for(const a of document.querySelectorAll('[data-copy-link]'))a.href='data:text/csv;base64,'+window.TYE_V2_EMBEDDED.copy_csv;render();if(apiBase){try{const health=await privateHealth();privateState=health.submission_open?'privateOpen':'privateClosed';if(health.submission_open)for(const id of ['teamKey','privateFile','privateSubmit'])$(id).disabled=false;await leaderboard()}catch(e){privateState=e.message===t('privateMismatch')?'privateMismatch':'privateClosed'}render()}}).catch(()=>{publicState='loadFailed';render()});
})();
