// BOT-CODE-AUDIT web helper: parse JS (acorn) and CSS/SCSS/LESS (postcss) and report risky
// shapes. Read-only: reads one JSON document on stdin, writes one on stdout, never touches
// the network or the file system beyond its own modules. Every file either parses and is
// walked, or comes back {ok:false} so the caller reports it as unaudited (fail closed).
import * as acorn from "acorn";
import * as walk from "acorn-walk";
import postcss from "postcss";
import scss from "postcss-scss";
import less from "postcss-less";
import { transform as sucrase } from "sucrase";

// security core: browser code writing these changes who may do what, or runs code
const SENSITIVE = new Set([
  "ir.config_parameter", "res.users", "res.users.apikeys", "ir.rule", "ir.model.access",
  "res.groups", "ir.cron", "ir.mail_server", "ir.actions.server", "ir.module.module",
  "auth.totp.device", "ir.model.data",
]);
// models whose plain reads already leak secrets
const SECRET_MODELS = new Set(["ir.config_parameter", "res.users.apikeys", "auth.totp.device"]);
const ORM_WRITES = new Set(["write", "create", "unlink", "copy"]);
const WRITE_METHODS = new Set(["write", "create", "unlink", "copy", "set_param", "set_values",
  "execute", "sudo", "button_immediate_install", "button_immediate_upgrade",
  "button_immediate_uninstall", "toggle_active", "action_archive", "action_unarchive", "run",
  "method_direct_trigger", "_set_password", "change_password"]);
const ORM_READS = new Set(["read", "search", "searchRead", "searchCount", "webSearchRead",
  "webRead", "readGroup", "webReadGroup", "nameSearch"]);
const GLOBALS = new Set(["window", "globalThis", "self", "top", "parent", "frames"]);
const SECRET = /token|secret|passw|api[_-]?key|session|csrf|auth(?!or)|bearer|jwt/i;
const ESCAPERS = /^(escape|htmlEscape|_\.escape|sanitize|sanitizeHtml|stripHtml|textContent)$/;

