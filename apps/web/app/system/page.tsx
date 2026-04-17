"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

type RefreshJobRunSummary = {
  id: string;
  job_name: string;
  source: string | null;
  trigger_kind: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  summary: Record<string, unknown> | null;
  error_message: string | null;
};

type SystemOverview = {
  development_count: number;
  development_with_coordinates_count: number;
  document_count: number;
  watchlist_count: number;
  latest_job: RefreshJobRunSummary | null;
};

type SchedulerTask = {
  job_name: string;
  source: string;
  command: string;
  url: string | null;
  language: string;
  limit: number | null;
  with_details: boolean;
  detect_withdrawn: boolean;
  rotation_mode: string;
  rotation_step: number | null;
};

type SchedulerPlan = {
  name: string;
  description: string;
  guideline: string;
  auto_run: boolean;
  interval_minutes: number | null;
  last_started_at: string | null;
  last_finished_at: string | null;
  last_status: string | null;
  next_run_at: string | null;
  due_now: boolean;
  has_override: boolean;
  tasks: SchedulerTask[];
};

type RunPlanResponse = {
  status: string;
  job_id: string;
  plan: string;
  message: string;
};

type RunDuePlansResponse = {
  status: string;
  due_plan_names: string[];
  run_count: number;
  job_ids: string[];
};

type SchedulerTaskDraft = {
  job_name: string;
  limit: string;
  with_details: boolean;
  detect_withdrawn: boolean;
  rotation_mode: string;
  rotation_step: string;
};

type SchedulerPlanDraft = {
  auto_run: boolean;
  interval_minutes: string;
  tasks: SchedulerTaskDraft[];
};

type MonitorCriteria = {
  listing_segments: string[];
  max_budget_hkd: number | null;
  bedroom_values: number[];
  max_age_years: number | null;
  default_limit: number | null;
  detail_limit: number | null;
  priority_level: number;
  detail_policy: string;
};

type MonitorLatestRun = {
  id: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  summary: Record<string, unknown> | null;
  error_message: string | null;
};

type CommercialSearchMonitor = {
  id: string;
  source: string;
  name: string;
  search_url: string;
  scope_type: string;
  development_name_hint: string | null;
  district: string | null;
  region: string | null;
  note: string | null;
  is_active: boolean;
  with_details: boolean;
  detect_withdrawn: boolean;
  tags: string[];
  criteria: MonitorCriteria;
  updated_at: string;
  health_status: string;
  latest_success_at: string | null;
  latest_failure_at: string | null;
  recent_failure_count: number;
  latest_run: MonitorLatestRun | null;
};

type MonitorDraft = {
  source: string;
  name: string;
  search_url: string;
  scope_type: string;
  development_name_hint: string;
  district: string;
  region: string;
  note: string;
  is_active: boolean;
  with_details: boolean;
  detect_withdrawn: boolean;
  default_limit: string;
  detail_limit: string;
  priority_level: string;
  detail_policy: string;
};

type MonitorRecommendedConfig = {
  with_details: boolean;
  default_limit: string;
  detail_limit: string;
  priority_level: string;
  detail_policy: string;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

async function extractErrorMessage(response: Response, fallback: string): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: string };
    if (payload.detail) {
      return `${fallback}: ${payload.detail}`;
    }
  } catch {
    // Ignore JSON parse errors and fall back to status text.
  }
  return `${fallback}: HTTP ${response.status}`;
}

