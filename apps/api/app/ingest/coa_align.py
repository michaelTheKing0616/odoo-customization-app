"""CoA alignment + remapping offers against installed l10n_* accounts."""

from __future__ import annotations

import re
from typing import Any

from odoo_client import OdooClient

from app.ingest.schema import IngestGap, IngestTable
from app.invoicing_l10n import detect_l10n


def load_instance_account_codes(client: OdooClient) -> dict[str, dict[str, Any]]:
    if not client.model_exists("account.account"):
        return {}
    rows = client.execute_kw(
        "account.account",
        "search_read",
        [[]],
        {"fields": ["id", "code", "name", "account_type"], "limit": 5000},
    )
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        code = str(r.get("code") or "").strip()
        if code:
            out[code] = r
    return out


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(t) > 2}


def _score_match(
    legacy_name: str,
    legacy_type: str,
    candidate: dict[str, Any],
) -> float:
    name = str(candidate.get("name") or "")
    atype = str(candidate.get("account_type") or "")
    a = _tokens(legacy_name)
    b = _tokens(name)
    if not a or not b:
        overlap = 0.0
    else:
        overlap = len(a & b) / max(len(a | b), 1)
    type_bonus = 0.35 if legacy_type and atype and legacy_type == atype else 0.0
    # Prefer similar account_type family prefixes (asset_, liability_, …)
    if legacy_type and atype and legacy_type.split("_")[0] == atype.split("_")[0]:
        type_bonus = max(type_bonus, 0.2)
    return overlap + type_bonus


def suggest_coa_remaps(
    client: OdooClient,
    table: IngestTable,
    *,
    min_score: float = 0.25,
) -> list[dict[str, Any]]:
    """For each legacy code not on instance, suggest best l10n/live account."""
    live = load_instance_account_codes(client)
    if not live:
        return []
    candidates = list(live.values())
    suggestions: list[dict[str, Any]] = []
    for row in table.rows:
        code = str(
            row.values.get("code") or row.raw.get("code") or row.raw.get("account_code") or ""
        ).strip()
        if not code or code in live:
            continue
        name = str(row.values.get("name") or row.raw.get("name") or "")
        atype = str(
            row.values.get("account_type")
            or row.raw.get("account_type")
            or row.raw.get("type")
            or ""
        )
        ranked = sorted(
            (
                (_score_match(name, atype, c), c)
                for c in candidates
            ),
            key=lambda x: -x[0],
        )
        if not ranked or ranked[0][0] < min_score:
            suggestions.append(
                {
                    "legacy_code": code,
                    "legacy_name": name,
                    "suggested_code": None,
                    "suggested_name": None,
                    "score": 0.0,
                    "alternatives": [],
                }
            )
            continue
        best_score, best = ranked[0]
        alts = [
            {
                "code": str(c.get("code")),
                "name": str(c.get("name")),
                "account_type": str(c.get("account_type") or ""),
                "score": round(s, 3),
            }
            for s, c in ranked[1:4]
            if s >= min_score
        ]
        suggestions.append(
            {
                "legacy_code": code,
                "legacy_name": name,
                "suggested_code": str(best.get("code")),
                "suggested_name": str(best.get("name")),
                "suggested_account_type": str(best.get("account_type") or ""),
                "score": round(best_score, 3),
                "alternatives": alts,
            }
        )
    return suggestions


def apply_coa_remap(
    table: IngestTable,
    remap: dict[str, str],
    *,
    live: dict[str, dict[str, Any]] | None = None,
) -> list[str]:
    """Rewrite row codes from legacy → target. Mutates table rows."""
    notes: list[str] = []
    if table.doc_type != "coa":
        return notes
    for row in table.rows:
        code = str(
            row.values.get("code") or row.raw.get("code") or row.raw.get("account_code") or ""
        ).strip()
        if not code or code not in remap:
            continue
        target = str(remap[code]).strip()
        if not target or target == code:
            continue
        row.raw["code"] = target
        row.raw["legacy_code"] = code
        row.values["code"] = target
        row.values["legacy_code"] = code
        if live and target in live:
            row.values["id"] = int(live[target]["id"])
            row.flags = [f for f in row.flags if f != "coa_legacy_code"]
            row.flags.append("coa_remapped")
        notes.append(f"coa: remapped {code} → {target}")
    return notes


