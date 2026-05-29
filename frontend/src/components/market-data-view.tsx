"use client";

import Link from "next/link";
import { Button, Card, Collapse, Drawer, Empty, Input, Select, Skeleton, Space, Table, Tag, Typography, message } from "antd";
import { useEffect, useMemo, useState } from "react";
import {
  apiFetch,
  apiFetchSafe,
  type MarketDataAdjustmentSegmentRow,
  type MarketCoverage,
  type MarketDataCorporateActionRow,
  type MarketDataIngestionJob,
  type MarketDataIngestionJobDetail,
  type MarketDataIngestionJobItem,
  type MarketDataProviderSummary,
  type MarketDataSeriesRow,
  type MarketDataStats,
} from "@/lib/api";
import { MetricCard, PageErrorState, PageHeader, StatusTag, ToolbarCount } from "@/components/platform-ui";
import { intervalOptions } from "@/lib/strategy-template-config";
import { buildBacktestLaunchHref, buildBacktestPresetHref, buildBeginnerPresets } from "@/lib/beginner-presets";

type IntervalRecommendation = {
  interval: string;
  title: string;
  description: string;
};

type CoverageProfile = {
  symbol: string;
  name: string;
  intervals: Set<string>;
};

type CoverageInsight = {
  key: string;
  value: string;
  title: string;
  description: string;
  recommendation: string;
  examples: CoverageProfile[];
};

type StartDecisionCard = {
  title: string;
  value: string;
  description: string;
};

type SymbolIntervalCard = {
  interval: string;
  title: string;
  value: string;
  description: string;
  ready: boolean;
};

type ProviderIntervalOption = {
  label: string;
  value: string;
};

type WorkflowStepResult = {
  step: string;
  step_label: string;
  provider: string;
  interval: string;
  symbols_count: number;
  bars_inserted: number;
  bars_updated: number;
  status: string;
  error_message: string;
  child_ingestion_job_ids: number[];
  blocked_by?: string;
};

type ProviderPanelConfig = {
  providerKey: string;
  fallbackName: string;
  title: string;
  description: string;
  currentActionLabel: string;
  batchActionLabel: string;
  symbolHint: string;
  currentIntervalLabel: string;
};

type ProviderPanelModel = ProviderPanelConfig & {
  summary: MarketDataProviderSummary;
  currentTarget: string;
};

const tdxIntervalOptions: ProviderIntervalOption[] = [
  { label: "all 全部周期", value: "all" },
  { label: "1d 原始日线", value: "1d" },
  { label: "1m 原始分钟", value: "1m" },
  { label: "5m 原始分钟", value: "5m" },
];

const tdxPipelineIntervalOptions: ProviderIntervalOption[] = [
  { label: "all 原始+事件+前复权", value: "all" },
  { label: "1d 日线链路", value: "1d" },
];

const providerPanelConfigs: ProviderPanelConfig[] = [
  {
    providerKey: "yahoo",
    fallbackName: "Yahoo Finance",
    title: "Yahoo 回测样本",
    description: "下载 Yahoo 行情，并继续双写当前回测主表与统一行情表。默认批量入口会使用内置 100 个全球高活跃样本，适合作为长期维护的回测底仓。",
    currentActionLabel: "同步当前标的",
    batchActionLabel: "同步默认样本池",
    symbolHint: "示例：1810.HK、SPY",
    currentIntervalLabel: "当前周期",
  },
  {
    providerKey: "tdx",
    fallbackName: "通达信本地行情",
    title: "通达信原始行情",
    description: "从本地 vipdoc 导入 A 股原始 `1d / 1m / 5m` 文件；也可直接按 `all` 一次性顺序导入全部周期，并维护文件 manifest，适合作为后续前复权与本地化扩仓底座。",
    currentActionLabel: "导入当前标的原始行情",
    batchActionLabel: "批量导入",
    symbolHint: "示例：SH600000、SZ000001",
    currentIntervalLabel: "支持 all / 1d / 1m / 5m",
  },
  {
    providerKey: "tdx_pipeline",
    fallbackName: "A 股统一补数链路",
    title: "A 股统一补数链路",
    description: "串行执行通达信原始导入、Tushare 公司行动抓取和通达信前复权重算。适合一次性把 A 股样本补到“原始数据 + 公司行动 + 前复权”的可复算状态。",
    currentActionLabel: "执行当前标的一键链路",
    batchActionLabel: "批量执行一键链路",
    symbolHint: "示例：SH600000、SZ000001",
    currentIntervalLabel: "支持 all / 1d",
  },
  {
    providerKey: "tushare",
    fallbackName: "Tushare 公司行动",
    title: "Tushare 公司行动",
    description: "抓取分红送转实施事件，写入统一公司行动事实表，供通达信前复权重算直接复用。",
    currentActionLabel: "抓取当前标的公司行动",
    batchActionLabel: "批量抓取",
    symbolHint: "示例：600000.SH、000001.SZ",
    currentIntervalLabel: "事件模式",
  },
  {
    providerKey: "tdx_qfq",
    fallbackName: "通达信前复权",
    title: "通达信前复权重算",
    description: "基于通达信原始日线与 Tushare 公司行动重建前复权序列，并落库公式区间，便于后续稳定复算。",
    currentActionLabel: "重算当前标的前复权",
    batchActionLabel: "批量重算",
    symbolHint: "示例：SH600000、SZ000001",
    currentIntervalLabel: "固定 1d / qfq",
  },
];

function normalizeProviderSymbol(providerKey: string, rawSymbol: string): string {
  const normalized = rawSymbol.trim().toUpperCase();
  if (!normalized) {
    return "";
  }
  const dottedMatch = normalized.match(/^(\d{6})\.(SH|SZ|BJ)$/);
  const prefixedMatch = normalized.match(/^(SH|SZ|BJ)(\d{6})$/);
  if (providerKey === "tdx" || providerKey === "tdx_qfq" || providerKey === "tdx_pipeline") {
    if (dottedMatch) {
      return `${dottedMatch[2].toLowerCase()}${dottedMatch[1]}`;
    }
    if (prefixedMatch) {
      return `${prefixedMatch[1].toLowerCase()}${prefixedMatch[2]}`;
    }
    return normalized.toLowerCase();
  }
  if (providerKey === "tushare") {
    if (prefixedMatch) {
      return `${prefixedMatch[2]}.${prefixedMatch[1]}`;
    }
    return normalized;
  }
  return normalized;
}

function ingestionStatusLabel(status: string): string {
  if (status === "succeeded") {
    return "已完成";
  }
  if (status === "completed") {
    return "已结束";
  }
  if (status === "partially_failed") {
    return "部分失败";
  }
  if (status === "failed") {
    return "失败";
  }
  if (status === "running") {
    return "执行中";
  }
  if (status === "queued") {
    return "排队中";
  }
  if (status === "skipped") {
    return "已跳过";
  }
  if (status === "inactive") {
    return "未初始化";
  }
  if (status === "active") {
    return "可用";
  }
  return status || "-";
}

function buildIngestionTargetLabel(job: MarketDataIngestionJob): string {
  const target = job.target_symbol?.trim();
  const interval = job.interval?.trim();
  if (target && interval) {
    return `${target} / ${interval}`;
  }
  if (target) {
    return target;
  }
  if (interval) {
    return `批量 / ${interval}`;
  }
  return "批量任务";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function toNumberArray(value: unknown): number[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item) => Number(item))
    .filter((item) => Number.isFinite(item))
    .map((item) => Math.trunc(item));
}

function extractWorkflowResults(job: MarketDataIngestionJob): WorkflowStepResult[] {
  const summary = isRecord(job.summary_json) ? job.summary_json : {};
  const rawResults = summary.workflow_results;
  if (!Array.isArray(rawResults)) {
    return [];
  }
  const parsedResults: WorkflowStepResult[] = [];
  for (const item of rawResults) {
    if (!isRecord(item)) {
      continue;
    }
    parsedResults.push({
      step: String(item.step ?? ""),
      step_label: String(item.step_label ?? item.step ?? ""),
      provider: String(item.provider ?? ""),
      interval: String(item.interval ?? ""),
      symbols_count: Number(item.symbols_count ?? 0),
      bars_inserted: Number(item.bars_inserted ?? 0),
      bars_updated: Number(item.bars_updated ?? 0),
      status: String(item.status ?? ""),
      error_message: String(item.error_message ?? ""),
      child_ingestion_job_ids: toNumberArray(item.child_ingestion_job_ids),
      blocked_by: item.blocked_by ? String(item.blocked_by) : undefined,
    });
  }
  return parsedResults;
}

function extractChildIngestionJobIds(job: MarketDataIngestionJob): number[] {
  const summary = isRecord(job.summary_json) ? job.summary_json : {};
  return toNumberArray(summary.child_ingestion_job_ids ?? summary.ingestion_job_ids);
}

function coverageStage(profile: CoverageProfile) {
  const hasDaily = profile.intervals.has("1d");
  const has15m = profile.intervals.has("15m");
  if (hasDaily && has15m) {
    return 0;
  }
  if (hasDaily) {
    return 1;
  }
  return 2;
}

function compareCoverageProfile(left: CoverageProfile, right: CoverageProfile) {
  const stageDiff = coverageStage(left) - coverageStage(right);
  if (stageDiff !== 0) {
    return stageDiff;
  }
  const intervalDiff = right.intervals.size - left.intervals.size;
  if (intervalDiff !== 0) {
    return intervalDiff;
  }
  return left.symbol.localeCompare(right.symbol);
}