function formatDateTime(value: string | null): string {
  if (!value) {
    return "In progress";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat(undefined, {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(parsed);
}

function describeJob(item: RefreshJobRunSummary): string {
  if (item.job_name.startsWith("refresh_plan:")) {
    return "refresh plan wrapper";
  }
  if (item.trigger_kind === "plan") {
    return "plan task";
  }
  return item.trigger_kind;
}

function describeTask(task: SchedulerTask): string {
  const parts = [task.job_name, task.source];
  if (task.command === "srpe_refresh") {
    parts.push(task.language);
  }
  if (task.limit !== null) {
    parts.push(`limit ${task.limit}`);
  }
  if (task.with_details) {
    parts.push("with details");
  }
  if (task.detect_withdrawn) {
    parts.push("detect withdrawn");
  }
  if (task.rotation_mode === "cycle") {
    parts.push(`rotate by ${task.rotation_step ?? task.limit ?? "window"}`);
  }
  return parts.join(" / ");
}

function buildPlanDraft(plan: SchedulerPlan): SchedulerPlanDraft {
  return {
    auto_run: plan.auto_run,
    interval_minutes: plan.interval_minutes?.toString() ?? "",
      tasks: plan.tasks.map((task) => ({
        job_name: task.job_name,
        limit: task.limit?.toString() ?? "",
        with_details: task.with_details,
        detect_withdrawn: task.detect_withdrawn,
        rotation_mode: task.rotation_mode,
        rotation_step: task.rotation_step?.toString() ?? "",
      })),
  };
}

function buildMonitorDraft(item: CommercialSearchMonitor): MonitorDraft {
  return {
    source: item.source,
    name: item.name,
    search_url: item.search_url,
    scope_type: item.scope_type,
    development_name_hint: item.development_name_hint ?? "",
    district: item.district ?? "",
    region: item.region ?? "",
    note: item.note ?? "",
    is_active: item.is_active,
    with_details: item.with_details,
    detect_withdrawn: item.detect_withdrawn,
    default_limit: item.criteria.default_limit?.toString() ?? "",
    detail_limit: item.criteria.detail_limit?.toString() ?? "",
    priority_level: item.criteria.priority_level?.toString() ?? "50",
    detail_policy: item.criteria.detail_policy ?? "always",
  };
}

function monitorHealthLabel(value: string): string {
  switch (value) {
    case "healthy":
      return "healthy";
    case "warning":
      return "warning";
    case "failing":
      return "failing";
    case "stale":
      return "stale";
    case "paused":
      return "paused";
    default:
      return "never run";
  }
}

function recommendedMonitorConfig(source: string): MonitorRecommendedConfig {
  if (source === "ricacorp") {
    return {
      with_details: false,
      default_limit: "30",
      detail_limit: "",
      priority_level: "55",
      detail_policy: "never",
    };
  }
  return {
    with_details: true,
    default_limit: "20",
    detail_limit: "8",
    priority_level: "70",
    detail_policy: "priority_only",
  };
}

function monitorStrategyLabel(criteria: MonitorCriteria, withDetails: boolean): string {
  const detailMode = !withDetails
    ? "search only"
    : criteria.detail_policy === "always"
      ? "detail on every run"
      : criteria.detail_policy === "priority_only"
        ? "detail on high-priority runs"
        : "detail disabled";
  return `${detailMode} / priority ${criteria.priority_level} / search ${criteria.default_limit ?? "all"}`;
}

function sourceGuidance(source: string): string {
  if (source === "ricacorp") {
    return "Prefer broader search-page coverage and lighter refreshes. Keep detail off by default unless a source-specific parser is added later.";
  }
  return "Prefer a moderate search limit and high-priority detail enrichment. Use detail only for priority monitors to avoid slow full-page refreshes.";
}

export default function SystemPage() {
  const [overview, setOverview] = useState<SystemOverview | null>(null);
  const [jobs, setJobs] = useState<RefreshJobRunSummary[]>([]);
  const [plans, setPlans] = useState<SchedulerPlan[]>([]);
  const [planDrafts, setPlanDrafts] = useState<Record<string, SchedulerPlanDraft>>({});
  const [monitors, setMonitors] = useState<CommercialSearchMonitor[]>([]);
  const [monitorDrafts, setMonitorDrafts] = useState<Record<string, MonitorDraft>>({});
  const [newMonitor, setNewMonitor] = useState<MonitorDraft>({
    source: "centanet",
    name: "",
    search_url: "",
    scope_type: "custom",
    development_name_hint: "",
    district: "",
    region: "",
    note: "",
    is_active: true,
    with_details: true,
    detect_withdrawn: false,
    default_limit: "20",
    detail_limit: "10",
    priority_level: "50",
    detail_policy: "always",
  });
  const [runningPlan, setRunningPlan] = useState<string | null>(null);
  const [runningMonitor, setRunningMonitor] = useState<string | null>(null);
  const [runningJobId, setRunningJobId] = useState<string | null>(null);
  const [runningDuePlans, setRunningDuePlans] = useState(false);
  const [info, setInfo] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadSystem() {
      try {
        const [overviewResponse, jobsResponse, plansResponse, monitorsResponse] = await Promise.all([
          fetch(`${API_BASE}/api/v1/system/overview`),
          fetch(`${API_BASE}/api/v1/system/refresh-jobs?limit=10`),
          fetch(`${API_BASE}/api/v1/system/scheduler-plans`),
          fetch(`${API_BASE}/api/v1/commercial-search-monitors`),
        ]);
        if (!overviewResponse.ok) {
          throw new Error(`overview HTTP ${overviewResponse.status}`);
        }
        if (!jobsResponse.ok) {
          throw new Error(`jobs HTTP ${jobsResponse.status}`);
        }
        if (!plansResponse.ok) {
          throw new Error(`plans HTTP ${plansResponse.status}`);
        }
        if (!monitorsResponse.ok) {
          throw new Error(`monitors HTTP ${monitorsResponse.status}`);
        }

        const overviewPayload = (await overviewResponse.json()) as SystemOverview;
        const jobsPayload = (await jobsResponse.json()) as RefreshJobRunSummary[];
        const plansPayload = (await plansResponse.json()) as SchedulerPlan[];
        const monitorsPayload = (await monitorsResponse.json()) as CommercialSearchMonitor[];
        if (!cancelled) {
          setOverview(overviewPayload);
          setJobs(jobsPayload);
          setPlans(plansPayload);
          setPlanDrafts(Object.fromEntries(plansPayload.map((plan) => [plan.name, buildPlanDraft(plan)])));
          setMonitors(monitorsPayload);
          setMonitorDrafts(
            Object.fromEntries(monitorsPayload.map((item) => [item.id, buildMonitorDraft(item)])),
          );
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Unknown error");
        }
      }
    }

    loadSystem();
    return () => {
      cancelled = true;
    };
  }, []);

  async function reloadSystem() {
    const [overviewResponse, jobsResponse, plansResponse, monitorsResponse] = await Promise.all([
      fetch(`${API_BASE}/api/v1/system/overview`),
      fetch(`${API_BASE}/api/v1/system/refresh-jobs?limit=10`),
      fetch(`${API_BASE}/api/v1/system/scheduler-plans`),
      fetch(`${API_BASE}/api/v1/commercial-search-monitors`),
    ]);
    if (!overviewResponse.ok || !jobsResponse.ok || !plansResponse.ok || !monitorsResponse.ok) {
      throw new Error("system reload failed");
    }
    setOverview((await overviewResponse.json()) as SystemOverview);
    const nextJobs = (await jobsResponse.json()) as RefreshJobRunSummary[];
    setJobs(nextJobs);
    const nextPlans = (await plansResponse.json()) as SchedulerPlan[];
    setPlans(nextPlans);
    setPlanDrafts(Object.fromEntries(nextPlans.map((plan) => [plan.name, buildPlanDraft(plan)])));
    const nextMonitors = (await monitorsResponse.json()) as CommercialSearchMonitor[];
    setMonitors(nextMonitors);
    setMonitorDrafts(Object.fromEntries(nextMonitors.map((item) => [item.id, buildMonitorDraft(item)])));
    return nextJobs;
  }

  useEffect(() => {
    if (!runningJobId) {
      return;
    }

    const timer = window.setInterval(async () => {
      try {
        const nextJobs = await reloadSystem();
        const target = nextJobs.find((item) => item.id === runningJobId);
        if (!target) {
          return;
        }
        if (target.status !== "running") {
          setRunningJobId(null);
          setRunningPlan(null);
          setRunningMonitor(null);
          setInfo(
            target.status === "succeeded"
              ? `Plan run finished: ${target.job_name}`
              : `Plan run failed: ${target.job_name}`,
          );
        }
      } catch {
        // Keep polling; page-level error is already handled elsewhere.
      }
    }, 2000);

    return () => window.clearInterval(timer);
  }, [runningJobId]);

  function renderJobSummary(item: RefreshJobRunSummary) {
    if (item.summary) {
      return (
        <pre className="job-summary">
          {JSON.stringify(item.summary, null, 2)}
        </pre>
      );
    }
    if (item.error_message) {
      return <pre className="job-summary">{item.error_message}</pre>;
    }
    return null;
  }

  async function runPlan(planName: string) {
    setRunningPlan(planName);
    setInfo(`Submitting plan ${planName}...`);
    try {
      const response = await fetch(`${API_BASE}/api/v1/system/run-plan`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ plan_name: planName }),
      });
      if (!response.ok) {
        throw new Error(await extractErrorMessage(response, "run-plan failed"));
      }
      const payload = (await response.json()) as RunPlanResponse;
      setRunningJobId(payload.job_id);
      setInfo(`${payload.message} Job ${payload.job_id} is now running.`);
      await reloadSystem();
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
      setInfo(null);
      setRunningPlan(null);
      setRunningJobId(null);
    }
  }

  async function runDuePlans() {
    setRunningDuePlans(true);
    setInfo("Checking and running due plans...");
    try {
      const response = await fetch(`${API_BASE}/api/v1/system/run-due-plans`, {
        method: "POST",
      });
      if (!response.ok) {
        throw new Error(await extractErrorMessage(response, "run-due-plans failed"));
      }
      const payload = (await response.json()) as RunDuePlansResponse;
      await reloadSystem();
      if (payload.run_count === 0) {
        setInfo("No scheduler plans are currently due.");
      } else {
        setInfo(`Started ${payload.run_count} due plan(s): ${payload.due_plan_names.join(", ")}`);
        if (payload.job_ids.length === 1) {
          setRunningJobId(payload.job_ids[0]);
        }
      }
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
      setInfo(null);
    } finally {
      setRunningDuePlans(false);
    }
  }

  function updatePlanDraft(planName: string, patch: Partial<SchedulerPlanDraft>) {
    setPlanDrafts((current) => ({
      ...current,
      [planName]: {
        ...(current[planName] ?? { auto_run: false, interval_minutes: "", tasks: [] }),
        ...patch,
      },
    }));
  }

  function updateTaskDraft(
    planName: string,
    taskJobName: string,
    patch: Partial<SchedulerTaskDraft>,
  ) {
    setPlanDrafts((current) => {
      const existing = current[planName];
      if (!existing) {
        return current;
      }
      return {
        ...current,
        [planName]: {
          ...existing,
          tasks: existing.tasks.map((task) =>
            task.job_name === taskJobName ? { ...task, ...patch } : task,
          ),
        },
      };
    });
  }

  async function savePlanConfig(planName: string) {
    const draft = planDrafts[planName];
    if (!draft) {
      return;
    }
    setRunningPlan(planName);
    setInfo(`Saving plan override for ${planName}...`);
    try {
      const response = await fetch(`${API_BASE}/api/v1/system/scheduler-plans/${planName}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          auto_run: draft.auto_run,
          interval_minutes: draft.interval_minutes === "" ? null : Number(draft.interval_minutes),
          task_overrides: draft.tasks.map((task) => ({
            job_name: task.job_name,
            limit: task.limit === "" ? null : Number(task.limit),
            with_details: task.with_details,
            detect_withdrawn: task.detect_withdrawn,
            rotation_mode: task.rotation_mode,
            rotation_step: task.rotation_step === "" ? null : Number(task.rotation_step),
          })),
        }),
      });
      if (!response.ok) {
        throw new Error(await extractErrorMessage(response, "scheduler override failed"));
      }
      await reloadSystem();
      setInfo(`Saved plan override for ${planName}.`);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
      setInfo(null);
    } finally {
      setRunningPlan(null);
    }
  }

  async function resetPlanConfig(planName: string) {
    setRunningPlan(planName);
    setInfo(`Resetting override for ${planName}...`);
    try {
      const response = await fetch(`${API_BASE}/api/v1/system/scheduler-plans/${planName}/override`, {
        method: "DELETE",
      });
      if (!response.ok) {
        throw new Error(await extractErrorMessage(response, "scheduler reset failed"));
      }
      await reloadSystem();
      setInfo(`Reset override for ${planName}.`);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
      setInfo(null);
    } finally {
      setRunningPlan(null);
    }
  }

  function updateMonitorDraft(monitorId: string, patch: Partial<MonitorDraft>) {
    setMonitorDrafts((current) => ({
      ...current,
      [monitorId]: {
        ...(current[monitorId] ?? {
          source: "centanet",
          name: "",
          search_url: "",
          scope_type: "custom",
          development_name_hint: "",
          district: "",
          region: "",
          note: "",
          is_active: true,
          with_details: true,
          detect_withdrawn: false,
          default_limit: "",
          detail_limit: "",
          priority_level: "50",
          detail_policy: "always",
        }),
        ...patch,
      },
    }));
  }

  function applyRecommendedConfigToNewMonitor() {
    setNewMonitor((current) => ({ ...current, ...recommendedMonitorConfig(current.source) }));
  }

  function applyRecommendedConfigToDraft(monitorId: string, source: string) {
    updateMonitorDraft(monitorId, recommendedMonitorConfig(source));
  }

  async function createMonitor() {
    setRunningMonitor("create");
    setInfo("Creating commercial search monitor...");
    try {
      const response = await fetch(`${API_BASE}/api/v1/commercial-search-monitors`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source: newMonitor.source,
          name: newMonitor.name,
          search_url: newMonitor.search_url,
          scope_type: newMonitor.scope_type,
          development_name_hint: newMonitor.development_name_hint || null,
          district: newMonitor.district || null,
          region: newMonitor.region || null,
          note: newMonitor.note || null,
          is_active: newMonitor.is_active,
          with_details: newMonitor.with_details,
          detect_withdrawn: newMonitor.detect_withdrawn,
          tags: [],
          criteria: {
            listing_segments: [],
            max_budget_hkd: null,
            bedroom_values: [],
            max_age_years: null,
            default_limit: newMonitor.default_limit === "" ? null : Number(newMonitor.default_limit),
            detail_limit: newMonitor.detail_limit === "" ? null : Number(newMonitor.detail_limit),
            priority_level: newMonitor.priority_level === "" ? 50 : Number(newMonitor.priority_level),
            detail_policy: newMonitor.detail_policy,
          },
        }),
      });
      if (!response.ok) {
        throw new Error(await extractErrorMessage(response, "create monitor failed"));
      }
      await reloadSystem();
      setNewMonitor({
        source: "centanet",
        name: "",
        search_url: "",
        scope_type: "custom",
        development_name_hint: "",
        district: "",
        region: "",
        note: "",
        is_active: true,
        with_details: true,
        detect_withdrawn: false,
        default_limit: "20",
        detail_limit: "10",
        priority_level: "50",
        detail_policy: "always",
      });
      setInfo("Commercial search monitor created.");
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
      setInfo(null);
    } finally {
      setRunningMonitor(null);
    }
  }

  async function saveMonitor(monitorId: string) {
    const draft = monitorDrafts[monitorId];
    if (!draft) {
      return;
    }
    setRunningMonitor(monitorId);
    setInfo(`Saving monitor ${draft.name}...`);
    try {
      const response = await fetch(`${API_BASE}/api/v1/commercial-search-monitors/${monitorId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source: draft.source,
          name: draft.name,
          search_url: draft.search_url,
          scope_type: draft.scope_type,
          development_name_hint: draft.development_name_hint || null,
          district: draft.district || null,
          region: draft.region || null,
          note: draft.note || null,
          is_active: draft.is_active,
          with_details: draft.with_details,
          detect_withdrawn: draft.detect_withdrawn,
          tags: [],
          criteria: {
            listing_segments: [],
            max_budget_hkd: null,
            bedroom_values: [],
            max_age_years: null,
            default_limit: draft.default_limit === "" ? null : Number(draft.default_limit),
            detail_limit: draft.detail_limit === "" ? null : Number(draft.detail_limit),
            priority_level: draft.priority_level === "" ? 50 : Number(draft.priority_level),
            detail_policy: draft.detail_policy,
          },
        }),
      });
      if (!response.ok) {
        throw new Error(await extractErrorMessage(response, "save monitor failed"));
      }
      await reloadSystem();
      setInfo(`Saved monitor ${draft.name}.`);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
      setInfo(null);
    } finally {
      setRunningMonitor(null);
    }
  }

  async function deleteMonitor(monitorId: string) {
    setRunningMonitor(monitorId);
    setInfo("Deleting commercial search monitor...");
    try {
      const response = await fetch(`${API_BASE}/api/v1/commercial-search-monitors/${monitorId}`, {
        method: "DELETE",
      });
      if (!response.ok) {
        throw new Error(await extractErrorMessage(response, "delete monitor failed"));
      }
      await reloadSystem();
      setInfo("Commercial search monitor deleted.");
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
      setInfo(null);
    } finally {
      setRunningMonitor(null);
    }
  }

  async function runMonitor(monitorId: string) {
    setRunningMonitor(monitorId);
    setInfo("Submitting commercial search monitor...");
    try {
      const response = await fetch(`${API_BASE}/api/v1/commercial-search-monitors/${monitorId}/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      if (!response.ok) {
        throw new Error(await extractErrorMessage(response, "run monitor failed"));
      }
      const payload = (await response.json()) as RunPlanResponse;
      setRunningJobId(payload.job_id);
      await reloadSystem();
      setInfo(`Commercial monitor started. Job ${payload.job_id} is now running.`);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
      setInfo(null);
      setRunningMonitor(null);
      setRunningJobId(null);
    }
  }

  async function runMonitorBatch(source: string) {
    setRunningMonitor(`batch:${source}`);
    setInfo(`Submitting active ${source} monitors...`);
    try {
      const response = await fetch(`${API_BASE}/api/v1/commercial-search-monitors/run-batch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source, active_only: true }),
      });
      if (!response.ok) {
        throw new Error(await extractErrorMessage(response, "run monitor batch failed"));
      }
      const payload = (await response.json()) as RunPlanResponse;
      setRunningJobId(payload.job_id);
      await reloadSystem();
      setInfo(`Active ${source} monitor batch started. Job ${payload.job_id} is now running.`);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
      setInfo(null);
      setRunningMonitor(null);
      setRunningJobId(null);
    }
  }

  return (
    <main className="page-shell">
      <section className="hero-card">
        <p className="eyebrow">System Monitor</p>
        <h1>System Monitor</h1>
        <p className="lead">
          Track refresh runs, basic dataset volume, and the last ingestion result before a fuller
          scheduler and job orchestration layer lands.
        </p>
        <div className="hero-actions">
          <Link href="/">Back to dashboard</Link>
          <Link href="/activity">Open activity</Link>
          <Link href="/map">Open map</Link>
          <Link href="/shortlist">Open shortlist</Link>
          <Link href="/watchlist">Open watchlist</Link>
          <button
            type="button"
            className="action-button"
            onClick={() => void runDuePlans()}
            disabled={runningPlan !== null || runningDuePlans}
          >
            {runningDuePlans ? "Running due plans..." : "Run due auto plans"}
          </button>
        </div>
        {info ? <p className="muted">{info}</p> : null}
        {error ? <p className="muted">Error: {error}</p> : null}
      </section>

      <section className="grid">
        <article className="panel">
          <h2>Overview</h2>
          {overview ? (
            <dl className="kv-list">
              <div>
                <dt>Developments</dt>
                <dd>{overview.development_count}</dd>
              </div>
              <div>
                <dt>With Coordinates</dt>
                <dd>{overview.development_with_coordinates_count}</dd>
              </div>
              <div>
                <dt>Documents</dt>
                <dd>{overview.document_count}</dd>
              </div>
              <div>
                <dt>Watchlist</dt>
                <dd>{overview.watchlist_count}</dd>
              </div>
              <div>
                <dt>Latest Job</dt>
                <dd>{overview.latest_job?.status ?? "No jobs yet"}</dd>
              </div>
            </dl>
          ) : (
            <p className="muted">{error ? `System unavailable: ${error}` : "Loading overview..."}</p>
          )}
        </article>

        <article className="panel detail-span-2">
          <h2>Recent Refresh Jobs</h2>
          {jobs.length > 0 ? (
            <ul className="development-list">
              {jobs.map((item) => (
                <li key={item.id}>
                  <strong>
                    {item.job_name} / {item.status}
                  </strong>
                  <span>
                    {item.source ?? "unknown source"} / {describeJob(item)}
                  </span>
                  <span>
                    {formatDateTime(item.started_at)} to {formatDateTime(item.finished_at)}
                  </span>
                  {(item.summary || item.error_message) ? (
                    <details className="plan-guideline" open={item.status === "failed"}>
                      <summary>Run details</summary>
                      {renderJobSummary(item)}
                    </details>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">No refresh jobs recorded yet.</p>
          )}
        </article>

        <article className="panel detail-span-2">
          <h2>Configured Refresh Plans</h2>
          {plans.length > 0 ? (
            <ul className="development-list">
              {plans.map((plan) => (
                <li key={plan.name}>
                  <strong>{plan.name}</strong>
                  <span>{plan.description}</span>
                  <span>{plan.has_override ? "custom override active" : "using file default"}</span>
                  <details className="plan-guideline">
                    <summary>Guideline</summary>
                    <p className="muted">{plan.guideline}</p>
                    <p className="muted">
                      Config file:
                      {" "}
                      <code>configs/scheduler.toml</code>
                    </p>
                  </details>
                  <span>
                    {plan.auto_run
                      ? `auto every ${plan.interval_minutes ?? "?"} min`
                      : "manual only"}
                    {plan.due_now ? " / due now" : ""}
                  </span>
                  <span>
                    Last run:
                    {" "}
                    {plan.last_started_at ? formatDateTime(plan.last_started_at) : "never"}
                    {plan.last_status ? ` / ${plan.last_status}` : ""}
                  </span>
                  <span>
                    Next run:
                    {" "}
                    {plan.next_run_at ? formatDateTime(plan.next_run_at) : "manual or not scheduled"}
                  </span>
                  <span>
                    Run with:
                    {" "}
                    <code>conda run -n py311 hhi-worker run-refresh-plan --plan {plan.name}</code>
                  </span>
                  <details className="plan-guideline">
                    <summary>Tasks & configuration</summary>
                    <div className="plan-editor">
                      <label className="checkbox-field">
                        <input
                          type="checkbox"
                          checked={planDrafts[plan.name]?.auto_run ?? plan.auto_run}
                          onChange={(event) =>
                            updatePlanDraft(plan.name, { auto_run: event.target.checked })
                          }
                        />
                        <span>Auto run</span>
                      </label>
                      <label className="field">
                        <span>Interval Minutes</span>
                        <input
                          type="number"
                          min="1"
                          value={planDrafts[plan.name]?.interval_minutes ?? ""}
                          onChange={(event) =>
                            updatePlanDraft(plan.name, { interval_minutes: event.target.value })
                          }
                        />
                      </label>
                      {(planDrafts[plan.name]?.tasks ?? []).map((task) => (
                        <div key={`${plan.name}-${task.job_name}`} className="task-editor">
                          <strong>{task.job_name}</strong>
                          <label className="field">
                            <span>Limit</span>
                            <input
                              type="number"
                              min="1"
                              value={task.limit}
                              onChange={(event) =>
                                updateTaskDraft(plan.name, task.job_name, { limit: event.target.value })
                              }
                            />
                          </label>
                          <label className="checkbox-field">
                            <input
                              type="checkbox"
                              checked={task.with_details}
                              onChange={(event) =>
                                updateTaskDraft(plan.name, task.job_name, {
                                  with_details: event.target.checked,
                                })
                              }
                            />
                            <span>With details</span>
                          </label>
                          <label className="checkbox-field">
                            <input
                              type="checkbox"
                              checked={task.detect_withdrawn}
                              onChange={(event) =>
                                updateTaskDraft(plan.name, task.job_name, {
                                  detect_withdrawn: event.target.checked,
                                })
                              }
                            />
                            <span>Detect withdrawn</span>
                          </label>
                          <label className="field">
                            <span>Rotation Mode</span>
                            <select
                              value={task.rotation_mode}
                              onChange={(event) =>
                                updateTaskDraft(plan.name, task.job_name, {
                                  rotation_mode: event.target.value,
                                })
                              }
                            >
                              <option value="none">none</option>
                              <option value="cycle">cycle</option>
                            </select>
                          </label>
                          <label className="field">
                            <span>Rotation Step</span>
                            <input
                              type="number"
                              min="1"
                              value={task.rotation_step}
                              onChange={(event) =>
                                updateTaskDraft(plan.name, task.job_name, {
                                  rotation_step: event.target.value,
                                })
                              }
                            />
                          </label>
                          {plan.tasks.find((item) => item.job_name === task.job_name)?.url ? (
                            <p className="muted">
                              Scope URL:
                              {" "}
                              <code>{plan.tasks.find((item) => item.job_name === task.job_name)?.url}</code>
                            </p>
                          ) : null}
                        </div>
                      ))}
                    </div>
                    <div className="watchlist-actions">
                      <button
                        type="button"
                        className="action-button"
                        onClick={() => void runPlan(plan.name)}
                        disabled={runningPlan !== null}
                      >
                        {runningPlan === plan.name ? "Running..." : "Run from UI"}
                      </button>
                      <button
                        type="button"
                        className="action-button"
                        onClick={() => void savePlanConfig(plan.name)}
                        disabled={runningPlan !== null || runningDuePlans}
                      >
                        {runningPlan === plan.name ? "Working..." : "Save override"}
                      </button>
                      <button
                        type="button"
                        className="action-button"
                        onClick={() => void resetPlanConfig(plan.name)}
                        disabled={runningPlan !== null || runningDuePlans}
                      >
                        Reset override
                      </button>
                    </div>
                    {runningPlan === plan.name ? (
                      <p className="muted">Plan request in progress. Watch Recent Refresh Jobs for updates.</p>
                    ) : null}
                    {plan.tasks.map((task) => (
                      <span key={`${plan.name}-${task.job_name}`}>
                        {describeTask(task)}
                      </span>
                    ))}
                  </details>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">No scheduler plans configured yet.</p>
          )}
        </article>

        <article className="panel detail-span-2">
          <h2>Commercial Search Monitors</h2>
          <p className="muted">
            Manage the Centanet search URLs you want to keep under watch. This is the monitored
            entrypoint layer that commercial-source refresh will reuse before we add more sources.
            Use <code>Default limit</code> to cap how many search results are processed per run, and
            <code>Detail limit</code> to keep HTML detail enrichment smaller than the search-page scan.
          </p>
          <details className="plan-guideline">
            <summary>Source strategy guide</summary>
            <p className="muted">
              <strong>centanet:</strong>
              {" "}
              {sourceGuidance("centanet")}
            </p>
            <p className="muted">
              <strong>ricacorp:</strong>
              {" "}
              {sourceGuidance("ricacorp")}
            </p>
            <p className="muted">
              For multi-monitor refreshes, start with moderate search limits and keep detail
              enrichment constrained to priority monitors. This keeps batches stable before you scale up.
            </p>
          </details>
          <div className="watchlist-actions">
            <button
              type="button"
              className="action-button"
              onClick={() => void runMonitorBatch("centanet")}
              disabled={runningMonitor !== null || runningPlan !== null || runningDuePlans}
            >
              {runningMonitor === "batch:centanet" ? "Running..." : "Run active Centanet monitors"}
            </button>
            <button
              type="button"
              className="action-button"
              onClick={() => void runMonitorBatch("ricacorp")}
              disabled={runningMonitor !== null || runningPlan !== null || runningDuePlans}
            >
              {runningMonitor === "batch:ricacorp" ? "Running..." : "Run active Ricacorp monitors"}
            </button>
          </div>
          <div className="plan-editor">
            <label className="field">
              <span>Source</span>
              <select
                value={newMonitor.source}
                onChange={(event) => setNewMonitor((current) => ({ ...current, source: event.target.value }))}
              >
                <option value="centanet">centanet</option>
                <option value="ricacorp">ricacorp</option>
              </select>
            </label>
            <label className="field">
              <span>Name</span>
              <input
                type="text"
                value={newMonitor.name}
                onChange={(event) => setNewMonitor((current) => ({ ...current, name: event.target.value }))}
              />
            </label>
            <label className="field">
              <span>Search URL</span>
              <input
                type="text"
                value={newMonitor.search_url}
                onChange={(event) => setNewMonitor((current) => ({ ...current, search_url: event.target.value }))}
              />
            </label>
            <label className="field">
              <span>Scope Type</span>
              <select
                value={newMonitor.scope_type}
                onChange={(event) => setNewMonitor((current) => ({ ...current, scope_type: event.target.value }))}
              >
                <option value="custom">custom</option>
                <option value="development">development</option>
                <option value="district">district</option>
              </select>
            </label>
            <label className="field">
              <span>Development Hint</span>
              <input
                type="text"
                value={newMonitor.development_name_hint}
                onChange={(event) =>
                  setNewMonitor((current) => ({ ...current, development_name_hint: event.target.value }))
                }
              />
            </label>
            <label className="field">
              <span>District</span>
              <input
                type="text"
                value={newMonitor.district}
                onChange={(event) => setNewMonitor((current) => ({ ...current, district: event.target.value }))}
              />
            </label>
            <label className="field">
              <span>Note</span>
              <input
                type="text"
                value={newMonitor.note}
                onChange={(event) => setNewMonitor((current) => ({ ...current, note: event.target.value }))}
              />
            </label>
            <label className="field">
              <span>Default limit</span>
              <input
                type="number"
                min={1}
                max={200}
                value={newMonitor.default_limit}
                onChange={(event) => setNewMonitor((current) => ({ ...current, default_limit: event.target.value }))}
              />
            </label>
            <label className="field">
              <span>Detail limit</span>
              <input
                type="number"
                min={1}
                max={100}
                value={newMonitor.detail_limit}
                onChange={(event) => setNewMonitor((current) => ({ ...current, detail_limit: event.target.value }))}
              />
            </label>
            <label className="field">
              <span>Priority</span>
              <input
                type="number"
                min={0}
                max={100}
                value={newMonitor.priority_level}
                onChange={(event) => setNewMonitor((current) => ({ ...current, priority_level: event.target.value }))}
              />
            </label>
            <label className="field">
              <span>Detail policy</span>
              <select
                value={newMonitor.detail_policy}
                onChange={(event) => setNewMonitor((current) => ({ ...current, detail_policy: event.target.value }))}
              >
                <option value="always">always</option>
                <option value="priority_only">priority only</option>
                <option value="never">never</option>
              </select>
            </label>
            <label className="checkbox-field">
              <input
                type="checkbox"
                checked={newMonitor.is_active}
                onChange={(event) => setNewMonitor((current) => ({ ...current, is_active: event.target.checked }))}
              />
              <span>Active</span>
            </label>
            <label className="checkbox-field">
              <input
                type="checkbox"
                checked={newMonitor.with_details}
                onChange={(event) =>
                  setNewMonitor((current) => ({ ...current, with_details: event.target.checked }))
                }
              />
              <span>With details</span>
            </label>
            <label className="checkbox-field">
              <input
                type="checkbox"
                checked={newMonitor.detect_withdrawn}
                onChange={(event) =>
                  setNewMonitor((current) => ({ ...current, detect_withdrawn: event.target.checked }))
                }
              />
              <span>Detect withdrawn</span>
            </label>
          </div>
          <div className="watchlist-actions">
            <button
              type="button"
              className="action-button"
              onClick={applyRecommendedConfigToNewMonitor}
              disabled={runningMonitor !== null || runningPlan !== null || runningDuePlans}
            >
              Apply recommended defaults
            </button>
            <button
              type="button"
              className="action-button"
              onClick={() => void createMonitor()}
              disabled={runningMonitor !== null || !newMonitor.name || !newMonitor.search_url}
            >
              {runningMonitor === "create" ? "Creating..." : "Add monitor"}
            </button>
          </div>
          {monitors.length > 0 ? (
            <ul className="development-list">
              {monitors.map((monitor) => {
                const draft = monitorDrafts[monitor.id] ?? buildMonitorDraft(monitor);
                return (
                  <li key={monitor.id}>
                    <strong>{monitor.name}</strong>
                    <span>{monitor.source} / {monitor.scope_type}{monitor.is_active ? " / active" : " / paused"}</span>
                    <span>
                      Health:
                      {" "}
                      {monitorHealthLabel(monitor.health_status)}
                      {monitor.recent_failure_count > 0 ? ` / recent failures ${monitor.recent_failure_count}` : ""}
                    </span>
                    <span>
                      Last run:
                      {" "}
                      {monitor.latest_run ? `${formatDateTime(monitor.latest_run.started_at)} / ${monitor.latest_run.status}` : "never"}
                    </span>
                    <span>
                      Last success:
                      {" "}
                      {monitor.latest_success_at ? formatDateTime(monitor.latest_success_at) : "never"}
                      {" / "}
                      Last failure:
                      {" "}
                      {monitor.latest_failure_at ? formatDateTime(monitor.latest_failure_at) : "never"}
                    </span>
                    <span>
                      Default limit:
                      {" "}
                      {monitor.criteria.default_limit ?? "all"}
                      {" / "}
                      Detail limit:
                      {" "}
                      {monitor.criteria.detail_limit ?? "all"}
                      {" / "}
                      Priority:
                      {" "}
                      {monitor.criteria.priority_level}
                      {" / "}
                      Detail policy:
                      {" "}
                      {monitor.criteria.detail_policy}
                    </span>
                    <span>
                      Strategy:
                      {" "}
                      {monitorStrategyLabel(monitor.criteria, monitor.with_details)}
                    </span>
                    <span>
                      URL:
                      {" "}
                      <code>{monitor.search_url}</code>
                    </span>
                    {monitor.latest_run?.summary ? (
                      <details className="plan-guideline" open={monitor.health_status === "failing"}>
                        <summary>Latest run summary</summary>
                        <pre className="job-summary">{JSON.stringify(monitor.latest_run.summary, null, 2)}</pre>
                      </details>
                    ) : null}
                    <div className="plan-editor">
                      <label className="field">
                        <span>Source</span>
                        <select
                          value={draft.source}
                          onChange={(event) => updateMonitorDraft(monitor.id, { source: event.target.value })}
                        >
                          <option value="centanet">centanet</option>
                          <option value="ricacorp">ricacorp</option>
                        </select>
                      </label>
                      <label className="field">
                        <span>Name</span>
                        <input
                          type="text"
                          value={draft.name}
                          onChange={(event) => updateMonitorDraft(monitor.id, { name: event.target.value })}
                        />
                      </label>
                      <label className="field">
                        <span>Search URL</span>
                        <input
                          type="text"
                          value={draft.search_url}
                          onChange={(event) => updateMonitorDraft(monitor.id, { search_url: event.target.value })}
                        />
                      </label>
                      <label className="field">
                        <span>Scope Type</span>
                        <select
                          value={draft.scope_type}
                          onChange={(event) => updateMonitorDraft(monitor.id, { scope_type: event.target.value })}
                        >
                          <option value="custom">custom</option>
                          <option value="development">development</option>
                          <option value="district">district</option>
                        </select>
                      </label>
                      <label className="field">
                        <span>Development Hint</span>
                        <input
                          type="text"
                          value={draft.development_name_hint}
                          onChange={(event) =>
                            updateMonitorDraft(monitor.id, { development_name_hint: event.target.value })
                          }
                        />
                      </label>
                      <label className="field">
                        <span>District</span>
                        <input
                          type="text"
                          value={draft.district}
                          onChange={(event) => updateMonitorDraft(monitor.id, { district: event.target.value })}
                        />
                      </label>
                      <label className="field">
                        <span>Note</span>
                        <input
                          type="text"
                          value={draft.note}
                          onChange={(event) => updateMonitorDraft(monitor.id, { note: event.target.value })}
                        />
                      </label>
                      <label className="field">
                        <span>Default limit</span>
                        <input
                          type="number"
                          min={1}
                          max={200}
                          value={draft.default_limit}
                          onChange={(event) => updateMonitorDraft(monitor.id, { default_limit: event.target.value })}
                        />
                      </label>
                      <label className="field">
                        <span>Detail limit</span>
                        <input
                          type="number"
                          min={1}
                          max={100}
                          value={draft.detail_limit}
                          onChange={(event) => updateMonitorDraft(monitor.id, { detail_limit: event.target.value })}
                        />
                      </label>
                      <label className="field">
                        <span>Priority</span>
                        <input
                          type="number"
                          min={0}
                          max={100}
                          value={draft.priority_level}
                          onChange={(event) =>
                            updateMonitorDraft(monitor.id, { priority_level: event.target.value })
                          }
                        />
                      </label>
                      <label className="field">
                        <span>Detail policy</span>
                        <select
                          value={draft.detail_policy}
                          onChange={(event) =>
                            updateMonitorDraft(monitor.id, { detail_policy: event.target.value })
                          }
                        >
                          <option value="always">always</option>
                          <option value="priority_only">priority only</option>
                          <option value="never">never</option>
                        </select>
                      </label>
                      <label className="checkbox-field">
                        <input
                          type="checkbox"
                          checked={draft.is_active}
                          onChange={(event) => updateMonitorDraft(monitor.id, { is_active: event.target.checked })}
                        />
                        <span>Active</span>
                      </label>
                      <label className="checkbox-field">
                        <input
                          type="checkbox"
                          checked={draft.with_details}
                          onChange={(event) => updateMonitorDraft(monitor.id, { with_details: event.target.checked })}
                        />
                        <span>With details</span>
                      </label>
                      <label className="checkbox-field">
                        <input
                          type="checkbox"
                          checked={draft.detect_withdrawn}
                          onChange={(event) =>
                            updateMonitorDraft(monitor.id, { detect_withdrawn: event.target.checked })
                          }
                        />
                        <span>Detect withdrawn</span>
                      </label>
                    </div>
                    <div className="watchlist-actions">
                      <button
                        type="button"
                        className="action-button"
                        onClick={() => applyRecommendedConfigToDraft(monitor.id, draft.source)}
                        disabled={runningMonitor !== null || runningPlan !== null || runningDuePlans}
                      >
                        Recommended defaults
                      </button>
                      <button
                        type="button"
                        className="action-button"
                        onClick={() => void runMonitor(monitor.id)}
                        disabled={runningMonitor !== null || runningPlan !== null || runningDuePlans}
                      >
                        {runningMonitor === monitor.id ? "Running..." : "Run monitor"}
                      </button>
                      <button
                        type="button"
                        className="action-button"
                        onClick={() => void saveMonitor(monitor.id)}
                        disabled={runningMonitor !== null || runningPlan !== null || runningDuePlans}
                      >
                        {runningMonitor === monitor.id ? "Working..." : "Save monitor"}
                      </button>
                      <button
                        type="button"
                        className="action-button"
                        onClick={() => void deleteMonitor(monitor.id)}
                        disabled={runningMonitor !== null || runningPlan !== null || runningDuePlans}
                      >
                        Delete monitor
                      </button>
                    </div>
                  </li>
                );
              })}
            </ul>
          ) : (
            <p className="muted">No commercial search monitors yet.</p>
          )}
        </article>
      </section>
    </main>
  );
}
