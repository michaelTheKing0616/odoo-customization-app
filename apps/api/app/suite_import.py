"""Configuration Suite: paste or upload any document into the import targets (catalog 2.21, spec 20.13).

Reading reuses the ingest readers (CSV/XLSX via data_import.parse_tabular, PDF text via
ingest.extract_pdf). Code maps columns to fields; a column it can't place becomes a
question, never a guess. Check is Odoo's own import test (base_import execute_import with
dryrun) and Apply imports with external ids __ingenium_import__.{job}_{table}_{row}, so Undo
can remove exactly those records (archiving any that are in use).
"""

from __future__ import annotations

import base64
import csv
import difflib
import io
import re
import zipfile
from typing import Any
from xml.etree import ElementTree as ET  # noqa: N817

XMLID_MODULE = "__ingenium_import__"
MAX_ROWS = 2000
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _x(client: Any, model: str, method: str, args: list[Any] | None = None, kw: dict[str, Any] | None = None) -> Any:
    return client.execute_kw(model, method, args or [], kw or {})


# ---------------------------------------------------------------- reading
def _table_from_text(text: str, name: str) -> list[dict[str, Any]]:
    lines = [ln for ln in (text or "").replace("\r\n", "\n").split("\n") if ln.strip()]
    if not lines:
        return []
    md = [ln for ln in lines if ln.strip().startswith("|")]
    if len(md) >= 2:
        rows = [[c.strip() for c in ln.strip().strip("|").split("|")] for ln in md if not re.fullmatch(r"\|?[\s:\-|]+\|?", ln.strip())]
        return [{"name": name, "headers": rows[0], "rows": rows[1:MAX_ROWS + 1]}] if len(rows) > 1 else []
    best = max(["\t", ";", ",", "|"], key=lambda d: min(ln.count(d) for ln in lines[:20]) if all(d in ln for ln in lines[:20]) else -1)
    if not all(best in ln for ln in lines[:5]):
        split = [re.split(r"\s{2,}", ln.strip()) for ln in lines]
        width = len(split[0])
        if width >= 2 and sum(1 for r in split if len(r) == width) >= max(2, len(split) * 0.8):
            return [{"name": name, "headers": split[0], "rows": [r for r in split[1:] if len(r) == width][:MAX_ROWS]}]
        return []
    rows = list(csv.reader(io.StringIO("\n".join(lines)), delimiter=best))
    return [{"name": name, "headers": [h.strip() for h in rows[0]], "rows": [[c.strip() for c in r] for r in rows[1:MAX_ROWS + 1]]}] if len(rows) > 1 else []


def _docx_tables(raw: bytes, name: str) -> list[dict[str, Any]]:
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    out = []
    for n, tbl in enumerate(root.iter(f"{_W}tbl"), start=1):
        rows = [["".join(t.text or "" for t in tc.iter(f"{_W}t")).strip() for tc in tr.iter(f"{_W}tc")] for tr in tbl.iter(f"{_W}tr")]
        rows = [r for r in rows if any(r)]
        if len(rows) > 1:
            out.append({"name": f"{name} table {n}", "headers": rows[0], "rows": rows[1:MAX_ROWS + 1]})
    if not out:
        text = "\n".join("".join(t.text or "" for t in p.iter(f"{_W}t")) for p in root.iter(f"{_W}p"))
        out = _table_from_text(text, name)
    return out


def read_document(filename: str = "", raw: bytes | None = None, text: str | None = None) -> tuple[list[dict[str, Any]], list[str]]:
    """Tables found in a pasted text or an uploaded file. Returns (tables, notes)."""
    if text is not None:
        t = _table_from_text(text, "Pasted text")
        return t, ([] if t else ["No table found in the pasted text. Paste rows with a header line, separated by tabs, commas or semicolons."])
    name = (filename or "file").lower()
    data = raw or b""
    if name.endswith((".csv", ".txt", ".tsv", ".xlsx", ".xlsm")):
        if name.endswith((".txt", ".tsv")):
            return read_document(text=data.decode("utf-8-sig", errors="replace"))
        from app.data_import import parse_tabular

        headers, rows = parse_tabular(data, filename)
        return ([{"name": filename, "headers": headers, "rows": [[str(r.get(h, "") or "") for h in headers] for r in rows[:MAX_ROWS]]}] if headers else [],
                [] if headers else ["The file has no header row."])
    if name.endswith(".docx"):
        t = _docx_tables(data, filename)
        return t, ([] if t else ["No table found in the document."])
    if name.endswith(".pdf") or data[:5] == b"%PDF-":
        from app.ingest.extract_pdf import extract_text_from_pdf

        txt = extract_text_from_pdf(data)
        if not txt.strip():
            return [], ["This PDF has no readable text (it may be a scan). Scans need the document reader set up."]
        t = _table_from_text(txt, filename)
        return t, ([] if t else ["No table found in the PDF text."])
    return [], ["This file type isn't read here. Use CSV, Excel, Word, PDF with text, or paste the rows."]