function buildStartDecisionCards(
  checkedSymbol: string,
  symbolRows: MarketCoverage[],
  symbolIntervals: Set<string>,
  intervalRecommendations: IntervalRecommendation[],
  readySymbolCount: number,
): StartDecisionCard[] {
  const normalizedSymbol = checkedSymbol.trim().toUpperCase();
  const hasRows = symbolRows.length > 0;
  const hasDaily = symbolIntervals.has("1d");
  const has15m = symbolIntervals.has("15m");

  let currentDecision: StartDecisionCard;
  let nextAction: StartDecisionCard;
  let syncAllDecision: StartDecisionCard;

  if (!normalizedSymbol) {
    currentDecision = {
      title: "当前状态",
      value: "待确认目标标的",
      description: "输入目标标的代码后，页面会给出覆盖情况与补数建议，无需先浏览完整覆盖表。",
    };
    nextAction = {
      title: "建议动作",
      value: "查看推荐样本",
      description: "若暂时没有明确标的，可先使用页面中的推荐样本，再决定是否检查自定义目标。",
    };
    syncAllDecision = {
      title: "全量同步时机",
      value: "当前通常无需执行",
      description: "建立初始研究样本不需要先做全量建库。只有准备批量扩充标的池时，才需要补全部标的某个周期。",
    };
    return [currentDecision, nextAction, syncAllDecision];
  }

  if (!hasRows) {
    currentDecision = {
      title: "当前状态",
      value: `${normalizedSymbol} 尚无覆盖`,
      description: "当前还没有该标的行情，建议先补齐可用覆盖，再考虑其他标的与更多周期。",
    };
    nextAction = {
      title: "建议动作",
      value: intervalRecommendations[0]?.title ?? "先补日线",
      description: intervalRecommendations[0]?.description ?? "通常先补 1d，再按研究需求补 15m。",
    };
    syncAllDecision = {
      title: "全量同步时机",
      value: "当前不建议全量同步",
      description: "先将当前标的补到可研究状态，比先补全库更直接。只有当前标的已满足需求且准备扩大范围时，再做全量同步。",
    };
    return [currentDecision, nextAction, syncAllDecision];
  }

  if (hasDaily && has15m) {
    currentDecision = {
      title: "当前状态",
      value: `${normalizedSymbol} 可直接进入研究`,
      description: "该标的已同时具备 1d 与 15m 覆盖，足以支撑大多数基线回测场景。",
    };
    nextAction = {
      title: "建议动作",
      value: "进入回测配置",
      description: "当前应优先形成一份结果，再根据复盘结论决定是否补充更多标的或更多周期。",
    };
    syncAllDecision = {
      title: "全量同步时机",
      value: readySymbolCount > 0 ? "扩充标的池时再执行" : "当前无需执行",
      description: "只有准备批量筛选更多标的，或当前可直接研究的标的过少时，才有必要做全量同步。当前该标的已可直接开始。",
    };
    return [currentDecision, nextAction, syncAllDecision];
  }

  currentDecision = {
    title: "当前状态",
    value: `${normalizedSymbol} 覆盖仍可补强`,
    description: "该标的已具备部分数据，可支持部分策略，但尚未覆盖最常用的基线组合。",
  };
  nextAction = {
    title: "建议动作",
    value: intervalRecommendations[0]?.title ?? "先补推荐周期",
    description: intervalRecommendations[0]?.description ?? "先补齐常用周期，再返回回测配置页。",
  };
  syncAllDecision = {
    title: "全量同步时机",
    value: "当前仍应优先补齐单标的覆盖",
    description: "若当前仅研究这一只标的，补齐推荐周期即可。只有准备同步扩展更多标的时，再做全量同步。",
  };
  return [currentDecision, nextAction, syncAllDecision];
}

function buildSymbolIntervalCards(symbolIntervals: Set<string>, hasRows: boolean): SymbolIntervalCard[] {
  const cards: Array<{
    interval: string;
    title: string;
    purpose: string;
  }> = [
    {
      interval: "1d",
      title: "日线基线",
      purpose: "用于定投、日线择时和更长区间的稳健复盘。",
    },
    {
      interval: "15m",
      title: "分钟级基线",
      purpose: "用于默认网格和大多数分钟级基线策略。",
    },
    {
      interval: "1m",
      title: "更细粒度短线",
      purpose: "只有需要更高频的分钟信号时才值得补。",
    },
  ];

  return cards.map((item) => {
    if (!hasRows) {
      return {
        interval: item.interval,
        title: item.title,
        value: "尚未准备",
        description: item.purpose,
        ready: false,
      };
    }
    const ready = symbolIntervals.has(item.interval);
    return {
      interval: item.interval,
      title: item.title,
      value: ready ? "已覆盖" : "待补齐",
      description: ready ? `当前已经具备 ${item.interval}，${item.purpose}` : `当前还没有 ${item.interval}，${item.purpose}`,
      ready,
    };
  });
}

function buildPrimaryResearchPath(params: {
  checkedSymbol: string;
  hasRows: boolean;
  intervalRecommendations: IntervalRecommendation[];
  symbolIntervals: Set<string>;
}): { title: string; description: string } {
  const normalizedSymbol = params.checkedSymbol.trim().toUpperCase();
  if (!normalizedSymbol) {
    return {
      title: "先输入一个目标标的，确认它是否具备最小研究样本",
      description: "不需要先浏览全库覆盖，先把一个熟悉标的补到可研究状态更直接。",
    };
  }
  if (!params.hasRows) {
    return {
      title: `先把 ${normalizedSymbol} 补到可研究状态`,
      description: `当前还没有 ${normalizedSymbol} 行情。通常先补 ${params.intervalRecommendations[0]?.interval ?? "1d"}，再按研究需求补 ${params.intervalRecommendations[1]?.interval ?? "15m"}。`,
    };
  }
  if (params.symbolIntervals.has("1d") && params.symbolIntervals.has("15m")) {
    return {
      title: `${normalizedSymbol} 已具备最常用研究样本，可直接进入回测`,
      description: "当前更值得做的是先跑出一份结果，再根据复盘结论决定要不要补更多标的或更细周期。",
    };
  }
  return {
    title: `${normalizedSymbol} 已有部分覆盖，建议补齐常用周期后再扩大范围`,
    description: "如果你只研究这一只标的，先把日线和 15m 补齐通常比先做全量同步更有效。",
  };
}

