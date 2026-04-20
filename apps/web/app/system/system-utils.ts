import type {
  CommercialSearchMonitor,
  MonitorDraft,
  MonitorRecommendedConfig,
  RefreshJobRunSummary,
  SchedulerPlan,
  SchedulerPlanDraft,
} from "./system-types";

export async function extractErrorMessage(response: Response, fallback: string): Promise<string> {
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

export function formatDateTime(value: string | null): string {
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

export function describeJob(item: RefreshJobRunSummary): string {
  if (item.job_name.startsWith("refresh_plan:")) {
    return "refresh plan wrapper";
  }
  if (item.trigger_kind === "plan") {
    return "plan task";
  }
  return item.trigger_kind;
}

export function describeTask(task: SchedulerPlan["tasks"][number]): string {
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

export function buildPlanDraft(plan: SchedulerPlan): SchedulerPlanDraft {
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

export function buildMonitorDraft(item: CommercialSearchMonitor): MonitorDraft {
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

export function mergePlanDrafts(
  plans: SchedulerPlan[],
  currentDrafts: Record<string, SchedulerPlanDraft>,
  dirtyDrafts: Record<string, boolean>,
): Record<string, SchedulerPlanDraft> {
  return Object.fromEntries(
    plans.map((plan) => [
      plan.name,
      dirtyDrafts[plan.name] && currentDrafts[plan.name]
        ? currentDrafts[plan.name]
        : buildPlanDraft(plan),
    ]),
  );
}

export function mergeMonitorDrafts(
  monitors: CommercialSearchMonitor[],
  currentDrafts: Record<string, MonitorDraft>,
  dirtyDrafts: Record<string, boolean>,
): Record<string, MonitorDraft> {
  return Object.fromEntries(
    monitors.map((item) => [
      item.id,
      dirtyDrafts[item.id] && currentDrafts[item.id]
        ? currentDrafts[item.id]
        : buildMonitorDraft(item),
    ]),
  );
}

export function monitorHealthLabel(value: string): string {
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

export function recommendedMonitorConfig(source: string): MonitorRecommendedConfig {
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

export function sourceGuidance(source: string): string {
  if (source === "ricacorp") {
    return "Prefer broader search-page coverage and lighter refreshes. Keep detail off by default unless a source-specific parser is added later.";
  }
  return "Prefer a moderate search limit and high-priority detail enrichment. Use detail only for priority monitors to avoid slow full-page refreshes.";
}
