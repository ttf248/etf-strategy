"use client";

import { useSearchParams } from "next/navigation";
import { Button, Card, Collapse, Empty, Form, Input, InputNumber, message, Progress, Select, Space, Steps, Table, Tag, Typography } from "antd";
import { useEffect, useMemo, useRef, useState, type Key } from "react";
import Link from "next/link";
import { apiFetch, apiFetchSafe, type BacktestJob, type MarketDataStats, type StrategyTemplate } from "@/lib/api";
import { intervalOptions, strategyLabel, strategyOptions } from "@/lib/strategy-template-config";
import { InlineErrorBanner, PageHeader, StatusTag, ToolbarCount } from "@/components/platform-ui";
import { buildBeginnerPresets } from "@/lib/beginner-presets";

const strategyGuide: Record<string, { scene: string; beginnerHint: string; risk: string }> = {
  grid: { scene: "震荡区间内分层低买高卖", beginnerHint: "常用基线策略", risk: "单边下跌阶段回撤可能扩大" },
  dca: { scene: "长期分批建仓", beginnerHint: "适合日线基线研究", risk: "短期收益未必优于买入持有" },
  ma_cross: { scene: "跟随中期趋势做顺势进出", beginnerHint: "适合建立趋势策略基线", risk: "横盘震荡阶段可能频繁来回止损" },
  macd_trend: { scene: "用 MACD 金叉和柱体转强跟随动量", beginnerHint: "适合建立动量型趋势基线", risk: "趋势转弱时也可能出现连续假信号" },
  donchian_breakout: { scene: "向上突破历史高点后顺势跟随", beginnerHint: "适合建立突破型趋势基线", risk: "假突破和震荡回撤会更频繁" },
  volume_breakout: { scene: "突破高点并要求量能同步放大", beginnerHint: "适合建立更偏交易员语境的突破基线", risk: "缩量假突破减少了，但进场次数通常也会更少" },
  bollinger_reversion: { scene: "围绕布林带下轨做均值回归", beginnerHint: "适合建立震荡环境基线", risk: "单边下跌时容易抄底过早" },
  daily_rebound: { scene: "日线超跌反弹", beginnerHint: "适合验证阶段性反转", risk: "需重点关注止损与持仓时长" },
  minute_rebound: { scene: "分钟级急跌反抽", beginnerHint: "适合分钟级短线研究", risk: "对手续费与滑点更敏感" },
  minute_rebound_with_fade_filter: { scene: "带过滤条件的分钟反抽", beginnerHint: "适合进阶筛选研究", risk: "参数维度更多，配置复杂度更高" },
  minute_index_grid_retrace: { scene: "指数回落后的网格承接", beginnerHint: "适合专项指数研究", risk: "依赖指数与标的数据匹配" },
};

function executionProfileLabel(profile: string): string {
  if (profile === "realistic") {
    return "真实成交口径";
  }
  if (profile === "research") {
    return "理想成交口径";
  }
  return profile;
}

function buildTemplatePickHint(template: StrategyTemplate | null, strategyKind: string, interval: string) {
  if (!template) {
    return {
      title: "当前组合尚无可直接使用的模板",
      description: `当前选择为 ${strategyLabel(strategyKind)} / ${interval}。若该组合没有启用模板，建议优先调整周期，或先到策略模板页启用标准模板。`,
    };
  }
  return {
    title: `推荐使用 ${template.template_name}`,
    description:
      template.description?.trim() ||
      `${strategyLabel(strategyKind)} / ${interval} 已有可用模板。建议先直接采用该配置形成结果，再决定是否展开高级参数调整。`,
  };
}

type GuideCard = {
  title: string;
  value: string;
  description: string;
};

function buildTemplateChoiceGuides(params: {
  selectedStrategy: string;
  selectedInterval: string;
  selectedTemplate: StrategyTemplate | null;
  recommendedTemplate: StrategyTemplate | null;
}): GuideCard[] {
  const { selectedStrategy, selectedInterval, selectedTemplate, recommendedTemplate } = params;
  const strategyMeta = strategyGuide[selectedStrategy] ?? {
    scene: "策略实验",
    beginnerHint: "按模板说明选择",
    risk: "先小样本验证",
  };
  const activeTemplate = selectedTemplate ?? recommendedTemplate;
  if (!activeTemplate) {
    return [
      {
        title: "当前状态",
        value: "暂无可用模板",
        description: `${strategyLabel(selectedStrategy)} / ${selectedInterval} 当前没有启用模板，建议先切换周期，或去模板页启用一套标准模板。`,
      },
      {
        title: "推荐动作",
        value: "先保证能跑通",
        description: "起步阶段不需要先追求最优参数，先拿到一份能正常生成结果的基线报告更重要。",
      },
      {
        title: "风险提醒",
        value: strategyMeta.risk,
        description: "即使后续补齐模板，也建议先用小样本验证，再决定是否扩大参数搜索范围。",
      },
    ];
  }
  return [
    {
      title: "当前推荐",
      value: activeTemplate.template_name,
      description:
        selectedTemplate?.id === activeTemplate.id
          ? "你当前已经选中这套模板。只要它和你的交易假设不冲突，通常不需要继续手动筛选。"
          : "系统会优先推荐这套模板作为基线配置。若你不手动改，下一步会按这套模板进入提交确认。",
    },
    {
      title: "适合场景",
      value: strategyMeta.beginnerHint,
      description: `${strategyMeta.scene}。这一步的目标不是找最复杂的策略，而是先确认这类交易逻辑在当前标的和周期上能否成立。`,
    },
    {
      title: "成本与范围",
      value: `${executionProfileLabel(activeTemplate.execution_profile)} / ${activeTemplate.jobs} 组参数`,
      description: "模板会预先带入成交口径和参数搜索范围。只有当费用、仓位或验证方式明显不匹配时，再去改高级参数。",
    },
  ];
}

function buildSubmissionGuides(params: {
  symbol: string;
  selectedInterval: string;
  selectedStrategy: string;
  selectedTemplate: StrategyTemplate | null;
  selectedExecutionProfile: string;
  selectedJobs: number;
  selectedValidationRatio?: number;
  selectedMarketDataProvider?: string;
  selectedMarketDataAdjustmentKind?: string;
}): GuideCard[] {
  const {
    symbol,
    selectedInterval,
    selectedStrategy,
    selectedTemplate,
    selectedExecutionProfile,
    selectedJobs,
    selectedValidationRatio,
    selectedMarketDataProvider,
    selectedMarketDataAdjustmentKind,
  } = params;
  const marketDataSourceLabel = !selectedMarketDataProvider
    ? "自动选择（优先旧 Yahoo 回测表，再回退统一序列）"
    : selectedMarketDataAdjustmentKind
      ? `${selectedMarketDataProvider} / ${selectedMarketDataAdjustmentKind}`
      : selectedMarketDataProvider;
  return [
    {
      title: "这次会提交什么",
      value: `${symbol || "-"} / ${selectedInterval} / ${strategyLabel(selectedStrategy)}`,
      description: `本次会按 ${selectedTemplate?.template_name ?? "未选模板"} 发起任务，读取来源为 ${marketDataSourceLabel}。提交成功后，系统会保留这次配置快照，方便后续直接重跑。`,
    },
    {
      title: "系统会怎么跑",
      value: `${executionProfileLabel(selectedExecutionProfile)} / 同时尝试 ${selectedJobs} 组参数`,
      description:
        selectedValidationRatio && Number.isFinite(selectedValidationRatio)
          ? `当前会把最后 ${(selectedValidationRatio * 100).toFixed(0)}% 的样本留作验证区间。平台会按 worker 并发上限与 CPU 预算自动收口，不会无限占满资源。`
          : "平台会按当前 worker 并发上限与 CPU 预算自动收口，不会无限占满资源。",
    },
    {
      title: "提交后先看什么",
      value: "阶段、ETA 和资源摘要",
      description: "提交后无需反复刷新多个页面。下方最近任务会自动更新当前阶段、预计剩余时间和资源占用摘要。",
    },
  ];
}

