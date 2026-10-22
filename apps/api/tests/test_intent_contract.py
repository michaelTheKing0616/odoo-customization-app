"""Source-anchored App Studio interpretation gates."""

from __future__ import annotations

from types import SimpleNamespace

from app.ai_conversation.app_design import _call_intent_contract, label_python_pieces
from app.ai_conversation.intent_contract import (
    apply_verifier_verdicts,
    normalize_critic_findings,
    normalize_intent_contract,
    pending_contract_clarification,
    resolve_contract_answers,
)
from app.brief_integrations import python_pieces


def test_scheduled_date_is_not_a_python_requirement() -> None:
    brief = "Maintenance Job fields: Scheduled date, equipment, and technician."
    assert python_pieces(brief, "self_hosted") == []


def test_explicit_schedule_still_has_a_deterministic_fallback() -> None:
    brief = "Run a nightly scheduled job to recompute health scores."
    assert {piece["key"] for piece in python_pieces(brief, "self_hosted")} == {
        "computed_score",
        "scheduled_actions",
    }


def test_negated_python_requirement_is_not_admitted() -> None:
    assert python_pieces("No scheduled jobs or computed scores.", "self_hosted") == []


def test_llm_python_piece_requires_a_source_anchored_option_a_contract() -> None:
    prompt = "Recompute each health score nightly from invoices and open tickets."
    contract = normalize_intent_contract(
        [
            {
                "id": "nightly_health_recompute",
                "kind": "python",
                "subject": "Nightly health score recompute",
                "decision": "option_a",
                "evidence": "Recompute each health score nightly from invoices and open tickets.",
                "why_metadata_cannot_do_it": (
                    "The calculation combines changing records on a schedule."
                ),
                "metadata_alternative": "A manually entered score",
                "trigger": "time",
                "rungs": [
                    {"rung": "metadata", "sufficient": False, "why": "Stored fields never recompute."},
                    {"rung": "stock_automation", "sufficient": False, "why": "Needs a cross-record calculation."},
                ],
                "confidence": "high",
            }
        ],
        prompt,
    )
    contract = apply_verifier_verdicts(contract, {contract[0]["id"]: "supports"})
    assert contract[0]["decision"] == "option_a"
    # Validation runs after design repair, so an already-normalized contract
    # must retain its source span and stable id.
    assert normalize_intent_contract(contract, prompt, trusted=True) == contract
    notes: list[str] = []
    accepted = label_python_pieces(
        [
            {
                "label": "Nightly health score recompute",
                "kind": "cron",
                "requirement_id": contract[0]["id"],
            }
        ],
        prompt,
        SimpleNamespace(hosting="self_hosted"),
        llm_designed=True,
        intent_contract=contract,
        notes=notes,
    )
    assert len(accepted) == 1
    assert accepted[0]["evidence"]["start"] == 0
    assert accepted[0]["metadata_alternative"] == "A manually entered score"
    assert notes == []


def test_llm_python_piece_without_contract_is_dropped_instead_of_regex_backfilled() -> None:
    notes: list[str] = []
    dropped = label_python_pieces(
        [{"label": "Scheduled recompute", "kind": "cron"}],
        "Maintenance Job fields: Scheduled date, equipment, and technician.",
        SimpleNamespace(hosting="self_hosted"),
        llm_designed=True,
        notes=notes,
    )
    assert dropped == []
    assert "verified requirement" in notes[0]


def test_suggestive_field_label_cannot_authorize_option_a() -> None:
    brief = "Maintenance Job fields: Scheduled date, equipment, and technician."
    contract = normalize_intent_contract(
        [
            {
                "kind": "python",
                "subject": "Scheduled actions",
                "decision": "option_a",
                "evidence": "Scheduled date",
                "why_metadata_cannot_do_it": "A recurring process must execute outside the form.",
                "metadata_alternative": "A date field",
            }
        ],
        brief,
    )
    assert all(r["decision"] != "option_a" for r in contract)


def test_operator_choice_resolves_a_source_anchored_ambiguity() -> None:
    brief = "Calculate a score after each inspection."
    contract = normalize_intent_contract(
        [
            {
                "kind": "python",
                "subject": "Inspection score",
                "decision": "clarify",
                "evidence": "Calculate a score",
                "question": "Should this be a configured field or calculated behavior?",
            }
        ],
        brief,
    )
    requirement = contract[0]
    resolved = resolve_contract_answers(
        contract, {f"intent_contract:{requirement['id']}": "option_a"}
    )
    assert resolved[0]["decision"] == "option_a"
    assert resolved[0]["operator_confirmed"] is True


def test_contract_is_frozen_before_an_operator_answer() -> None:
    class Provider:
        calls = 0

        def generate_json(self, *_args, **_kwargs):
            self.calls += 1
            return {
                "requirements": [
                    {
                        "kind": "python",
                        "subject": "Inspection score",
                        "decision": "clarify",
                        "evidence": "Calculate a score",
                        "question": "Should custom code calculate it?",
                    }
                ]
            }

    provider = Provider()
    answers: dict[str, str] = {}
    prompt = "Calculate a score after each inspection."
    first, first_meta = _call_intent_contract(provider, prompt, None, answers=answers)
    assert first_meta["status"] == "called"
    answer_key = f"intent_contract:{first[0]['id']}"
    second, second_meta = _call_intent_contract(
        provider, prompt, None, answers={**answers, answer_key: "option_a"}
    )
    assert second_meta["reason"] == "frozen_session_contract"
    assert provider.calls == 1
    assert second[0]["decision"] == "option_a"


def test_contract_ambiguity_becomes_one_operator_question_until_answered() -> None:
    brief = "Calculate a score after each inspection."
    contract = normalize_intent_contract(
        [
            {
                "id": "inspection_score",
                "kind": "python",
                "subject": "Inspection score",
                "decision": "clarify",
                "evidence": "Calculate a score after each inspection.",
                "question": "Should people enter this score, or should custom code calculate it?",
            }
        ],
        brief,
    )
    pending = pending_contract_clarification(contract, [], {})
    assert pending and pending["merge_key"] == f"intent_contract:{contract[0]['id']}"
    assert (
        pending_contract_clarification(
            contract, [], {f"intent_contract:{contract[0]['id']}": "metadata"}
        )
        is None
    )


def test_critic_finding_needs_a_positive_source_span() -> None:
    brief = "Add a scheduled date to each Maintenance Job."
    findings = normalize_critic_findings(
        {
            "findings": [
                {
                    "id": "date_ambiguity",
                    "kind": "ambiguity",
                    "subject": "Scheduled date",
                    "evidence": "scheduled date",
                    "question": "Should this start work automatically?",
                },
                {
                    "id": "invented",
                    "kind": "unsupported_design",
                    "subject": "Cron job",
                    "evidence": "nightly cron",
                },
            ]
        },
        brief,
    )
    assert [row["id"] for row in findings] == ["date_ambiguity"]
    assert findings[0]["evidence"]["quote"] == "scheduled date"
    assert pending_contract_clarification([], findings, {}) is None
