const $ = (id) => document.getElementById(id);
const apiBase = (window.CHALLENGE_CONFIG?.apiBase || "").replace(/\/$/, "");
const awaitingService = !apiBase && location.hostname.endsWith("github.io");
const EXPECTED_SCORER = "ko-cer-v1";
let service = null,
  submitting = false,
  connecting = false,
  leaderboardRequest = 0;
const percent = (n) => (n == null ? "N/A" : `${Number(n).toFixed(2)}%`);
const dateText = (s) => new Date(s).toLocaleString("ko-KR");
const names = {
  helpful: "도움",
  partially_wrong: "부분 오류",
  misleading: "오류",
  irrelevant: "무관",
  no_context: "문맥 없음",
};
const titles = {
  home: "한국어 ASR 챌린지",
  challenge: "챌린지",
  data: "데이터·평가",
  submit: "제출",
  leaderboard: "리더보드",
  workshop: "워크숍",
};
const element = (tag, text, className) => {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
};
function route() {
  if (location.hash === "#main") {
    $("main").focus();
    return;
  }
  const name = Object.hasOwn(titles, location.hash.slice(1))
    ? location.hash.slice(1)
    : "home";
  document
    .querySelectorAll("[data-page]")
    .forEach((p) => (p.hidden = p.dataset.page !== name));
  document.querySelectorAll("nav a, header > a.button").forEach((a) => {
    if (a.hash === `#${name}`) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  });
  document.title = `${titles[name]} · Trust Your Ears`;
  window.scrollTo(0, 0);
  if (location.hash) {
    const heading = document.querySelector(`[data-page="${name}"] h1`);
    heading.setAttribute("tabindex", "-1");
    heading.focus({ preventScroll: true });
  }
  if (name === "leaderboard") loadLeaderboard();
}
window.addEventListener("hashchange", route);
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
      throw new Error("채점 서비스가 연결되지 않았습니다.");
    const body = await response.json();
    if (!response.ok)
      throw new Error(
        typeof body.detail === "string"
          ? body.detail
          : `요청을 처리하지 못했습니다 (${response.status}).`,
      );
    return body;
  } catch (error) {
    if (error.name === "AbortError")
      throw new Error(
        "연결 시간이 초과되었습니다. 같은 파일로 재시도해도 제출 횟수가 중복 차감되지 않습니다.",
      );
    if (error instanceof TypeError)
      throw new Error(
        "채점 서비스에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.",
      );
    throw error;
  } finally {
    clearTimeout(timer);
  }
}
function ensureVersion(value) {
  if (value.scorer !== EXPECTED_SCORER)
    throw new Error(
      "채점 서비스의 버전이 페이지와 다릅니다. 운영자의 업데이트 후 다시 시도해 주세요.",
    );
}
async function connectService() {
  if (awaitingService) {
    $("connection").textContent =
      "공식 평가 준비 중 · 현재는 제출 형식을 확인할 수 있습니다. 데이터와 채점 서비스 공개 후 팀 키를 안내합니다.";
    $("submit-button").disabled = true;
    $("submit-button").textContent = "공식 평가 준비 중";
    $("reconnect").hidden = true;
    $("team-key").disabled = true;
    $("team-key").placeholder = "공식 평가 시작 후 발급됩니다";
    $("load-history").disabled = true;
    $("history").replaceChildren(
      element(
        "p",
        "평가가 시작되면 이곳에서 팀별 제출 기록을 확인할 수 있습니다.",
        "empty",
      ),
    );
    return;
  }
  if (connecting) return;
  connecting = true;
  $("connection").textContent =
    "채점 서비스 연결 중… 절전 상태인 서버는 시작에 약 1분이 걸릴 수 있습니다.";
  $("reconnect").disabled = true;
  $("submit-button").disabled = true;
  try {
    const health = await api("/health");
    ensureVersion(health);
    service = health;
    const sandbox = service.mode === "sandbox";
    $("connection").textContent = sandbox
      ? `샌드박스 · ${service.samples}개 공개 텍스트 예시 · 실제 서버 채점 · 연구 결과 아님 · UTC 하루 ${service.daily_limit}회`
      : `${service.dataset} · ${service.samples}개 입력 · UTC 하루 ${service.daily_limit}회 · ${service.submission_open ? "제출 가능" : "제출 마감"}`;
    $("connection").classList.toggle("warning", sandbox);
    $("demo-key").hidden = !sandbox;
    $("submit-button").disabled = submitting || !service.submission_open;
  } catch (error) {
    service = null;
    $("demo-key").hidden = true;
    $("connection").textContent =
      `${error.message} 연결 전에는 파일이 전송되지 않습니다.`;
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
});
function resultRow(label, value) {
  const row = element("div", undefined, "score-row");
  row.append(element("span", label), element("strong", value));
  return row;
}
function showResult(result) {
  ensureVersion(result);
  $("result-empty").hidden = true;
  const box = $("result-content");
  box.hidden = false;
  box.replaceChildren();
  box.append(
    element(
      "p",
      service?.mode === "sandbox" ? "SANDBOX · 공개 예시" : "채점 완료",
      "tag",
    ),
  );
  box.append(element("div", percent(result.macro_cer), "score-number"));
  box.append(element("p", "MACRO CER · 낮을수록 좋습니다", "score-label"));
  Object.entries(result.conditions).forEach(([name, value]) => {
    box.append(
      resultRow(
        `${names[name] || name} · ${value.utterances}개`,
        percent(value.cer),
      ),
    );
  });
  const details = element("details", undefined, "result-details");
  details.append(element("summary", "이름 진단 및 보조 지표"));
  details.append(
    resultRow(
      `핵심 개체 정확도 ↑ (${result.entity_total}개)`,
      percent(result.entity_accuracy),
    ),
  );
  details.append(
    resultRow(
      `오답 문맥 수용률 ↓ (${result.wrong_total}개)`,
      percent(result.wrong_context_rate),
    ),
  );
  details.append(
    resultRow(
      `부분 오류 동시 정답률 ↑ (${result.mixed_total}개)`,
      percent(result.mixed_accuracy),
    ),
  );
  details.append(resultRow("최악 조건 CER ↓", percent(result.worst_cer)));
  details.append(resultRow("Micro CER ↓", percent(result.micro_cer)));
  details.append(resultRow("어절 WER ↓ · 참고용", percent(result.micro_wer)));
  box.append(
    details,
    element(
      "p",
      `${result.utterances}개 입력 · ${result.scorer} · N/A: 평가 주석 없음`,
      "fine",
    ),
  );
  box.append(
    element(
      "p",
      result.reused
        ? "같은 예측의 기존 결과입니다. 제출 횟수는 차감되지 않았습니다."
        : "제출 기록에 저장했습니다.",
      "fine",
    ),
  );
  const link = element("a", "리더보드 보기 →", "text-link");
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
    message.textContent = "2 MiB 이하의 CSV 파일을 선택해 주세요.";
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
  message.textContent = "파일을 검증하고 채점하고 있습니다…";
  try {
    const result = await api("/submissions", {
      method: "POST",
      headers: { Authorization: `Bearer ${$("team-key").value.trim()}` },
      body: data,
    });
    showResult(result);
    message.textContent = "평가를 완료했습니다.";
    await loadHistory();
  } catch (error) {
    message.textContent = error.message;
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
  headers.forEach((text) => {
    const th = element("th", text);
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
    $("history").replaceChildren(
      element("p", "먼저 팀 키를 입력해 주세요.", "empty"),
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
    $("history").replaceChildren(
      data.entries.length
        ? table(
            ["제출 ID", "MACRO CER ↓", "제출 시각"],
            data.entries.map((r) => [
              r.id.slice(0, 8),
              percent(r.macro_cer),
              dateText(r.created),
            ]),
            `${data.team} · 최근 제출 기록`,
          )
        : element(
            "p",
            "아직 제출 기록이 없습니다. 첫 평가 결과가 이곳에 표시됩니다.",
            "empty",
          ),
    );
  } catch (error) {
    if (key === $("team-key").value.trim())
      $("history").replaceChildren(element("p", error.message, "empty"));
  } finally {
    $("load-history").disabled = false;
  }
}
$("load-history").addEventListener("click", loadHistory);
$("team-key").addEventListener("input", () => {
  $("history").replaceChildren(
    element("p", "새 팀 키로 기록을 불러오세요.", "empty"),
  );
});
async function loadLeaderboard() {
  if (awaitingService) {
    $("leaderboard-mode").textContent =
      "공식 순위는 데이터와 채점 서비스 공개 후 시작됩니다.";
    $("leaderboard").replaceChildren(
      element(
        "p",
        "아직 공식 결과가 없습니다. 데이터·평가 페이지에서 채점 규칙과 예시 CSV를 확인하세요.",
        "empty",
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
    $("leaderboard-mode").textContent =
      data.mode === "sandbox"
        ? "샌드박스 리더보드 · 공개 텍스트 예시의 채점 결과입니다. 공식 대회 결과가 아닙니다."
        : "공식 리더보드 · 팀별 최고 점수 · 정확한 동점은 공동 순위";
    $("leaderboard-mode").classList.toggle("warning", data.mode === "sandbox");
    $("leaderboard").replaceChildren(
      data.entries.length
        ? table(
            [
              "순위",
              "팀",
              "MACRO CER ↓",
              "이름 정확도 ↑",
              "오답 수용률 ↓",
              "부분 오류 정답률 ↑",
              "최악 CER ↓",
              "제출 시각",
            ],
            data.entries.map((r) => [
              String(r.rank).padStart(2, "0"),
              r.team,
              percent(r.macro_cer),
              percent(r.entity_accuracy),
              percent(r.wrong_context_rate),
              percent(r.mixed_accuracy),
              percent(r.worst_cer),
              dateText(r.created),
            ]),
            "팀별 최고 제출물 · 가로로 스크롤해 모든 지표를 확인하세요",
          )
        : element(
            "p",
            "채점된 제출물이 없습니다. 첫 결과가 이곳에 표시됩니다.",
            "empty",
          ),
    );
  } catch (error) {
    if (request !== leaderboardRequest) return;
    $("leaderboard-mode").textContent = "결과를 불러올 수 없습니다.";
    $("leaderboard-mode").classList.add("warning");
    $("leaderboard").replaceChildren(element("p", error.message, "empty"));
  } finally {
    if (request === leaderboardRequest)
      $("refresh-leaderboard").disabled = false;
  }
}
$("refresh-leaderboard").addEventListener("click", loadLeaderboard);
const wave = document.querySelector(".wave");
for (let i = 0; i < 63; i++) {
  const bar = document.createElement("i");
  bar.style.height = `${5 + Math.sin((Math.PI * i) / 62) * (12 + Math.abs(Math.sin(i * 1.73)) * 53)}px`;
  if (i > 36 && i < 49) bar.style.background = "#9eb777";
  wave.append(bar);
}
const contexts = {
  helpful: [
    "김민서 · 네오젠",
    "두 이름 모두 정확합니다.",
    "올바른 단서를 활용하세요.",
    "참고자료의 이름이 실제 발화와 일치합니다.",
  ],
  partially_wrong: [
    "김민수 · 네오젠",
    "회사명은 맞지만 이름은 틀립니다.",
    "정보별로 판단하세요.",
    "네오젠은 활용하되, 김민수로 바꾸지 않아야 합니다.",
  ],
  misleading: [
    "김민수 · 네오진",
    "두 이름 모두 잘못되었습니다.",
    "음향적 근거를 확인하세요.",
    "자료의 오답 대신 실제 발화의 김민서와 네오젠을 지켜야 합니다.",
  ],
  irrelevant: [
    "이서연 · 다온테크",
    "다른 회의의 자료입니다.",
    "필요 없는 문맥은 버리세요.",
    "자료에 나온 이름을 음성에 없는 내용으로 추가하지 않아야 합니다.",
  ],
};
document.querySelectorAll("[data-context]").forEach((button) =>
  button.addEventListener("click", () => {
    document
      .querySelectorAll("[data-context]")
      .forEach((b) => b.setAttribute("aria-pressed", String(b === button)));
    const [name, hint, title, description] = contexts[button.dataset.context];
    $("context-example").dataset.tone = button.dataset.context;
    $("example-name").textContent = name;
    $("example-hint").textContent = hint;
    $("example-title").textContent = title;
    $("example-description").textContent = description;
  }),
);
$("prediction-file").addEventListener("change", () => {
  const file = $("prediction-file").files[0];
  $("file-selection").textContent = file
    ? `${file.name} · ${(file.size / 1024).toFixed(1)} KB`
    : "선택된 파일 없음";
  $("form-message").textContent = "";
});
route();
connectService();
