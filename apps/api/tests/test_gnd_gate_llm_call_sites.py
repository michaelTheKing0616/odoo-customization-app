"""GND-GATE — every LLM call site under ``apps/api/app`` is on the allowlist.

The scan is AST-only: no import of the scanned modules, no live LLM. A call site is a
call to ``generate_json`` / ``generate_text`` / gateway ``complete`` (method or bare name),
or to a transport wrapper that forwards to them. Wrapper names come from allowlist entries
classified ``wrapper``, so the callers of a wrapper must be listed too.

Adding, moving, or renaming a call site means updating ``ALLOWLIST`` in the same change.
Do not classify a site that names Odoo structure without the live packet as grounded:
use ``ungrounded`` and say what is missing.
"""

from __future__ import annotations

import ast
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import pytest

API_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = API_ROOT / "app"
TESTS_ROOT = API_ROOT / "tests"

BASE_ENTRY_NAMES = frozenset({"generate_json", "generate_text", "complete"})

# The model sees a live slice (or the version table) before it answers, and output
# outside the slice is dropped. Each needs a source marker and an evidence test.
GROUNDED_CLASSES = {
    "live_packet": re.compile(r"schema_packet"),
    "version_table": re.compile(r"\bversion_table\b"),
    "refuses_invent": re.compile(r"No regions were invented"),
}
# live_packet must show the packet inside the enclosing top-level function, not just
# somewhere in the module.
FUNCTION_SCOPED_CLASSES = frozenset({"live_packet"})
# Output cannot introduce Odoo structure: a caller-supplied closed set, a filter over
# findings already read from the instance, or text that is not about Odoo structure.
NON_NAMING_CLASSES = frozenset({"closed_choice", "no_odoo_structure"})
# Can name Odoo structure without the live packet in the prompt. Known debt, listed
# here so it cannot grow silently.
DEBT_CLASSES = frozenset({"ungrounded"})
# Provider plumbing: the provider's own delegation, or a transport wrapper.
PLUMBING_CLASSES = frozenset({"provider_internal", "wrapper"})
ALL_CLASSES = frozenset(GROUNDED_CLASSES) | NON_NAMING_CLASSES | DEBT_CLASSES | PLUMBING_CLASSES


@dataclass(frozen=True)
class Site:
    path: str  # relative to apps/api/app, posix
    qualname: str  # enclosing Class.func, or <module>
    callee: str  # generate_json | generate_text | complete | <wrapper name>
    count: int = 1


@dataclass(frozen=True)
class Entry:
    site: Site
    classification: str
    card: str
    reason: str
    evidence_test: str = ""


def _e(
    path: str,
    qualname: str,
    callee: str,
    classification: str,
    card: str,
    reason: str,
    *,
    count: int = 1,
    evidence_test: str = "",
) -> Entry:
    return Entry(Site(path, qualname, callee, count), classification, card, reason, evidence_test)


