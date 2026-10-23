/* Plain workshop page. Public evaluation is local; private grading needs a verified API. */
(() => {
  const $ = id => document.getElementById(id);
  const english = {
    whyNav:"Why participate?",
    whyTitle:"Can your model fix mistakes without making new ones?",
    whyIntro:"The challenge goes beyond making text sound natural. When audio and the draft disagree, decide what to trust and preserve the parts that are already correct.",
    whyListen:"01 \u00b7 Listen before you build",
    whyListenText:"Real ASR errors appear alongside drafts that are already correct. Make a choice on two examples, then compare it with actual model outputs.",
    whyListenCTA:"Try two recordings \u2192",
    whyFeedback:"02 \u00b7 What did you repair, and what did you damage?",
    whyFeedbackText:"Compare ranks by Micro CER, then inspect error-slot restoration and harmful edits separately to understand repair and preservation. Use that feedback to choose your next improvement.",
    whyFeedbackCTA:"Try scoring and diagnostics without installation \u2192",
    whyStart:"03 \u00b7 Start with Copy, then challenge Whisper",
    whyStartText:"Score Copy in your browser without signing in, then build your first prediction CSV with the CPU notebook. Shared registration retains team bests and submission history; it requires GitHub sign-in.",
    whyStartCTA:"Build your first correction model \u2192",
    platformSummary:"How does this compare with Kaggle and Codabench?",
    platformIntro:"Both platforms support custom scoring and leaderboards. Our distinction is the task and participant experience: a focused path from listening to Korean speech, to correcting transcripts, to inspecting repair and preservation.",
    platformAspect:"Aspect",
    platformGeneral:"Kaggle / Codabench",
    platformOurs:"Our implementation",
    platformTask:"Task",
    platformTaskGeneral:"General competition platforms where organizers define the data and task",
    platformTaskOurs:"Korean audio + actual ASR draft \u2192 correct only what needs correcting",
    platformScore:"Scoring feedback",
    platformScoreGeneral:"Organizer-configured scoring; Codabench supports multiple metric columns",
    platformScoreOurs:"Micro CER ranking + diagnostics for error repair and preservation",
    platformFlow:"First attempt",
    platformFlowGeneral:"Submit predictions and inspect results on the platform",
    platformFlowOurs:"Listening quiz \u2192 browser scoring \u2192 CPU notebook \u2192 shared registration",
    platformOperation:"Current operation",
    platformOperationGeneral:"Configure competitions, submissions and leaderboards on the platform",
    platformOperationOurs:"GitHub Pages + Actions re-scoring. Shared Eval is a public development board; Private Test is evaluated separately by organizers",
    platformLimits:"Eval references are distributed for development and reproduction. Shared registration publishes prediction CSVs and methods and requires a GitHub form submission. Online Private Test submission is currently not connected.",
    platformSources:"Official documentation:",
    platformDoc:"Comparison evidence and operating scope",
    diagnosticNote:"Rank is determined by Micro CER. These two diagnostics describe error repair and preservation of correct content.",

    sharedLimits:"Use one representative GitHub account per team. Five new valid submissions per account per day (reset 00:00 KST); identical CSVs do not count. Compressed packages are limited to 60,000 characters. Check the shared history for processing status.",
    openSharedLabel:"Open GitHub submission form ↗",
    copySharedLabel:"Copy package",
    sharedPackageLabel:"Package to paste into the GitHub form",
    prepareSharedLabel:"Create submission package",
    sharedConsentText:"I agree to publish the team, GitHub account, method, code link and prediction CSV, and have followed the competition rules. No Test files or secret keys are included.",
    sharedCodeLabel:"Public code or reproduction link (HTTPS)",
    sharedMethodLabel:"Model or method (up to 160 characters)",
    sharedTeamLabel:"Team name (up to 60 characters)",
    sharedIntro:"1. Score a CSV. 2. Create and copy the package below. 3. Paste it into the GitHub form and submit. GitHub sign-in is required. Automatic re-scoring updates the shared standings and history.",
    sharedTitle:"Register your result in the shared standings",
    fileLabel:"File or example",
    localHistoryTitle:"Scoring history in this browser",
    sharedRaw:"Full shared history (JSON)",
    sharedHistoryNote:"Showing the latest 50 submissions, including duplicates and rejections. The source JSON retains the full history.",
    statusLabel:"Status",
    methodLabel:"Method",
    teamAccountLabel:"Team · account",
    timeLabel:"Time",
    recordLabel:"Submission",
    sharedHistoryTitle:"Participant submission history",
    sharedScope:"Shared standings use each team’s best CSV re-scored by GitHub Actions. Entries appear alongside baselines and cover Public Eval only.",
    sharedRegisterLink:"Register my result",
    refreshSharedLabel:"Refresh shared records",
    metaTeam:"Team",metaMembers:"Members",metaMetric:"Primary metric",metaOutput:"Output",
    baselineStart:"Start with the notebook or Copy example",
    baselineQuestionsTitle:"Start here",
    baselineQuestionCopy:"Check the workflow: create a prediction CSV with the CPU training notebook or Copy example, then score it on the website. You can also try the Copy demo without installing anything.",
    baselineQuestionASR:"First performance target: achieve lower CER than copying the draft unchanged. Copy scores about 11.77% CER on public Eval.",
    baselineQuestionBoth:"Next challenge: beat Whisper, the strongest provided baseline at about 6.19% CER on public Eval. Extend the audio+draft example with your own approach.",
    baselineMeasured:"Compare your score with these references in the leaderboard. The three Qwen examples offer starting code for different approaches, with measured scores shown alongside them. All five methods cover all 409 Eval and 1,750 Test recordings.",
    baselineExecutionTitle:"Execution, training and reproduction",
    baselineExecution:"Pretrained models run without additional training or reference transcripts at inference. Predictions are written to CSV and scored separately. Model, input and output hashes are recorded; empty and token-limited outputs are scored as produced.",
    baselineStarter:"The CPU token-replacement notebook learns from Train as a starter example and is separate from the five measured rows above.",
    baselineGuide:"Execution code, commands and reference scores",
    collectionSource:"Public source: audio and distributed transcripts come from a pinned Zeroth Korean revision. Original 16 kHz mono PCM samples are preserved in WAV files; transcripts receive NFC normalization only.",
    collectionMerge:"Merging and splitting: 2,079 existing and 2,002 additional recordings formed a pool of 4,081; 2,631 are used in Train/Eval/Test. Checks covered cross-split speakers, sessions, identical/near transcripts and audio. The remaining 1,450 are organizer-only reserves.",
    collectionDraft:"Actual drafts: fixed Whisper and Qwen models receive audio alone. Generators alternate in hashed ID order without consulting references or error rates. Eval has 205 Whisper and 204 Qwen drafts, including all 131 normalized-correct drafts.",
    collectionCheck:"Integrity checks: all 2,631 active recordings were checked for decoding, duration and checksums, unchanged references and agreement between drafts and recorded model outputs. Copy/reference invariants and Python/browser scores were also compared.",
    collectionRelease:"Distribution: participants receive Train/Eval audio, drafts, references, attribution and checksums. Test references, source mappings and reserves remain organizer-only. The five evaluation hours are one-hour Eval plus four-hour Test; about 1 h 13 min of Train is additional.",
    collectionTitle:"How we built the dataset",
    collectionPinned:"Pinned source revision",
    collectionHistoryTitle:"What changed from the previous version?",
    collectionHistory:"V2 replaces synthetic v1 word substitutions with actual ASR outputs while retaining recordings, references and splits. The inherited Eval/Test pool was originally selected for eligible synthetic substitutions. This history is separate from reference-blind v2 generator assignment and is documented with the scope of validation.",
    collectionRecord:"Full collection, merging, splitting and draft-generation record",
    collectionMetadata:"Counts, durations and model revisions",
    comparisonData:"Output strings, metrics and source hashes",
    comparisonDenominator:"Scores show errors / normalized reference characters and CER. Highlighting is explanatory; recorded output strings are unchanged.",
    comparisonScope:"These two cases illustrate correction and preservation. On the full Eval split, Whisper scores 6.19% CER and Qwen audio+draft 13.54%. Selected successes do not imply overall superiority. Participant inputs contain neither answers nor marked edit positions.",
    comparisonKeep:"The Qwen draft correctly says “랜섬웨어”. Whisper retranscription changes it to “랜선웨어”, while audio+draft preserves the correct content. CER ignores spaces and punctuation.",
    comparisonRepair:"Here the Whisper draft and its retranscription both say “생성”. Qwen audio+draft corrects it to “생산”. Copy and Whisper are identical because Whisper generated this draft.",
    comparisonMetric:"Character errors · CER ↓",
    comparisonTranscript:"Actual output transcript",
    comparisonCaption:"Recorded baseline outputs for the same utterance",
    showComparison:"How did three actual systems respond?",
    flowCaption:"Compare the audio and draft, correct errors and preserve accurate content.",
    flowTranscript:"Complete corrected transcript",
    flowKeep:"Keep correct content",
    flowEdit:"Fix recognition errors",
    flowAudioDraft:"Korean audio + ASR draft",
    chooseEdit:"Correct it",chooseKeep:"Keep it",showAnswer:"Answer and explanation",commandGuide:"Reproduce Copy from the command line",
    resultMore:"Detailed metrics and error types",
    demoLoading:"Loading and scoring the Copy CSV…",
    benchmarkCaption:"Organizer baselines and re-scored shared entries · lower CER is better · CER and harmful edits are percentages",
    gainContext:"CER gain over Copy (percentage points)",
    rankContext:"Comparison rank in the displayed Eval table",
    demoName:"Copy demo (local)",
    localName:"Your result (local)",
    quizKeepWrong:"Keep this content. Compare the new error introduced by retranscription below.",
    quizKeepCorrect:"Correct. 랜섬웨어 is already right. Compare it with the retranscription below.",
    quizRepairWrong:"The draft misrecognizes 생산되는 as 생성되는. Compare the results below.",
    quizRepairCorrect:"Correct. Change 생성되는 to 생산되는. Compare the actual systems below.",
    demoButton:"Score the Copy baseline",
    rulesSources:"Rule structure informed by Kaggle Competitions and DrivenData. This course project is not affiliated with either platform.",
    fullRules:"Full rules & reporting issues",
    ruleOperations:"Operations: local scoring is unlimited and retains the latest 20 results in this browser. Shared Eval allows five new valid submissions per representative account per day, reset 00:00 KST; identical CSVs do not count. Team bests and processing history are public.",
    ruleReproduce:"Reproducibility: accompany shared results with code, model and parameters, training data, seed and runtime environment. Use the same inference procedure for all evaluation recordings.",
    ruleRanking:"Ranking: ascending unrounded Micro CER; exact ties share ranks (1, 2, 2, 4). Secondary metrics are not combined into a weighted score. Eval and Test rankings are separate.",
    ruleCSV:"Submission: UTF-8 CSV, header id,prediction, each of 409 Eval IDs once, maximum 2 MiB. Include complete transcripts without explanations; use standard CSV quoting.",
    ruleExternal:"External resources: public pretrained models and external data are allowed. Disclose versions, licenses and sources. Exclude Eval/Test source recordings and derivatives from added training. Declare unknown pretraining exposure.",
    ruleData:"Training: fit on Train references and use Eval for development and scoring. Do not feed Eval/Test answers into inference, build answer lookups by ID, or manually correct evaluated predictions.",
    ruleTeam:"Teams: one or two members; one team per person. Identify the team and method when sharing results.",
    rulesIntro:"Public Eval scoring is unlimited. The following rules keep comparisons fair.",
    rulesTitle:"Competition rules",
    privatePolicy:"The private Test contains 1,750 recordings / four hours for organizer-run final evaluation. Its leaderboard values are fixed baseline measurements. Public Eval and browser scoring are available now. An online Test round will have a separate schedule and team-key announcement.",
    methodCTA:"Baseline configurations",
    leaderboardNote:"Compare organizer baselines, each registered team’s best result and your current local result. Shared registration requires a separate submission. Exactly equal unrounded CER values share a rank.",
    rulesCTA:"Read the rules",
    notebookScope:"The CPU example is a text-only starter, separate from the Qwen models in the leaderboard.",
    evalNotebook:"02 Evaluation notebook",
    trainNotebook:"01 Training & inference notebook",
    stepNotebookText:"The first notebook learns token replacements from Train and generates an Eval CSV. The second scores Copy and your predictions. Python 3.12+, no extra packages required.",
    stepNotebook:"Open a notebook — start without a GPU",
    exampleTwo:"When retranscription changes a correct draft",
    exampleOne:"One word retranscription missed",
    challengeInvite:"Compare copying, retranscription and learned correction under the same protocol. Whisper leads the measured public Eval baselines at 6.19% CER. Can your approach beat this reference?",
    notebookCTA:"③ Build your own corrector",
    demoCTA:"② Try scoring, no setup",
    listenCTA:"① Try two recordings",
    factRanking:"Ranking: lower Micro CER is better",
    factOutput:"Complete corrected transcript",
    factInput:"Korean audio + ASR draft",
    rulesNav:"Competition rules",
    atAGlance:"Korean · Real ASR drafts · Train 472 / Eval 409 / Test 1,750 · Browser scoring · Korean / English",
    skip:'Skip to content',startNav:'Get started',examplesNav:"Listen & try",
    statusPublicLabel:'Public Eval:',statusPublic:'In-browser scoring available for 409 recordings',
    startLink:'Get started →',scoreLink:'Score public Eval →',startTitle:"Get started with your model",
    stepData:"Get audio data and model code",
    stepDataText:"The participant ZIP provides Train/Eval audio, drafts and references. Run Whisper or Qwen, or build a model combining speech and drafts. Verify the ZIP using the supplied SHA-256 file.",
    startDownload:"Download participant data",stepRun:'Create a baseline CSV',
    stepRunText:'Use Python 3.12 or newer. Extract the ZIP into a tye-v2 folder beside the repository. Copy requires no extra packages or GPU.',
    stepExpected:"Copy scores 11.7663% Micro CER on public Eval.",
    runGuide:"Model execution guide",stepScore:"Score and compare on the website",
    stepScoreText:"Create a UTF-8 CSV with the id,prediction header and all 409 Eval predictions. View CER, repair and preservation metrics on the website and save the JSON.",
    startScore:"Go to public Eval scoring",startCopy:'Download a ready-made Copy CSV',
    examplesTitle:"Listen and decide: correct it or keep it?",
    examplesIntro:"Listen and make a choice. Then compare copying the draft, Whisper retranscription and Qwen audio+draft correction on the same recording.",
    exampleRepair:"First example recording",examplePreserve:"Second example recording",exampleDraft:'ASR draft',exampleReference:"Reference transcript",
    exampleRepairNote:"일상화탄소 → 일산화탄소. Correct the misrecognized word.",
    examplePreserveNote:"Keep this draft. CER ignores spaces and punctuation, so it has no character errors. Rewording correct content can increase the error rate.",
    exampleAttribution:"Audio and reference transcripts: Zeroth Korean (CC BY 4.0). Original audio and actual model outputs.",
    exampleSource:'Source corpus',
    dataLimits:"Reference policy: scoring uses the transcripts distributed with Zeroth Korean. Recordings and source transcripts are retained. Numeric spelling and spacing follow the normalization rules below. Report reference issues with an utterance ID and evidence via GitHub Issues; corrections receive a version and changelog.",
    privateSummaryClosed:"Organizer evaluation",privateSummaryOpen:'Official submissions open',
    subtitle:'Korean Audio-grounded Transcript Correction Challenge',version:"Fix the errors. Keep what was right.",
    overview:'Challenge',data:'Dataset',evaluation:'Evaluation',baselines:'Benchmarks',submit:'Web evaluation',official:'Private Test',archive:'Synthetic v1 archive',
    overviewTitle:"Can your model catch a speech recognizer’s mistakes?",task:"A plausible sentence can still mishear the speaker. Given Korean audio and an ASR draft, return a full transcript that fixes recognition errors while keeping correct text.",
    stressLink:'More to try: audio stress track →',
    stressDescription:'What changes when the same drafts are paired with noisy or packet-dropped audio? Compare five methods across three audio conditions of 409 originals and score your predictions.',
    pipelineNav:'Pipeline',methodNav:'Method',referencesNav:'References',pipelineTitle:'Pipeline',
    pipelineSource:'Obtain original Korean audio and transcripts, then check speaker, session, exact-transcript and audio separation across splits.',
    pipelineDraft:'Whisper and Qwen generate drafts from audio alone. A fixed rule assigns the generator to each recording without consulting references or error rates.',
    pipelineCorrection:'The participant model receives audio and a draft and returns a complete corrected transcript. Reference transcripts are not model inputs.',
    pipelineScore:'Develop on public Eval and evaluate on private Test. The same scoring code measures character errors and damage to originally correct text.',
    methodTitle:"Baselines for participants",methodIntro:"Baselines provide runnable starting points and performance references for your model. Run an example to learn the submission workflow, then aim to improve on Copy and Whisper.",
    methodInput:'Model input',methodRole:"How to use it",inputDraft:'Transcript draft',inputAudio:'Audio',inputBoth:'Audio + transcript draft',
    roleCopy:"Check submission and scoring; first performance reference",roleWhisper:"A speech-recognition baseline to beat",roleAudio:"Runnable example using audio alone",roleText:"Runnable example correcting a draft alone",roleBoth:"Runnable example correcting with audio and a draft",
    methodSettings:'The three Qwen2.5-Omni-3B conditions use the same checkpoint, greedy generation, seed 0 and a 512-new-token limit. Empty and token-limited outputs are scored as produced. Reproduction code records model revisions and full prompts.',
    methodPrompts:'Input construction and prompts',methodRunner:'Qwen inference code',referencesTitle:'References',
    referencesIntro:"Source data, models and related ASR correction research.",
    referenceData:' — source Korean read speech, CC BY 4.0',referenceModel:' — model for audio and text input comparisons',referencePaper:' — EMNLP 2025 Industry Track, Chinese ASR error-correction benchmark',
    spec:'Dataset, evaluation and listening-review specification',code:'Baseline and reproduction code',dataTitle:'Dataset',
    dataText:'Original recordings and source transcripts are retained. Drafts are actual audio-only outputs from Whisper large-v3-turbo and Qwen2.5-Omni-3B, assigned in equal proportions by a fixed rule. Recordings are not selected for high recognition error.',
    samples:'Recordings',duration:'Audio duration',access:'Reference access',
    dataSplit:'Existing speaker, session, exact-transcript and audio separation is retained. The source is Zeroth Korean public read speech (CC-BY-4.0), not spontaneous conversation or newly recorded speech.',
    download:"Download participant data",copyDownload:'Public Eval Copy CSV',
    review:"The participant ZIP includes Train/Eval audio, drafts, references, attribution and checksums. Test references and individual predictions are organizer-only. This read-speech dataset does not represent every conversational or domain setting.",
    evalTitle:'Evaluation protocol',
    primary:"Primary Micro CER is total substitutions, deletions and insertions divided by total reference characters. Lower is better. Macro CER averages utterance CERs; it and WER are secondary diagnostics. Archived v1 results use a different protocol and are not ranked together.",
    normalization:'Text is NFC-normalized and lowercased. Whitespace and specified punctuation are ignored; decimal points between digits remain. “3시” and “세 시” are scored as different forms. Secondary WER uses whitespace-delimited Korean eojeol.',
    metricRepair:'Error-slot restoration, correction precision and correction F1 measure repairs of incorrect character positions and insertion gaps.',
    metricHarm:'Harmful edits, unwanted insertions and Clean changes measure preservation of originally correct text.',
    metricGroups:'Results are reported by draft-error type and draft generator. Slot metrics use deterministic text alignment and do not certify acoustic correctness.',
    scorerLink:'Python evaluator',browserLink:'Browser evaluator',benchmarkTitle:'Baseline measurements',
    comparison:"Compare your model with organizer reference scores and registered team bests. Start by beating Copy, then aim for Whisper. Score your CSV for an immediate comparison, and register it to share the record with other participants.",
    overlap:"Whisper and Qwen also generated the drafts. Each model’s Audio-only output equals Copy on its own source subset. Compare both overall and source-specific results.",
    splitLabel:'Displayed split',improvement:'Gain ↑',restoration:'Slot repair ↑',harm:'Harmful edits ↓',insertion:'Unwanted insertions ↓',sourceDetails:'CER by draft generator',
    benchmarkLimits:"The three Qwen conditions use the same checkpoint. Pretraining exposure to the public source corpus cannot be ruled out.",allMetrics:"All metrics and condition results (JSON)",
    publicTitle:"Public Eval — score on the website",publicText:"Try Copy to score all 409 drafts. Scoring alone processes files locally and saves the latest 20 results in this browser. Shared registration is separate; read the public-sharing notice below before submitting.",
    csvLabel:'Prediction CSV (maximum 2 MiB)',scoreButton:'Score public Eval',saveButton:'Save all metrics as JSON',
    privateTitle:'Private Test — official submissions',privateClosed:"Private Test uses organizer-run evaluation; public Eval scoring is available above.",
    keyLabel:'Team key',privateCsv:'Test prediction CSV',privateButton:'Official submission',rank:'Rank',team:'Team',
    footer:'A Speech Recognition course Challenge project.',
    loading:'Loading public evaluation data…',ready:'Ready: 409 public Eval recordings.',loadFailed:'Could not load the evaluation data. Reload this page.',
    chooseFile:'Select a prediction CSV first.',tooLarge:'Maximum submission size is 2 MiB.',scoring:'Scoring in your browser…',
    scored:"Public Eval scoring completed. Your comparison is also shown in the leaderboard.",pending:'Not completed',completed:'complete',pendingWord:'pending',public:'Public',private:'Private',
    privateOpen:'Official submissions are open for the verified v2 Test.',privateMismatch:'The configured service does not match this v2 Test. Contact the organizers.',
    privateScoring:'Submitting to the private grading service…',privateDone:'Submission scored.',noTeams:'No official participant submissions.',
    needKey:'Enter your organizer-issued team key.',failure:'Evaluation failed. Check your file and try again.',
    metric:'Metric',value:'Value',condition:'Draft-error type',n:'Recordings',restorationName:'Error-slot restoration',
    harmName:'Harmful edit rate',insertionName:'Unwanted insertion rate',cleanName:'Clean change rate',precisionName:'Correction precision',f1Name:'Correction F1',
    details:'All metrics and denominators',clean:'Clean',substitution:'Substitution only',deletion:'Deletion only',insertionOnly:'Insertion only',mixed:'Mixed',
  };
  const korean = {
    diagnosticNote:"순위는 Micro CER로 정합니다. 아래 두 지표는 오류 수정과 정상 부분 보존을 설명하는 보조 지표입니다.",
    exampleRepair:'첫 번째 예시 음성',examplePreserve:'두 번째 예시 음성',
    privateClosed:'비공개 Test는 운영자 평가용입니다. 현재 공개 Eval 웹 채점을 이용할 수 있습니다.',
    quizRepairCorrect:"맞습니다. 생성되는 → 생산되는. 아래 실제 모델 결과와 비교해 보세요.",
    quizRepairWrong:"이 초안에는 생성되는 → 생산되는 인식 오류가 있습니다. 아래 결과를 비교해 보세요.",
    quizKeepCorrect:"맞습니다. 랜섬웨어는 맞는 표현입니다. 아래 재전사 결과와 비교해 보세요.",
    quizKeepWrong:"내용을 유지하면 됩니다. 아래 결과에서 재전사가 만든 새 오류를 확인해 보세요.",
    localName:'내 결과 (브라우저)',demoName:'Copy 체험 (브라우저)',rankContext:'표시된 Eval 표에서의 비교 순위',
    gainContext:'Copy 대비 CER 개선 (%p)',benchmarkCaption:'운영자 베이스라인과 재채점한 공동 기록 · CER가 낮을수록 높은 순위 · CER·훼손률 단위 %',
    demoLoading:'Copy CSV를 불러와 채점하고 있습니다…',resultMore:'상세 지표·오류 유형',
loading:'공개 평가 데이터를 불러오는 중입니다…',ready:'공개 Eval 409개 채점 준비가 됐습니다.',loadFailed:'평가 데이터를 불러오지 못했습니다. 페이지를 새로고침해 주세요.',
    privateSummaryClosed:'운영자 평가',privateSummaryOpen:'공식 접수 중',
    chooseFile:'예측 CSV를 먼저 선택해 주세요.',tooLarge:'제출 파일은 최대 2 MiB입니다.',scoring:'브라우저에서 채점 중입니다…',scored:'공개 Eval 채점이 끝났습니다. 리더보드에서도 내 결과를 비교할 수 있습니다.',
    pending:'미완료',completed:'완료',pendingWord:'미완료',public:'공개',private:'비공개',privateOpen:'검증된 v2 Test의 공식 접수가 열렸습니다.',
    privateMismatch:'연결된 서비스가 이 v2 Test와 일치하지 않습니다. 운영자에게 문의해 주세요.',privateScoring:'비공개 채점 서비스에 제출하고 있습니다…',privateDone:'제출 채점이 끝났습니다.',
    noTeams:'공식 참가자 제출 기록이 없습니다.',needKey:'운영자가 발급한 팀 키를 입력해 주세요.',failure:'채점하지 못했습니다. 파일을 확인해 주세요.',
    metric:'지표',value:'값',condition:'초안 오류 유형',n:'녹음 수',restorationName:'오류 슬롯 복원률',harmName:'정상 문자 훼손률',insertionName:'불필요 삽입률',
    cleanName:'Clean 변경률',precisionName:'교정 정밀도',f1Name:'교정 F1',details:'전체 지표와 분자·분모',clean:'정상',substitution:'치환만',deletion:'누락만',insertionOnly:'삽입만',mixed:'혼합'};
  const originals = new Map([...document.querySelectorAll('[data-t]')].map(node => [node,node.textContent]));
  for(const [node,original]of originals)if(!(node.dataset.t in korean))korean[node.dataset.t]=original;
  let language='ko',manifest,metadata,baselines,lastResult,busy=false,privateState='privateClosed';
  let publicState='loading',publicError='',resultKind='local';
  try{if(localStorage.getItem('tye-v2-language')==='en')language='en'}catch(e){}
  const t = key => language==='en' ? english[key]||key : korean[key]||english[key]||key;
  const percent = v => v === null || v === undefined ? 'N/A' : Number(v).toFixed(2)+'%';
  const cell = (row,value,numeric=false) => {const c=document.createElement('td');c.textContent=value;if(numeric)c.className='num';row.append(c);return c};
  function rowFor(body,values){const row=document.createElement('tr');values.forEach((value,i)=>cell(row,value,i>0));body.append(row);return row}
  function duration(seconds){const total=Math.round(seconds),h=Math.floor(total/3600),m=Math.floor(total%3600/60),s=total%60;return language==='en'?`${h}h ${m}m ${s}s`:`${h}시간 ${m}분 ${s}초`}
  function renderData(){if(!metadata)return;$('dataRows').replaceChildren();for(const split of ['train','eval','test']){const value=metadata.splits[split];rowFor($('dataRows'),[split,value.utterances,duration(value.duration_seconds),t(split==='test'?'private':'public'),percent(value.draft_micro_cer)])}}
  function renderBenchmarks(){if(!baselines)return;const split=$('benchmarkSplit').value;$('benchmarkRows').replaceChildren();$('sourceRows').replaceChildren();$('benchmarkStatus').textContent=t('benchmarkCaption');
    for(const entry of TYELeaderboard.rank([...baselines.entries,...(window.TYECommunity?.entries()||[])],split,lastResult)){const m=entry.metrics;
      const row=document.createElement('tr');cell(row,entry.rank,true);cell(row,entry.local?t(resultKind==='demo'?'demoName':'localName'):entry.baseline);cell(row,percent(m.micro_cer),true);cell(row,Number(m.cer_improvement_pp).toFixed(2)+(language==='en'?' pp':'%p'),true);cell(row,percent(m.harmful_edit_rate),true);if(entry.local)row.className='my-result';if(entry.shared)row.className='shared-result';$('benchmarkRows').append(row);
      if(!entry.local)for(const [source,value]of Object.entries(m.sources||{}))rowFor($('sourceRows'),[entry.baseline,source,value.utterances,percent(value.draft_cer),percent(value.cer)]);
    }
  }
  function metricTable(parent,values){const table=document.createElement('table');const head=table.createTHead().insertRow();for(const label of [t('metric'),t('value')]){const c=document.createElement('th');c.textContent=label;head.append(c)}const body=table.createTBody();for(const value of values)rowFor(body,value);parent.append(table)}
  function renderResult(){const box=$('publicResult');box.hidden=!lastResult;$('saveScores').disabled=!lastResult;box.replaceChildren();if(!lastResult)return;
    const lead=document.createElement('p');lead.className='result-lead';lead.textContent=`${t(resultKind==='demo'?'demoName':'localName')} · Micro CER ${lastResult.micro_cer.toFixed(4)}%`;box.append(lead);
    const ranked=TYELeaderboard.rank([...baselines.entries,...(window.TYECommunity?.entries()||[])],'eval',lastResult),position=ranked.find(e=>e.local).rank;
    const comparison=document.createElement('p');comparison.textContent=`${t('rankContext')}: ${position} / ${ranked.length} · ${t('gainContext')}: ${lastResult.cer_improvement_pp.toFixed(4)}`;box.append(comparison);
    const diagnostics=document.createElement('dl');diagnostics.className='result-diagnostics';
    for(const [key,value] of [['restorationName',lastResult.slot_restoration_rate],['harmName',lastResult.harmful_edit_rate]]){const group=document.createElement('div'),label=document.createElement('dt'),amount=document.createElement('dd');label.textContent=t(key);amount.textContent=percent(value);group.append(label,amount);diagnostics.append(group)}
    box.append(diagnostics);const note=document.createElement('p');note.className='small';note.textContent=t('diagnosticNote');box.append(note);
    const more=document.createElement('details'),moreTitle=document.createElement('summary');moreTitle.textContent=t('resultMore');more.append(moreTitle);box.append(more);metricTable(more,[['Micro CER',percent(lastResult.micro_cer)],['Utterance Macro CER',percent(lastResult.macro_cer)],['WER',percent(lastResult.micro_wer)],
      [t('restorationName'),percent(lastResult.slot_restoration_rate)],[t('precisionName'),percent(lastResult.correction_precision)],[t('f1Name'),percent(lastResult.correction_f1)],
      [t('harmName'),percent(lastResult.harmful_edit_rate)],[t('insertionName'),percent(lastResult.unwanted_insertion_rate)],[t('cleanName'),percent(lastResult.clean_change_rate)]]);
    const table=document.createElement('table');const head=table.createTHead().insertRow();for(const text of [t('condition'),'N','Draft CER','Output CER']){const c=document.createElement('th');c.textContent=text;head.append(c)}const body=table.createTBody();for(const [key,value]of Object.entries(lastResult.conditions))rowFor(body,[t(key==='insertion'?'insertionOnly':key),value.utterances,percent(value.draft_cer),percent(value.cer)]);more.append(table);
    const details=document.createElement('details'),summary=document.createElement('summary'),pre=document.createElement('pre');summary.textContent=t('details');pre.textContent=JSON.stringify(lastResult,null,2);details.append(summary,pre);more.append(details);
  }
  function render(){document.documentElement.lang=language;for(const [node,original]of originals)node.textContent=language==='en'?english[node.dataset.t]||original:original;$('language').textContent=language==='ko'?'English':'한국어';$('language').setAttribute('aria-label',language==='ko'?'Switch to English':'한국어로 전환');$('publicStatus').textContent=publicError||t(publicState);$('privateStatus').textContent=t(privateState);$('privateLive').hidden=privateState!=='privateOpen';for(const audio of document.querySelectorAll('[data-audio-kind]'))audio.setAttribute('aria-label',t(audio.dataset.audioKind==='repair'?'exampleRepair':'examplePreserve'));renderData();renderBenchmarks();renderResult();renderQuizzes();document.dispatchEvent(new Event('tye:render'))}
  document.addEventListener('tye:community',()=>{renderBenchmarks();renderResult()});
  $('language').onclick=()=>{language=language==='ko'?'en':'ko';try{localStorage.setItem('tye-v2-language',language)}catch(e){}render()};$('benchmarkSplit').onchange=renderBenchmarks;
  function scorePublic(file){return new Promise((resolve,reject)=>{let url='public-eval-worker-v2.js',owned=false;if(window.TYE_V2_EMBEDDED){url=URL.createObjectURL(new Blob([window.TYE_V2_EMBEDDED.scorer+'\n'+window.TYE_V2_EMBEDDED.scorer_v2+'\n'+window.TYE_V2_EMBEDDED.worker],{type:'text/javascript'}));owned=true}const worker=new Worker(url);const close=()=>{clearTimeout(timer);worker.terminate();if(owned)URL.revokeObjectURL(url)};const timer=setTimeout(()=>{close();reject(new Error(t('failure')))},60000);worker.onmessage=({data})=>{close();data.error?reject(new Error(data.error)):resolve(data.result)};worker.onerror=()=>{close();reject(new Error(t('failure')))};file.arrayBuffer().then(csv=>worker.postMessage({csv,manifest},[csv])).catch(e=>{close();reject(e)})})}
  $('publicFile').onchange=()=>{window.TYECommunity?.reset();lastResult=null;publicError='';publicState=manifest?'ready':'loading';render()};
  async function evaluateFile(file,kind){if(busy)return;window.TYECommunity?.reset();lastResult=null;if(!file){publicError=t('chooseFile');render();return}if(file.size>2*1024*1024){publicError=t('tooLarge');render();return}busy=true;resultKind=kind;publicState='scoring';publicError='';for(const id of ['publicScore','publicFile','demoScore'])$(id).disabled=true;render();try{lastResult=await scorePublic(file);window.TYECommunity?.record(lastResult,{kind,name:file.name||(kind==='demo'?'Copy draft':'prediction.csv'),file});publicState='scored'}catch(e){publicError=e.message}finally{busy=false;for(const id of ['publicScore','publicFile','demoScore'])$(id).disabled=false;render()}}
  $('publicScore').onclick=()=>evaluateFile($('publicFile').files[0],'local');
  $('demoScore').onclick=async()=>{if(busy||!manifest)return;busy=true;lastResult=null;for(const id of ['publicScore','publicFile','demoScore'])$(id).disabled=true;publicState='demoLoading';publicError='';render();let blob;try{if(window.TYE_V2_EMBEDDED?.copy_csv){const raw=atob(window.TYE_V2_EMBEDDED.copy_csv);blob=new Blob([Uint8Array.from(raw,c=>c.charCodeAt(0))],{type:'text/csv'})}else{const response=await fetch('data-v2/eval-copy.csv');if(!response.ok)throw new Error(t('loadFailed'));blob=await response.blob()}}catch(e){publicError=e.message}finally{busy=false;for(const id of ['publicScore','publicFile','demoScore'])$(id).disabled=false}if(blob)await evaluateFile(blob,'demo');else render()};
  function renderQuizzes(){for(const quiz of document.querySelectorAll('[data-quiz]')){const choice=quiz.dataset.selected;for(const button of quiz.querySelectorAll('[data-choice]'))button.setAttribute('aria-pressed',String(button.dataset.choice===choice));if(!choice)continue;const correct=choice===(quiz.dataset.quiz==='repair'?'edit':'keep');quiz.querySelector('output').textContent=t(quiz.dataset.quiz==='repair'?(correct?'quizRepairCorrect':'quizRepairWrong'):(correct?'quizKeepCorrect':'quizKeepWrong'))}}
  for(const quiz of document.querySelectorAll('[data-quiz]'))for(const button of quiz.querySelectorAll('[data-choice]'))button.onclick=()=>{quiz.dataset.selected=button.dataset.choice;quiz.closest('article').querySelector('.model-comparison').open=true;renderQuizzes()};
  $('saveScores').onclick=()=>{if(!lastResult)return;const url=URL.createObjectURL(new Blob([JSON.stringify(lastResult,null,2)+'\n'],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='tye-ko-asr-v2-public-eval.scores.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};
  const config=window.CHALLENGE_CONFIG_V2||{},apiBase=(config.apiBase||'').replace(/\/$/,'');
  async function privateHealth(){const response=await fetch(apiBase+'/api/health');if(!response.ok)throw new Error(t('privateClosed'));const value=await response.json();if(value.mode!=='evaluation'||value.dataset!==(config.expectedDataset||'tye-ko-asr-v2-test')||value.scorer!=='ko-correction-v2'||value.primary_metric!=='micro_cer'||value.samples!==1750||value.dataset_version!==metadata.splits.test.references_sha256.slice(0,12))throw new Error(t('privateMismatch'));return value}
  async function leaderboard(){const response=await fetch(apiBase+'/api/leaderboard');if(!response.ok)return;const value=await response.json();$('officialRows').replaceChildren();for(const entry of value.entries||[])rowFor($('officialRows'),[entry.rank,entry.team,percent(entry.micro_cer)]);if(!value.entries?.length){const row=document.createElement('tr'),c=cell(row,t('noTeams'));c.colSpan=3;$('officialRows').append(row)}}
  $('privateForm').onsubmit=async event=>{event.preventDefault();if(!apiBase)return;const key=$('teamKey').value.trim(),file=$('privateFile').files[0];if(!key){$('privateResult').textContent=t('needKey');return}if(!file||file.size>2*1024*1024){$('privateResult').textContent=t(file?'tooLarge':'chooseFile');return}$('privateSubmit').disabled=true;$('privateResult').textContent=t('privateScoring');try{if(!(await privateHealth()).submission_open)throw new Error(t('privateClosed'));const body=new FormData();body.append('file',file);const response=await fetch(apiBase+'/api/submissions',{method:'POST',headers:{Authorization:'Bearer '+key},body});const value=await response.json();if(!response.ok)throw new Error(typeof value.detail==='string'?value.detail:t('failure'));$('privateResult').textContent=t('privateDone')+'\n'+JSON.stringify(value,null,2);await leaderboard()}catch(e){$('privateResult').textContent=e.message}finally{$('privateSubmit').disabled=privateState!=='privateOpen'}};
  async function read(name){if(window.TYE_V2_EMBEDDED)return window.TYE_V2_EMBEDDED[name];const file={manifest:'eval.json',metadata:'metadata.json',baselines:'baselines.json'}[name];const response=await fetch('data-v2/'+file);if(!response.ok)throw new Error(t('loadFailed'));return response.json()}
  const oldHashes={'#home':'#overview','#challenge':'#overview','#leaderboard':'#baselines','#workshop':'#method'};
  if(oldHashes[location.hash]){history.replaceState(null,'',location.pathname+location.search+oldHashes[location.hash]);document.querySelector(location.hash)?.scrollIntoView()}
  render();Promise.all([read('manifest'),read('metadata'),read('baselines')]).then(async values=>{[manifest,metadata,baselines]=values;if(manifest.protocol!=='ko-correction-v2'||manifest.items.length!==409||metadata.name!=='tye-ko-asr-v2'||baselines.protocol!=='ko-correction-v2')throw new Error(t('loadFailed'));publicState='ready';$('publicScore').disabled=false;$('demoScore').disabled=false;if(window.TYE_V2_EMBEDDED?.copy_csv)for(const a of document.querySelectorAll('[data-copy-link]'))a.href='data:text/csv;base64,'+window.TYE_V2_EMBEDDED.copy_csv;render();if(apiBase){try{const health=await privateHealth();privateState=health.submission_open?'privateOpen':'privateClosed';if(health.submission_open)for(const id of ['teamKey','privateFile','privateSubmit'])$(id).disabled=false;await leaderboard()}catch(e){privateState=e.message===t('privateMismatch')?'privateMismatch':'privateClosed'}render()}}).catch(()=>{publicState='loadFailed';render()});
})();
