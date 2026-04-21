"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";

import { CompareToggleButton } from "../components/compare-toggle-button";
import { MoneyValue } from "../components/money-value";
import { formatListingSegment, SEGMENT_OPTIONS } from "../lib/segment";

type ShortlistItem = {
  id: string;
  source_url: string | null;
  display_name: string | null;
  district: string | null;
  region: string | null;
  completion_year: number | null;
  age_years: number | null;
  listing_segment: string;
  active_listing_count: number;
  active_listing_min_price_hkd: number | null;
  active_listing_max_price_hkd: number | null;
  active_listing_bedroom_mix: Record<string, number>;
  active_listing_saleable_area_values: number[];
  latest_listing_event_at: string | null;
  decision_score: number;
  decision_band: string;
  decision_reasons: string[];
  risk_flags: string[];
  estimated_stamp_duty_hkd: number | null;
  estimated_total_acquisition_cost_hkd: number | null;
  acquisition_gap_hkd: number | null;
  watchlist_stage: string | null;
  personal_score: number | null;
};

type ShortlistResponse = {
  profile: {
    min_budget_hkd: number;
    max_budget_hkd: number;
    bedroom_values: number[];
    min_saleable_area_sqft: number;
    max_saleable_area_sqft: number;
    max_age_years: number;
    extended_age_years: number;
    listing_segments: string[];
  };
  items: ShortlistItem[];
  total: number;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

function formatDateTime(value: string | null): string {
  if (!value) {
    return "TBD";
  }
  return new Intl.DateTimeFormat("zh-HK", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function formatBedroomMix(mix: Record<string, number>): string {
  const parts = Object.entries(mix)
    .sort(([left], [right]) => Number(left) - Number(right))
    .map(([bedrooms, count]) => (bedrooms === "0" ? `開放式 × ${count}` : `${bedrooms}房 × ${count}`));
  return parts.length > 0 ? parts.join(" / ") : "No bedroom signal yet";
}

function bandLabel(value: string): string {
  switch (value) {
    case "strong_fit":
      return "Strong fit";
    case "possible_fit":
      return "Possible fit";
    case "needs_review":
      return "Needs review";
    default:
      return "Weak fit";
  }
}

function isRecent(item: ShortlistItem): boolean {
  if (!item.latest_listing_event_at) {
    return false;
  }
  return Date.now() - new Date(item.latest_listing_event_at).getTime() <= 14 * 24 * 60 * 60 * 1000;
}

function hasPreferredBedroomSignal(item: ShortlistItem): boolean {
  return Object.keys(item.active_listing_bedroom_mix).length > 0;
}

function classifyRisk(risk: string): "coverage" | "budget" | "market" | "asset" {
  if (risk.includes("预算") || risk.includes("总买入成本") || risk.includes("叫价")) {
    return "budget";
  }
  if (risk.includes("缺少") || risk.includes("字段覆盖") || risk.includes("不完整")) {
    return "coverage";
  }
  if (risk.includes("近期") || risk.includes("热度") || risk.includes("盘面变化")) {
    return "market";
  }
  return "asset";
}

function buildWhyNow(item: ShortlistItem): string {
  const parts: string[] = [];

  if (item.latest_listing_event_at) {
    const ageMs = Date.now() - new Date(item.latest_listing_event_at).getTime();
    if (ageMs <= 7 * 24 * 60 * 60 * 1000) {
      parts.push("最近 7 天有新盘面变化");
    }
  }

  if (
    item.estimated_total_acquisition_cost_hkd !== null &&
    item.estimated_total_acquisition_cost_hkd >= 8_000_000 &&
    item.estimated_total_acquisition_cost_hkd <= 18_000_000
  ) {
    parts.push("税后总买入仍在目标预算带内");
  } else if (
    item.active_listing_min_price_hkd !== null &&
    item.active_listing_min_price_hkd >= 8_000_000 &&
    item.active_listing_min_price_hkd <= 18_000_000
  ) {
    parts.push("最低叫价位于目标价值带内");
  }

  if ("2" in item.active_listing_bedroom_mix) {
    parts.push("当前盘面有 2 房信号");
  } else if ("3" in item.active_listing_bedroom_mix) {
    parts.push("当前盘面有 3 房信号");
  } else if ("1" in item.active_listing_bedroom_mix) {
    parts.push("当前盘面至少有 1 房信号");
  } else if ("0" in item.active_listing_bedroom_mix) {
    parts.push("当前盘面至少有开放式信号");
  }

  if (item.active_listing_saleable_area_values.some((value) => value >= 400 && value <= 750)) {
    parts.push("已有 400-750 尺户型");
  }

  if (item.active_listing_count >= 5) {
    parts.push("盘面够厚，可以直接比较不同叫价");
  } else if (item.active_listing_count > 0) {
    parts.push("已有活跃盘源，可继续跟");
  }

  if (parts.length === 0) {
    return "当前更像候选观察盘，值得先补齐房型、预算或近期变化信号。";
  }
  return parts.slice(0, 3).join("，") + "。";
}

function ShortlistPageContent() {
  const searchParams = useSearchParams();
  const [items, setItems] = useState<ShortlistItem[]>([]);
  const [minBudget, setMinBudget] = useState("8000000");
  const [budget, setBudget] = useState("18000000");
  const [maxAge, setMaxAge] = useState("10");
  const [extendedAge, setExtendedAge] = useState("15");
  const [bedroomValues, setBedroomValues] = useState("2,3,1,0");
  const [minSaleableArea, setMinSaleableArea] = useState("400");
  const [maxSaleableArea, setMaxSaleableArea] = useState("750");
  const [segments, setSegments] = useState(["new", "first_hand_remaining", "second_hand"]);
  const [budgetReadyOnly, setBudgetReadyOnly] = useState(false);
  const [bedroomSignalOnly, setBedroomSignalOnly] = useState(false);
  const [recentOnly, setRecentOnly] = useState(false);
  const [bandFilter, setBandFilter] = useState(searchParams.get("band") ?? "all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setBandFilter(searchParams.get("band") ?? "all");
  }, [searchParams]);

  const filteredItems = useMemo(() => {
    return items.filter((item) => {
      if (bandFilter !== "all" && item.decision_band !== bandFilter) {
        return false;
      }
      if (budgetReadyOnly && (item.acquisition_gap_hkd ?? 0) > 0) {
        return false;
      }
      if (bedroomSignalOnly && !hasPreferredBedroomSignal(item)) {
        return false;
      }
      if (recentOnly && !isRecent(item)) {
        return false;
      }
      return true;
    });
  }, [bandFilter, bedroomSignalOnly, budgetReadyOnly, items, recentOnly]);

  const groupedItems = useMemo(() => {
    const order = ["strong_fit", "possible_fit", "needs_review", "weak_fit"];
    return order
      .map((band) => ({
        band,
        label: bandLabel(band),
        items: filteredItems.filter((item) => item.decision_band === band),
      }))
      .filter((item) => item.items.length > 0);
  }, [filteredItems]);
  const shortlistSummary = useMemo(() => {
    return {
      strong: filteredItems.filter((item) => item.decision_band === "strong_fit").length,
      budgetReady: filteredItems.filter((item) => (item.acquisition_gap_hkd ?? 0) <= 0).length,
      recent: filteredItems.filter((item) => isRecent(item)).length,
    };
  }, [filteredItems]);

  useEffect(() => {
    let cancelled = false;

    async function loadShortlist() {
      try {
        setLoading(true);
        const params = new URLSearchParams({
          lang: "zh-Hant",
          min_budget_hkd: minBudget,
          max_budget_hkd: budget,
          min_saleable_area_sqft: minSaleableArea,
          max_saleable_area_sqft: maxSaleableArea,
          max_age_years: maxAge,
          extended_age_years: extendedAge,
          bedroom_values: bedroomValues,
          listing_segments: segments.join(","),
          limit: "30",
        });
        const response = await fetch(`${API_BASE}/api/v1/shortlist?${params.toString()}`);
        if (!response.ok) {
          throw new Error(`shortlist HTTP ${response.status}`);
        }
        const payload = (await response.json()) as ShortlistResponse;
        if (!cancelled) {
          setItems(payload.items);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Unknown error");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadShortlist();
    return () => {
      cancelled = true;
    };
  }, [bedroomValues, budget, extendedAge, maxAge, maxSaleableArea, minBudget, minSaleableArea, segments]);

  return (
    <main className="page-shell">
      <section className="hero-card">
        <p className="eyebrow">Shortlist</p>
        <h1>Decision Shortlist</h1>
        <p className="lead">
          Rank developments against your current buying preferences with an explainable score, then
          review why each one looks worth seeing, what it roughly costs to buy in, and why it
          should stay on watch only.
        </p>
        <div className="hero-actions">
          <Link href="/">Back to dashboard</Link>
          <Link href="/map">Map</Link>
          <Link href="/watchlist">Watchlist</Link>
          <Link href="/compare">Compare</Link>
        </div>
      </section>

      <section className="activity-layout">
        <aside className="panel filter-panel">
          <h2>Decision Profile</h2>
          <label className="field">
            <span>Budget Floor (HKD)</span>
            <input type="number" min="0" value={minBudget} onChange={(event) => setMinBudget(event.target.value)} />
          </label>
          <label className="field">
            <span>Budget Ceiling (HKD)</span>
            <input type="number" min="0" value={budget} onChange={(event) => setBudget(event.target.value)} />
          </label>
          <label className="field">
            <span>Min Saleable Area (sqft)</span>
            <input
              type="number"
              min="0"
              value={minSaleableArea}
              onChange={(event) => setMinSaleableArea(event.target.value)}
            />
          </label>
          <label className="field">
            <span>Max Saleable Area (sqft)</span>
            <input
              type="number"
              min="0"
              value={maxSaleableArea}
              onChange={(event) => setMaxSaleableArea(event.target.value)}
            />
          </label>
          <label className="field">
            <span>Ideal Max Age</span>
            <input type="number" min="0" value={maxAge} onChange={(event) => setMaxAge(event.target.value)} />
          </label>
          <label className="field">
            <span>Extended Max Age</span>
            <input
              type="number"
              min="0"
              value={extendedAge}
              onChange={(event) => setExtendedAge(event.target.value)}
            />
          </label>
          <label className="field">
            <span>Bedroom Preference Order</span>
            <input value={bedroomValues} onChange={(event) => setBedroomValues(event.target.value)} />
          </label>
          <div className="field">
            <span>Segments</span>
            <div className="checkbox-stack">
              {SEGMENT_OPTIONS.filter((item) => item.value !== "all").map((item) => (
                <label key={item.value} className="checkbox-field">
                  <input
                    type="checkbox"
                    checked={segments.includes(item.value)}
                    onChange={() =>
                      setSegments((current) =>
                        current.includes(item.value)
                          ? current.filter((value) => value !== item.value)
                          : [...current, item.value],
                      )
                    }
                  />
                  <span>{item.label}</span>
                </label>
              ))}
            </div>
          </div>
          <p className="muted">
            Default profile follows your current preference: 800萬-1800萬、400-750呎（約 37-70 平方米）、2房优先，
            再看 3房、1房、开放式；优先新盘 / 一手，再看 10-15 年内二手。
          </p>
          <div className="field">
            <span>Decision band</span>
            <select value={bandFilter} onChange={(event) => setBandFilter(event.target.value)}>
              <option value="all">All bands</option>
              <option value="strong_fit">Strong fit</option>
              <option value="possible_fit">Possible fit</option>
              <option value="needs_review">Needs review</option>
            </select>
          </div>
          <div className="field">
            <span>Quick Decision Filters</span>
            <div className="checkbox-stack">
              <label className="checkbox-field">
                <input
                  type="checkbox"
                  checked={budgetReadyOnly}
                  onChange={(event) => setBudgetReadyOnly(event.target.checked)}
                />
                <span>Only budget-ready after tax</span>
              </label>
              <label className="checkbox-field">
                <input
                  type="checkbox"
                  checked={bedroomSignalOnly}
                  onChange={(event) => setBedroomSignalOnly(event.target.checked)}
                />
                <span>Only with bedroom signal</span>
              </label>
              <label className="checkbox-field">
                <input
                  type="checkbox"
                  checked={recentOnly}
                  onChange={(event) => setRecentOnly(event.target.checked)}
                />
                <span>Only active in last 14 days</span>
              </label>
            </div>
          </div>
        </aside>

        <section className="panel detail-span-2">
          <h2>Ranked Candidates</h2>
          {!loading && !error ? (
            <div className="compare-summary">
              <div className="compare-summary-card">
                <strong>Strong fit now</strong>
                <span>{shortlistSummary.strong} candidate(s)</span>
              </div>
              <div className="compare-summary-card">
                <strong>Budget-ready after tax</strong>
                <span>{shortlistSummary.budgetReady} candidate(s)</span>
              </div>
              <div className="compare-summary-card">
                <strong>Recent live signal</strong>
                <span>{shortlistSummary.recent} candidate(s) active in the last 14 days</span>
              </div>
            </div>
          ) : null}
          {loading ? <p className="muted">Refreshing shortlist...</p> : null}
          {error ? <p className="muted">Shortlist unavailable: {error}</p> : null}
          {!loading && !error && filteredItems.length === 0 ? (
            <p className="muted">No developments matched the current shortlist profile.</p>
          ) : null}
          {!loading && !error ? (
            <p className="muted">Showing {filteredItems.length} / {items.length} candidates after quick filters.</p>
          ) : null}
          <div className="shortlist-band-stack">
            {groupedItems.map((group) => (
              <section key={group.band} className="shortlist-band-section">
                <div className="shortlist-band-header">
                  <strong>{group.label}</strong>
                  <span>{group.items.length} candidate{group.items.length === 1 ? "" : "s"}</span>
                </div>
                <div className="development-list">
                  {group.items.map((item) => (
                    <div key={item.id} className="panel shortlist-card">
                      {(() => {
                        const coverageRisks = item.risk_flags.filter((risk) => classifyRisk(risk) === "coverage");
                        const decisionRisks = item.risk_flags.filter((risk) => classifyRisk(risk) !== "coverage");
                        return (
                          <>
                <div className="listing-event-head">
                  <strong>{item.display_name ?? item.id}</strong>
                  <span className="status-pill">Score {item.decision_score} / 100</span>
                </div>
                <span>
                  {bandLabel(item.decision_band)}
                  {" / "}
                  {item.district ?? "Unknown district"}
                  {item.region ? ` / ${item.region}` : ""}
                  {" / "}
                  {formatListingSegment(item.listing_segment)}
                </span>
                <span>
                  <MoneyValue amount={item.active_listing_min_price_hkd} />
                  {" → "}
                  <MoneyValue amount={item.active_listing_max_price_hkd} />
                  {" / "}
                  {item.active_listing_count} active listing(s)
                </span>
                <span>
                  Stamp est. <MoneyValue amount={item.estimated_stamp_duty_hkd} />
                  {" / "}
                  Total buy-in <MoneyValue amount={item.estimated_total_acquisition_cost_hkd} />
                </span>
                {item.acquisition_gap_hkd && item.acquisition_gap_hkd > 0 ? (
                  <span>Budget gap after tax <MoneyValue amount={item.acquisition_gap_hkd} /></span>
                ) : null}
                <span>{formatBedroomMix(item.active_listing_bedroom_mix)}</span>
                <span>
                  {item.age_years !== null
                    ? `${item.age_years} years`
                    : item.completion_year
                      ? `Completion ${item.completion_year}`
                      : "Age TBD"}
                  {" / "}
                  latest event {formatDateTime(item.latest_listing_event_at)}
                </span>
                <span className="decision-why-now">
                  Why now: {buildWhyNow(item)}
                </span>
                {item.watchlist_stage ? (
                  <span>
                    Watchlist / {item.watchlist_stage}
                    {item.personal_score !== null ? ` / personal ${item.personal_score}/10` : ""}
                  </span>
                ) : null}
                <div className="shortlist-reasons">
                  <div>
                    <strong>Worth seeing</strong>
                    <ul className="bullet-list">
                      {item.decision_reasons.map((reason) => (
                        <li key={reason}>{reason}</li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <strong>Decision risks</strong>
                    <ul className="bullet-list">
                      {decisionRisks.length > 0 ? (
                        decisionRisks.map((risk) => <li key={risk}>{risk}</li>)
                      ) : (
                        <li>No major decision risk flagged yet.</li>
                      )}
                    </ul>
                  </div>
                  <div>
                    <strong>Coverage gaps</strong>
                    <ul className="bullet-list">
                      {coverageRisks.length > 0 ? (
                        coverageRisks.map((risk) => <li key={risk}>{risk}</li>)
                      ) : (
                        <li>No major data gap flagged yet.</li>
                      )}
                    </ul>
                  </div>
                </div>
                <div className="hero-actions">
                  <Link href={`/developments/${item.id}`}>Open detail</Link>
                  <Link href={`/map?selected=${item.id}`}>Open in map</Link>
                  <Link href={`/compare?ids=${item.id}`}>Compare</Link>
                  <CompareToggleButton
                    developmentId={item.id}
                    developmentName={item.display_name ?? item.id}
                  />
                  {item.source_url ? (
                    <a href={item.source_url} target="_blank" rel="noreferrer">
                      Open source
                    </a>
                  ) : null}
                </div>
                          </>
                        );
                      })()}
                    </div>
                  ))}
                </div>
              </section>
            ))}
          </div>
        </section>
      </section>
    </main>
  );
}

export default function ShortlistPage() {
  return (
    <Suspense fallback={<main className="page-shell"><p className="muted">Loading shortlist...</p></main>}>
      <ShortlistPageContent />
    </Suspense>
  );
}
