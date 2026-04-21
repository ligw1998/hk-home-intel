export type DevelopmentSummary = {
  id: string;
  source_url: string | null;
  available_sources: string[];
  source_links: { source: string; url: string }[];
  display_name: string | null;
  district: string | null;
  region: string | null;
  completion_year: number | null;
  age_years: number | null;
  listing_segment: string;
  lat: number | null;
  lng: number | null;
  active_listing_count: number;
  active_listing_min_price_hkd: number | null;
  active_listing_saleable_area_values: number[];
  active_listing_bedroom_options: number[];
  coverage_status: string;
  coverage_notes: string[];
  data_gap_flags: string[];
};

export type LaunchWatchMapItem = {
  id: string;
  display_name: string;
  district: string | null;
  region: string | null;
  expected_launch_window: string | null;
  launch_stage: string;
  signal_bucket: string;
  signal_label: string;
  signal_rank: number;
  official_site_url: string | null;
  source_url: string | null;
  linked_development_id: string | null;
  linked_development_name: string | null;
  note: string | null;
  lat: number | null;
  lng: number | null;
  coordinate_mode: string;
};

export type DevelopmentLaunchWatchSignal = {
  id: string;
  display_name: string;
  launch_stage: string;
  signal_bucket: string;
  signal_label: string;
  expected_launch_window: string | null;
  official_site_url: string | null;
  source_url: string | null;
  note: string | null;
};

export type DevelopmentListResponse = {
  items: DevelopmentSummary[];
  total: number;
};

export type LaunchWatchResponse = {
  items: LaunchWatchMapItem[];
  total: number;
};

export type DevelopmentDetailResponse = DevelopmentSummary & {
  source_confidence: string;
};

export type WatchlistItem = {
  development_id: string;
  decision_stage: string;
};

export type SearchPresetCriteria = {
  region: string | null;
  district: string | null;
  search: string | null;
  listing_segments: string[];
  min_budget_hkd: number | null;
  max_budget_hkd: number | null;
  bedroom_values: number[];
  min_saleable_area_sqft: number | null;
  max_saleable_area_sqft: number | null;
  max_age_years: number | null;
  watchlist_only: boolean;
};

export type SearchPreset = {
  id: string;
  name: string;
  scope: string;
  note: string | null;
  is_default: boolean;
  criteria: SearchPresetCriteria;
  updated_at: string;
};
