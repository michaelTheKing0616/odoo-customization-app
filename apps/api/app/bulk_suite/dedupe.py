"""Generic duplicate scan + merge with FK relinking (BLK-3)."""

from __future__ import annotations

import difflib
import re
import unicodedata
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Literal

from odoo_client import OdooClient
from odoo_client.client import OdooClientError

from app.bulk_suite.transitions import BulkRunResult, BulkSuiteError, PerRecordResult
from app.protected_enforcement import is_custom_model, protected_models_for

Mode = Literal["exact", "fuzzy"]
ArchiveMode = Literal["archive", "unlink"]

_FUZZY_RATIO = 0.92
_DEFAULT_SCAN_LIMIT = 2000


class DedupeValidationError(BulkSuiteError):
    pass


@dataclass(frozen=True)
class ReferenceField:
    model: str
    field: str
    ttype: str  # many2one | many2many


@dataclass
class DedupeCandidateRecord:
    id: int
    display_name: str
    preview: dict[str, Any]


@dataclass
class DedupeGroup:
    group_key: str
    match_fields: list[str]
    records: list[DedupeCandidateRecord]


@dataclass
class DedupeScanResult:
    model: str
    mode: str
    match_fields: list[str]
    groups: list[DedupeGroup]
    partner_merge_available: bool = False
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "mode": self.mode,
            "match_fields": self.match_fields,
            "partner_merge_available": self.partner_merge_available,
            "total_groups": len(self.groups),
            "groups": [
                {
                    "group_key": g.group_key,
                    "match_fields": g.match_fields,
                    "records": [
                        {
                            "id": r.id,
                            "display_name": r.display_name,
                            "preview": r.preview,
                        }
                        for r in g.records
                    ],
                }
                for g in self.groups
            ],
            "message": self.message,
        }


@dataclass
class RelinkStat:
    model: str
    field: str
    ttype: str
    count: int


@dataclass
class DedupeMergeResult(BulkRunResult):
    winner_id: int = 0
    loser_ids: list[int] = field(default_factory=list)
    relinks: list[RelinkStat] = field(default_factory=list)
    snapshot_id: str | None = None
    reversibility: str = "partial"

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data.update(
            {
                "winner_id": self.winner_id,
                "loser_ids": list(self.loser_ids),
                "relinks": [
                    {
                        "model": r.model,
                        "field": r.field,
                        "ttype": r.ttype,
                        "count": r.count,
                    }
                    for r in self.relinks
                ],
                "snapshot_id": self.snapshot_id,
                "reversibility": self.reversibility,
            }
        )
        return data


def check_dedupe_allowed(manifest: dict[str, Any], model: str) -> None:
    tier = protected_models_for(manifest, model)
    if tier == "tier_1" and not is_custom_model(model):
        raise DedupeValidationError(
            f"Deduplicate/merge on tier-1 model {model!r} is out of scope "
            "(accounting/financial records need dedicated operations)."
        )


def partner_merge_available(client: OdooClient) -> bool:
    try:
        return client.model_exists("base.partner.merge.automatic.wizard")
    except OdooClientError:
        return False


def normalize_fuzzy_value(value: Any) -> str:
    if value is False or value is None:
        return ""
    text = str(value)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.casefold()
    text = re.sub(r"[\s\W_]+", "", text, flags=re.UNICODE)
    return text


def _composite_key(record: dict[str, Any], match_fields: list[str], mode: Mode) -> str:
    parts: list[str] = []
    for fname in match_fields:
        raw = record.get(fname)
        if mode == "fuzzy":
            parts.append(normalize_fuzzy_value(raw))
        else:
            parts.append("" if raw in (False, None) else str(raw))
    return "|".join(parts)


