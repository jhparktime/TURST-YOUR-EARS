const $ = (id) => document.getElementById(id);
const t = (ko, en, values) => window.I18n.text(ko, en, values);
const apiBase = (window.CHALLENGE_CONFIG?.apiBase || "").replace(/\/$/, "");
const awaitingService = !apiBase && location.hostname.endsWith("github.io");
const EXPECTED_SCORER = "ko-correction-v1";
let service = null,
  submitting = false,
  connecting = false,
  leaderboardRequest = 0;
let lastResult = null;
// Keep render functions in memory so switching languages never sends requests,
// clears a file input, stores credentials or consumes another submission attempt.
const views = new Map();
function paint(id, render) {
  views.set(id, render);
  render();
}
function text(id, render) {
  paint(id, () => {
    $(id).textContent = render();
  });
}
function content(id, render) {
  paint(id, () => {
    $(id).replaceChildren(render());
  });
}
const percent = (n) => (n == null ? "N/A" : `${Number(n).toFixed(2)}%`);
const dateText = (s) =>
  new Date(s).toLocaleString(window.I18n.language === "en" ? "en-US" : "ko-KR");
const points = (n) =>
  n == null
    ? "N/A"
    : `${n > 0 ? "+" : ""}${Number(n).toFixed(2)}${t("%p", " pp")}`;
const pageTitles = {
  home: ["개요", "Overview"],
  challenge: ["챌린지", "Challenge"],
  data: ["데이터·평가", "Data & Evaluation"],
  submit: ["제출", "Submit Results"],
  leaderboard: ["리더보드", "Leaderboard"],
  workshop: ["연구 발표", "Research Presentations"],
};
const currentPage = () =>
  Object.hasOwn(pageTitles, location.hash.slice(1))
    ? location.hash.slice(1)
    : "home";
const updateTitle = () => {
  document.title = `${t(...pageTitles[currentPage()])} · Trust Your Ears`;
};
const element = (tag, label, className) => {
  const node = document.createElement(tag);
  if (label !== undefined) node.textContent = label;
  if (className) node.className = className;
  return node;
};
const empty = (ko, en) => element("p", t(ko, en), "empty");
function route() {
  if (location.hash === "#main") {
    $("main").focus();
    return;
  }
  const name = currentPage();
  document.querySelectorAll("[data-page]").forEach((p) => {
    p.hidden = p.dataset.page !== name;
  });
  document.querySelectorAll("nav a").forEach((a) => {
    if (a.hash === `#${name}`) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  });
  updateTitle();
  window.scrollTo(0, 0);
  if (location.hash) {
    const heading = document.querySelector(`[data-page="${name}"] h1`);
    heading.setAttribute("tabindex", "-1");
    heading.focus({ preventScroll: true });
  }
  if (name === "leaderboard") loadLeaderboard();
}
window.addEventListener("hashchange", route);
const errors = {
  "Enter the team key issued by the organizers.":
    "운영자가 발급한 팀 키를 입력해 주세요.",
  "Invalid team key.": "유효하지 않은 팀 키입니다.",
  "Submissions are closed.": "제출이 마감되었습니다.",
  "Maximum submission size is 2 MiB.": "제출 파일은 최대 2 MiB입니다.",
  "Daily submission limit reached. It resets at 00:00 UTC.":
    "하루 제출 한도에 도달했습니다. UTC 00:00(한국 시간 오전 9시)에 초기화됩니다.",
  "CSV header must be exactly: id,prediction.":
    "CSV 헤더는 정확히 id,prediction이어야 합니다.",
  "Every row must have exactly two CSV fields.":
    "각 행은 CSV 필드 두 개로 구성해야 합니다.",
  "IDs must be non-empty and unique.": "ID는 비어 있거나 중복될 수 없습니다.",
  "An ID or prediction exceeds the size limit.":
    "ID 또는 전사문이 길이 제한을 초과했습니다.",
  "Too many rows.": "행 수가 너무 많습니다.",
  "The submission is empty.": "제출 파일이 비어 있습니다.",
  "Upload a valid UTF-8 CSV file.": "유효한 UTF-8 CSV 파일을 업로드해 주세요.",
  "Submission IDs must exactly match this evaluation set (no missing or extra IDs).":
    "제출 ID는 평가셋과 정확히 일치해야 합니다. 누락되거나 추가된 ID를 확인해 주세요.",
  "Prediction must be a string of at most 4000 characters.":
    "전사문은 4,000자 이하의 문자열이어야 합니다.",
  "Submission exceeds the scorer computation limit. Contact the organizers.":
    "채점 계산 한도를 초과했습니다. 운영자에게 문의해 주세요.",
};
const errorMessage = (error) =>
  error.localized
    ? error.localized()
    : t(errors[error.message] || error.message, error.message);
