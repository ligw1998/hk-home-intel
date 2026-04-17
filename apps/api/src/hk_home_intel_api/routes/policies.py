from datetime import date

from fastapi import APIRouter, Query
from pydantic import BaseModel

from hk_home_intel_domain.policies import TaxEstimateBreakdown, estimate_hk_residential_tax

router = APIRouter(prefix="/policies", tags=["policies"])


class TaxEstimateBreakdownResponse(BaseModel):
    name: str
    amount_hkd: float
    note: str


class TaxEstimateResponse(BaseModel):
    price_hkd: float
    transaction_date: str
    buyer_profile: str
    avd_hkd: float
    total_tax_hkd: float
    total_acquisition_cost_hkd: float
    rule_version: str
    explanation: str
    assumptions: list[str]
    source_urls: list[str]
    breakdown: list[TaxEstimateBreakdownResponse]


@router.get("/tax-estimate", response_model=TaxEstimateResponse)
def tax_estimate(
    price_hkd: float = Query(ge=0),
    buyer_profile: str = Query(default="hk_individual_residential"),
    transaction_date: date = Query(default_factory=date.today),
) -> TaxEstimateResponse:
    result = estimate_hk_residential_tax(
        price_hkd=price_hkd,
        transaction_date=transaction_date,
        buyer_profile=buyer_profile,
    )
    return TaxEstimateResponse(
        price_hkd=result.price_hkd,
        transaction_date=result.transaction_date.isoformat(),
        buyer_profile=result.buyer_profile,
        avd_hkd=result.avd_hkd,
        total_tax_hkd=result.total_tax_hkd,
        total_acquisition_cost_hkd=result.total_acquisition_cost_hkd,
        rule_version=result.rule_version,
        explanation=result.explanation,
        assumptions=result.assumptions,
        source_urls=result.source_urls,
        breakdown=[
            TaxEstimateBreakdownResponse(
                name=item.name,
                amount_hkd=item.amount_hkd,
                note=item.note,
            )
            for item in result.breakdown
        ],
    )
