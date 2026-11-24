/* DICED offline UI: keypad, toggles, results, log, theme, compact mode. */
(function () {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const input = $("sequence");
  const LOG_KEY = "dicedLog";
  const LOG_MAX = 7;

  function store(key, value) {
    try { localStorage.setItem(key, value); } catch (_e) { /* private mode */ }
  }
  function load(key) {
    try { return localStorage.getItem(key); } catch (_e) { return null; }
  }

  const pct = (x) => `${(x * 100).toFixed(1)}%`;

  // ---------------------------------------------------------- keypad

  document.querySelectorAll(".key-row[data-tokens]").forEach((row) => {
    for (const t of row.dataset.tokens.split(" ")) {
      const b = document.createElement("button");
      b.type = "button";
      b.className = `key ${row.dataset.class || ""}`.trim();
      b.dataset.token = t;
      b.textContent = t;
      row.appendChild(b);
    }
  });

  const toggleRow = $("toggle-row");
  const toggles = {};
  for (const name of DICED.OPTION_NAMES) {
    const label = document.createElement("label");
    label.className = "key key-mod key-toggle";
    const box = document.createElement("input");
    box.type = "checkbox";
    box.className = "option-toggle";
    box.dataset.option = name;
    const span = document.createElement("span");
    span.textContent = DICED.OPTION_LABELS[name];
    label.append(box, span);
    toggleRow.appendChild(label);
    toggles[name] = box;
  }

  function focusEnd() {
    // Avoid popping up the phone keyboard on every key tap.
    if (window.matchMedia("(pointer: fine)").matches) input.focus();
  }

  function appendToken(t) {
    const v = input.value.replace(/\s+$/, "");
    input.value = v ? `${v} ${t}` : t;
    focusEnd();
  }
  function appendSuffix(s) {
    const v = input.value.replace(/\s+$/, "");
    if (!v) return;
    input.value = v + s;
    focusEnd();
  }

  document.addEventListener("click", (e) => {
    const key = e.target.closest(".key");
    if (!key) return;
    if (key.dataset.token) appendToken(key.dataset.token);
    else if (key.dataset.suffix) appendSuffix(key.dataset.suffix);
    else if (key.id === "key-back") {
      const parts = input.value.trim().split(/\s+/);
      parts.pop();
      input.value = parts.join(" ");
    } else if (key.id === "key-clear") input.value = "";
    if (navigator.vibrate && key.tagName === "BUTTON") navigator.vibrate(8);
  });

  // ---------------------------------------------------------- results

  const zone = $("result-zone");
  function showResult(main, rr, armour, message, state) {
    zone.className = `result-zone${state ? ` ${state}` : ""}`;
    $("main-result").textContent = main;
    $("rr-result").innerHTML = rr;
    $("armour-line").textContent = armour || "";
    $("armour-line").hidden = !armour;
    $("message-line").textContent = message;
  }

  function logLine(sequence, result) {
    const width = 66;
    const dots = Math.max(6, width - sequence.length - result.length);
    return `${sequence} ${".".repeat(dots)} ${result}`;
  }

  let log = [];
  try { log = JSON.parse(load(LOG_KEY) || "[]"); } catch (_e) { log = []; }
  if (!Array.isArray(log)) log = [];

  function renderLog() {
    const panel = $("log-panel");
    panel.innerHTML = "";
    if (!log.length) {
      const p = document.createElement("p");
      p.className = "log-line placeholder-line";
      p.textContent = "Type a chain and press Go! to write a log line here.";
      panel.appendChild(p);
      return;
    }
    for (const line of log.slice().reverse()) {
      const p = document.createElement("p");
      p.className = "log-line";
      p.textContent = line;
      panel.appendChild(p);
    }
  }

  function addLog(line) {
    log.push(line);
    log = log.slice(-LOG_MAX);
    store(LOG_KEY, JSON.stringify(log));
    renderLog();
  }

  function calculate() {
    const text = input.value.trim();
    if (!text) return;
    const state = {};
    for (const [name, box] of Object.entries(toggles)) state[name] = box.checked;
    try {
      const r = DICED.evaluate(text, state);
      const [base, rr1, rr2] = r.totals;
      const armour = r.armour
        ? Object.entries(r.armour).map(([label, v]) => `${label} ${pct(v[0])}`).join(" · ")
        : "";
      const opts = r.labels.length ? ` · ${r.labels.join(", ")}` : "";
      showResult(
        pct(base),
        `<span class="rr-tag">1 RR</span> ${pct(rr1)} <span class="rr-sep">/</span> <span class="rr-tag">2 RR</span> ${pct(rr2)}`,
        armour,
        r.tokens.join(" ") + opts,
        "",
      );
      let seq = r.tokens.join(" ");
      if (r.labels.length) seq += ` [${r.labels.join(", ")}]`;
      addLog(logLine(seq, `${pct(base)} (${pct(rr1)} / ${pct(rr2)})`));
    } catch (err) {
      showResult("-%", "-% / -%", "", err.message, "error-state");
      addLog(`${text}: ERROR (${err.message})`);
    }
    if (window.matchMedia("(pointer: coarse)").matches) input.blur();
  }

  $("sequence-form").addEventListener("submit", (e) => {
    e.preventDefault();
    calculate();
  });

  // ------------------------------------------------- theme & compact

  const themeToggle = $("theme-toggle");
  const isDark = () => {
    const t = document.documentElement.dataset.theme;
    if (t) return t === "dark";
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  };
  const syncThemeIcon = () => { themeToggle.textContent = isDark() ? "☀" : "☾"; };
  themeToggle.addEventListener("click", () => {
    const next = isDark() ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    store("dicedTheme", next);
    syncThemeIcon();
  });
  syncThemeIcon();

  const compactToggle = $("compact-toggle");
  // Compact is the default on phones until the user chooses otherwise.
  const savedCompact = load("dicedCompact");
  const isPhone = /iPhone|iPod|Android.*Mobile|Mobi/i.test(navigator.userAgent) || (matchMedia("(pointer: coarse)").matches && Math.min(screen.width, screen.height) < 600);
  const compactOn = savedCompact === null ? isPhone : savedCompact === "1";
  compactToggle.checked = compactOn;
  document.body.classList.toggle("compact", compactOn);
  document.documentElement.classList.remove("compact-pending");
  compactToggle.addEventListener("change", () => {
    document.body.classList.toggle("compact", compactToggle.checked);
    store("dicedCompact", compactToggle.checked ? "1" : "0");
  });

  // ------------------------------------------------------ help panel

  const panel = $("syntax-help-panel");
  const overlay = $("syntax-overlay");
  const openHelp = () => { panel.classList.remove("is-hidden"); overlay.classList.remove("is-hidden"); };
  const closeHelp = () => { panel.classList.add("is-hidden"); overlay.classList.add("is-hidden"); };
  $("syntax-help-open").addEventListener("click", openHelp);
  $("syntax-help-close").addEventListener("click", closeHelp);
  overlay.addEventListener("click", closeHelp);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeHelp(); });

  renderLog();

  // ------------------------------------------------------- offline

  if ("serviceWorker" in navigator && location.protocol !== "file:") {
    navigator.serviceWorker.register("sw.js").catch(() => {});
  }
})();
