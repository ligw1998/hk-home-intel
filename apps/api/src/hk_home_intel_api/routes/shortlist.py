from datetime import date, datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from hk_home_intel_api.routes.developments import (
    DevelopmentSummary,
    _apply_filters,
    _build_listing_metrics,
    _parse_bedroom_values,
    _parse_listing_segments,
    _serialize_development,
)
from hk_home_intel_domain.enums import ListingSegment
from hk_home_intel_domain.models import Development, WatchlistItem
from hk_home_intel_domain.policies import estimate_hk_residential_tax
from hk_home_intel_shared.db import get_db_session

router = APIRouter(prefix="/shortlist", tags=["shortlist"])


class ShortlistProfileResponse(BaseModel):
    max_budget_hkd: float
    bedroom_values: list[int]
    max_age_years: int
    extended_age_years: int
    listing_segments: list[str]


class ShortlistDevelopmentItem(DevelopmentSummary):
    decision_score: int
    decision_band: str
    decision_reasons: list[str]
    risk_flags: list[str]
    estimated_stamp_duty_hkd: float | None
    estimated_total_acquisition_cost_hkd: float | None
    acquisition_gap_hkd: float | None
    watchlist_stage: str | None
    personal_score: int | None


class ShortlistResponse(BaseModel):
    profile: ShortlistProfileResponse
    items: list[ShortlistDevelopmentItem]
    total: int


def _decision_band(score: int) -> str:
    if score >= 75:
        return "strong_fit"
    if score >= 55:
        return "possible_fit"
    if score >= 35:
        return "needs_review"
    return "weak_fit"


def _score_development(
    item: DevelopmentSummary,
    *,
    max_budget_hkd: float,
    bedroom_values: list[int],
    max_age_years: int,
    extended_age_years: int,
    watchlist_item: WatchlistItem | None,
) -> tuple[int, list[str], list[str]]:
    score = 0
    reasons: list[str] = []
    risks: list[str] = []

    segment_weights = {
        ListingSegment.NEW.value: 18,
        ListingSegment.FIRST_HAND_REMAINING.value: 16,
        ListingSegment.SECOND_HAND.value: 10,
        ListingSegment.MIXED.value: 12,
    }
    score += segment_weights.get(item.listing_segment.value, 0)
    if item.listing_segment == ListingSegment.NEW:
        reasons.append("新盘 / 楼花库存，符合你优先关注的新房范围。")
    elif item.listing_segment == ListingSegment.FIRST_HAND_REMAINING:
        reasons.append("一手余货仍在售，属于你的核心关注范围。")
    elif item.listing_segment == ListingSegment.SECOND_HAND:
        reasons.append("属于二手盘范围，可作为新盘和一手盘之外的替代候选。")
    elif item.listing_segment == ListingSegment.MIXED:
        reasons.append("盘面同时覆盖多种来源，可继续细看。")

    if item.active_listing_min_price_hkd is not None:
        ratio = item.active_listing_min_price_hkd / max(max_budget_hkd, 1)
        if ratio <= 0.8:
            score += 30
            reasons.append("最低在售价明显落在预算内。")
        elif ratio <= 1.0:
            score += 26
            reasons.append("最低在售价位于预算上限内。")
        elif ratio <= 1.1:
            score += 10
            risks.append("最低在售价略高于预算上限，需要更强谈价空间。")
        else:
            risks.append("最低在售价明显高于当前预算。")
    else:
        risks.append("当前缺少可用叫价，预算匹配度仍不够明确。")

    if bedroom_values:
        matched_rank = next(
            (index for index, value in enumerate(bedroom_values) if value in item.active_listing_bedroom_options),
            None,
        )
        if matched_rank == 0:
            score += 22
            reasons.append(f"当前盘面包含你最优先的 {bedroom_values[0]} 房。")
        elif matched_rank == 1:
            score += 16
            reasons.append(f"当前盘面包含你第二优先的 {bedroom_values[1]} 房。")
        elif matched_rank == 2:
            score += 10
            reasons.append(f"当前盘面包含你第三优先的 {bedroom_values[2]} 房。")
        elif item.active_listing_count > 0 and not item.active_listing_bedroom_options:
            score += 4
            risks.append("当前有盘源，但房型字段覆盖仍不完整。")
        else:
            risks.append("当前盘面未看到你优先的 2房 / 3房 / 1房信号。")

    if item.listing_segment in {ListingSegment.NEW, ListingSegment.FIRST_HAND_REMAINING}:
        score += 18
        reasons.append("主力盘面不是二手房龄约束问题。")
    elif item.age_years is None:
        risks.append("房龄信息不完整，无法判断是否落在 10-15 年窗口内。")
    elif item.age_years <= max_age_years:
        score += 16
        reasons.append(f"楼龄 {item.age_years} 年，落在你优先的 {max_age_years} 年内。")
    elif item.age_years <= extended_age_years:
        score += 8
        reasons.append(f"楼龄 {item.age_years} 年，略高于理想值，但仍在 {extended_age_years} 年扩展范围内。")
        risks.append("楼龄高于理想 10 年窗口。")
    else:
        risks.append(f"楼龄 {item.age_years} 年，已超出当前扩展范围。")

    if item.source_confidence.value == "high":
        score += 8
        reasons.append("当前主数据可信度较高。")
    elif item.source_confidence.value == "medium":
        score += 5

    if item.active_listing_count >= 5:
        score += 10
        reasons.append("当前有多条活跃盘源，可观察盘面更充分。")
    elif item.active_listing_count > 0:
        score += 6
        reasons.append("当前有活跃盘源可供继续跟踪。")
    else:
        risks.append("当前缺少活跃盘源，只能先看 development 级信息。")

    if item.latest_listing_event_at:
        try:
            days_since_event = (datetime.now() - datetime.fromisoformat(item.latest_listing_event_at)).days
        except ValueError:
            days_since_event = None
        if days_since_event is not None:
            if days_since_event <= 7:
                score += 6
                reasons.append("最近 7 天有盘面变化，适合继续跟踪。")
            elif days_since_event <= 30:
                score += 3
            else:
                risks.append("盘面变化较旧，近期热度一般。")

    if watchlist_item is not None:
        reasons.append(f"已在 watchlist 中，当前阶段为 {watchlist_item.decision_stage.value}。")

    score = max(0, min(100, score))
    return score, reasons[:5], risks[:4]


