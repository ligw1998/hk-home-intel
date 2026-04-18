import Link from "next/link";

import { MoneyValue } from "../components/money-value";

type CompareDevelopmentItem = {
  id: string;
  source: string | null;
  source_url: string | null;
  display_name: string | null;
  district: string | null;
  region: string | null;
  listing_segment: string;
  source_confidence: string;
  completion_year: number | null;
  age_years: number | null;
  developer_names: string[];
  address: string | null;
  active_listing_count: number;
  active_listing_min_price_hkd: number | null;
  active_listing_max_price_hkd: number | null;
  active_listing_bedroom_options: number[];
  active_listing_bedroom_mix: Record<string, number>;
  active_listing_saleable_area_values: number[];
  active_listing_source_counts: Record<string, number>;
  latest_listing_event_at: string | null;
  current_min_price_hkd: number | null;
  current_max_price_hkd: number | null;
  overall_min_price_hkd: number | null;
  overall_max_price_hkd: number | null;
  price_history_point_count: number;
};

type CompareDevelopmentsResponse = {
  focus_development_id: string | null;
  items: CompareDevelopmentItem[];
};

type CompareSuggestionItem = {
  development: CompareDevelopmentItem;
  match_score: number;
  reasons: string[];
};

type CompareSuggestionsResponse = {
  focus_development_id: string;
  items: CompareSuggestionItem[];
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
const DEFAULT_MIN_BUDGET_HKD = 8_000_000;
const DEFAULT_BUDGET_HKD = 18_000_000;
const DEFAULT_BEDROOM_ORDER = [2, 3, 1, 0];
const DEFAULT_MAX_AGE_YEARS = 10;
const DEFAULT_EXTENDED_AGE_YEARS = 15;
const DEFAULT_MIN_SALEABLE_AREA_SQFT = 400;
const DEFAULT_MAX_SALEABLE_AREA_SQFT = 700;

type DecisionView = {
  band: string;
  score: number;
  reasons: string[];
  cautions: string[];
};

type ScoredCompareItem = {
  item: CompareDevelopmentItem;
  decision: DecisionView;
};

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
    .map(([bedrooms, count]) => {
      if (bedrooms === "0") {
        return `開放式 × ${count}`;
      }
      return `${bedrooms}房 × ${count}`;
    });
  return parts.length > 0 ? parts.join(" / ") : "No bedroom signal yet";
}

function formatSourceMix(mix: Record<string, number>): string {
  const parts = Object.entries(mix)
    .sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]))
    .map(([source, count]) => `${source} × ${count}`);
  return parts.length > 0 ? parts.join(" / ") : "No active source rows";
}

function decisionBand(score: number): string {
  if (score >= 75) {
    return "strong_fit";
  }
  if (score >= 55) {
    return "possible_fit";
  }
  if (score >= 35) {
    return "needs_review";
  }
  return "weak_fit";
}