def _fuzzy_merge_keys(keys: list[str]) -> dict[str, str]:
    """Map raw keys to cluster representative (single-field fuzzy only)."""
    if not keys:
        return {}
    unique = sorted(set(keys))
    rep: dict[str, str] = {}
    clusters: list[str] = []
    for key in unique:
        if not key:
            continue
        matched = None
        for cluster in clusters:
            if difflib.SequenceMatcher(None, key, cluster).ratio() >= _FUZZY_RATIO:
                matched = cluster
                break
        if matched is None:
            clusters.append(key)
            rep[key] = key
        else:
            rep[key] = matched
    return rep


def discover_inbound_references(client: OdooClient, target_model: str) -> list[ReferenceField]:
    rows = client.execute_kw(
        "ir.model.fields",
        "search_read",
        [[("relation", "=", target_model), ("ttype", "in", ["many2one", "many2many"])]],
        {"fields": ["name", "model", "ttype", "relation"], "limit": 5000},
    )
    out: list[ReferenceField] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        ref_model = str(row.get("model") or "")
        fname = str(row.get("name") or "")
        ttype = str(row.get("ttype") or "")
        if not ref_model or not fname or ref_model == target_model:
            continue
        key = (ref_model, fname)
        if key in seen:
            continue
        seen.add(key)
        if not client.model_exists(ref_model):
            continue
        out.append(ReferenceField(model=ref_model, field=fname, ttype=ttype))
    return sorted(out, key=lambda r: (r.model, r.field))


def scan_duplicates(
    client: OdooClient,
    *,
    model: str,
    match_fields: list[str],
    mode: Mode = "exact",
    limit: int = _DEFAULT_SCAN_LIMIT,
    domain: list[Any] | None = None,
    manifest: dict[str, Any] | None = None,
) -> DedupeScanResult:
    if manifest is not None:
        check_dedupe_allowed(manifest, model)
    if not match_fields:
        raise DedupeValidationError("match_fields must include at least one field name")
    if not client.model_exists(model):
        raise DedupeValidationError(f"Model {model!r} is not installed")

    limit = max(1, min(int(limit or _DEFAULT_SCAN_LIMIT), 5000))
    fields = list(dict.fromkeys([*match_fields, "display_name"]))
    rows = client.execute_kw(
        model,
        "search_read",
        [domain or []],
        {"fields": fields, "limit": limit, "order": "id"},
    )

    keyed: dict[str, list[dict[str, Any]]] = defaultdict(list)
    if mode == "fuzzy" and len(match_fields) == 1:
        raw_keys: list[str] = []
        row_keys: list[str] = []
        for row in rows:
            key = _composite_key(row, match_fields, "fuzzy")
            row_keys.append(key)
            raw_keys.append(key)
        merge_map = _fuzzy_merge_keys(raw_keys)
        for row, key in zip(rows, row_keys, strict=False):
            cluster = merge_map.get(key, key)
            if cluster:
                keyed[cluster].append(row)
    else:
        for row in rows:
            key = _composite_key(row, match_fields, mode)
            if key.strip("|"):
                keyed[key].append(row)

    groups: list[DedupeGroup] = []
    for key, members in keyed.items():
        if len(members) < 2:
            continue
        groups.append(
            DedupeGroup(
                group_key=key,
                match_fields=list(match_fields),
                records=[
                    DedupeCandidateRecord(
                        id=int(m["id"]),
                        display_name=str(m.get("display_name") or m["id"]),
                        preview={f: m.get(f) for f in match_fields},
                    )
                    for m in members
                ],
            )
        )
    groups.sort(key=lambda g: (-len(g.records), g.group_key))

    return DedupeScanResult(
        model=model,
        mode=mode,
        match_fields=list(match_fields),
        groups=groups,
        partner_merge_available=(
            partner_merge_available(client) if model == "res.partner" else False
        ),
        message=f"Found {len(groups)} duplicate group(s) among {len(rows)} record(s) scanned.",
    )


def _count_m2o(client: OdooClient, ref: ReferenceField, loser_ids: list[int]) -> int:
    return len(
        client.execute_kw(
            ref.model,
            "search",
            [[(ref.field, "in", loser_ids)]],
        )
    )