@router.get("", response_model=ShortlistResponse)
def shortlist_developments(
    district: str | None = None,
    region: str | None = None,
    listing_segments: str | None = Query(default="new,first_hand_remaining,second_hand"),
    q: str | None = Query(default=None),
    max_budget_hkd: float = Query(default=16_000_000, ge=0),
    bedroom_values: str | None = Query(default="2,3,1"),
    max_age_years: int = Query(default=10, ge=0),
    extended_age_years: int = Query(default=15, ge=0),
    lang: str = Query(default="zh-Hant"),
    limit: int = Query(default=30, ge=1, le=100),
    session: Session = Depends(get_db_session),
) -> ShortlistResponse:
    parsed_listing_segments = _parse_listing_segments(listing_segments)
    parsed_bedroom_values = _parse_bedroom_values(bedroom_values)

    developments = session.scalars(
        _apply_filters(
            select(Development).where(Development.source.is_not(None)),
            district,
            region,
            parsed_listing_segments,
            has_coordinates=None,
        ).order_by(Development.updated_at.desc())
    ).all()

    listing_metrics = _build_listing_metrics(session, [item.id for item in developments])
    watchlist_items = {
        item.development_id: item
        for item in session.scalars(select(WatchlistItem)).all()
    }

    serialized: list[ShortlistDevelopmentItem] = []
    for development in developments:
        summary = _serialize_development(development, lang, listing_metrics)
        if q:
            haystack = " ".join(
                value
                for value in [
                    summary.display_name,
                    summary.name_zh,
                    summary.name_en,
                    summary.district,
                    summary.region,
                ]
                if value
            ).lower()
            if q.strip().lower() not in haystack:
                continue

        watchlist_item = watchlist_items.get(summary.id)
        score, reasons, risks = _score_development(
            summary,
            max_budget_hkd=max_budget_hkd,
            bedroom_values=parsed_bedroom_values,
            max_age_years=max_age_years,
            extended_age_years=extended_age_years,
            watchlist_item=watchlist_item,
        )
        tax_estimate = (
            estimate_hk_residential_tax(
                price_hkd=summary.active_listing_min_price_hkd,
                transaction_date=date.today(),
            )
            if summary.active_listing_min_price_hkd is not None
            else None
        )
        acquisition_gap_hkd = None
        if tax_estimate is not None:
            acquisition_gap_hkd = max(0.0, tax_estimate.total_acquisition_cost_hkd - max_budget_hkd)
            if acquisition_gap_hkd > 0 and acquisition_gap_hkd <= max_budget_hkd * 0.05:
                risks = [*risks, "连同印花税后，总买入成本略高于当前预算。"][:4]
            elif acquisition_gap_hkd > max_budget_hkd * 0.05:
                risks = [*risks, "连同印花税后，总买入成本明显高于当前预算。"][:4]
        serialized.append(
            ShortlistDevelopmentItem(
                **summary.model_dump(),
                decision_score=score,
                decision_band=_decision_band(score),
                decision_reasons=reasons,
                risk_flags=risks,
                estimated_stamp_duty_hkd=tax_estimate.avd_hkd if tax_estimate else None,
                estimated_total_acquisition_cost_hkd=(
                    tax_estimate.total_acquisition_cost_hkd if tax_estimate else None
                ),
                acquisition_gap_hkd=acquisition_gap_hkd,
                watchlist_stage=watchlist_item.decision_stage.value if watchlist_item else None,
                personal_score=watchlist_item.personal_score if watchlist_item else None,
            )
        )

    serialized.sort(
        key=lambda item: (
            -item.decision_score,
            item.active_listing_min_price_hkd if item.active_listing_min_price_hkd is not None else float("inf"),
            item.age_years if item.age_years is not None else 999,
            item.display_name or "",
        )
    )

    return ShortlistResponse(
        profile=ShortlistProfileResponse(
            max_budget_hkd=max_budget_hkd,
            bedroom_values=parsed_bedroom_values,
            max_age_years=max_age_years,
            extended_age_years=extended_age_years,
            listing_segments=[item.value for item in parsed_listing_segments] if parsed_listing_segments else [],
        ),
        items=serialized[:limit],
        total=len(serialized),
    )
