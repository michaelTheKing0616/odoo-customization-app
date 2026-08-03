"""REM-4 unit tests: partner merge option + send execute path."""

from __future__ import annotations

from app.bulk_suite.dedupe import merge_duplicates
from app.bulk_suite.send_message import run_bulk_send_message


def test_partner_merge_offered_instead_of_error() -> None:
    class _Client:
        def model_exists(self, model: str) -> bool:
            return model == "base.partner.merge.automatic.wizard"

        def execute_kw(self, *args, **kwargs):  # noqa: ANN002, ANN003
            raise AssertionError("generic merge should not RPC when wizard available")

    result = merge_duplicates(
        _Client(),  # type: ignore[arg-type]
        model="res.partner",
        winner_id=10,
        loser_ids=[11],
        dry_run=False,
        force_generic_merge=False,
    )
    assert result.partner_merge_recommended is True
    assert result.succeeded == 0
    assert "force_generic_merge" in result.message


def test_send_message_execute_calls_message_post_per_record() -> None:
    posts: list[int] = []

    class _MailClient:
        def model_exists(self, model: str) -> bool:
            return model == "mail.message"

        def execute_kw(self, model: str, method: str, args, kwargs=None):  # noqa: ANN001
            if model == "x_test" and method == "fields_get":
                return {"message_ids": {}, "display_name": {}}
            if model == "x_test" and method == "read":
                return [{"id": i, "display_name": f"R{i}"} for i in args[0]]
            if method == "message_post":
                posts.append(int(args[0][0]))
                return 1
            raise AssertionError(f"{model}.{method}")

    result = run_bulk_send_message(
        _MailClient(),  # type: ignore[arg-type]
        model="x_test",
        record_ids=[1, 2, 3],
        body="<p>Hello</p>",
        dry_run=False,
    )
    assert posts == [1, 2, 3]
    assert result.succeeded == 3
    assert result.failed == 0
    assert result.dry_run is False