ALLOWLIST: tuple[Entry, ...] = (
    # --- GND-GEN: Draft Studio understand / intent / refine -------------------------
    _e(
        "ai_conversation/intent_llm.py",
        "maybe_llm_refine_assessment",
        "generate_json",
        "live_packet",
        "GND-GEN",
        "packet prepended; host_model outside the packet discarded",
        evidence_test="test_gnd_gen_live_schema.py",
    ),
    _e(
        "ai_conversation/understand.py",
        "_llm_enrich._call",
        "generate_json",
        "live_packet",
        "GND-GEN",
        "packet in prompt; admit_host_from_packet after",
        evidence_test="test_gnd_gen_live_schema.py",
    ),
    _e(
        "ai_conversation/refine.py",
        "llm_propose_ops",
        "generate_json",
        "live_packet",
        "GND-GEN",
        "packet prepended; model/field outside the packet refused",
        evidence_test="test_gnd_gen_live_schema.py",
    ),
    # --- GND-EXPERT ---------------------------------------------------------------------
    _e(
        "expert/ask.py",
        "ask_expert._generate",
        "generate_json",
        "live_packet",
        "GND-EXPERT",
        "answer cites the packet; second read before decline",
        evidence_test="test_gnd_expert_live_schema.py",
    ),
    # --- GND-AUTO -----------------------------------------------------------------------
    _e(
        "job_autopilot/planner.py",
        "_enrich_with_llm",
        "generate_json",
        "live_packet",
        "GND-AUTO",
        "planner output outside the packet dropped before apply",
        evidence_test="test_gnd_auto_live_schema.py",
    ),
    _e(
        "ingest/classify.py",
        "classify_with_llm",
        "generate_json",
        "live_packet",
        "GND-AUTO",
        "packet prepended; models/methods outside it dropped",
        evidence_test="test_gnd_auto_live_schema.py",
    ),
    _e(
        "ai_workflow.py",
        "_llm_workflow_sample",
        "generate_json",
        "live_packet",
        "GND-AUTO",
        "packet prepended; models/methods outside it dropped",
        evidence_test="test_gnd_auto_live_schema.py",
    ),
    # --- GND-DEMO (no connection by design) --------------------------------------------
    _e(
        "live_demo_copilot/stage2_answer.py",
        "propose_demo_verdict",
        "generate_json",
        "version_table",
        "GND-DEMO",
        "verdict checked against the version table",
        evidence_test="test_gnd_demo.py",
    ),
    # --- Wireframe vision: must keep refusing to invent regions ------------------------
    _e(
        "wireframe_live.py",
        "read_uploaded_photo",
        "generate_json",
        "refuses_invent",
        "GND-GATE",
        "unreadable sketch returns no regions",
        evidence_test="test_wireframe_live_vision.py",
    ),
    # --- GND-STUDIO: App Studio stock-first design (app_design.py) -----------------------
    _e(
        "ai_conversation/app_design.py",
        "_call_intent_contract",
        "generate_json",
        "live_packet",
        "GND-STUDIO",
        "schema_packet + live snapshot digest in prompt; targets bound to known models, "
        "capability policy demotes lanes the snapshot cannot run",
        evidence_test="test_gnd_studio_live_schema.py",
    ),
    _e(
        "ai_conversation/app_design.py",
        "build_app_design",
        "_call_llm",
        "live_packet",
        "GND-STUDIO",
        "design + repair pass: schema_packet + snapshot digest in prompt; validate_and_repair "
        "drops names the snapshot does not have",
        count=2,
        evidence_test="test_gnd_studio_live_schema.py",
    ),
    _e(
        "ai_conversation/app_design.py",
        "_call_llm",
        "generate_json",
        "wrapper",
        "LLM",
        "timeout / status metadata transport; app callers of _call_llm must list",
    ),
    # --- Cannot introduce Odoo structure ------------------------------------------------
    _e(
        "ai_overlap.py",
        "default_semantic_filter",
        "generate_text",
        "closed_choice",
        "AI-9",
        "keeps or drops findings already scanned from the instance",
    ),
    _e(
        "ai_self_consistency.py",
        "llm_vote_domain_pack",
        "generate_json",
        "closed_choice",
        "AI-3",
        "pack_id validated against the caller's pack_ids",
    ),
    _e(
        "ai_self_consistency.py",
        "llm_merge_workflow_states_for_model",
        "generate_json",
        "no_odoo_structure",
        "AI-3",
        "emits selection values for the draft's own x_status only",
    ),
    _e(
        "ai_pack_generalizer.py",
        "_llm_suggest_tags_and_antipatterns",
        "generate_json",
        "no_odoo_structure",
        "AI-6",
        "tags/anti-patterns for a download-only pack candidate",
    ),
    _e(
        "ingest/extract_pdf.py",
        "_llm_extract",
        "generate_json",
        "no_odoo_structure",
        "ING-4",
        "document rows into a fixed JSON schema; no model/field names",
    ),
    _e(
        "ai_conversation/app_design.py",
        "_call_verifier",
        "generate_json",
        "closed_choice",
        "GND-STUDIO",
        "supports|not_supported|unclear per caller-supplied requirement id; downgrade-only",
    ),
    _e(
        "ai_conversation/app_design.py",
        "build_app_design._design_call",
        "_call_llm",
        "live_packet",
        "GND-STUDIO",
        "design call run in parallel with the contract verifier: same prompt as build_app_design "
        "(schema_packet + snapshot digest); validate_and_repair rebuilds from the final contract",
        evidence_test="test_gnd_studio_live_schema.py",
    ),
    _e(
        "ai_conversation/app_design.py",
        "checklist_only",
        "generate_json",
        "no_odoo_structure",
        "GND-STUDIO",
        "brief parts + status + verbatim quote (INGENIUM_BRIEF_CHECKLIST, non-design routes); no model/field names",
    ),
    _e(
        "ai_conversation/app_design.py",
        "_call_second_look",
        "generate_json",
        "closed_choice",
        "GND-STUDIO",
        "yes|no|unsure per caller-supplied checklist id (INGENIUM_BRIEF_CHECKLIST); can only keep items in",
    ),
    _e(
        "ai_conversation/app_design.py",
        "_call_conflict_look",
        "generate_json",
        "closed_choice",
        "GND-STUDIO",
        "conflict pairs among caller-supplied quoted row ids (INGENIUM_BRIEF_CHECKLIST); code authorizes",
    ),
    _e(
        "ai_conversation/app_design.py",
        "_call_intent_contract._classify",
        "generate_json",
        "closed_choice",
        "GND-STUDIO",
        "labels caller-numbered clauses from a closed enum (INGENIUM_CLAUSE_GROUNDING); no model/field names",
    ),
    _e(
        "ai_conversation/app_design.py",
        "_call_critic",
        "generate_json",
        "no_odoo_structure",
        "GND-STUDIO",
        "flags only; findings need a source span and never edit the design",
    ),
    _e(
        "ai_conversation/app_design.py",
        "_llm_support",
        "_call_llm",
        "no_odoo_structure",
        "GND-STUDIO",
        "closed kinds; relational fields dropped, so no stock model/field can be named",
    ),
    _e(
        "ai_conversation/brief_expand.py",
        "_expand",
        "generate_json",
        "no_odoo_structure",
        "GND-STUDIO",
        "plain-language brief text that re-enters the grounded understand pipeline",
    ),
    # --- GND-G-PIPE: Draft pipeline calls read the packet --------------------------------
    _e(
        "ai_pipeline.py",
        "_llm_json",
        "llm_json_with_budget",
        "live_packet",
        "GND-G-PIPE",
        "schema_packet in prompt + filter; staged pipeline draft JSON",
        evidence_test="test_gnd_g_pipe_live_schema.py",
    ),
    _e(
        "ai_depth.py",
        "llm_expand_depth",
        "llm_json_with_budget",
        "live_packet",
        "GND-G-PIPE",
        "schema_packet in prompt + filter; depth expand pass",
        evidence_test="test_gnd_g_pipe_live_schema.py",
    ),
    _e(
        "ai_critique.py",
        "llm_critique",
        "llm_json_with_budget",
        "live_packet",
        "GND-G-PIPE",
        "schema_packet in prompt + filter; critique of draft",
        evidence_test="test_gnd_g_pipe_live_schema.py",
    ),
    _e(
        "ai_model_quality.py",
        "llm_deepen_model_fields",
        "llm_json_with_budget",
        "live_packet",
        "GND-G-PIPE",
        "schema_packet in prompt + filter; field deepen pass",
        evidence_test="test_gnd_g_pipe_live_schema.py",
    ),
    _e(
        "ai_model_quality.py",
        "llm_emit_missing_scaffold_models",
        "llm_json_with_budget",
        "live_packet",
        "GND-G-PIPE",
        "schema_packet in prompt + filter; scaffold gap emit",
        evidence_test="test_gnd_g_pipe_live_schema.py",
    ),
    _e(
        "ai_domain_briefing.py",
        "_enrich_briefing_with_llm",
        "llm_json_with_budget",
        "live_packet",
        "GND-G-PIPE",
        "schema_packet in prompt + filter; domain briefing enrich",
        evidence_test="test_gnd_g_pipe_live_schema.py",
    ),
    _e(
        "ai_ollama.py",
        "draft_module_from_prompt",
        "generate_json_with_timeout_retry",
        "live_packet",
        "GND-G-PIPE",
        "schema_packet in prompt + filter; single-pass ModuleSpec",
        evidence_test="test_gnd_g_pipe_live_schema.py",
    ),
    _e(
        "ai_ollama.py",
        "call_ollama_generate",
        "generate_json",
        "live_packet",
        "GND-G-PIPE",
        "schema_packet in prompt + filter; legacy ModuleSpec wrapper (grounded, not deleted)",
        evidence_test="test_gnd_g_pipe_live_schema.py",
    ),
    _e(
        "ai_option_a_author.py",
        "_default_generate_blocks._call",
        "generate_json_with_timeout_retry",
        "live_packet",
        "GND-G-OPTA",
        "schema_packet slice for host model(s) in prompt; static refuse missing field/xpath before zip",
        evidence_test="test_gnd_opta_live_schema.py",
    ),
    _e(
        "ai_option_a_feedback.py",
        "_default_repair_blocks._call",
        "generate_json_with_timeout_retry",
        "live_packet",
        "GND-G-OPTA",
        "schema_packet slice in repair prompt; static refuse missing field/xpath before zip",
        evidence_test="test_gnd_opta_live_schema.py",
    ),
    # --- GND-G-MAP / GND-G-TEXT ---------------------------------------------------------
    _e(
        "ingest/map_columns.py",
        "_llm_map_columns",
        "generate_json",
        "live_packet",
        "GND-G-MAP",
        "packet prepended; mapping to a field outside it left unmapped with a reason",
        evidence_test="test_gnd_g_map_live_schema.py",
    ),
    _e(
        "expert/narrative.py",
        "generate_finding_narratives",
        "generate_json",
        "live_packet",
        "GND-G-TEXT",
        "packet prepended; paragraph naming structure outside packet/finding -> fallback",
        evidence_test="test_gnd_g_text_live_schema.py",
    ),
    _e(
        "routers/ai_studio.py",
        "refine_session_route",
        "generate_text",
        "live_packet",
        "GND-G-TEXT",
        "packet prepended; reply naming structure outside packet/patch -> patch summary",
        evidence_test="test_gnd_g_text_live_schema.py",
    ),
    # --- Provider plumbing ----------------------------------------------------------------
    _e(
        "llm_provider.py",
        "LLMProvider.generate_text",
        "generate_json",
        "provider_internal",
        "LLM",
        "base generate_text delegates to generate_json",
    ),
    _e(
        "llm_provider.py",
        "generate_json_with_timeout_retry._call",
        "generate_json",
        "wrapper",
        "LLM",
        "timeout retry / fallback transport",
    ),
    _e(
        "ai_llm_budget.py",
        "llm_json_with_budget",
        "generate_json_with_timeout_retry",
        "wrapper",
        "LLM",
        "per-step budget + downshift transport",
        count=2,
    ),
    # --- Gateway complete() (scanned since GND-AGENT landed) -----------------------------
    _e(
        "llm_gateway/gateway.py",
        "Gateway._complete_once",
        "complete",
        "provider_internal",
        "LLM",
        "Gateway delegates to adapter.complete after prepare/retry",
    ),
    _e(
        "llm_gateway/fallback.py",
        "call_with_fallback",
        "complete",
        "wrapper",
        "LLM",
        "tiered fallback calls Gateway.complete; app callers of call_with_fallback must list",
    ),
    _e(
        "llm_gateway/conformance.py",
        "run_conformance",
        "complete",
        "provider_internal",
        "LLM",
        "conformance harness exercises Gateway.complete against ScriptedAdapter",
        count=21,
    ),
)


