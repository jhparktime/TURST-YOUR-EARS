const $ = (id) => document.getElementById(id);
const config = window.CHALLENGE_CONFIG || {};
const apiBase = (config.apiBase || "").replace(/\/$/, "");
let service = null;
let submitting = false;
const awaitingService = !apiBase && location.hostname.endsWith("github.io");
const percent = (n) => `${Number(n).toFixed(2)}%`;
const dateText = (s) => new Date(s).toLocaleString();
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
  const valid = [
    "home",
    "challenge",
    "data",
    "submit",
    "leaderboard",
    "workshop",
  ];
  const name = valid.includes(location.hash.slice(1))
    ? location.hash.slice(1)
    : "home";
  document.querySelectorAll("[data-page]").forEach((p) => {
    p.hidden = p.dataset.page !== name;
  });
  document.querySelectorAll("nav a, header > a.button").forEach((a) => {
    if (a.hash === `#${name}`) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  });
  document.title = `${name === "home" ? "Contextual ASR Challenge" : name[0].toUpperCase() + name.slice(1)} · Trust Your Ears`;
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
    });
    const type = response.headers.get("content-type") || "";
    if (!type.includes("application/json"))
      throw new Error("Evaluation service is not connected yet.");
    const body = await response.json();
    if (!response.ok)
      throw new Error(
        typeof body.detail === "string"
          ? body.detail
          : `Request rejected (${response.status}).`,
      );
    return body;
  } catch (error) {
    if (error.name === "AbortError")
      throw new Error(
        "The request timed out. Retry the same file; identical predictions do not consume another submission.",
      );
    if (error instanceof TypeError)
      throw new Error(
        "Cannot reach the evaluation service. Please try again later.",
      );
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

async function connectService() {
  if (awaitingService) {
    $("connection").textContent =
      "Evaluation opens soon. Explore the submission format while the scoring service is being prepared.";
    $("submit-button").disabled = true;
    $("submit-button").textContent = "Evaluation opens soon";
    $("reconnect").hidden = true;
    $("team-key").disabled = true;
    $("team-key").placeholder =
      "Team keys will be available when evaluation opens";
    $("load-history").disabled = true;
    return;
  }
  $("connection").textContent =
    "Connecting to the evaluation service… Free hosting may take about a minute to wake up.";
  $("reconnect").disabled = true;
  try {
    service = await api("/health");
    const sandbox = service.mode === "sandbox";
    $("connection").textContent = sandbox
      ? `SANDBOX · ${service.samples} text-only test fixtures. Real server scoring; these are not research results. ${service.daily_limit} unique submissions per UTC day.`
      : `${service.dataset} · ${service.samples} samples · ${service.daily_limit} submissions per UTC day. ${service.submission_open ? "Submissions open." : "Submissions closed."}`;
    $("connection").classList.toggle("warning", sandbox);
    $("demo-key").hidden = !sandbox;
    $("submit-button").disabled = submitting || !service.submission_open;
  } catch (error) {
    service = null;
    $("demo-key").hidden = true;
    $("connection").textContent =
      `${error.message} File submission is unavailable until the organizers connect the scorer.`;
    $("connection").classList.add("warning");
    $("submit-button").disabled = true;
  } finally {
    $("reconnect").disabled = false;
  }
}
$("reconnect").addEventListener("click", connectService);

$("use-demo-key").addEventListener("click", () => {
  $("team-key").value = "demo-team-key";
});

function showResult(result) {
  $("result-empty").hidden = true;
  const box = $("result-content");
  box.hidden = false;
  box.replaceChildren();
  box.append(
    element(
      "p",
      service?.mode === "sandbox" ? "SANDBOX SCORE" : "SUBMISSION SCORED",
      "tag",
    ),
  );
  box.append(element("div", percent(result.macro_wer), "score-number"));
  box.append(
    element("p", "MACRO CONDITION WER · LOWER IS BETTER", "score-label"),
  );
  Object.entries(result.conditions).forEach(([name, value]) => {
    const row = element("div", undefined, "score-row");
    row.append(element("span", name), element("strong", percent(value.wer)));
    box.append(row);
  });
  box.append(
    element("p", `${result.utterances} utterances · ${result.scorer}`, "fine"),
  );
  box.append(
    element(
      "p",
      result.reused
        ? "Identical predictions: existing result returned. No allowance used."
        : "Saved to your submission history.",
      "fine",
    ),
  );
  const link = element("a", "View leaderboard →", "text-link");
  link.href = "#leaderboard";
  box.append(link);
}

$("submission-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (submitting || !service?.submission_open) return;
  const file = $("prediction-file").files[0];
  const message = $("form-message");
  message.className = "form-message";
  if (!file) return;
  if (
    !file.name.toLowerCase().endsWith(".csv") ||
    file.size > 2 * 1024 * 1024
  ) {
    message.textContent = "Choose a CSV file no larger than 2 MiB.";
    message.classList.add("error");
    return;
  }
  const data = new FormData();
  data.append("file", file);
  submitting = true;
  $("submission-form").setAttribute("aria-busy", "true");
  $("submit-button").disabled = true;
  message.textContent = "Validating and evaluating your predictions…";
  try {
    const result = await api("/submissions", {
      method: "POST",
      headers: { Authorization: `Bearer ${$("team-key").value.trim()}` },
      body: data,
    });
    showResult(result);
    message.textContent = "Evaluation complete.";
    await loadHistory();
  } catch (error) {
    message.textContent = error.message;
    message.classList.add("error");
  } finally {
    submitting = false;
    $("submission-form").removeAttribute("aria-busy");
    $("submit-button").disabled = !service?.submission_open;
  }
});

