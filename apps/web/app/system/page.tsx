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
  language: string;
  limit: number | null;
  with_details: boolean;
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
  rotation_mode: string;
  rotation_step: string;
};

type SchedulerPlanDraft = {
  auto_run: boolean;
  interval_minutes: string;
  tasks: SchedulerTaskDraft[];
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
  const parts = [task.job_name, task.source, task.language];
  if (task.limit !== null) {
    parts.push(`limit ${task.limit}`);
  }
  if (task.with_details) {
    parts.push("with details");
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
      rotation_mode: task.rotation_mode,
      rotation_step: task.rotation_step?.toString() ?? "",
    })),
  };
}

export default function SystemPage() {
  const [overview, setOverview] = useState<SystemOverview | null>(null);
  const [jobs, setJobs] = useState<RefreshJobRunSummary[]>([]);
  const [plans, setPlans] = useState<SchedulerPlan[]>([]);
  const [planDrafts, setPlanDrafts] = useState<Record<string, SchedulerPlanDraft>>({});
  const [runningPlan, setRunningPlan] = useState<string | null>(null);
  const [runningJobId, setRunningJobId] = useState<string | null>(null);
  const [runningDuePlans, setRunningDuePlans] = useState(false);
  const [info, setInfo] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadSystem() {
      try {
        const [overviewResponse, jobsResponse, plansResponse] = await Promise.all([
          fetch(`${API_BASE}/api/v1/system/overview`),
          fetch(`${API_BASE}/api/v1/system/refresh-jobs?limit=10`),
          fetch(`${API_BASE}/api/v1/system/scheduler-plans`),
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

        const overviewPayload = (await overviewResponse.json()) as SystemOverview;
        const jobsPayload = (await jobsResponse.json()) as RefreshJobRunSummary[];
        const plansPayload = (await plansResponse.json()) as SchedulerPlan[];
        if (!cancelled) {
          setOverview(overviewPayload);
          setJobs(jobsPayload);
          setPlans(plansPayload);
          setPlanDrafts(Object.fromEntries(plansPayload.map((plan) => [plan.name, buildPlanDraft(plan)])));
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
    const [overviewResponse, jobsResponse, plansResponse] = await Promise.all([
      fetch(`${API_BASE}/api/v1/system/overview`),
      fetch(`${API_BASE}/api/v1/system/refresh-jobs?limit=10`),
      fetch(`${API_BASE}/api/v1/system/scheduler-plans`),
    ]);
    if (!overviewResponse.ok || !jobsResponse.ok || !plansResponse.ok) {
      throw new Error("system reload failed");
    }
    setOverview((await overviewResponse.json()) as SystemOverview);
    const nextJobs = (await jobsResponse.json()) as RefreshJobRunSummary[];
    setJobs(nextJobs);
    const nextPlans = (await plansResponse.json()) as SchedulerPlan[];
    setPlans(nextPlans);
    setPlanDrafts(Object.fromEntries(nextPlans.map((plan) => [plan.name, buildPlanDraft(plan)])));
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

  return (
    <main className="page-shell">
      <section className="hero-card">
        <p className="eyebrow">Phase 2</p>
        <h1>System Monitor</h1>
        <p className="lead">
          Track refresh runs, basic dataset volume, and the last ingestion result before a fuller
          scheduler and job orchestration layer lands.
        </p>
        <div className="hero-actions">
          <Link href="/">Back to dashboard</Link>
          <Link href="/activity">Open activity</Link>
          <Link href="/map">Open map</Link>
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
                  {renderJobSummary(item)}
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
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">No scheduler plans configured yet.</p>
          )}
        </article>
      </section>
    </main>
  );
}
