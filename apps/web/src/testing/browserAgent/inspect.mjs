#!/usr/bin/env node
/**
 * Browser-testing sub-agent (Stage F). Reads {files} JSON on stdin.
 * Same defect classes as apps/api/app/ai_browser_agent.py. Not a second compiler.
 */

import { pathToFileURL } from "node:url";

const DEFECT_UNPARSEABLE = "view_arch_unparseable";
const DEFECT_FIELD_NAME = "view_arch_field_missing_name";
const DEFECT_XPATH_EMPTY = "view_arch_xpath_empty";

export function inspectModuleFiles(files) {
  const moduleName = moduleNameOf(files);
  const findings = [];
  const caught = [];
  const tour = [];
  let viewsChecked = 0;

  for (const path of Object.keys(files).sort()) {
    const norm = path.replace(/\\/g, "/");
    if (!norm.endsWith(".xml")) continue;
    if (`/${norm}`.includes("/security/")) continue;
    const content = files[path] || "";
    if (isQwebOnly(content)) continue;
    if (!content.includes("ir.ui.view")) continue;

    const parsed = parseXml(content);
    if (!parsed) {
      viewsChecked += 1;
      const viewId = hintViewId(content) || norm;
      record(findings, caught, {
        module: moduleName,
        view: viewId,
        defect: DEFECT_UNPARSEABLE,
        detail: "ir.ui.view XML is not well-formed",
        file: norm,
      });
      tour.push({
        action: "open_view",
        view_id: viewId,
        model: "",
        file: norm,
        result: "fail",
      });
      continue;
    }

    for (const rec of iterByTag(parsed, "record")) {
      if ((attr(rec, "model") || "").trim() !== "ir.ui.view") continue;
      const viewId = (attr(rec, "id") || "").trim() || norm;
      const model = recordModelField(rec);
      viewsChecked += 1;
      const archEl = childField(rec, "arch");
      const step = {
        action: "open_view",
        view_id: viewId,
        model,
        file: norm,
        result: "ok",
      };
      if (!archEl || (!archEl.children.length && !(archEl.text || "").trim())) {
        record(findings, caught, {
          module: moduleName,
          view: viewId,
          defect: DEFECT_UNPARSEABLE,
          detail: "ir.ui.view arch is empty",
          file: norm,
        });
        step.result = "fail";
        tour.push(step);
        continue;
      }
      for (const el of walk(archEl)) {
        if (el === archEl) continue;
        const tag = (el.tag || "").toLowerCase();
        if (tag === "field" && !(attr(el, "name") || "").trim()) {
          record(findings, caught, {
            module: moduleName,
            view: viewId,
            defect: DEFECT_FIELD_NAME,
            detail: "OWL field widget is missing name",
            file: norm,
          });
          step.result = "fail";
        }
        if (tag === "xpath" && !(attr(el, "expr") || "").trim()) {
          record(findings, caught, {
            module: moduleName,
            view: viewId,
            defect: DEFECT_XPATH_EMPTY,
            detail: "inherit xpath expr is empty",
            file: norm,
          });
          step.result = "fail";
        }
      }
      tour.push(step);
    }
  }

  return {
    ran: true,
    ok: findings.length === 0,
    module: moduleName,
    views_checked: viewsChecked,
    tour,
    findings,
    caught,
    false_positive_rate: rate(findings.length, viewsChecked),
  };
}

function moduleNameOf(files) {
  for (const path of Object.keys(files)) {
    const norm = path.replace(/\\/g, "/");
    if (norm.endsWith("__manifest__.py")) {
      const parts = norm.split("/").filter(Boolean);
      if (parts.length >= 2) return parts[parts.length - 2];
      return parts[0] || "unknown";
    }
  }
  for (const path of Object.keys(files)) {
    const parts = path.replace(/\\/g, "/").split("/").filter(Boolean);
    if (parts[0]) return parts[0];
  }
  return "unknown";
}

function isQwebOnly(content) {
  if (content.includes("ir.ui.view")) return false;
  return content.includes("<templates") || content.includes("t-name=");
}

function hintViewId(content) {
  const dq = content.match(/\bid="([^"]+)"/);
  if (dq) return dq[1];
  const sq = content.match(/\bid='([^']+)'/);
  return sq ? sq[1] : "";
}

function record(findings, caught, row) {
  findings.push(
    `browser_agent: module=${row.module} view=${row.view} defect=${row.defect}: ${row.detail} [${row.file}]`,
  );
  const slim = {
    module: row.module,
    view: row.view,
    defect: row.defect,
    file: row.file,
  };
  if (!caught.some((c) => JSON.stringify(c) === JSON.stringify(slim))) {
    caught.push(slim);
  }
}

function rate(findingCount, viewsChecked) {
  if (viewsChecked <= 0) return 0.0;
  return findingCount / viewsChecked;
}

