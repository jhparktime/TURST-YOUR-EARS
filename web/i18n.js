// Translations are trusted, repository-owned markup. API values never enter this map.
(() => {
  const english = {
    publicEvalHeading: "Public eval · Score in your browser",
    publicEvalNote: "The 409-utterance, one-hour public eval split of merged-v1. Score without a server or team key; your CSV is not uploaded. These are development scores using public references, separate from official private-test submissions and rankings.",
    publicEvalFile: "Public eval prediction CSV · id,prediction · Maximum 2 MiB",
    publicEvalButton: "Score public eval",
    publicEvalCopy: "409-row Copy baseline CSV",
    privateTestHeading: "Private test · Submit to the organizer server",
    baselineResultsHeading: "Baseline benchmark",
    baselineResultsNote: "Dataset: tye-ko-merged-v1. Eval is the public development split; test is the organizer-held evaluation split. The table reports measured fixed-model results, separate from participant rankings.",
    teamLeaderboardHeading: "Participant leaderboard",
    text001: "Skip to content",
    text002: "Speech Recognition Project",
    text003: "Overview",
    text004: "Challenge",
    text005: "Data & Evaluation",
    text006: "Leaderboard",
    text007: "Submit Results",
    text008: "Research Presentations",
    text009: "Code & Resources",
    text010: "Project Repository",
    text011: "Baselines",
    text012: "Evaluation Code",
    text013: "Correcting Korean Transcript Drafts",
    text014:
      "Listen to the audio and correct a transcript draft. The current dataset uses synthetic substitutions between phonetically similar nouns and includes drafts requiring no correction.",
    text015:
      "We evaluate both <strong>restoring erroneous spans</strong> and <strong>preserving correct spans</strong>. Comparisons with copying the draft and retranscribing the entire utterance help assess how audio contributes to correction.",
    text016: "Example utterance",
    text019: "Clean draft",
    text020: "Keep unchanged",
    text021: "One error",
    text023: "Correct the day",
    text024: "Two errors",
    text027: "Correct day & time",
    text028:
      "Figure 1. Draft conditions for the same utterance. Underlining marks injected errors; their locations are hidden from participants. This is an illustrative sentence, not an audio sample or a model result.",
    text029: "Evaluation Setup",
    text030:
      "We preserve upstream references and modify only drafts, with one draft per original recording. The dataset card separately records the listening-review status.",
    text031: "Input",
    text032: "Korean audio file and transcript draft",
    text033: "Submission",
    text034: "Complete corrected transcript · <code>id,prediction</code> CSV",
    text035: "Ranking metric",
    text036: "Macro CER across Clean, Single and Multiple conditions",
    text037: "Diagnostic metrics",
    text038:
      "Improvement over the draft, span restoration and damage to correct spans",
    text039:
      '<a href="#challenge">Task & Baselines</a> / <a href="#data">Data & Evaluation Protocol</a> / <a href="#submit">How to Submit</a>',
    text040: "Public Resources",
    text041:
      '<a href="https://github.com/jhparktime/TURST-YOUR-EARS/blob/main/scripts/baseline.py" target="_blank" rel="noopener">Baseline code</a>: Copy draft, Audio only, Text only and Audio + draft comparisons',
    text042:
      '<a href="https://github.com/jhparktime/TURST-YOUR-EARS/blob/main/server/scoring.py" target="_blank" rel="noopener">Korean scoring code</a>: shared by web scoring and local evaluation',
    text043:
      '<a href="assets/sample-submission.csv" download>Sample submission</a>: a six-row software test fixture without audio',
    text044:
      "Merged-v1: 472 train utterances (about 1h 13m), 409 public eval utterances (1h), and 1,750 private test utterances (4h). Eval/test evaluations for Copy, Whisper and Qwen Text-only are complete. The two Qwen audio-input comparisons are in progress; independent listening review and the hosted private-test service remain pending.",
    text045: "Challenge",
    text046:
      "Trust Your Ears takes Korean audio and a potentially erroneous transcript draft as input and returns a complete transcript matching the utterance. It is a transcript correction task using both audio and text.",
    text047: "Participant Task",
    text048: "Input",
    text049: "Korean audio segment + transcript draft",
    text050: "Output",
    text051: "One complete corrected transcript",
    text052: "Hidden information",
    text053: "Error presence, locations, counts and reference transcript",
    text054: "Ranking",
    text055: "Macro CER with equal weight for the three conditions ↓",
    text056:
      "The draft may already be correct. Do not add explanations, summaries or stylistic rewrites that are absent from the audio.",
    text057: "Proposed Method: Acoustic Verification Before Editing",
    text058:
      "We study selective correction by comparing the draft with an independently generated audio transcript and accepting edits only when the utterance provides sufficient evidence.",
    text059: "Transcribe the audio without seeing the draft.",
    text060: "Locate differences between the draft and the audio transcript.",
    text061: "Check acoustic evidence for the differing expressions.",
    text062:
      "Edit or retain each expression using criteria set on the development set.",
    text063:
      "This is a proposed method. The acoustic verification module and its effectiveness require further experiments and are separate from the current baseline implementation.",
    text064: "Three Evaluation Conditions",
    text065:
      "ko-correction-v1 · Condition labels are hidden from participant inputs.",
    text066: "Condition",
    text067: "Draft construction",
    text068: "Evaluation question",
    text069: "Use the upstream reference unchanged",
    text070: "Does the system preserve a correct transcript?",
    text071: "Replace one span with a similar incorrect expression",
    text072: "Does the system restore that span accurately?",
    text073: "Replace two nonadjacent spans",
    text074:
      "Does the system correct several errors while preserving the rest?",
    text075:
      "This version uses original audio and synthetic noun substitutions. Whitespace or punctuation changes alone are not injected errors. Some homophones are filtered automatically; independent listening is still needed to verify every substitution is acoustically distinguishable.",
    text076: "Four Baselines",
    text077:
      "Measured eval/test results for Copy, Whisper and Qwen Text-only are on the Leaderboard page. The remaining input-ablation experiments are in progress.",
    text078: "Method",
    text079: "Available input",
    text080: "Purpose",
    text081: "Draft",
    text082: "Reference point with no corrections",
    text083: "Audio",
    text084: "Retranscription without a draft",
    text085: "Draft",
    text086: "Whether errors can be corrected without audio",
    text087: "Audio + draft",
    text088: "Additional benefit of providing audio",
    text089:
      "Copy, Whisper audio-only and Qwen Text-only have been measured. The two audio-input ablations are in progress with the same Qwen2.5-Omni checkpoint. Differences between Whisper and Qwen cannot be attributed solely to input modality.",
    text090: "Baseline code <span>↗</span>",
    text091: "Execution & reproducibility details <span>↗</span>",
    text092: "Research Focus",
    text093:
      "We do not claim audio–text conflict itself as a new discovery. This project compares the restoration of sparse Korean substitution errors with the preservation of correct expressions. Generalization from injected errors to real ASR errors requires separate evaluation.",
    text094: "When Audio and Text Disagree · Related work <span>↗</span>",
    text095: "Qwen2.5-Omni · Model & terms of use <span>↗</span>",
    text096: "Data & Evaluation",
    text097:
      "We pooled 4,081 original recordings (about 9h 42m) and assigned 2,631 to disjoint active splits: public train about 1h 13m, public eval 1h, and private test 4h. Original audio and references are preserved; errors are synthesized only in drafts.",
    text098: "Submission File",
    text099:
      "Use a UTF-8 CSV with the columns <code>id,prediction</code>. Include every evaluation ID exactly once and provide the complete corrected transcript.",
    text100: "Download sample CSV",
    text101:
      "Complete six-row file · Copy draft output.<br />Submit the erroneous drafts unchanged to check the scoring workflow.",
    text102: "Dataset Construction",
    text103:
      "Select utterances from audio–transcript sources with verified usage terms.",
    text104: "Keep upstream references and generate draft substitutions from attested nouns. Independent listening review has not yet been performed.",
    text105:
      "Separate speakers, sessions and sentences; exclude test candidates similar to previously released text.",
    text106:
      "Keep references unchanged and record substituted spans and replacement expressions.",
    text107: "Distribute public inputs separately from private references.",
    text108:
      "Whisper transcription is complete for all 2,159 evaluation utterances. Automated file/split checks and model inference do not replace independent human listening review.",
    text109:
      "Public evaluation inputs contain only one draft per original audio file. Releasing both clean and corrupted variants of the same audio can reveal the reference through comparison. We separately document source lookup and pretraining contamination risks from reusing public corpora.",
    text110: "Korean Evaluation Protocol",
    text111: "Scorer version: ko-correction-v1",
    text112:
      "CER is measured on Hangul syllable characters. Within each condition, errors and reference characters are pooled to calculate CER. Clean, Single and Multiple each receive one-third of the weight. Clean drafts are included in the main ranking.",
    text113:
      "Macro CER determines ranking · Other metrics describe correction behavior.",
    text114: "Metric",
    text115: "Definition",
    text116: "Preferred direction",
    text117: "Equal-weight mean of the three condition CERs",
    text118: "Lower",
    text119: "Improvement over draft",
    text120: "Draft Macro CER − output Macro CER, percentage points",
    text121: "Higher · Negative values indicate degradation",
    text122: "Span restoration rate",
    text123: "Fully restored injected spans / total injected spans",
    text124: "Higher",
    text125: "Damage rate outside injected spans",
    text126:
      "Damaged reference characters outside injected spans / all such characters",
    text127: "Lower",
    text128: "Clean draft change rate",
    text129:
      "Clean utterances changed after normalization / total Clean utterances",
    text130: "Lower",
    text131:
      "Diagnostic metrics pool spans, characters or utterances across conditions. A zero denominator is reported as N/A. We also report worst-condition CER, Micro CER and space-sensitive Korean word-unit WER.",
    text132: "Spacing Is Ignored",
    text133: "Reference",
    text134: "Output",
    text135:
      "<strong>CER 0%</strong> · Differences in spaces and sentence-final periods are ignored.",
    text136: "Copying Gives Zero Improvement",
    text137: "Draft",
    text138: "Output",
    text139:
      "<strong>Improvement 0 pp · Restoration 0%</strong> · Previously correct spans remain undamaged.",
    text140: "How is Korean text normalized?",
    text141:
      'We apply NFC normalization, lowercase Latin letters and remove spaces. Specified punctuation and periods that are not between digits are excluded. Decimal points, signs, percent symbols, Korean particles and endings are retained. Number readings, synonyms and similar pronunciations are not automatically treated as equivalent. For example, <span lang="ko">3시</span> and <span lang="ko">세 시</span>, or AI and <span lang="ko">에이아이</span>, receive different scores. Reference spelling rules must be fixed before data release. Error rates can exceed 100%.',
    text142: "How are correction locations compared?",
    text143:
      "References and outputs are aligned by minimum edit distance. An injected span counts as restored only when its entire aligned output matches the reference. Ties prefer diagonal, deletion, then insertion. Insertions attach to the character on their left; an insertion at the start attaches to the first character. Dataset registration also verifies that reference-to-draft alignment matches the substitution annotations. These diagnostics depend on alignment choices for repeated expressions and boundary insertions. CER also measures the final transcript errors.",
    text144: "What is the denominator of the damage rate?",
    text145:
      "The number of reference characters outside injected spans. A character counts as damaged when its aligned output differs, including substitution, deletion and attached insertions. Originally matching characters inside injected spans are excluded from this denominator. Injected spans must consistently represent words or meaningful expressions.",
    text146: "Does a good score prove effective use of audio?",
    text147:
      "The score alone cannot establish this. A draft-only model may correct errors using grammar or general knowledge. We plan to compare Text only with Audio + draft using the same model, then verify on a separate set of actual ASR drafts. Code tests do not replace listening-based review or model experiments.",
    text148: "How are ties and submission limits handled?",
    text149:
      "Each team’s lowest Macro CER is ranked using unrounded values. Exact ties share a rank. The default limit is five submissions per UTC day, resetting at 09:00 Korea Standard Time. Invalid files do not consume attempts. Identical predictions return the existing result. The service displays the actual limit.",
    text150:
      "Public input & private reference formats and review rules <span>↗</span>",
    text151: "Shared web & local scoring code <span>↗</span>",
    text152: "Submit Results",
    text153:
      "Run your model in your own environment. Score public eval directly on this page; submit private test predictions to the organizer server.",
    text154: "Reconnect to scoring service ↻",
    text155: "Submit a Transcript File",
    text156: "Team key",
    text157:
      "Used only in this screen. It is not saved in the URL or browser storage.",
    text158: "Use public sandbox key",
    text159: "Prediction file",
    text160: "UTF-8 · id,prediction · Maximum 2 MiB",
    text161: "Sample CSV",
    text162: "Evaluation Results",
    text163:
      "After scoring, this panel shows condition CERs, improvement, restoration and damage metrics.",
    text164: "Private test references stay on the server",
    text165:
      "Public eval references are included for browser scoring. Private test references are excluded from the website, public repository and submission HTML.",
    text166: "Recent Submissions",
    text167: "Load history with team key ↻",
    text168: "Leaderboard",
    text169: "Refresh ↻",
    text170:
      "Each team’s best submission is ranked by ascending Macro CER. Improvement, error restoration and damage to correct spans are shown alongside the main score. Exact ties share a rank.",
    text171:
      "↓ indicates lower is better; ↑ indicates higher is better. N/A means a zero denominator. Sandbox scores are neither model performance measurements nor official competition results.",
    text172: "Research Presentations",
    text173:
      "We are preparing research presentations on Korean transcript correction, evaluation data design and acoustic verification.",
    diagnosticHeading: "Preliminary Experiment · Synthetic Error Difficulty",
    diagnosticMethod: "On all 409 public eval utterances, we compared existing Whisper outputs with the drafts and changed only Hangul words of equal length with a small jamo edit distance. This development experiment compared five fixed editing limits.",
    diagnosticMethodColumn: "Method",
    diagnosticRestoreColumn: "Error restoration ↑",
    diagnosticDamageColumn: "Damage to correct spans ↓",
    diagnosticCopy: "Copy draft",
    diagnosticWhisper: "Whisper full retranscription",
    diagnosticFilter: "Whisper + simple editing filter (2/2)",
    diagnosticInterpretation: "2/2 allows at most two changed syllables and a jamo edit distance of two; it had the lowest CER on public eval. This filter still changed 42 of 137 clean utterances (30.66%). The result shows an advantage for a simple filter that knows the generation rules. It does not establish private test performance or methodological novelty.",
    diagnosticNext: "The current data is a pilot with controlled synthetic errors. Further validation requires real ASR errors, contextually plausible confusions and independent listening review. This experiment does not implement or validate the acoustic verification module listed as a discussion topic below.",
    diagnosticLink: "All five settings, public predictions & reproduction code",
    text174: "Presentation & Discussion Topics",
    text175: "Selective correction of erroneous drafts and over-editing",
    text176: "Evaluating Korean proper names, particles and mixed English text",
    text177: "Errors correctable from text alone versus errors requiring audio",
    text178: "Acoustic verification before editing and confidence estimation",
    text179: "Data leakage and reproducible leaderboards",
    text180: "Schedule & Organization",
    text181: "Data release",
    text182: "To be announced",
    text183: "Submission deadline",
    text184: "To be announced",
    text185: "Final presentations",
    text186: "To be announced",
    text187: "Organizers & contact",
    text188: "To be announced before official evaluation",
    text189: "Trust Your Ears · 2026 Speech Recognition Course Project",
    datasetHeading: "Korean Transcript Correction · merged-v1",
    datasetDetails:
      "Train: 472 utterances / 63 speakers; eval: 409 / 20; test: 1,750 / 32. Clean / Single / Multiple counts are 157 / 150 / 165 for train, 137 / 136 / 136 for eval, and 583 / 583 / 584 for test. Speakers, sessions, identical/near sentences and PCM waveforms are separated. The 1,450 reserved recordings are organizer-only and must not be used for training.",
    datasetLinks:
      "<a href=\"https://github.com/jhparktime/TURST-YOUR-EARS/tree/main/datasets/tye-ko-merged-v1\" target=\"_blank\" rel=\"noopener\">Public inputs, references & dataset card</a> / <a href=\"https://github.com/jhparktime/TURST-YOUR-EARS/blob/main/scripts/merge_correction_datasets.py\" target=\"_blank\" rel=\"noopener\">Merge & split code</a> / <a href=\"data/eval-copy.csv\" download>Public eval Copy CSV</a>",
    datasetDownloads: "<a href=\"https://github.com/jhparktime/TURST-YOUR-EARS/releases/download/dataset-ko-merged-v1/tye-ko-merged-v1-participant.zip\">Train & eval audio, drafts and references ZIP</a> / <a href=\"https://github.com/jhparktime/TURST-YOUR-EARS/blob/main/datasets/tye-ko-merged-v1/validation-report.json\" target=\"_blank\" rel=\"noopener\">Validation report</a> / <a href=\"https://github.com/jhparktime/TURST-YOUR-EARS/blob/main/datasets/tye-ko-merged-v1/public-release-lock.json\" target=\"_blank\" rel=\"noopener\">Public file hashes</a>",
    datasetLimits:
      "Source: Zeroth-Korean, CC BY 4.0. References receive NFC only. Blind Whisper inference is complete; independent listening review is pending. Synthetic substitutions do not represent an observed ASR error distribution and may be solvable from text cues. Public-source lookup and pretraining contamination remain possible. Releasing the new train split retires the previous test version; scores must not be mixed.",
  };
  const attributes = {
    "Trust Your Ears 홈": "Trust Your Ears home",
    메뉴: "Menu",
    "주 메뉴": "Main navigation",
    "평가 조건 표": "Evaluation conditions table",
    "베이스라인 비교 표": "Baseline comparison table",
    "평가 지표 표": "Evaluation metrics table",
    "제출 기록 표": "Submission history table",
    "리더보드 표": "Leaderboard table",
    "운영자가 발급한 팀 키": "Team key issued by the organizers",
    "언어 선택": "Language selection",
  };
  let language = "ko";
  try {
    if (localStorage.getItem("tye-language") === "en") language = "en";
  } catch {
    /* Language selection still works when browser storage is unavailable. */
  }
  const fragments = [...document.querySelectorAll("[data-i18n]")].map(
    (node) => ({
      node,
      korean: node.innerHTML,
      english: english[node.dataset.i18n],
    }),
  );
  const labels = [...document.querySelectorAll("[data-i18n-attr]")].map(
    (node) => {
      const attribute = node.dataset.i18nAttr;
      const korean = node.getAttribute(attribute);
      return { node, attribute, korean, english: attributes[korean] };
    },
  );
  const descriptions = {
    ko: "Trust Your Ears: 음성을 근거로 틀린 전사 초안만 고치는 한국어 전사 교정 챌린지. 데이터, 평가 규칙, 웹 제출과 리더보드.",
    en: "Trust Your Ears: Korean audio-grounded transcript correction. Task, data, evaluation protocol, online submissions and leaderboard.",
  };
  function apply(next, notify = true) {
    if (!["ko", "en"].includes(next)) return;
    language = next;
    document.documentElement.lang = next;
    fragments.forEach(({ node, korean, english }) => {
      if (english === undefined)
        throw new Error(`Missing translation: ${node.dataset.i18n}`);
      node.innerHTML = next === "en" ? english : korean;
    });
    labels.forEach(({ node, attribute, korean, english }) => {
      node.setAttribute(attribute, next === "en" ? english : korean);
    });
    document.querySelector('meta[name="description"]').content =
      descriptions[next];
    document.querySelectorAll("[data-language]").forEach((button) => {
      button.setAttribute(
        "aria-pressed",
        String(button.dataset.language === next),
      );
    });
    try {
      localStorage.setItem("tye-language", next);
    } catch {}
    if (notify) window.dispatchEvent(new Event("languagechange"));
  }
  window.I18n = {
    get language() {
      return language;
    },
    text(korean, english, values = {}) {
      const template = language === "en" ? english : korean;
      return template.replace(/\{(\w+)\}/g, (_, key) =>
        String(values[key] ?? ""),
      );
    },
  };
  document.querySelectorAll("[data-language]").forEach((button) => {
    button.addEventListener("click", () => apply(button.dataset.language));
  });
  apply(language, false);
})();
