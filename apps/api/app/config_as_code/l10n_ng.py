"""Nigerian localisation adoption. The accountant decides the rate."""

from __future__ import annotations


def l10n_ng_xmlid(company_id: int, code: str) -> str:
    if company_id <= 0:
        raise ValueError("company id required")
    slug = code.strip()
    if not slug or not slug.replace("_", "").isalnum():
        raise ValueError("tax code required")
    return f"account.{company_id}_l10n_ng_{slug}"


def adopt_or_refuse(existing_xmlids: set[str], company_id: int, code: str) -> str:
    """Return the existing xmlid. Never create a parallel tax."""
    xmlid = l10n_ng_xmlid(company_id, code)
    if xmlid in existing_xmlids:
        return xmlid
    raise ValueError(f"refusing to invent {xmlid}; install l10n_ng and adopt the existing tax")
