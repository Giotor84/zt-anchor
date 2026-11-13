/* ZT Anchor contract lint — JavaScript port of src/zt_anchor/contract_lint.py and the amount helpers of
 * it_normalize.py. Deterministic, no network. Works in the browser (window.ZtAnchorLint) and in Node (require). */
(function (root) {
  "use strict";

  // ------------------------------------------------------------ amounts in digits
  function parseAmount(text) {
    if (text == null) return null;
    let s = String(text).trim().replace(/\b(?:eur|euro)\b|€/gi, "").trim();
    s = s.replace(/[  '’]/g, "");
    if (!s || !/^[-+]?[\d.,]+$/.test(s)) return null;
    const sign = s.startsWith("-") ? -1 : 1;
    s = s.replace(/^[+-]/, "");
    if (s.includes(",") && s.includes(".")) {
      s = s.lastIndexOf(",") > s.lastIndexOf(".") ? s.replace(/\./g, "").replace(",", ".") : s.replace(/,/g, "");
    } else if (s.includes(",")) {
      if ((s.match(/,/g) || []).length > 1) return null;
      s = s.replace(",", ".");
    } else if (s.includes(".")) {
      const parts = s.split(".");
      if (parts.length > 2 || (parts.length === 2 && parts[1].length === 3)) {
        if (!parts.slice(1).every(p => p.length === 3)) return null;
        s = s.replace(/\./g, "");
      }
    }
    const v = Number(s);
    return Number.isFinite(v) ? sign * v : null;
  }

  // ------------------------------------------------------------ amounts in words
  const UNITS = { zero: 0, un: 1, uno: 1, una: 1, due: 2, tre: 3, quattro: 4, cinque: 5, sei: 6, sette: 7, otto: 8,
    nove: 9, dieci: 10, undici: 11, dodici: 12, tredici: 13, quattordici: 14, quindici: 15, sedici: 16,
    diciassette: 17, diciotto: 18, diciannove: 19 };
  const TENS = { venti: 20, trenta: 30, quaranta: 40, cinquanta: 50, sessanta: 60, settanta: 70, ottanta: 80, novanta: 90 };
  const has = (o, k) => Object.prototype.hasOwnProperty.call(o, k);

  function lt100(s) {
    if (has(UNITS, s)) return UNITS[s];
    for (const word of Object.keys(TENS)) {
      for (const stem of [word, word.slice(0, -1)]) {
        if (!s.startsWith(stem)) continue;
        const rest = s.slice(stem.length);
        if (rest === "") { if (stem === word) return TENS[word]; continue; }
        const elided = rest === "uno" || rest === "otto";
        if (has(UNITS, rest) && UNITS[rest] >= 1 && UNITS[rest] <= 9 && ((stem === word) !== elided)) return TENS[word] + UNITS[rest];
      }
    }
    throw new Error(s);
  }

  function lt1000(s) {
    if (s === "") return 0;
    s = s.replace("centott", "centoott");
    const i = s.indexOf("cento");
    if (i < 0) return lt100(s);
    const pre = s.slice(0, i), post = s.slice(i + 5);
    const h = pre === "" ? 1 : UNITS[pre];
    if (!(h >= 1 && h <= 9)) throw new Error(s);
    return h * 100 + (post ? lt100(post) : 0);
  }

  function parseWords(s) {
    for (const [word, mult] of [["miliardi", 1e9], ["miliardo", 1e9], ["milioni", 1e6], ["milione", 1e6]]) {
      const i = s.indexOf(word);
      if (i >= 0) {
        const pre = s.slice(0, i), post = s.slice(i + word.length);
        const n = (pre === "" || pre === "un" || pre === "uno") ? 1 : parseWords(pre);
        return n * mult + (post ? parseWords(post) : 0);
      }
    }
    if (s.startsWith("mille")) return 1000 + lt1000(s.slice(5));
    const i = s.indexOf("mila");
    if (i >= 0) return lt1000(s.slice(0, i)) * 1000 + lt1000(s.slice(i + 4));
    return lt1000(s);
  }

  function wordsToNumber(text) {
    let s = text.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
    s = s.replace(/\b(?:euro|eur)\b|€/g, " ");
    let cents = 0;
    const m = s.match(/\/\s*(\d{1,2})\s*$/);
    if (m) { cents = Number(m[1].padEnd(2, "0")) / 100; s = s.slice(0, m.index); }
    else if (s.includes("virgola")) {
      const parts = s.split("virgola");
      s = parts[0];
      const dec = parts.slice(1).join("virgola").replace(/[\s-]/g, "");
      try { cents = (dec ? lt100(dec) : 0) / 100; } catch (e) { return null; }
    }
    s = (" " + s + " ").replace(/\s+e\s+/g, " ").replace(/[\s-]/g, "");
    if (!s || !/^[a-z]+$/.test(s)) return null;
    try { return Math.round((parseWords(s) + cents) * 100) / 100; } catch (e) { return null; }
  }

  // ------------------------------------------------------------ checks
  const finding = (rule, severity, message, text, start, end) => ({ rule, severity, message, start, end, excerpt: text.slice(start, end) });
  const esc = s => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

  const AMOUNT_WITH_WORDS = /(?:€|euro|eur)\s*(\d{1,3}(?:\.\d{3})*(?:,\d{1,2})?|\d+(?:,\d{1,2})?)\s*\(\s*(?:euro\s+)?([a-zàèéìòù\s'\/\-0-9]+?)\s*\)/gi;

  function checkAmounts(text) {
    const out = [];
    for (const m of text.matchAll(AMOUNT_WITH_WORDS)) {
      const digits = parseAmount(m[1]), words = wordsToNumber(m[2]);
      const end = m.index + m[0].length;
      if (words === null) out.push(finding("amount_words_unreadable", "warning", "amount in words not readable", text, m.index, end));
      else if (digits !== null && Math.abs(digits - words) > 0.004)
        out.push(finding("amount_mismatch", "error", `digits say ${digits}, words say ${words}`, text, m.index, end));
    }
    return out;
  }

  function checkSections(text, required) {
    return (required || []).filter(t => t.trim()).filter(title =>
      !new RegExp(`^\\s*(?:\\d+[.)]?\\s*|art(?:icolo|\\.)\\s*\\d+\\s*[-–.:]?\\s*)?${esc(title.trim())}(?![\\wàèéìòù])`, "im").test(text)
    ).map(title => ({ rule: "section_missing", severity: "error", message: `missing section: ${title.trim()}`, start: 0, end: 0, excerpt: "" }));
  }

  const DEF = /\((?:di seguito|in seguito|d'ora innanzi|breviter)?[^()]{0,30}?[«"“]([^»"”]{2,60})[»"”]\s*\)/gi;

  function checkDefinitions(text) {
    const out = [];
    for (const m of text.matchAll(DEF)) {
      const term = m[1].trim(), end = m.index + m[0].length;
      if (!new RegExp(`(?<![\\wàèéìòù])${esc(term)}(?![\\wàèéìòù])`).test(text.slice(end)))
        out.push(finding("definition_unused", "warning", `defined term never used: ${term}`, text, m.index, end));
    }
    return out;
  }

  const ART_HEAD = /^\s*art(?:icolo|\.)\s*(\d+)/gim;
  const ART_REF = /\bart(?:icol[oi]|t?\.)\s*(\d+)(?:\s*(?:,|e)\s*(\d+))?/gi;
  const LAW_AFTER = /^[\s,]*(?:(?:comma|co\.|lett\.|lettera|n\.|num\.)\s*\w+[\s,]*)*(?:c\.?\s?c\.|c\.?\s?p\.?\s?c\.|c\.?\s?p\.|cod\.|codice|d\.?\s?lgs|d\.?\s?l\.|d\.?\s?p\.?\s?r|l\.|legge|reg\.|regolamento|r\.?\s?d\.|tub|tuf|cost\.)/i;

  function checkReferences(text) {
    const defined = new Set([...text.matchAll(ART_HEAD)].map(m => Number(m[1])));
    const out = [];
    for (const m of text.matchAll(ART_REF)) {
      const end = m.index + m[0].length;
      const lineStart = text.lastIndexOf("\n", m.index - 1) + 1;
      const head = new RegExp(ART_HEAD.source, "iy"); head.lastIndex = lineStart;
      const hm = head.exec(text);
      if (hm && lineStart + hm[0].length >= end - 1) continue;
      if (LAW_AFTER.test(text.slice(end, end + 40))) continue;
      for (const g of [m[1], m[2]]) {
        if (g && !defined.has(Number(g)))
          out.push(finding("reference_missing", "error", `refers to art. ${g}, which is not in the document`, text, m.index, end));
      }
    }
    return out;
  }

  function lint(text, requiredSections) {
    const f = [...checkAmounts(text), ...checkDefinitions(text), ...checkReferences(text)];
    if (requiredSections && requiredSections.length) f.push(...checkSections(text, requiredSections));
    return f.sort((a, b) => a.start - b.start || (a.rule < b.rule ? -1 : a.rule > b.rule ? 1 : 0));
  }

  const api = { parseAmount, wordsToNumber, checkAmounts, checkSections, checkDefinitions, checkReferences, lint };
  if (typeof module !== "undefined" && module.exports) module.exports = api; else root.ZtAnchorLint = api;
})(typeof window !== "undefined" ? window : globalThis);