def _count_m2m(client: OdooClient, ref: ReferenceField, loser_ids: list[int]) -> int:
    total = 0
    for loser in loser_ids:
        total += len(
            client.execute_kw(
                ref.model,
                "search",
                [[(ref.field, "in", [loser])]],
            )
        )
    return total


def _relink_m2o(
    client: OdooClient,
    ref: ReferenceField,
    *,
    winner_id: int,
    loser_ids: list[int],
    dry_run: bool,
) -> int:
    ids = client.execute_kw(
        ref.model,
        "search",
        [[(ref.field, "in", loser_ids)]],
    )
    if not ids or dry_run:
        return len(ids)
    client.execute_kw(ref.model, "write", [ids, {ref.field: winner_id}])
    return len(ids)


def _relink_m2m(
    client: OdooClient,
    ref: ReferenceField,
    *,
    winner_id: int,
    loser_ids: list[int],
    dry_run: bool,
) -> int:
    touched = 0
    for loser in loser_ids:
        ids = client.execute_kw(
            ref.model,
            "search",
            [[(ref.field, "in", [loser])]],
        )
        if not ids:
            continue
        touched += len(ids)
        if dry_run:
            continue
        for rid in ids:
            client.execute_kw(
                ref.model,
                "write",
                [[int(rid)], {ref.field: [(3, loser), (4, winner_id)]}],
            )
    return touched


def _relink_chatter(
    client: OdooClient,
    model: str,
    *,
    winner_id: int,
    loser_ids: list[int],
    dry_run: bool,
) -> list[RelinkStat]:
    stats: list[RelinkStat] = []
    for chatter_model, model_field in (
        ("mail.message", "model"),
        ("mail.followers", "res_model"),
    ):
        if not client.model_exists(chatter_model):
            continue
        id_field = "res_id"
        count = 0
        for loser in loser_ids:
            ids = client.execute_kw(
                chatter_model,
                "search",
                [[(model_field, "=", model), (id_field, "=", loser)]],
            )
            count += len(ids)
            if ids and not dry_run:
                if chatter_model == "mail.followers":
                    for fid in ids:
                        rows = client.execute_kw(
                            "mail.followers",
                            "read",
                            [[fid]],
                            {"fields": ["partner_id"]},
                        )
                        partner_id = rows[0].get("partner_id") if rows else None
                        if isinstance(partner_id, (list, tuple)):
                            partner_id = partner_id[0]
                        dup = []
                        if partner_id:
                            dup = client.execute_kw(
                                "mail.followers",
                                "search",
                                [
                                    [
                                        (model_field, "=", model),
                                        (id_field, "=", winner_id),
                                        ("partner_id", "=", partner_id),
                                    ]
                                ],
                            )
                        if dup:
                            client.execute_kw("mail.followers", "unlink", [[fid]])
                        else:
                            client.execute_kw(
                                chatter_model,
                                "write",
                                [[fid], {id_field: winner_id}],
                            )
                else:
                    client.execute_kw(
                        chatter_model,
                        "write",
                        [ids, {id_field: winner_id}],
                    )
        if count:
            stats.append(
                RelinkStat(model=chatter_model, field=id_field, ttype="chatter", count=count)
            )
    return stats


def build_merge_snapshot_payload(
    client: OdooClient,
    *,
    model: str,
    winner_id: int,
    loser_ids: list[int],
    references: list[ReferenceField],
) -> dict[str, Any]:
    loser_rows = client.execute_kw(model, "read", [loser_ids], {})
    ref_map: list[dict[str, Any]] = []
    for ref in references:
        if ref.ttype == "many2one":
            cnt = _count_m2o(client, ref, loser_ids)
        else:
            cnt = _count_m2m(client, ref, loser_ids)
        if cnt:
            ref_map.append(
                {
                    "model": ref.model,
                    "field": ref.field,
                    "ttype": ref.ttype,
                    "affected_rows": cnt,
                }
            )
    return {
        "operation": "dedupe_merge",
        "model": model,
        "winner_id": winner_id,
        "loser_ids": loser_ids,
        "losers": loser_rows,
        "inbound_references": ref_map,
        "recovery_note": (
            "Merge relinks FKs and archives/unlinks losers. "
            "Restoring losers requires manual reverse from this snapshot payload."
        ),
    }


