// BOT-CODE-AUDIT web helper: parse JS (acorn) and CSS/SCSS/LESS (postcss) and report risky
// shapes. Read-only: reads one JSON document on stdin, writes one on stdout, never touches
// the network or the file system beyond its own modules. Every file either parses and is
// walked, or comes back {ok:false} so the caller reports it as unaudited (fail closed).
import * as acorn from "acorn";
import * as walk from "acorn-walk";
import postcss from "postcss";
import scss from "postcss-scss";
import less from "postcss-less";

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

function lit(n) {
  if (!n) return null;
  if (n.type === "Literal" && typeof n.value === "string") return n.value;
  if (n.type === "TemplateLiteral" && n.expressions.length === 0) return n.quasis[0].value.cooked;
  return null;
}

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
  // aliases: const e = eval; const { write } = document; const w = window; let f = fetch
  const alias = new Map();
  const markupNames = new Set(["markup", "Markup"]);
  walk.full(ast, (n) => {
    if (n.type === "VariableDeclarator" && n.id.type === "Identifier" && n.init) {
      const r = resolve(n.init);
      if (r) alias.set(n.id.name, r);
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
    if (n.type === "CallExpression" && n.callee.type === "MemberExpression" && !n.callee.computed
        && n.callee.property.name === "bind") return resolve(n.callee.object);
    return null;
  }
  const last = (r) => (r || "").split(".").pop();
  walk.full(ast, (n) => {
    if (n.type === "CallExpression" || n.type === "NewExpression") {
      const r = resolve(n.callee) || "";
      const a0 = n.arguments[0];
      if (r === "?dynamic") {
        add("low", "js-dynamic-call", n, "Call through a computed global name: target undecidable, flagged.");
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
      else if (last(r) === "open" && n.arguments.length >= 2 && /xhr|request|XMLHttpRequest/i.test(r)) urlArg = n.arguments[1];
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
  return { ok: true, findings: out };
}

const EXT = /^\s*(?:url\(\s*)?["']?\s*(https?:|\/\/|ftp:)/i;
const INTERP = /#\{|@\{|\$\{|var\(|attr\(|@[a-zA-Z_-]+/;

function auditCss(text, kind) {
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
    if (n.type === "atrule" && n.name === "import") {
      const p = n.params || "";
      if (EXT.test(p)) add("high", "css-external-import", n, "@import from an external host.");
      else if (/url\(/.test(p) && INTERP.test(p.replace(/^[^(]*\(/, ""))) add("medium", "css-dynamic-url", n, "@import of a URL built from variables: undecidable, flagged.");
    }
    if (n.type === "decl") {
      const v = String(n.value || "");
      const prop = String(n.prop || "").toLowerCase();
      if (/expression\s*\(/i.test(v)) add("high", "css-expression", n, "CSS expression() runs script (legacy IE).");
      if (prop === "behavior" || prop === "-moz-binding") add("high", "css-expression", n, `${prop} loads script.`);
      if (/javascript:/i.test(v)) add("high", "css-expression", n, "javascript: URL in CSS.");
      const urls = [...v.matchAll(/url\(\s*([^)]*)\)/gi)].map((m) => m[1]);
      for (const u of urls) {
        const sel = n.parent && n.parent.selector ? n.parent.selector : "";
        const ext = EXT.test(u);
        const runtime = /var\(|attr\(/.test(u); // set at runtime (custom property / attribute)
        if (ext && /\[[^\]]*[\^$*~|]?=/.test(sel)) {
          add("high", "css-exfiltration", n, "Attribute selector loads an external URL: leaks attribute values.");
        } else if (ext && runtime) {
          add("high", "css-exfiltration", n, "External url() built from runtime values (data exfiltration).");
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
      const r = f.kind === "js" ? auditJs(f.text) : auditCss(f.text, f.kind);
      return { path: f.path, ...r };
    } catch (e) {
      return { path: f.path, ok: false, error: `helper error ${String(e.message).slice(0, 120)}`, line: 0 };
    }
  });
  process.stdout.write(JSON.stringify({ helper: "ingenium-code-audit-js/1", results }));
});
