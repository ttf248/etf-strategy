export type MarketCoverage = {
  symbol: string;
  name: string;
  exchange: string;
  interval: string;
  bar_count: number;
  start_time: string;
  end_time: string;
  last_ingested_at: string;
};

export type MarketDataStats = {
  instrument_count: number;
  total_bars: number;
  by_interval: Array<{ interval: string; bar_count: number }>;
  coverages: MarketCoverage[];
  recent_sync_runs: Array<Record<string, unknown>>;
};

export type BacktestJob = {
  id: number;
  status: string;
  job_type: string;
  request_payload: Record<string, unknown>;
  progress_pct: number;
  runtime_details: {
    stage_key?: string;
    stage_label?: string;
    stage_message?: string;
    current_step?: number;
    total_steps?: number;
    elapsed_seconds?: number | null;
    eta_seconds?: number | null;
    queue_position?: number;
    worker_name?: string;
    requested_parallelism?: number;
    effective_parallelism?: number;
    worker_concurrency?: number;
    max_optimization_workers?: number;
    resource_summary?: string;
    updated_at?: string;
  };
  submitted_at: string;
  started_at: string;
  completed_at: string;
  error_message: string;
  reports?: Array<{ id: number; report_name: string; strategy_kind: string; interval: string }>;
};

export type PlatformStatus = {
  api: { status: string; host: string; port: number; base_url: string };
  frontend: { status: string; host: string; port: number; base_url: string };
  database: { status: string; url: string; error?: string };
  heartbeats: Array<{
    service_name: string;
    status: string;
    pid: number;
    started_at: string;
    last_seen_at: string;
    age_seconds: number;
    details: Record<string, unknown>;
  }>;
  queue: Record<string, number>;
  process_control_enabled: boolean;
  sync_schedule: Array<{ id: string; interval: string; cron: string; period: string }>;
};

export type PlatformProcess = {
  pid: number;
  name: string;
  service_name: string;
  created_at: string;
  command_line: string;
};

export type PlatformLogs = {
  service: string;
  lines: string[];
};

export type ReportSummary = {
  id: number;
  job_id: number;
  symbol: string;
  name: string;
  interval: string;
  strategy_kind: string;
  report_name: string;
  dataset_start: string;
  dataset_end: string;
  created_at: string;
  summary_metrics: Record<string, Record<string, unknown>>;
};

export type ReportDetail = ReportSummary & {
  parameters: Record<string, unknown>;
  artifacts: Record<string, unknown>;
  equity_curve: Array<{ curve_time: string; equity: number; drawdown_pct: number; return_pct: number }>;
  trades: Array<Record<string, unknown>>;
  events: Array<Record<string, unknown>>;
};

export type StrategyTemplate = {
  id: number;
  template_key: string;
  template_name: string;
  strategy_kind: string;
  interval: string;
  execution_profile: string;
  validation_start: string;
  lookback_days: number | null;
  validation_ratio: number | null;
  jobs: number;
  execution_overrides_json: Record<string, unknown>;
  parameter_space_json: Record<string, unknown>;
  description: string;
  is_active: boolean;
  is_default: boolean;
  created_at: string;
  updated_at: string;
};

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `请求失败：${response.status}`);
  }
  return (await response.json()) as T;
}
