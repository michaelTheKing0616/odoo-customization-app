"""Country statutory payroll packs — compute only.

Never writes hr.payslip / payment.transaction. Golden-file rates must be verified
against current law; Autopilot reports the numbers and does not file returns.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class StatutoryResult:
    country: str
    gross: float
    employee_pension: float
    employer_pension: float
    nhf: float
    paye: float
    net: float
    notes: tuple[str, ...]


def _band_tax(taxable: float, bands: tuple[tuple[float, float], ...]) -> float:
    remaining = max(taxable, 0.0)
    tax = 0.0
    for width, rate in bands:
        slice_amt = remaining if width < 0 else min(remaining, width)
        tax += slice_amt * rate
        remaining -= slice_amt
        if remaining <= 0:
            break
    return round(tax, 2)


def compute_ng(gross: float, *, basic: float | None = None) -> StatutoryResult:
    """Nigeria: pension 8/10, NHF 0.5% of gross (brief default), PIT bands + CRA.

    Rates are a sandbox fixture. Confirm against current FIRS/PENCOM/NHF before prod.
    """
    g = round(float(gross), 2)
    pension_ee = round(g * 0.08, 2)
    pension_er = round(g * 0.10, 2)
    nhf = round(g * 0.005, 2)
    cra = round(max(200_000.0, g * 0.01) + g * 0.20, 2)
    taxable = max(g - pension_ee - nhf - cra, 0.0)
    # Annual PIT bands (Finance Act style). Treat *gross* as annual for the fixture.
    paye = _band_tax(
        taxable,
        (
            (300_000.0, 0.07),
            (300_000.0, 0.11),
            (500_000.0, 0.15),
            (500_000.0, 0.19),
            (1_600_000.0, 0.21),
            (-1.0, 0.24),
        ),
    )
    net = round(g - pension_ee - nhf - paye, 2)
    notes = (
        "Fixture rates — verify FIRS PAYE, PENCOM 8/10, and NHF before filing.",
        "NHF here is 0.5% of gross as commonly briefed; some filings use 2.5% of basic.",
        "Does not write hr.payslip (Enterprise / tier-1).",
    )
    if basic is not None:
        notes = notes + (f"Basic provided ({basic}) was not used in this fixture.",)
    return StatutoryResult(
        country="NG",
        gross=g,
        employee_pension=pension_ee,
        employer_pension=pension_er,
        nhf=nhf,
        paye=paye,
        net=net,
        notes=notes,
    )


_PACKS: dict[str, Any] = {
    "NG": compute_ng,
}


def has_pack(country_code: str | None) -> bool:
    return (country_code or "").upper() in _PACKS


def compute(country_code: str | None, gross: float = 500_000.0) -> StatutoryResult | None:
    fn = _PACKS.get((country_code or "").upper())
    if fn is None:
        return None
    return fn(gross)


__all__ = ["StatutoryResult", "compute", "compute_ng", "has_pack"]