# --------------------------------------------------------------------------------------
# Scanner
# --------------------------------------------------------------------------------------


def _callee_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return None


class _SiteVisitor(ast.NodeVisitor):
    def __init__(self, entry_names: frozenset[str]) -> None:
        self.entry_names = entry_names
        self.stack: list[str] = []
        self.hits: Counter[tuple[str, str]] = Counter()

    def _scoped(self, node: ast.AST, name: str) -> None:
        self.stack.append(name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._scoped(node, node.name)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._scoped(node, node.name)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._scoped(node, node.name)

    def visit_Call(self, node: ast.Call) -> None:
        name = _callee_name(node)
        if name in self.entry_names:
            self.hits[(".".join(self.stack) or "<module>", name)] += 1
        self.generic_visit(node)


def scan_call_sites(root: Path, entry_names: frozenset[str]) -> set[Site]:
    """Return every call to ``entry_names`` under ``root``, keyed by enclosing scope."""
    sites: set[Site] = set()
    for py in sorted(root.rglob("*.py")):
        if "__pycache__" in py.parts:
            continue
        tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        visitor = _SiteVisitor(entry_names)
        visitor.visit(tree)
        rel = py.relative_to(root).as_posix()
        for (qualname, callee), count in visitor.hits.items():
            sites.add(Site(rel, qualname, callee, count))
    return sites


def entry_names_for(allowlist: tuple[Entry, ...]) -> frozenset[str]:
    """Base names plus each wrapper's top-level function name (``outer._call`` -> ``outer``)."""
    wrappers = {
        e.site.qualname.split(".", 1)[0] for e in allowlist if e.classification == "wrapper"
    }
    return BASE_ENTRY_NAMES | frozenset(wrappers)


def top_level_source(path: Path, qualname: str) -> str:
    """Source of the top-level def/class that encloses ``qualname``."""
    source = path.read_text(encoding="utf-8")
    outer = qualname.split(".", 1)[0]
    for node in ast.parse(source).body:
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and node.name == outer
        ):
            return ast.get_source_segment(source, node) or ""
    return ""


