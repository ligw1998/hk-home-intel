import type { DevelopmentSummary, SearchPresetCriteria } from "./map-types";

export const DEFAULT_MAX_AGE_YEARS = "10";
export const DEFAULT_SEGMENTS = ["new", "first_hand_remaining", "second_hand", "mixed"];
export const SUGGESTED_BEDROOM_VALUES = [2, 3, 1, 0];
export const MARKET_TYPE_OPTIONS = [
  { value: "primary_market", label: "Primary market" },
  { value: "second_hand", label: "Second-hand" },
  { value: "mixed", label: "Mixed" },
] as const;

const MARKET_TYPE_SEGMENTS: Record<string, string[]> = {
  primary_market: ["new", "first_hand_remaining"],
  second_hand: ["second_hand"],
  mixed: ["mixed"],
};

export function formatPrice(amount: number | null): string {
  if (amount === null) {
    return "TBD";
  }
  return new Intl.NumberFormat("en-HK", {
    style: "currency",
    currency: "HKD",
    maximumFractionDigits: 0,
  }).format(amount);
}

export function buildWhyNow(item: DevelopmentSummary): string {
  const reasons: string[] = [];
  if (item.active_listing_count >= 5) {
    reasons.push("盘面活跃");
  } else if (item.active_listing_count > 0) {
    reasons.push("已有在售盘源");
  }
  if (
    item.active_listing_min_price_hkd !== null &&
    item.active_listing_min_price_hkd >= 8_000_000 &&
    item.active_listing_min_price_hkd <= 18_000_000
  ) {
    reasons.push("最低叫价落在目标价值带内");
  }
  if (item.active_listing_bedroom_options.includes(2)) {
    reasons.push("有 2 房信号");
  } else if (item.active_listing_bedroom_options.includes(3)) {
    reasons.push("有 3 房信号");
  } else if (item.active_listing_bedroom_options.includes(1)) {
    reasons.push("有 1 房信号");
  } else if (item.active_listing_bedroom_options.includes(0)) {
    reasons.push("至少有开放式信号");
  }
  if (item.active_listing_saleable_area_values.some((value) => value >= 400 && value <= 750)) {
    reasons.push("已有 400-750 尺户型");
  }
  if (item.listing_segment === "new" || item.listing_segment === "first_hand_remaining") {
    reasons.push("属于新盘 / 一手范围");
  } else if (item.age_years !== null && item.age_years <= 10) {
    reasons.push("楼龄仍在优先窗口内");
  }
  return reasons.length > 0 ? `${reasons.slice(0, 3).join("，")}。` : "目前更适合作为待观察地图点。";
}

export function toggleStringValue(values: string[], value: string): string[] {
  if (values.includes(value)) {
    return values.filter((item) => item !== value);
  }
  return [...values, value];
}

export function marketTypesFromSegments(segments: string[]): string[] {
  const types: string[] = [];
  if (segments.includes("new") || segments.includes("first_hand_remaining")) {
    types.push("primary_market");
  }
  if (segments.includes("second_hand")) {
    types.push("second_hand");
  }
  if (segments.includes("mixed")) {
    types.push("mixed");
  }
  return types;
}

export function segmentsFromMarketTypes(marketTypes: string[]): string[] {
  const segments = new Set<string>();
  for (const marketType of marketTypes) {
    for (const segment of MARKET_TYPE_SEGMENTS[marketType] ?? []) {
      segments.add(segment);
    }
  }
  return Array.from(segments);
}

export function toggleNumberValue(values: number[], value: number): number[] {
  if (values.includes(value)) {
    return values.filter((item) => item !== value);
  }
  return [...values, value];
}

export function buildCriteriaFromState(input: {
  region: string;
  district: string;
  search: string;
  segments: string[];
  minBudgetHkd: string;
  maxBudgetHkd: string;
  bedroomValues: number[];
  minSaleableAreaSqft: string;
  maxSaleableAreaSqft: string;
  maxAgeYears: string;
  watchlistOnly: boolean;
}): SearchPresetCriteria {
  return {
    region: input.region === "all" ? null : input.region,
    district: input.district === "all" ? null : input.district,
    search: input.search.trim() || null,
    listing_segments: input.segments,
    min_budget_hkd: input.minBudgetHkd === "" ? null : Number(input.minBudgetHkd),
    max_budget_hkd: input.maxBudgetHkd === "" ? null : Number(input.maxBudgetHkd),
    bedroom_values: input.bedroomValues,
    min_saleable_area_sqft:
      input.minSaleableAreaSqft === "" ? null : Number(input.minSaleableAreaSqft),
    max_saleable_area_sqft:
      input.maxSaleableAreaSqft === "" ? null : Number(input.maxSaleableAreaSqft),
    max_age_years: input.maxAgeYears === "" ? null : Number(input.maxAgeYears),
    watchlist_only: input.watchlistOnly,
  };
}

export function applyPresetCriteria(
  criteria: SearchPresetCriteria,
  setters: {
    setRegion: (value: string) => void;
    setDistrict: (value: string) => void;
    setSearch: (value: string) => void;
    setSegments: (value: string[]) => void;
    setMinBudgetHkd: (value: string) => void;
    setMaxBudgetHkd: (value: string) => void;
    setBedroomValues: (value: number[]) => void;
    setMinSaleableAreaSqft: (value: string) => void;
    setMaxSaleableAreaSqft: (value: string) => void;
    setMaxAgeYears: (value: string) => void;
    setWatchlistOnly: (value: boolean) => void;
  },
) {
  setters.setRegion(criteria.region ?? "all");
  setters.setDistrict(criteria.district ?? "all");
  setters.setSearch(criteria.search ?? "");
  setters.setSegments(criteria.listing_segments.length > 0 ? criteria.listing_segments : DEFAULT_SEGMENTS);
  setters.setMinBudgetHkd(criteria.min_budget_hkd !== null ? String(criteria.min_budget_hkd) : "");
  setters.setMaxBudgetHkd(criteria.max_budget_hkd !== null ? String(criteria.max_budget_hkd) : "");
  setters.setBedroomValues(criteria.bedroom_values);
  setters.setMinSaleableAreaSqft(
    criteria.min_saleable_area_sqft !== null ? String(criteria.min_saleable_area_sqft) : "",
  );
  setters.setMaxSaleableAreaSqft(
    criteria.max_saleable_area_sqft !== null ? String(criteria.max_saleable_area_sqft) : "",
  );
  setters.setMaxAgeYears(criteria.max_age_years !== null ? String(criteria.max_age_years) : "");
  setters.setWatchlistOnly(criteria.watchlist_only);
}

export function coverageLabel(status: string): string {
  switch (status) {
    case "rich":
      return "Rich coverage";
    case "partial":
      return "Partial coverage";
    default:
      return "Baseline only";
  }
}