function buildDecisionView(item: CompareDevelopmentItem): DecisionView {
  let score = 0;
  const reasons: string[] = [];
  const cautions: string[] = [];

  if (item.listing_segment === "new") {
    score += 18;
    reasons.push("新盘 / 楼花库存，符合当前优先范围。");
  } else if (item.listing_segment === "first_hand_remaining") {
    score += 16;
    reasons.push("一手余货仍在售，属于核心关注范围。");
  } else if (item.listing_segment === "second_hand") {
    score += 10;
    reasons.push("属于二手盘范围，可作为新盘和一手盘之外的替代候选。");
  } else {
    score += 12;
    reasons.push("盘面同时覆盖多种来源，可继续细看。");
  }

  if (item.current_min_price_hkd !== null) {
    if (item.current_min_price_hkd < DEFAULT_MIN_BUDGET_HKD) {
      score += 6;
      cautions.push("最低在售价低于当前目标价值带，盘质与目标盘面可能偏弱。");
    } else {
      const ratio = item.current_min_price_hkd / DEFAULT_BUDGET_HKD;
      if (ratio <= 0.8) {
        score += 30;
        reasons.push("最低在售价明显落在目标预算带内。");
      } else if (ratio <= 1.0) {
        score += 26;
        reasons.push("最低在售价位于预算上限内。");
      } else if (ratio <= 1.1) {
        score += 10;
        cautions.push("最低在售价略高于预算上限，需要更强谈价空间。");
      } else {
        cautions.push("最低在售价明显高于当前预算。");
      }
    }
  } else {
    cautions.push("当前缺少可用叫价，预算匹配度仍不够明确。");
  }

  const matchedRank = DEFAULT_BEDROOM_ORDER.findIndex((value) =>
    item.active_listing_bedroom_options.includes(value),
  );
  if (matchedRank === 0) {
    score += 22;
    reasons.push("当前盘面包含你最优先的 2 房。");
  } else if (matchedRank === 1) {
    score += 16;
    reasons.push("当前盘面包含你第二优先的 3 房。");
  } else if (matchedRank === 2) {
    score += 10;
    reasons.push("当前盘面包含你第三优先的 1 房。");
  } else if (matchedRank === 3) {
    score += 4;
    reasons.push("当前盘面至少包含开放式。");
  } else if (item.active_listing_count > 0 && item.active_listing_bedroom_options.length === 0) {
    score += 4;
    cautions.push("当前有盘源，但房型字段覆盖仍不完整。");
  } else {
    cautions.push("当前盘面未看到你优先的 2房 / 3房 / 1房 / 开放式信号。");
  }

  if (
    item.active_listing_saleable_area_values.some(
      (value) => value >= DEFAULT_MIN_SALEABLE_AREA_SQFT && value <= DEFAULT_MAX_SALEABLE_AREA_SQFT,
    )
  ) {
    score += 14;
    reasons.push(`当前盘面包含 ${DEFAULT_MIN_SALEABLE_AREA_SQFT}-${DEFAULT_MAX_SALEABLE_AREA_SQFT} 尺区间户型。`);
  } else if (item.active_listing_count > 0) {
    cautions.push(`当前盘面未见 ${DEFAULT_MIN_SALEABLE_AREA_SQFT}-${DEFAULT_MAX_SALEABLE_AREA_SQFT} 尺信号。`);
  }

  if (item.listing_segment === "new" || item.listing_segment === "first_hand_remaining") {
    score += 18;
    reasons.push("主力盘面不是二手房龄约束问题。");
  } else if (item.age_years === null) {
    cautions.push("房龄信息不完整，无法判断是否落在 10-15 年窗口内。");
  } else if (item.age_years <= DEFAULT_MAX_AGE_YEARS) {
    score += 16;
    reasons.push(`楼龄 ${item.age_years} 年，落在你优先的 ${DEFAULT_MAX_AGE_YEARS} 年内。`);
  } else if (item.age_years <= DEFAULT_EXTENDED_AGE_YEARS) {
    score += 8;
    reasons.push(`楼龄 ${item.age_years} 年，仍在 ${DEFAULT_EXTENDED_AGE_YEARS} 年扩展范围内。`);
    cautions.push("楼龄高于理想 10 年窗口。");
  } else {
    cautions.push(`楼龄 ${item.age_years} 年，已超出当前扩展范围。`);
  }

  if (item.source_confidence === "high") {
    score += 8;
    reasons.push("当前主数据可信度较高。");
  } else if (item.source_confidence === "medium") {
    score += 5;
  }

  if (item.active_listing_count >= 5) {
    score += 10;
    reasons.push("当前有多条活跃盘源，可观察盘面更充分。");
  } else if (item.active_listing_count > 0) {
    score += 6;
    reasons.push("当前有活跃盘源可供继续跟踪。");
  } else {
    cautions.push("当前缺少活跃盘源，只能先看 development 级信息。");
  }

  if (item.latest_listing_event_at) {
    const daysSince = Math.floor(
      (Date.now() - new Date(item.latest_listing_event_at).getTime()) / (1000 * 60 * 60 * 24),
    );
    if (daysSince <= 7) {
      score += 6;
      reasons.push("最近 7 天有盘面变化，适合继续跟踪。");
    } else if (daysSince > 30) {
      cautions.push("盘面变化较旧，近期热度一般。");
    }
  }

  score = Math.max(0, Math.min(100, score));
  return {
    band: decisionBand(score),
    score,
    reasons: reasons.slice(0, 4),
    cautions: cautions.slice(0, 4),
  };
}

