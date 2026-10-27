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
function lit(n) {
  if (!n) return null;
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
  return null;
}

// does this expression read document.cookie anywhere (exfiltration through a URL or body)
function readsCookie(n) {
  let hit = false;
  if (!n) return false;
  walk.full(n, (x) => {
    if (x.type === "MemberExpression" && ((!x.computed && x.property.name === "cookie") ||
        lit(x.property) === "cookie")) hit = true;
    if (x.type === "Identifier" && COOKIE_VARS.has(x.name)) hit = true;
  });
  return hit;
}
const HTTP_VERB = /^(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)$/i;
const LOADERS = new Set(["loadJS", "loadCSS", "loadBundle", "loadAssets", "loadLibs", "getScript", "$.getScript", "jQuery.getScript"]);
const JQ_HTML = new Set(["html", "append", "prepend", "after", "before", "replaceWith", "wrap", "wrapAll", "wrapInner"]);

// "external" | "dynamic" | "local" for a URL argument
function urlKind(n) {
  const s = lit(n);
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
  const out = [];
  const add = (sev, code, node, msg) => out.push({ sev, code, line: node.loc.start.line, msg });
  // H10: fold identifiers bound to constant strings (once, never reassigned) and track
  // variables that hold document.cookie, to a fixpoint
  CONSTS = new Map();
  COOKIE_VARS = new Set();
  const assigned = new Map();
  walk.full(ast, (n) => {
    if (n.type === "VariableDeclarator" && n.id.type === "Identifier") {
      assigned.set(n.id.name, (assigned.get(n.id.name) || 0) + 1);
    }
    if (n.type === "AssignmentExpression" && n.left.type === "Identifier") {
      assigned.set(n.left.name, (assigned.get(n.left.name) || 0) + 2);
    }
  });
  for (let round = 0, changed = true; changed && round < 64; round++) {
    changed = false;
    walk.full(ast, (n) => {
      let id = null, v = null;
      if (n.type === "VariableDeclarator" && n.id.type === "Identifier" && n.init) [id, v] = [n.id.name, n.init];
      if (n.type === "AssignmentExpression" && n.left.type === "Identifier") [id, v] = [n.left.name, n.right];
      if (!id) return;
      if (assigned.get(id) === 1 && !CONSTS.has(id)) {
        const s = lit(v);
        if (s !== null) { CONSTS.set(id, s); changed = true; }
      }
      if (!COOKIE_VARS.has(id) && readsCookie(v)) { COOKIE_VARS.add(id); changed = true; }
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
        }
      }
    }
    if (n.type === "ImportDeclaration" && n.source.value === "@odoo/owl") {
      for (const s of n.specifiers) {
        if (s.imported && s.imported.name === "markup") markupNames.add(s.local.name);
      }
    }
  });
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
    if (prop === "srcdoc") { if (lit(val) === null) add("medium", "js-html-sink", n, "srcdoc set from non-constant HTML."); return; }
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
          add("low", "js-markup", n, "markup() of non-constant text: rendered unescaped by t-out; make sure it is sanitized.");
        }
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
      if (["rpc", "jsonrpc", "this.rpc", "rpc.query", "ajax.rpc", "session.rpc"].includes(r) || last(r) === "rpc") {
        const route = lit(a0);
        if (route !== null) {
          const seg = route.match(/\/web\/dataset\/call_kw\/([^/]+)(?:\/([^/?]+))?/);
          const p = n.arguments[1];
          let model = seg ? seg[1] : null, method = seg ? (seg[2] || null) : null;
          if (p && p.type === "ObjectExpression") {
            for (const prop of p.properties) {
              const k = prop.key && (prop.key.name || prop.key.value);
              if (k === "model") model = lit(prop.value) ?? model;
              if (k === "method") method = lit(prop.value);
            }
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
    }
    if (n.type === "ImportExpression") {
      const k = urlKind(n.source);
      if (k !== "local") add(k === "external" ? "high" : "medium", "js-dynamic-import", n,
        `import() of ${k === "external" ? "an external" : "a runtime-built"} URL.`);
    }
    if (n.type === "AssignmentExpression" && n.left.type === "MemberExpression") {
      const r = resolve(n.left) || "";
      const prop = last(r);
      if (["src", "href", "srcdoc", "data"].includes(prop)) {
        const o = n.left.object;
        const t = elemOf(o) || (o.type === "Identifier" ? elems.get(o.name) : null);
        loadSink(n, t, n.right, prop);
      }
      if (/(^|\.)location(\.href)?$/.test(r) && !/\.(hash|search|pathname)$/.test(r)) {
        const s = lit(n.right);
        if (s !== null && /^\s*javascript:/i.test(s)) add("high", "js-eval", n, "Navigates to a javascript: URL.");
        else if (s === null && urlKind(n.right) === "dynamic") add("medium", "js-open-redirect", n,
          "location set from a runtime value: open redirect or javascript: navigation, flagged.");
        if (readsCookie(n.right)) add("high", "js-cookie-leak", n, "Navigation URL carries document.cookie.");
      }
      if ((prop === "innerHTML" || prop === "outerHTML") && lit(n.right) === null) {
        add("medium", "js-html-sink", n, `${prop} assigned non-constant HTML.`);
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
    if (n.type === "TaggedTemplateExpression" && n.tag.type === "Identifier" && n.tag.name === "xml") {
      const text = n.quasi.quasis.map((q) => q.value.cooked || "").join("${}");
      for (const m of text.matchAll(/\bt-(out|esc|raw)\s*=\s*(["'])(.*?)\2/gs)) {
        const v = m[3];
        if (m[1] === "raw") { add("high", "owl-t-out", n, "t-raw renders unescaped HTML."); continue; }
        if (/^\s*(['"`][^'"`$]*['"`]|-?\d+)\s*$/.test(v)) continue;
        const mk = v.match(/\b(?:markup|Markup)\s*\(\s*(.*)\)\s*$/s);
        if (mk && !/^\s*(['"`][^'"`$]*['"`])\s*$/.test(mk[1])) add("high", "owl-t-out", n, "t-out of markup(...) of runtime data renders it as raw HTML.");
        else if (!mk && /\b(props|record|env|state)\b|\.data\b/.test(v)) add("medium", "owl-t-out", n, "t-out of props/record data: unescaped when the value is a Markup.");
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
  const SINK_CALL = { "eval": "high", "Function": "high", "setTimeout": null, "setInterval": null, "document.write": "medium",
    "document.writeln": "medium", "insertAdjacentHTML": "medium", "markup": "medium", "Markup": "medium",
    "createContextualFragment": "medium", "importScripts": "high", "loadJS": "high", "getScript": "high" };
  const summ = new Map(); // name -> Map(paramIdx -> sev)
  const rank = { high: 2, medium: 1 };
  const addSumm = (name, i, sev) => {
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
            const k = SINK_CALL[r] !== undefined ? r : (SINK_CALL[last(r)] !== undefined && last(r) !== "eval" ? last(r) : null);
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
          add(readsCookie(a) ? "high" : sv, "js-flow-sink", x,
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
  root.walk((n) => {
    if (n.type === "atrule" && ["import", "use", "forward", "require", "plugin"].includes(cssUnescape(n.name).toLowerCase())) {
      const p = cssUnescape(n.params || "");
      if (EXT.test(p)) add("high", "css-external-import", n, "@import from an external host.");
      else if (/url\(/.test(p) && INTERP.test(p.replace(/^[^(]*\(/, ""))) add("medium", "css-dynamic-url", n, "@import of a URL built from variables: undecidable, flagged.");
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