function renderWorkflowSummary(job: MarketDataIngestionJob) {
  const workflowResults = extractWorkflowResults(job);
  const childJobIds = extractChildIngestionJobIds(job);
  if (workflowResults.length === 0 && childJobIds.length === 0) {
    return null;
  }
  return (
    <Collapse
      size="small"
      ghost
      items={[
        {
          key: `workflow-${job.id}`,
          label: "查看链路详情",
          children: (
            <div className="provider-panel-tags">
              {childJobIds.length > 0 ? (
                <Typography.Text type="secondary">子任务 #{childJobIds.join(", #")}</Typography.Text>
              ) : null}
              {workflowResults.map((item) => (
                <article key={`${job.id}-${item.step}`} className="ingestion-mobile-card">
                  <div className="ingestion-mobile-card-head">
                    <div>
                      <strong>{item.step_label || item.step || item.provider}</strong>
                      <span>{item.provider}{item.interval ? ` / ${item.interval}` : ""}</span>
                    </div>
                    <StatusTag value={item.status} label={ingestionStatusLabel(item.status)} />
                  </div>
                  <div className="ingestion-mobile-metrics">
                    <span>目标 {item.symbols_count}</span>
                    <span>新增 {item.bars_inserted.toLocaleString()}</span>
                    <span>更新 {item.bars_updated.toLocaleString()}</span>
                  </div>
                  {item.child_ingestion_job_ids.length > 0 ? <small>子任务 #{item.child_ingestion_job_ids.join(", #")}</small> : null}
                  {item.error_message ? <Typography.Text type="danger">{item.error_message}</Typography.Text> : null}
                </article>
              ))}
            </div>
          ),
        },
      ]}
    />
  );
}

export function MarketDataView() {
  const [stats, setStats] = useState<MarketDataStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [checkInput, setCheckInput] = useState("1810.HK");
  const [checkedSymbol, setCheckedSymbol] = useState("1810.HK");
  const [tableKeyword, setTableKeyword] = useState("");
  const [interval, setInterval] = useState<string | undefined>(undefined);
  const [syncInterval, setSyncInterval] = useState("1d");
  const [tdxSyncInterval, setTdxSyncInterval] = useState("1d");
  const [tdxPipelineSyncInterval, setTdxPipelineSyncInterval] = useState("all");
  const [batchLimit, setBatchLimit] = useState(20);
  const [syncing, setSyncing] = useState(false);
  const [syncingSymbol, setSyncingSymbol] = useState(false);
  const [syncingActionKey, setSyncingActionKey] = useState<string | null>(null);
  const [selectedJobId, setSelectedJobId] = useState<number | null>(null);
  const [selectedJobDetail, setSelectedJobDetail] = useState<MarketDataIngestionJobDetail | null>(null);
  const [jobDetailLoading, setJobDetailLoading] = useState(false);
  const [seriesProviderFilter, setSeriesProviderFilter] = useState("all");
  const [providerSeriesRows, setProviderSeriesRows] = useState<MarketDataSeriesRow[]>([]);
  const [providerSeriesLoading, setProviderSeriesLoading] = useState(false);
  const [qfqSymbolFilter, setQfqSymbolFilter] = useState("");
  const [corporateActionRows, setCorporateActionRows] = useState<MarketDataCorporateActionRow[]>([]);
  const [adjustmentSegmentRows, setAdjustmentSegmentRows] = useState<MarketDataAdjustmentSegmentRow[]>([]);
  const [qfqDiagnosticsLoading, setQfqDiagnosticsLoading] = useState(false);
  const [messageApi, contextHolder] = message.useMessage();

  async function loadStatsData(showSpinner: boolean = true) {
    if (showSpinner) {
      setLoading(true);
    }
    const result = await apiFetchSafe<MarketDataStats>("/api/market-data/stats");
    if (result.ok) {
      setStats(result.data);
      setLoadError(null);
    } else {
      setLoadError(result.error.message);
    }
    setLoading(false);
  }

  async function loadProviderSeriesData(providerKey: string = seriesProviderFilter, showSpinner: boolean = true) {
    if (showSpinner) {
      setProviderSeriesLoading(true);
    }
    const path = `/api/market-data/provider-series?provider=${encodeURIComponent(providerKey)}&limit=50`;
    const result = await apiFetchSafe<MarketDataSeriesRow[]>(path);
    if (result.ok) {
      setProviderSeriesRows(result.data);
    } else {
      messageApi.error(result.error.message);
    }
    setProviderSeriesLoading(false);
  }

  async function loadQfqDiagnosticsData(symbol: string = qfqSymbolFilter, showSpinner: boolean = true) {
    if (showSpinner) {
      setQfqDiagnosticsLoading(true);
    }
    const normalizedSymbol = symbol.trim().toUpperCase();
    const symbolQuery = normalizedSymbol ? `&symbol=${encodeURIComponent(normalizedSymbol)}` : "";
    const [actionsResult, segmentsResult] = await Promise.all([
      apiFetchSafe<MarketDataCorporateActionRow[]>(`/api/market-data/corporate-actions?provider=tushare${symbolQuery}&limit=20`),
      apiFetchSafe<MarketDataAdjustmentSegmentRow[]>(`/api/market-data/adjustment-segments?provider=tdx_qfq${symbolQuery}&limit=20`),
    ]);
    if (actionsResult.ok) {
      setCorporateActionRows(actionsResult.data);
    } else {
      messageApi.error(actionsResult.error.message);
    }
    if (segmentsResult.ok) {
      setAdjustmentSegmentRows(segmentsResult.data);
    } else {
      messageApi.error(segmentsResult.error.message);
    }
    setQfqDiagnosticsLoading(false);
  }

  useEffect(() => {
    queueMicrotask(() => {
      void loadStatsData();
      void (async () => {
        setProviderSeriesLoading(true);
        const result = await apiFetchSafe<MarketDataSeriesRow[]>("/api/market-data/provider-series?provider=all&limit=50");
        if (result.ok) {
          setProviderSeriesRows(result.data);
        } else {
          messageApi.error(result.error.message);
        }
        setProviderSeriesLoading(false);
      })();
      void (async () => {
        setQfqDiagnosticsLoading(true);
        const [actionsResult, segmentsResult] = await Promise.all([
          apiFetchSafe<MarketDataCorporateActionRow[]>("/api/market-data/corporate-actions?provider=tushare&limit=20"),
          apiFetchSafe<MarketDataAdjustmentSegmentRow[]>("/api/market-data/adjustment-segments?provider=tdx_qfq&limit=20"),
        ]);
        if (actionsResult.ok) {
          setCorporateActionRows(actionsResult.data);
        } else {
          messageApi.error(actionsResult.error.message);
        }
        if (segmentsResult.ok) {
          setAdjustmentSegmentRows(segmentsResult.data);
        } else {
          messageApi.error(segmentsResult.error.message);
        }
        setQfqDiagnosticsLoading(false);
      })();
    });
  }, [messageApi]);

  function syncPeriodForInterval(targetInterval: string) {
    return targetInterval === "15m" ? "60d" : targetInterval === "1m" ? "7d" : undefined;
  }

  function providerIntervalValue(providerKey: string) {
    if (providerKey === "tdx") {
      return tdxSyncInterval;
    }
    if (providerKey === "tdx_pipeline") {
      return tdxPipelineSyncInterval;
    }
    return "1d";
  }

  function providerIntervalDisplay(providerKey: string) {
    if (providerKey === "tdx") {
      return tdxSyncInterval;
    }
    if (providerKey === "tdx_pipeline") {
      return tdxPipelineSyncInterval;
    }
    return providerKey === "yahoo" ? syncInterval : "1d";
  }

  async function syncAll() {
    setSyncing(true);
    try {
      await apiFetch("/api/market-data/sync", {
        method: "POST",
        body: JSON.stringify({ interval: syncInterval, period: syncPeriodForInterval(syncInterval) }),
      });
      messageApi.success("同步已完成");
      await loadStatsData(false);
      await loadProviderSeriesData(seriesProviderFilter, false);
      await loadQfqDiagnosticsData(qfqSymbolFilter, false);
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "同步失败");
    } finally {
      setSyncing(false);
    }
  }

  async function syncCheckedSymbol() {
    await syncSymbolForInterval(syncInterval);
  }

  async function syncSymbolForInterval(targetInterval: string) {
    const targetSymbol = checkedSymbol.trim().toUpperCase();
    if (!targetSymbol) {
      messageApi.warning("请先输入并检查一个标的");
      return;
    }
    setSyncingSymbol(true);
    setSyncInterval(targetInterval);
    try {
      await apiFetch("/api/market-data/sync", {
        method: "POST",
        body: JSON.stringify({ symbol: targetSymbol, interval: targetInterval, period: syncPeriodForInterval(targetInterval) }),
      });
      messageApi.success(`${targetSymbol} ${targetInterval} 同步完成`);
      await loadStatsData(false);
      await loadProviderSeriesData(seriesProviderFilter, false);
      await loadQfqDiagnosticsData(qfqSymbolFilter || targetSymbol, false);
      setTableKeyword(targetSymbol);
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "同步失败");
    } finally {
      setSyncingSymbol(false);
    }
  }

  async function runProviderAction(providerKey: string, mode: "current" | "batch") {
    if (providerKey === "yahoo") {
      if (mode === "current") {
        await syncSymbolForInterval(syncInterval);
      } else {
        setSyncingActionKey(`${providerKey}:${mode}`);
        try {
          await apiFetch("/api/market-data/sync", {
            method: "POST",
            body: JSON.stringify({
              provider: "yahoo",
              symbol_set: "yahoo_global_active_100",
              interval: syncInterval,
              period: syncPeriodForInterval(syncInterval),
              limit: batchLimit,
            }),
          });
          messageApi.success(`Yahoo 默认样本池 ${syncInterval} 同步完成`);
          await loadStatsData(false);
          await loadProviderSeriesData(seriesProviderFilter, false);
          await loadQfqDiagnosticsData(qfqSymbolFilter, false);
        } catch (error) {
          messageApi.error(error instanceof Error ? error.message : "同步失败");
        } finally {
          setSyncingActionKey(null);
        }
      }
      return;
    }

    const normalizedTarget = normalizeProviderSymbol(providerKey, checkedSymbol);
    if (mode === "current" && !normalizedTarget) {
      messageApi.warning("请先输入一个目标标的，再执行当前标的任务。");
      return;
    }
    const actionKey = `${providerKey}:${mode}`;
    const requestedInterval = providerIntervalValue(providerKey);
    const payload: Record<string, unknown> = {
      provider: providerKey,
      interval: requestedInterval,
    };
    if (mode === "current") {
      payload.symbol = normalizedTarget;
    } else {
      payload.limit = batchLimit;
    }

    setSyncingActionKey(actionKey);
    try {
      await apiFetch("/api/market-data/sync", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      const actionLabel =
        mode === "current"
          ? `${providerKey} ${providerIntervalDisplay(providerKey)} 当前标的任务已完成`
          : `${providerKey} ${providerIntervalDisplay(providerKey)} 批量任务已完成`;
      messageApi.success(actionLabel);
      await loadStatsData(false);
      await loadProviderSeriesData(seriesProviderFilter, false);
      await loadQfqDiagnosticsData(qfqSymbolFilter || normalizedTarget || "", false);
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "同步失败");
    } finally {
      setSyncingActionKey(null);
    }
  }

  async function openJobDetail(jobId: number) {
    setSelectedJobId(jobId);
    setJobDetailLoading(true);
    try {
      const detail = await apiFetch<MarketDataIngestionJobDetail>(`/api/market-data/ingestion-jobs/${jobId}`);
      setSelectedJobDetail(detail);
    } catch (error) {
      setSelectedJobDetail(null);
      messageApi.error(error instanceof Error ? error.message : "读取任务详情失败");
    } finally {
      setJobDetailLoading(false);
    }
  }

  function closeJobDetail() {
    setSelectedJobId(null);
    setSelectedJobDetail(null);
    setJobDetailLoading(false);
  }

  const filteredRows = useMemo(() => {
    if (!stats) {
      return [];
    }
    return stats.coverages.filter((item) => {
      const matchesKeyword =
        !tableKeyword ||
        item.symbol.toLowerCase().includes(tableKeyword.toLowerCase()) ||
        item.name.toLowerCase().includes(tableKeyword.toLowerCase());
      const matchesInterval = !interval || item.interval === interval;
      return matchesKeyword && matchesInterval;
    });
  }, [stats, tableKeyword, interval]);

  const beginnerPresets = useMemo(() => (stats ? buildBeginnerPresets(stats.coverages) : []), [stats]);
  const providerPanels = useMemo<ProviderPanelModel[]>(() => {
    if (!stats) {
      return [];
    }
    return providerPanelConfigs.map((config) => {
      const matched = stats.provider_summaries.find((item) => item.provider_key === config.providerKey);
      return {
        ...config,
        summary:
          matched ?? {
            provider_key: config.providerKey,
            provider_name: config.fallbackName,
            provider_type: "unknown",
            status: "inactive",
            series_count: 0,
            bars_count: 0,
            action_count: 0,
            segment_count: 0,
            manifest_count: 0,
            intervals: [],
            adjustment_kinds: [],
            latest_bar_time: "",
            latest_ingestion_at: "",
            latest_ingestion_status: "",
            latest_ingestion_job_id: null,
          },
        currentTarget: normalizeProviderSymbol(config.providerKey, checkedSymbol),
      };
    });
  }, [checkedSymbol, stats]);

  const coverageProfiles = useMemo<CoverageProfile[]>(() => {
    if (!stats) {
      return [];
    }
    const grouped = new Map<string, CoverageProfile>();
    for (const item of stats.coverages) {
      const current =
        grouped.get(item.symbol) ??
        {
          symbol: item.symbol,
          name: item.name || item.symbol,
          intervals: new Set<string>(),
        };
      current.name = current.name || item.name || item.symbol;
      current.intervals.add(item.interval);
      grouped.set(item.symbol, current);
    }
    return Array.from(grouped.values());
  }, [stats]);

  const coverageInsights = useMemo<CoverageInsight[]>(() => {
    const sortedProfiles = [...coverageProfiles].sort(compareCoverageProfile);
    const readyProfiles = sortedProfiles.filter((item) => item.intervals.has("1d") && item.intervals.has("15m"));
    const dailyOnlyProfiles = sortedProfiles.filter((item) => item.intervals.has("1d") && !item.intervals.has("15m"));
    const partialProfiles = sortedProfiles.filter((item) => !item.intervals.has("1d"));

    return [
      {
        key: "ready",
        value: `${readyProfiles.length} 个`,
        title: "可直接开展研究",
        description: "同时具备 1d 和 15m，适合作为标准研究样本。",
        recommendation: "优先从这类标的中选择，不需要额外补数。",
        examples: readyProfiles.slice(0, 3),
      },
      {
        key: "daily-only",
        value: `${dailyOnlyProfiles.length} 个`,
        title: "只适合长周期",
        description: "目前只有日线，适合先做定投或日线策略验证。",
        recommendation: "可以先跑日线或定投，再决定要不要继续补 15m。",
        examples: dailyOnlyProfiles.slice(0, 3),
      },
      {
        key: "partial",
        value: `${partialProfiles.length} 个`,
        title: "还需补关键周期",
        description: "只有分钟线或缺少 1d / 15m，建议先补齐再开始。",
        recommendation: "先补 1d 或 15m，再回到创建回测页。",
        examples: partialProfiles.slice(0, 3),
      },
    ];
  }, [coverageProfiles]);
  const readySymbolCount = useMemo(
    () => coverageProfiles.filter((item) => item.intervals.has("1d") && item.intervals.has("15m")).length,
    [coverageProfiles],
  );

  const symbolRows = useMemo(() => {
    if (!stats || !checkedSymbol.trim()) {
      return [];
    }
    const normalizedKeyword = checkedSymbol.trim().toLowerCase();
    return stats.coverages.filter((item) => item.symbol.toLowerCase() === normalizedKeyword);
  }, [stats, checkedSymbol]);

  const symbolIntervals = useMemo(() => new Set(symbolRows.map((item) => item.interval)), [symbolRows]);

  const readiness = useMemo(() => {
    if (!checkedSymbol.trim()) {
      return { label: "待输入标的", color: "default", description: "例如 1810.HK、0700.HK、513050.SS。" };
    }
    if (symbolRows.length === 0) {
      return { label: "未找到覆盖", color: "red", description: "当前还没有该标的行情。可先确认代码格式，再执行同步。" };
    }
    const daily = symbolIntervals.has("1d");
    const intraday = Array.from(symbolIntervals).some((item) => item !== "1d");
    if (daily && intraday) {
      return { label: "覆盖可用", color: "green", description: "该标的已同时具备日线和分钟级数据，可直接创建回测。" };
    }
    return { label: "覆盖有限", color: "gold", description: "该标的已有部分周期数据，建议先确认策略所需周期是否齐备。" };
  }, [checkedSymbol, symbolRows, symbolIntervals]);

  const intervalRecommendations = useMemo<IntervalRecommendation[]>(() => {
    if (!checkedSymbol.trim()) {
      return [];
    }
    if (symbolRows.length === 0) {
      return [
        {
          interval: "1d",
          title: "先补日线",
          description: "建议先补 1d，用于长期回测、定投研究和基础可用性检查。",
        },
        {
          interval: "15m",
          title: "再补 15m",
          description: "若计划运行网格或短周期反弹策略，再补 15m 即可覆盖大部分分钟级研究。",
        },
      ];
    }

    const recommendations: IntervalRecommendation[] = [];
    if (!symbolIntervals.has("1d")) {
      recommendations.push({
        interval: "1d",
        title: "补日线",
        description: "补 1d 后可以做定投、日线择时和更长区间的稳健复盘。",
      });
    }
    if (!symbolIntervals.has("15m")) {
      recommendations.push({
        interval: "15m",
        title: "补 15m",
        description: "补齐 15m 后，可直接覆盖默认分钟网格与大多数分钟级基线策略。",
      });
    }
    if (symbolIntervals.has("15m") && !symbolIntervals.has("1m")) {
      recommendations.push({
        interval: "1m",
        title: "补 1m",
        description: "只有当你需要更细粒度的分钟信号时，再补 1m 做更高频的研究。",
      });
    }
    return recommendations;
  }, [checkedSymbol, symbolRows, symbolIntervals]);

  const checkedSymbolLaunchHref = useMemo(() => {
    const normalizedSymbol = checkedSymbol.trim().toUpperCase();
    if (!normalizedSymbol || symbolRows.length === 0) {
      return null;
    }
    if (symbolIntervals.has("15m")) {
      return buildBacktestLaunchHref({ symbol: normalizedSymbol, interval: "15m", strategyKind: "grid" });
    }
    if (symbolIntervals.has("1d")) {
      return buildBacktestLaunchHref({ symbol: normalizedSymbol, interval: "1d", strategyKind: "dca" });
    }
    if (symbolIntervals.has("1m")) {
      return buildBacktestLaunchHref({ symbol: normalizedSymbol, interval: "1m", strategyKind: "grid" });
    }
    return null;
  }, [checkedSymbol, symbolIntervals, symbolRows.length]);
  const startDecisionCards = useMemo(
    () => buildStartDecisionCards(checkedSymbol, symbolRows, symbolIntervals, intervalRecommendations, readySymbolCount),
    [checkedSymbol, intervalRecommendations, readySymbolCount, symbolIntervals, symbolRows],
  );
  const symbolIntervalCards = useMemo(
    () => buildSymbolIntervalCards(symbolIntervals, symbolRows.length > 0),
    [symbolIntervals, symbolRows.length],
  );
  const primaryResearchPath = useMemo(
    () =>
      buildPrimaryResearchPath({
        checkedSymbol,
        hasRows: symbolRows.length > 0,
        intervalRecommendations,
        symbolIntervals,
      }),
    [checkedSymbol, intervalRecommendations, symbolIntervals, symbolRows.length],
  );
  const unifiedBarsCount = useMemo(
    () => providerPanels.reduce((total, item) => total + item.summary.bars_count, 0),
    [providerPanels],
  );
  const corporateActionCount = useMemo(
    () => providerPanels.reduce((total, item) => total + item.summary.action_count, 0),
    [providerPanels],
  );
  const adjustmentSegmentCount = useMemo(
    () => providerPanels.reduce((total, item) => total + item.summary.segment_count, 0),
    [providerPanels],
  );
  const activeProviderCount = useMemo(
    () =>
      providerPanels.filter(
        (item) =>
          item.summary.series_count > 0 ||
          item.summary.action_count > 0 ||
          item.summary.segment_count > 0 ||
          item.summary.manifest_count > 0 ||
          item.summary.latest_ingestion_at,
      ).length,
    [providerPanels],
  );
  const recentIngestionJobs = stats?.recent_ingestion_jobs ?? [];
  const batchLimitOptions = [
    { label: "10", value: 10 },
    { label: "20", value: 20 },
    { label: "50", value: 50 },
    { label: "100", value: 100 },
  ];
  const providerSeriesOptions = useMemo(
    () => [
      { label: "全部渠道", value: "all" },
      ...providerPanels.map((item) => ({
        label: item.summary.provider_name || item.fallbackName,
        value: item.providerKey,
      })),
    ],
    [providerPanels],
  );
  const selectedJobItems = useMemo(() => selectedJobDetail?.items ?? [], [selectedJobDetail]);
  const selectedJobFailedItems = useMemo(
    () => selectedJobItems.filter((item) => item.status === "failed" || item.error_message),
    [selectedJobItems],
  );

  function applyCheckedSymbol(targetSymbol: string) {
    const normalizedSymbol = targetSymbol.trim().toUpperCase();
    setCheckInput(normalizedSymbol);
    setCheckedSymbol(normalizedSymbol);
    setTableKeyword(normalizedSymbol);
  }

  function checkSymbol() {
    applyCheckedSymbol(checkInput);
  }

  if (loading && !stats) {
    return <Skeleton active paragraph={{ rows: 10 }} />;
  }

  if (!stats) {
    return <PageErrorState title="数据准备页暂时不可用" description={loadError ?? "暂时无法读取数据覆盖状态"} onRetry={() => void loadStatsData()} />;
  }

  return (
    <div className="page-stack">
      {contextHolder}
      <PageHeader
        eyebrow="数据准备"
        title="多渠道数据准备"
        description="先设定当前目标标的，再决定是补 Yahoo 回测样本、执行 A 股统一补数链路、导入通达信原始 all/1d/1m/5m、抓取 Tushare 公司行动，还是单独重算前复权。"
      />

      <Card size="small" className="section-card data-check-card">
        <div className="data-check-main">
          <Typography.Title level={4}>设定当前目标标的</Typography.Title>
          <Typography.Paragraph>
            下方多渠道卡片会复用这里的标的代码。当前覆盖检查仍主要围绕可直接回测的样本覆盖，A 股统一补数链路、原始 all/1d/1m/5m、公司行动和前复权状态请看后面的多渠道任务面板。
          </Typography.Paragraph>
          <Space.Compact className="data-check-input">
            <Input
              value={checkInput}
              onChange={(event) => setCheckInput(event.target.value)}
              onPressEnter={checkSymbol}
              placeholder="例如 1810.HK、SH600000、600000.SH"
            />
            <Button type="primary" onClick={checkSymbol}>
              设为当前标的
            </Button>
          </Space.Compact>
        </div>
        <div className="data-check-result">
          <Tag color={readiness.color}>{readiness.label}</Tag>
          <strong>{symbolRows[0]?.name ?? (checkedSymbol || "等待输入")}</strong>
          {checkedSymbol ? <small>最近检查：{checkedSymbol}</small> : null}
          <span>{readiness.description}</span>
          <small>多渠道任务会自动把当前输入转换成各 provider 所需格式，例如 `SH600000` / `600000.SH`。</small>
          {intervalRecommendations.length > 0 ? (
            <div className="data-recommend-list">
              {intervalRecommendations.map((item) => (
                <div key={item.interval} className="data-recommend-item">
                  <div>
                    <b>{item.title}</b>
                    <small>{item.description}</small>
                  </div>
                  <Button size="small" loading={syncingSymbol && syncInterval === item.interval} onClick={() => void syncSymbolForInterval(item.interval)}>
                    同步 {item.interval}
                  </Button>
                </div>
              ))}
            </div>
          ) : null}
          <div className="data-check-actions">
            <Button loading={syncingSymbol} onClick={() => void syncCheckedSymbol()}>
              同步当前标的 {syncInterval}
            </Button>
            <small>若不确定补数顺序，优先按上方推荐周期执行；这里主要处理现有回测样本覆盖，其他渠道请使用下方 provider 卡片。</small>
          </div>
        </div>
      </Card>

      <Card size="small" title="多渠道任务面板" className="section-card">
        <div className="provider-overview-banner">
          <div>
            <strong>同一页直接管理 Yahoo、A 股统一补数链路、通达信原始 all/1d/1m/5m、Tushare 公司行动和通达信前复权</strong>
            <p>当前目标标的：{checkedSymbol || "未设置"}。Yahoo 使用上方当前周期；TDX 与统一补数链路在卡片内单独选择周期；其余批量任务使用这里的批量上限。</p>
          </div>
          <Space wrap>
            <Select value={syncInterval} options={intervalOptions} onChange={setSyncInterval} style={{ width: 120 }} />
            <Select value={batchLimit} options={batchLimitOptions} onChange={setBatchLimit} style={{ width: 120 }} />
          </Space>
        </div>
        <div className="provider-panel-grid">
          {providerPanels.map((provider) => (
            <article key={provider.providerKey} className="provider-panel-card">
              <div className="provider-panel-head">
                <div>
                  <span>{provider.title}</span>
                  <strong>{provider.summary.provider_name || provider.fallbackName}</strong>
                </div>
                <StatusTag
                  value={provider.summary.latest_ingestion_status || provider.summary.status}
                  label={ingestionStatusLabel(provider.summary.latest_ingestion_status || provider.summary.status || "inactive")}
                />
              </div>
              <p>{provider.description}</p>
              <div className="provider-panel-meta">
                <small>{provider.symbolHint}</small>
                <small>当前任务目标：{provider.currentTarget || "未设置"}</small>
                <small>
                  {provider.providerKey === "tdx"
                    ? `当前选择：${tdxSyncInterval}（${provider.currentIntervalLabel}）`
                    : provider.providerKey === "tdx_pipeline"
                      ? `当前选择：${tdxPipelineSyncInterval}（${provider.currentIntervalLabel}）`
                    : provider.currentIntervalLabel}
                </small>
              </div>
              {provider.providerKey === "tdx" || provider.providerKey === "tdx_pipeline" ? (
                <div className="provider-panel-meta">
                  <small>导入周期</small>
                  <Select
                    size="small"
                    value={provider.providerKey === "tdx" ? tdxSyncInterval : tdxPipelineSyncInterval}
                    options={provider.providerKey === "tdx" ? tdxIntervalOptions : tdxPipelineIntervalOptions}
                    onChange={provider.providerKey === "tdx" ? setTdxSyncInterval : setTdxPipelineSyncInterval}
                    style={{ width: 180 }}
                  />
                </div>
              ) : null}
              <div className="provider-panel-metric-grid">
                <div className="provider-panel-metric">
                  <span>序列</span>
                  <strong>{provider.summary.series_count.toLocaleString()}</strong>
                </div>
                <div className="provider-panel-metric">
                  <span>K 线</span>
                  <strong>{provider.summary.bars_count.toLocaleString()}</strong>
                </div>
                <div className="provider-panel-metric">
                  <span>公司行动</span>
                  <strong>{provider.summary.action_count.toLocaleString()}</strong>
                </div>
                <div className="provider-panel-metric">
                  <span>前复权区间</span>
                  <strong>{provider.summary.segment_count.toLocaleString()}</strong>
                </div>
                <div className="provider-panel-metric">
                  <span>Manifest</span>
                  <strong>{provider.summary.manifest_count.toLocaleString()}</strong>
                </div>
              </div>
              <div className="provider-panel-tags">
                {(provider.summary.intervals.length > 0 ? provider.summary.intervals : ["未形成序列"]).map((item) => (
                  <Tag key={`${provider.providerKey}-interval-${item}`}>{item}</Tag>
                ))}
                {provider.summary.adjustment_kinds.map((item) => (
                  <Tag key={`${provider.providerKey}-adjustment-${item}`} color="cyan">
                    {item}
                  </Tag>
                ))}
              </div>
              <div className="provider-panel-latest">
                <span>最近导入</span>
                <strong>{provider.summary.latest_ingestion_at || "暂无任务记录"}</strong>
                <small>最近 K 线时间：{provider.summary.latest_bar_time || "暂无"}</small>
              </div>
              <div className="provider-panel-actions">
                <Button
                  loading={syncingActionKey === `${provider.providerKey}:current`}
                  onClick={() => void runProviderAction(provider.providerKey, "current")}
                >
                  {provider.providerKey === "yahoo"
                    ? `${provider.currentActionLabel} ${syncInterval}`
                    : provider.providerKey === "tdx" || provider.providerKey === "tdx_pipeline"
                      ? `${provider.currentActionLabel} ${providerIntervalDisplay(provider.providerKey)}`
                      : provider.currentActionLabel}
                </Button>
                <Button
                  type="primary"
                  loading={syncingActionKey === `${provider.providerKey}:batch`}
                  onClick={() => void runProviderAction(provider.providerKey, "batch")}
                >
                  {provider.providerKey === "yahoo"
                    ? `${provider.batchActionLabel} ${batchLimit} 个`
                    : provider.providerKey === "tdx" || provider.providerKey === "tdx_pipeline"
                      ? `${provider.batchActionLabel} ${providerIntervalDisplay(provider.providerKey)} ${batchLimit} 项`
                      : `${provider.batchActionLabel} ${batchLimit} 项`}
                </Button>
              </div>
            </article>
          ))}
        </div>
      </Card>

      <Card size="small" title="最近导入任务" className="section-card">
        <div className="provider-overview-banner compact">
          <div>
            <strong>统一任务域会同时记录 Yahoo、A 股统一补数链路、TDX、Tushare 和前复权重算</strong>
            <p>这里优先看最近一次批量或单标的导入是否成功，再决定是否深入排查某个 provider。</p>
          </div>
        </div>
        {recentIngestionJobs.length === 0 ? (
          <Typography.Text type="secondary">当前还没有导入任务记录。执行任一 provider 操作后，这里会显示统一任务状态。</Typography.Text>
        ) : (
          <>
            <div className="ingestion-mobile-list">
              {recentIngestionJobs.slice(0, 8).map((job) => (
                <article key={job.id} className="ingestion-mobile-card">
                  <div className="ingestion-mobile-card-head">
                    <div>
                      <strong>任务 #{job.id}</strong>
                      <span>{job.provider_name || job.provider_key || "未命名渠道"}</span>
                    </div>
                    <StatusTag value={job.status} label={ingestionStatusLabel(job.status)} />
                  </div>
                  <div className="ingestion-mobile-metrics">
                    <span>目标 {buildIngestionTargetLabel(job)}</span>
                    <span>进度 {job.targets_completed}/{job.targets_total || 0}</span>
                    <span>新增 {job.rows_inserted.toLocaleString()}</span>
                    <span>更新 {job.rows_updated.toLocaleString()}</span>
                  </div>
                  <small>申请时间：{job.requested_at || "-"}</small>
                  {extractChildIngestionJobIds(job).length > 0 ? <small>子任务 #{extractChildIngestionJobIds(job).join(", #")}</small> : null}
                  {job.error_message ? <Typography.Text type="danger">{job.error_message}</Typography.Text> : null}
                  <Button size="small" onClick={() => void openJobDetail(job.id)}>
                    查看详情
                  </Button>
                  {renderWorkflowSummary(job)}
                </article>
              ))}
            </div>
            <Table<MarketDataIngestionJob>
              className="ingestion-desktop-table"
              size="small"
              rowKey="id"
              dataSource={recentIngestionJobs}
              pagination={{ pageSize: 8, showSizeChanger: false }}
              scroll={{ x: 1180 }}
              expandable={{
                expandedRowRender: (row) => renderWorkflowSummary(row),
                rowExpandable: (row) => extractWorkflowResults(row).length > 0 || extractChildIngestionJobIds(row).length > 0,
              }}
              columns={[
                { title: "编号", dataIndex: "id", width: 80, fixed: "left" },
                {
                  title: "渠道",
                  width: 180,
                  render: (_, row) => (
                    <div className="ingestion-provider-cell">
                      <strong>{row.provider_name || row.provider_key || "-"}</strong>
                      <span>{row.provider_key || "-"}</span>
                    </div>
                  ),
                },
                { title: "任务类型", dataIndex: "job_type", width: 180 },
                { title: "目标", width: 180, render: (_, row) => buildIngestionTargetLabel(row) },
                { title: "状态", dataIndex: "status", width: 110, render: (value: string) => <StatusTag value={value} label={ingestionStatusLabel(value)} /> },
                { title: "完成/总数", width: 110, render: (_, row) => `${row.targets_completed}/${row.targets_total}` },
                { title: "新增", dataIndex: "rows_inserted", width: 110, render: (value: number) => value.toLocaleString() },
                { title: "更新", dataIndex: "rows_updated", width: 110, render: (value: number) => value.toLocaleString() },
                { title: "申请时间", dataIndex: "requested_at", width: 180 },
                { title: "完成时间", dataIndex: "completed_at", width: 180 },
                {
                  title: "详情",
                  width: 110,
                  fixed: "right",
                  render: (_, row) => (
                    <Button size="small" onClick={() => void openJobDetail(row.id)}>
                      查看详情
                    </Button>
                  ),
                },
              ]}
            />
          </>
        )}
      </Card>

      <Card size="small" title="统一序列检查" className="section-card">
        <div className="provider-overview-banner compact">
          <div>
            <strong>按渠道检查 `market_data_series` 的真实持久化结果</strong>
            <p>这里直接看统一主干表中的序列范围、周期、复权口径和最近入库时间，用于判断“任务跑完之后，数据库里到底留下了什么”。</p>
          </div>
          <Space wrap>
            <Select
              value={seriesProviderFilter}
              options={providerSeriesOptions}
              onChange={(value) => {
                setSeriesProviderFilter(value);
                void loadProviderSeriesData(value);
              }}
              style={{ width: 200 }}
            />
            <Button loading={providerSeriesLoading} onClick={() => void loadProviderSeriesData(seriesProviderFilter)}>
              刷新序列
            </Button>
          </Space>
        </div>
        {providerSeriesLoading && providerSeriesRows.length === 0 ? (
          <Skeleton active paragraph={{ rows: 6 }} />
        ) : providerSeriesRows.length === 0 ? (
          <Typography.Text type="secondary">当前筛选条件下还没有统一序列记录。</Typography.Text>
        ) : (
          <>
            <div className="ingestion-mobile-list">
              {providerSeriesRows.slice(0, 8).map((row) => (
                <article key={row.series_id} className="ingestion-mobile-card">
                  <div className="ingestion-mobile-card-head">
                    <div>
                      <strong>{row.instrument_symbol}</strong>
                      <span>{row.provider_name || row.provider_key}</span>
                    </div>
                    <Tag color={row.is_active ? "green" : "default"}>{row.interval}</Tag>
                  </div>
                  <div className="ingestion-mobile-metrics">
                    <span>复权 {row.adjustment_kind}</span>
                    <span>K 线 {row.bar_count.toLocaleString()}</span>
                    <span>市场 {row.market || row.exchange || "-"}</span>
                  </div>
                  <small>源代码：{row.source_symbol || "-"}</small>
                  <small>最新 K 线：{row.last_bar_time || "暂无"}</small>
                </article>
              ))}
            </div>
            <Table<MarketDataSeriesRow>
              size="small"
              rowKey="series_id"
              dataSource={providerSeriesRows}
              pagination={{ pageSize: 10, showSizeChanger: false }}
              scroll={{ x: 1400 }}
              columns={[
                { title: "序列", dataIndex: "series_id", width: 90, fixed: "left" },
                {
                  title: "标的",
                  width: 180,
                  render: (_, row) => (
                    <div className="ingestion-provider-cell">
                      <strong>{row.instrument_symbol}</strong>
                      <span>{row.instrument_name || row.source_symbol || row.instrument_symbol}</span>
                    </div>
                  ),
                },
                {
                  title: "渠道",
                  width: 180,
                  render: (_, row) => (
                    <div className="ingestion-provider-cell">
                      <strong>{row.provider_name || row.provider_key}</strong>
                      <span>{row.provider_key}</span>
                    </div>
                  ),
                },
                { title: "源代码", dataIndex: "source_symbol", width: 140 },
                { title: "市场", dataIndex: "market", width: 100 },
                { title: "交易所", dataIndex: "exchange", width: 100 },
                { title: "周期", dataIndex: "interval", width: 90 },
                { title: "复权", dataIndex: "adjustment_kind", width: 100 },
                { title: "Session", dataIndex: "session_type", width: 100 },
                { title: "价格类型", dataIndex: "price_type", width: 110 },
                { title: "K线类型", dataIndex: "bar_type", width: 110 },
                { title: "条数", dataIndex: "bar_count", width: 100, render: (value: number) => value.toLocaleString() },
                { title: "首条时间", dataIndex: "first_bar_time", width: 180 },
                { title: "最新时间", dataIndex: "last_bar_time", width: 180 },
                { title: "最近入库", dataIndex: "last_ingested_at", width: 180 },
              ]}
            />
          </>
        )}
      </Card>

      <Card size="small" title="前复权输入与公式检查" className="section-card">
        <div className="provider-overview-banner compact">
          <div>
            <strong>直接检查 `corporate_action_events` 和 `price_adjustment_segments`</strong>
            <p>当 Tushare 抓取或前复权任务显示成功，但你还想确认“到底抓到了哪些实施事件、生成了哪些公式区间”时，就在这里按标的核对。</p>
          </div>
          <Space wrap>
            <Input
              placeholder="留空看最近记录，或输入 SH600000"
              value={qfqSymbolFilter}
              onChange={(event) => setQfqSymbolFilter(event.target.value.toUpperCase())}
              style={{ width: 220 }}
            />
            <Button
              onClick={() => {
                const normalized = checkedSymbol.trim().toUpperCase();
                setQfqSymbolFilter(normalized);
                void loadQfqDiagnosticsData(normalized);
              }}
            >
              使用当前标的
            </Button>
            <Button loading={qfqDiagnosticsLoading} onClick={() => void loadQfqDiagnosticsData(qfqSymbolFilter)}>
              刷新排查
            </Button>
          </Space>
        </div>
        <div className="page-stack">
          <Card size="small" title="最近公司行动">
            {qfqDiagnosticsLoading && corporateActionRows.length === 0 ? (
              <Skeleton active paragraph={{ rows: 4 }} />
            ) : corporateActionRows.length === 0 ? (
              <Typography.Text type="secondary">当前筛选条件下还没有 Tushare 实施事件。</Typography.Text>
            ) : (
              <>
                <div className="ingestion-mobile-list">
                  {corporateActionRows.slice(0, 6).map((row) => (
                    <article key={row.event_id} className="ingestion-mobile-card">
                      <div className="ingestion-mobile-card-head">
                        <div>
                          <strong>{row.instrument_symbol}</strong>
                          <span>{row.provider_name || row.provider_key}</span>
                        </div>
                        <Tag>{row.action_type}</Tag>
                      </div>
                      <div className="ingestion-mobile-metrics">
                        <span>除权日 {row.ex_date || "-"}</span>
                        <span>现金 {row.cash_dividend}</span>
                        <span>送转 {(row.stock_bonus_ratio + row.stock_conversion_ratio).toFixed(4)}</span>
                      </div>
                      <small>源代码：{row.source_symbol || "-"}</small>
                    </article>
                  ))}
                </div>
                <Table<MarketDataCorporateActionRow>
                  size="small"
                  rowKey="event_id"
                  dataSource={corporateActionRows}
                  pagination={{ pageSize: 8, showSizeChanger: false }}
                  scroll={{ x: 1440 }}
                  columns={[
                    { title: "事件", dataIndex: "event_id", width: 90, fixed: "left" },
                    {
                      title: "标的",
                      width: 180,
                      render: (_, row) => (
                        <div className="ingestion-provider-cell">
                          <strong>{row.instrument_symbol}</strong>
                          <span>{row.instrument_name || row.source_symbol || row.instrument_symbol}</span>
                        </div>
                      ),
                    },
                    { title: "源代码", dataIndex: "source_symbol", width: 140 },
                    { title: "类型", dataIndex: "action_type", width: 100 },
                    { title: "公告日", dataIndex: "announce_date", width: 120 },
                    { title: "登记日", dataIndex: "record_date", width: 120 },
                    { title: "除权日", dataIndex: "ex_date", width: 120 },
                    { title: "派息日", dataIndex: "pay_date", width: 120 },
                    { title: "现金分红", dataIndex: "cash_dividend", width: 110 },
                    { title: "送股", dataIndex: "stock_bonus_ratio", width: 90 },
                    { title: "转增", dataIndex: "stock_conversion_ratio", width: 90 },
                    { title: "配股比例", dataIndex: "rights_ratio", width: 100 },
                    { title: "配股价", dataIndex: "rights_price", width: 100 },
                    { title: "状态", dataIndex: "status", width: 100 },
                    { title: "最近更新", dataIndex: "updated_at", width: 180 },
                  ]}
                />
              </>
            )}
          </Card>

          <Card size="small" title="最近复权区间">
            {qfqDiagnosticsLoading && adjustmentSegmentRows.length === 0 ? (
              <Skeleton active paragraph={{ rows: 4 }} />
            ) : adjustmentSegmentRows.length === 0 ? (
              <Typography.Text type="secondary">当前筛选条件下还没有前复权公式区间。</Typography.Text>
            ) : (
              <>
                <div className="ingestion-mobile-list">
                  {adjustmentSegmentRows.slice(0, 6).map((row) => (
                    <article key={row.segment_id} className="ingestion-mobile-card">
                      <div className="ingestion-mobile-card-head">
                        <div>
                          <strong>{row.instrument_symbol}</strong>
                          <span>{row.provider_name || row.provider_key}</span>
                        </div>
                        <Tag>{row.adjustment_kind}</Tag>
                      </div>
                      <div className="ingestion-mobile-metrics">
                        <span>{row.start_date || "-"} 至 {row.end_date || "-"}</span>
                        <span>A {row.adjust_a.toFixed(6)}</span>
                        <span>B {row.adjust_b.toFixed(6)}</span>
                      </div>
                      <small>事件数：{String(row.payload_json.event_count ?? "-")}</small>
                    </article>
                  ))}
                </div>
                <Table<MarketDataAdjustmentSegmentRow>
                  size="small"
                  rowKey="segment_id"
                  dataSource={adjustmentSegmentRows}
                  pagination={{ pageSize: 8, showSizeChanger: false }}
                  scroll={{ x: 1320 }}
                  columns={[
                    { title: "区间", dataIndex: "segment_id", width: 90, fixed: "left" },
                    {
                      title: "标的",
                      width: 180,
                      render: (_, row) => (
                        <div className="ingestion-provider-cell">
                          <strong>{row.instrument_symbol}</strong>
                          <span>{row.instrument_name || row.instrument_symbol}</span>
                        </div>
                      ),
                    },
                    { title: "复权", dataIndex: "adjustment_kind", width: 90 },
                    { title: "起始日", dataIndex: "start_date", width: 120 },
                    { title: "结束日", dataIndex: "end_date", width: 120 },
                    { title: "AdjustA", dataIndex: "adjust_a", width: 120, render: (value: number) => value.toFixed(8) },
                    { title: "AdjustB", dataIndex: "adjust_b", width: 120, render: (value: number) => value.toFixed(8) },
                    { title: "事件来源", dataIndex: "action_provider_name", width: 140 },
                    {
                      title: "事件数",
                      width: 90,
                      render: (_, row) => String(row.payload_json.event_count ?? "-"),
                    },
                    { title: "状态", dataIndex: "status", width: 100 },
                    { title: "生成时间", dataIndex: "generated_at", width: 180 },
                    { title: "最近更新", dataIndex: "updated_at", width: 180 },
                  ]}
                />
              </>
            )}
          </Card>
        </div>
      </Card>

      <Drawer
        title={selectedJobId ? `导入任务 #${selectedJobId}` : "导入任务详情"}
        placement="right"
        width={720}
        open={selectedJobId !== null}
        onClose={closeJobDetail}
        destroyOnClose
      >
        {jobDetailLoading ? (
          <Skeleton active paragraph={{ rows: 8 }} />
        ) : !selectedJobDetail ? (
          <Empty description="暂无任务详情" />
        ) : (
          <div className="page-stack">
            <Card size="small" title="任务概览">
              <div className="provider-panel-metric-grid">
                <div className="provider-panel-metric">
                  <span>渠道</span>
                  <strong>{selectedJobDetail.provider_name || selectedJobDetail.provider_key || "-"}</strong>
                </div>
                <div className="provider-panel-metric">
                  <span>状态</span>
                  <strong>{ingestionStatusLabel(selectedJobDetail.status)}</strong>
                </div>
                <div className="provider-panel-metric">
                  <span>目标</span>
                  <strong>{buildIngestionTargetLabel(selectedJobDetail)}</strong>
                </div>
                <div className="provider-panel-metric">
                  <span>完成/总数</span>
                  <strong>{selectedJobDetail.targets_completed}/{selectedJobDetail.targets_total}</strong>
                </div>
                <div className="provider-panel-metric">
                  <span>新增</span>
                  <strong>{selectedJobDetail.rows_inserted.toLocaleString()}</strong>
                </div>
                <div className="provider-panel-metric">
                  <span>更新</span>
                  <strong>{selectedJobDetail.rows_updated.toLocaleString()}</strong>
                </div>
              </div>
              <div className="provider-panel-tags">
                <Tag>{selectedJobDetail.job_type}</Tag>
                <Tag>{selectedJobDetail.requested_via || "manual"}</Tag>
                <Tag color={selectedJobFailedItems.length > 0 ? "red" : "green"}>
                  失败子项 {selectedJobFailedItems.length}
                </Tag>
              </div>
              {selectedJobDetail.error_message ? <Typography.Text type="danger">{selectedJobDetail.error_message}</Typography.Text> : null}
              {renderWorkflowSummary(selectedJobDetail)}
            </Card>

            <Card size="small" title="子项明细">
              {selectedJobItems.length === 0 ? (
                <Typography.Text type="secondary">当前任务还没有子项明细。</Typography.Text>
              ) : (
                <>
                  <div className="ingestion-mobile-list">
                    {selectedJobItems.map((item) => (
                      <article key={item.id} className="ingestion-mobile-card">
                        <div className="ingestion-mobile-card-head">
                          <div>
                            <strong>{item.instrument_symbol || item.source_symbol || item.item_key}</strong>
                            <span>{item.interval || item.stage || "-"}</span>
                          </div>
                          <StatusTag value={item.status} label={ingestionStatusLabel(item.status)} />
                        </div>
                        <div className="ingestion-mobile-metrics">
                          <span>阶段 {item.stage || "-"}</span>
                          <span>新增 {item.rows_inserted.toLocaleString()}</span>
                          <span>更新 {item.rows_updated.toLocaleString()}</span>
                        </div>
                        <small>{item.item_key}</small>
                        {item.error_message ? <Typography.Text type="danger">{item.error_message}</Typography.Text> : null}
                      </article>
                    ))}
                  </div>
                  <Table<MarketDataIngestionJobItem>
                    size="small"
                    rowKey="id"
                    dataSource={selectedJobItems}
                    pagination={{ pageSize: 10, showSizeChanger: false }}
                    scroll={{ x: 1080 }}
                    columns={[
                      { title: "编号", dataIndex: "id", width: 80 },
                      {
                        title: "标的/文件",
                        width: 220,
                        render: (_, row) => (
                          <div className="ingestion-provider-cell">
                            <strong>{row.instrument_symbol || row.source_symbol || "-"}</strong>
                            <span>{row.item_key}</span>
                          </div>
                        ),
                      },
                      { title: "周期", dataIndex: "interval", width: 100 },
                      { title: "阶段", dataIndex: "stage", width: 120 },
                      { title: "状态", dataIndex: "status", width: 110, render: (value: string) => <StatusTag value={value} label={ingestionStatusLabel(value)} /> },
                      { title: "新增", dataIndex: "rows_inserted", width: 100, render: (value: number) => value.toLocaleString() },
                      { title: "更新", dataIndex: "rows_updated", width: 100, render: (value: number) => value.toLocaleString() },
                      { title: "开始时间", dataIndex: "started_at", width: 180 },
                      { title: "完成时间", dataIndex: "completed_at", width: 180 },
                      { title: "错误", dataIndex: "error_message", width: 260 },
                    ]}
                  />
                </>
              )}
            </Card>
          </div>
        )}
      </Drawer>

      <Card size="small" className="section-card start-path-card">
        <div className="start-path-main">
          <strong>{primaryResearchPath.title}</strong>
          <p>{primaryResearchPath.description}</p>
          <div className="start-path-guide-grid">
            {startDecisionCards.map((item) => (
              <article key={item.title} className="start-path-guide-card">
                <span>{item.title}</span>
                <strong>{item.value}</strong>
                <p>{item.description}</p>
              </article>
            ))}
          </div>
        </div>
        <div className="start-path-actions">
          {checkedSymbolLaunchHref ? (
            <Button type="primary">
              <Link href={checkedSymbolLaunchHref}>基于当前标的创建回测</Link>
            </Button>
          ) : null}
          {beginnerPresets[0] ? (
            <Button>
              <Link href={buildBacktestPresetHref(beginnerPresets[0])}>使用推荐样本创建回测</Link>
            </Button>
          ) : null}
          {intervalRecommendations[0] ? (
            <Button loading={syncingSymbol && syncInterval === intervalRecommendations[0].interval} onClick={() => void syncSymbolForInterval(intervalRecommendations[0].interval)}>
              先补 {intervalRecommendations[0].interval}
            </Button>
          ) : null}
        </div>
      </Card>

      <Card size="small" title="当前标的下一步" className="section-card">
        <div className="data-next-step-grid">
          <div className="data-next-step-main">
            <div className="data-next-step-banner">
              <strong>
                {checkedSymbol.trim()
                  ? `${checkedSymbol.trim().toUpperCase()} 的研究准备情况`
                  : "先输入一个标的，页面会告诉你最短研究路径"}
              </strong>
              <p>
                目标不是一次性补齐所有周期，而是先回答两个问题：这只标的现在能不能直接跑？如果不能，最先该补哪个周期？
              </p>
            </div>
            <div className="data-next-step-card-grid">
              {symbolIntervalCards.map((item) => (
                <article key={item.interval} className={`data-next-step-card${item.ready ? " is-ready" : ""}`}>
                  <div className="data-next-step-card-head">
                    <Tag color={item.ready ? "green" : "default"}>{item.interval}</Tag>
                    <span>{item.title}</span>
                  </div>
                  <strong>{item.value}</strong>
                  <p>{item.description}</p>
                  {!item.ready && checkedSymbol.trim() ? (
                    <Button
                      size="small"
                      loading={syncingSymbol && syncInterval === item.interval}
                      onClick={() => void syncSymbolForInterval(item.interval)}
                    >
                      补 {item.interval}
                    </Button>
                  ) : null}
                </article>
              ))}
            </div>
          </div>
          <div className="data-next-step-side">
            <div className="data-next-step-side-card">
              <span>最短路径</span>
              <strong>
                {checkedSymbolLaunchHref
                  ? "当前可以直接进入回测"
                  : intervalRecommendations[0]
                    ? `先补 ${intervalRecommendations[0].interval}`
                    : "先检查一个标的"}
              </strong>
              <p>
                {checkedSymbolLaunchHref
                  ? "已经具备主流程所需覆盖，下一步应先创建回测，而不是继续停留在覆盖明细页。"
                  : intervalRecommendations[0]
                    ? intervalRecommendations[0].description
                    : "输入目标标的后，系统会直接给出最先该补的周期。"}
              </p>
            </div>
            <div className="data-next-step-side-card">
              <span>何时看高级明细</span>
              <strong>只有筛选多个标的或排查异常时再看</strong>
              <p>如果你当前只是想把一个标的跑起来，上面的状态卡和推荐动作通常已经足够，不需要先读完整覆盖表。</p>
            </div>
          </div>
        </div>
      </Card>

      <Card size="small" title="推荐研究样本" className="section-card">
        {beginnerPresets.length === 0 ? (
          <Typography.Text type="secondary">当前尚无可直接使用的推荐样本。可先在上方检查目标标的，并补齐 1d 或 15m。</Typography.Text>
        ) : (
          <div className="beginner-preset-grid">
            {beginnerPresets.map((preset) => (
              <article key={`${preset.symbol}-${preset.interval}`} className="beginner-preset-card">
                <div className="beginner-preset-head">
                  <div>
                    <strong>{preset.symbol}</strong>
                    <span>{preset.name || "未命名标的"}</span>
                  </div>
                  <Tag color={preset.interval === "1d" ? "blue" : "cyan"}>{preset.interval}</Tag>
                </div>
                <p>{preset.reason}</p>
                <div className="beginner-preset-tags">
                  {preset.availableIntervals.map((item) => (
                    <Tag key={item}>{item}</Tag>
                  ))}
                </div>
                <div className="beginner-preset-actions">
                  <Button onClick={() => applyCheckedSymbol(preset.symbol)}>检查该标的</Button>
                  <Button type="primary">
                    <Link href={buildBacktestPresetHref(preset)}>直接创建回测</Link>
                  </Button>
                </div>
              </article>
            ))}
          </div>
        )}
      </Card>

      <Card size="small" title="如果你还没定标的，可先从这里开始" className="section-card">
        <div className="quality-hint-grid">
          {coverageInsights.map((item) => (
            <article key={item.key} className="quality-hint-card">
              <strong>{item.value}</strong>
              <b>{item.title}</b>
              <span>{item.description}</span>
              <small>{item.recommendation}</small>
              <div className="quality-hint-examples">
                {item.examples.length > 0 ? (
                  item.examples.map((profile) => (
                    <Button key={`${item.key}-${profile.symbol}`} size="small" onClick={() => applyCheckedSymbol(profile.symbol)}>
                      先检查 {profile.symbol}
                    </Button>
                  ))
                ) : (
                  <Typography.Text type="secondary">当前还没有这一类标的。</Typography.Text>
                )}
              </div>
            </article>
          ))}
        </div>
        <Typography.Paragraph className="quality-hint-note">
          无需先将全部标的同步完毕。优先选择同时具备 1d 和 15m 的标的建立研究样本，待主流程验证完成后，再逐步扩展更多周期与更多标的。只有需要核对全部覆盖细节时，再展开下方高级明细。
        </Typography.Paragraph>
      </Card>

      {symbolRows.length > 0 ? (
        <Card size="small" title="当前标的覆盖明细" className="section-card">
          <div className="coverage-card-grid">
            {symbolRows.map((item) => (
              <div key={`${item.symbol}-${item.interval}`} className="coverage-card">
                <Tag color={item.interval === "1d" ? "blue" : "cyan"}>{item.interval}</Tag>
                <strong>{item.bar_count.toLocaleString()} 条 K 线</strong>
                <span>{item.start_time} 至 {item.end_time}</span>
              </div>
            ))}
          </div>
        </Card>
      ) : null}

      <div className="summary-grid">
        <MetricCard label="可回测标的" value={stats.instrument_count} note="当前仍以 Yahoo 覆盖为主" />
        <MetricCard label="回测 K 线" value={stats.total_bars.toLocaleString()} note="当前主流程直接读取的行情表" />
        <MetricCard label="统一 K 线" value={unifiedBarsCount.toLocaleString()} note={`${activeProviderCount}/${providerPanels.length} 个渠道已产生数据痕迹`} />
        <MetricCard label="公司行动事件" value={corporateActionCount.toLocaleString()} note="Tushare 实施事件总量" />
        <MetricCard label="前复权区间" value={adjustmentSegmentCount.toLocaleString()} note="通达信前复权公式区间" />
        {stats.by_interval.map((item) => (
          <MetricCard key={item.interval} label={`${item.interval} 覆盖`} value={item.bar_count.toLocaleString()} note="当前可直接回测的样本周期" />
        ))}
      </div>

      <Card size="small" title="回测样本覆盖高级明细" className="section-card">
        <div className="data-library-banner">
          <strong>这里只有现有回测主流程直接使用的覆盖明细</strong>
          <p>上方多渠道任务面板负责 Yahoo、A 股统一补数链路、TDX、Tushare 和前复权任务状态；这里继续保留面向回测样本的完整覆盖表，适合筛选可直接跑策略的标的。</p>
        </div>
        <div className="data-maintenance-banner">
          <div>
            <strong>高级补数：这里只处理当前回测样本的 Yahoo 全量同步</strong>
            <p>如果当前只需建立单标的研究样本，通常无需执行这里的操作。A 股统一补数链路、原始 all/1d/1m/5m、公司行动和前复权批量任务请使用上方 provider 卡片。</p>
          </div>
          <Space wrap>
            <Select value={syncInterval} options={intervalOptions} onChange={setSyncInterval} style={{ width: 120 }} />
            <Button loading={syncing} onClick={() => void syncAll()}>
              同步全部标的当前周期
            </Button>
          </Space>
        </div>
        <Collapse
          className="advanced-table-panel"
          ghost
          items={[
            {
              key: "coverage-table",
              label: "高级明细：当前回测样本覆盖、筛选与更新时间",
              children: (
                <>
                  <div className="table-toolbar">
                    <Space wrap>
                      <Input
                        placeholder="筛选标的或名称"
                        value={tableKeyword}
                        onChange={(event) => setTableKeyword(event.target.value)}
                        style={{ width: 240 }}
                      />
                      <Select
                        allowClear
                        placeholder="按周期筛选"
                        value={interval}
                        onChange={setInterval}
                        options={intervalOptions}
                        style={{ width: 150 }}
                      />
                    </Space>
                    <ToolbarCount>共 {filteredRows.length} 条覆盖记录</ToolbarCount>
                  </div>

                  {filteredRows.length === 0 ? (
                    <Empty description="没有匹配的数据" />
                  ) : (
                    <>
                      <div className="coverage-mobile-list">
                        {filteredRows.slice(0, 20).map((row) => (
                          <article key={`${row.symbol}-${row.interval}`} className="coverage-mobile-card">
                            <div className="coverage-mobile-card-head">
                              <div>
                                <strong>{row.symbol}</strong>
                                <span>{row.name || "未命名标的"} / {row.exchange}</span>
                              </div>
                              <Tag color={row.interval === "1d" ? "blue" : "cyan"}>{row.interval}</Tag>
                            </div>
                            <div className="coverage-mobile-metrics">
                              <span>{row.bar_count.toLocaleString()} 条 K 线</span>
                              <span>{row.start_time} 至 {row.end_time}</span>
                            </div>
                            <small>最近更新：{row.last_ingested_at || "-"}</small>
                          </article>
                        ))}
                        {filteredRows.length > 20 ? <Typography.Text type="secondary">移动端先显示前 20 条，可用筛选缩小范围。</Typography.Text> : null}
                      </div>
                      <Table<MarketCoverage>
                        className="coverage-desktop-table"
                        rowKey={(row) => `${row.symbol}-${row.interval}`}
                        size="small"
                        dataSource={filteredRows}
                        pagination={{ pageSize: 20, showSizeChanger: false }}
                        scroll={{ x: 1160 }}
                        columns={[
                          { title: "标的", dataIndex: "symbol", width: 120, fixed: "left" },
                          { title: "名称", dataIndex: "name", ellipsis: true },
                          { title: "交易所", dataIndex: "exchange", width: 90 },
                          { title: "周期", dataIndex: "interval", width: 90 },
                          { title: "K 线数量", dataIndex: "bar_count", width: 120, render: (value: number) => value.toLocaleString() },
                          { title: "开始日期", dataIndex: "start_time", width: 180 },
                          { title: "结束日期", dataIndex: "end_time", width: 180 },
                          { title: "最近更新", dataIndex: "last_ingested_at", width: 220 },
                        ]}
                      />
                    </>
                  )}
                </>
              ),
            },
          ]}
        />
      </Card>
    </div>
  );
}
