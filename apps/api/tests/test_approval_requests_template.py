"""Module zip for Approval Requests template."""

from __future__ import annotations

from app.approval_requests_pack import approval_requests_draft
from app.module_spec_codec import draft_dict_to_module_spec, export_draft_module_zip


def test_approval_requests_module_zip() -> None:
    draft = approval_requests_draft()
    spec = draft_dict_to_module_spec(draft)
    assert any(m.model == "x_approval_request" for m in spec.models)
    raw = export_draft_module_zip(draft)
    assert len(raw) > 200
    assert b"x_approval_request" in raw
