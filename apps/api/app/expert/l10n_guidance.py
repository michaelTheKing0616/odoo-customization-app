"""Rule-based localization / state / governorate guidance."""

from __future__ import annotations

import re
from typing import Any

from app.expert.grounding import GroundingBundle

_L10N_TOPIC_RE = re.compile(
    r"(?i)\b("
    r"governorate|state|province|res\.country\.state|fed\.?\s*states|"
    r"localization|l10n_|capital governorate|address field"
    r")\b"
)

_COUNTRY_RE = re.compile(
    r"(?i)\b(jordan|kuwait|jo\b|kw\b|amman|capital governorate)\b"
)


def looks_like_l10n_state_question(question: str) -> bool:
    text = (question or "").strip()
    if not text:
        return False
    if not _L10N_TOPIC_RE.search(text):
        return False
    return bool(_COUNTRY_RE.search(text) or re.search(r"(?i)\bcountry\b", text))


def _version_note(version: str | None) -> str:
    v = (version or "").strip()
    if v.startswith("16"):
        return (
            "**Odoo 16.0:** Jordan governorates are **not** preloaded in `base` — expect an "
            "empty State dropdown until you add `res.country.state` rows manually."
        )
    if v.startswith(("17", "18", "19")):
        return (
            f"**Odoo {v}:** Jordan has **12 preloaded governorates** in `res.country.state` "
            "(Amman, Zarqa, Irbid, …). **Capital Governorate** is **not** a separate label — "
            "use **Amman** (`JO-AM`) for the capital region."
        )
    return (
        "**Version note:** Connect an Odoo instance so Expert filters to your server version — "
        "Jordan states were added in base from 17.0 onward."
    )


def try_rule_based_l10n_guidance(
    question: str,
    bundle: GroundingBundle,
    *,
    connection_id: str | None = None,
    client: Any | None = None,
) -> dict[str, Any] | None:
    del client
    if not looks_like_l10n_state_question(question):
        return None

    version = bundle.retrieval_version
    q = question.lower()
    lines = [
        "Odoo models regions as **`res.country.state`** records linked to **`res.country`**. "
        "Partner/company forms show a **State** dropdown only when states exist for the "
        "selected country.",
        "",
        _version_note(version),
        "",
    ]

    if re.search(r"(?i)\bcapital governorate\b", question):
        lines.extend(
            [
                "**Capital Governorate:**",
                "- **Jordan** — not shipped under that name. Default data uses **Amman** "
                "for the capital governorate. Add a custom state if your integration requires "
                "the literal label *Capital Governorate*.",
                "- **Kuwait** — not in default `base` state data; create **Capital** / "
                "**Al Asimah** manually under Fed. States if needed.",
            ]
        )
    elif "kuwait" in q or re.search(r"\bkw\b", q):
        lines.extend(
            [
                "**Kuwait (`l10n_kw`):** accounting localization is available, but **default "
                "Community base data does not preload Kuwait governorates** as states. "
                "Expect an empty State field unless you import or create `res.country.state` rows.",
            ]
        )
    elif "jordan" in q or re.search(r"\bjo\b", q):
        lines.extend(
            [
                "**Jordan (`l10n_jo`, `l10n_jo_edi`):** fiscal/e-invoicing modules do not rename "
                "base governorates. Preloaded names include **Amman**, **Zarqa**, **Irbid**, "
                "**Aqaba**, **Balqa**, **Karak**, **Ma'an**, **Mafraq**, **Madaba**, **Jerash**, "
                "**Ajloun**, **Tafileh** (17.0+).",
            ]
        )

    lines.extend(
        [
            "",
            "**Add or fix states:** Contacts → Configuration → Localization → **Fed. States**, "
            "or import CSV in a custom module.",
        ]
    )

    if connection_id:
        notable = (bundle.instance_summary or {}).get("notable_flags") or {}
        if notable.get("l10n_installed"):
            lines.append(
                "\nYour connection has **`l10n_*` modules** installed — verify live states under "
                "Developer Mode → Settings → Technical → **Countries** / **Country States**."
            )
        lines.append(
            f"\nDesigner (custom fields): `/connections/{connection_id}/designer`"
        )

    return {
        "answer_markdown": "\n".join(lines),
        "grounded": bool(connection_id and bundle.instance_summary),
        "caution_flags": ["rule_based_l10n_guidance"],
    }