function marketDataProviderLabel(provider: string | undefined): string {
  if (!provider) {
    return "自动选择";
  }
  if (provider === "yahoo") {
    return "Yahoo";
  }
  if (provider === "tdx") {
    return "通达信原始";
  }
  if (provider === "tdx_qfq") {
    return "通达信前复权";
  }
  return provider;
}

function marketDataAdjustmentLabel(adjustmentKind: string | undefined): string {
  if (!adjustmentKind) {
    return "自动判断";
  }
  if (adjustmentKind === "raw") {
    return "raw 原始";
  }
  if (adjustmentKind === "qfq") {
    return "qfq 前复权";
  }
  return adjustmentKind;
}

function buildTemplateFieldValues(template: StrategyTemplate) {
  const execution = template.execution_overrides_json ?? {};
  return {
    template_id: template.id,
    strategy_kind: template.strategy_kind,
    interval: template.interval,
    execution_profile: template.execution_profile,
    validation_start: template.validation_start || undefined,
    lookback_days: template.lookback_days ?? undefined,
    validation_ratio: template.validation_ratio ?? undefined,
    jobs: template.jobs,
    commission_bps: execution.commission_bps,
    slippage_bps: execution.slippage_bps,
    max_position_ratio: execution.max_position_ratio,
    stop_loss_pct: execution.stop_loss_pct,
    cooldown_bars: execution.cooldown_bars,
    benchmark: execution.benchmark,
    left_side_policy: execution.left_side_policy,
    force_exit_loss_pct: execution.force_exit_loss_pct,
  };
}

function buildJobReadingHint(job: BacktestJob) {
  const stageLabel = job.runtime_details.stage_label;
  if (job.status === "succeeded") {
    return job.reports?.length ? "本次任务已生成报告，建议直接进入结果页复盘收益、回撤与交易记录。" : "本次任务已执行完成；若结果尚未出现，请到结果库刷新确认。";
  }
  if (job.status === "failed") {
    return "本次任务执行失败，建议先查看错误信息；常见原因包括数据覆盖不足、模板不匹配或参数与标的不适配。";
  }
  if (job.status === "queued") {
    const queuePosition = job.runtime_details.queue_position;
    return queuePosition && queuePosition > 1
      ? `任务仍在排队，前面还有 ${queuePosition - 1} 个任务等待执行。通常无需重复提交。`
      : "任务仍在排队，通常无需重复提交；待进入执行阶段后，再判断是否需要取消。";
  }
  if (job.status === "running") {
    return stageLabel
      ? `任务仍在执行中，当前阶段为“${stageLabel}”。若长时间无进展，再进入系统状态页排查。`
      : "任务仍在执行中，建议等待结果输出；若长时间无进展，再进入系统状态页排查。";
  }
  if (job.status === "cancelled" || job.status === "cancel_requested") {
    return "任务已取消；若仍需继续验证，可直接按原配置重新提交。";
  }
  return "建议先确认当前状态与错误信息，再决定是重跑、取消，还是进入结果库继续复盘。";
}

function formatDuration(seconds: number | null | undefined) {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds)) {
    return "暂无法估计";
  }
  if (seconds < 60) {
    return `${Math.max(0, Math.round(seconds))} 秒`;
  }
  const minutes = Math.floor(seconds / 60);
  const remainSeconds = Math.max(0, Math.round(seconds % 60));
  if (minutes < 60) {
    return remainSeconds > 0 ? `${minutes} 分 ${remainSeconds} 秒` : `${minutes} 分`;
  }
  const hours = Math.floor(minutes / 60);
  const remainMinutes = minutes % 60;
  return remainMinutes > 0 ? `${hours} 小时 ${remainMinutes} 分` : `${hours} 小时`;
}

function buildJobRuntimeSummary(job: BacktestJob) {
  const runtime = job.runtime_details;
  if (job.status === "queued") {
    return {
      title: runtime.queue_position && runtime.queue_position > 1 ? `队列第 ${runtime.queue_position} 位` : "等待进入执行",
      description: runtime.stage_message ?? "任务已入队，等待 worker 领取。",
    };
  }
  if (job.status === "running") {
    const etaText = formatDuration(runtime.eta_seconds);
    const elapsedText = formatDuration(runtime.elapsed_seconds);
    return {
      title: runtime.stage_label ? `当前阶段：${runtime.stage_label}` : "正在执行",
      description: `已运行 ${elapsedText}，预计还需 ${etaText}。${runtime.stage_message ?? ""}`.trim(),
    };
  }
  if (job.status === "succeeded") {
    return {
      title: "结果已生成",
      description: runtime.elapsed_seconds ? `本次回测共耗时 ${formatDuration(runtime.elapsed_seconds)}。` : "回测已经完成，可直接进入结果页复盘。",
    };
  }
  if (job.status === "failed") {
    return {
      title: "执行失败",
      description: runtime.elapsed_seconds ? `本次任务在 ${formatDuration(runtime.elapsed_seconds)} 后失败。` : "任务未顺利完成，请先查看错误信息。",
    };
  }
  if (job.status === "cancel_requested") {
    return {
      title: "等待取消落地",
      description: runtime.stage_message ?? "系统会在安全检查点尽快停止当前任务。",
    };
  }
  return {
    title: runtime.stage_label ?? "任务已结束",
    description: runtime.stage_message ?? "请根据当前状态决定是否继续处理。",
  };
}

function backtestStatusLabel(status: string) {
  if (status === "succeeded") {
    return "已生成结果";
  }
  if (status === "failed") {
    return "执行失败";
  }
  if (status === "queued") {
    return "等待执行";
  }
  if (status === "running") {
    return "执行中";
  }
  if (status === "cancel_requested") {
    return "取消中";
  }
  if (status === "cancelled") {
    return "已取消";
  }
  return status || "-";
}

function buildJobPrimaryAction(job: BacktestJob) {
  const reportId = job.reports?.[0]?.id;
  if (reportId) {
    return {
      disabled: false,
      href: `/reports/${reportId}`,
      label: "查看结果",
    };
  }
  if (job.status === "succeeded") {
    return {
      disabled: false,
      href: "/reports",
      label: "进入结果库",
    };
  }
  if (job.status === "failed") {
    return {
      disabled: true,
      href: null,
      label: "未生成结果",
    };
  }
  if (job.status === "cancelled" || job.status === "cancel_requested") {
    return {
      disabled: true,
      href: null,
      label: "任务已取消",
    };
  }
  return {
    disabled: true,
    href: null,
    label: "等待结果生成",
  };
}

