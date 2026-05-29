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

export type MarketDataProviderSummary = {
  provider_key: string;
  provider_name: string;
  provider_type: string;
  status: string;
  series_count: number;
  bars_count: number;
  action_count: number;
  segment_count: number;
  manifest_count: number;
  intervals: string[];
  adjustment_kinds: string[];
  latest_bar_time: string;
  latest_ingestion_at: string;
  latest_ingestion_status: string;
  latest_ingestion_job_id: number | null;
};

export type MarketDataIngestionJob = {
  id: number;
  provider_key: string;
  provider_name: string;
  job_type: string;
  status: string;
  targets_total: number;
  targets_completed: number;
  rows_inserted: number;
  rows_updated: number;
  error_count: number;
  requested_at: string;
  completed_at: string;
  error_message: string;
  target_symbol: string;
  interval: string;
  requested_via: string;
  summary_json: Record<string, unknown>;
};

export type MarketDataIngestionJobItem = {
  id: number;
  job_id: number;
  item_key: string;
  source_symbol: string;
  instrument_symbol: string;
  interval: string;
  stage: string;
  status: string;
  rows_inserted: number;
  rows_updated: number;
  error_message: string;
  details_json: Record<string, unknown>;
  instrument_id: number | null;
  series_id: number | null;
  started_at: string;
  completed_at: string;
};

export type MarketDataIngestionJobDetail = MarketDataIngestionJob & {
  started_at: string;
  target_scope_json: Record<string, unknown>;
  options_json: Record<string, unknown>;
  items: MarketDataIngestionJobItem[];
};

export type MarketDataSyncEnqueueResult = {
  provider: string;
  ingestion_job_id: number;
  status: string;
  target_symbol: string;
  interval: string;
  requested_via: string;
};

export type MarketDataJobActionResult = {
  job_id: number;
  status: string;
  changed: boolean;
};

export type MarketDataSeriesRow = {
  series_id: number;
  provider_key: string;
  provider_name: string;
  instrument_symbol: string;
  instrument_name: string;
  source_symbol: string;
  market: string;
  exchange: string;
  interval: string;
  adjustment_kind: string;
  session_type: string;
  price_type: string;
  bar_type: string;
  currency: string;
  timezone: string;
  bar_count: number;
  first_bar_time: string;
  last_bar_time: string;
  last_ingested_at: string;
  is_active: boolean;
};

export type MarketDataCorporateActionRow = {
  event_id: number;
  provider_key: string;
  provider_name: string;
  instrument_symbol: string;
  instrument_name: string;
  source_symbol: string;
  action_type: string;
  announce_date: string;
  record_date: string;
  ex_date: string;
  pay_date: string;
  end_date: string;
  cash_dividend: number;
  stock_bonus_ratio: number;
  stock_conversion_ratio: number;
  rights_ratio: number;
  rights_price: number;
  status: string;
  ingested_at: string;
  updated_at: string;
};

export type MarketDataAdjustmentSegmentRow = {
  segment_id: number;
  provider_key: string;
  provider_name: string;
  instrument_symbol: string;
  instrument_name: string;
  adjustment_kind: string;
  start_date: string;
  end_date: string;
  adjust_a: number;
  adjust_b: number;
  status: string;
  payload_json: Record<string, unknown>;
  action_provider_name: string;
  generated_at: string;
  updated_at: string;
};

export type MarketDataSourceFileManifestRow = {
  manifest_id: number;
  provider_key: string;
  provider_name: string;
  instrument_symbol: string;
  instrument_name: string;
  series_id: number | null;
  source_path: string;
  file_kind: string;
  market: string;
  interval: string;
  source_size: number;
  source_mtime: number;
  record_count: number;
  tail_hash: string;
  status: string;
  last_bar_time: string;
  payload_json: Record<string, unknown>;
  updated_at: string;
};

export type MarketDataSymbolDiagnostics = {
  symbol: string;
  instrument_name: string;
  exchange: string;
  summary: {
    series_count: number;
    corporate_action_count: number;
    adjustment_segment_count: number;
    manifest_count: number;
    recent_job_count: number;
  };
  series_rows: MarketDataSeriesRow[];
  corporate_action_rows: MarketDataCorporateActionRow[];
  adjustment_segment_rows: MarketDataAdjustmentSegmentRow[];
  source_file_manifest_rows: MarketDataSourceFileManifestRow[];
  recent_ingestion_jobs: MarketDataIngestionJob[];
};

export type MarketDataStats = {
  instrument_count: number;
  total_bars: number;
  by_interval: Array<{ interval: string; bar_count: number }>;
  coverages: MarketCoverage[];
  provider_summaries: MarketDataProviderSummary[];
  recent_ingestion_jobs: MarketDataIngestionJob[];
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

const API_BASE_PATH = "";
const DEFAULT_TIMEOUT_MS = 15_000;

export class ApiError extends Error {
  readonly status: number | null;
  readonly path: string;
  readonly detail: unknown;
  readonly code: "HTTP_ERROR" | "NETWORK_ERROR" | "TIMEOUT" | "ABORTED";

  constructor(params: {
    message: string;
    path: string;
    code: "HTTP_ERROR" | "NETWORK_ERROR" | "TIMEOUT" | "ABORTED";
    status?: number | null;
    detail?: unknown;
  }) {
    super(params.message);
    this.name = "ApiError";
    this.status = params.status ?? null;
    this.path = params.path;
    this.detail = params.detail;
    this.code = params.code;
  }
}

export type ApiRequestInit = RequestInit & {
  timeoutMs?: number;
  retries?: number;
};

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}

type ApiFetchSafeResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: ApiError };

function resolveApiUrl(path: string): string {
  if (!path.startsWith("/")) {
    throw new Error(`API 路径必须以 "/" 开头，收到：${path}`);
  }
  return `${API_BASE_PATH}${path}`;
}

function shouldAttachJsonContentType(body: BodyInit | null | undefined): boolean {
  if (!body) {
    return false;
  }
  return !(body instanceof FormData) && !(body instanceof URLSearchParams);
}

function mergeRequestHeaders(init: RequestInit): Headers {
  const headers = new Headers(init.headers ?? undefined);
  if (!headers.has("Accept")) {
    headers.set("Accept", "application/json");
  }
  if (shouldAttachJsonContentType(init.body) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  return headers;
}

function buildApiErrorMessage(status: number, detail: unknown): string {
  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }
  if (detail && typeof detail === "object" && "detail" in detail) {
    const nestedDetail = (detail as { detail?: unknown }).detail;
    if (typeof nestedDetail === "string" && nestedDetail.trim()) {
      return nestedDetail;
    }
  }
  if (status === 404) {
    return "请求的资源不存在。";
  }
  if (status >= 500) {
    return "后端服务暂时不可用，请稍后重试。";
  }
  return `请求失败：${status}`;
}

async function parseErrorDetail(response: Response): Promise<unknown> {
  const contentType = response.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    try {
      return await response.json();
    } catch {
      return null;
    }
  }
  try {
    const text = await response.text();
    return text || null;
  } catch {
    return null;
  }
}

function createNetworkApiError(path: string, error: unknown): ApiError {
  if (error instanceof DOMException && error.name === "AbortError") {
    return new ApiError({
      message: "请求已取消。",
      path,
      code: "ABORTED",
      detail: error,
    });
  }
  return new ApiError({
    message: "无法连接后端服务，请确认本机 API 已启动。",
    path,
    code: "NETWORK_ERROR",
    detail: error,
  });
}

function createTimeoutApiError(path: string): ApiError {
  return new ApiError({
    message: "请求超时，请确认本机 API 服务状态或稍后重试。",
    path,
    code: "TIMEOUT",
  });
}

async function runApiRequest(url: string, init: ApiRequestInit): Promise<Response> {
  const controller = new AbortController();
  const timeoutMs = init.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const timeout = globalThis.setTimeout(() => controller.abort("timeout"), timeoutMs);
  const headers = mergeRequestHeaders(init);
  const upstreamSignal = init.signal;

  const abortFromUpstream = () => controller.abort(upstreamSignal?.reason);
  if (upstreamSignal) {
    if (upstreamSignal.aborted) {
      controller.abort(upstreamSignal.reason);
    } else {
      upstreamSignal.addEventListener("abort", abortFromUpstream, { once: true });
    }
  }

  try {
    return await fetch(url, {
      ...init,
      headers,
      cache: init.cache ?? "no-store",
      signal: controller.signal,
    });
  } catch (error) {
    if (controller.signal.aborted && controller.signal.reason === "timeout") {
      throw createTimeoutApiError(url);
    }
    throw createNetworkApiError(url, error);
  } finally {
    globalThis.clearTimeout(timeout);
    if (upstreamSignal) {
      upstreamSignal.removeEventListener("abort", abortFromUpstream);
    }
  }
}

export async function apiFetch<T>(path: string, init: ApiRequestInit = {}): Promise<T> {
  const url = resolveApiUrl(path);
  const method = (init.method ?? "GET").toUpperCase();
  const retries = init.retries ?? (method === "GET" ? 1 : 0);

  let lastError: ApiError | null = null;
  for (let attempt = 0; attempt <= retries; attempt += 1) {
    try {
      const response = await runApiRequest(url, init);
      if (!response.ok) {
        const detail = await parseErrorDetail(response);
        throw new ApiError({
          message: buildApiErrorMessage(response.status, detail),
          path,
          code: "HTTP_ERROR",
          status: response.status,
          detail,
        });
      }
      return (await response.json()) as T;
    } catch (error) {
      const normalizedError = isApiError(error)
        ? error
        : new ApiError({
            message: "请求失败，请稍后重试。",
            path,
            code: "NETWORK_ERROR",
            detail: error,
          });
      lastError = normalizedError;
      const shouldRetry =
        attempt < retries &&
        method === "GET" &&
        (normalizedError.code === "NETWORK_ERROR" || normalizedError.code === "TIMEOUT" || normalizedError.status === 502 || normalizedError.status === 503 || normalizedError.status === 504);
      if (!shouldRetry) {
        throw normalizedError;
      }
    }
  }

  throw lastError ?? new ApiError({
    message: "请求失败，请稍后重试。",
    path,
    code: "NETWORK_ERROR",
  });
}

export async function apiFetchSafe<T>(path: string, init?: ApiRequestInit): Promise<ApiFetchSafeResult<T>> {
  try {
    const data = await apiFetch<T>(path, init);
    return { ok: true, data };
  } catch (error) {
    const normalizedError = isApiError(error)
      ? error
      : new ApiError({
          message: "请求失败，请稍后重试。",
          path,
          code: "NETWORK_ERROR",
          detail: error,
        });
    return { ok: false, error: normalizedError };
  }
}