def merge_duplicates(
    client: OdooClient,
    *,
    model: str,
    winner_id: int,
    loser_ids: list[int],
    dry_run: bool = True,
    archive_or_delete: ArchiveMode = "archive",
    run_id: str | None = None,
    snapshot_id: str | None = None,
    manifest: dict[str, Any] | None = None,
) -> DedupeMergeResult:
    run_id = run_id or str(uuid.uuid4())
    losers = [int(i) for i in loser_ids if int(i) != int(winner_id)]
    losers = list(dict.fromkeys(losers))
    if not losers:
        raise DedupeValidationError("loser_ids must include at least one id different from winner_id")
    if manifest is not None:
        check_dedupe_allowed(manifest, model)

    if model == "res.partner" and partner_merge_available(client) and not dry_run:
        raise DedupeValidationError(
            "res.partner merge is available via Odoo's base.partner.merge wizard on this "
            "instance — prefer that for partners; generic merge blocked when wizard exists."
        )

    references = discover_inbound_references(client, model)
    relinks: list[RelinkStat] = []

    for ref in references:
        if ref.ttype == "many2one":
            cnt = _relink_m2o(
                client, ref, winner_id=winner_id, loser_ids=losers, dry_run=dry_run
            )
        else:
            cnt = _relink_m2m(
                client, ref, winner_id=winner_id, loser_ids=losers, dry_run=dry_run
            )
        if cnt:
            relinks.append(
                RelinkStat(model=ref.model, field=ref.field, ttype=ref.ttype, count=cnt)
            )

    relinks.extend(
        _relink_chatter(client, model, winner_id=winner_id, loser_ids=losers, dry_run=dry_run)
    )

    per_record: list[PerRecordResult] = []
    succeeded = 0
    failed = 0

    if dry_run:
        for lid in losers:
            per_record.append(
                PerRecordResult(id=lid, display_name=str(lid), ok=True, error=None)
            )
        succeeded = len(losers)
        msg = (
            f"Dry-run: would merge {len(losers)} loser(s) into winner {winner_id}; "
            f"{sum(r.count for r in relinks)} inbound reference row(s) to relink."
        )
    else:
        try:
            if archive_or_delete == "archive" and client.field_exists(model, "active"):
                client.execute_kw(model, "write", [losers, {"active": False}])
                action = "archived"
            elif archive_or_delete == "archive":
                action = "left-in-place (no active field)"
            else:
                client.execute_kw(model, "unlink", [losers])
                action = "unlinked"
            for lid in losers:
                per_record.append(
                    PerRecordResult(id=lid, display_name=str(lid), ok=True)
                )
            succeeded = len(losers)
            msg = (
                f"Merged into winner {winner_id}: {len(losers)} loser(s) {action}; "
                f"{sum(r.count for r in relinks)} reference row(s) relinked."
            )
        except Exception as exc:  # noqa: BLE001
            failed = len(losers)
            for lid in losers:
                per_record.append(
                    PerRecordResult(
                        id=lid,
                        display_name=str(lid),
                        ok=False,
                        error=str(exc),
                    )
                )
            msg = f"Merge failed: {exc}"

    return DedupeMergeResult(
        run_id=run_id,
        operation="dedupe_merge",
        model=model,
        total=len(losers),
        succeeded=succeeded,
        failed=failed,
        per_record=per_record,
        dry_run=dry_run,
        message=msg,
        winner_id=winner_id,
        loser_ids=losers,
        relinks=relinks,
        snapshot_id=snapshot_id,
        reversibility="partial",
    )