def gate_violations(root: Path, allowlist: tuple[Entry, ...]) -> tuple[set[Site], set[Site]]:
    """(unlisted sites found in code, listed sites no longer in code)."""
    found = scan_call_sites(root, entry_names_for(allowlist))
    listed = {e.site for e in allowlist}
    return found - listed, listed - found


# --------------------------------------------------------------------------------------
# Gate
# --------------------------------------------------------------------------------------


def _fmt(sites: set[Site]) -> str:
    return "\n".join(
        f"  {s.path} :: {s.qualname} -> {s.callee} (x{s.count})"
        for s in sorted(sites, key=lambda s: (s.path, s.qualname, s.callee))
    )


def test_every_llm_call_site_is_on_the_allowlist() -> None:
    unlisted, stale = gate_violations(APP_ROOT, ALLOWLIST)
    assert not unlisted, (
        "New LLM call site(s) not on the GND-GATE allowlist. Add each to ALLOWLIST in "
        "tests/test_gnd_gate_llm_call_sites.py with its grounding classification:\n"
        + _fmt(unlisted)
    )
    assert not stale, "Allowlist entries no longer in code (remove or update):\n" + _fmt(stale)


def test_allowlist_entries_are_unique_and_classified() -> None:
    keys = [(e.site.path, e.site.qualname, e.site.callee) for e in ALLOWLIST]
    assert len(keys) == len(set(keys)), "duplicate allowlist entries"
    for e in ALLOWLIST:
        assert e.classification in ALL_CLASSES, (e.site, e.classification)
        assert e.card and e.reason.strip(), e.site


