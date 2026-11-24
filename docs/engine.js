/* DICED calculation engine — JavaScript port of src/diced/core.py.
 * Runs in the browser (window.DICED) and in Node (module.exports) so the
 * parity test can compare it against the Python reference.
 */
(function (root) {
  "use strict";

  // ---------------------------------------------------------------- dice

  // Block die faces: POW, POW* (stumble), PUSH, PUSH, BOTH DOWN, SKULL (attacker down).
  const BLOCK_FACES = { "": 2, "+": 3, "*": 1, "-": 4, "+-": 5, "/": 2 };
  const DIE = ["pow", "stumble", "push", "push", "both", "skull"];

  function rollProbability(threshold) {
    if (threshold < 1 || threshold > 6) throw new Error("Roll target must be between 1 and 6 on a D6.");
    // A natural 1 always fails, so 1+ is the same as 2+.
    return (7 - Math.max(threshold, 2)) / 6;
  }

  function wantedFaces(outcome) {
    if (!(outcome in BLOCK_FACES)) throw new Error(`Unknown block die outcome: '${outcome}'.`);
    const base = { "": ["pow", "stumble"], "*": ["pow"], "-": ["pow", "stumble", "push"], "/": ["push"] }[
      outcome.replace(/\+/g, "")
    ];
    return new Set(outcome.includes("+") ? [...base, "both"] : base);
  }

  // Attacker picks any die; the defender (-2d/-3d) picks the result worst for the
  // attacker: Skull, Both Down (unless attacker has Block), Push, Stumble, Both Down with Block, Pow.
  function blockSucceeds(t, faces) {
    const wanted = wantedFaces(t.outcome);
    const eff = faces.map((f) => (f === "stumble" && t.stunty ? "push" : f));
    if (!t.negative) return eff.some((f) => wanted.has(f));
    const hasBlock = t.block || t.outcome.includes("+");
    const rank = { skull: 0, both: hasBlock ? 4 : 1, push: 2, stumble: 3, pow: 5 };
    let chosen = eff[0];
    for (const f of eff) if (rank[f] < rank[chosen]) chosen = f;
    return wanted.has(chosen);
  }

  function* blockPools(n) {
    const total = 6 ** n;
    for (let code = 0; code < total; code++) {
      const faces = [];
      let c = code;
      for (let k = 0; k < n; k++) { faces.push(DIE[c % 6]); c = Math.floor(c / 6); }
      yield faces;
    }
  }

  function blockDieSingle(outcome) {
    if (!(outcome in BLOCK_FACES)) throw new Error(`Unknown block die outcome: '${outcome}'.`);
    return BLOCK_FACES[outcome] / 6;
  }

  function blockBase(t) {
    let hits = 0;
    for (const faces of blockPools(t.diceCount)) if (blockSucceeds(t, faces)) hits++;
    return hits / 6 ** t.diceCount;
  }

  function twoD6AtLeast(target) {
    let n = 0;
    for (let a = 1; a <= 6; a++) for (let b = 1; b <= 6; b++) if (a + b >= target) n++;
    return n / 36;
  }

  function armorBreak(target) {
    if (target < 1 || target > 11) throw new Error("Armor value target must be between 1 and 11.");
    return twoD6AtLeast(target);
  }

  const INJURY_TARGETS = { k: 8, i: 10, ks: 7, si: 9 };

  function normalizeInjurySuffix(suffix) {
    if (!suffix) return "";
    const lowered = suffix.toLowerCase();
    if (/[^kism]/.test(lowered)) {
      throw new Error(`Invalid injury suffix: '${suffix}'. Use k, i, ks/sk, si/is, optionally with m.`);
    }
    const mCount = (lowered.match(/m/g) || []).length;
    if (mCount > 1) throw new Error(`Invalid injury suffix: '${suffix}'. 'm' can be used at most once.`);
    const hasM = mCount === 1;
    let core = lowered.replace(/m/g, "");
    core = { sk: "ks", is: "si" }[core] || core;
    if (core === "" || core === "s") return hasM ? "m" : "";
    if (!(core in INJURY_TARGETS)) {
      throw new Error(`Invalid injury suffix: '${suffix}'. Use k, i, ks/sk, si/is, optionally with m.`);
    }
    return core + (hasM ? "m" : "");
  }

  function injuryProbability(suffix) {
    const n = normalizeInjurySuffix(suffix);
    if (!n) return 1;
    const hasM = n.endsWith("m");
    const core = hasM ? n.slice(0, -1) : n;
    if (!core) return 1;
    return twoD6AtLeast(INJURY_TARGETS[core] - (hasM ? 1 : 0));
  }

  // Mighty Blow modifies armour OR injury, chosen after the armour roll.
  function armorAndInjury(t) {
    const n = normalizeInjurySuffix(t.injurySuffix);
    if (!n.endsWith("m")) return armorBreak(t.target) * injuryProbability(n);
    const core = n.slice(0, -1);
    if (!core) return twoD6AtLeast(t.target - 1);
    const injuryTarget = INJURY_TARGETS[core];
    const clean = twoD6AtLeast(t.target);
    const oneShort = twoD6AtLeast(t.target - 1) - clean;
    return clean * twoD6AtLeast(injuryTarget - 1) + oneShort * twoD6AtLeast(injuryTarget);
  }

  // -------------------------------------------------------------- tokens

  function d6(threshold, localRerolls = 0, weighted = false) {
    return { kind: "d6", threshold, localRerolls, weighted };
  }
  function block(diceCount, negative, outcome, localRerolls = 0, hasBlock = false, stunty = false) {
    return { kind: "block", diceCount, negative, outcome, localRerolls, block: hasBlock, stunty };
  }
  function armor(target, injurySuffix = "") {
    return { kind: "armor", target, injurySuffix, localRerolls: 0 };
  }

  function token(step) {
    if (step.kind === "d6") {
      return step.weighted ? `${step.threshold}+p` : `${step.threshold}${"+".repeat(step.localRerolls + 1)}`;
    }
    if (step.kind === "block") {
      return `${step.negative ? "-" : ""}${step.diceCount}d${step.outcome}${step.localRerolls ? "++" : ""}`;
    }
    return `av${step.target}${step.injurySuffix}`;
  }

  function displayToken(step) {
    if (step.kind === "d6") return step.weighted ? `${step.threshold}+ (pro)` : token(step);
    if (step.kind === "block") {
      const labels = {
        "+": ["Block"], "-": ["No Turnover"], "*": ["Pow"], "/": ["Push Only"], "+-": ["Block", "No Turnover"],
      }[step.outcome] || [];
      if (step.localRerolls) labels.push("Brawler");
      const base = `${step.negative ? "-" : ""}${step.diceCount}d`;
      return labels.length ? `${base} (${labels.join(", ")})` : base;
    }
    if (!step.injurySuffix) return `av${step.target}`;
    const hasM = step.injurySuffix.endsWith("m");
    const core = hasM ? step.injurySuffix.slice(0, -1) : step.injurySuffix;
    if (!core) return `av${step.target} (mb)`;
    let label = { k: "ko", i: "injury", ks: "stunty ko", si: "stunty injury" }[core];
    if (hasM) label += " (mb)";
    return `av${step.target} ${label}`;
  }

  // ------------------------------------------------------------- parsing

  const isDigit = (c) => c >= "0" && c <= "9";
  const lower = (c) => (c || "").toLowerCase();

  function startsArmor(text, i) {
    if (i >= text.length || lower(text[i]) !== "a") return false;
    let j = i + 1;
    if (j < text.length && lower(text[j]) === "v") j++;
    return j < text.length && isDigit(text[j]);
  }

  function parseArmorFrom(text, i) {
    const start = i;
    i++;
    if (i < text.length && lower(text[i]) === "v") i++;
    if (i >= text.length || !isDigit(text[i])) {
      throw new Error(`Invalid armor token near '${text.slice(start)}'. Use a1..a11 or av1..av11.`);
    }
    let digits = text[i++];
    if (i < text.length && isDigit(text[i])) digits += text[i++];
    const target = parseInt(digits, 10);
    if (target < 1 || target > 11) throw new Error(`Invalid armor value ${target}. Use a1..a11 or av1..av11.`);
    const s = i;
    while (i < text.length && "kism".includes(lower(text[i]))) i++;
    return [armor(target, normalizeInjurySuffix(text.slice(s, i))), i];
  }

  function startsBlock(text, i) {
    if (i >= text.length) return false;
    if (text[i] === "-") {
      return i + 2 < text.length && "123".includes(text[i + 1]) && lower(text[i + 2]) === "d";
    }
    return i + 1 < text.length && "123".includes(text[i]) && lower(text[i + 1]) === "d";
  }

  const BLOCK_HELP = "Use e.g. 1d, 2d+, 3d*, -2d, -3d-, 2d+-, or 2d+++ for Brawler.";

  function parseBlockFrom(text, i) {
    const start = i;
    let negative = false;
    if (text[i] === "-") { negative = true; i++; }
    if (i >= text.length || !"123".includes(text[i])) {
      throw new Error(`Invalid block dice token near '${text.slice(start)}'. ${BLOCK_HELP}`);
    }
    const diceCount = parseInt(text[i++], 10);
    if (i >= text.length || lower(text[i]) !== "d") {
      throw new Error(`Invalid block dice token near '${text.slice(start)}'. ${BLOCK_HELP}`);
    }
    i++;
    let outcome = "";
    let localRerolls = 0;
    const two = text.slice(i, i + 2);
    if (two === "+-" || two === "-+") {
      outcome = "+-"; i += 2;
    } else if (i < text.length && "*/-".includes(text[i])) {
      outcome = text[i++];
    } else if (i < text.length && text[i] === "+") {
      let plus = 0;
      while (i < text.length && text[i] === "+") { plus++; i++; }
      if (plus === 1) outcome = "+";
      else if (plus === 2) localRerolls = 1;
      else if (plus === 3) { outcome = "+"; localRerolls = 1; }
      else throw new Error(`Invalid block dice token near '${text.slice(start, i)}'. Too many '+' markers after 'd'.`);
    }
    if (localRerolls === 0 && text.slice(i, i + 2) === "++") { localRerolls = 1; i += 2; }
    return [block(diceCount, negative, outcome, localRerolls), i];
  }

  function parseD6From(text, i) {
    if (i >= text.length || text[i] < "1" || text[i] > "6") {
      throw new Error(`Invalid roll target near '${text.slice(i)}'. Use values like 2+, 3++, 6+ or shorthand like 224s3.`);
    }
    const threshold = parseInt(text[i], 10);
    let localRerolls = 0;
    let weighted = false;
    let j = i + 1;
    if (j < text.length && lower(text[j]) === "p") {
      weighted = true; j++;
    } else if (text.slice(j, j + 2) === "++") {
      localRerolls = 1; j += 2;
    } else if (j < text.length && text[j] === "+") {
      j++;
      if (j < text.length && lower(text[j]) === "p") { weighted = true; j++; }
    } else if (j < text.length && lower(text[j]) === "s") {
      localRerolls = 1; j++;
    }
    return [d6(threshold, localRerolls, weighted), j];
  }

  function parseMixedPart(part) {
    const steps = [];
    let i = 0;
    while (i < part.length) {
      let r;
      if (startsArmor(part, i)) r = parseArmorFrom(part, i);
      else if (startsBlock(part, i)) r = parseBlockFrom(part, i);
      else r = parseD6From(part, i);
      steps.push(r[0]);
      i = r[1];
    }
    return steps;
  }

  const splitParts = (text) => text.trim().split(/[,\s]+/).filter(Boolean);

  function combineSpacedArmor(parts) {
    const out = [];
    for (let i = 0; i < parts.length; ) {
      const cur = parts[i];
      if (/^a(?:v)?(?:[1-9]|10|11)$/i.test(cur)) {
        let j = i + 1;
        let suffix = "";
        while (j < parts.length && /^[kism]+$/i.test(parts[j])) suffix += parts[j++];
        out.push(cur + suffix);
        i = j;
      } else {
        out.push(cur);
        i++;
      }
    }
    return out;
  }

  function parseRollSequence(raw) {
    let parts = splitParts(raw);
    if (!parts.length) throw new Error("Enter at least one target roll such as 2+, 3+, 4+.");
    parts = combineSpacedArmor(parts);
    const steps = [];
    for (const p of parts) steps.push(...parseMixedPart(p));
    return steps;
  }

  function parseWithPro(raw) {
    const parts = splitParts(raw);
    let pro = parts.some((p) => p.toLowerCase() === "p");
    const remaining = parts.filter((p) => p.toLowerCase() !== "p").join(" ");
    if (!remaining) throw new Error("Enter at least one target roll such as 2+, 3+, 4+.");
    const steps = parseRollSequence(remaining).map((s) => {
      if (s.kind === "d6" && s.weighted) { pro = true; return d6(s.threshold, s.localRerolls); }
      return s;
    });
    return [steps, pro];
  }

  // 's' means vs Stunty unless it directly follows a D6 digit (224s3 shorthand).
  function extractStunty(text) {
    let found = false;
    const armourSuffix = /(a(?:v)?\d{1,2}[kim]*)s([kim]*)/i;
    let m;
    while ((m = armourSuffix.exec(text))) {
      found = true;
      text = text.slice(0, m.index) + m[1] + m[2] + text.slice(m.index + m[0].length);
    }
    let out = "";
    for (let i = 0; i < text.length; i++) {
      const c = text[i];
      const prev = i > 0 ? text[i - 1] : "";
      if (lower(c) === "s" && !(prev >= "1" && prev <= "6")) { found = true; out += " "; }
      else out += c;
    }
    return [out, found];
  }

  const OPTION_NAMES = ["block", "pro", "brawler", "mighty_blow", "stunty"];
  const OPTION_LABELS = { block: "Block", pro: "Pro", brawler: "Brawler", mighty_blow: "MB", stunty: "vs Stunty" };

  function optionLabels(o) {
    return OPTION_NAMES.filter((n) => o[n]).map((n) => OPTION_LABELS[n]);
  }

  function mergeOptions(a, b) {
    const r = {};
    for (const n of OPTION_NAMES) r[n] = Boolean(a[n] || b[n]);
    return r;
  }

  function parseSequence(raw) {
    const brawler = /b/i.test(raw);
    let cleaned = raw.replace(/b/gi, " ");
    let stunty;
    [cleaned, stunty] = extractStunty(cleaned);
    const [steps, pro] = parseWithPro(cleaned);
    return [steps, { block: false, pro, brawler, mighty_blow: false, stunty }];
  }

  const injuryCore = (suffix) => suffix.replace(/[ms]/g, "");

  function withInjury(step, injury, o) {
    const hasM = o.mighty_blow || step.injurySuffix.endsWith("m");
    const stunty = o.stunty || step.injurySuffix.includes("s");
    let suffix = injury;
    if (injury && stunty) suffix = { k: "ks", i: "si" }[injury];
    if (hasM) suffix += "m";
    return armor(step.target, normalizeInjurySuffix(suffix));
  }

  function applyOptions(steps, o) {
    return steps.map((s) => {
      if (s.kind === "block") {
        let outcome = s.outcome;
        if (o.block) outcome = { "": "+", "-": "+-" }[outcome] ?? outcome;
        return block(
          s.diceCount, s.negative, outcome, o.brawler ? 1 : s.localRerolls,
          Boolean(o.block) || outcome.includes("+"), Boolean(o.stunty),
        );
      }
      if (s.kind === "armor") return withInjury(s, injuryCore(s.injurySuffix), o);
      return s;
    });
  }

  // --------------------------------------------------------- calculation

  // Enumerate a block pool face by face into success and failure classes.
  // Rescues (only one per roll): free = Brawler re-rolls one unwanted Both Down
  // (always taken when it can help), pro = best single die after 2/3, rr = whole pool.
  function blockBranches(t) {
    const n = t.diceCount;
    const die = 1 / 6;
    const single = blockBase(t);
    const wanted = wantedFaces(t.outcome);
    const rescue = (faces, index) => {
      let chance = 0;
      for (const face of DIE) {
        const next = faces.slice();
        next[index] = face;
        if (blockSucceeds(t, next)) chance += die;
      }
      return chance;
    };
    const classes = new Map();
    let ok = 0;
    for (const faces of blockPools(n)) {
      const prob = die ** n;
      if (blockSucceeds(t, faces)) { ok += prob; continue; }
      let free = 0;
      if (t.localRerolls && !wanted.has("both") && faces.includes("both")) free = rescue(faces, faces.indexOf("both"));
      let pro = 0;
      for (let i = 0; i < n; i++) pro = Math.max(pro, rescue(faces, i));
      const key = `${free}|${pro}`;
      const cur = classes.get(key);
      if (cur) cur[0] += prob;
      else classes.set(key, [prob, free, pro]);
    }
    const branches = [];
    for (const [prob, free, pro] of classes.values()) {
      const actions = {};
      if (free > 0) actions.free = free;
      else {
        if (single > 0) actions.rr = single;
        if (pro > 0) actions.pro = (2 / 3) * pro;
      }
      branches.push([prob, actions]);
    }
    return [ok, branches];
  }

  function stepBranches(t) {
    if (t.kind === "armor") return [armorAndInjury(t), []];
    if (t.kind === "block") return blockBranches(t);
    const single = rollProbability(t.threshold);
    if (t.weighted) return [single, [[1 - single, { free: (2 / 3) * single }]]];
    if (t.localRerolls) return [single, [[1 - single, { free: single }]]];
    return [single, [[1 - single, { rr: single, pro: (2 / 3) * single }]]];
  }

  // Best re-roll policy over states (team RR left, Pro available).
  function chainHistory(sequence, rerolls, pro) {
    const n = sequence.length;
    const branches = sequence.map(stepBranches);
    const key = (r, p) => r * 2 + p;
    const states = [];
    for (let r = 0; r <= rerolls; r++) for (const p of [0, 1]) states.push([r, p]);
    const value = Array.from({ length: n + 1 }, () => new Map());
    for (const [r, p] of states) value[n].set(key(r, p), 1);

    function transitions(i, r, p) {
      const [ok, fails] = branches[i];
      const result = [[ok, [r, p]]];
      for (const [prob, actions] of fails) {
        if ("free" in actions) { result.push([prob * actions.free, [r, p]]); continue; }
        const options = [];
        if ("rr" in actions && r > 0) options.push([actions.rr, [r - 1, p]]);
        if ("pro" in actions && p) options.push([actions.pro, [r, 0]]);
        if (options.length) {
          let best = options[0];
          let bestValue = best[0] * value[i + 1].get(key(...best[1]));
          for (const o of options.slice(1)) {
            const v = o[0] * value[i + 1].get(key(...o[1]));
            if (v > bestValue) { best = o; bestValue = v; }
          }
          result.push([prob * best[0], best[1]]);
        }
      }
      return result;
    }

    for (let i = n - 1; i >= 0; i--) {
      for (const [r, p] of states) {
        let v = 0;
        for (const [prob, nxt] of transitions(i, r, p)) v += prob * value[i + 1].get(key(...nxt));
        value[i].set(key(r, p), v);
      }
    }

    const history = [];
    let dist = new Map([[key(rerolls, pro ? 1 : 0), [rerolls, pro ? 1 : 0, 1]]]);
    for (let i = 0; i < n; i++) {
      const next = new Map();
      for (const [r, p, mass] of dist.values()) {
        for (const [prob, [nr, np]] of transitions(i, r, p)) {
          const k = key(nr, np);
          const cur = next.get(k);
          if (cur) cur[2] += mass * prob;
          else next.set(k, [nr, np, mass * prob]);
        }
      }
      dist = next;
      let sum = 0;
      for (const v of dist.values()) sum += v[2];
      history.push(sum);
    }
    return history;
  }

  function calculate(sequence, maxRerolls = 2, pro = false) {
    if (!sequence.length) throw new Error("Sequence cannot be empty.");
    for (const t of sequence) {
      if (t.localRerolls !== 0 && t.localRerolls !== 1) throw new Error("Each die can be rerolled at most once.");
    }
    const totals = [];
    for (let r = 0; r <= maxRerolls; r++) {
      const h = chainHistory(sequence, r, pro);
      totals.push(h[h.length - 1]);
    }
    return { totals, tokens: sequence.map(displayToken) };
  }

  function armourOutcomes(steps, o, maxRerolls = 2) {
    let last = -1;
    steps.forEach((s, i) => { if (s.kind === "armor") last = i; });
    if (last < 0) return null;
    const out = {};
    for (const [label, injury] of [["Break", ""], ["KO", "k"], ["CAS", "i"]]) {
      const variant = steps.slice();
      variant[last] = withInjury(steps[last], injury, o);
      out[label] = calculate(variant, maxRerolls, o.pro).totals;
    }
    return out;
  }

  /** One call for the UI: text + toggle options -> everything to display. */
  function evaluate(text, toggles) {
    const [parsed, typed] = parseSequence(text);
    const options = mergeOptions(toggles || {}, typed);
    const steps = applyOptions(parsed, options);
    const result = calculate(steps, 2, options.pro);
    return {
      totals: result.totals,
      tokens: result.tokens,
      options,
      labels: optionLabels(options),
      armour: armourOutcomes(steps, options),
    };
  }

  const api = {
    evaluate, parseSequence, applyOptions, calculate, armourOutcomes, parseRollSequence,
    armorAndInjury, injuryProbability, blockDieSingle, displayToken, OPTION_NAMES, OPTION_LABELS,
  };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.DICED = api;
})(typeof self !== "undefined" ? self : this);