# ---------------------------------------------------------------- mapping
def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(s or "").lower()).strip()


SKIP_TYPES = {"one2many", "many2many", "binary", "html", "properties", "json", "reference", "many2one_reference"}


def importable(fmeta: dict[str, Any]) -> dict[str, Any]:
    return {f: m for f, m in fmeta.items() if m.get("store", True) and not m.get("readonly") and m.get("type") not in SKIP_TYPES
            and not f.startswith("__") and f not in {"id", "create_uid", "write_uid", "create_date", "write_date"}}


def map_columns(headers: list[str], fmeta: dict[str, Any]) -> tuple[dict[str, str | None], list[dict[str, Any]]]:
    """Code maps each column to a field by label or name. Unclear ones become questions with options."""
    fields = importable(fmeta)
    by_label = {_norm(m.get("string") or f): f for f, m in fields.items()}
    by_name = {_norm(f): f for f in fields}
    mapping: dict[str, str | None] = {}
    questions = []
    used: set[str] = set()
    for h in headers:
        k = _norm(h)
        f = by_label.get(k) or by_name.get(k)
        if not f and " " in str(h).strip():
            # "Product Name", "Customer Email": drop the leading record word and try again.
            rest = _norm(str(h).strip().split(None, 1)[1])
            f = by_label.get(rest) or by_name.get(rest)
        if not f:
            hit = difflib.get_close_matches(k, list(by_label), n=1, cutoff=0.88)
            f = by_label[hit[0]] if hit else None
        if f and f not in used:
            mapping[h] = f
            used.add(f)
        else:
            mapping[h] = None
            opts = difflib.get_close_matches(k, list(by_label), n=3, cutoff=0.4)
            questions.append({"column": h, "question": f"Which field is '{h}'?", "options": [{"field": by_label[o], "label": fields[by_label[o]].get("string") or by_label[o]} for o in opts],
                              "can_skip": True})
    return mapping, questions


def required_missing(mapping: dict[str, str | None], fmeta: dict[str, Any]) -> list[str]:
    have = {f for f in mapping.values() if f}
    return [m.get("string") or f for f, m in fmeta.items() if m.get("required") and not m.get("readonly") and m.get("store", True)
            and m.get("type") in {"char", "text"} and f not in have and not m.get("default")]


def rank_targets(headers: list[str], metas: dict[str, dict[str, Any]], labels: dict[str, str]) -> list[dict[str, Any]]:
    out = []
    for model, fm in metas.items():
        mapping, qs = map_columns(headers, fm)
        hits = sum(1 for v in mapping.values() if v)
        if hits:
            out.append({"model": model, "label": labels.get(model, model), "mapped": hits, "unmapped": len(qs)})
    common = ["res.partner", "product.template", "product.product", "crm.lead", "hr.employee", "product.category", "uom.uom"]
    return sorted(out, key=lambda r: (-r["mapped"], r["unmapped"], common.index(r["model"]) if r["model"] in common else 99, r["label"]))[:5]


# ---------------------------------------------------------------- Odoo's import test and apply
def _csv(fields: list[str], rows: list[list[Any]]) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(fields)
    for r in rows:
        w.writerow(["" if c is None else c for c in r])
    return buf.getvalue().encode()


OPTIONS = {"quoting": '"', "separator": ",", "has_headers": True, "encoding": "utf-8", "date_format": "", "datetime_format": "",
           "float_thousand_separator": ",", "float_decimal_separator": ".", "fields": [], "advanced": False, "keep_matches": False,
           "name_create_enabled_fields": {}, "import_set_empty_fields": [], "import_skip_records": [], "fallback_values": {}, "skip": 0, "limit": MAX_ROWS}


def xmlids(job: str, table: int, n: int) -> list[str]:
    return [f"{XMLID_MODULE}.{job}_{table}_{i + 1}" for i in range(n)]


def _odoo_import(client: Any, model: str, fields: list[str], rows: list[list[Any]], *, dryrun: bool) -> dict[str, Any]:
    raw = _csv(fields, rows)
    major = int(getattr(getattr(client, "capabilities", None), "major", 19) or 19)
    content = base64.b64encode(raw).decode() if major >= 20 else raw.decode()  # up to 19 base_import keeps raw text; 20 wants base64
    wid = _x(client, "base_import.import", "create", [{"res_model": model, "file": content,
                                                       "file_name": "suite_import.csv", "file_type": "text/csv"}])
    args, kw = [[wid], fields, list(fields), OPTIONS], {"dryrun": dryrun}
    if getattr(client, "_rpc_protocol", "") == "xmlrpc":
        # Odoo's import answer contains empty (None) values that XML-RPC can't carry; its JSON-RPC endpoint can.
        from odoo_client.client import _jsonrpc_call

        cfg = client.config
        res = _jsonrpc_call(cfg.url, "object", "execute_kw", [cfg.db, client.uid, cfg.password, "base_import.import", "execute_import", args, kw], timeout=120)
    else:
        res = _x(client, "base_import.import", "execute_import", args, kw)
    return res or {}