def grounding_backing_errors(
    root: Path, tests_root: Path, allowlist: tuple[Entry, ...]
) -> list[str]:
    """Grounded claims with no source marker in scope or no evidence test file."""
    errors: list[str] = []
    for e in allowlist:
        marker = GROUNDED_CLASSES.get(e.classification)
        if marker is None:
            continue
        path = root / e.site.path
        if e.classification in FUNCTION_SCOPED_CLASSES:
            source = top_level_source(path, e.site.qualname)
        else:
            source = path.read_text(encoding="utf-8")
        if not marker.search(source):
            errors.append(f"{e.site} claims {e.classification} without {marker.pattern!r}")
        if not e.evidence_test or not (tests_root / e.evidence_test).is_file():
            errors.append(f"{e.site} claims {e.classification} without an evidence test")
    return errors


def test_grounded_entries_are_backed_by_source_marker_and_test() -> None:
    assert grounding_backing_errors(APP_ROOT, TESTS_ROOT, ALLOWLIST) == []


def test_wireframe_live_stays_on_the_allowlist_as_refusing_to_invent() -> None:
    wire = [e for e in ALLOWLIST if e.site.path == "wireframe_live.py"]
    assert wire and all(e.classification == "refuses_invent" for e in wire)


def test_no_ungrounded_debt_entries() -> None:
    """GND-GATE closes only when ALLOWLIST has zero ``ungrounded`` debt."""
    debt = [e for e in ALLOWLIST if e.classification == "ungrounded"]
    assert debt == [], "ungrounded allowlist debt remains:\n" + "\n".join(
        f"  {e.site.path} :: {e.site.qualname} -> {e.site.callee} ({e.card}: {e.reason})"
        for e in debt
    )