function localizedError(ko, en, values) {
  const error = new Error(en);
  error.localized = () => t(ko, en, values);
  return error;
}
async function api(path, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 90000);
  try {
    const response = await fetch(`${apiBase}/api${path}`, {
      ...options,
      signal: controller.signal,
      cache: "no-store",
    });
    if (
      !(response.headers.get("content-type") || "").includes("application/json")
    )
      throw localizedError(
        "채점 서비스가 연결되지 않았습니다.",
        "The scoring service is not connected.",
      );
    const body = await response.json();
    if (!response.ok) {
      if (typeof body.detail === "string") throw new Error(body.detail);
      throw localizedError(
        "요청을 처리하지 못했습니다 ({status}).",
        "The request could not be processed ({status}).",
        { status: response.status },
      );
    }
    return body;
  } catch (error) {
    if (error.name === "AbortError")
      throw localizedError(
        "연결 시간이 초과되었습니다. 같은 파일로 재시도해도 제출 횟수가 중복 차감되지 않습니다.",
        "The connection timed out. Retrying the same file will not consume another submission attempt.",
      );
    if (error instanceof TypeError)
      throw localizedError(
        "채점 서비스에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.",
        "Cannot reach the scoring service. Please try again shortly.",
      );
    throw error;
  } finally {
    clearTimeout(timer);
  }
}
function ensureVersion(value) {
  if (value.scorer !== EXPECTED_SCORER)
    throw localizedError(
      "채점 서비스의 버전이 페이지와 다릅니다. 운영자의 업데이트 후 다시 시도해 주세요.",
      "The scoring service version does not match this page. Please retry after the organizers update it.",
    );
}
async function connectService() {
  if (awaitingService) {
    text("connection", () =>
      t(
        "공식 평가 준비 중 · 현재는 제출 형식을 확인할 수 있습니다. 데이터와 채점 서비스 공개 후 팀 키를 안내합니다.",
        "Official evaluation is in preparation · You can check the submission format now. Team keys will be issued after the dataset and scoring service are released.",
      ),
    );
    $("submit-button").disabled = true;
    text("submit-button", () =>
      t("공식 평가 준비 중", "Evaluation in preparation"),
    );
    $("reconnect").hidden = true;
    $("team-key").disabled = true;
    paint("team-key", () => {
      $("team-key").placeholder = t(
        "공식 평가 시작 후 발급됩니다",
        "Issued when official evaluation starts",
      );
    });
    $("load-history").disabled = true;
    content("history", () =>
      empty(
        "평가가 시작되면 이곳에서 팀별 제출 기록을 확인할 수 있습니다.",
        "Team submission history will appear here once evaluation starts.",
      ),
    );
    return;
  }
  if (connecting) return;
  connecting = true;
  text("connection", () =>
    t(
      "채점 서비스 연결 중… 절전 상태인 서버는 시작에 약 1분이 걸릴 수 있습니다.",
      "Connecting to the scoring service… A sleeping server may take about a minute to start.",
    ),
  );
  $("reconnect").disabled = true;
  $("submit-button").disabled = true;
  try {
    const health = await api("/health");
    ensureVersion(health);
    service = health;
    const sandbox = health.mode === "sandbox";
    text("connection", () =>
      sandbox
        ? t(
            "샌드박스 · {samples}개 공개 텍스트 예시 · 실제 서버 채점 · 연구 결과 아님 · UTC 하루 {limit}회",
            "Sandbox · {samples} public text examples · Server scoring · Not research results · {limit} attempts per UTC day",
            { samples: health.samples, limit: health.daily_limit },
          )
        : t(
            "{dataset} · {samples}개 입력 · UTC 하루 {limit}회 · {state}",
            "{dataset} · {samples} inputs · {limit} attempts per UTC day · {state}",
            {
              dataset: health.dataset,
              samples: health.samples,
              limit: health.daily_limit,
              state: health.submission_open
                ? t("제출 가능", "Submissions open")
                : t("제출 마감", "Submissions closed"),
            },
          ),
    );
    $("connection").classList.toggle("warning", sandbox);
    $("demo-key").hidden = !sandbox;
    $("submit-button").disabled = submitting || !health.submission_open;
  } catch (error) {
    service = null;
    $("demo-key").hidden = true;
    text(
      "connection",
      () =>
        `${errorMessage(error)} ${t("연결 전에는 파일이 전송되지 않습니다.", "Files are not sent until connected.")}`,
    );
    $("connection").classList.add("warning");
    $("submit-button").disabled = true;
  } finally {
    connecting = false;
    $("reconnect").disabled = false;
  }
}
$("reconnect").addEventListener("click", connectService);
$("use-demo-key").addEventListener("click", () => {
  $("team-key").value = "demo-team-key";
  clearHistory();
});
function resultRow(label, value) {
  const row = element("div", undefined, "score-row");
  row.append(element("span", label), element("strong", value));
  return row;
}
function showResult(result) {
  ensureVersion(result);
  lastResult = result;
  $("result-empty").hidden = true;
  const box = $("result-content");
  const wasOpen = Boolean(box.querySelector("details")?.open);
  box.hidden = false;
  box.replaceChildren();
  box.append(
    element(
      "p",
      service?.mode === "sandbox"
        ? t("SANDBOX · 공개 예시", "SANDBOX · Public examples")
        : t("채점 완료", "Scoring complete"),
      "tag",
    ),
  );
  box.append(element("div", percent(result.macro_cer), "score-number"));
  box.append(
    element(
      "p",
      t("MACRO CER · 낮을수록 좋습니다", "MACRO CER · Lower is better"),
      "score-label",
    ),
  );
  const names = {
    clean: t("무오류", "Clean"),
    single: t("오류 1곳", "Single error"),
    multiple: t("오류 2–4곳", "Multiple errors (2–4)"),
  };
  Object.entries(result.conditions).forEach(([name, value]) => {
    box.append(
      resultRow(
        t("{name} · {count}개", "{name} · {count} utterances", {
          name: names[name] || name,
          count: value.utterances,
        }),
        percent(value.cer),
      ),
    );
  });
  const details = element("details", undefined, "result-details");
  details.open = wasOpen;
  details.append(
    element(
      "summary",
      t(
        "교정·보존 및 보조 지표",
        "Correction, preservation & diagnostic metrics",
      ),
    ),
  );
  details.append(
    resultRow(
      t("초안 Macro CER", "Draft Macro CER"),
      percent(result.draft_macro_cer),
    ),
  );
  details.append(
    resultRow(
      t("초안 대비 개선폭 ↑", "Improvement over draft ↑"),
      points(result.cer_improvement_pp),
    ),
  );
  details.append(
    resultRow(
      t(
        "오류 구간 복원률 ↑ ({count}곳)",
        "Span restoration ↑ ({count} spans)",
        { count: result.edit_total },
      ),
      percent(result.restoration_rate),
    ),
  );
  details.append(
    resultRow(
      t(
        "정상 구간 훼손률 ↓ ({count}문자)",
        "Damage outside injected spans ↓ ({count} characters)",
        { count: result.preserved_total },
      ),
      percent(result.harmful_edit_rate),
    ),
  );
  details.append(
    resultRow(
      t(
        "무오류 초안 변경률 ↓ ({count}발화)",
        "Clean draft changes ↓ ({count} utterances)",
        { count: result.clean_total },
      ),
      percent(result.clean_change_rate),
    ),
  );
  details.append(
    resultRow(
      t("최악 조건 CER ↓", "Worst-condition CER ↓"),
      percent(result.worst_cer),
    ),
  );
  details.append(resultRow("Micro CER ↓", percent(result.micro_cer)));
  details.append(
    resultRow(
      t("어절 WER ↓ · 참고용", "Korean word-unit WER ↓ · Diagnostic"),
      percent(result.micro_wer),
    ),
  );
  box.append(
    details,
    element(
      "p",
      t(
        "{count}개 입력 · {scorer} · N/A: 해당 지표의 분모가 0",
        "{count} inputs · {scorer} · N/A: zero denominator",
        { count: result.utterances, scorer: result.scorer },
      ),
      "fine",
    ),
  );
  box.append(
    element(
      "p",
      result.reused
        ? t(
            "같은 예측의 기존 결과입니다. 제출 횟수는 차감되지 않았습니다.",
            "Existing result for identical predictions. No submission attempt was consumed.",
          )
        : t("제출 기록에 저장했습니다.", "Saved to your submission history."),
      "fine",
    ),
  );
  const link = element(
    "a",
    t("리더보드 보기 →", "View leaderboard →"),
    "text-link",
  );
  link.href = "#leaderboard";
  box.append(link);
}
$("submission-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (submitting || connecting || !service?.submission_open) return;
  const file = $("prediction-file").files[0],
    message = $("form-message");
  message.className = "form-message";
  if (!file) return;
  if (
    !file.name.toLowerCase().endsWith(".csv") ||
    file.size > 2 * 1024 * 1024
  ) {
    text("form-message", () =>
      t(
        "2 MiB 이하의 CSV 파일을 선택해 주세요.",
        "Choose a CSV file no larger than 2 MiB.",
      ),
    );
    message.classList.add("error");
    return;
  }
  const data = new FormData();
  data.append("file", file);
  submitting = true;
  $("submission-form").setAttribute("aria-busy", "true");
  $("submit-button").disabled = true;
  $("team-key").disabled = true;
  $("use-demo-key").disabled = true;
  $("prediction-file").disabled = true;
  text("form-message", () =>
    t(
      "파일을 검증하고 채점하고 있습니다…",
      "Validating and scoring your file…",
    ),
  );
  try {
    const result = await api("/submissions", {
      method: "POST",
      headers: { Authorization: `Bearer ${$("team-key").value.trim()}` },
      body: data,
    });
    showResult(result);
    text("form-message", () =>
      t("평가를 완료했습니다.", "Evaluation complete."),
    );
    await loadHistory();
  } catch (error) {
    text("form-message", () => errorMessage(error));
    message.classList.add("error");
  } finally {
    submitting = false;
    $("submission-form").removeAttribute("aria-busy");
    $("submit-button").disabled = connecting || !service?.submission_open;
    $("team-key").disabled = false;
    $("use-demo-key").disabled = false;
    $("prediction-file").disabled = false;
  }
});
function table(headers, rows, caption) {
  const node = element("table"),
    head = element("thead"),
    tr = element("tr"),
    body = element("tbody");
  node.append(element("caption", caption));
  headers.forEach((label) => {
    const th = element("th", label);
    th.scope = "col";
    tr.append(th);
  });
  head.append(tr);
  node.append(head);
  rows.forEach((values) => {
    const row = element("tr");
    values.forEach((value) => row.append(element("td", value)));
    body.append(row);
  });
  node.append(body);
  return node;
}
async function loadHistory() {
  if (awaitingService) return;
  const key = $("team-key").value.trim();
  if (!key) {
    content("history", () =>
      empty("먼저 팀 키를 입력해 주세요.", "Enter your team key first."),
    );
    return;
  }
  $("load-history").disabled = true;
  try {
    const data = await api("/submissions", {
      headers: { Authorization: `Bearer ${key}` },
    });
    if (key !== $("team-key").value.trim()) return;
    data.entries.forEach(ensureVersion);
    content("history", () =>
      data.entries.length
        ? table(
            [
              t("제출 ID", "Submission ID"),
              "MACRO CER ↓",
              t("제출 시각", "Submitted"),
            ],
            data.entries.map((r) => [
              r.id.slice(0, 8),
              percent(r.macro_cer),
              dateText(r.created),
            ]),
            t("{team} · 최근 제출 기록", "{team} · Recent submissions", {
              team: data.team,
            }),
          )
        : empty(
            "아직 제출 기록이 없습니다. 첫 평가 결과가 이곳에 표시됩니다.",
            "No submissions yet. Your first evaluation result will appear here.",
          ),
    );
  } catch (error) {
    if (key === $("team-key").value.trim())
      content("history", () => element("p", errorMessage(error), "empty"));
  } finally {
    $("load-history").disabled = false;
  }
}
function clearHistory() {
  content("history", () =>
    empty(
      "새 팀 키로 기록을 불러오세요.",
      "Load history using the new team key.",
    ),
  );
}
$("load-history").addEventListener("click", loadHistory);
$("team-key").addEventListener("input", clearHistory);
async function loadLeaderboard() {
  if (awaitingService) {
    text("leaderboard-mode", () =>
      t(
        "공식 순위는 데이터와 채점 서비스 공개 후 시작됩니다.",
        "Official rankings will open after the dataset and scoring service are released.",
      ),
    );
    content("leaderboard", () =>
      empty(
        "아직 공식 결과가 없습니다. 데이터·평가 페이지에서 채점 규칙과 예시 CSV를 확인하세요.",
        "No official results yet. See Data & Evaluation for the scoring rules and sample CSV.",
      ),
    );
    $("refresh-leaderboard").hidden = true;
    return;
  }
  const request = ++leaderboardRequest;
  $("refresh-leaderboard").disabled = true;
  try {
    const data = await api("/leaderboard");
    if (request !== leaderboardRequest) return;
    data.entries.forEach(ensureVersion);
    text("leaderboard-mode", () =>
      data.mode === "sandbox"
        ? t(
            "샌드박스 리더보드 · 공개 텍스트 예시의 채점 결과입니다. 공식 대회 결과가 아닙니다.",
            "Sandbox leaderboard · Scores on public text examples, not official competition results.",
          )
        : t(
            "공식 리더보드 · 팀별 최고 점수 · 정확한 동점은 공동 순위",
            "Official leaderboard · Best score per team · Exact ties share a rank",
          ),
    );
    $("leaderboard-mode").classList.toggle("warning", data.mode === "sandbox");
    content("leaderboard", () =>
      data.entries.length
        ? table(
            [
              t("순위", "Rank"),
              t("팀", "Team"),
              "MACRO CER ↓",
              t("개선폭 ↑", "Improvement ↑"),
              t("오류 복원률 ↑", "Restoration ↑"),
              t("정상 구간 훼손률 ↓", "Damage outside spans ↓"),
              t("무오류 변경률 ↓", "Clean changes ↓"),
              t("최악 CER ↓", "Worst CER ↓"),
              t("제출 시각", "Submitted"),
            ],
            data.entries.map((r) => [
              String(r.rank).padStart(2, "0"),
              r.team,
              percent(r.macro_cer),
              points(r.cer_improvement_pp),
              percent(r.restoration_rate),
              percent(r.harmful_edit_rate),
              percent(r.clean_change_rate),
              percent(r.worst_cer),
              dateText(r.created),
            ]),
            t(
              "팀별 최고 제출물 · 가로로 스크롤해 모든 지표를 확인하세요",
              "Best submission per team · Scroll horizontally to view all metrics",
            ),
          )
        : empty(
            "채점된 제출물이 없습니다. 첫 결과가 이곳에 표시됩니다.",
            "No scored submissions yet. The first result will appear here.",
          ),
    );
  } catch (error) {
    if (request !== leaderboardRequest) return;
    text("leaderboard-mode", () =>
      t("결과를 불러올 수 없습니다.", "Unable to load results."),
    );
    $("leaderboard-mode").classList.add("warning");
    content("leaderboard", () => element("p", errorMessage(error), "empty"));
  } finally {
    if (request === leaderboardRequest)
      $("refresh-leaderboard").disabled = false;
  }
}
$("refresh-leaderboard").addEventListener("click", loadLeaderboard);
function renderFileSelection() {
  const file = $("prediction-file").files[0];
  $("file-selection").textContent = file
    ? `${file.name} · ${(file.size / 1024).toFixed(1)} KB`
    : t("선택된 파일 없음", "No file selected");
}
$("prediction-file").addEventListener("change", () => {
  renderFileSelection();
  text("form-message", () => "");
});
window.addEventListener("languagechange", () => {
  updateTitle();
  views.forEach((render) => render());
  renderFileSelection();
  if (lastResult) showResult(lastResult);
});
text("submit-button", () => t("제출 및 채점", "Submit & score"));
text("connection", () =>
  t("채점 서비스에 연결하고 있습니다…", "Connecting to the scoring service…"),
);
content("history", () =>
  empty(
    "팀 키를 입력하면 제출 기록을 확인할 수 있습니다.",
    "Enter your team key to view submission history.",
  ),
);
text("leaderboard-mode", () =>
  t("평가 상태 확인 중…", "Checking evaluation status…"),
);
content("leaderboard", () =>
  empty("결과를 불러오고 있습니다…", "Loading results…"),
);
renderFileSelection();
route();
connectService();