function pickFocusJob(jobs: BacktestJob[]): BacktestJob | null {
  const orderedJobs = [...jobs].sort((left, right) => right.id - left.id);
  return (
    orderedJobs.find((item) => item.status === "running") ??
    orderedJobs.find((item) => item.status === "queued") ??
    orderedJobs.find((item) => item.status === "cancel_requested") ??
    orderedJobs.find((item) => item.status === "failed") ??
    orderedJobs.find((item) => item.status === "succeeded" && (item.reports?.length ?? 0) > 0) ??
    orderedJobs[0] ??
    null
  );
}

function buildFocusJobReason(job: BacktestJob): string {
  if (job.status === "running") {
    return "这是当前最需要盯的一条任务，因为它正在消耗执行资源，且阶段、ETA 和资源摘要都会持续变化。";
  }
  if (job.status === "queued") {
    return "这是当前最需要盯的一条任务，因为它决定你接下来什么时候能看到新的结果，通常不需要再重复提交。";
  }
  if (job.status === "failed") {
    return "这是当前最需要处理的一条任务，因为它直接阻断了结果生成，应先确认失败原因是否需要重跑或改配置。";
  }
  if (job.status === "succeeded") {
    return "这是当前最值得继续推进的一条任务，因为它已经产出结果，下一步应直接进入结果页判断策略是否有效。";
  }
  return "这是当前最值得优先确认的一条任务。先处理完这条，再决定是否展开完整任务历史。";
}

function buildFocusJobGuides(job: BacktestJob): GuideCard[] {
  const runtime = buildJobRuntimeSummary(job);
  const payload = job.request_payload;
  const templateName = (payload.template_snapshot as { template_name?: string } | undefined)?.template_name;
  const requestedParallelism = job.runtime_details.requested_parallelism;
  const effectiveParallelism = job.runtime_details.effective_parallelism;
  const workerConcurrency = job.runtime_details.worker_concurrency;
  const maxOptimizationWorkers = job.runtime_details.max_optimization_workers;

  let timeValue = "等待更新";
  const timeDescription = runtime.description;
  if (job.status === "running") {
    timeValue = `已运行 ${formatDuration(job.runtime_details.elapsed_seconds)} / 预计还需 ${formatDuration(job.runtime_details.eta_seconds)}`;
  } else if (job.status === "queued") {
    timeValue = job.runtime_details.queue_position ? `队列第 ${job.runtime_details.queue_position} 位` : "等待 worker 领取";
  } else if (job.status === "failed" || job.status === "succeeded") {
    timeValue = job.runtime_details.elapsed_seconds ? `总耗时 ${formatDuration(job.runtime_details.elapsed_seconds)}` : "已结束";
  }

  const resourceParts: string[] = [];
  if (job.runtime_details.worker_name) {
    resourceParts.push(`执行槽位 ${job.runtime_details.worker_name}`);
  }
  if (typeof requestedParallelism === "number" && Number.isFinite(requestedParallelism)) {
    resourceParts.push(`请求并发 ${requestedParallelism}`);
  }
  if (typeof effectiveParallelism === "number" && Number.isFinite(effectiveParallelism)) {
    resourceParts.push(`实际并发 ${effectiveParallelism}`);
  }
  if (typeof workerConcurrency === "number" && Number.isFinite(workerConcurrency)) {
    resourceParts.push(`worker 上限 ${workerConcurrency}`);
  }
  if (typeof maxOptimizationWorkers === "number" && Number.isFinite(maxOptimizationWorkers)) {
    resourceParts.push(`单任务上限 ${maxOptimizationWorkers}`);
  }

  const nextAction = buildJobPrimaryAction(job);
  let nextActionDescription = buildJobReadingHint(job);
  if (job.status === "running" || job.status === "queued") {
    nextActionDescription = "当前更应等待阶段推进或结果生成，而不是重复提交相同配置。只有长时间无进展时，再取消或排障。";
  } else if (job.status === "succeeded" && nextAction.href) {
    nextActionDescription = "结果已经可读，下一步应直接进入结果页先判断收益、回撤和是否跑赢买入持有。";
  } else if (job.status === "failed") {
    nextActionDescription = "先根据错误信息判断是数据覆盖不足、模板不匹配，还是参数不适配，再决定按原配置重跑还是回到配置页调整。";
  }

  return [
    {
      title: "当前阶段",
      value: runtime.title,
      description: runtime.description,
    },
    {
      title: "时间判断",
      value: timeValue,
      description: timeDescription,
    },
    {
      title: "资源安排",
      value: job.runtime_details.resource_summary ?? "按平台资源预算执行",
      description: resourceParts.length > 0 ? resourceParts.join("，") : "平台会按 worker 并发与单任务上限自动收口资源使用。",
    },
    {
      title: "下一步动作",
      value: nextAction.label,
      description:
        templateName && job.status !== "failed"
          ? `${templateName}。${nextActionDescription}`
          : nextActionDescription,
    },
  ];
}