def test_gateway_complete_sites_are_listed_as_plumbing() -> None:
    complete_entries = [e for e in ALLOWLIST if e.site.callee == "complete"]
    assert complete_entries, "expected Gateway complete() allowlist entries"
    assert all(e.classification in PLUMBING_CLASSES for e in complete_entries)
    paths = {e.site.path for e in complete_entries}
    assert paths >= {
        "llm_gateway/gateway.py",
        "llm_gateway/fallback.py",
        "llm_gateway/conformance.py",
    }


# --------------------------------------------------------------------------------------
# Mutants: the gate must catch these
# --------------------------------------------------------------------------------------


def _write(root: Path, rel: str, body: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


_LISTED_SRC = """
def ask(provider, packet):
    return provider.generate_json(prepend(packet))
"""

_MINI_ALLOWLIST = (
    _e("listed.py", "ask", "generate_json", "live_packet", "GND-GEN", "fixture"),
    _e("transport.py", "with_retry", "generate_json", "wrapper", "GND-GATE", "fixture"),
)

_TRANSPORT_SRC = """
def with_retry(provider, text):
    return provider.generate_json(text)
"""


@pytest.fixture
def mini_app(tmp_path: Path) -> Path:
    _write(tmp_path, "listed.py", _LISTED_SRC)
    _write(tmp_path, "transport.py", _TRANSPORT_SRC)
    return tmp_path


def test_mini_app_baseline_passes(mini_app: Path) -> None:
    assert gate_violations(mini_app, _MINI_ALLOWLIST) == (set(), set())


@pytest.mark.parametrize(
    ("rel", "body", "expected"),
    [
        (
            "rogue/new_surface.py",
            "def suggest(provider, brief):\n    return provider.generate_text(brief)\n",
            Site("rogue/new_surface.py", "suggest", "generate_text"),
        ),
        (
            "rogue/bare.py",
            "from x import generate_json\n\ndef go(p):\n    return generate_json(p)\n",
            Site("rogue/bare.py", "go", "generate_json"),
        ),
        (
            "rogue/via_wrapper.py",
            "from transport import with_retry\n\nclass Bot:\n    def run(self, p):\n"
            "        return with_retry(None, p)\n",
            Site("rogue/via_wrapper.py", "Bot.run", "with_retry"),
        ),
        (
            "rogue/via_gateway.py",
            "def ask(gw, req):\n    return gw.complete(req)\n",
            Site("rogue/via_gateway.py", "ask", "complete"),
        ),
    ],
    ids=[
        "unlisted_method_call",
        "unlisted_bare_call",
        "unlisted_wrapper_caller",
        "unlisted_gateway_complete",
    ],
)
def test_unlisted_call_site_fails_the_gate(
    mini_app: Path, rel: str, body: str, expected: Site
) -> None:
    _write(mini_app, rel, body)
    unlisted, stale = gate_violations(mini_app, _MINI_ALLOWLIST)
    assert unlisted == {expected}
    assert not stale


def test_second_call_in_a_listed_function_fails_the_gate(mini_app: Path) -> None:
    _write(
        mini_app,
        "listed.py",
        _LISTED_SRC + "    provider.generate_json('again')\n",
    )
    unlisted, stale = gate_violations(mini_app, _MINI_ALLOWLIST)
    assert unlisted == {Site("listed.py", "ask", "generate_json", 2)}
    assert stale == {Site("listed.py", "ask", "generate_json", 1)}


def test_live_packet_claim_without_packet_in_function_fails(mini_app: Path) -> None:
    _write(mini_app, "tests/test_fixture.py", "")
    _write(
        mini_app,
        "listed.py",
        "schema_packet = None\n\n"
        "def ask(provider, brief):\n    return provider.generate_json(brief)\n",
    )
    claim = (
        _e(
            "listed.py",
            "ask",
            "generate_json",
            "live_packet",
            "GND-GEN",
            "fixture",
            evidence_test="test_fixture.py",
        ),
    )
    errors = grounding_backing_errors(mini_app, mini_app / "tests", claim)
    assert len(errors) == 1 and "without 'schema_packet'" in errors[0]


def test_removed_call_site_is_reported_stale(mini_app: Path) -> None:
    (mini_app / "listed.py").write_text(
        "def ask(provider, packet):\n    return None\n", encoding="utf-8"
    )
    unlisted, stale = gate_violations(mini_app, _MINI_ALLOWLIST)
    assert not unlisted
    assert stale == {Site("listed.py", "ask", "generate_json")}
