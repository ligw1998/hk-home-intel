from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class TaxEstimateBreakdown:
    name: str
    amount_hkd: float
    note: str


@dataclass(frozen=True, slots=True)
class TaxEstimateResult:
    price_hkd: float
    transaction_date: date
    buyer_profile: str
    avd_hkd: float
    total_tax_hkd: float
    total_acquisition_cost_hkd: float
    rule_version: str
    explanation: str
    assumptions: list[str]
    breakdown: list[TaxEstimateBreakdown]
    source_urls: list[str]


IRD_AVD_FAQ_URL = "https://www.ird.gov.hk/eng/faq/avd.htm"
IRD_AVD_2025_URL = "https://www.ird.gov.hk/eng/ppr/archives/25022610.htm"


def _compute_scale_2_avd(price_hkd: float, transaction_date: date) -> tuple[float, str]:
    if transaction_date >= date(2026, 2, 26):
        if price_hkd <= 4_000_000:
            return 100.0, "scale_2_2026_residential"
        if price_hkd <= 4_323_780:
            return 100.0 + 0.20 * (price_hkd - 4_000_000), "scale_2_2026_residential"
        if price_hkd <= 4_500_000:
            return price_hkd * 0.015, "scale_2_2026_residential"
        if price_hkd <= 4_935_480:
            return 67_500.0 + 0.10 * (price_hkd - 4_500_000), "scale_2_2026_residential"
        if price_hkd <= 6_000_000:
            return price_hkd * 0.0225, "scale_2_2026_residential"
        if price_hkd <= 6_642_860:
            return 135_000.0 + 0.10 * (price_hkd - 6_000_000), "scale_2_2026_residential"
        if price_hkd <= 9_000_000:
            return price_hkd * 0.03, "scale_2_2026_residential"
        if price_hkd <= 10_080_000:
            return 270_000.0 + 0.10 * (price_hkd - 9_000_000), "scale_2_2026_residential"
        if price_hkd <= 20_000_000:
            return price_hkd * 0.0375, "scale_2_2026_residential"
        if price_hkd <= 21_739_120:
            return 750_000.0 + 0.10 * (price_hkd - 20_000_000), "scale_2_2026_residential"
        if price_hkd <= 100_000_000:
            return price_hkd * 0.0425, "scale_2_2026_residential"
        if price_hkd <= 109_574_470:
            return 4_250_000.0 + 0.30 * (price_hkd - 100_000_000), "scale_2_2026_residential"
        return price_hkd * 0.065, "scale_2_2026_residential"

    if transaction_date >= date(2025, 2, 26):
        if price_hkd <= 4_000_000:
            return 100.0, "scale_2_2025_residential"
        if price_hkd <= 4_323_780:
            return 100.0 + 0.20 * (price_hkd - 4_000_000), "scale_2_2025_residential"
        if price_hkd <= 4_500_000:
            return price_hkd * 0.015, "scale_2_2025_residential"
        if price_hkd <= 4_935_480:
            return 67_500.0 + 0.10 * (price_hkd - 4_500_000), "scale_2_2025_residential"
        if price_hkd <= 6_000_000:
            return price_hkd * 0.0225, "scale_2_2025_residential"
        if price_hkd <= 6_642_860:
            return 135_000.0 + 0.10 * (price_hkd - 6_000_000), "scale_2_2025_residential"
        if price_hkd <= 9_000_000:
            return price_hkd * 0.03, "scale_2_2025_residential"
        if price_hkd <= 10_080_000:
            return 270_000.0 + 0.10 * (price_hkd - 9_000_000), "scale_2_2025_residential"
        if price_hkd <= 20_000_000:
            return price_hkd * 0.0375, "scale_2_2025_residential"
        if price_hkd <= 21_739_120:
            return 750_000.0 + 0.10 * (price_hkd - 20_000_000), "scale_2_2025_residential"
        return price_hkd * 0.0425, "scale_2_2025_residential"

    if price_hkd <= 3_000_000:
        return 100.0, "scale_2_2023_residential"
    if price_hkd <= 3_528_240:
        return 100.0 + 0.10 * (price_hkd - 3_000_000), "scale_2_2023_residential"
    if price_hkd <= 4_500_000:
        return price_hkd * 0.015, "scale_2_2023_residential"
    if price_hkd <= 4_935_480:
        return 67_500.0 + 0.10 * (price_hkd - 4_500_000), "scale_2_2023_residential"
    if price_hkd <= 6_000_000:
        return price_hkd * 0.0225, "scale_2_2023_residential"
    if price_hkd <= 6_642_860:
        return 135_000.0 + 0.10 * (price_hkd - 6_000_000), "scale_2_2023_residential"
    if price_hkd <= 9_000_000:
        return price_hkd * 0.03, "scale_2_2023_residential"
    if price_hkd <= 10_080_000:
        return 270_000.0 + 0.10 * (price_hkd - 9_000_000), "scale_2_2023_residential"
    if price_hkd <= 20_000_000:
        return price_hkd * 0.0375, "scale_2_2023_residential"
    if price_hkd <= 21_739_120:
        return 750_000.0 + 0.10 * (price_hkd - 20_000_000), "scale_2_2023_residential"
    return price_hkd * 0.0425, "scale_2_2023_residential"


def estimate_hk_residential_tax(
    *,
    price_hkd: float,
    transaction_date: date,
    buyer_profile: str = "hk_individual_residential",
) -> TaxEstimateResult:
    avd_hkd, rule_version = _compute_scale_2_avd(price_hkd, transaction_date)
    explanation = (
        "Estimate uses Hong Kong residential AVD Scale 2 / Part 1 of Scale 1. "
        "Demand-side measures for residential property were cancelled from 28 February 2024, "
        "so this baseline focuses on AVD for a standard residential acquisition."
    )
    assumptions = [
        "This is a planning estimate for residential property only.",
        "No legal reliefs, exemptions, or special family transfer rules are applied.",
        "BSD, NRSD, and SSD are treated as cancelled from 28 February 2024 in this baseline.",
        "Legal fees, agency commission, mortgage insurance, and renovation cost are excluded.",
    ]
    breakdown = [
        TaxEstimateBreakdown(
            name="AVD",
            amount_hkd=round(avd_hkd, 2),
            note="Ad valorem stamp duty estimate based on property value band.",
        )
    ]
    total_tax_hkd = round(avd_hkd, 2)
    total_acquisition_cost_hkd = round(price_hkd + total_tax_hkd, 2)
    return TaxEstimateResult(
        price_hkd=round(price_hkd, 2),
        transaction_date=transaction_date,
        buyer_profile=buyer_profile,
        avd_hkd=total_tax_hkd,
        total_tax_hkd=total_tax_hkd,
        total_acquisition_cost_hkd=total_acquisition_cost_hkd,
        rule_version=rule_version,
        explanation=explanation,
        assumptions=assumptions,
        breakdown=breakdown,
        source_urls=[IRD_AVD_FAQ_URL, IRD_AVD_2025_URL],
    )