export function BacktestsView() {
  const [form] = Form.useForm();
  const [jobs, setJobs] = useState<BacktestJob[]>([]);
  const [stats, setStats] = useState<MarketDataStats | null>(null);
  const [templates, setTemplates] = useState<StrategyTemplate[]>([]);
  const [selectedJobIds, setSelectedJobIds] = useState<Key[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [activeStep, setActiveStep] = useState(0);
  const [loadWarning, setLoadWarning] = useState<string | null>(null);
  const [messageApi, contextHolder] = message.useMessage();
  const searchParams = useSearchParams();
  const basePresetAppliedRef = useRef(false);
  const templatePresetAppliedRef = useRef(false);
  const selectedStrategy = Form.useWatch("strategy_kind", form) ?? "grid";
  const selectedInterval = Form.useWatch("interval", form) ?? "15m";
  const selectedSymbol = Form.useWatch("symbol", form) ?? "";
  const selectedTemplateId = Form.useWatch("template_id", form) as number | undefined;
  const selectedExecutionProfile = Form.useWatch("execution_profile", form) ?? "realistic";
  const selectedMarketDataProvider = Form.useWatch("market_data_provider", form) as string | undefined;
  const selectedMarketDataAdjustmentKind = Form.useWatch("market_data_adjustment_kind", form) as string | undefined;
  const selectedJobsValue = Form.useWatch("jobs", form);
  const selectedValidationRatioValue = Form.useWatch("validation_ratio", form);

  const filteredTemplates = useMemo(
    () => templates.filter((item) => item.is_active && item.strategy_kind === selectedStrategy && item.interval === selectedInterval),
    [selectedInterval, selectedStrategy, templates],
  );
  const selectedTemplate = filteredTemplates.find((item) => item.id === selectedTemplateId) ?? null;
  const recommendedTemplate = filteredTemplates.find((item) => item.is_default) ?? filteredTemplates[0] ?? null;
  const beginnerPresets = useMemo(() => (stats ? buildBeginnerPresets(stats.coverages) : []), [stats]);
  const runningJobs = useMemo(() => jobs.filter((item) => item.status === "running"), [jobs]);
  const queuedJobs = useMemo(() => jobs.filter((item) => item.status === "queued"), [jobs]);
  const failedJobs = useMemo(() => jobs.filter((item) => item.status === "failed"), [jobs]);
  const succeededJobs = useMemo(() => jobs.filter((item) => item.status === "succeeded"), [jobs]);
  const recentJobs = useMemo(() => jobs.slice(0, 6), [jobs]);
  const latestSucceededJob = useMemo(() => succeededJobs.find((item) => item.reports?.length), [succeededJobs]);
  const focusJob = useMemo(() => pickFocusJob(jobs), [jobs]);
  const templatePickHint = useMemo(
    () => buildTemplatePickHint(recommendedTemplate, selectedStrategy, selectedInterval),
    [recommendedTemplate, selectedInterval, selectedStrategy],
  );
  const templateChoiceGuides = useMemo(
    () =>
      buildTemplateChoiceGuides({
        selectedStrategy,
        selectedInterval,
        selectedTemplate,
        recommendedTemplate,
      }),
    [recommendedTemplate, selectedInterval, selectedStrategy, selectedTemplate],
  );
  const selectedJobs = useMemo(() => {
    const numeric = Number(selectedJobsValue ?? selectedTemplate?.jobs ?? recommendedTemplate?.jobs ?? 1);
    return Number.isFinite(numeric) && numeric > 0 ? numeric : 1;
  }, [recommendedTemplate?.jobs, selectedJobsValue, selectedTemplate?.jobs]);
  const selectedValidationRatio = useMemo(() => {
    const numeric = Number(selectedValidationRatioValue ?? selectedTemplate?.validation_ratio ?? recommendedTemplate?.validation_ratio ?? NaN);
    return Number.isFinite(numeric) ? numeric : undefined;
  }, [
    recommendedTemplate?.validation_ratio,
    selectedTemplate?.validation_ratio,
    selectedValidationRatioValue,
  ]);
  const submissionGuides = useMemo(
    () =>
      buildSubmissionGuides({
        symbol: String(selectedSymbol ?? ""),
        selectedInterval,
        selectedStrategy,
        selectedTemplate,
        selectedExecutionProfile,
        selectedJobs,
        selectedValidationRatio,
        selectedMarketDataProvider,
        selectedMarketDataAdjustmentKind,
      }),
    [
      selectedExecutionProfile,
      selectedInterval,
      selectedJobs,
      selectedMarketDataAdjustmentKind,
      selectedMarketDataProvider,
      selectedStrategy,
      selectedSymbol,
      selectedTemplate,
      selectedValidationRatio,
    ],
  );
  const marketDataProviderOptions = useMemo(
    () => [
      { label: "自动选择", value: "__auto__" },
      { label: "Yahoo", value: "yahoo" },
      { label: "通达信原始", value: "tdx" },
      { label: "通达信前复权", value: "tdx_qfq" },
    ],
    [],
  );
  const marketDataAdjustmentOptions = useMemo(
    () => [
      { label: "自动判断", value: "__auto__" },
      { label: "raw 原始", value: "raw" },
      { label: "qfq 前复权", value: "qfq" },
    ],
    [],
  );
  const queryPreset = useMemo(() => {
    const symbol = searchParams.get("symbol")?.trim().toUpperCase();
    const interval = searchParams.get("interval");
    const strategyKind = searchParams.get("strategy_kind");
    const templateIdRaw = searchParams.get("template_id");
    const marketDataProvider = searchParams.get("market_data_provider")?.trim().toLowerCase() || undefined;
    const marketDataAdjustmentKind = searchParams.get("market_data_adjustment_kind")?.trim().toLowerCase() || undefined;
    const templateId = templateIdRaw ? Number(templateIdRaw) : undefined;
    const validIntervals = new Set(intervalOptions.map((item) => item.value));
    const validStrategies = new Set(strategyOptions.map((item) => item.value));
    if (!symbol && !interval && !strategyKind && templateId === undefined && !marketDataProvider && !marketDataAdjustmentKind) {
      return null;
    }
    return {
      symbol: symbol || undefined,
      interval: interval && validIntervals.has(interval) ? interval : undefined,
      strategy_kind: strategyKind && validStrategies.has(strategyKind) ? strategyKind : undefined,
      template_id: templateId !== undefined && Number.isFinite(templateId) ? templateId : undefined,
      market_data_provider: marketDataProvider,
      market_data_adjustment_kind: marketDataAdjustmentKind,
    };
  }, [searchParams]);

  async function loadJobs() {
    const payload = await apiFetch<BacktestJob[]>("/api/backtests?limit=100");
    setJobs(payload);
  }

  async function loadInitialSnapshot() {
    const [jobsResult, templatesResult, statsResult] = await Promise.all([
      apiFetchSafe<BacktestJob[]>("/api/backtests?limit=100"),
      apiFetchSafe<StrategyTemplate[]>("/api/templates?active_only=true"),
      apiFetchSafe<MarketDataStats>("/api/market-data/stats"),
    ]);
    const issues: string[] = [];

    if (jobsResult.ok) {
      setJobs(jobsResult.data);
    } else {
      issues.push(`最近任务读取失败：${jobsResult.error.message}`);
    }

    if (templatesResult.ok) {
      setTemplates(templatesResult.data);
    } else {
      issues.push(`模板列表读取失败：${templatesResult.error.message}`);
    }

    if (statsResult.ok) {
      setStats(statsResult.data);
    } else {
      issues.push(`研究样本读取失败：${statsResult.error.message}`);
    }

    setLoadWarning(issues.length > 0 ? issues.join("；") : null);
  }

  useEffect(() => {
    queueMicrotask(() => {
      void loadInitialSnapshot();
    });
  }, []);

  useEffect(() => {
    const hasActiveJobs = jobs.some((item) => ["queued", "running", "cancel_requested"].includes(item.status));
    if (!hasActiveJobs) {
      return;
    }
    const timer = window.setInterval(() => {
      void loadJobs().catch(() => undefined);
    }, 3000);
    return () => window.clearInterval(timer);
  }, [jobs]);

  useEffect(() => {
    if (basePresetAppliedRef.current || !queryPreset) {
      return;
    }
    const nextValues: Record<string, unknown> = {};
    if (queryPreset.symbol) {
      nextValues.symbol = queryPreset.symbol;
    }
    if (queryPreset.interval) {
      nextValues.interval = queryPreset.interval;
    }
    if (queryPreset.strategy_kind) {
      nextValues.strategy_kind = queryPreset.strategy_kind;
    }
    if (queryPreset.template_id !== undefined) {
      nextValues.template_id = queryPreset.template_id;
    }
    if (queryPreset.market_data_provider) {
      nextValues.market_data_provider = queryPreset.market_data_provider;
    }
    if (queryPreset.market_data_adjustment_kind) {
      nextValues.market_data_adjustment_kind = queryPreset.market_data_adjustment_kind;
    }
    form.setFieldsValue(nextValues);
    basePresetAppliedRef.current = true;
  }, [form, queryPreset]);

  useEffect(() => {
    if (!queryPreset?.template_id || templatePresetAppliedRef.current || templates.length === 0) {
      return;
    }
    const matchedTemplate = templates.find((item) => item.id === queryPreset.template_id) ?? null;
    if (matchedTemplate) {
      form.setFieldsValue(buildTemplateFieldValues(matchedTemplate));
    }
    templatePresetAppliedRef.current = true;
  }, [form, queryPreset, templates]);

  function applyTemplate(template: StrategyTemplate | null) {
    if (!template) {
      form.setFieldValue("template_id", undefined);
      return;
    }
    form.setFieldsValue(buildTemplateFieldValues(template));
  }

  async function goNextStep() {
    if (activeStep === 0) {
      await form.validateFields(["symbol", "interval"]);
    }
    if (activeStep === 1) {
      await form.validateFields(["strategy_kind"]);
      if (!form.getFieldValue("template_id") && recommendedTemplate) {
        applyTemplate(recommendedTemplate);
      }
    }
    setActiveStep((current) => Math.min(current + 1, 2));
  }

  async function onFinish() {
    setSubmitting(true);
    try {
      const submittedValues = form.getFieldsValue(true);
      const result = await apiFetch<{ job_id: number }>("/api/backtests", {
        method: "POST",
        body: JSON.stringify({
          ...submittedValues,
          parameter_space: selectedTemplate?.parameter_space_json,
        }),
      });
      messageApi.success(`任务已提交，编号 ${result.job_id}`);
      await loadJobs();
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "提交失败");
    } finally {
      setSubmitting(false);
    }
  }

  async function cancelJob(jobId: number) {
    try {
      await apiFetch(`/api/backtests/${jobId}/cancel`, { method: "POST" });
      messageApi.success(`已请求取消任务，编号 ${jobId}`);
      await loadJobs();
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "取消失败");
    }
  }

  async function retryJob(jobId: number) {
    try {
      await apiFetch(`/api/backtests/${jobId}/retry`, { method: "POST" });
      messageApi.success(`任务已重新安排，编号 ${jobId}`);
      await loadJobs();
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "重试失败");
    }
  }

  async function bulkCancelJobs() {
    try {
      await apiFetch("/api/backtests/bulk-cancel", {
        method: "POST",
        body: JSON.stringify({ job_ids: selectedJobIds.map(Number) }),
      });
      messageApi.success("已提交所选任务的取消请求");
      setSelectedJobIds([]);
      await loadJobs();
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "取消所选任务失败");
    }
  }

  async function bulkRetryJobs() {
    try {
      await apiFetch("/api/backtests/bulk-retry", {
        method: "POST",
        body: JSON.stringify({ job_ids: selectedJobIds.map(Number) }),
      });
      messageApi.success("已重新提交所选失败任务");
      setSelectedJobIds([]);
      await loadJobs();
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "重试所选任务失败");
    }
  }

  return (
    <div className="page-stack">
      {contextHolder}
      {loadWarning ? <InlineErrorBanner message={loadWarning} onRetry={() => void loadInitialSnapshot()} /> : null}
      <PageHeader
        eyebrow="回测配置"
        title="创建回测任务"
        description="按三步完成任务配置：定义标的与周期、选择策略模板、确认执行口径后提交。任务提交后会自动刷新进度、阶段和预计剩余时间。"
        actions={<Button onClick={() => void loadJobs()}>看一下最新进展</Button>}
      />

      <Card title="任务配置流程" size="small" className="section-card backtest-wizard-card">
        <Form
          form={form}
          layout="vertical"
          onFinish={onFinish}
          initialValues={{ interval: "15m", strategy_kind: "grid", execution_profile: "realistic", jobs: 1 }}
          onValuesChange={(changedValues) => {
            if ("strategy_kind" in changedValues || "interval" in changedValues) {
              const currentId = form.getFieldValue("template_id");
              const currentTemplate = templates.find((item) => item.id === currentId);
              if (currentTemplate && (currentTemplate.strategy_kind !== form.getFieldValue("strategy_kind") || currentTemplate.interval !== form.getFieldValue("interval"))) {
                form.setFieldValue("template_id", undefined);
              }
            }
            if ("market_data_provider" in changedValues) {
              const nextProvider = changedValues.market_data_provider;
              if (!nextProvider) {
                form.setFieldValue("market_data_adjustment_kind", undefined);
              } else if (nextProvider === "tdx_qfq") {
                form.setFieldValue("market_data_adjustment_kind", "qfq");
              } else if (nextProvider === "yahoo" || nextProvider === "tdx") {
                const currentAdjustmentKind = form.getFieldValue("market_data_adjustment_kind");
                if (!currentAdjustmentKind || currentAdjustmentKind === "qfq") {
                  form.setFieldValue("market_data_adjustment_kind", "raw");
                }
              }
            }
          }}
        >
          <div className="wizard-first-run-banner">
            <strong>标准研究起点</strong>
            <p>可直接使用现成样本，优先选择 15m 或 1d，策略使用网格或定投，模板保持推荐项。先形成一份可复盘的基线结果，再按结论扩展参数空间，通常比起步阶段就展开大规模调参更高效。</p>
            <div className="wizard-first-run-tags">
              <span>1. 选择标准样本</span>
              <span>2. 使用推荐模板</span>
              <span>3. 复盘最近结果</span>
            </div>
          </div>

          <Steps
            className="backtest-wizard-steps"
            current={activeStep}
            items={[
              { title: "标的与周期" },
              { title: "策略与模板" },
              { title: "确认提交" },
            ]}
          />

          {activeStep === 0 ? (
            <div className="wizard-step-panel">
              <Typography.Title level={4}>定义研究标的与数据周期</Typography.Title>
              <Typography.Paragraph>建议优先使用已具备覆盖的数据标的，例如 1810.HK。若暂无明确偏好，可先以 15m 作为分钟级基线周期。</Typography.Paragraph>
              {queryPreset ? (
                <div className="wizard-preset-banner">
                  <strong>已载入推荐研究样本</strong>
                  <span>
                    {[
                      queryPreset.symbol,
                      queryPreset.interval,
                      queryPreset.strategy_kind ? strategyLabel(queryPreset.strategy_kind) : undefined,
                      queryPreset.market_data_provider ? marketDataProviderLabel(queryPreset.market_data_provider) : undefined,
                      queryPreset.market_data_adjustment_kind ? marketDataAdjustmentLabel(queryPreset.market_data_adjustment_kind) : undefined,
                    ]
                      .filter(Boolean)
                      .join(" / ")}
                    ，确认无误后可直接进入下一步。
                  </span>
                </div>
              ) : null}
              <div className="template-form-grid">
                <Form.Item name="symbol" label="回测标的" rules={[{ required: true, message: "请输入回测标的" }]} extra="支持统一标的代码，例如 1810.HK、SH600000、10#AUDUSD。">
                  <Input placeholder="例如 1810.HK、SH600000、10#AUDUSD" />
                </Form.Item>
                <Form.Item name="interval" label="数据周期" extra="常用基线周期为 15m 或 1d。">
                  <Select options={intervalOptions} />
                </Form.Item>
                <Form.Item
                  name="market_data_provider"
                  label="行情来源"
                  extra="默认先用旧 Yahoo 回测表；若你想直接使用统一主干表里的 TDX 原始或前复权序列，可在这里显式指定。"
                >
                  <Select
                    allowClear
                    placeholder="默认自动选择"
                    options={marketDataProviderOptions}
                    onChange={(value) => form.setFieldValue("market_data_provider", value === "__auto__" ? undefined : value)}
                  />
                </Form.Item>
                <Form.Item
                  name="market_data_adjustment_kind"
                  label="复权口径"
                  extra="通常保留自动判断即可；若同一标的同周期同时存在 raw 和 qfq，再显式指定。"
                >
                  <Select
                    allowClear
                    placeholder="默认自动判断"
                    options={marketDataAdjustmentOptions}
                    onChange={(value) => form.setFieldValue("market_data_adjustment_kind", value === "__auto__" ? undefined : value)}
                  />
                </Form.Item>
              </div>
              {beginnerPresets.length > 0 ? (
                <div className="wizard-preset-section">
                  <Typography.Text strong>可直接使用的研究样本</Typography.Text>
                  <div className="beginner-preset-grid">
                    {beginnerPresets.map((preset) => (
                      <button
                        key={`${preset.symbol}-${preset.interval}`}
                        type="button"
                        className={`beginner-preset-card beginner-preset-button${form.getFieldValue("symbol") === preset.symbol && form.getFieldValue("interval") === preset.interval ? " is-active" : ""}`}
                        onClick={() => {
                          form.setFieldsValue({
                            symbol: preset.symbol,
                            interval: preset.interval,
                            strategy_kind: preset.strategyKind,
                            template_id: undefined,
                            market_data_provider: undefined,
                            market_data_adjustment_kind: undefined,
                          });
                        }}
                      >
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
                          <Tag color="gold">{strategyLabel(preset.strategyKind)}</Tag>
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              ) : null}
            </div>
          ) : null}

          {activeStep === 1 ? (
            <div className="wizard-step-panel">
              <Typography.Title level={4}>选择策略与模板</Typography.Title>
              <Typography.Paragraph>若暂无明确偏好，可先采用“网格”与推荐模板作为标准研究配置。模板已封装常用参数，待结果形成后再做针对性调整。</Typography.Paragraph>
              <div className="wizard-template-banner">
                <strong>{templatePickHint.title}</strong>
                <p>{templatePickHint.description}</p>
                <div className="wizard-template-guide-grid">
                  {templateChoiceGuides.map((item) => (
                    <article key={item.title} className="wizard-template-guide-card">
                      <span>{item.title}</span>
                      <strong>{item.value}</strong>
                      <p>{item.description}</p>
                    </article>
                  ))}
                </div>
              </div>
              <div className="strategy-choice-grid">
                {strategyOptions.map((item) => {
                  const guide = strategyGuide[item.value] ?? { scene: "策略实验", beginnerHint: "按模板说明选择", risk: "先小样本验证" };
                  const hasTemplate = templates.some(
                    (template) => template.is_active && template.strategy_kind === item.value && template.interval === selectedInterval,
                  );
                  const active = selectedStrategy === item.value;
                  return (
                    <button
                      key={item.value}
                      type="button"
                      className={`strategy-choice-card${active ? " is-active" : ""}`}
                      onClick={() => {
                        form.setFieldValue("strategy_kind", item.value);
                        form.setFieldValue("template_id", undefined);
                      }}
                    >
                      <strong>{item.label}</strong>
                      <span>{guide.scene}</span>
                      <small>{guide.beginnerHint}</small>
                      <span>主要风险：{guide.risk}</span>
                      <em>{hasTemplate ? "当前周期有可用模板" : "当前周期暂无模板，建议换周期"}</em>
                    </button>
                  );
                })}
              </div>
              <div className="template-form-grid">
                <Form.Item name="strategy_kind" label="策略类型" extra="也可以直接选择上方策略卡片。">
                  <Select options={strategyOptions} />
                </Form.Item>
                <Form.Item name="template_id" label="参数模板" extra="推荐优先使用标准默认模板。">
                  <Select
                    allowClear
                    placeholder="按当前策略/周期筛选"
                    options={filteredTemplates.map((item) => ({ label: `${item.template_name}${item.is_default ? " · 默认" : ""}`, value: item.id }))}
                    onChange={(value) => {
                      const template = filteredTemplates.find((item) => item.id === value) ?? null;
                      applyTemplate(template);
                    }}
                  />
                </Form.Item>
              </div>
              {recommendedTemplate ? (
                <div className="wizard-template-action-row">
                  <Typography.Text type="secondary">
                    若不准备手动筛选参数，下一步会自动带入推荐模板。
                  </Typography.Text>
                  <Button onClick={() => applyTemplate(recommendedTemplate)}>应用推荐模板：{recommendedTemplate.template_name}</Button>
                </div>
              ) : (
                <Typography.Text type="secondary">当前策略与周期暂无可用模板，建议调整周期或先到策略模板页启用模板。</Typography.Text>
              )}
            </div>
          ) : null}

          {activeStep === 2 ? (
            <div className="wizard-step-panel">
              <Typography.Title level={4}>确认执行配置并提交</Typography.Title>
              <Typography.Paragraph>确认标的、周期、策略与模板无误后即可提交。若无专项需求，高级参数可保持默认。</Typography.Paragraph>
              <div className="wizard-submit-summary-card">
                <div className="wizard-submit-main">
                  <strong>当前将按这套配置创建任务</strong>
                  <div className="detail-grid">
                    <div className="detail-item"><span className="detail-label">标的</span><span className="detail-value">{form.getFieldValue("symbol") || "-"}</span></div>
                    <div className="detail-item"><span className="detail-label">周期</span><span className="detail-value">{selectedInterval}</span></div>
                    <div className="detail-item"><span className="detail-label">策略</span><span className="detail-value">{strategyLabel(selectedStrategy)}</span></div>
                    <div className="detail-item"><span className="detail-label">模板</span><span className="detail-value">{selectedTemplate?.template_name ?? recommendedTemplate?.template_name ?? "未选择模板"}</span></div>
                    <div className="detail-item"><span className="detail-label">行情来源</span><span className="detail-value">{marketDataProviderLabel(selectedMarketDataProvider)}</span></div>
                    <div className="detail-item"><span className="detail-label">复权口径</span><span className="detail-value">{marketDataAdjustmentLabel(selectedMarketDataAdjustmentKind)}</span></div>
                  </div>
                  <div className="submit-reading-grid">
                    {submissionGuides.map((item) => (
                      <article key={item.title} className="submit-reading-card">
                        <span>{item.title}</span>
                        <strong>{item.value}</strong>
                        <p>{item.description}</p>
                      </article>
                    ))}
                  </div>
                </div>
                <div className="wizard-submit-side">
                  <div className="wizard-submit-side-card">
                    <span>默认建议</span>
                    <strong>先提交基线任务，不要急着展开高级参数</strong>
                    <p>如果当前模板、费用口径和仓位上限都没有明显问题，先让系统跑出一份结果，再根据收益、回撤和交易节奏做下一步调整。</p>
                  </div>
                  <div className="wizard-submit-side-card">
                    <span>提交后去哪里</span>
                    <strong>先盯最近任务，再去结果页</strong>
                    <p>任务开始后，下方会自动更新阶段、ETA 和资源摘要。任务完成并生成报告后，再进入结果页判断结论。</p>
                  </div>
                </div>
              </div>
              <Collapse
                className="advanced-collapse"
                items={[
                  {
                    key: "advanced",
                    label: "只有费用、仓位或验证口径不匹配时，再改高级参数",
                    children: (
                      <div className="template-form-grid">
                        <Form.Item name="execution_profile" label="成交假设">
                          <Select options={[{ label: "真实成交口径", value: "realistic" }, { label: "理想成交口径", value: "research" }]} />
                        </Form.Item>
                        <Form.Item name="lookback_days" label="先回看多少天历史">
                          <InputNumber min={1} style={{ width: "100%" }} />
                        </Form.Item>
                        <Form.Item name="validation_ratio" label="最后留多少比例做验证">
                          <InputNumber min={0.05} max={0.95} step={0.05} style={{ width: "100%" }} />
                        </Form.Item>
                        <Form.Item name="jobs" label="同时试几组参数" extra="平台会按当前 worker 并发上限和 CPU 预算自动收口，不会无限占满资源。">
                          <InputNumber min={1} max={16} style={{ width: "100%" }} />
                        </Form.Item>
                        <Form.Item name="commission_bps" label="手续费（万分比）">
                          <InputNumber min={0} step={0.5} style={{ width: "100%" }} />
                        </Form.Item>
                        <Form.Item name="slippage_bps" label="滑点（万分比）">
                          <InputNumber min={0} step={0.5} style={{ width: "100%" }} />
                        </Form.Item>
                        <Form.Item name="max_position_ratio" label="最大仓位">
                          <InputNumber min={0} max={1} step={0.05} style={{ width: "100%" }} />
                        </Form.Item>
                        <Form.Item name="left_side_policy" label="左侧行情时怎么处理">
                          <Select
                            allowClear
                            options={[
                              { label: "持有", value: "hold" },
                              { label: "强制离场", value: "force_exit" },
                              { label: "两种都保留", value: "both" },
                            ]}
                          />
                        </Form.Item>
                      </div>
                    ),
                  },
                ]}
              />
            </div>
          ) : null}

          <div className="form-action-row wizard-action-row">
            <Button disabled={activeStep === 0} onClick={() => setActiveStep((current) => Math.max(current - 1, 0))}>
              上一步
            </Button>
            {activeStep < 2 ? (
              <Button type="primary" onClick={() => void goNextStep()}>
                下一步
              </Button>
            ) : (
              <Button type="primary" htmlType="submit" loading={submitting}>
                开始回测
              </Button>
            )}
          </div>
        </Form>
      </Card>

      <Card
        title="最近回测任务"
        size="small"
        className="section-card"
      >
        {jobs.length === 0 ? (
          <Empty description="当前还没有回测任务。提交后，执行状态与结果入口会展示在这里。" />
        ) : (
          <>
            {focusJob ? (
              <div className="job-focus-card">
                <div className="job-focus-main">
                  <div className="job-focus-head">
                    <div>
                      <span className="job-focus-label">当前焦点任务</span>
                      <strong>
                        任务 #{focusJob.id} · {String(focusJob.request_payload.symbol ?? "-")} / {String(focusJob.request_payload.interval ?? "-")} / {strategyLabel(String(focusJob.request_payload.strategy_kind ?? "-"))}
                      </strong>
                    </div>
                    <StatusTag value={focusJob.status} label={backtestStatusLabel(focusJob.status)} />
                  </div>
                  <p className="job-focus-summary">{buildFocusJobReason(focusJob)}</p>
                  <div className="job-focus-progress">
                    <div className="job-focus-progress-head">
                      <strong>当前进度 {focusJob.progress_pct.toFixed(0)}%</strong>
                      <span>{focusJob.runtime_details.stage_label ?? "等待阶段更新"}</span>
                    </div>
                    <Progress
                      percent={Math.round(focusJob.progress_pct)}
                      status={focusJob.status === "failed" ? "exception" : focusJob.status === "succeeded" ? "success" : "active"}
                    />
                  </div>
                  <div className="job-focus-guide-grid">
                    {buildFocusJobGuides(focusJob).map((item) => (
                      <article key={item.title} className="job-focus-guide-card">
                        <span>{item.title}</span>
                        <strong>{item.value}</strong>
                        <p>{item.description}</p>
                      </article>
                    ))}
                  </div>
                </div>
                <div className="job-focus-side">
                  <div className="job-focus-side-card">
                    <span>为什么先看它</span>
                    <strong>{backtestStatusLabel(focusJob.status)}</strong>
                    <p>{buildJobReadingHint(focusJob)}</p>
                  </div>
                  {focusJob.error_message ? (
                    <div className="job-focus-side-card is-danger">
                      <span>失败或异常信息</span>
                      <strong>需要先处理</strong>
                      <p>{focusJob.error_message}</p>
                    </div>
                  ) : null}
                  <div className="job-focus-actions">
                    {buildJobPrimaryAction(focusJob).href ? (
                      <Button type="primary">
                        <Link href={buildJobPrimaryAction(focusJob).href ?? "/reports"}>{buildJobPrimaryAction(focusJob).label}</Link>
                      </Button>
                    ) : (
                      <Button disabled>{buildJobPrimaryAction(focusJob).label}</Button>
                    )}
                    <Button disabled={!["queued", "running"].includes(focusJob.status)} onClick={() => void cancelJob(focusJob.id)}>
                      取消当前焦点任务
                    </Button>
                    <Button disabled={focusJob.status !== "failed"} onClick={() => void retryJob(focusJob.id)}>
                      按原配置重跑
                    </Button>
                  </div>
                </div>
              </div>
            ) : null}
            <div className="job-summary-banner">
              <div className="job-summary-main">
                <strong>先看最近几次任务，再决定要不要展开完整历史</strong>
                <p>当前最重要的是确认是否已生成报告、任务卡在哪个阶段、预计还要多久，以及失败原因是否重复，而不是直接浏览全部历史记录。</p>
              </div>
              <div className="job-summary-metrics">
                <span>执行中 {runningJobs.length}</span>
                <span>排队中 {queuedJobs.length}</span>
                <span>失败 {failedJobs.length}</span>
                <span>已完成 {succeededJobs.length}</span>
              </div>
              <div className="job-summary-actions">
                {latestSucceededJob?.reports?.[0]?.id ? (
                  <Button type="primary">
                    <Link href={`/reports/${latestSucceededJob.reports[0].id}`}>查看最新结果</Link>
                  </Button>
                ) : null}
                <Button>
                  <Link href="/reports">进入结果库</Link>
                </Button>
              </div>
            </div>

            <div className="job-mobile-list">
              {recentJobs.map((job) => {
                const payload = job.request_payload;
                const templateName = (payload.template_snapshot as { template_name?: string } | undefined)?.template_name;
                const primaryAction = buildJobPrimaryAction(job);
                const runtime = buildJobRuntimeSummary(job);
                return (
                  <article key={job.id} className="job-mobile-card">
                    <div className="job-mobile-card-head">
                      <div>
                        <strong>任务 #{job.id}</strong>
                        <span>{String(payload.symbol ?? "-")} / {String(payload.interval ?? "-")} / {strategyLabel(String(payload.strategy_kind ?? "-"))}</span>
                      </div>
                      <StatusTag value={job.status} label={backtestStatusLabel(job.status)} />
                    </div>
                    <p>{buildJobReadingHint(job)}</p>
                    <div className="job-mobile-runtime">
                      <strong>{runtime.title}</strong>
                      <span>{runtime.description}</span>
                    </div>
                    <Progress
                      percent={Math.round(job.progress_pct)}
                      size="small"
                      status={job.status === "failed" ? "exception" : job.status === "succeeded" ? "success" : "active"}
                    />
                    <div className="job-mobile-metrics">
                      <span>进度 {job.progress_pct.toFixed(0)}%</span>
                      <span>模板 {templateName ?? "未选择"}</span>
                      {job.runtime_details.worker_name ? <span>执行槽位 {job.runtime_details.worker_name}</span> : null}
                      {job.runtime_details.queue_position ? <span>排队位置 #{job.runtime_details.queue_position}</span> : null}
                    </div>
                    {job.runtime_details.resource_summary ? <p>{job.runtime_details.resource_summary}</p> : null}
                    {job.error_message ? <p className="job-mobile-error">{job.error_message}</p> : null}
                    <div className="job-mobile-actions">
                      {primaryAction.href ? (
                        <Button type="primary">
                          <Link href={primaryAction.href}>{primaryAction.label}</Link>
                        </Button>
                      ) : (
                        <Button disabled={primaryAction.disabled}>{primaryAction.label}</Button>
                      )}
                      <Button disabled={!["queued", "running"].includes(job.status)} onClick={() => void cancelJob(job.id)}>
                        取消任务
                      </Button>
                      <Button disabled={job.status !== "failed"} onClick={() => void retryJob(job.id)}>
                        按原配置重跑
                      </Button>
                    </div>
                  </article>
                );
              })}
            </div>
            <div className="detail-secondary-hint">
              <strong>只有在需要逐条核对或批量处理时，再展开下面的完整历史</strong>
              <p>如果你只是确认是否成功生成报告、是否仍有任务在执行，以及失败原因是否重复，前面的任务卡通常已经足够。</p>
            </div>

            <Collapse
              className="advanced-table-panel"
              ghost
              items={[
                {
                  key: "history",
                  label: (
                    <div className="advanced-trace-label">
                      <strong>批量处理或逐条核对时，再看完整历史</strong>
                      <span>这里更适合批量取消、批量重试，或按列核对每条任务的状态、时间与错误信息。</span>
                    </div>
                  ),
                  children: (
                    <>
                      <div className="table-toolbar">
                        <ToolbarCount>已选 {selectedJobIds.length} 条，仅在需要批量处理时再操作。</ToolbarCount>
                        <Space>
                          <Button size="small" disabled={selectedJobIds.length === 0} onClick={() => void bulkCancelJobs()}>
                            取消所选任务
                          </Button>
                          <Button size="small" disabled={selectedJobIds.length === 0} onClick={() => void bulkRetryJobs()}>
                            重跑所选任务
                          </Button>
                        </Space>
                      </div>
                      <Table
                        className="job-desktop-table"
                        rowKey="id"
                        size="small"
                        dataSource={jobs}
                        rowSelection={{ selectedRowKeys: selectedJobIds, onChange: setSelectedJobIds }}
                        pagination={{ pageSize: 12, showSizeChanger: false }}
                        scroll={{ x: 1540 }}
                        columns={[
                          { title: "回测编号", dataIndex: "id", width: 88, fixed: "left" },
                          { title: "标的", render: (_, row) => String(row.request_payload.symbol ?? "-"), width: 120 },
                          { title: "周期", render: (_, row) => String(row.request_payload.interval ?? "-"), width: 90 },
                          { title: "策略", render: (_, row) => strategyLabel(String(row.request_payload.strategy_kind ?? "-")), width: 160, ellipsis: true },
                          { title: "模板", render: (_, row) => String((row.request_payload.template_snapshot as { template_name?: string } | undefined)?.template_name ?? "-"), ellipsis: true },
                          { title: "状态", dataIndex: "status", width: 110, render: (value: string) => <StatusTag value={value} label={backtestStatusLabel(value)} /> },
                          {
                            title: "进度",
                            dataIndex: "progress_pct",
                            width: 170,
                            render: (value: number, row) => (
                              <div>
                                <Progress
                                  percent={Math.round(value)}
                                  size="small"
                                  status={row.status === "failed" ? "exception" : row.status === "succeeded" ? "success" : "active"}
                                />
                                <Typography.Text type="secondary">
                                  {row.runtime_details.stage_label ?? "等待更新"}
                                </Typography.Text>
                              </div>
                            ),
                          },
                          {
                            title: "预计剩余",
                            width: 110,
                            render: (_, row) =>
                              row.status === "running"
                                ? formatDuration(row.runtime_details.eta_seconds)
                                : row.status === "queued" && row.runtime_details.queue_position
                                  ? `队列第 ${row.runtime_details.queue_position} 位`
                                  : "-",
                          },
                          {
                            title: "已运行",
                            width: 110,
                            render: (_, row) => (row.runtime_details.elapsed_seconds ? formatDuration(row.runtime_details.elapsed_seconds) : "-"),
                          },
                          {
                            title: "资源计划",
                            width: 240,
                            render: (_, row) => row.runtime_details.resource_summary ?? "-",
                            ellipsis: true,
                          },
                          { title: "提交时间", dataIndex: "submitted_at", width: 180 },
                          { title: "完成时间", dataIndex: "completed_at", width: 180 },
                          { title: "错误信息", dataIndex: "error_message", ellipsis: true },
                          {
                            title: "操作",
                            width: 150,
                            fixed: "right",
                            render: (_, row) => (
                              <Space size="small">
                                <Button size="small" disabled={!["queued", "running"].includes(row.status)} onClick={() => void cancelJob(row.id)}>
                                  取消
                                </Button>
                                <Button size="small" disabled={row.status !== "failed"} onClick={() => void retryJob(row.id)}>
                                  重跑
                                </Button>
                              </Space>
                            ),
                          },
                        ]}
                      />
                      <Typography.Paragraph className="table-help">
                        任务完成后会自动生成结果，可直接进入结果库查看；若执行失败，常见原因通常是覆盖不足、模板不匹配或参数组合不适应当前样本。
                      </Typography.Paragraph>
                    </>
                  ),
                },
              ]}
            />
          </>
        )}
      </Card>
    </div>
  );
}