function buildCompareSummary(items: ScoredCompareItem[]) {
  if (items.length === 0) {
    return null;
  }
  const sorted = [...items].sort((left, right) => right.decision.score - left.decision.score);
  const bestOverall = sorted[0];
  const bestBudgetFit =
    [...items]
      .filter((entry) => entry.item.current_min_price_hkd !== null)
      .sort(
        (left, right) =>
          (left.item.current_min_price_hkd ?? Number.MAX_SAFE_INTEGER) -
          (right.item.current_min_price_hkd ?? Number.MAX_SAFE_INTEGER),
      )[0] ?? null;
  const bestBedroomFit =
    [...items].sort((left, right) => {
      const leftRank = DEFAULT_BEDROOM_ORDER.findIndex((value) =>
        left.item.active_listing_bedroom_options.includes(value),
      );
      const rightRank = DEFAULT_BEDROOM_ORDER.findIndex((value) =>
        right.item.active_listing_bedroom_options.includes(value),
      );
      const normalizedLeft = leftRank === -1 ? 999 : leftRank;
      const normalizedRight = rightRank === -1 ? 999 : rightRank;
      return normalizedLeft - normalizedRight || right.decision.score - left.decision.score;
    })[0] ?? null;
  return { bestOverall, bestBudgetFit, bestBedroomFit };
}

async function fetchCompare(ids: string[]): Promise<CompareDevelopmentsResponse | null> {
  if (ids.length === 0) {
    return null;
  }
  const params = new URLSearchParams();
  for (const id of ids) {
    params.append("development_id", id);
  }
  const response = await fetch(`${API_BASE}/api/v1/compare/developments?${params.toString()}`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`compare HTTP ${response.status}`);
  }
  return (await response.json()) as CompareDevelopmentsResponse;
}

async function fetchSuggestions(id: string): Promise<CompareSuggestionsResponse | null> {
  const response = await fetch(`${API_BASE}/api/v1/compare/developments/${id}/suggestions?limit=6`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`suggestions HTTP ${response.status}`);
  }
  return (await response.json()) as CompareSuggestionsResponse;
}