function parseXml(content) {
  const body = (content || "").replace(/^\uFEFF/, "").trim();
  if (!body) return null;
  const stripped = body.replace(/^<\?xml[^?]*\?>\s*/i, "");
  try {
    return parseElement(stripped);
  } catch {
    try {
      return parseElement(`<data>${stripped}</data>`);
    } catch {
      return null;
    }
  }
}

function parseElement(xml) {
  const tokens = tokenize(xml);
  const stack = [];
  let root = null;
  let i = 0;
  while (i < tokens.length) {
    const tok = tokens[i];
    if (tok.kind === "text") {
      if (stack.length) stack[stack.length - 1].text += tok.value;
      i += 1;
      continue;
    }
    if (tok.kind === "comment" || tok.kind === "pi") {
      i += 1;
      continue;
    }
    if (tok.kind === "close") {
      if (!stack.length || stack[stack.length - 1].tag !== tok.tag) {
        throw new Error("mismatch");
      }
      const done = stack.pop();
      if (!stack.length) root = done;
      i += 1;
      continue;
    }
    const node = {
      tag: tok.tag,
      attrs: tok.attrs,
      children: [],
      text: "",
    };
    if (stack.length) stack[stack.length - 1].children.push(node);
    if (tok.selfClosing) {
      if (!stack.length) root = node;
    } else {
      stack.push(node);
    }
    i += 1;
  }
  if (stack.length) throw new Error("unclosed");
  if (!root) throw new Error("empty");
  return root;
}

function tokenize(xml) {
  const tokens = [];
  let i = 0;
  while (i < xml.length) {
    if (xml.startsWith("<!--", i)) {
      const end = xml.indexOf("-->", i + 4);
      if (end === -1) throw new Error("comment");
      tokens.push({ kind: "comment" });
      i = end + 3;
      continue;
    }
    if (xml.startsWith("<?", i)) {
      const end = xml.indexOf("?>", i + 2);
      if (end === -1) throw new Error("pi");
      tokens.push({ kind: "pi" });
      i = end + 2;
      continue;
    }
    if (xml[i] !== "<") {
      const next = xml.indexOf("<", i);
      const text = next === -1 ? xml.slice(i) : xml.slice(i, next);
      tokens.push({ kind: "text", value: text });
      i = next === -1 ? xml.length : next;
      continue;
    }
    let j = i + 1;
    let quote = "";
    while (j < xml.length) {
      const c = xml[j];
      if (quote) {
        if (c === quote) quote = "";
      } else if (c === '"' || c === "'") {
        quote = c;
      } else if (c === ">") {
        break;
      }
      j += 1;
    }
    if (j >= xml.length) throw new Error("unterminated");
    const raw = xml.slice(i + 1, j);
    i = j + 1;
    if (raw.startsWith("/")) {
      tokens.push({ kind: "close", tag: raw.slice(1).trim().split(/\s+/)[0] });
      continue;
    }
    const selfClosing = raw.endsWith("/");
    const body = selfClosing ? raw.slice(0, -1).trim() : raw.trim();
    const tagMatch = body.match(/^([A-Za-z_][\w:.-]*)/);
    if (!tagMatch) throw new Error("tag");
    tokens.push({
      kind: "open",
      tag: tagMatch[1],
      attrs: parseAttrs(body.slice(tagMatch[1].length)),
      selfClosing,
    });
  }
  return tokens;
}

function parseAttrs(src) {
  const attrs = {};
  const re = /([A-Za-z_][\w:.-]*)\s*=\s*("([^"]*)"|'([^']*)')/g;
  let m;
  while ((m = re.exec(src))) {
    attrs[m[1]] = m[3] !== undefined ? m[3] : m[4];
  }
  return attrs;
}

function attr(node, name) {
  return node?.attrs?.[name] ?? "";
}

function childField(rec, name) {
  return (rec.children || []).find(
    (c) => c.tag === "field" && attr(c, "name") === name,
  );
}

function recordModelField(rec) {
  const el = childField(rec, "model");
  return (el?.text || "").trim();
}

function iterByTag(root, tag) {
  return walk(root).filter((n) => n.tag === tag);
}

function walk(node) {
  const out = [node];
  for (const child of node.children || []) out.push(...walk(child));
  return out;
}

function readStdin() {
  return new Promise((resolve, reject) => {
    const chunks = [];
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (c) => chunks.push(c));
    process.stdin.on("end", () => resolve(chunks.join("")));
    process.stdin.on("error", reject);
  });
}

function runningAsCli() {
  try {
    return Boolean(process.argv[1]) && import.meta.url === pathToFileURL(process.argv[1]).href;
  } catch {
    return false;
  }
}

if (runningAsCli()) {
  const raw = await readStdin();
  let payload;
  try {
    payload = JSON.parse(raw || "{}");
  } catch {
    process.stderr.write("browser_agent: invalid JSON on stdin\n");
    process.exit(2);
  }
  const report = inspectModuleFiles(payload.files || {});
  process.stdout.write(`${JSON.stringify(report)}\n`);
}