def align_coa_table(
    client: OdooClient,
    table: IngestTable,
    *,
    allow_as_is: bool = False,
    auto_remap: bool = False,
) -> tuple[list[IngestGap], list[str], dict[str, Any]]:
    """Compare extracted CoA codes to live/l10n accounts; optionally auto-remap."""
    gaps: list[IngestGap] = []
    warnings: list[str] = []
    summary: dict[str, Any] = {
        "matched": 0,
        "missing_on_instance": [],
        "legacy_only": [],
        "remap_suggestions": [],
        "remapped": [],
        "l10n": detect_l10n(client),
    }
    if table.doc_type != "coa":
        return gaps, warnings, summary

    l10n = summary["l10n"]
    if not l10n.get("ok"):
        warnings.append(str(l10n.get("message") or "Fiscal localization not detected"))
        if not allow_as_is:
            gaps.append(
                IngestGap(
                    model="account.account",
                    field="l10n",
                    value="",
                    message=(
                        "Install matching l10n_* for company country before CoA commit, "
                        "or re-run with allow_coa_as_is after financial confirm."
                    ),
                )
            )

    live = load_instance_account_codes(client)
    if not live and client.model_exists("account.account"):
        warnings.append(
            "No accounts on instance yet — CoA import will create codes; "
            "verify they match your country's fiscal package."
        )

    suggestions = suggest_coa_remaps(client, table) if live else []
    summary["remap_suggestions"] = suggestions

    if auto_remap and suggestions:
        remap = {
            s["legacy_code"]: s["suggested_code"]
            for s in suggestions
            if s.get("suggested_code") and (s.get("score") or 0) >= 0.45
        }
        if remap:
            notes = apply_coa_remap(table, remap, live=live)
            warnings.extend(notes)
            summary["remapped"] = list(remap.items())

    for row in table.rows:
        code = str(
            row.values.get("code") or row.raw.get("code") or row.raw.get("account_code") or ""
        ).strip()
        if not code:
            gaps.append(
                IngestGap(
                    model="account.account",
                    field="code",
                    value="",
                    message=f"CoA row {row.source_ref or '?'} missing code",
                )
            )
            continue
        row.values["code"] = code
        if code in live:
            summary["matched"] += 1
            row.values["id"] = int(live[code]["id"])
            if "coa_matched_existing" not in row.flags:
                row.flags.append("coa_matched_existing")
        else:
            summary["missing_on_instance"].append(code)
            summary["legacy_only"].append(code)
            if "coa_legacy_code" not in row.flags:
                row.flags.append("coa_legacy_code")
            sug = next((s for s in suggestions if s["legacy_code"] == code), None)
            hint = ""
            if sug and sug.get("suggested_code"):
                hint = (
                    f" — suggested l10n align: {sug['suggested_code']} "
                    f"({sug.get('suggested_name')}, score={sug.get('score')})"
                )
            if live and not allow_as_is:
                gaps.append(
                    IngestGap(
                        model="account.account",
                        field="code",
                        value=code,
                        message=(
                            f"Account {code} not in installed CoA/l10n set{hint}. "
                            "Apply remap via /coa-remap, or confirm allow_coa_as_is."
                        ),
                    )
                )

    if summary["legacy_only"]:
        warnings.append(
            f"{len(summary['legacy_only'])} legacy account code(s) not on instance: "
            + ", ".join(summary["legacy_only"][:8])
        )
    return gaps, warnings, summary


__all__ = [
    "align_coa_table",
    "apply_coa_remap",
    "load_instance_account_codes",
    "suggest_coa_remaps",
]
