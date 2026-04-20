export type RefreshJobRunSummary = {
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

export type SystemOverview = {
  development_count: number;
  development_with_coordinates_count: number;
  document_count: number;
  watchlist_count: number;
  commercial_listing_count: number;
  price_event_count: number;
  active_monitor_count: number;
  attention_monitor_count: number;
  readiness_status: string;
  readiness_notes: string[];
  latest_job: RefreshJobRunSummary | null;
};

export type SchedulerTask = {
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

export type SchedulerPlan = {
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

export type RunPlanResponse = {
  status: string;
  job_id: string;
  plan: string;
  message: string;
};

export type RunDuePlansResponse = {
  status: string;
  due_plan_names: string[];
  run_count: number;
  job_ids: string[];
};

export type SchedulerTaskDraft = {
  job_name: string;
  limit: string;
  with_details: boolean;
  detect_withdrawn: boolean;
  rotation_mode: string;
  rotation_step: string;
};

export type SchedulerPlanDraft = {
  auto_run: boolean;
  interval_minutes: string;
  tasks: SchedulerTaskDraft[];
};

export type MonitorCriteria = {
  listing_segments: string[];
  max_budget_hkd: number | null;
  bedroom_values: number[];
  max_age_years: number | null;
  default_limit: number | null;
  detail_limit: number | null;
  priority_level: number;
  detail_policy: string;
};

export type MonitorLatestRun = {
  id: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  summary: Record<string, unknown> | null;
  error_message: string | null;
};

export type CommercialSearchMonitor = {
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

export type MonitorDraft = {
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

export type MonitorRecommendedConfig = {
  with_details: boolean;
  default_limit: string;
  detail_limit: string;
  priority_level: string;
  detail_policy: string;
};