// constant string value, folding "a" + "b" and `a${"b"}` (so window["ev" + "al"] is eval)
// per-file: identifiers bound once to a constant string, and those holding document.cookie
let CONSTS = new Map();
let COOKIE_VARS = new Set();
let URL_VARS = new Set(); // locals holding a URL-controlled value
let PUSHED = new Map(); // CA11 H7: array domains built by push: name -> [init, ...pushed]
let JSURL_PROPS = new Set(); // CA11 H9: keys/properties bound to a javascript: URL literal
let EMPTY_VARS = new Set(); // locals holding ids/rows of an empty-domain search (H1/H2)
let PROPS_BUILT = false; // CA13 H3/L2: module XML/JS passes a module-built domain prop
let STATE_DOM = new Map(); // CA12 H3: view-state domain key -> what this module assigns to it
let URL_OBJS = new Map();
let URL_MUTS = new Map(); // CA13 H2: URL var -> [[prop, value]] writes (u.pathname = .. / Object.assign(u, {..})) // CA12 H2: once-bound new URL(..) whose path is never reassigned (search/hash may be)
let DOM_VARS = new Map(); // CA9 H5: identifier (once-bound) / helper name -> domain-valued expression(s)
// ORM HTTP endpoints reached with fetch / XHR / sendBeacon / axios (CA9 H6)
// CA13 M2: Odoo 19/20 JSON-1/JSON-2 APIs (/json/2/<model>/<method>) are the ORM too
const ORM_ROUTE = /\/web\/dataset\/(?:call_kw|call_button|call|search_read|resequence)\b|\/web\/action\/run\b|\/jsonrpc\b|\/xmlrpc\b|\/json\/[12](?:\/|\b)|\/web\/session\/authenticate/i;
// literal JS value (numbers, booleans, null, strings, arrays of those)
function jsVal(n) {
  if (!n) return { ok: false };
  if (n.type === "Literal") return { ok: true, v: n.value };
  if (n.type === "Identifier" && n.name === "undefined") return { ok: true, v: null };
  if (n.type === "UnaryExpression" && n.operator === "-" && n.argument.type === "Literal" && typeof n.argument.value === "number") return { ok: true, v: -n.argument.value };
  if (n.type === "ArrayExpression") {
    const xs = n.elements.map(jsVal);
    return xs.every((x) => x.ok) ? { ok: true, v: xs.map((x) => x.v) } : { ok: false };
  }
  const s = lit(n);
  return s === null ? { ok: false } : { ok: true, v: s };
}
const ALWAYS_SET = new Set(["id", "create_date", "write_date", "create_uid", "write_uid"]);
function leafTruth(el) {
  const [L, O, R] = el.map(jsVal);
  if (!O.ok || typeof O.v !== "string") return "C";
  const op = O.v.trim().toLowerCase();
  if (L.ok && R.ok && typeof L.v !== "string") {
    const t = { "=": L.v === R.v, "==": L.v === R.v, "!=": L.v !== R.v, "<>": L.v !== R.v, ">": L.v > R.v, ">=": L.v >= R.v, "<": L.v < R.v, "<=": L.v <= R.v }[op];
    return t === undefined ? "C" : (t ? "T" : "F");
  }
  if (!(L.ok && typeof L.v === "string" && R.ok)) return "C";
  const fld = L.v.split(".")[0], r = R.v;
  const isNum = typeof r === "number";
  if (ALWAYS_SET.has(fld)) {
    if ((op === "!=" || op === "<>") && (r === false || r === null || r === 0 || r === -1)) return "T";
    if ((op === "!=" || op === "<>") && fld === "id" && isNum && r <= 0) return "T";
    if (fld === "id" && isNum && ((op === ">" && r < 1) || (op === ">=" && r <= 1))) return "T";
    if (op === "not in" && Array.isArray(r) && r.every((v) => v === false || v === null || v === 0)) return "T";
  }
  if (op === "not in" && Array.isArray(r) && !r.length) return "T";
  if (op === "in" && Array.isArray(r) && !r.length) return "F";
  if (fld === "active" && op === "in" && Array.isArray(r) && r.includes(true) && r.includes(false)) return "T";
  return "C";
}
const AND = (a, b) => (a === "F" || b === "F") ? "F" : (a === "T" && b === "T" ? "T" : "C");
const OR = (a, b) => (a === "T" || b === "T") ? "T" : (a === "F" && b === "F" ? "F" : "C");
// T: the domain matches every record (empty, tautology, via names/helpers/concat/Domain.and);
// F: matches none; C: a real condition or a runtime value
function domTruth(d, depth = 0) {
  if (!d || (d.type === "Identifier" && d.name === "undefined")) return "T";
  if (depth > 8) return "C";
  if (d.type === "AwaitExpression") return domTruth(d.argument, depth + 1);
  if (d.type === "Identifier") {
    const vs = DOM_VARS.get(d.name);
    if (!vs) return "C";
    const ts = new Set(vs.map((v) => domTruth(v, depth + 1)));
    return ts.size === 1 ? [...ts][0] : "C";
  }
  if (d.type === "CallExpression") {
    const c = d.callee;
    const nm = c.type === "MemberExpression" ? (c.property.name || c.property.value) : (c.name || "");
    if (c.type === "Identifier" && DOM_VARS.has("()" + c.name)) {
      const ts = new Set(DOM_VARS.get("()" + c.name).map((v) => domTruth(v, depth + 1)));
      return ts.size === 1 ? [...ts][0] : "C";
    }
    if (nm === "concat" && c.type === "MemberExpression") return [c.object, ...d.arguments].map((x) => domTruth(x, depth + 1)).reduce(AND);
    if (/^(and|AND|or|OR)$/.test(nm) && d.arguments.length === 1 && d.arguments[0].type === "ArrayExpression") {
      const ps = d.arguments[0].elements.map((x) => domTruth(x, depth + 1));
      if (!ps.length) return /and/i.test(nm) ? "T" : "F";
      return ps.reduce(/and/i.test(nm) ? AND : OR);
    }
    if (nm === "toList" && c.type === "MemberExpression") return domTruth(c.object, depth + 1);
    if (nm === "Domain") return domTruth(d.arguments[0], depth + 1);
    return "C";
  }
  if (d.type === "NewExpression" && (d.callee.name === "Domain") ) return domTruth(d.arguments[0], depth + 1);
  if (d.type === "MemberExpression" && !d.computed && d.object.name === "Domain") return d.property.name === "TRUE" ? "T" : d.property.name === "FALSE" ? "F" : "C";
  if (d.type !== "ArrayExpression") return "C";
  const terms = [];
  for (const e of d.elements) {
    if (!e) return "C";
    if (e.type === "Literal" && ["&", "|", "!"].includes(e.value)) terms.push(e.value);
    else if (e.type === "ArrayExpression" && e.elements.length === 3) terms.push(leafTruth(e.elements));
    else if (e.type === "SpreadElement") terms.push(domTruth(e.argument, depth + 1));
    else return "C";
  }
  let pos = 0;
  const take = () => {
    if (pos >= terms.length) throw new Error("dom");
    const t = terms[pos++];
    if (t === "!") { const v = take(); return v === "T" ? "F" : v === "F" ? "T" : "C"; }
    if (t === "&" || t === "|") { const a = take(), b = take(); return t === "&" ? AND(a, b) : OR(a, b); }
    return t;
  };
  let out = "T";
  try { while (pos < terms.length) out = AND(out, take()); } catch { return "C"; }
  return out;
}
// CA11 H7: a domain is bounded (B) only when provably selective; anything unprovable (U) is
// treated as every record (negations, ranges over literals, '%' patterns, JSON.parse, params).
const MASS_JS = /^(unlink|write|_write|action_archive|action_unarchive|toggle_active)$/;
function leafBound(el) {
  const t = leafTruth(el);
  if (t === "T") return "U";
  if (t === "F") return "B";
  const [L, O, R] = el.map(jsVal);
  if (!O.ok || typeof O.v !== "string") return "U";
  const op = O.v.trim().toLowerCase();
  if (L.ok && L.v === "active") return "U";
  if (/like$/.test(op) && !op.startsWith("not")) {
    if (!R.ok) return "B";
    return String(R.v ?? "").replace(/[%_]/g, "") ? "B" : "U";
  }
  if (/^(=|==|in|child_of|parent_of|any)$/.test(op)) return "B";
  return "U";
}
function domBound(d, depth = 0) {
  const t = domTruth(d);
  if (t === "T") return "U";
  if (t === "F") return "B";
  if (!d || depth > 8) return "U";
  if (d.type === "AwaitExpression") return domBound(d.argument, depth + 1);
  // a domain held in view/component state (this.domain, this.props.domain) is the user's own
  // visible selection, run with the user's ACL; literal, decoded or parameter domains are not
  const k = mkey(d);
  // CA12 H3: only when nothing in the module assigns it (the framework's search) or every value the module
  // assigns comes from the search/filter UI (or is itself selective); [] / tautology / JSON.parse(..) is not
  if (k && /^this\.(?:props\.)?(?:\w+\.)?domain$/.test(k)) {
    const vs = STATE_DOM.get(k);
    if (!vs) return /^this\.props\./.test(k) && PROPS_BUILT ? "U" : "B";
    // CA13 L2: this.domain = this.props.domain grades exactly like this.props.domain
    const stateRef = (v) => v.type === "MemberExpression" && /^this\.(?:props\.)?(?:\w+\.)?domain$/.test(mkey(v) || "") && mkey(v) !== k;
    return depth < 6 && vs.every(([v, fn]) => userSel(v, fn) || ((v.type !== "MemberExpression" || stateRef(v)) && domBound(v, depth + 1) === "B")) ? "B" : "U";
  }
  if (d.type === "Identifier" && !DOM_VARS.has(d.name) && PUSHED.has(d.name)) {
    // [] + push(leaf...): implicit AND, so one selective leaf bounds it; any operator push is unprovable
    const [init, ...ps] = PUSHED.get(d.name);
    if (!init || ps.some((x) => x.type === "Literal" || x.type === "SpreadElement")) return "U";
    const b0 = init.elements.length ? domBound(init, depth + 1) : "U";
    return b0 === "B" || ps.some((x) => x.type === "ArrayExpression" && x.elements.length === 3 && leafBound(x.elements) === "B") ? "B" : "U";
  }
  if (d.type === "Identifier") {
    const vs = DOM_VARS.get(d.name);
    return vs && vs.length && vs.every((v) => domBound(v, depth + 1) === "B") ? "B" : "U";
  }
  if (d.type !== "ArrayExpression") return "U";
  const terms = [];
  for (const e of d.elements) {
    if (!e) return "U";
    if (e.type === "Literal" && ["&", "|", "!"].includes(e.value)) terms.push(e.value);
    else if (e.type === "ArrayExpression" && e.elements.length === 3) terms.push(leafBound(e.elements));
    else if (e.type === "SpreadElement") terms.push(domBound(e.argument, depth + 1));
    else return "U";
  }
  let pos = 0;
  const take = () => {
    if (pos >= terms.length) throw new Error("dom");
    const x = terms[pos++];
    if (x === "!") { take(); return "U"; }
    if (x === "&" || x === "|") { const a = take(), b = take(); return x === "&" ? (a === "B" || b === "B" ? "B" : "U") : (a === "B" && b === "B" ? "B" : "U"); }
    return x;
  };
  let out = "U";
  try { while (pos < terms.length) { const v = take(); if (v === "B") out = "B"; } } catch { return "U"; }
  return out;
}
// a value that is the user's search/filter selection: read from the search model / a search event, or the
// parameter of a search/filter handler
const SEARCH_SRC = /searchModel|^search(Domain|Params|State)?$|^(facets?|filters?|detail)$/;
function userSel(v, fn) {
  if (!v) return false;
  if (v.type === "Identifier" && fn && fn.params.some((p) => p.type === "Identifier" && p.name === v.name) &&
      /^(on)?_?(search|filter|update(Search|Domain)|domainChange)/i.test(fn.name || "")) return true;
  if (v.type === "MemberExpression" && !v.computed && v.property.name === "domain") {
    let o = v.object;
    while (o && o.type === "MemberExpression") { if (!o.computed && SEARCH_SRC.test(o.property.name)) return true; o = o.object; }
    return !!(o && o.type === "Identifier" && SEARCH_SRC.test(o.name));
  }
  return false;
}
function mkey(n) {
  if (!n) return null;
  if (n.type === "Identifier") return n.name;
  if (n.type === "ThisExpression") return "this";
  if (n.type === "MemberExpression" && !n.computed && n.property.type === "Identifier") { const o = mkey(n.object); return o ? o + "." + n.property.name : null; }
  return null;
}
function decodeEntities(t) {
  // quotes stay encoded: they delimit the attribute values the checks split on
  const named = { amp: "&", lt: "<", gt: ">", colon: ":", tab: "\t", newline: "\n", sol: "/", lpar: "(", rpar: ")", period: ".", nbsp: " " };
  for (let i = 0; i < 3 && /&(#\d+|#x[0-9a-f]+|[a-z]+);?/i.test(t); i++) {  // nested &amp;#115; too
    t = t.replace(/&#(\d+);?/g, (q, d) => { const c = +d; return c > 0 && c < 0x110000 && c !== 34 && c !== 39 ? String.fromCodePoint(c) : q; })
      .replace(/&#x([0-9a-f]+);?/gi, (q, h) => { const c = parseInt(h, 16); return c > 0 && c < 0x110000 && c !== 34 && c !== 39 ? String.fromCodePoint(c) : q; })
      .replace(/&([a-z]+);/gi, (q, nm) => named[nm.toLowerCase()] ?? q);
  }
  return t;
}
let DEPTH = 0;
function litArr(n) {
  if (!n) return null;
  if (n.type === "ArrayExpression") { const xs = n.elements.map((e) => lit(e)); return xs.every((x) => x !== null) ? xs : null; }
  if (n.type === "CallExpression" && n.callee.type === "MemberExpression" && !n.callee.computed) {
    const m = n.callee.property.name;
    if (m === "split") { const s0 = lit(n.callee.object), sep = n.arguments.length ? lit(n.arguments[0]) : null; return s0 !== null && sep !== null ? s0.split(sep) : null; }
    if (m === "reverse" && !n.arguments.length) { const a = litArr(n.callee.object); return a ? [...a].reverse() : null; }
    if (m === "concat") { const a = litArr(n.callee.object), b = n.arguments.map((x) => litArr(x) ?? (lit(x) !== null ? [lit(x)] : null)); return a && b.every(Boolean) ? a.concat(...b) : null; }
  }
  return null;
}
function lit(n) {
  if (!n) return null;
  if (n.type === "MemberExpression" && !n.computed && n.property.name === "href" && n.object.type === "NewExpression") return lit(n.object);
  // CA11 M2: new URL('/x', 'https://e.v') folds to its absolute href
  if (n.type === "NewExpression" && n.callee.type === "Identifier" && n.callee.name === "URL" && n.arguments.length) {
    const a = lit(n.arguments[0]), b = n.arguments.length > 1 ? lit(n.arguments[1]) : null;
    if (a !== null && (n.arguments.length === 1 || b !== null)) {
      try { return n.arguments.length > 1 ? new URL(a, b).href : a; } catch { return a; }
    }
  }
  if (n.type === "Literal" && typeof n.value === "string") return n.value;
  if (n.type === "Identifier" && CONSTS.has(n.name)) return CONSTS.get(n.name);
  if (n.type === "TemplateLiteral") {
    let s = n.quasis[0].value.cooked;
    for (let i = 0; i < n.expressions.length; i++) {
      const e = lit(n.expressions[i]);
      if (e === null) return null;
      s += e + n.quasis[i + 1].value.cooked;
    }
    return s;
  }
  if (n.type === "BinaryExpression" && n.operator === "+") {
    const a = lit(n.left), b = lit(n.right);
    return a !== null && b !== null ? a + b : null;
  }
  // ['ev', 'al'].join('') / 'a'.concat('b') / String.fromCharCode(..literals)
  if (n.type === "CallExpression" && n.callee.type === "MemberExpression" && !n.callee.computed) {
    const m = n.callee.property.name;
    if (m === "join") {
      const parts = litArr(n.callee.object) || [null];
      const sep = n.arguments.length ? lit(n.arguments[0]) : ",";
      if (sep !== null && parts.every((x) => x !== null)) return parts.join(sep);
    }
    // CA13 H2: deterministic string transforms on folded strings
    if (["replace", "replaceAll"].includes(m) && n.arguments.length === 2) {
      const b0 = lit(n.callee.object), a = lit(n.arguments[0]), r = lit(n.arguments[1]);
      if (b0 !== null && a !== null && r !== null) return m === "replace" ? b0.replace(a, () => r) : b0.split(a).join(r);
    }
    if (["slice", "substring", "substr"].includes(m) && n.arguments.every((x) => x.type === "Literal" && typeof x.value === "number" ||
        (x.type === "UnaryExpression" && x.operator === "-" && x.argument.type === "Literal"))) {
      const b0 = lit(n.callee.object);
      const nums = n.arguments.map((x) => x.type === "Literal" ? x.value : -x.argument.value);
      if (b0 !== null) return b0[m](...nums);
    }
    if (["toLowerCase", "toUpperCase", "trim", "trimStart", "trimEnd", "normalize"].includes(m) && !n.arguments.length) {
      const b0 = lit(n.callee.object);
      if (b0 !== null) return b0[m]();
    }
    if (m === "concat") {
      const parts = [n.callee.object, ...n.arguments].map((e) => lit(e));
      if (parts.every((x) => x !== null)) return parts.join("");
    }
    if (m === "atob" && GLOBALS.has(n.callee.object.name || "") && n.arguments.length === 1) {
      const a = lit(n.arguments[0]);
      if (a !== null && /^[A-Za-z0-9+/=\s]*$/.test(a)) return Buffer.from(a, "base64").toString("latin1");
    }
    if (m === "fromCharCode" && n.callee.object.type === "Identifier" && n.callee.object.name === "String" &&
        n.arguments.every((a) => a.type === "Literal" && typeof a.value === "number")) {
      return String.fromCharCode(...n.arguments.map((a) => a.value));
    }
  }
  // atob('aHR0cHM6Ly9lLnYv') / decodeURIComponent('%68ttps...') / unescape(...): deterministic decoders (M3)
  if (n.type === "CallExpression" && n.callee.type === "Identifier" && n.arguments.length === 1 &&
      ["atob", "decodeURIComponent", "decodeURI", "unescape"].includes(n.callee.name)) {
    const a = lit(n.arguments[0]);
    if (a === null) return null;
    try {
      if (n.callee.name === "atob") return /^[A-Za-z0-9+/=\s]*$/.test(a) ? Buffer.from(a, "base64").toString("latin1") : null;
      return n.callee.name === "unescape" ? unescape(a) : decodeURIComponent(a);
    } catch { return null; }
  }
  return null;
}
// CA12 H2: fold a URL expression to a pattern; \u0001 marks a runtime part. Follows once-bound
// variables, new URL(path, base), Request(url), .href/.toString()/String(), + chains and templates.
const RT = "\u0001";
// CA14 H4: WHATWG-style path normalisation before any route match: percent-decoding, \ -> /,
// collapsed //, resolved . and .. segments
function normUrl(u) {
  if (u === null || u === undefined) return u;
  let s = u.replace(/\\/g, "/");
  for (let i = 0; i < 3; i++) {
    const t = s.replace(/%([0-9a-f]{2})/gi, (_m, h) => String.fromCharCode(parseInt(h, 16)));
    if (t === s) break;
    s = t.replace(/\\/g, "/");
  }
  const m = s.match(/^([a-z][a-z0-9+.-]*:\/\/[^/?#]*)?([\s\S]*)$/i);
  const pre = m[1] || "", rest = m[2];
  const qi = rest.search(/[?#]/);
  const q = qi >= 0 ? rest.slice(qi) : "";
  const segs = (qi >= 0 ? rest.slice(0, qi) : rest).replace(/\/{2,}/g, "/").split("/");
  const out = [];
  segs.forEach((sg, i) => {
    const end = i === segs.length - 1;
    if (sg === "." || sg === "..") {
      const rel = !pre && segs[0] !== "" && !segs[0].includes(RT);  // relative ref: keep leading ..
      if (sg === ".." && out.length > (rel ? 0 : 1) && out[out.length - 1] !== "..") out.pop();
      else if (sg === ".." && rel) out.push("..");
      if (end) out.push("");
      return;
    }
    out.push(sg);
  });
  return pre + out.join("/") + q;
}
function urlPat(n, d = 0) { return normUrl(urlPat0(n, d)); }
function urlPat0(n, d = 0) {
  if (!n || d > 8) return null;
  const s = lit(n);
  if (s !== null) return s;
  if (n.type === "Identifier" && DOM_VARS.has(n.name)) return urlPat(DOM_VARS.get(n.name)[0], d + 1);
  if (n.type === "Identifier" && URL_OBJS.has(n.name)) { const c = urlCands(n, d); return c[c.length - 1]; }
  if (n.type === "MemberExpression" && !n.computed && ["href", "pathname"].includes(n.property.name)) return urlPat(n.object, d + 1);
  if (n.type === "CallExpression" && n.callee.type === "MemberExpression" && !n.callee.computed && n.callee.property.name === "toString") return urlPat(n.callee.object, d + 1);
  if (n.type === "CallExpression" && n.callee.type === "Identifier" && n.callee.name === "String" && n.arguments.length === 1) return urlPat(n.arguments[0], d + 1);
  if (n.type === "NewExpression" && n.callee.type === "Identifier" && ["URL", "Request"].includes(n.callee.name) && n.arguments.length) {
    const a = urlPat(n.arguments[0], d + 1) ?? RT;
    if (n.callee.name === "Request" || n.arguments.length === 1 || /^(\/|[a-z][a-z0-9+.-]*:)/i.test(a)) return a;
    const base = urlPat(n.arguments[1], d + 1) ?? RT;  // CA14 H4: resolve against the base directory
    if (a.startsWith("/")) { const o = base.match(/^([a-z][a-z0-9+.-]*:\/\/[^/]*)/i); return (o ? o[1] : base.startsWith("/") ? "" : RT) + a; }
    return (base.includes("/") ? base.replace(/[^/]*$/, "") : base + "/") + a;
  }
  if (n.type === "TemplateLiteral") {
    let o = n.quasis[0].value.cooked;
    n.expressions.forEach((e, i) => { o += (urlPat(e, d + 1) ?? RT) + n.quasis[i + 1].value.cooked; });
    return o;
  }
  if (n.type === "BinaryExpression" && n.operator === "+") {
    const a = urlPat(n.left, d + 1), b = urlPat(n.right, d + 1);
    return a === null && b === null ? null : (a ?? RT) + (b ?? RT);
  }
  return null;
}
// CA13 H2: every state a URL object passes through (initial, then after each pathname/href/.. write)
function urlCands(n, d = 0) {
  if (!n || n.type !== "Identifier" || !URL_OBJS.has(n.name)) return [urlPat(n, d)];
  let cur = urlPat(URL_OBJS.get(n.name), d + 1) ?? RT;
  const out = [cur];
  const origin = (u) => { const m = u.match(/^([a-z][a-z0-9+.-]*:\/\/[^/]*)/i); return m ? m[1] : u.startsWith("/") ? "" : RT; };
  for (const [prop, v] of URL_MUTS.get(n.name) || []) {
    if (["search", "hash"].includes(prop)) continue;
    const val = v ? urlPat(v, d + 1) : null;
    if (prop === "pathname") cur = origin(cur) + (val === null ? RT : (val.startsWith("/") ? "" : "/") + val);
    else if (prop === "href") cur = val === null ? RT : /^[a-z][a-z0-9+.-]*:/i.test(val) ? val : origin(cur) + val;
    else cur = RT + "/" + RT;  // host/origin/protocol/unknown property: anything
    out.push(cur);
  }
  return out.map(normUrl);
}
// could a URL pattern reach an ORM endpoint (runtime parts may be anything)
const ORM_PATHS = ["/web/dataset/call_kw/a.a/write", "/web/dataset/call_kw", "/web/dataset/call_button", "/web/dataset/call_button/a.a/write", "/web/dataset/call", "/web/dataset/search_read", "/web/action/run", "/json/2/a.a/write", "/json/1/a.a/write", "/jsonrpc", "/xmlrpc/2/object"];
function mayReachOrm(pat) {
  if (pat === null) return true;
  const path = pat.split(/[?#]/)[0];
  const rx = new RegExp("^" + path.split(RT).map((x) => x.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join(".*") + "$");
  return ORM_PATHS.some((c) => rx.test(c) || rx.test("https://h.h" + c));
}
// a URL-controlled source (DOM XSS): location.hash/search/href, document.URL/referrer, window.name
function readsUrl(n) {
  let hit = false;
  if (!n) return false;
  walk.full(n, (x) => {
    if (x.type === "Identifier" && URL_VARS.has(x.name)) hit = true;
    if (x.type !== "MemberExpression") return;
    const p = x.computed ? lit(x.property) : x.property.name;
    const o = x.object.type === "Identifier" ? x.object.name : x.object.type === "MemberExpression" && !x.object.computed ? x.object.property.name : "";
    if (o === "location" && ["hash", "search", "href"].includes(p)) hit = true;
    if (o === "document" && ["URL", "documentURI", "referrer", "baseURI"].includes(p)) hit = true;
    if (["window", "self", "top"].includes(o) && p === "name") hit = true;
  });
  return hit;
}

// does this expression read document.cookie anywhere (exfiltration through a URL or body)
function readsCookie(n) {
  let hit = false;
  if (!n) return false;
  walk.full(n, (x) => {
    if (x.type === "MemberExpression" && ((!x.computed && x.property.name === "cookie") ||
        lit(x.property) === "cookie")) hit = true;
    if (x.type === "Identifier" && COOKIE_VARS.has(x.name)) hit = true;
    if (x.type === "CallExpression" && x.callee.type === "MemberExpression" &&
        /^(Reflect\.get|Object\.getOwnPropertyDescriptor|Reflect\.getOwnPropertyDescriptor)$/.test(
          `${x.callee.object.name || ""}.${x.callee.property.name || ""}`) &&
        lit(x.arguments[1]) === "cookie") hit = true;
  });
  return hit;
}
const HTTP_VERB = /^(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)$/i;
const LOADERS = new Set(["loadJS", "loadCSS", "loadBundle", "loadAssets", "loadLibs", "getScript", "$.getScript", "jQuery.getScript"]);
const JQ_HTML = new Set(["html", "append", "prepend", "after", "before", "replaceWith", "wrap", "wrapAll", "wrapInner"]);

// "external" | "dynamic" | "local" for a URL argument
function urlKind(n) {
  const p0 = urlPat(n), s = p0 !== null && !p0.includes(RT) ? p0 : lit(n);  // CA12 H2: URL objects fold
  const ext = (t) => /^\s*(https?:|wss?:|ftp:|\/\/|data:|blob:|javascript:)/i.test(t);
  if (s !== null) return ext(s) ? "external" : "local";
  let head = null;
  if (n && n.type === "TemplateLiteral") head = n.quasis[0].value.cooked;
  if (n && n.type === "BinaryExpression" && n.operator === "+") {
    let l = n;
    while (l.type === "BinaryExpression" && l.operator === "+") l = l.left;
    head = lit(l);
  }
  if (head !== null && head !== "") {
    if (ext(head)) return "external";
    if (/^\/[^/]/.test(head)) return "local"; // same-origin path prefix
  }
  return "dynamic";
}

// constant head of a URL expression: a literal, a template's first quasi, or the left end of a + chain
function urlHead(n) {
  if (!n) return null;
  const s = lit(n);
  if (s !== null) return s;
  if (n.type === "TemplateLiteral") return n.quasis[0].value.cooked;
  if (n.type === "BinaryExpression" && n.operator === "+") {
    let l = n;
    while (l.type === "BinaryExpression" && l.operator === "+") l = l.left;
    return lit(l);
  }
  return null;
}
// a URL scheme that executes code when navigated / loaded
function scriptScheme(s) {
  if (typeof s === "string") s = s.replace(/\\[tnr]/g, "").replace(/[\t\n\r]/g, "");
  return typeof s === "string" && /^[\s\x00-\x20]*(javascript|vbscript|livescript)\s*:|^\s*data:\s*(text\/html|image\/svg|application\/(x-)?javascript|text\/javascript)/i.test(s);
}

// Generated data files (CLDR emoji tables) concatenate thousands of string pieces in one
// left-deep `a + b + c ...` chain; every recursive pass over that tree overflows the stack.
// When the chain starts with a string, `+` is plain string concatenation and therefore
// associative, so the chain is rebuilt balanced (depth log2 n) without changing its value.
// Iterative: the rebuild itself must not recurse on the deep chain.
const DEEP_CHAIN = 256;
function isStr(n) {
  return n && ((n.type === "Literal" && typeof n.value === "string") || n.type === "TemplateLiteral");
}
function balance(leaves) {
  let level = leaves;
  while (level.length > 1) {
    const next = [];
    for (let i = 0; i < level.length; i += 2) {
      if (i + 1 === level.length) { next.push(level[i]); continue; }
      const l = level[i], r = level[i + 1];
      next.push({ type: "BinaryExpression", operator: "+", left: l, right: r, start: l.start, end: r.end,
        loc: { start: l.loc.start, end: r.loc.end } });
    }
    level = next;
  }
  return level[0];
}
function rebalanceChains(root) {
  const stack = [root];
  let seen = 0;
  while (stack.length) {
    const n = stack.pop();
    if (++seen > 50_000_000) throw new Error("AST too large");
    for (const k of Object.keys(n)) {
      if (k === "loc") continue;
      let v = n[k];
      const kids = Array.isArray(v) ? v : [v];
      for (let i = 0; i < kids.length; i++) {
        let c = kids[i];
        if (!c || typeof c.type !== "string") continue;
        if (c.type === "BinaryExpression" && c.operator === "+") {
          const leaves = [];
          let x = c;
          while (x.type === "BinaryExpression" && x.operator === "+") { leaves.push(x.right); x = x.left; }
          leaves.push(x);
          if (leaves.length > DEEP_CHAIN && isStr(x)) {
            leaves.reverse();
            const b = balance(leaves);
            if (Array.isArray(v)) v[i] = b; else n[k] = b;
            c = b;
            for (const l of leaves) stack.push(l);
            continue;
          }
        }
        stack.push(c);
      }
    }
  }
  return root;
}

function auditJs(text) {
  let ast;
  const opts = { ecmaVersion: "latest", locations: true, allowHashBang: true,
    allowAwaitOutsideFunction: true, allowReturnOutsideFunction: true,
    allowImportExportEverywhere: true };
  try {
    ast = acorn.parse(text, { ...opts, sourceType: "module" });
  } catch (e1) {
    try {
      ast = acorn.parse(text, { ...opts, sourceType: "script" });
    } catch (e2) {
      return { ok: false, error: String(e1.message).slice(0, 200), line: e1.loc ? e1.loc.line : 0 };
    }
  }
  rebalanceChains(ast);
  const out = [];
  const add = (sev, code, node, msg) => out.push({ sev, code, line: node.loc.start.line, msg });
  for (const m of text.matchAll(/[#@]\s*source(?:Mapping)?URL\s*=\s*(\S+)/g)) {
    if (/^(https?:|\/\/|data:)/i.test(m[1]) && !/^data:application\/json/i.test(m[1])) {
      out.push({ sev: "medium", code: "js-external-request", line: text.slice(0, m.index).split("\n").length,
        msg: "sourceMappingURL points at an external host (devtools fetch it; it can also mask the real source)." });
    }
  }
  // H10: fold identifiers bound to constant strings (once, never reassigned) and track
  // variables that hold document.cookie, to a fixpoint
  CONSTS = new Map();
  COOKIE_VARS = new Set();
  URL_VARS = new Set();
  EMPTY_VARS = new Set();
  JSURL_PROPS = new Set();
  PUSHED = new Map();
  walk.full(ast, (n) => {
    if (n.type === "VariableDeclarator" && n.id.type === "Identifier" && n.init && n.init.type === "ArrayExpression") {
      if (!PUSHED.has(n.id.name)) PUSHED.set(n.id.name, [n.init]); else PUSHED.set(n.id.name, [null]);
    }
  });
  walk.full(ast, (n) => {
    if (n.type === "CallExpression" && n.callee.type === "MemberExpression" && n.callee.object.type === "Identifier" &&
        (n.callee.property.name === "push") && PUSHED.has(n.callee.object.name)) PUSHED.get(n.callee.object.name).push(...n.arguments);
    if (n.type === "AssignmentExpression" && n.left.type === "Identifier" && PUSHED.has(n.left.name)) PUSHED.set(n.left.name, [null]);
  });
  walk.full(ast, (n) => {
    if (n.type === "Property" && n.key && scriptScheme(lit(n.value))) JSURL_PROPS.add(n.key.name || n.key.value);
    if (n.type === "AssignmentExpression" && n.left.type === "MemberExpression" && !n.left.computed && scriptScheme(lit(n.right))) JSURL_PROPS.add(n.left.property.name);
  });
  DOM_VARS = new Map();
  const assigned = new Map();
  const patIds = (pt, out = []) => {
    if (!pt) return out;
    if (pt.type === "Identifier") out.push(pt.name);
    else if (pt.type === "ArrayPattern") pt.elements.forEach((e) => patIds(e, out));
    else if (pt.type === "ObjectPattern") pt.properties.forEach((q) => patIds(q.type === "RestElement" ? q.argument : q.value, out));
    else if (pt.type === "RestElement") patIds(pt.argument, out);
    else if (pt.type === "AssignmentPattern") patIds(pt.left, out);
    return out;
  };
  walk.full(ast, (n) => {
    if (n.type === "VariableDeclarator" && n.id.type === "Identifier") {
      assigned.set(n.id.name, (assigned.get(n.id.name) || 0) + 1);
    }
    if (n.type === "AssignmentExpression" && n.left.type === "Identifier") {
      assigned.set(n.left.name, (assigned.get(n.left.name) || 0) + 2);
    }
  });
  const mutated = new Set(), pathMut = new Set();
  walk.full(ast, (n) => {
    if (n.type === "CallExpression" && n.callee.type === "MemberExpression" && n.callee.object.type === "Identifier" &&
        /^(push|unshift|splice)$/.test(n.callee.property.name || "")) mutated.add(n.callee.object.name);
    if (n.type === "AssignmentExpression" && n.left.type === "MemberExpression" && n.left.object.type === "Identifier") {
      mutated.add(n.left.object.name);
      if (n.left.computed || !["search", "hash"].includes(n.left.property.name)) pathMut.add(n.left.object.name);
    }
  });
  STATE_DOM = new Map();
  {
    const put = (k, v, fn) => { if (!STATE_DOM.has(k)) STATE_DOM.set(k, []); STATE_DOM.get(k).push([v, fn]); };
    const objDom = (base, o, fn) => {
      if (o && o.type === "CallExpression" && o.arguments.length && /(^|\.)(useState|reactive)$/.test(mkey(o.callee) || "")) o = o.arguments[0];
      if (o && o.type === "ObjectExpression") for (const q of o.properties) if (q.key && (q.key.name || q.key.value) === "domain") put(base + ".domain", q.value, fn);
    };
    const fnName = (anc) => {
      for (let i = anc.length - 1; i >= 0; i--) {
        const a = anc[i];
        if (/Function/.test(a.type)) {
          const par = anc[i - 1];
          const name = a.id ? a.id.name : par && par.type === "MethodDefinition" ? par.key.name : par && par.type === "Property" ? (par.key.name || par.key.value) : par && par.type === "VariableDeclarator" ? par.id.name : "";
          return { params: a.params, name, kind: par && par.type === "MethodDefinition" ? par.kind : "" };
        }
      }
      return null;
    };
    // CA13 H3: aliases of this / this.<x> (const s = this.state; s.domain = ..) write the same state
    const ALIAS = new Map();
    walk.full(ast, (n) => {
      if (n.type === "VariableDeclarator" && n.id.type === "Identifier" && n.init) {
        const b = n.init.type === "ThisExpression" ? "this" : mkey(n.init);
        if (b && /^this(\.props)?(\.\w+)?$/.test(b)) ALIAS.set(n.id.name, b);
      }
    });
    const nk = (x) => {
      const k = mkey(x);
      if (!k) return k;
      const [h, ...r] = k.split(".");
      return ALIAS.has(h) ? [ALIAS.get(h), ...r].join(".") : k;
    };
    const UNK = { type: "Identifier", name: "\u0000" };  // in-place / opaque write: unprovable
    const DOMK = /^this\.(?:props\.)?(?:\w+\.)?domain$/;
    walk.ancestor(ast, {
      CallExpression(n, _s, anc) {
        const c = n.callee, fn = fnName(anc);
        if (c.type === "MemberExpression" && !c.computed && /^(push|unshift|splice|pop|shift|fill|sort|reverse|copyWithin)$/.test(c.property.name) &&
            DOMK.test(nk(c.object) || "")) put(nk(c.object), UNK, fn);
        if (/(^|\.)Object\.(assign|defineProperty|defineProperties)$/.test(mkey(c) || "") && n.arguments[0]) {
          const t = nk(n.arguments[0]);
          if (t && DOMK.test(t)) put(t, UNK, fn);  // Object.assign(this.state.domain, [...])
          else if (t && /^this(\.props)?(\.\w+)?$/.test(t)) {
            for (const o of n.arguments.slice(1)) {
              if (o && o.type === "ObjectExpression" && o.properties.every((q) => q.type === "Property")) {
                for (const q of o.properties) if ((q.key.name || q.key.value) === "domain") put(t + ".domain", q.value, fn);
              } else put(t + ".domain", UNK, fn);  // spread / runtime object: may carry a domain
            }
          }
        }
      },
      AssignmentExpression(n, _s, anc) {
        const k = nk(n.left), fn = fnName(anc);
        if (n.left.type === "MemberExpression") {  // this.state.domain.length = 0 / this.state.domain[0] = ..
          const ok = nk(n.left.object);
          if (ok && DOMK.test(ok)) { put(ok, UNK, fn); return; }
        }
        if (k && /^this\.(?:props\.)?(?:\w+\.)?domain$/.test(k)) put(k, n.right, fn);
        else if (k && /^this\.(?:\w+)$/.test(k)) {
          const r0 = n.right.type === "CallExpression" && n.right.arguments.length && /(^|\.)(useState|reactive)$/.test(mkey(n.right.callee) || "") ? n.right.arguments[0] : n.right;
          if (r0.type === "ObjectExpression" && r0.properties.some((q) => q.type !== "Property")) put(k + ".domain", UNK, fn);  // {...x}: may carry a domain
          else if (r0.type === "Identifier") put(k + ".domain", UNK, fn);  // this.state = obj: whatever obj holds
          objDom(k, n.right, fn);
        }
      },
      PropertyDefinition(n) {
        const nm = n.key && (n.key.name || n.key.value);
        if (!n.value) return;
        if (nm === "domain" && !n.static) put("this.domain", n.value, null);
        else if (nm === "defaultProps" && n.static) objDom("this.props", n.value, null);
        else if (!n.static) objDom("this." + nm, n.value, null);
      },
      MethodDefinition(n) {  // set domain(d) {..}: whatever callers pass, unprovable
        if (n.kind === "set" && n.key && n.key.name === "domain") put("this.domain", { type: "Identifier", name: n.value.params[0] ? "\u0000" : "\u0000" }, null);
      },
    });
  }
  URL_OBJS = new Map(); URL_MUTS = new Map();
  const putMut = (nm, prop, v) => { if (!URL_MUTS.has(nm)) URL_MUTS.set(nm, []); URL_MUTS.get(nm).push([prop, v]); };
  walk.full(ast, (n) => {
    if (n.type === "AssignmentExpression" && n.left.type === "MemberExpression" && n.left.object.type === "Identifier")
      putMut(n.left.object.name, n.left.computed ? lit(n.left.property) ?? "?" : n.left.property.name, n.operator === "=" ? n.right : null);
    if (n.type === "CallExpression" && /(^|\.)Object\.(assign|defineProperty|defineProperties)$/.test(mkey(n.callee) || "") &&
        n.arguments[0] && n.arguments[0].type === "Identifier") {
      const o = n.arguments[1];
      if (o && o.type === "ObjectExpression") for (const q of o.properties) putMut(n.arguments[0].name, q.key ? (q.key.name || q.key.value) : "?", q.type === "Property" ? q.value : null);
      else putMut(n.arguments[0].name, "?", null);
    }
  });
  walk.full(ast, (n) => {
    if (n.type === "VariableDeclarator" && n.id.type === "Identifier" && n.init && n.init.type === "NewExpression" &&
        n.init.callee.type === "Identifier" && n.init.callee.name === "URL" && assigned.get(n.id.name) === 1) URL_OBJS.set(n.id.name, n.init);
  });
  walk.full(ast, (n) => {
    if (n.type === "VariableDeclarator" && n.id.type === "Identifier" && n.init && assigned.get(n.id.name) === 1 && !mutated.has(n.id.name)) DOM_VARS.set(n.id.name, [n.init]);
    const fn = n.type === "FunctionDeclaration" && n.id ? n.id.name : null;
    if (fn) {
      const rets = [];
      walk.simple(n.body, { ReturnStatement(r) { if (r.argument) rets.push(r.argument); } });
      if (n.body.type !== "BlockStatement") rets.push(n.body);
      if (rets.length) DOM_VARS.set("()" + fn, rets);
    }
    if (n.type === "VariableDeclarator" && n.id.type === "Identifier" && n.init && /ArrowFunctionExpression|FunctionExpression/.test(n.init.type)) {
      const b = n.init.body, rets = [];
      if (b.type !== "BlockStatement") rets.push(b); else walk.simple(b, { ReturnStatement(r) { if (r.argument) rets.push(r.argument); } });
      if (rets.length) DOM_VARS.set("()" + n.id.name, rets);
    }
  });
  for (let round = 0, changed = true; changed && round < 64; round++) {
    changed = false;
    walk.full(ast, (n) => {
      // CA9 H7: const [ids] = [await orm.search(..)] / const {ids} = {ids: ...} / [a, b] = ...
      const pat = n.type === "VariableDeclarator" && n.id.type !== "Identifier" ? [n.id, n.init]
        : n.type === "AssignmentExpression" && n.left.type !== "Identifier" && n.left.type !== "MemberExpression" ? [n.left, n.right] : null;
      if (pat && pat[1] && emptySearch(pat[1])) {
        for (const i of patIds(pat[0])) if (!EMPTY_VARS.has(i)) { EMPTY_VARS.add(i); changed = true; }
      }
      let id = null, v = null;
      if (n.type === "VariableDeclarator" && n.id.type === "Identifier" && n.init) [id, v] = [n.id.name, n.init];
      if (n.type === "AssignmentExpression" && n.left.type === "Identifier") [id, v] = [n.left.name, n.right];
      if (!id) return;
      if (assigned.get(id) === 1 && !CONSTS.has(id)) {
        const s = lit(v);
        if (s !== null) { CONSTS.set(id, s); changed = true; }
      }
      if (!COOKIE_VARS.has(id) && readsCookie(v)) { COOKIE_VARS.add(id); changed = true; }
      if (!URL_VARS.has(id) && readsUrl(v)) { URL_VARS.add(id); changed = true; }
      if (!EMPTY_VARS.has(id) && emptySearch(v)) { EMPTY_VARS.add(id); changed = true; }
    });
    // CA11 H7: unbounded ids flow through .then params, object properties, push/unshift and for-of
    walk.full(ast, (n) => {
      const mark = (k) => { if (k && !EMPTY_VARS.has(k)) { EMPTY_VARS.add(k); changed = true; } };
      if (n.type === "CallExpression" && n.callee.type === "MemberExpression" && /^(then|finally)$/.test(n.callee.property.name || "") && emptySearch(n.callee.object)) {
        const f = n.arguments[0];
        if (f && /Function/.test(f.type)) for (const p of f.params) patIds(p).forEach(mark);
      }
      if (n.type === "AssignmentExpression" && n.left.type === "MemberExpression" && emptySearch(n.right)) mark(mkey(n.left));
      if (n.type === "CallExpression" && n.callee.type === "MemberExpression" && /^(push|unshift|splice|concat)$/.test(n.callee.property.name || "") &&
          n.arguments.some((a) => emptySearch(a))) mark(mkey(n.callee.object));
      if ((n.type === "ForOfStatement" || n.type === "ForInStatement") && emptySearch(n.right)) {
        patIds(n.left.type === "VariableDeclaration" ? n.left.declarations[0].id : n.left).forEach(mark);
      }
    });
  }
  // aliases: const e = eval; const { write } = document; const w = window; let f = fetch
  const alias = new Map();
  const markupNames = new Set(["markup", "Markup"]);
  const elems = new Map(); // variable -> created element tag (script, iframe, img, ...)
  const elemOf = (init) => {
    if (!init) return null;
    if (init.type === "NewExpression" && init.callee.type === "Identifier" && init.callee.name === "Image") return "img";
    if (init.type === "CallExpression" && /(^|\.)createElement$/.test(resolve(init.callee) || "")) {
      const t = lit(init.arguments[0]);
      return t === null ? "?" : t.toLowerCase();
    }
    if (init.type === "Identifier" && elems.has(init.name)) return elems.get(init.name);
    return null;
  };
  walk.full(ast, (n) => {
    if (n.type === "VariableDeclarator" && n.id.type === "Identifier" && n.init) {
      const r = resolve(n.init);
      if (r) alias.set(n.id.name, r);
      const t = elemOf(n.init);
      if (t) elems.set(n.id.name, t);
    }
    if (n.type === "AssignmentExpression" && n.operator === "=" && n.left.type === "Identifier") {
      const r = resolve(n.right);
      if (r && !alias.has(n.left.name)) alias.set(n.left.name, r);
      const t = elemOf(n.right);
      if (t) elems.set(n.left.name, t);
    }
    if (n.type === "VariableDeclarator" && n.id.type === "ObjectPattern" && n.init) {
      const base = resolve(n.init);
      for (const p of n.id.properties) {
        if (p.type === "Property" && p.value.type === "Identifier") {
          const key = p.computed ? null : (p.key.name || p.key.value);
          if (key === null) alias.set(p.value.name, "?dynamic");
          else alias.set(p.value.name, base ? `${base}.${key}` : key);
          if (key === "cookie" && /(^|\.)document$/.test(base || "")) COOKIE_VARS.add(p.value.name);
        }
      }
    }
    if (n.type === "ImportDeclaration" && n.source.value === "@odoo/owl") {
      for (const s of n.specifiers) {
        if (s.imported && s.imported.name === "markup") markupNames.add(s.local.name);
      }
    }
  });
  let XHR_ORM = null;
  function xhrOrm() {  // XMLHttpRequest variables opened on an ORM endpoint
    if (XHR_ORM) return XHR_ORM;
    XHR_ORM = new Map();
    walk.full(ast, (m) => {
      if (m.type === "CallExpression" && m.callee.type === "MemberExpression" && m.callee.object.type === "Identifier" &&
          (m.callee.property.name || "") === "open" && m.arguments.length >= 2) {
        const u = urlPat(m.arguments[1]);
        if (u !== null ? ORM_ROUTE.test(u) || mayReachOrm(u) : true) XHR_ORM.set(m.callee.object.name, u ?? RT);
      }
    });
    return XHR_ORM;
  }
  function bodyObj(b, d = 0) {
    if (!b || d > 6) return null;
    if (b.type === "ObjectExpression") return b;
    if (b.type === "CallExpression" && /(^|\.)JSON\.stringify$/.test(resolve(b.callee) || "")) return bodyObj(b.arguments[0], d + 1);
    if (b.type === "NewExpression" && b.callee.name === "Blob" && b.arguments[0] && b.arguments[0].type === "ArrayExpression") return bodyObj(b.arguments[0].elements[0], d + 1);
    if (b.type === "Identifier" && DOM_VARS.has(b.name)) return bodyObj(DOM_VARS.get(b.name)[0], d + 1);
    return null;
  }
  // FormData / URLSearchParams / File bodies cannot be a JSON-RPC call (Odoo's ORM routes are type=jsonrpc)
  function nonJsonBody(b, d = 0) {
    if (!b || d > 6) return false;
    if (b.type === "NewExpression" && b.callee.type === "Identifier" && ["FormData", "URLSearchParams", "File"].includes(b.callee.name)) return true;
    if (b.type === "Identifier" && DOM_VARS.has(b.name)) return nonJsonBody(DOM_VARS.get(b.name)[0], d + 1);
    if (b.type === "Literal" && typeof b.value === "string") { try { JSON.parse(b.value); return false; } catch { return true; } }
    return false;
  }
  function gradeOrmBody(n, what, route0, body, dyn = false) {
    const o = bodyObj(body);
    const route = route0.split(RT).join("${...}");
    const sev = dyn ? "high" : "medium";  // CA12 H2: runtime URL that may be the ORM: unprovable is HIGH
    const get = (x, k) => x && x.type === "ObjectExpression" ? (x.properties.find((q) => q.key && (q.key.name || q.key.value) === k) || {}).value || null : null;
    const seg = normUrl(route0).match(/\/(?:web\/dataset\/call_kw|web\/dataset\/call_button|json\/[12])\/([^/?#]+)(?:\/([^/?#]+))?/i);
    let model = seg ? seg[1] : null, method = seg ? (seg[2] || null) : null, args = null;
    if (model && model.includes(RT)) model = null;
    if (method && method.includes(RT)) method = null;
    const prm = get(o, "params") || o;
    if (prm) {
      model = lit(get(prm, "model")) ?? model;
      method = lit(get(prm, "method")) ?? method;
      args = get(prm, "args");
      // /jsonrpc {service: 'object', method: 'execute(_kw)', args: [db, uid, pwd, model, method, args]}
      if (/^execute(_kw)?$/.test(method || "") && args && args.type === "ArrayExpression" && args.elements.length >= 5) {
        model = lit(args.elements[3]); method = lit(args.elements[4]); args = args.elements[5] || null;
      }
    }
    if (!body) {  // no payload: only a route that itself names model/method is a call (CA12 H2)
      if (!seg || !method) return;
    } else if (!o && !(seg && model && method)) {  // CA13 L1: a route naming model+method is graded by route
      add(sev, "js-raw-orm-request", n, `${what}() to ${dyn ? "a runtime URL that may be" : ""} the ORM endpoint ${route} with a body built at runtime: model/method undecidable, flagged.`);
      if (dyn) add("high", "js-sensitive-model", n, `${what}() may reach the ORM (${route}) with an unprovable model/method: treated as a privileged write.`);
      return;
    }
    let first = args && args.type === "ArrayExpression" ? args.elements[0] : null;
    if (!first && o && /\/json\/[12]\//i.test(normUrl(route0))) first = get(o, "ids");  // CA14 H4: JSON-2 ids
    if (MASS_JS.test(method || "") && first && emptySearch(first)) {
      add("high", "js-mass-change", n, `${what}() ${method} over every record (ids from an unbounded search) through ${route}.`);
    }
    const button = /\/web\/dataset\/call_button/i.test(normUrl(route0));  // CA14 H4: any button method runs model code
    if (model && SENSITIVE.has(model) && (method === null || WRITE_METHODS.has(method) || (button && method))) {
      add(method === null ? "medium" : "high", "js-sensitive-model", n, `${what}() ${method || "<runtime method>"} on ${model} through ${route} from the browser.`);
    } else if (model && SECRET_MODELS.has(model)) {
      add("medium", "js-sensitive-model", n, `${what}() reads ${model} through ${route} from the browser.`);
    } else if (model === null || method === null) {
      add(sev, "js-raw-orm-request", n, `${what}() to ${route} with a runtime model/method: undecidable, flagged.`);
      if (dyn || route0.includes(RT)) add("high", "js-sensitive-model", n, `${what}() to ${route}: model/method not provable, treated as a privileged write (CA13 H2).`);
    }
  }
  function resolve(n) {
    if (!n) return null;
    if (n.type === "Identifier") {
      const a = alias.get(n.name);
      return a && a !== n.name ? a : n.name;
    }
    if (n.type === "ThisExpression") return "this";
    if (n.type === "MemberExpression") {
      const obj = resolve(n.object);
      let prop = null;
      if (!n.computed) prop = n.property.name;
      else prop = lit(n.property);
      if (prop === null) return obj && GLOBALS.has(obj) ? "?dynamic" : `${obj || "?"}.?`;
      if (obj && GLOBALS.has(obj)) return prop; // window.eval -> eval
      return obj ? `${obj}.${prop}` : `?.${prop}`;
    }
    if (n.type === "ChainExpression") return resolve(n.expression);
    if (n.type === "SequenceExpression") return resolve(n.expressions[n.expressions.length - 1]); // (0, eval)
    if (n.type === "ParenthesizedExpression") return resolve(n.expression);
    if (n.type === "CallExpression" && n.callee.type === "MemberExpression" && !n.callee.computed
        && n.callee.property.name === "bind") return resolve(n.callee.object);
    return null;
  }
  const last = (r) => (r || "").split(".").pop();
  // something loaded from a URL: script/iframe code, or an image/link beacon
  function loadSink(n, tag, val, prop) {
    if (!val) return;
    if (readsCookie(val)) { add("high", "js-cookie-leak", n, `${tag || "element"}.${prop} URL carries document.cookie.`); return; }
    if (prop === "srcdoc" && readsUrl(val)) { add("high", "js-dom-xss", n, "srcdoc from a URL-controlled value: DOM XSS."); return; }
    if (prop === "srcdoc") { if (lit(val) === null) add("medium", "js-html-sink", n, "srcdoc set from non-constant HTML."); return; }
    if (scriptScheme(urlHead(val))) { add("high", "js-eval", n, `${tag || "element"}.${prop} set to a javascript:/vbscript:/data:text/html URL runs code.`); return; }
    if (!tag) return;
    const k = urlKind(val);
    const code = ["script", "iframe", "frame", "object", "embed", "?"].includes(tag);
    if (k === "external") add(code ? "high" : "medium", code ? "js-script-load" : "js-external-request", n,
      `<${tag}> ${prop} points at an external host.`);
    else if (k === "dynamic" && code) add("medium", "js-script-load", n, `<${tag}> ${prop} built at runtime: undecidable, flagged.`);
    else if (k === "dynamic") add("low", "js-dynamic-request", n, `<${tag}> ${prop} built at runtime: destination undecidable, flagged.`);
  }
  walk.full(ast, (n) => {
    if (n.type === "CallExpression" || n.type === "NewExpression") {
      const r = resolve(n.callee) || "";
      const a0 = n.arguments[0];
      if (r === "?dynamic") {
        add("medium", "js-dynamic-call", n, "Call through a computed global name (could be eval): target undecidable, flagged.");
      }
      // Function reached through constructor chains: [].constructor.constructor(code)
      if (last(r) === "constructor" && n.arguments.length) {
        const deep = /constructor\.constructor$|getPrototypeOf|\?\.constructor$/.test(r) ||
          (n.callee.type === "MemberExpression" && n.callee.object.type === "MemberExpression" &&
           (n.callee.object.computed ? lit(n.callee.object.property) : n.callee.object.property.name) === "constructor");
        add(deep ? "high" : "medium", "js-eval", n, deep
          ? "Function constructor reached through .constructor.constructor: compiles code from a string."
          : "Calls a .constructor with arguments: may be the Function constructor, flagged.");
      }
      if (["createContextualFragment", "parseFromString"].includes(last(r)) && a0 && lit(a0) === null &&
          (last(r) !== "parseFromString" || !/xml/i.test(lit(n.arguments[1]) || "html"))) {
        add("medium", "js-html-sink", n, `${last(r)}() of non-constant HTML builds live markup.`);
      }
      if (n.callee.type === "MemberExpression" && JQ_HTML.has(last(r)) && a0 && lit(a0) === null &&
          (last(r) === "html" || /^(\$|jQuery)$|^\$\w|\.\$el$|^\$el$/.test((resolve(n.callee.object) || (n.callee.object.type === "CallExpression" ? resolve(n.callee.object.callee) : "")) || "")) &&
          !["FunctionExpression", "ArrowFunctionExpression"].includes(a0.type)) {
        add("medium", "js-html-sink", n, `jQuery .${last(r)}() of non-constant content parses it as HTML.`);
      }
      if (LOADERS.has(r) || LOADERS.has(last(r))) {
        const k = urlKind(a0);
        if (k !== "local") add(k === "external" ? "high" : "medium", "js-script-load", n,
          `${last(r)}() loads ${k === "external" ? "code from an external host" : "a URL built at runtime (undecidable, flagged)"}.`);
      }
      if (last(r) === "setAttribute" && n.callee.type === "MemberExpression" &&
          ["src", "href", "srcdoc"].includes((lit(a0) || "").toLowerCase())) {
        const t = elemOf(n.callee.object) || (n.callee.object.type === "Identifier" ? elems.get(n.callee.object.name) : null);
        loadSink(n, t, n.arguments[1], lit(a0).toLowerCase());
      }
      if (["fetch", "navigator.sendBeacon", "WebSocket", "EventSource", "$.ajax", "$.get", "$.post",
           "jQuery.ajax", "window.open", "open", "rpc"].includes(r) || last(r) === "open" ||
          last(r) === "send" || last(r) === "rpc") {
        if (n.arguments.some(readsCookie)) add("high", "js-cookie-leak", n, `${r || "request"}() sends document.cookie.`);
      }
      if (r === "eval") add("high", "js-eval", n, "eval() runs arbitrary code.");
      if (r === "Function") add("high", "js-eval", n, "Function(...) compiles code from a string.");
      if (["setTimeout", "setInterval", "setImmediate"].includes(r) && a0 &&
          (lit(a0) !== null || a0.type === "TemplateLiteral" ||
           (a0.type === "BinaryExpression" && a0.operator === "+"))) {
        add("high", "js-eval", n, `${r}() with a string argument evaluates code.`);
      }
      if (["document.write", "document.writeln"].includes(r)) {
        add("medium", "js-html-sink", n, `${r}() writes raw HTML into the page.`);
      }
      if (last(r) === "insertAdjacentHTML" && n.arguments[1] && lit(n.arguments[1]) === null) {
        add("medium", "js-html-sink", n, "insertAdjacentHTML() of non-constant HTML.");
      }
      if ((markupNames.has(r)) && a0 && lit(a0) === null) {
        const inner = a0.type === "CallExpression" ? last(resolve(a0.callee)) : "";
        if (!ESCAPERS.test(inner)) {
          const data = /\b(props|record|data|state|result|res|response)\b/.test(text.slice(a0.start, a0.end));
          add(data ? "medium" : "low", "js-markup", n, data
            ? "markup() of record/server data: rendered unescaped by t-out (stored XSS unless sanitized)."
            : "markup() of non-constant text: rendered unescaped by t-out; make sure it is sanitized.");
        }
      }
      // postMessage to any origin: the message is readable by whatever page embeds this one
      if (last(r) === "postMessage" && lit(n.arguments[1]) === "*") {
        add(readsCookie(a0) ? "high" : "medium", "js-postmessage", n,
            "postMessage(..., '*') hands the message to any origin" + (readsCookie(a0) ? " (carries document.cookie)." : "."));
      }
      // WebAssembly: compiled code the JS audit cannot read
      if (/^WebAssembly\.(instantiate|instantiateStreaming|compile|compileStreaming|Module|Instance)$/.test(r)) {
        add("high", "js-eval", n, `${r}() runs compiled code the audit cannot read.`);
      }
      // patching Odoo's session / user / rpc / network primitives rewrites who the client is
      if (last(r) === "patch" && a0 && /^(session|user|rpc|browser|odoo|window|XMLHttpRequest\.prototype|fetch|navigator)$|(^|\.)(session|user)$/.test(resolve(a0) || "")) {
        add("high", "js-patch-core", n, `patch(${resolve(a0)}) rewrites a core session/network object.`);
      }
      // prototype pollution / network hooks through defineProperty
      if (/^(Object|Reflect)\.(defineProperty|defineProperties|setPrototypeOf|assign)$/.test(r) && a0 &&
          /^(Object|Array|Function|String|Element|Node|HTMLElement|EventTarget|XMLHttpRequest|Document)\.prototype$|^(window|document|navigator)$/.test(resolve(a0) || "") &&
          !(r.endsWith("assign") && resolve(a0) === "window")) {
        const base = resolve(a0) || "";
        add(base === "Object.prototype" || base === "window" || base === "document" || base === "navigator" ? "high" : "medium",
            "js-prototype-tamper", n, `${r}(${base}, ...) changes built-in behaviour for every script (a polyfill is MEDIUM; review it).`);
      }
      // keylogger: key/input listeners on the whole page that send data out
      if (last(r) === "addEventListener" && /^(keydown|keyup|keypress|input|paste|change)$/.test(lit(a0) || "") &&
          n.callee.type === "MemberExpression" && /^(document|window|document\.body|this\.el|el)$/.test(resolve(n.callee.object) || "")) {
        let sends = false;
        if (n.arguments[1]) walk.full(n.arguments[1], (x) => {
          if (x.type === "CallExpression" || x.type === "NewExpression") {
            const q = resolve(x.callee) || "";
            if (/^(fetch|navigator\.sendBeacon|WebSocket|XMLHttpRequest|Image|\$\.ajax|\$\.post|rpc)$/.test(q) || /\.(send|sendBeacon|setItem)$/.test(q)) sends = true;
          }
          if (x.type === "AssignmentExpression" && /(^|\.)src$/.test(resolve(x.left) || "")) sends = true;
        });
        if (sends) add("high", "js-keylogger", n, `Page-wide ${lit(a0)} listener sends what is typed elsewhere.`);
      }
      // JSX / createElement props (TSX compiled by sucrase): src/href into a loaded element
      if (last(r) === "createElement" && n.arguments[1] && n.arguments[1].type === "ObjectExpression") {
        for (const pr of n.arguments[1].properties) {
          const k = pr.type === "Property" && !pr.computed ? (pr.key.name || pr.key.value) : null;
          if (["src", "href", "srcdoc", "data"].includes(k)) loadSink(n, (lit(a0) || "?").toLowerCase(), pr.value, k);
          if (k === "dangerouslySetInnerHTML" && readsUrl(pr.value)) add("high", "js-dom-xss", n, "dangerouslySetInnerHTML from a URL-controlled value.");
        }
      }
      // M3: URL-controlled source into an HTML/code sink
      if ((["document.write", "document.writeln", "eval", "Function", "setTimeout", "setInterval"].includes(r) ||
           ["insertAdjacentHTML", "createContextualFragment", "parseFromString"].includes(last(r)) ||
           (JQ_HTML.has(last(r)) && n.callee.type === "MemberExpression") || markupNames.has(r)) &&
          n.arguments.some(readsUrl)) {
        add("high", "js-dom-xss", n, `${last(r)}() of a URL-controlled value (location/referrer/window.name): DOM XSS.`);
      }
      // network
      const net = new Set(["fetch", "navigator.sendBeacon", "WebSocket", "EventSource", "Worker",
        "SharedWorker", "$.ajax", "$.get", "$.post", "$.getJSON", "jQuery.ajax", "importScripts",
        "window.open", "open", "location.assign", "location.replace"]);
      let urlArg = null, what = r;
      if (net.has(r)) urlArg = a0;
      else if (last(r) === "open" && n.arguments.length >= 2 &&
               (/xhr|request|XMLHttpRequest/i.test(r) || HTTP_VERB.test(lit(a0) || ""))) urlArg = n.arguments[1];
      if (urlArg !== null || (net.has(r) && !a0 && r !== "open" && r !== "window.open")) {
        const k = a0 && a0.type === "ObjectExpression" ? "dynamic" : urlKind(urlArg);
        if (k === "external") add("high", "js-external-request", n, `${what}() to an external URL.`);
        else if (k === "dynamic") add("low", "js-dynamic-request", n, `${what}() to a URL built at runtime: destination undecidable, flagged.`);
      }
      if (r === "navigator.serviceWorker.register" || last(r) === "register" && /serviceWorker/.test(r)) {
        add("high", "js-service-worker", n, "Registers a service worker (persists and intercepts requests).");
      }
      // storage of secrets
      if (/(localStorage|sessionStorage)\.setItem$/.test(r) && n.arguments.length >= 1) {
        const key = lit(a0) || (a0 && a0.type === "Identifier" ? a0.name : "");
        const val = n.arguments[1];
        const vname = val ? (lit(val) || last(resolve(val) || "") || "") : "";  // a.b.token -> token
        if (SECRET.test(key) || SECRET.test(vname)) {
          add("high", "js-token-storage", n, "Stores a token or secret in browser storage.");
        }
      }
      // ORM / RPC to sensitive models: writes (or a write-like server method) on the
      // security core, reads of secret-holding models; a runtime model/method is undecidable
      const meth = last(r);
      const onOrm = /(^|\.)orm(\.|$)|services\.orm/.test(r);
      if (onOrm && a0 && (ORM_WRITES.has(meth) || ORM_READS.has(meth) || meth === "call")) {
        const model = lit(a0);
        const m2 = meth === "call" ? lit(n.arguments[1]) : meth;
        if (model === null) {
          if (ORM_WRITES.has(meth)) add("info", "js-dynamic-model", n, `orm.${meth}() on a model chosen at runtime: undecidable, flagged.`);
        } else if (SENSITIVE.has(model) && (m2 === null || WRITE_METHODS.has(m2))) {
          add(m2 === null ? "medium" : "high", "js-sensitive-model", n,
              `orm.${meth}(${m2 === null ? "<runtime method>" : m2}) on ${model} from the browser.`);
        } else if (SECRET_MODELS.has(model)) {
          add("medium", "js-sensitive-model", n, `orm.${meth}() reads ${model} from the browser.`);
        }
      }
      // H15: mass change from the client - write/unlink over ids from an empty-domain search
      if (onOrm && (MASS_JS.test(meth) || (meth === "call" && MASS_JS.test(lit(n.arguments[1]) || "")))) {
        const idsArg = meth === "call" ? n.arguments[2] : n.arguments[1];
        if (idsArg && emptySearch(idsArg)) add("high", "js-mass-change", n,
          `orm.${meth}() over every record (ids from an empty-domain search) from the browser.`);
      }
      if (["rpc", "jsonrpc", "this.rpc", "rpc.query", "ajax.rpc", "session.rpc"].includes(r) || last(r) === "rpc") {
        const route = lit(a0);
        if (route !== null) {
          const seg = normUrl(route).match(/\/(?:web\/dataset\/call_kw|web\/dataset\/call_button|json\/[12])\/([^/?#]+)(?:\/([^/?#]+))?/i);
          const p = n.arguments[1];
          let model = seg ? seg[1] : null, method = seg ? (seg[2] || null) : null;
          if (p && p.type === "ObjectExpression") {
            for (const prop of p.properties) {
              const k = prop.key && (prop.key.name || prop.key.value);
              if (k === "model") model = lit(prop.value) ?? model;
              if (k === "method") method = lit(prop.value);
            }
          }
          if (MASS_JS.test(method || "") && p && p.type === "ObjectExpression") {
            const ap = p.properties.find((q) => q.key && (q.key.name || q.key.value) === "args");
            const first = ap && ap.value.type === "ArrayExpression" ? ap.value.elements[0] : null;
            if (first && emptySearch(first)) add("high", "js-mass-change", n,
              `rpc() ${method} over every record (ids from an empty-domain search) from the browser.`);
          }
          if (model && SENSITIVE.has(model) && (method === null || WRITE_METHODS.has(method))) {
            add(method === null ? "medium" : "high", "js-sensitive-model", n,
                `rpc() ${method || "<runtime method>"} on ${model} from the browser.`);
          } else if (model && SECRET_MODELS.has(model)) {
            add("medium", "js-sensitive-model", n, `rpc() reads ${model} from the browser.`);
          }
          if (/^\s*(https?:|\/\/)/i.test(route)) add("high", "js-external-request", n, "rpc() to an external URL.");
        } else if (a0) {
          add("low", "js-dynamic-request", n, "rpc() to a route built at runtime: undecidable, flagged.");
        }
      }
      // CA9 H6: raw HTTP (fetch / XMLHttpRequest / sendBeacon / axios / $.ajax) to an ORM endpoint:
      // the JSON body is graded with the same taxonomy as orm.* / rpc()
      let rawUrl = null, rawBody = null, rawWhat = r;
      const optProp = (o, k) => o && o.type === "ObjectExpression" ? (o.properties.find((q) => q.key && (q.key.name || q.key.value) === k) || {}).value || null : null;
      if (r === "fetch" || r === "navigator.sendBeacon") {
        rawUrl = a0; rawBody = r === "fetch" ? optProp(n.arguments[1], "body") : n.arguments[1];
        // CA11 H8: fetch(new Request(url, {body})) / const q = new Request(..); fetch(q)
        let rq = a0;
        if (rq && rq.type === "Identifier" && DOM_VARS.has(rq.name)) rq = DOM_VARS.get(rq.name).find((v) => v && v.type === "NewExpression") || rq;
        if (rq && rq.type === "NewExpression" && rq.callee.type === "Identifier" && rq.callee.name === "Request") {
          rawUrl = rq.arguments[0]; rawBody = rawBody || optProp(rq.arguments[1], "body");
          rawWhat = "fetch(Request)";
        }
      }
      else if (/(^|\.)(axios|http|ajax)\.(post|put|patch|request)$/.test(r) || /^(\$|jQuery)\.(post|ajax)$/.test(r)) {
        if (a0 && a0.type === "ObjectExpression") { rawUrl = optProp(a0, "url"); rawBody = optProp(a0, "data") || optProp(a0, "body"); }
        else { rawUrl = a0; rawBody = n.arguments[1]; }
      } else if (r === "axios" && a0 && a0.type === "ObjectExpression") { rawUrl = optProp(a0, "url"); rawBody = optProp(a0, "data"); }
      else if (last(r) === "send" && n.callee.type === "MemberExpression" && n.callee.object.type === "Identifier" && xhrOrm().has(n.callee.object.name)) {
        rawUrl = xhrOrm().get(n.callee.object.name); rawBody = a0; rawWhat = "XMLHttpRequest.send";
      }
      const cands = rawUrl && rawUrl.type ? urlCands(rawUrl) : [rawUrl];
      const ormC = cands.find((x) => x && ORM_ROUTE.test(x));
      const rawRoute = ormC || cands[cands.length - 1];
      if (rawUrl && cands.length > 1 && ormC && cands.slice(cands.indexOf(ormC) + 1).some((x) => x === null || x.includes(RT)))
        add("high", "js-sensitive-model", n, `${rawWhat}() to a URL rewritten at runtime after naming the ORM (${ormC.split(RT).join("${...}")}): the final model/method is unprovable.`);
      if (rawRoute && ORM_ROUTE.test(rawRoute)) gradeOrmBody(n, rawWhat, rawRoute, rawBody);
      else if (rawUrl && !rawBody && (rawRoute === null || rawRoute.includes(RT)) && mayReachOrm(rawRoute) &&
               /^(post|put|patch|delete)$/i.test(lit(optProp(n.arguments[1], "method")) || (r === "navigator.sendBeacon" ? "post" : ""))) {
        // CA13 H2: a mutating request with no provable body to a URL that may be the ORM
        add("high", "js-sensitive-model", n, `${rawWhat}() ${"POST"} to a URL that may reach the ORM and cannot be proven safe.`);
      }
      else if (rawUrl && rawBody && cands.some((x) => mayReachOrm(x)) && !nonJsonBody(rawBody)) {
        // CA12 H2: a runtime URL that may be call_kw/call_button//jsonrpc: graded by the body
        const bo = bodyObj(rawBody);
        const keys = bo ? bo.properties.map((q) => q.key && (q.key.name || q.key.value)) : [];
        if (!bo || keys.some((k) => ["params", "jsonrpc", "model", "method", "service", "args", "kwargs"].includes(k)))
          gradeOrmBody(n, rawWhat, rawRoute ?? RT, rawBody, true);
      }
    }
    if (n.type === "ImportExpression") {
      const k = urlKind(n.source);
      if (k !== "local") add(k === "external" ? "high" : "medium", "js-dynamic-import", n,
        `import() of ${k === "external" ? "an external" : "a runtime-built"} URL.`);
    }
    // CA11 L2: an HTML form posted to an ORM endpoint (form.action / setAttribute('action'))
    {
      let act = null;
      if (n.type === "AssignmentExpression" && n.left.type === "MemberExpression" && /^(action|formAction)$/.test(n.left.property.name || n.left.property.value || "")) act = n.right;
      if (n.type === "CallExpression" && n.callee.type === "MemberExpression" && (n.callee.property.name === "setAttribute") && /^(action|formaction)$/i.test(lit(n.arguments[0]) || "")) act = n.arguments[1];
      const au = act ? lit(act) : null;
      if (au && ORM_ROUTE.test(au)) add("medium", "js-raw-orm-request", n, `HTML form posts to the ORM endpoint ${au}: CSRF-shaped ORM call, flagged.`);
    }
    if (n.type === "AssignmentExpression" && n.left.type === "MemberExpression") {
      const r = resolve(n.left) || "";
      const prop = last(r);
      if (["src", "href", "srcdoc", "data"].includes(prop)) {
        const o = n.left.object;
        const t = elemOf(o) || (o.type === "Identifier" ? elems.get(o.name) : null);
        loadSink(n, t, n.right, prop);
      }
      if (/(^|\.)document\.domain$/.test(r)) add("medium", "js-document-domain", n,
        "document.domain relaxed: same-origin policy widened to sibling subdomains.");
      if (/(^|\.)location(\.href)?$/.test(r) && !/\.(hash|search|pathname)$/.test(r)) {
        const s = lit(n.right);
        if (s !== null && /^\s*javascript:/i.test(s)) add("high", "js-eval", n, "Navigates to a javascript: URL.");
        else if (s === null && urlKind(n.right) === "dynamic") add("medium", "js-open-redirect", n,
          "location set from a runtime value: open redirect or javascript: navigation, flagged.");
        if (readsCookie(n.right)) add("high", "js-cookie-leak", n, "Navigation URL carries document.cookie.");
      }
      if ((prop === "innerHTML" || prop === "outerHTML") && lit(n.right) === null) {
        if (readsUrl(n.right)) add("high", "js-dom-xss", n, `${prop} from a URL-controlled value (location/referrer/window.name): DOM XSS.`);
        else add("medium", "js-html-sink", n, `${prop} assigned non-constant HTML.`);
      }
      {
        const o = n.left.object;
        const t = elemOf(o) || (o.type === "Identifier" ? elems.get(o.name) : null);
        if (t === "script" && ["text", "textContent", "innerText", "innerHTML"].includes(prop) && lit(n.right) === null) {
          add("high", "js-eval", n, `<script>.${prop} set from a runtime value: runs code built at runtime.`);
        }
      }
      // prototype pollution / network hooks: built-ins rewritten for every script on the page
      if (/^(Object|Array|Function|String|Element|Node|HTMLElement|EventTarget|Document)\.prototype(\.|$)/.test(r) ||
          /(^|\.)__proto__(\.|$)/.test(r)) {
        // writing THROUGH __proto__ pollutes a shared prototype (HIGH); setting an own
        // object's __proto__ (compiled code, Object.setPrototypeOf) only re-links it (LOW)
        const own = /__proto__$/.test(r) && !/^(Object|Array|Function|String|window|document|navigator|globalThis|self)\./.test(r);
        add(own ? "low" : /^Object\.prototype|__proto__/.test(r) ? "high" : "medium", "js-prototype-tamper", n,
            `Assigns ${r}: changes built-in behaviour for every script.`);
      }
      if (/^(fetch|XMLHttpRequest|XMLHttpRequest\.prototype\.(open|send|setRequestHeader)|navigator\.sendBeacon|WebSocket|WebSocket\.prototype\.send|EventSource)$/.test(r)) {
        add("high", "js-network-hook", n, `Replaces ${r}: intercepts every request on the page.`);
      }
      if (r === "document.cookie" || r.endsWith(".document.cookie")) {
        const v = n.right;
        const s = lit(v) || (v.type === "TemplateLiteral" ? v.quasis.map((q) => q.value.cooked).join("") : "") || (resolve(v) || "");
        add(SECRET.test(s) ? "high" : "low", SECRET.test(s) ? "js-token-storage" : "js-cookie-write", n,
            SECRET.test(s) ? "Writes a token or secret into a cookie from script." : "Writes document.cookie from script.");
      }
      if (/^(localStorage|sessionStorage)\.(.+)$/.test(r) && SECRET.test(r)) {
        add("high", "js-token-storage", n, "Stores a token or secret in browser storage.");
      }
      if (n.left.computed && lit(n.left.property) === null && lit(n.right) === null &&
          !["Literal", "ArrowFunctionExpression", "FunctionExpression", "ObjectExpression",
            "ArrayExpression", "NewExpression"].includes(n.right.type)) {
        // el[prop] = value: could be innerHTML; undecidable only on DOM-looking targets
        const o = resolve(n.left.object) || "";
        if (/(^|\.)(el|element|node|target|document\.body|innerEl|\$el)$/i.test(o)) {
          add("low", "js-dynamic-sink", n, "Computed property write on a DOM node: target undecidable, flagged.");
        }
      }
    }
    if (n.type === "Property" && !n.computed) {
      const k = n.key.name || n.key.value;
      if (k === "dangerouslySetInnerHTML" || k === "innerHTML" && n.value && lit(n.value) === null) {
        add("medium", "js-html-sink", n, `${k} set from a non-constant value.`);
      }
    }
  });
  // H9: eval / Function referenced as a value (Reflect.apply(eval, ..), [eval][0](..),
  // eval.call(..), passing it to a helper): any non-call reference is HIGH
  const CODE_GLOBALS = new Set(["eval", "Function"]);
  walk.ancestor(ast, {
    Identifier(n, _s, anc) { valueRef(n, anc); },
    MemberExpression(n, _s, anc) { valueRef(n, anc); },
  });
  function valueRef(n, anc) {
    const p = anc[anc.length - 2];
    const r = n.type === "Identifier" ? (alias.get(n.name) || n.name) : resolve(n);
    if (!CODE_GLOBALS.has(r)) return;
    if (!p) return;
    if ((p.type === "CallExpression" || p.type === "NewExpression") && p.callee === n) return;
    if (p.type === "VariableDeclarator" && p.id === n) return;
    if (p.type === "MemberExpression" && p.object === n && n.type === "Identifier" && n.name === "Function" &&
        !p.computed && p.property.name === "prototype") return;
    if (p.type === "BinaryExpression" && p.operator === "instanceof") return;
    // OWL prop schemas: `static props = { onClick: Function }` / `{ type: Function }` name a
    // type; calling the constructor still needs a call, which is flagged where it happens
    if (r === "Function" && (p.type === "Property" || p.type === "ArrayExpression") && anc.some((x) =>
        ((x.type === "Property" || x.type === "PropertyDefinition") && !x.computed && x.key && (x.key.name || x.key.value) === "props") ||
        (x.type === "AssignmentExpression" && /(^|\.)props$/.test(resolve(x.left) || "")) ||
        (x.type === "Property" && x === p && !p.computed && (p.key.name || p.key.value) === "type"))) return;
    if (p.type === "UnaryExpression" && p.operator === "typeof") return;
    if (p.type === "MemberExpression" && p.property === n && !p.computed) return;
    if (p.type === "Property" && p.key === n && !p.computed && p.value !== n) return;
    if (n.type === "MemberExpression" && anc.length >= 3) {
      const g = anc[anc.length - 2];
      if (g.type === "MemberExpression" && g.object === n) { /* eval.call */ }
    }
    add("high", "js-eval", n, `${r} used as a value (aliased, passed or applied): runs code from strings.`);
  }
  // M3: style URLs carrying cookies / external hosts; Worker from in-memory code
  walk.full(ast, (n) => {
    if (n.type === "AssignmentExpression" && n.left.type === "MemberExpression") {
      const r = resolve(n.left) || "";
      if (/(^|\.)style(\.|$)/.test(r) || /^(background|backgroundImage|cssText|listStyleImage|borderImage|borderImageSource|cursor|content|maskImage|filter)$/.test(last(r))) {
        if (readsCookie(n.right)) add("high", "js-cookie-leak", n, "Style URL carries document.cookie.");
        else {
          const s = lit(n.right) ?? (n.right.type === "TemplateLiteral" ? n.right.quasis.map((q) => q.value.cooked).join("") : "");
          const head = n.right.type === "BinaryExpression" ? lit((function l(x) { while (x.type === "BinaryExpression") x = x.left; return x; })(n.right)) || "" : s;
          if (/url\(\s*["']?\s*(https?:|\/\/)/i.test(s || head || "")) add("medium", "js-external-request", n, "Style loads a URL from an external host.");
        }
      }
    }
    if (n.type === "CallExpression") {
      const r = resolve(n.callee) || "";
      if (/(^|\.)(setProperty|insertRule|setAttribute)$/.test(r) && n.arguments.some(readsCookie)) {
        add("high", "js-cookie-leak", n, `${last(r)}() carries document.cookie into the page.`);
      }
    }
    if (n.type === "NewExpression" || n.type === "CallExpression") {
      const r = resolve(n.callee) || "";
      if (/^(Worker|SharedWorker)$/.test(last(r)) && n.type === "NewExpression") {
        const a0 = n.arguments[0];
        let blob = false;
        if (a0) walk.full(a0, (x) => {
          if (x.type === "CallExpression" && /createObjectURL$/.test(resolve(x.callee) || "")) blob = true;
          if (x.type === "NewExpression" && /^Blob$/.test(resolve(x.callee) || "")) blob = true;
        });
        const k = urlKind(a0);
        let head = lit(a0);
        if (head === null && a0 && a0.type === "TemplateLiteral") head = a0.quasis[0].value.cooked;
        if (head === null && a0 && a0.type === "BinaryExpression") { let l = a0; while (l.type === "BinaryExpression") l = l.left; head = lit(l); }
        if (blob || /^\s*(data:|blob:)/i.test(head || "")) add("high", "js-eval", n, `${last(r)} runs code built in memory (Blob/data URL).`);
        else if (k === "external") add("high", "js-script-load", n, `${last(r)} loads code from an external host.`);
        else if (k === "dynamic") add("medium", "js-script-load", n, `${last(r)} script URL built at runtime: undecidable, flagged.`);
      }
    }
    // H8: OWL inline templates (xml`...`): t-out of Markup renders raw HTML (Odoo 17+)
    // CA9 M2: `static template = T` with T an inline string/backtick template (not a template name)
    const tplOf = (v, d = 0) => {
      if (!v || d > 4) return null;
      if (v.type === "Literal" && typeof v.value === "string") return /</.test(v.value) ? v.value : null;
      if (v.type === "TemplateLiteral") { const t = v.quasis.map((q) => q.value.cooked || "").join("__owl_interp__"); return /</.test(t) ? t : null; }
      if (v.type === "Identifier" && DOM_VARS.has(v.name)) return tplOf(DOM_VARS.get(v.name)[0], d + 1);
      if (v.type === "BinaryExpression" && v.operator === "+") { const a = tplOf(v.left, d + 1) ?? lit(v.left), b = tplOf(v.right, d + 1) ?? lit(v.right); return a !== null && b !== null && /</.test(a + b) ? a + b : null; }
      // CA11 M4: any string the folder can compute ([..].join(''), concat, decoders)
      const f = lit(v);
      return f !== null && /</.test(f) ? f : null;
    };
    const staticTpl = (n.type === "PropertyDefinition" || n.type === "AssignmentExpression") ?
      (n.type === "PropertyDefinition" ? (!n.computed && n.key && (n.key.name || n.key.value) === "template" ? tplOf(n.value) : null)
        : (n.left.type === "MemberExpression" && !n.left.computed && n.left.property.name === "template" ? tplOf(n.right) : null)) : null;
    if ((n.type === "TaggedTemplateExpression" && n.tag.type === "Identifier" && n.tag.name === "xml") || staticTpl !== null) {
      // CA9 M1: the template is XML: character references are decoded before any check
      const text = decodeEntities(staticTpl !== null ? staticTpl : n.quasi.quasis.map((q) => q.value.cooked || "").join("__owl_interp__"));
      for (const m of text.matchAll(/\bt-(out|esc|raw)\s*=\s*(["'])(.*?)\2/gs)) {
        const v = m[3];
        if (m[1] === "raw") { add("high", "owl-t-out", n, "t-raw renders unescaped HTML."); continue; }
        if (/^\s*(['"`][^'"`$]*['"`]|-?\d+)\s*$/.test(v)) continue;
        const mk = v.match(/\b(?:markup|Markup)\s*\(\s*(.*)\)\s*$/s);
        if (mk && !/^\s*(['"`][^'"`$]*['"`])\s*$/.test(mk[1])) add("high", "owl-t-out", n, "t-out of markup(...) of runtime data renders it as raw HTML.");
        else if (!mk && /\b(props|record|env|state)\b|\.data\b/.test(v)) add("medium", "owl-t-out", n, "t-out of props/record data: unescaped when the value is a Markup.");
      }
      // static URL attributes in the inline template
      for (const m of text.matchAll(/\s(href|src|action|formaction|xlink:href|data)\s*=\s*(["'])(.*?)\2/gs)) {
        if (scriptScheme(m[3])) add("high", "owl-js-url", n, `${m[1]} is a javascript:/data:text/html URL: runs code on click/load.`);
      }
      for (const m of text.matchAll(/\ssrcdoc\s*=\s*(["'])(.*?)\1/gs)) {
        if (/<\s*script|\son\w+\s*=|javascript:/i.test(m[2])) add("high", "owl-srcdoc", n, "static srcdoc carries script.");
      }
      // H12: event handlers and dynamic attributes are JS expressions: audit them as code
      for (const m of text.matchAll(/\b(t-on-[\w.-]+|t-att-[\w-]+|t-attf-[\w-]+|t-att|t-props|t-call-context)\s*=\s*(["'])(.*?)\2/gs)) {
        // OWL/QWeb expression syntax: word operators compile to JavaScript ones
        const owlOps = (e) => e.replace(/("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')|\b(and|or|not|gte|lte|gt|lt)\b/g,
          (_q, str, op) => str || { and: "&&", or: "||", not: "!", gte: ">=", lte: "<=", gt: ">", lt: "<" }[op])
          // OWL scope lookups: bare reserved names (class) read ctx, `{ this }` shorthand
          .replace(/(^|[^.\w$'"])class\b(?!\s*:)/g, "$1ctx_class")
          .replace(/([{,]\s*)this(\s*[,}])/g, "$1this: this$2")
          .replace(/[\s;]+$/, "")
          // a bare reserved word is a component method looked up on ctx (t-on-click="delete")
          .replace(/^\s*(delete|default|new|void|typeof|in|instanceof|do|if|for|while|switch|case|return|var|let|const|function|catch|try|finally|throw|with|yield|export|import|super|enum|extends|debugger|continue|break|else|class)\s*$/, "ctx_$1");
        const expr = m[1].startsWith("t-attf-") ? "`" + m[3].replace(/\{\{(.*?)\}\}|#\{(.*?)\}/g, (_q, a1, a2) => "${" + owlOps(a1 || a2) + "}") + "`" : owlOps(m[3]);
        if (DEPTH < 2) {
          DEPTH++;
          const saved = [CONSTS, COOKIE_VARS, URL_VARS, EMPTY_VARS, JSURL_PROPS, PUSHED];
          let r2;
          try { r2 = auditJs("(" + expr + "\n)"); } finally { [CONSTS, COOKIE_VARS, URL_VARS, EMPTY_VARS, JSURL_PROPS, PUSHED] = saved; DEPTH--; }
          if (!r2.ok) add("medium", "owl-expr-unaudited", n, `${m[1]} expression does not parse: unaudited.`);
          else for (const f of r2.findings) if (f.sev === "high" || f.sev === "medium") add(f.sev, f.code, n, `${m[1]}: ${f.msg}`);
        } else if (/[`(]|\bxml\b/.test(m[3])) {
          // CA11 L1: nested inline templates beyond the audit depth fail closed
          add("medium", "owl-expr-unaudited", n, `${m[1]} nested inline template expression beyond audit depth: unaudited.`);
        }
        if (/^t-att(f)?-(href|src|action|formaction|xlink:href|data)$/.test(m[1])) {
          let head = m[1].startsWith("t-attf-") ? m[3].replace(/\{\{\s*(['"])(.*?)\1\s*\}\}|#\{\s*(['"])(.*?)\3\s*\}/g, (_q, _a, x, _b, y) => x ?? y)
            : (m[3].match(/^\s*(['"`])((?:(?!\1).)*)\1/s) || [])[2];
          if (!m[1].startsWith("t-attf-")) {
            try { const e = acorn.parseExpressionAt(owlOps(m[3]), 0, { ecmaVersion: "latest" }); const f = lit(e); if (f !== null) head = f;
              const k = e.type === "MemberExpression" && !e.computed ? e.property.name : e.type === "Identifier" ? e.name : null;
              if (k && JSURL_PROPS.has(k)) head = "javascript:"; } catch { /* unparsable: graded below */ }
          }
          if (scriptScheme(head)) { add("high", "owl-js-url", n, `${m[1]} is a javascript:/data:text/html URL: runs code on click/load.`); continue; }
        }
        if (m[1] === "t-att-srcdoc" && !/^\s*(['"`])[^'"`]*\1\s*$/.test(m[3])) {
          add("high", "owl-srcdoc", n, "t-att-srcdoc from runtime data: the iframe renders it as a live document (DOM XSS).");
          continue;
        }
        if (/^t-att(f)?-(href|src|action|formaction|xlink:href|data)$/.test(m[1]) && !/^\s*(['"`])[^'"`]*\1\s*$/.test(m[3]) &&
            !(m[1].startsWith("t-attf-") && /^\s*(\/[^/{#]|mailto:|tel:|sms:|https?:\/\/)/.test(m[3])) &&
            // a fixed safe scheme/path prefix + data (optionally in a ternary with a null branch)
            !/^\s*(?:[^?'"]*\?\s*)?(['"])(?:mailto:|tel:|sms:|https?:\/\/[^'"\/]+\/|\/(?!\/))[^'"]*\1\s*\+[^:?]*(?::\s*(?:undefined|null|false|''|""))?\s*$/.test(m[3])) {
          // graded by source: URL-controlled HIGH, stored record data MEDIUM, else LOW (flagged)
          const sev = /\b(location|document\.referrer|window\.name)\b/.test(m[3]) ? "high"
            : /\brecord\b|\.data\b/.test(m[3]) ? "medium" : "low";
          add(sev, "owl-url-attr", n, `${m[1]} from runtime data: OWL does not block javascript: URLs.`);
        }
      }
    }
  });
  // JS fixpoint summaries: a function whose parameter reaches a code/HTML/navigation sink
  // is itself a sink; calls to it with a non-constant argument are flagged
  const fns = [];
  const fnName = (n, p) => {
    if (n.id && n.id.name) return n.id.name;
    if (p && p.type === "VariableDeclarator" && p.id.type === "Identifier") return p.id.name;
    if (p && (p.type === "Property" || p.type === "MethodDefinition" || p.type === "PropertyDefinition") && p.key)
      return p.key.name || p.key.value;
    if (p && p.type === "AssignmentExpression") return last(resolve(p.left) || "");
    return null;
  };
  walk.ancestor(ast, {
    Function(n, _s, anc) {
      const name = fnName(n, anc[anc.length - 2]);
      if (!name) return;
      const params = n.params.map((q) => (q.type === "Identifier" ? q.name : q.type === "AssignmentPattern" && q.left.type === "Identifier" ? q.left.name : null));
      fns.push({ name, params, body: n.body });
    }
  });
  const mentions = (e, name) => { let h = false; if (e) walk.full(e, (x) => { if (x.type === "Identifier" && x.name === name) h = true; }); return h; };
  // null prototype + own-key lookups: inherited keys (toString, constructor...) are not sinks
  const SINK_CALL = { __proto__: null, "eval": "high", "Function": "high", "setTimeout": null, "setInterval": null, "document.write": "medium",
    "document.writeln": "medium", "insertAdjacentHTML": "medium", "markup": "medium", "Markup": "medium",
    "createContextualFragment": "medium", "importScripts": "high", "loadJS": "high", "getScript": "high" };
  const summ = new Map(); // name -> Map(paramIdx -> sev)
  const rank = { high: 2, medium: 1 };
  const addSumm = (name, i, sev) => {
    if (!rank[sev]) return false;
    const m = summ.get(name) || new Map();
    if ((rank[m.get(i)] || 0) >= rank[sev]) return false;
    m.set(i, sev); summ.set(name, m); return true;
  };
  for (let round = 0, changed = true; changed; round++) {
    if (round >= 64) { add("high", "js-flow-incomplete", ast, "Taint summaries did not converge: unaudited."); break; }
    changed = false;
    for (const f of fns) {
      f.params.forEach((pn, i) => {
        if (!pn) return;
        walk.full(f.body, (x) => {
          let sev = null;
          if (x.type === "CallExpression" || x.type === "NewExpression") {
            const r = resolve(x.callee) || "";
            const k = Object.hasOwn(SINK_CALL, r) ? r : (Object.hasOwn(SINK_CALL, last(r)) && last(r) !== "eval" ? last(r) : null);
            if (k) {
              const args = x.arguments;
              if ((k === "setTimeout" || k === "setInterval") ? args[0] && args[0].type !== "ArrowFunctionExpression" && args[0].type !== "FunctionExpression" && mentions(args[0], pn) : args.some((a) => mentions(a, pn))) {
                sev = SINK_CALL[k] || "high";
              }
            }
            const callee = last(r);
            const sm = summ.get(callee);
            if (sm && callee !== f.name) {
              for (const [j, sv] of sm) if (x.arguments[j] && mentions(x.arguments[j], pn)) sev = rank[sv] > (rank[sev] || 0) ? sv : sev;
            }
          }
          if (x.type === "AssignmentExpression" && x.left.type === "MemberExpression" && mentions(x.right, pn)) {
            const p = last(resolve(x.left) || "");
            if (p === "innerHTML" || p === "outerHTML" || p === "srcdoc") sev = sev || "medium";
            if (/(^|\.)location(\.href)?$/.test(resolve(x.left) || "")) sev = sev || "medium";
          }
          if (sev && addSumm(f.name, i, sev)) changed = true;
        });
      });
    }
  }
  if (summ.size) {
    const defs = new Set(fns.map((f) => f.body));
    walk.full(ast, (x) => {
      if (x.type !== "CallExpression") return;
      const name = last(resolve(x.callee) || "");
      const sm = summ.get(name);
      if (!sm) return;
      for (const [j, sv] of sm) {
        const a = x.arguments[j];
        if (a && lit(a) === null && a.type !== "ArrowFunctionExpression" && a.type !== "FunctionExpression") {
          // M3: graded by source; attacker-controlled (URL) or cookie arguments are HIGH
          add(readsCookie(a) || readsUrl(a) ? "high" : sv, "js-flow-sink", x,
              `${name}() passes argument ${j + 1} to ${sv === "high" ? "code execution" : "an HTML/navigation sink"} (interprocedural).`);
          break;
        }
      }
    });
    void defs;
  }
  return { ok: true, findings: out };
}

const EXT = /^\s*(?:url\(\s*)?["']?\s*(https?:|\/\/|ftp:)/i;
const INTERP = /#\{|@\{|\$\{|var\(|attr\(|@[a-zA-Z_-]+/;

// TypeScript / JSX: strip types and compile JSX (sucrase keeps line numbers), then audit
function auditTyped(text, kind) {
  // sucrase silently drops non-declare namespaces/modules (their code would vanish unaudited)
  const ns = String(text).match(/(^|[\s;}])(?<!declare\s+)(namespace|module)\s+[\w.]+\s*\{/);
  if (ns) {
    return { ok: false, error: "TypeScript namespace/module block: the type stripper drops it, unaudited",
      line: text.slice(0, ns.index).split("\n").length };
  }
  let code;
  try {
    code = sucrase(text, {
      transforms: kind === "ts" ? ["typescript"] : kind === "tsx" ? ["typescript", "jsx"] : ["jsx"],
      jsxRuntime: "classic", production: true, keepUnusedImports: true, disableESTransforms: true,
    }).code;
  } catch (e) {
    return { ok: false, error: String(e.message).slice(0, 200), line: e.loc ? e.loc.line : 0 };
  }
  return auditJs(code);
}

// CSS escapes (\\75rl( is url(, \\6a avascript: ...) decoded before matching
function cssUnescape(s) {
  return String(s || "").replace(/\\([0-9a-fA-F]{1,6})[ \t\n\r\f]?|\\([^\n0-9a-fA-F])/g, (_m, hex, ch) => {
    if (hex) { const cp = parseInt(hex, 16); return cp > 0 && cp <= 0x10ffff ? String.fromCodePoint(cp) : "\uFFFD"; }
    return ch;
  }).replace(/\/\*[\s\S]*?\*\//g, "");
}

// Indented Sass -> flat SCSS, one output line per input line (line numbers kept): every
// at-rule and declaration is kept with its enclosing selector chain; no parser for the
// indented syntax is trusted to be lossless, so each line is rewritten literally
function sassToScss(text) {
  const stack = []; // [indent, selector]
  const lines = String(text).replace(/\r\n?/g, "\n").split("\n");
  return lines.map((raw) => {
    const t = cssUnescape(raw).trim();
    const ind = raw.length - raw.trimStart().length;
    if (!t || t.startsWith("//")) return "";
    if (t.startsWith("/*")) return "/* */";
    while (stack.length && stack[stack.length - 1][0] >= ind) stack.pop();
    const sel = stack.map((x) => x[1]).join(" ") || "x";
    if (t.startsWith("@") || t.startsWith("+") || t.startsWith("=")) {
      const body = t.replace(/^\+/, "@include ").replace(/^=/, "@mixin ").replace(/;\s*$/, "");
      stack.push([ind, "x"]);
      return /^@(import|use|forward|require|plugin|charset)\b/i.test(body) ? `${body};` : `${sel}{${body.replace(/[{}]/g, "")};}`;
    }
    const decl = t.match(/^(:?[\w$#{}-][\w$#{}.-]*)\s*:\s*(.*)$/) || t.match(/^:([\w-]+)\s+(.*)$/);
    if (decl && !/^[\w-]+:(hover|focus|active|before|after|not|nth|first|last|root|is|where|has)\b/.test(t)) {
      stack.push([ind, sel]);
      return `${sel}{${decl[1].replace(/^:/, "")}:${decl[2].replace(/[{};]/g, " ")};}`;
    }
    stack.push([ind, t.replace(/[{};]/g, " ")]);
    return "";
  }).join("\n");
}

function auditCss(text, kind) {
  if (kind === "sass") { text = sassToScss(text); kind = "scss"; }
  let root;
  try {
    root = (kind === "scss" ? scss : kind === "less" ? less : postcss).parse(text, { from: undefined });
  } catch (e) {
    return { ok: false, error: String(e.reason || e.message).slice(0, 200), line: e.line || 0 };
  }
  const out = [];
  const add = (sev, code, node, msg) =>
    out.push({ sev, code, line: (node.source && node.source.start && node.source.start.line) || 0, msg });
  // H13: preprocessor values: variables, interpolation, string concatenation, unquote(),
  // mixin/function arguments. Substitute what is known, then look for external hosts anywhere
  const vars = new Map();
  root.walk((n) => {
    if (n.type === "decl" && /^\$[\w-]+$/.test(n.prop)) vars.set(n.prop.slice(1), cssUnescape(n.value));
    if (n.type === "atrule" && (n.variable || /:$/.test(n.name))) vars.set(n.name.replace(/:$/, ""), cssUnescape(n.value || n.params || ""));
  });
  const subst = (v) => {
    let t = cssUnescape(v);
    for (let i = 0; i < 8; i++) {
      const before = t;
      t = t.replace(/#\{\s*\$([\w-]+)\s*\}|@\{([\w-]+)\}|\$([\w-]+)|@([\w-]+)/g, (m, a1, a2, a3, a4) => {
        const k = a1 || a2 || a3 || a4;
        return vars.has(k) ? vars.get(k) : m;
      });
      t = t.replace(/(["'])\s*\+\s*(["'])/g, "").replace(/\b(unquote|quote|string\.unquote)\(\s*(["'][^"']*["'])\s*\)/g, "$2");
      if (t === before) break;
    }
    return t;
  };
  const EXT_ANY = /(["'(]\s*|\burl\(\s*["']?)(https?:|\/\/[\w.-]+\.|ftp:)/i;
  root.walk((n) => {
    if (n.type === "atrule" && !n.variable && !["import", "use", "forward", "require", "plugin", "media", "supports", "font-face", "keyframes", "charset", "namespace"].includes(cssUnescape(n.name).toLowerCase())) {
      const p = subst(n.params || "");
      if (/^(include|return|mixin|function|each|if|else|while|for|extend|debug|warn|error)$/i.test(n.name) || /load-css/.test(p)) {
        if (/load-css|loadCss/.test(p) && (EXT_ANY.test(p) || /load-css\(\s*\$|load-css\(\s*#\{/.test(n.params || ""))) {
          add("high", "css-external-import", n, "meta.load-css() of an external or runtime-chosen stylesheet.");
        } else if (EXT_ANY.test(p)) {
          add("medium", "css-external-url", n, `@${n.name} passes an external URL (preprocessor argument).`);
        }
      }
    }
    if (n.type === "decl" && !/^\$[\w-]+$/.test(n.prop)) {
      const raw = cssUnescape(n.value || "");
      const v = subst(n.value || "");
      if (v !== raw && /url\(|image-set\(/i.test(v) && EXT_ANY.test(v)) {
        add("medium", "css-external-url", n, "url() resolves (after variables/interpolation) to an external host.");
      }
    }
    // overlay phishing: a fixed, full-screen, top-most layer that prints its own text
    if (n.type === "rule") {
      const d = {};
      n.each((x) => { if (x.type === "decl") d[cssUnescape(x.prop).toLowerCase()] = cssUnescape(x.value); });
      const full = /^0(px)?(\s+0(px)?)*$/.test((d.inset || "").trim()) || (/100(vw|%)/.test(d.width || "") && /100(vh|%)/.test(d.height || ""));
      if (/fixed/.test(d.position || "") && full && parseInt(d["z-index"] || "0", 10) >= 1000 &&
          /^["'][^"']{12,}["']/.test((d.content || "").trim())) {
        add("medium", "css-overlay", n, "Full-screen top-most layer with its own text (can impersonate a login or alert).");
      }
    }
  });
  root.walk((n) => {
    if (n.type === "atrule" && ["import", "use", "forward", "require", "plugin"].includes(cssUnescape(n.name).toLowerCase())) {
      const p = subst(n.params || "").replace(/^\s*\([^)]*\)\s*/, ""); // LESS @import (css) url(...)
      if (EXT.test(p) || EXT_ANY.test(p)) add("high", "css-external-import", n, "@import from an external host.");
      else if (INTERP.test(p.replace(/^[^(]*\(/, ""))) add("medium", "css-dynamic-url", n, "@import of a URL built from variables: undecidable, flagged.");
    }
    if (n.type === "decl") {
      const v = cssUnescape(n.value || "");
      const prop = cssUnescape(n.prop || "").toLowerCase();
      if (/expression\s*\(/i.test(v)) add("high", "css-expression", n, "CSS expression() runs script (legacy IE).");
      if (prop === "behavior" || prop === "-moz-binding") add("high", "css-expression", n, `${prop} loads script.`);
      if (/javascript:/i.test(v)) add("high", "css-expression", n, "javascript: URL in CSS.");
      const urls = [...v.matchAll(/url\(\s*([^)]*)\)/gi)].map((m) => m[1]);
      // image-set("a.png" 1x) / -webkit-image-set: bare strings are URLs too
      for (const m of v.matchAll(/image-set\(([^)]*(?:\([^)]*\)[^)]*)*)\)/gi)) {
        for (const q of m[1].matchAll(/(["'])(.*?)\1/g)) urls.push(q[2]);
      }
      for (const u of urls) {
        const sel = n.parent && n.parent.selector ? cssUnescape(n.parent.selector) : "";
        const ext = EXT.test(u);
        const runtime = /var\(|attr\(/.test(u); // set at runtime (custom property / attribute)
        if (ext && /\[[^\]]*[\^$*~|]?=/.test(sel)) {
          add("high", "css-exfiltration", n, "Attribute selector loads an external URL: leaks attribute values.");
        } else if (ext && runtime) {
          add("high", "css-exfiltration", n, "External url() built from runtime values (data exfiltration).");
        } else if (/\[[^\]]*[\^$*]=/.test(sel) && /^\s*["']?\s*data:/i.test(u)) {
          // inline data: URL: no request is made, nothing can leak
        } else if (/\[[^\]]*[\^$*]=/.test(sel) && !runtime && !/[?#]/.test(u)) {
          add("low", "css-exfiltration", n, "Attribute value-match selector loads a fixed same-origin URL (icons by type); a leak needs a per-value query, flagged LOW.");
        } else if (/\[[^\]]*[\^$*]=/.test(sel)) {
          add("medium", "css-exfiltration", n, "Attribute value-match selector loads a URL: leaks attribute values to the server log.");
        } else if (ext) {
          add("medium", "css-external-url", n, "url() loads from an external host.");
        } else if (runtime && /^\s*["']?\s*(var\(|attr\()/.test(u)) {
          add("medium", "css-dynamic-url", n, "url() target set at runtime: undecidable, flagged.");
        } else if (/^\s*["']?\s*(#\{|@\{|\$|@[a-zA-Z_-])/.test(u)) {
          add("info", "css-dynamic-url", n, "url() host chosen by a stylesheet variable: undecidable, flagged.");
        }
      }
    }
  });
  return { ok: true, findings: out };
}

let raw = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (d) => { raw += d; });
process.stdin.on("end", () => {
  const req = JSON.parse(raw);
  PROPS_BUILT = !!req.propsDomain;
  const results = req.files.map((f) => {
    try {
      const r = f.kind === "js" ? auditJs(f.text)
        : ["ts", "tsx", "jsx"].includes(f.kind) ? auditTyped(f.text, f.kind)
        : auditCss(f.text, f.kind);
      return { path: f.path, ...r };
    } catch (e) {
      return { path: f.path, ok: false, error: `helper error ${String(e.message).slice(0, 120)}`, line: 0 };
    }
  });
  process.stdout.write(JSON.stringify({ helper: "ingenium-code-audit-js/1", results }));
});

function emptySearch(node) {
  // true when node (or an await/array wrapping it) is orm.search*(model, []) with an empty domain
  let found = false;
  (function walk(x, d) {
    if (!x || typeof x !== "object" || found || d > 12) return;
    if (x.type === "Identifier" && EMPTY_VARS.has(x.name)) { found = true; return; }
    if (x.type === "MemberExpression" && EMPTY_VARS.has(mkey(x))) { found = true; return; }
    const isEmpty = (a) => domBound(a) !== "B";
    const SEARCHES = /^(search|searchRead|search_read|webSearchRead|web_search_read)$/;
    if (x.type === "CallExpression" && x.callee) {
      const c0 = x.callee;
      const nm = c0.type === "MemberExpression" && c0.property ? (c0.property.name || c0.property.value) : (c0.name || "");
      // orm.call(model, 'search', [[]]) / orm.call(model, 'search_read', [], {domain: []})
      if (nm === "call" && SEARCHES.test(lit(x.arguments[1]) || "")) {
        const a = x.arguments[2];
        if (!a || (a.type === "ArrayExpression" ? (a.elements.length === 0 || isEmpty(a.elements[0])) : false)) { found = true; return; }
      }
    }
    // CA14 H4: JSON-2 search, fetch('/json/2/<model>/search', {body: {domain: []}}) (no domain = all)
    if (x.type === "CallExpression" && x.callee && x.arguments.length && /^(fetch|rpc)$/.test(x.callee.name || (x.callee.property && x.callee.property.name) || "")) {
      const u = urlPat(x.arguments[0]);
      if (u && /\/json\/[12]\/[^/]+\/(search|search_read|web_search_read|search_fetch)\b/i.test(u)) {
        const opt = x.arguments[1];
        const gp = (o, k) => o && o.type === "ObjectExpression" ? (o.properties.find((q) => q.key && (q.key.name || q.key.value) === k) || {}).value || null : null;
        let body = x.callee.name === "fetch" ? gp(opt, "body") : opt;
        if (body && body.type === "CallExpression" && body.arguments.length) body = body.arguments[0];
        const dom = body && body.type === "ObjectExpression" ? gp(body, "domain") : null;
        if (!body || body.type !== "ObjectExpression" || !dom || isEmpty(dom)) { found = true; return; }
      }
    }
    // rpc payload {model, method: 'search', args: [[]]} / kwargs {domain: []}
    if (x.type === "ObjectExpression") {
      const get = (k) => { const q = x.properties.find((y) => y.key && (y.key.name || y.key.value) === k); return q ? q.value : null; };
      const m = get("method");
      if (m && SEARCHES.test(lit(m) || "")) {
        const a = get("args"), kw = get("kwargs");
        const dom = kw && kw.type === "ObjectExpression" ? kw.properties.find((y) => y.key && (y.key.name || y.key.value) === "domain") : null;
        if (dom ? isEmpty(dom.value) : (!a || (a.type === "ArrayExpression" && (a.elements.length === 0 || isEmpty(a.elements[0]))))) { found = true; return; }
      }
    }
    if (x.type === "CallExpression" && x.callee) {
      const c = x.callee;
      const name = c.type === "MemberExpression" && c.property ? (c.property.name || c.property.value) : "";
      if (/^(search|searchRead|search_read|webSearchRead)$/.test(name || "")) {
        const dom = x.arguments[1];
        if (isEmpty(dom)) { found = true; return; }
      }
    }
    for (const k of Object.keys(x)) if (k !== "loc" && k !== "start" && k !== "end") {
      const v = x[k];
      if (Array.isArray(v)) v.forEach((y) => walk(y, d + 1)); else if (v && typeof v === "object") walk(v, d + 1);
    }
  })(node, 0);
  return found;
}