function table(headers, rows) {
  const node = element("table");
  const head = element("thead"),
    tr = element("tr");
  headers.forEach((text) => {
    const th = element("th", text);
    th.scope = "col";
    tr.append(th);
  });
  head.append(tr);
  node.append(head);
  const body = element("tbody");
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
  if (!$("team-key").value.trim()) {
    $("history").replaceChildren(
      element("p", "Enter your team key above first.", "empty"),
    );
    return;
  }
  try {
    const data = await api("/submissions", {
      headers: { Authorization: `Bearer ${$("team-key").value.trim()}` },
    });
    $("history").replaceChildren(
      data.entries.length
        ? table(
            ["SUBMISSION", "MACRO WER", "DATE"],
            data.entries.map((r) => [
              r.id.slice(0, 8),
              percent(r.macro_wer),
              dateText(r.created),
            ]),
          )
        : element(
            "p",
            "No submissions yet. Your first evaluation will appear here.",
            "empty",
          ),
    );
  } catch (error) {
    $("history").replaceChildren(element("p", error.message, "empty"));
  }
}
$("load-history").addEventListener("click", loadHistory);

async function loadLeaderboard() {
  if (awaitingService) {
    $("leaderboard-mode").textContent =
      "Official standings will open with the evaluation service.";
    $("leaderboard").replaceChildren(
      element(
        "p",
        "The first results are still ahead. Submission rules and a sample file are available in Data & rules.",
        "empty",
      ),
    );
    $("refresh-leaderboard").hidden = true;
    return;
  }
  try {
    const data = await api("/leaderboard");
    $("leaderboard-mode").textContent =
      data.mode === "sandbox"
        ? "SANDBOX LEADERBOARD · Toy fixture results only. Official competition has not started."
        : "EVALUATION LEADERBOARD · Best score per team.";
    $("leaderboard-mode").classList.toggle("warning", data.mode === "sandbox");
    $("leaderboard").replaceChildren(
      data.entries.length
        ? table(
            ["RANK", "TEAM", "MACRO WER ↓", "MICRO WER", "SUBMITTED"],
            data.entries.map((r, i) => [
              String(i + 1).padStart(2, "0"),
              r.team,
              percent(r.macro_wer),
              percent(r.micro_wer),
              dateText(r.created),
            ]),
          )
        : element(
            "p",
            "No scored submissions yet. Be the first to test the evaluation pipeline.",
            "empty",
          ),
    );
  } catch (error) {
    $("leaderboard-mode").textContent = "Evaluation service not connected.";
    $("leaderboard-mode").classList.add("warning");
    $("leaderboard").replaceChildren(element("p", error.message, "empty"));
  }
}
$("refresh-leaderboard").addEventListener("click", loadLeaderboard);
const wave = document.querySelector(".wave");
for (let i = 0; i < 63; i++) {
  const bar = document.createElement("i");
  const envelope = Math.sin((Math.PI * i) / 62);
  bar.style.height = `${5 + envelope * (12 + Math.abs(Math.sin(i * 1.73)) * 53)}px`;
  if (i > 36 && i < 49) bar.style.background = "#9eb777";
  wave.append(bar);
}
const contexts = {
  helpful: [
    "Marina",
    "The right name is available.",
    "Use the helpful clue.",
    "The reference and the spoken name agree: Marina.",
  ],
  misleading: [
    "Maria",
    "Similar name. Wrong person.",
    "Trust the acoustic evidence.",
    "The reference suggests Maria. The spoken name is Marina.",
  ],
  irrelevant: [
    "Lucas",
    "No relevant name in the list.",
    "Know when to ignore context.",
    "The list offers no useful clue. Preserve the spoken name: Marina.",
  ],
};
document.querySelectorAll("[data-context]").forEach((button) => {
  button.addEventListener("click", () => {
    const kind = button.dataset.context;
    document
      .querySelectorAll("[data-context]")
      .forEach((b) => b.setAttribute("aria-pressed", String(b === button)));
    const [name, hint, title, description] = contexts[kind];
    $("context-example").dataset.tone = kind;
    $("example-name").textContent = name;
    $("example-hint").textContent = hint;
    $("example-title").textContent = title;
    $("example-description").textContent = description;
  });
});
$("prediction-file").addEventListener("change", () => {
  const file = $("prediction-file").files[0];
  $("file-selection").textContent = file
    ? `${file.name} · ${(file.size / 1024).toFixed(1)} KB`
    : "No file selected";
});
route();
connectService();
