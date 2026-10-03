"""Wave 0 — invent-outside-admit lint floor + densifier mutant."""

from __future__ import annotations

from app.ai_generate_ir_lint import invent_outside_admit_violations


def test_invent_lint_flags_domain_density_mutant() -> None:
    draft = {
        "_user_prompt": "Thin tickets Draft→Done only",
        "_ambition": "thin",
        "_document_shape": "register",
        "grain": "full_app",
        "models": [
            {
                "model": "x_ticket",
                "mode": "new",
                "source": "honesty",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_partner_id",
                        "ttype": "many2one",
                        "relation": "res.partner",
                        "source": "domain_density",
                    },
                ],
            }
        ],
        "_generate_ir": {"admitted": [], "models": []},
    }
    hits = invent_outside_admit_violations(draft)
    assert any("x_partner_id" in h and "domain_density" in h for h in hits)


def test_invent_lint_flags_uncued_model_density() -> None:
    draft = {
        "_user_prompt": "Thin tickets",
        "_ambition": "thin",
        "_document_shape": "register",
        "grain": "full_app",
        "models": [
            {
                "model": "x_ghost_pad",
                "mode": "new",
                "source": "domain_density",
                "fields": [{"name": "x_name", "ttype": "char"}],
            }
        ],
        "_generate_ir": {"admitted": [], "models": []},
    }
    hits = invent_outside_admit_violations(draft)
    assert any("model:x_ghost_pad" in h for h in hits)
