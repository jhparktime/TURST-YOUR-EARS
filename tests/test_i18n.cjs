const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");
const root = path.resolve(__dirname, "..");
const html = fs.readFileSync(path.join(root, "web/archive-v1.html"), "utf8");
const source = fs.readFileSync(path.join(root, "web/i18n.js"), "utf8");

function boot(saved, blocked = false) {
  let stored = saved;
  const fragments = [...html.matchAll(/data-i18n="([^"]+)"/g)].map((match) => ({
    dataset: { i18n: match[1] },
    innerHTML: `원문 ${match[1]}`,
  }));
  const label = {
    dataset: { i18nAttr: "aria-label" },
    value: "언어 선택",
    getAttribute() {
      return this.value;
    },
    setAttribute(name, value) {
      this.value = value;
    },
  };
  const buttons = ["ko", "en"].map((language) => ({
    dataset: { language },
    addEventListener(name, fn) {
      this.click = fn;
    },
    setAttribute(name, value) {
      this[name] = value;
    },
  }));
  const description = {};
  const document = {
    documentElement: {},
    querySelectorAll(selector) {
      return selector === "[data-i18n]"
        ? fragments
        : selector === "[data-i18n-attr]"
          ? [label]
          : buttons;
    },
    querySelector() {
      return description;
    },
  };
  const events = [];
  const window = {
    dispatchEvent(event) {
      events.push(event.type);
    },
  };
  vm.runInNewContext(source, {
    document,
    window,
    Event: class {
      constructor(type) {
        this.type = type;
      }
    },
    localStorage: {
      getItem(key) {
        assert.equal(key, "tye-language");
        if (blocked) throw new Error("Storage denied");
        return stored;
      },
      setItem(key, value) {
        assert.equal(key, "tye-language");
        if (blocked) throw new Error("Storage denied");
        stored = value;
      },
    },
  });
  return {
    fragments,
    label,
    buttons,
    document,
    window,
    events,
    description,
    get stored() {
      return stored;
    },
  };
}

test("all published page fragments have English translations; Korean remains the default", () => {
  const app = boot();
  assert.equal(app.document.documentElement.lang, "ko");
  app.buttons[1].click();
  assert.ok(app.fragments.length >= 184);
  assert.ok(app.fragments.every((node) => !node.innerHTML.startsWith("원문")));
  assert.equal(app.document.documentElement.lang, "en");
  assert.equal(app.label.value, "Language selection");
  assert.equal(app.buttons[1]["aria-pressed"], "true");
  assert.equal(app.buttons[0]["aria-pressed"], "false");
  assert.deepEqual(app.events, ["languagechange"]);
});

test("switching back restores original markup and accessible labels", () => {
  const app = boot();
  const originals = app.fragments.map((node) => node.innerHTML);
  app.buttons[1].click();
  app.buttons[0].click();
  assert.deepEqual(
    app.fragments.map((node) => node.innerHTML),
    originals,
  );
  assert.equal(app.label.value, "언어 선택");
  assert.equal(app.document.documentElement.lang, "ko");
});

test("language preference survives reload and unsupported stored values default to Korean", () => {
  const app = boot();
  app.buttons[1].click();
  assert.equal(boot(app.stored).document.documentElement.lang, "en");
  assert.equal(boot("invalid").document.documentElement.lang, "ko");
});

test("storage denial does not prevent switching or dynamic interpolation", () => {
  const app = boot(undefined, true);
  app.buttons[1].click();
  assert.equal(
    app.window.I18n.text("{count}개 입력", "{count} inputs", { count: 6 }),
    "6 inputs",
  );
  app.buttons[0].click();
  assert.equal(
    app.window.I18n.text("{count}개 입력", "{count} inputs", { count: 6 }),
    "6개 입력",
  );
});

test("UI translations retain dataset identifiers, submission format and Korean notation examples", () => {
  const app = boot("en");
  const lookup = (key) =>
    app.fragments.find((node) => node.dataset.i18n === key).innerHTML;
  assert.match(lookup("text099"), /id,prediction/);
  assert.match(lookup("text111"), /ko-correction-v1/);
  assert.match(lookup("text141"), /<span lang="ko">세 시<\/span>/);
  assert.match(
    lookup("text043"),
    /href="assets\/sample-submission.csv" download/,
  );
  const examples = [
    ...html.matchAll(/<(?:p|pre) lang="ko">([\s\S]*?)<\/(?:p|pre)\s*>/g),
  ];
  assert.equal(examples.length, 9);
  assert.ok(examples.every((match) => !match[1].includes("data-i18n")));
  assert.ok(examples.some((match) => match[1].includes("수요일")));
});
