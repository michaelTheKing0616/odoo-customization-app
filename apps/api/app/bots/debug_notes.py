# ruff: noqa: E501 - catalogue prose and verified source strings stay on one line
"""BOT-ODOO-DEBUG-NOTES: known Odoo error signatures, a safe matcher, and a review queue.

Read-only knowledge. ``match`` takes an error/log excerpt (bounded, redacted first) and returns
ranked signature matches with evidence spans, or ``unknown`` with no fix (never a guess).
Every seed signature's ``needles`` are literal source strings verified against the odoo:17-20
images (file per version in ``files``; regenerate with evals/bots/verify_debug_notes.py).
New lessons go to an append-only candidates queue; promotion into the catalogue is a reviewed
code change, never automatic. Callers (code_audit, owned_change, the spine) only get data.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from app.bots import tiers as tt
from app.bots.audit import redact as _audit_redact

VERSIONS = (17, 18, 19, 20)
MAX_INPUT = 256 * 1024  # bytes accepted; only the tail MAX_SCAN is scanned
MAX_SCAN = 64 * 1024
MAX_LINE = 2000
MAX_SPAN = 300
MAX_MATCHES = 5
NOTE_ID_RE = re.compile(r"dn-[0-9a-z][0-9a-z-]{2,59}")
NOTE_FIELDS = frozenset(
    {"id", "title", "sample", "cause", "diagnosis", "fix_tier", "dont", "versions", "source"}
)
NOTES_PATH = Path(__file__).resolve().parents[2] / "evals" / "bots" / "debug_notes_candidates.jsonl"

_EXTRA_SECRETS = (
    re.compile(
        r"(?i)\b(password|passwd|pwd|secret|api[_-]?key|token|admin_passwd)\b(\s{0,3}[=:]\s{0,3})\S{1,200}"
    ),
    re.compile(r"(?i)\bauthorization:\s{0,3}(bearer|basic|token)\s{1,3}\S{1,500}"),
    re.compile(r"(?i)\b([a-z][a-z0-9+.-]{1,20}://)[^\s:/@]{1,100}:[^\s@]{1,200}@"),
    re.compile(r"\b(?:sk|pk|ghp|gho|xox[abp])[-_][A-Za-z0-9_-]{8,200}"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{4,}"),
)
_CTRL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def redact(text: str) -> str:
    text = _EXTRA_SECRETS[0].sub(lambda m: f"{m.group(1)}{m.group(2)}[REDACTED]", text)
    text = _EXTRA_SECRETS[1].sub("Authorization: [REDACTED]", text)
    text = _EXTRA_SECRETS[2].sub(lambda m: f"{m.group(1)}[REDACTED]@", text)
    for p in _EXTRA_SECRETS[3:]:
        text = p.sub("[REDACTED]", text)
    return _audit_redact(text)


@dataclass(frozen=True)
class Signature:
    id: str
    title: str
    pattern: str
    needles: Mapping[int, str]  # version -> literal string present in Odoo source
    files: Mapping[int, str]  # version -> source file containing the needle
    cause: str
    diagnosis: tuple[str, ...]
    fix_tier: int
    fix_kind: str
    dont: tuple[str, ...]

    @property
    def versions(self) -> tuple[int, ...]:
        return tuple(sorted(self.needles))


def _all(needle: str, files: Mapping[int, str] | str) -> tuple[dict[int, str], dict[int, str]]:
    f = files if isinstance(files, Mapping) else {v: files for v in VERSIONS}
    return {v: needle for v in f}, dict(f)


_BASE = "odoo/addons/base/models/"
_M = {
    17: "odoo/models.py",
    18: "odoo/models.py",
    19: "odoo/orm/models.py",
    20: "odoo/orm/models.py",
}
_F = {17: "odoo/fields.py", 18: "odoo/fields.py"}
_REG = {
    17: "odoo/modules/registry.py",
    18: "odoo/modules/registry.py",
    19: "odoo/orm/registry.py",
    20: "odoo/orm/registry.py",
}
_NO_DB = "Do not edit the database by hand (SQL UPDATE/DELETE) to make the error go away."
_NO_UNINSTALL = (
    "Do not uninstall the module to clear the error: uninstalling drops its tables and data."
)
_NO_FORCE = "Do not run module upgrades or installs on production without a backup and a rehearsal."


def _sig(id_, title, pattern, nf, cause, diag, tier, kind, dont):
    needles, files = nf
    return Signature(
        id_, title, pattern, needles, files, cause, tuple(diag), tier, kind, tuple(dont)
    )


CATALOGUE: tuple[Signature, ...] = (
    _sig(
        "xmlid-not-found",
        "External ID not found",
        r"External ID not found in the system: ([\w.]{1,200})",
        _all("External ID not found in the system", _BASE + "ir_model.py"),
        "Code or data references an XML id that does not exist (module not installed, typo, or record removed in this version).",
        [
            "Read the XML id in the message.",
            "Check the owning module is installed and the id exists in ir.model.data.",
            "Check the id still exists in this Odoo version.",
        ],
        tt.T3,
        "fix the reference in module code/data",
        [_NO_DB, "Do not create a placeholder record with that XML id by hand."],
    ),
    _sig(
        "singleton",
        "Expected singleton",
        r"Expected singleton: ([\w.]{1,128})\(",
        ({v: "Expected singleton: " for v in VERSIONS}, _M),
        "A method that needs exactly one record was called on a recordset with zero or several records.",
        [
            "Find the frame in the traceback that accesses a field or calls ensure_one().",
            "Check how the recordset was built (search without limit, multi-record action).",
        ],
        tt.T3,
        "loop over records or ensure_one() in module code",
        ["Do not add limit=1 blindly: it hides which record is wrong."],
    ),
    _sig(
        "xpath-not-located",
        "View inheritance target not found",
        r"Element .{1,300}? cannot be located in parent view",
        _all("cannot be located in parent view", "odoo/tools/template_inheritance.py"),
        "An inherited view's xpath/field locator does not match the parent view (parent changed across versions or another module altered it).",
        [
            "Read the locator in the message.",
            "Open the parent view's combined arch for this version and search for the target.",
            "Check view priority/order of inheriting modules.",
        ],
        tt.T2,
        "fix the inheriting view's locator",
        ["Do not delete or deactivate the parent view.", "Do not edit stock views in place."],
    ),
    _sig(
        "invalid-field",
        "Invalid field on model",
        r"Invalid field '([\w.]{1,128})' on model '([\w.]{1,128})'",
        _all("Invalid field %r on model %r", _M),
        "Code writes or reads a field that is not defined on the model (renamed/removed in this version, or module not loaded).",
        [
            "Check the field exists for this version (versioncaps).",
            "Check the module defining it is installed and in depends.",
        ],
        tt.T3,
        "rename/remove the field use in module code",
        [_NO_DB],
    ),
    _sig(
        "view-field-missing",
        "View uses a field missing on the model",
        r'Field "(\w{1,128})" does not exist in model "([\w.]{1,128})"',
        _all(
            'Field "%(field_name)s" does not exist in model "%(model_name)s"',
            _BASE + "ir_ui_view.py",
        ),
        "A view arch references a field the model does not have in this version.",
        [
            "Read field and model from the message.",
            "Check the field in this version's model (versioncaps).",
            "Check the module adding the field is in depends.",
        ],
        tt.T2,
        "fix the view arch",
        ["Do not add a dummy field just to satisfy the view."],
    ),
    _sig(
        "missing-record",
        "Record does not exist or has been deleted",
        r"Record does not exist or has been deleted\.",
        (
            {v: "Record does not exist or has been deleted." for v in VERSIONS},
            {
                17: "odoo/fields.py",
                18: "odoo/fields.py",
                19: "odoo/orm/fields.py",
                20: "odoo/orm/fields.py",
            },
        ),
        "Code read a record id that was deleted or is not visible to the user (record rules).",
        [
            "Check whether the id exists with sudo in a read-only shell.",
            "Check record rules/company for the user.",
        ],
        tt.T1,
        "fix the stale reference (data) or the access setup",
        [_NO_DB, "Do not recreate the record with the same id."],
    ),
    _sig(
        "module-load-failed",
        "Couldn't load module",
        r"Couldn't load module (\w{1,128})",
        _all("Couldn't load module", "odoo/modules/module.py"),
        "Importing the module's Python package raised (syntax error, missing Python dependency, bad import).",
        [
            "Read the traceback just above this line.",
            "Check external_dependencies in the manifest are installed.",
        ],
        tt.T3,
        "fix module Python code or its dependencies",
        [_NO_UNINSTALL, _NO_FORCE],
    ),
    _sig(
        "modules-not-loaded",
        "Modules not loaded (dependencies/manifest)",
        r"Some modules are not loaded, some dependencies or manifest may be missing",
        _all(
            "Some modules are not loaded, some dependencies or manifest may be missing",
            "odoo/modules/loading.py",
        ),
        "Modules marked installed are missing from the addons path or their dependencies are missing.",
        [
            "List the module names in the message.",
            "Check the addons path contains them for this version.",
        ],
        tt.T3,
        "restore the addons path / module source",
        [_NO_UNINSTALL, _NO_DB],
    ),
    _sig(
        "modules-inconsistent",
        "Modules in inconsistent states",
        r"Some modules have inconsistent states, some dependencies may be missing",
        _all("Some modules have inconsistent states", "odoo/modules/loading.py"),
        "Modules are stuck in to install/to upgrade/to remove states after an interrupted operation.",
        [
            "List the modules and their state (read-only query on ir_module_module).",
            "Find which operation was interrupted.",
        ],
        tt.T3,
        "finish or cancel the pending module operation via a reviewed upgrade",
        [_NO_DB, _NO_FORCE],
    ),
    _sig(
        "registry-load-failed",
        "Failed to load registry",
        r"Failed to load registry",
        _all("Failed to load registry", _REG),
        "The database registry could not be built; a module raised during load.",
        [
            "Read the first traceback before this line; it names the failing module.",
            "Match that traceback against this catalogue.",
        ],
        tt.T3,
        "fix the failing module found in the traceback",
        [_NO_UNINSTALL, _NO_DB],
    ),
    _sig(
        "smtp-failed",
        "Mail delivery failed via SMTP server",
        r"Mail delivery failed via SMTP server '([^'\n]{1,200})'",
        _all("Mail delivery failed via SMTP server", _BASE + "ir_mail_server.py"),
        "The outgoing mail server rejected or could not be reached (auth, TLS, host, port, sender).",
        [
            "Read the exception name and message after the server name.",
            "Use the mail server's Test Connection button.",
        ],
        tt.T1,
        "correct the outgoing mail server settings",
        [
            "Do not paste mail server passwords into notes or tickets.",
            "Do not delete queued mails to clear the error.",
        ],
    ),
    _sig(
        "wrong-value",
        "Wrong value for field",
        r"Wrong value for ([\w.]{1,200}): ",
        (
            {v: "Wrong value for %s: %r" for v in VERSIONS},
            {**_F, 19: "odoo/orm/fields_selection.py", 20: "odoo/orm/fields_selection.py"},
        ),
        "A value outside the field's allowed values (selection key, wrong record type) was assigned.",
        ["Read field and value.", "Compare with the selection keys for this version."],
        tt.T3,
        "fix the assigned value in code or data",
        [_NO_DB],
    ),
    _sig(
        "recursion",
        "Recursion detected",
        r"Recursion Detected\.",
        ({v: "Recursion Detected." for v in (17, 18, 19)}, {v: _M[v] for v in (17, 18, 19)}),
        "A parent/child hierarchy would loop (record set as its own ancestor).",
        ["Identify the record and its parent chain."],
        tt.T1,
        "fix the parent assignment in data",
        [_NO_DB],
    ),
    _sig(
        "import-no-match",
        "Import: no matching record",
        r"No matching record found for ",
        _all("No matching record found for", _BASE + "ir_fields.py"),
        "An imported relation value does not match any existing record by name/XML id.",
        [
            "Read the value and field.",
            "Check the target record exists and the column uses the right identifier.",
        ],
        tt.T1,
        "fix the import file or create the target records first",
        ["Do not enable 'create if not found' without review: it creates duplicates."],
    ),
    _sig(
        "unknown-currency-field",
        "Monetary field with unknown currency_field",
        r"Field ([\w.]{1,200}) with unknown currency_field ",
        _all(
            "with unknown currency_field",
            {**_F, 19: "odoo/orm/fields_numeric.py", 20: "odoo/orm/fields_numeric.py"},
        ),
        "A monetary field's currency_field names a field that does not exist on the model.",
        ["Read the field; check the model defines the currency many2one it names."],
        tt.T3,
        "add the currency many2one or fix currency_field in module code",
        [_NO_UNINSTALL],
    ),
    _sig(
        "unknown-comodel",
        "Relational field with unknown comodel",
        r"with unknown comodel_name ",
        _all(
            "unknown comodel_name",
            {**_F, 19: "odoo/orm/fields_relational.py", 20: "odoo/orm/fields_relational.py"},
        ),
        "A relational field points to a model that is not loaded (missing depends or removed model).",
        [
            "Find which module defines the comodel in this version.",
            "Check it is in the manifest depends.",
        ],
        tt.T3,
        "add the dependency or fix the comodel in module code",
        [_NO_UNINSTALL],
    ),
    _sig(
        "access-denied",
        "Access error on records",
        r"You are not allowed to access '([^'\n]{1,128})' \(([\w.]{1,128})\) records",
        _all(
            "You are not allowed to access '%(document_kind)s' (%(document_model)s) records.",
            {
                17: _BASE + "ir_model.py",
                18: _BASE + "ir_model.py",
                19: _BASE + "ir_model.py",
                20: _BASE + "ir_access.py",
            },
        ),
        "The user's groups have no access right for that model/operation.",
        ["Read the model and operation.", "List the user's groups and the model's access rights."],
        tt.T1,
        "grant the right group to the user or add an access right",
        [
            "Do not make the user an administrator to clear it.",
            "Do not run the code with sudo() to bypass access.",
        ],
    ),
    _sig(
        "cron-running",
        "Scheduled action is running",
        r"Record cannot be modified right now",
        _all("Record cannot be modified right now", _BASE + "ir_cron.py"),
        "A scheduled action record is locked because the job is executing.",
        ["Check when the job finishes; retry after."],
        tt.T1,
        "wait and retry the settings change",
        ["Do not kill database sessions or restart workers to break the lock."],
    ),
    _sig(
        "missing-required",
        "Missing required value",
        r"Missing required value for the field '([^'\n]{1,128})'",
        (
            {v: "Missing required value for the field" for v in (17, 18, 19)},
            {v: _M[v] for v in (17, 18, 19)},
        ),
        "A required column was left empty on create/write (NOT NULL violation).",
        ["Read the field.", "Check the default and the code path creating the record."],
        tt.T1,
        "provide the value (data) or a default (T3 if code)",
        [_NO_DB, "Do not drop the required flag to accept bad data."],
    ),
    _sig(
        "composed-field",
        "Invalid composed field in view",
        r"Invalid composed field (\S{1,200}) in ",
        _all("Invalid composed field %(definition)s in %(use)s", _BASE + "ir_ui_view.py"),
        "A view uses a dotted path (a.b.c) that does not resolve in this version.",
        ["Resolve each hop of the path against versioncaps."],
        tt.T2,
        "fix the view expression",
        ["Do not edit stock views in place."],
    ),
    _sig(
        "field-in-views",
        "Cannot delete a field still used in views",
        r"Cannot rename/delete fields that are still present in views",
        _all("Cannot rename/delete fields that are still present in views", _BASE + "ir_model.py"),
        "A field removal/rename (often during upgrade) is blocked by views still using it.",
        ["Read the field and view names.", "Remove the field from those views first."],
        tt.T2,
        "update the views, then remove the field",
        [_NO_DB, _NO_FORCE],
    ),
    _sig(
        "template-render-failed",
        "Mail template failed to render",
        r"Failed to render template",
        _all("Failed to render template", "odoo/addons/mail/models/mail_render_mixin.py"),
        "A mail/QWeb template raised while rendering (missing field, bad expression).",
        [
            "Read the template reference and the inner error.",
            "Preview the template on a sample record.",
        ],
        tt.T2,
        "fix the template expression",
        ["Do not delete the template; reset it to the module version instead."],
    ),
    _sig(
        "qweb-render-error",
        "QWeb rendering error",
        r"Error while render(?:ing)? the template",
        (
            {
                17: "Error while render the template",
                18: "Error while render the template",
                19: "Error while rendering the template",
                20: "Error while rendering the template",
            },
            {v: _BASE + "ir_qweb.py" for v in VERSIONS},
        ),
        "A QWeb template expression raised (missing field/variable, None access).",
        ["Read the inner error and template name in the traceback."],
        tt.T2,
        "fix the template",
        ["Do not switch t-out to t-raw to silence escaping errors."],
    ),
    _sig(
        "invalid-view-definition",
        "Invalid view definition",
        r"Invalid view (.{1,200}?) definition in (\S{1,300})",
        _all("Invalid view %(name)s definition in %(file)s", _BASE + "ir_ui_view.py"),
        "A view in a module data file failed validation during install/upgrade.",
        ["Read the view name and file.", "Read the validation error beneath it."],
        tt.T2,
        "fix the view in the module data",
        [_NO_FORCE],
    ),
    _sig(
        "view-validation",
        "Error while validating view",
        r"Error while validating view",
        _all("Error while validating view", _BASE + "ir_ui_view.py"),
        "A view arch failed validation (unknown field, bad attribute, invalid structure).",
        ["Read the detail lines that follow."],
        tt.T2,
        "fix the view arch",
        ["Do not deactivate the view to bypass validation."],
    ),
    _sig(
        "fk-delete-blocked",
        "Delete blocked by another model",
        r"another model requires the record being deleted",
        (
            {v: "another model requires the record being deleted" for v in (17, 18, 19)},
            {17: "odoo/service/model.py", 18: "odoo/service/model.py", 19: "odoo/orm/models.py"},
        ),
        "A foreign key from another table references the record being deleted.",
        ["Find which model references the record.", "Archive instead of deleting if supported."],
        tt.T1,
        "archive the record or reassign the references",
        [_NO_DB, "Do not cascade-delete the referencing records."],
    ),
    _sig(
        "mandatory-not-set",
        "Mandatory field not set",
        r"a mandatory field is not set",
        (
            {v: "a mandatory field is not set" for v in (17, 18, 19)},
            {17: "odoo/service/model.py", 18: "odoo/service/model.py", 19: "odoo/orm/models.py"},
        ),
        "Create/update hit a NOT NULL constraint.",
        ["Find which field is empty in the request."],
        tt.T1,
        "provide the value",
        [_NO_DB],
    ),
    _sig(
        "invalid-leaf",
        "Invalid domain leaf",
        r"Invalid leaf ",
        (
            {v: "Invalid leaf" for v in (17, 18, 19)},
            {v: "odoo/osv/expression.py" for v in (17, 18, 19)},
        ),
        "A domain contains a malformed term.",
        ["Print the domain; check each term is (field, operator, value)."],
        tt.T2,
        "fix the domain in the action/rule/filter",
        ["Do not replace the domain with [] (it opens all records)."],
    ),
    _sig(
        "invalid-operator",
        "Invalid domain operator",
        r"Invalid operator",
        (
            {v: "Invalid operator" for v in VERSIONS},
            {
                17: "odoo/osv/expression.py",
                18: "odoo/models.py",
                19: "odoo/orm/domains.py",
                20: "odoo/orm/domains.py",
            },
        ),
        "A domain uses an operator not supported in this version.",
        ["Read the term; compare with this version's supported operators."],
        tt.T2,
        "fix the domain operator",
        ["Do not replace the domain with [] (it opens all records)."],
    ),
    _sig(
        "cron-action-failed",
        "Scheduled action failed",
        r"(?:Call from cron .{1,200}? for server action #\d{1,10} failed|Job .{1,200}? server action #\d{1,10} failed)",
        (
            {
                17: "Call from cron %s for server action #%s failed",
                **{v: "server action #%s failed" for v in (18, 19, 20)},
            },
            {v: _BASE + "ir_cron.py" for v in VERSIONS},
        ),
        "The server action run by a scheduled job raised.",
        ["Read the traceback after the line.", "Match that traceback against this catalogue."],
        tt.T2,
        "fix the server action (T3 if its code lives in a module)",
        ["Do not deactivate the job permanently without telling the owner."],
    ),
)

_COMPILED = {s.id: re.compile(s.pattern) for s in CATALOGUE}
_NESTED = re.compile(r"\([^()]*[+*][^()]*\)[+*{]")
assert not any(_NESTED.search(s.pattern) for s in CATALOGUE), "nested quantifier"
assert len({s.id for s in CATALOGUE}) == len(CATALOGUE)


@dataclass
class Match:
    id: str
    title: str
    score: int
    evidence: list[dict[str, Any]]
    cause: str
    diagnosis: tuple[str, ...]
    fix_tier: int
    fix_tier_ready: bool
    fix_kind: str
    dont: tuple[str, ...]
    source_files: dict[int, str]


@dataclass
class Result:
    status: str  # "matched" | "unknown" | "invalid"
    version: int | None
    matches: list[Match] = field(default_factory=list)
    truncated: bool = False
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _prepare(text: Any) -> tuple[list[str], bool]:
    if isinstance(text, (bytes, bytearray)):
        if len(text) > MAX_INPUT:
            raise ValueError("input too large")
        text = bytes(text).decode("utf-8", errors="replace")
    if not isinstance(text, str):
        raise ValueError("input must be text")
    if len(text) > MAX_INPUT:
        raise ValueError("input too large")
    truncated = len(text) > MAX_SCAN
    text = _CTRL.sub(" ", text[-MAX_SCAN:])
    return [ln[:MAX_LINE] for ln in text.split("\n")], truncated


def match(text: Any, *, version: Any = None) -> Result:
    """Rank catalogue signatures against ``text``. Never raises; never invents a fix."""
    if version is not None and (type(version) is not int or version not in VERSIONS):
        return Result("invalid", None, error=f"version must be one of {VERSIONS} or None")
    try:
        lines, truncated = _prepare(text)
    except ValueError as e:
        return Result("invalid", version, error=str(e))
    found: list[Match] = []
    for sig in CATALOGUE:
        if version is not None and version not in sig.needles:
            continue
        rx = _COMPILED[sig.id]
        ev = []
        for i, ln in enumerate(lines, 1):
            m = rx.search(ln)
            if m:
                lo = max(0, m.start() - 40)
                ev.append({"line": i, "span": redact(ln[lo : m.end() + 40])[:MAX_SPAN]})
                if len(ev) >= 3:
                    break
        if ev:
            # Later lines in a traceback are closer to the real error; literal length = specificity.
            score = (
                10 * len(ev) + ev[-1]["line"] * 100 // max(len(lines), 1) + len(sig.pattern) // 10
            )
            found.append(
                Match(
                    sig.id,
                    sig.title,
                    score,
                    ev,
                    sig.cause,
                    sig.diagnosis,
                    sig.fix_tier,
                    tt.tier_ready(sig.fix_tier),
                    sig.fix_kind,
                    sig.dont,
                    dict(sig.files),
                )
            )
    found.sort(key=lambda m: (-m.score, m.id))
    if not found:
        return Result("unknown", version, truncated=truncated)
    return Result("matched", version, found[:MAX_MATCHES], truncated)


# ---------------------------------------------------------------- candidates queue


def _read(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def _str(v: Any, n: int) -> bool:
    return isinstance(v, str) and 0 < len(v) <= n


def check_note(note: Any) -> dict[str, Any]:
    if not isinstance(note, dict) or set(note) - NOTE_FIELDS:
        raise ValueError(f"note fields must be a subset of {sorted(NOTE_FIELDS)}")
    if not isinstance(note.get("id"), str) or not NOTE_ID_RE.fullmatch(note["id"]):
        raise ValueError("note id must match dn-<lowercase-slug>")
    for k, n in (("title", 120), ("sample", 4000), ("cause", 1000), ("source", 200)):
        if not _str(note.get(k), n):
            raise ValueError(f"{k} must be text, 1-{n} characters")
    for k in ("diagnosis", "dont"):
        v = note.get(k, [])
        if not isinstance(v, list) or len(v) > 10 or not all(_str(x, 300) for x in v):
            raise ValueError(f"{k} must be a list of up to 10 short texts")
    if (
        note.get("fix_tier") not in (None, tt.T1, tt.T2, tt.T3)
        or type(note.get("fix_tier", 1)) is not int
    ):
        raise ValueError("fix_tier must be 1, 2 or 3")
    vs = note.get("versions", [])
    if not isinstance(vs, list) or not all(type(v) is int and v in VERSIONS for v in vs):
        raise ValueError(f"versions must be a list of {VERSIONS}")
    clean = {
        k: (
            redact(v)
            if isinstance(v, str)
            else [redact(x) for x in v]
            if isinstance(v, list) and k != "versions"
            else v
        )
        for k, v in note.items()
    }
    clean["id"] = note["id"]
    return clean


def append_note(note: Any, *, path: Path = NOTES_PATH) -> dict[str, Any]:
    """Append-only: queue a new lesson for review. Never enters CATALOGUE by itself."""
    clean = check_note(note)
    rows = _read(path)
    digest = hashlib.sha256(clean["sample"].encode()).hexdigest()
    if any(r["note"]["id"] == clean["id"] for r in rows):
        raise ValueError(f"duplicate note id {clean['id']}")
    if any(r["sample_sha"] == digest for r in rows):
        raise ValueError("duplicate sample")
    if clean["id"].removeprefix("dn-") in {s.id for s in CATALOGUE}:
        raise ValueError("id collides with a catalogue signature")
    rec = {"note": clean, "sample_sha": digest, "status": "candidate"}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, sort_keys=True) + "\n")
    return rec


def list_notes(*, path: Path = NOTES_PATH) -> list[dict[str, Any]]:
    return _read(path)


def promotion_draft(
    note_id: str,
    *,
    reviewer: str,
    needle: str,
    file_by_version: Mapping[int, str],
    path: Path = NOTES_PATH,
) -> dict[str, Any]:
    """Draft a catalogue entry for a human-reviewed code change. Writes nothing."""
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise PermissionError("promotion needs a named reviewer")
    if not _str(needle, 300) or not file_by_version or set(file_by_version) - set(VERSIONS):
        raise ValueError("needle and source file per verified version are required")
    recs = [r for r in _read(path) if r["note"]["id"] == note_id]
    if len(recs) != 1:
        raise KeyError(f"{note_id}: {len(recs)} notes match, need exactly 1")
    n = recs[0]["note"]
    return {
        "id": note_id.removeprefix("dn-"),
        "title": n["title"],
        "pattern": re.escape(needle),
        "needles": {v: needle for v in file_by_version},
        "files": dict(file_by_version),
        "cause": n["cause"],
        "diagnosis": n.get("diagnosis", []),
        "fix_tier": n.get("fix_tier"),
        "dont": n.get("dont", []),
        "reviewed_by": reviewer.strip(),
    }
