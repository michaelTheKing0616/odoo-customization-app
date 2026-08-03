"""CMP-10 approval process service (fake Odoo RPC)."""

from __future__ import annotations

import json
from typing import Any

from app.approval_process_service import (
    approve_request,
    create_request,
    submit_request,
)
from app.approval_requests_pack import DEFAULT_CHAIN


class _FakeClient:
    def __init__(self) -> None:
        self.models = {"x_approval_type", "x_approval_request", "res.users", "mail.activity.type"}
        self.seq = 0
        self.types: dict[int, dict[str, Any]] = {
            1: {"id": 1, "x_name": "Demo", "x_chain_json": json.dumps(DEFAULT_CHAIN)}
        }
        self.requests: dict[int, dict[str, Any]] = {}
        self.activities: list[dict[str, Any]] = []
        self.messages: list[str] = []

    def model_exists(self, model: str) -> bool:
        return model in self.models

    def execute_kw(
        self,
        model: str,
        method: str,
        args: list[Any],
        kwargs: dict[str, Any] | None = None,
    ) -> Any:
        if model == "x_approval_type" and method == "read":
            return [self.types[int(args[0][0])]]
        if model == "x_approval_request" and method == "create":
            self.seq += 1
            vals = args[0]
            self.requests[self.seq] = {"id": self.seq, **vals}
            return self.seq
        if model == "x_approval_request" and method == "read":
            rid = int(args[0][0])
            return [self.requests[rid]]
        if model == "x_approval_request" and method == "write":
            rid, vals = args[0][0], args[1]
            self.requests[rid].update(vals)
            return True
        if model == "x_approval_request" and method == "message_post":
            body = (kwargs or {}).get("body", "")
            self.messages.append(str(body))
            return True
        if model == "res.users" and method == "read":
            return [{"groups_id": []}]
        if model == "mail.activity.type" and method == "search_read":
            return [{"id": 1}]
        if model == "mail.activity" and method == "create":
            self.activities.append(args[0])
            return len(self.activities)
        raise AssertionError(f"{model}.{method}")


def test_two_level_approve_flow_min_two() -> None:
    client = _FakeClient()
    req = create_request(
        client, type_id=1, subject="Budget", amount=500.0, requester_id=2
    )
    rid = int(req["id"])
    submit_request(client, request_id=rid)
    assert client.requests[rid]["x_state"] == "submitted"
    approve_request(client, request_id=rid, actor_user_id=2)
    assert client.requests[rid]["x_state"] == "submitted"
    final = approve_request(client, request_id=rid, actor_user_id=3)
    assert final["advanced_to"] == 2
    approve_request(client, request_id=rid, actor_user_id=2)
    assert client.requests[rid]["x_state"] == "approved"
