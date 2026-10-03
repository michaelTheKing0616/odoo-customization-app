"""Track 5A — plan fingerprint and dry-run hash tests."""

from __future__ import annotations

from app.plan_fingerprint import (
    fingerprints_match,
    plan_fingerprint,
    structural_dry_run_hash,
)


def test_plan_fingerprint_excludes_res_id() -> None:
    changes = [{"model": "res.partner", "res_id": 1, "field": "name", "value": "A"}]
    fp_with = plan_fingerprint(changes)
    fp_without = plan_fingerprint([{"model": "res.partner", "field": "name", "value": "A"}])
    assert fp_with == fp_without
    assert len(fp_with) == 16
    assert changes[0]["res_id"] == 1


def test_plan_fingerprint_drift() -> None:
    baseline = [{"model": "res.partner", "field": "name", "value": "A"}]
    expected = plan_fingerprint(baseline)
    assert fingerprints_match(expected, baseline) is True
    drifted = [{"model": "res.partner", "field": "name", "value": "B"}]
    assert fingerprints_match(expected, drifted) is False


def test_dry_run_hash_ignores_dry_run_flag() -> None:
    a = structural_dry_run_hash("apply_change", {"model": "x", "dry_run": True})
    b = structural_dry_run_hash("apply_change", {"model": "x", "dry_run": False})
    c = structural_dry_run_hash("apply_change", {"model": "x"})
    assert a == b == c
    assert len(a) == 64