def _messages(res: dict[str, Any]) -> list[str]:
    out = []
    for m in res.get("messages") or []:
        if m.get("type") not in {"error", "warning"}:
            continue
        rows = m.get("rows") or {}
        where = f"Row {int(rows.get('from', 0)) + 1}: " if rows else ""
        out.append(f"{where}{str(m.get('message') or '').strip()}")
    return out


def step_rows(inp: dict[str, Any]) -> tuple[list[str], list[list[Any]]]:
    mapping = inp.get("mapping") or {}
    headers = list(inp.get("headers") or [])
    keep = [(i, mapping.get(h)) for i, h in enumerate(headers) if mapping.get(h)]
    fields = [f for _, f in keep]
    rows = [[(r[i] if i < len(r) else "") for i, _ in keep] for r in inp.get("rows") or []]
    return fields, rows


def check_import(client: Any, step: dict[str, Any], fmeta: dict[str, Any]) -> dict[str, Any]:
    inp = step["inputs"]
    model = str(inp["model"])
    unanswered = [h for h, f in (inp.get("mapping") or {}).items() if f is None and h not in set(inp.get("skip") or [])]
    if unanswered:
        return {"verdict": "needs_input", "message": "Say which field these columns are, or skip them: " + ", ".join(unanswered[:6])}
    bad = [f for f in (inp.get("mapping") or {}).values() if f and f not in importable(fmeta)]
    if bad:
        return {"verdict": "blocked", "message": "These can't be imported here: " + ", ".join(bad)}
    fields, rows = step_rows(inp)
    if not rows:
        return {"verdict": "no_change", "message": "No rows to import."}
    miss = required_missing(inp.get("mapping") or {}, fmeta)
    if miss:
        return {"verdict": "needs_input", "message": "Add a column for: " + ", ".join(miss)}
    res = _odoo_import(client, model, ["id", *fields], [[x, *r] for x, r in zip(xmlids(str(inp["job"]), int(inp.get("table") or 1), len(rows)), rows, strict=True)],
                       dryrun=True)
    msgs = _messages(res)
    errs = [m for m in res.get("messages") or [] if m.get("type") == "error"]
    if errs:
        return {"verdict": "needs_input", "message": f"Odoo's import test found {len(errs)} problem(s). " + " ".join(msgs[:3]), "problems": msgs[:20]}
    return {"verdict": "ready", "changes": {"import": len(rows)}, "message": f"Odoo's import test passed for {len(rows)} row(s). Nothing was saved.",
            "notes": msgs[:5]}


def apply_import(client: Any, step: dict[str, Any]) -> dict[str, Any]:
    inp = step["inputs"]
    model = str(inp["model"])
    fields, rows = step_rows(inp)
    ids_ = xmlids(str(inp["job"]), int(inp.get("table") or 1), len(rows))
    test = _odoo_import(client, model, ["id", *fields], [[x, *r] for x, r in zip(ids_, rows, strict=True)], dryrun=True)
    if any(m.get("type") == "error" for m in test.get("messages") or []):
        from app.suite_setup import StepChanged

        raise StepChanged("Odoo's import test fails now: " + " ".join(_messages(test)[:2]))
    res = _odoo_import(client, model, ["id", *fields], [[x, *r] for x, r in zip(ids_, rows, strict=True)], dryrun=False)
    made = [int(i) for i in res.get("ids") or []]
    return {"state": "done", "message": f"Imported {len(made)} {model} record(s).", "undo": {"import": True, "model": model, "xmlids": ids_}}


def resolve_xmlids(client: Any, model: str, names: list[str]) -> list[int]:
    short = [n.split(".", 1)[1] for n in names]
    rows = _x(client, "ir.model.data", "search_read", [[("module", "=", XMLID_MODULE), ("name", "in", short), ("model", "=", model)]], {"fields": ["res_id"]})
    return [int(r["res_id"]) for r in rows]


def remove_imported(client: Any, model: str, names: list[str]) -> dict[str, Any]:
    ids_ = resolve_xmlids(client, model, names)
    ids_ = list(_x(client, model, "search", [[("id", "in", ids_)]], {"context": {"active_test": False}})) if ids_ else []
    if not ids_:
        return {"state": "no_change", "message": "Already gone.", "undo": None}
    removed, archived = 0, 0
    for rid in ids_:
        try:
            _x(client, model, "unlink", [[rid]])
            removed += 1
        except Exception:  # noqa: BLE001  in use: archive instead
            if "active" in _x(client, model, "fields_get", [["active"]], {"attributes": ["type"]}):
                _x(client, model, "write", [[rid], {"active": False}])
                archived += 1
    return {"state": "done", "message": f"Removed {removed} imported record(s)" + (f", archived {archived} in use." if archived else "."), "undo": {"one_way": True}}