export default async function ComparePage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;
  const rawIds = params.ids;
  const ids = Array.from(
    new Set(
      (Array.isArray(rawIds) ? rawIds.join(",") : rawIds ?? "")
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean),
    ),
  );

  const compare = ids.length > 0 ? await fetchCompare(ids) : null;
  const focusId = compare?.focus_development_id ?? ids[0] ?? null;
  const suggestions = focusId ? await fetchSuggestions(focusId) : null;
  const scoredItems =
    compare?.items.map((item) => ({
      item,
      decision: buildDecisionView(item),
    })) ?? [];
  const compareSummary = buildCompareSummary(scoredItems);

  return (
    <main className="page-shell">
      <section className="hero-card">
        <p className="eyebrow">Compare</p>
        <h1>Development Compare</h1>
        <p className="lead">
          Compare multiple developments side by side, then use the suggested comparables panel to
          add nearby or similarly priced stock into the same review workflow.
        </p>
        <div className="hero-actions">
          <Link href="/">Back to dashboard</Link>
          <Link href="/map">Map</Link>
          <Link href="/shortlist">Shortlist</Link>
          <Link href="/listings">Listings</Link>
          <Link href="/watchlist">Watchlist</Link>
        </div>
      </section>

      <section className="compare-layout">
        <article className="panel compare-main">
          <h2>Selected Developments</h2>
          {compareSummary ? (
            <div className="compare-summary">
              <div className="compare-summary-card">
                <strong>Current lead</strong>
                <span>{compareSummary.bestOverall.item.display_name ?? compareSummary.bestOverall.item.id}</span>
                <span>
                  {bandLabel(compareSummary.bestOverall.decision.band)}
                  {" / score "}
                  {compareSummary.bestOverall.decision.score}
                </span>
              </div>
              <div className="compare-summary-card">
                <strong>Lowest current entry</strong>
                <span>{compareSummary.bestBudgetFit?.item.display_name ?? "TBD"}</span>
                <span><MoneyValue amount={compareSummary.bestBudgetFit?.item.current_min_price_hkd ?? null} /></span>
              </div>
              <div className="compare-summary-card">
                <strong>Closest bedroom fit</strong>
                <span>{compareSummary.bestBedroomFit?.item.display_name ?? "TBD"}</span>
                <span>{formatBedroomMix(compareSummary.bestBedroomFit?.item.active_listing_bedroom_mix ?? {})}</span>
              </div>
            </div>
          ) : null}
          {compare && compare.items.length > 0 ? (
            <div className="compare-grid">
              {scoredItems.map(({ item, decision }) => (
                <article key={item.id} className="compare-card">
                  <div className="listing-event-head">
                    <strong>{item.display_name ?? item.id}</strong>
                    <span className="status-pill">{item.active_listing_count} active</span>
                  </div>
                  <span className="compare-card-meta">
                    {bandLabel(decision.band)} / score {decision.score}
                  </span>
                  <span className="compare-card-meta">
                    {item.source ?? "unknown source"}
                    {" / "}
                    {item.district ?? "Unknown district"}
                    {item.region ? ` / ${item.region}` : ""}
                  </span>
                  <dl className="kv-list compact-kv-list">
                    <div>
                      <dt>Current Band</dt>
                      <dd><MoneyValue amount={item.current_min_price_hkd} /> → <MoneyValue amount={item.current_max_price_hkd} /></dd>
                    </div>
                    <div>
                      <dt>Observed Range</dt>
                      <dd><MoneyValue amount={item.overall_min_price_hkd} /> → <MoneyValue amount={item.overall_max_price_hkd} /></dd>
                    </div>
                    <div>
                      <dt>Bedroom Mix</dt>
                      <dd>{formatBedroomMix(item.active_listing_bedroom_mix)}</dd>
                    </div>
                    <div>
                      <dt>Source Mix</dt>
                      <dd>{formatSourceMix(item.active_listing_source_counts)}</dd>
                    </div>
                    <div>
                      <dt>Completion / Age</dt>
                      <dd>{item.completion_year ?? "TBD"} / {item.age_years ?? "TBD"}</dd>
                    </div>
                    <div>
                      <dt>Latest Event</dt>
                      <dd>{formatDateTime(item.latest_listing_event_at)}</dd>
                    </div>
                    <div>
                      <dt>Developers</dt>
                      <dd>{item.developer_names.length > 0 ? item.developer_names.join(" / ") : "TBD"}</dd>
                    </div>
                  </dl>
                  <div className="shortlist-reasons">
                    <div>
                      <strong>Why it fits</strong>
                      <ul className="bullet-list">
                        {decision.reasons.length > 0 ? (
                          decision.reasons.map((reason) => <li key={reason}>{reason}</li>)
                        ) : (
                          <li>No strong fit signal yet.</li>
                        )}
                      </ul>
                    </div>
                    <div>
                      <strong>Why to be careful</strong>
                      <ul className="bullet-list">
                        {decision.cautions.length > 0 ? (
                          decision.cautions.map((risk) => <li key={risk}>{risk}</li>)
                        ) : (
                          <li>No major caution flagged yet.</li>
                        )}
                      </ul>
                    </div>
                  </div>
                  <div className="hero-actions">
                    <Link
                      href={
                        (() => {
                          const nextIds = compare.items
                            .map((row) => row.id)
                            .filter((developmentId) => developmentId !== item.id);
                          return nextIds.length > 0 ? `/compare?ids=${nextIds.join(",")}` : "/compare";
                        })()
                      }
                    >
                      Remove from compare
                    </Link>
                    <Link href={`/developments/${item.id}`}>Open detail</Link>
                    <Link href={`/listings?development_id=${item.id}`}>Focus listing feed</Link>
                    {item.source_url ? (
                      <a href={item.source_url} target="_blank" rel="noreferrer">
                        Open source page
                      </a>
                    ) : null}
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <p className="muted">
              Open this page with one or more development ids, for example
              {" "}
              <code>/compare?ids=&lt;development_id_1&gt;,&lt;development_id_2&gt;</code>.
            </p>
          )}
        </article>

        <aside className="compare-sidebar">
          <article className="panel">
            <h2>Suggested Comparables</h2>
            {suggestions && suggestions.items.length > 0 ? (
              <ul className="development-list">
                {suggestions.items.map((item) => {
                  const nextIds = Array.from(new Set([...(compare?.items.map((row) => row.id) ?? []), item.development.id]));
                  return (
                    <li key={item.development.id}>
                      <strong>{item.development.display_name ?? item.development.id}</strong>
                      <span>
                        Score {item.match_score}
                        {item.reasons.length > 0 ? ` / ${item.reasons.join(" / ")}` : ""}
                      </span>
                      <span>
                        <MoneyValue amount={item.development.current_min_price_hkd} /> → <MoneyValue amount={item.development.current_max_price_hkd} />
                      </span>
                      <div className="hero-actions">
                        <Link href={`/compare?ids=${nextIds.join(",")}`}>Add to compare</Link>
                        <Link href={`/developments/${item.development.id}`}>Open detail</Link>
                      </div>
                    </li>
                  );
                })}
              </ul>
            ) : (
              <p className="muted">
                No close comparables cleared the current scoring threshold. This usually means the
                available candidates are too far away in district, size, or asking-price band, so
                the compare engine is choosing not to show noisy matches.
              </p>
            )}
          </article>
        </aside>
      </section>
    </main>
  );
}
