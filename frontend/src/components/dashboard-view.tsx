"use client";

import { ArrowRightOutlined, CheckCircleOutlined, DatabaseOutlined, FileSearchOutlined, MonitorOutlined, PlayCircleOutlined } from "@ant-design/icons";
import { Button, Card, Col, Collapse, Empty, Progress, Row, Skeleton, Space, Table, Tag, Typography, message } from "antd";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { apiFetch, apiFetchSafe, type BacktestJob, type MarketDataStats, type ReportSummary } from "@/lib/api";
import { FormatPercent, InlineErrorBanner, MetricCard, PageErrorState, PageHeader, StatusTag } from "@/components/platform-ui";
import { strategyLabel } from "@/lib/strategy-template-config";
import { buildBacktestLaunchHref, buildBacktestPresetHref, buildBeginnerPresets, type BeginnerPreset } from "@/lib/beginner-presets";

type GuideCard = {
  title: string;
  value: string;
  description: string;
};

function getValidationMetrics(report: ReportSummary) {
  const validation = report.summary_metrics.validation ?? {};
  const netReturn = Number(validation.NetReturnPct ?? validation.ReturnPct ?? 0);
  const maxDrawdown = Number(validation.MaxDrawdownPct ?? 0);
  const closedTrades = Number(validation.ClosedTrades ?? 0);
  return { netReturn, maxDrawdown, closedTrades };
}

function latestSuccessGuides(report: ReportSummary) {
  const { netReturn, maxDrawdown, closedTrades } = getValidationMetrics(report);
  return [
    {
      title: "结果有效性",
      value: netReturn > 0 ? "具备继续复盘价值" : "暂不宜直接采用",
      description:
        netReturn > 0
          ? `单独验证收益 ${netReturn.toFixed(2)}%，说明该配置在当前验证区间内取得正收益。`
          : `单独验证收益 ${netReturn.toFixed(2)}%，建议优先与其他模板或周期做对照。`,
    },
    {
      title: "风险暴露",
      value: maxDrawdown <= 8 ? "回撤相对可控" : maxDrawdown <= 15 ? "回撤中等" : "回撤偏高",
      description:
        maxDrawdown <= 8
          ? `最大回撤 ${maxDrawdown.toFixed(2)}%，风险暴露与收益表现相对平衡。`
          : `最大回撤 ${maxDrawdown.toFixed(2)}%，继续采用前应重点评估波动承受能力。`,
    },
    {
      title: "后续动作",
      value: closedTrades === 0 ? "调整标的或周期" : netReturn > 0 ? "进入横向对比" : "调整配置重跑",
      description:
        closedTrades === 0
          ? "当前验证区间未形成有效成交，建议优先更换更活跃的标的或研究周期。"
          : netReturn > 0
            ? "建议先打开报告详情，再与同标的其他结果做横向比较。"
            : "建议保留当前结果作为对照，再基于同一路径调整模板或周期重跑。",
    },
  ];
}

function buildStartRecommendation(params: {
  instrumentCount: number;
  presetCount: number;
  latestSucceededReportId: number | null;
  rerunHref: string | null;
}) {
  if (params.latestSucceededReportId && params.rerunHref) {
    return {
      title: "优先沿用最近一次有效研究配置",
      description: "当前最直接的做法不是重新填写表单，而是先复盘最近一次有效结果，再沿原配置发起对照回测。",
      primaryLabel: "查看最近结果",
      primaryHref: `/reports/${params.latestSucceededReportId}`,
      secondaryLabel: "按原配置重跑",
      secondaryHref: params.rerunHref,
      guideItems: [
        {
          title: "推荐依据",
          value: "已存在有效任务与结果",
          description: "最近一次成功任务和报告已构成完整研究闭环，复盘或重跑的效率高于从空白配置重新开始。",
        },
        {
          title: "当前优先级",
          value: "先完成结果判断",
          description: "应先确认收益、回撤和交易节奏是否具备继续研究价值，再决定进入对比、调参还是换标的。",
        },
      ] satisfies GuideCard[],
    };
  }
  if (params.presetCount > 0) {
    return {
      title: "优先使用现成研究样本进入主流程",
      description: "当前已有可直接使用的标的与周期，无需先浏览全部功能；直接基于推荐样本进入回测配置即可。",
      primaryLabel: "查看推荐样本",
      primaryHref: "#beginner-presets",
      secondaryLabel: "进入回测配置",
      secondaryHref: "/backtests",
      guideItems: [
        {
          title: "推荐依据",
          value: "已有可直接使用的样本组合",
          description: "首页已筛出同时满足当前数据条件和基线研究需求的标的，无需先浏览全部功能页。",
        },
        {
          title: "当前优先级",
          value: "先形成一份可复盘结果",
          description: "先完成一次提交与结果复盘，比先补齐大量标的更能确认平台主路径是否满足研究需求。",
        },
      ] satisfies GuideCard[],
    };
  }
  if (params.instrumentCount > 0) {
    return {
      title: "先确认目标标的的覆盖情况",
      description: "当前库内已有行情数据，但尚未形成标准样本；建议先检查 1d 或 15m 是否齐备，再决定是否发起回测。",
      primaryLabel: "检查覆盖情况",
      primaryHref: "/market-data",
      secondaryLabel: "进入回测配置",
      secondaryHref: "/backtests",
      guideItems: [
        {
          title: "推荐依据",
          value: "已有数据但缺少标准样本",
          description: "当前更应确认目标标的是否具备 1d 或 15m，而不是优先浏览更多模板或历史结果。",
        },
        {
          title: "当前优先级",
          value: "先确认关键周期",
          description: "先确认可用周期，再进入回测配置，可以减少因覆盖不足导致的提交失败。",
        },
      ] satisfies GuideCard[],
    };
  }
  return {
    title: "先补齐一个可研究标的的关键覆盖",
    description: "当前尚无可直接使用的行情覆盖。建议先在数据覆盖页补齐熟悉标的的 1d 或 15m，再返回主流程。",
    primaryLabel: "前往数据覆盖",
    primaryHref: "/market-data",
    secondaryLabel: "查看模板库",
    secondaryHref: "/templates",
    guideItems: [
      {
        title: "推荐依据",
        value: "当前缺少可直接研究的数据覆盖",
        description: "在没有行情覆盖的情况下，模板和报告都无法支撑研究起点，优先补齐一个熟悉标的最直接。",
      },
      {
        title: "当前优先级",
        value: "先建立最小可研究样本",
        description: "一只具备 1d 或 15m 的标的已足够验证主路径；待流程确认后，再扩展更多数据覆盖。",
      },
    ] satisfies GuideCard[],
  };
}

function buildPresetGuides(preset: BeginnerPreset): GuideCard[] {
  const readyForShortCycle = preset.availableIntervals.includes("15m");
  const readyForLongCycle = preset.availableIntervals.includes("1d");
  return [
    {
      title: "研究适配性",
      value: readyForShortCycle && readyForLongCycle ? "日线与分钟研究均可覆盖" : readyForShortCycle ? "可直接开展分钟研究" : "适合日线与长期研究",
      description: preset.reason,
    },
    {
      title: "建议用途",
      value: readyForShortCycle ? `以 ${strategyLabel(preset.strategyKind)} 作为基线配置` : "用于日线或长期节奏验证",
      description:
        readyForShortCycle
          ? "这类样本更适合快速形成完整的回测、提交与复盘闭环。"
          : "这类样本更适合先观察长期收益与回撤，再决定是否扩展到分钟级策略。",
    },
  ];
}

function buildHomeReportSpotlight(report: ReportSummary, latestSucceededReportId: number | null): { label: string; color: string; description: string } {
  const { netReturn, maxDrawdown, closedTrades } = getValidationMetrics(report);
  if (report.id === latestSucceededReportId) {
    return {
      label: "最近有效结果",
      color: "blue",
      description: "该报告直接对应最近一次有效研究路径，适合优先确认其是否具备继续研究价值。",
    };
  }
  if (closedTrades === 0) {
    return {
      label: "优先检查触发条件",
      color: "default",
      description: "该结果更适合用于判断问题来自标的活跃度、周期选择，还是模板条件过严。",
    };
  }
  if (netReturn > 0 && maxDrawdown <= 8) {
    return {
      label: "优先复盘",
      color: "green",
      description: "该结果同时具备正收益与相对可控的回撤，适合作为优先复盘样本。",
    };
  }
  if (netReturn > 0) {
    return {
      label: "关注波动暴露",
      color: "gold",
      description: "该结果虽取得正收益，但更需要确认回撤和净值波动是否在可接受范围内。",
    };
  }
  return {
    label: "作为反向对照",
    color: "red",
    description: "该结果更适合作为对照样本，帮助判断应优先排除的模板、参数或周期组合。",
  };
}

function formatDuration(seconds: number | null | undefined): string {
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

function dashboardBacktestStatusLabel(status: string): string {
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

function pickDashboardFocusJob(jobs: BacktestJob[]): BacktestJob | null {
  const orderedJobs = [...jobs].sort((left, right) => right.id - left.id);
  return (
    orderedJobs.find((item) => item.status === "running") ??
    orderedJobs.find((item) => item.status === "queued") ??
    orderedJobs.find((item) => item.status === "cancel_requested") ??
    orderedJobs.find((item) => item.status === "failed") ??
    null
  );
}

function buildDashboardJobRuntimeSummary(job: BacktestJob): { title: string; description: string } {
  const runtime = job.runtime_details;
  if (job.status === "queued") {
    return {
      title: runtime.queue_position && runtime.queue_position > 1 ? `队列第 ${runtime.queue_position} 位` : "等待进入执行",
      description: runtime.stage_message ?? "任务已入队，等待 worker 领取。",
    };
  }
  if (job.status === "running") {
    return {
      title: runtime.stage_label ? `当前阶段：${runtime.stage_label}` : "正在执行",
      description: `已运行 ${formatDuration(runtime.elapsed_seconds)}，预计还需 ${formatDuration(runtime.eta_seconds)}。${runtime.stage_message ?? ""}`.trim(),
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

function buildDashboardJobReadingHint(job: BacktestJob): string {
  const stageLabel = job.runtime_details.stage_label;
  if (job.status === "failed") {
    return "本次任务执行失败，建议先确认错误信息；常见原因包括数据覆盖不足、模板不匹配或参数与标的不适配。";
  }
  if (job.status === "queued") {
    const queuePosition = job.runtime_details.queue_position;
    return queuePosition && queuePosition > 1
      ? `任务仍在排队，前面还有 ${queuePosition - 1} 个任务等待执行。通常无需重复提交。`
      : "任务仍在排队，通常无需重复提交；待进入执行阶段后，再判断是否需要取消。";
  }
  if (job.status === "running") {
    return stageLabel
      ? `任务仍在执行中，当前阶段为“${stageLabel}”。若长时间无进展，再进入运行维护页排查。`
      : "任务仍在执行中，建议等待结果输出；若长时间无进展，再进入运行维护页排查。";
  }
  if (job.status === "cancel_requested" || job.status === "cancelled") {
    return "任务正在取消或已取消；若仍需继续验证，可直接按原配置重新提交。";
  }
  return "建议先确认当前状态与错误信息，再决定是重跑、取消，还是进入结果库继续复盘。";
}

function buildDashboardFocusReason(job: BacktestJob): string {
  if (job.status === "running") {
    return "这是当前最需要盯的一条任务，因为它正在消耗执行资源，且阶段、ETA 和资源摘要会持续变化。";
  }
  if (job.status === "queued") {
    return "这是当前最需要盯的一条任务，因为它决定你接下来什么时候能看到新的结果，通常不需要再重复提交。";
  }
  if (job.status === "failed") {
    return "这是当前最需要处理的一条任务，因为它直接阻断了结果生成，应先确认失败原因是否需要重跑或改配置。";
  }
  return "这是当前最值得优先确认的一条任务。先处理完这条，再决定是否进入完整历史或维护页。";
}

function buildDashboardJobPrimaryAction(job: BacktestJob): { label: string; href: string | null; disabled: boolean } {
  const reportId = job.reports?.[0]?.id;
  if (reportId) {
    return { label: "查看结果", href: `/reports/${reportId}`, disabled: false };
  }
  if (job.status === "failed") {
    return { label: "未生成结果", href: null, disabled: true };
  }
  return { label: "进入回测页", href: "/backtests", disabled: false };
}

function buildDashboardFocusGuides(job: BacktestJob): GuideCard[] {
  const runtime = buildDashboardJobRuntimeSummary(job);
  const resourceParts: string[] = [];
  if (job.runtime_details.worker_name) {
    resourceParts.push(`执行槽位 ${job.runtime_details.worker_name}`);
  }
  if (typeof job.runtime_details.requested_parallelism === "number") {
    resourceParts.push(`请求并发 ${job.runtime_details.requested_parallelism}`);
  }
  if (typeof job.runtime_details.effective_parallelism === "number") {
    resourceParts.push(`实际并发 ${job.runtime_details.effective_parallelism}`);
  }
  if (typeof job.runtime_details.worker_concurrency === "number") {
    resourceParts.push(`worker 上限 ${job.runtime_details.worker_concurrency}`);
  }
  if (typeof job.runtime_details.max_optimization_workers === "number") {
    resourceParts.push(`单任务上限 ${job.runtime_details.max_optimization_workers}`);
  }

  let timeValue = "等待更新";
  if (job.status === "running") {
    timeValue = `已运行 ${formatDuration(job.runtime_details.elapsed_seconds)} / 预计还需 ${formatDuration(job.runtime_details.eta_seconds)}`;
  } else if (job.status === "queued") {
    timeValue = job.runtime_details.queue_position ? `队列第 ${job.runtime_details.queue_position} 位` : "等待 worker 领取";
  } else if (job.status === "failed") {
    timeValue = job.runtime_details.elapsed_seconds ? `已运行 ${formatDuration(job.runtime_details.elapsed_seconds)}` : "已结束";
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
      description: job.status === "running" ? "首页会自动刷新这里的 ETA 和已运行时间，无需反复切页确认。" : runtime.description,
    },
    {
      title: "资源安排",
      value: job.runtime_details.resource_summary ?? "按平台资源预算执行",
      description: resourceParts.length > 0 ? resourceParts.join("，") : "平台会按 worker 并发与单任务上限自动收口资源使用。",
    },
    {
      title: "下一步动作",
      value: job.status === "failed" ? "先判定失败原因" : job.status === "queued" ? "等待进入执行" : "盯进度与 ETA",
      description: buildDashboardJobReadingHint(job),
    },
  ];
}

export function DashboardView() {
  const [stats, setStats] = useState<MarketDataStats | null>(null);
  const [jobs, setJobs] = useState<BacktestJob[]>([]);
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [partialError, setPartialError] = useState<string | null>(null);
  const [messageApi, contextHolder] = message.useMessage();
  const beginnerPresets = useMemo(() => (stats ? buildBeginnerPresets(stats.coverages) : []), [stats]);

  const loadDashboardSnapshot = useCallback(async (showSpinner: boolean = true) => {
    if (showSpinner) {
      setLoading(true);
    }
    const [statsResult, jobsResult, reportsResult] = await Promise.all([
      apiFetchSafe<MarketDataStats>("/api/market-data/stats"),
      apiFetchSafe<BacktestJob[]>("/api/backtests?limit=8"),
      apiFetchSafe<ReportSummary[]>("/api/reports?limit=8"),
    ]);

    const issues: string[] = [];
    if (statsResult.ok) {
      setStats(statsResult.data);
      setLoadError(null);
    } else {
      issues.push(`总览统计读取失败：${statsResult.error.message}`);
      if (!stats) {
        setLoadError(statsResult.error.message);
      }
    }

    if (jobsResult.ok) {
      setJobs(jobsResult.data);
    } else {
      issues.push(`任务列表读取失败：${jobsResult.error.message}`);
    }

    if (reportsResult.ok) {
      setReports(reportsResult.data);
    } else {
      issues.push(`结果列表读取失败：${reportsResult.error.message}`);
    }

    setPartialError(statsResult.ok || stats ? (issues.length > 0 ? issues.join("；") : null) : null);
    setLoading(false);
  }, [stats]);

  useEffect(() => {
    queueMicrotask(() => {
      void loadDashboardSnapshot();
    });
  }, [loadDashboardSnapshot]);

  const hasActiveJobs = useMemo(
    () => jobs.some((item) => ["queued", "running", "cancel_requested"].includes(item.status)),
    [jobs],
  );

  useEffect(() => {
    if (!hasActiveJobs) {
      return;
    }
    const timer = window.setInterval(() => {
      void loadDashboardSnapshot(false);
    }, 4000);
    return () => window.clearInterval(timer);
  }, [hasActiveJobs, loadDashboardSnapshot]);

  async function cancelJob(jobId: number) {
    try {
      await apiFetch(`/api/backtests/${jobId}/cancel`, {
        method: "POST",
      });
      messageApi.success(`已提交任务 #${jobId} 的取消请求`);
      await loadDashboardSnapshot(false);
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "取消任务失败");
    }
  }

  async function retryJob(jobId: number) {
    try {
      await apiFetch(`/api/backtests/${jobId}/retry`, {
        method: "POST",
      });
      messageApi.success(`已按原配置重新提交任务 #${jobId}`);
      await loadDashboardSnapshot(false);
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "重跑任务失败");
    }
  }

  if (loading && !stats) {
    return <Skeleton active paragraph={{ rows: 8 }} />;
  }

  if (!stats) {
    return <PageErrorState title="研究总览暂时不可用" description={loadError ?? "暂时无法读取平台数据"} onRetry={() => void loadDashboardSnapshot()} />;
  }

  const latestSync = stats.recent_sync_runs[0] as { status?: string; interval?: string; completed_at?: string } | undefined;
  const succeededJobs = jobs.filter((item) => item.status === "succeeded").length;
  const failedJobs = jobs.filter((item) => item.status === "failed").length;
  const latestSyncStatus = latestSync?.status === "completed" ? "已完成" : latestSync?.status === "failed" ? "失败" : latestSync?.status ?? "暂无";
  const latestSucceededJob = jobs.find((item) => item.status === "succeeded") ?? null;
  const focusJob = pickDashboardFocusJob(jobs);
  const latestSucceededReportSummary = reports.find((item) => item.job_id === latestSucceededJob?.id) ?? null;
  const latestSucceededReportId = latestSucceededJob?.reports?.[0]?.id ?? latestSucceededReportSummary?.id ?? null;
  const latestSucceededPayload = latestSucceededJob?.request_payload ?? null;
  const latestSucceededTemplateId =
    typeof latestSucceededPayload?.template_id === "number"
      ? latestSucceededPayload.template_id
      : typeof (latestSucceededPayload?.template_snapshot as { id?: unknown } | undefined)?.id === "number"
        ? ((latestSucceededPayload?.template_snapshot as { id?: number }).id ?? undefined)
        : undefined;
  const latestSucceededRerunHref = latestSucceededPayload
    ? buildBacktestLaunchHref({
        symbol: String(latestSucceededPayload.symbol ?? ""),
        interval: String(latestSucceededPayload.interval ?? "15m"),
        strategyKind: String(latestSucceededPayload.strategy_kind ?? "grid"),
        templateId: latestSucceededTemplateId,
        marketDataProvider:
          typeof latestSucceededPayload.market_data_provider === "string" ? latestSucceededPayload.market_data_provider : undefined,
        marketDataAdjustmentKind:
          typeof latestSucceededPayload.market_data_adjustment_kind === "string"
            ? latestSucceededPayload.market_data_adjustment_kind
            : undefined,
      })
    : null;
  const startRecommendation = buildStartRecommendation({
    instrumentCount: stats.instrument_count,
    presetCount: beginnerPresets.length,
    latestSucceededReportId,
    rerunHref: latestSucceededRerunHref,
  });
  const spotlightReports = [...reports]
    .sort((left, right) => {
      const leftSpotlight = buildHomeReportSpotlight(left, latestSucceededReportId);
      const rightSpotlight = buildHomeReportSpotlight(right, latestSucceededReportId);
      const leftPriority =
        leftSpotlight.label === "最近有效结果" ? 4 :
        leftSpotlight.label === "优先复盘" ? 3 :
        leftSpotlight.label === "关注波动暴露" ? 2 :
        leftSpotlight.label === "作为反向对照" ? 1 : 0;
      const rightPriority =
        rightSpotlight.label === "最近有效结果" ? 4 :
        rightSpotlight.label === "优先复盘" ? 3 :
        rightSpotlight.label === "关注波动暴露" ? 2 :
        rightSpotlight.label === "作为反向对照" ? 1 : 0;
      if (leftPriority !== rightPriority) {
        return rightPriority - leftPriority;
      }
      return right.id - left.id;
    })
    .slice(0, 4);

  return (
    <div className="page-stack">
      {contextHolder}
      {partialError ? <InlineErrorBanner message={partialError} onRetry={() => void loadDashboardSnapshot(false)} /> : null}
      <section className="hero-panel beginner-hero">
        <div className="beginner-hero-copy">
          <PageHeader
            eyebrow="研究总览"
            title="从数据覆盖到结果复盘的策略研究工作台"
            description="围绕单一标的建立回测样本，选择策略模板并提交任务，再基于收益、回撤与交易记录完成结果复盘。"
          />
          <Space wrap className="hero-actions">
            <Button type="primary" size="large" icon={<PlayCircleOutlined />}>
              <Link href="/backtests">发起回测</Link>
            </Button>
            <Button size="large" icon={<FileSearchOutlined />}>
              <Link href="/reports">查看结果库</Link>
            </Button>
          </Space>
        </div>
        <div className="readiness-card">
          <span className="readiness-label">当前研究状态</span>
          <strong>{stats.instrument_count > 0 ? "可直接进入主流程" : "需先补齐关键覆盖"}</strong>
          <span>{stats.instrument_count.toLocaleString()} 个标的，{stats.total_bars.toLocaleString()} 条 K 线</span>
        </div>
      </section>

      <Card size="small" className="section-card start-path-card">
        <div className="start-path-main">
          <strong>{startRecommendation.title}</strong>
          <p>{startRecommendation.description}</p>
          <div className="start-path-guide-grid">
            {startRecommendation.guideItems.map((item) => (
              <article key={item.title} className="start-path-guide-card">
                <span>{item.title}</span>
                <strong>{item.value}</strong>
                <p>{item.description}</p>
              </article>
            ))}
          </div>
        </div>
        <div className="start-path-actions">
          <Button type="primary">
            <Link href={startRecommendation.primaryHref}>{startRecommendation.primaryLabel}</Link>
          </Button>
          <Button>
            <Link href={startRecommendation.secondaryHref}>{startRecommendation.secondaryLabel}</Link>
          </Button>
        </div>
      </Card>

      {focusJob ? (
        <Card size="small" title="当前执行焦点" className="section-card">
          <div className="job-focus-card">
            <div className="job-focus-main">
              <div className="job-focus-head">
                <div>
                  <span className="job-focus-label">首页实时执行脉冲</span>
                  <strong>
                    任务 #{focusJob.id} · {String(focusJob.request_payload.symbol ?? "-")} / {String(focusJob.request_payload.interval ?? "-")} / {strategyLabel(String(focusJob.request_payload.strategy_kind ?? "-"))}
                  </strong>
                </div>
                <StatusTag value={focusJob.status} label={dashboardBacktestStatusLabel(focusJob.status)} />
              </div>
              <p className="job-focus-summary">{buildDashboardFocusReason(focusJob)}</p>
              <div className="job-focus-progress">
                <div className="job-focus-progress-head">
                  <strong>当前进度 {focusJob.progress_pct.toFixed(0)}%</strong>
                  <span>{focusJob.runtime_details.stage_label ?? "等待阶段更新"}</span>
                </div>
                <Progress
                  percent={Math.round(focusJob.progress_pct)}
                  status={focusJob.status === "failed" ? "exception" : focusJob.status === "running" ? "active" : "normal"}
                />
              </div>
              <div className="job-focus-guide-grid">
                {buildDashboardFocusGuides(focusJob).map((item) => (
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
                <span>为什么现在看它</span>
                <strong>{dashboardBacktestStatusLabel(focusJob.status)}</strong>
                <p>{buildDashboardJobReadingHint(focusJob)}</p>
              </div>
              {focusJob.error_message ? (
                <div className="job-focus-side-card is-danger">
                  <span>失败或异常信息</span>
                  <strong>需要先处理</strong>
                  <p>{focusJob.error_message}</p>
                </div>
              ) : null}
              <div className="job-focus-actions">
                {buildDashboardJobPrimaryAction(focusJob).href ? (
                  <Button type="primary">
                    <Link href={buildDashboardJobPrimaryAction(focusJob).href ?? "/backtests"}>{buildDashboardJobPrimaryAction(focusJob).label}</Link>
                  </Button>
                ) : (
                  <Button disabled>{buildDashboardJobPrimaryAction(focusJob).label}</Button>
                )}
                <Button disabled={!["queued", "running"].includes(focusJob.status)} onClick={() => void cancelJob(focusJob.id)}>
                  取消当前任务
                </Button>
                <Button disabled={focusJob.status !== "failed"} onClick={() => void retryJob(focusJob.id)}>
                  按原配置重跑
                </Button>
              </div>
            </div>
          </div>
        </Card>
      ) : null}

      <Row gutter={[16, 16]}>
        <Col xs={24} md={8}>
          <Card className="action-card" size="small">
            <div className="action-card-icon"><DatabaseOutlined /></div>
            <Typography.Title level={4}>1. 数据覆盖</Typography.Title>
            <p>先确认目标标的是否具备 1d 或 15m。优先补齐当前研究所需周期，无需一开始全量建库。</p>
            <Button type="link">
              <Link href="/market-data">检查覆盖情况 <ArrowRightOutlined /></Link>
            </Button>
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card className="action-card" size="small">
            <div className="action-card-icon"><PlayCircleOutlined /></div>
            <Typography.Title level={4}>2. 创建回测</Typography.Title>
            <p>输入 Yahoo 标的代码并选择策略模板，先建立一份可复盘的基线结果。</p>
            <Button type="link">
              <Link href="/backtests">配置任务 <ArrowRightOutlined /></Link>
            </Button>
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card className="action-card" size="small">
            <div className="action-card-icon"><FileSearchOutlined /></div>
            <Typography.Title level={4}>3. 结果复盘</Typography.Title>
            <p>优先检查验证收益、最大回撤、净值曲线与交易记录，再决定对比还是重跑。</p>
            <Button type="link">
              <Link href="/reports">进入结果库 <ArrowRightOutlined /></Link>
            </Button>
          </Card>
        </Col>
      </Row>

      <Card size="small" className="section-card support-boundary-card">
        <div className="support-boundary-main">
          <div className="support-boundary-icon"><MonitorOutlined /></div>
          <div>
            <strong>只有服务异常、任务停滞或连续失败时，再进入系统状态</strong>
            <p>{"系统状态页用于排障与运行检查，不是日常研究入口。常规操作优先停留在“数据覆盖 -> 创建回测 -> 结果复盘”主路径中。"}</p>
          </div>
        </div>
        <Button>
          <Link href="/platform">进入系统状态</Link>
        </Button>
      </Card>

      <Card id="beginner-presets" title="推荐研究样本" size="small" className="section-card">
        {beginnerPresets.length === 0 ? (
          <Typography.Text type="secondary">当前尚无可直接使用的标准样本，建议先到数据覆盖页补齐 15m 或 1d。</Typography.Text>
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
                  <Tag color="gold">{strategyLabel(preset.strategyKind)}</Tag>
                </div>
                <div className="beginner-preset-guides">
                  {buildPresetGuides(preset).map((item) => (
                    <article key={`${preset.symbol}-${item.title}`} className="beginner-preset-guide-card">
                      <span>{item.title}</span>
                      <strong>{item.value}</strong>
                      <p>{item.description}</p>
                    </article>
                  ))}
                </div>
                <Button type="primary">
                  <Link href={buildBacktestPresetHref(preset)}>基于该样本发起回测</Link>
                </Button>
              </article>
            ))}
          </div>
        )}
      </Card>

      <Card title="最近一次有效研究配置" size="small" className="section-card">
        {!latestSucceededJob || !latestSucceededPayload ? (
          <Typography.Text type="secondary">当前还没有形成有效回测结果。完成一次有效任务后，这里会保留可复用的配置入口。</Typography.Text>
        ) : (
          <div className="recent-success-card">
            <div className="recent-success-head">
              <div>
                <strong>任务编号 {latestSucceededJob.id} 已完成</strong>
                <span>
                  {String(latestSucceededPayload.symbol ?? "-")} / {String(latestSucceededPayload.interval ?? "-")} / {strategyLabel(String(latestSucceededPayload.strategy_kind ?? "-"))}
                </span>
              </div>
              <StatusTag value={latestSucceededJob.status} />
            </div>
            <div className="recent-success-metrics">
              <span>完成时间 {latestSucceededJob.completed_at || latestSucceededJob.submitted_at || "-"}</span>
              <span>模板 {String((latestSucceededPayload.template_snapshot as { template_name?: string } | undefined)?.template_name ?? "未记录模板")}</span>
            </div>
            {latestSucceededReportSummary ? (
              <div className="recent-success-guide-grid">
                {latestSuccessGuides(latestSucceededReportSummary).map((item) => (
                  <article key={item.title} className="recent-success-guide-card">
                    <span>{item.title}</span>
                    <strong>{item.value}</strong>
                    <p>{item.description}</p>
                  </article>
                ))}
              </div>
            ) : null}
            <p>若该结果仍具备研究价值，可先进入报告详情；若只需继续验证，可直接基于原标的、周期与模板再次发起任务。</p>
            <div className="recent-success-actions">
              {latestSucceededReportId ? (
                <Button type="primary">
                  <Link href={`/reports/${latestSucceededReportId}`}>查看该报告</Link>
                </Button>
                ) : (
                  <Button type="primary">
                  <Link href="/reports">进入结果库</Link>
                  </Button>
                )}
              <Button>
                <Link href={latestSucceededRerunHref ?? "/backtests"}>
                  按原配置重跑
                </Link>
              </Button>
            </div>
          </div>
        )}
      </Card>

      <div className="summary-grid">
        <MetricCard label="可回测标的" value={stats.instrument_count} note="已准备好的标的" />
        <MetricCard label="行情记录" value={stats.total_bars.toLocaleString()} note="用于回测的 K 线" />
        <MetricCard label="可用周期" value={stats.by_interval.map((item) => item.interval).join(" / ") || "-"} note={`${stats.by_interval.length} 类周期`} />
        <MetricCard label="数据最近更新" value={latestSyncStatus} note={latestSync?.completed_at ?? latestSync?.interval ?? "还没有更新记录"} />
      </div>

      <Card title="优先复盘的报告" size="small" className="section-card">
        {reports.length === 0 ? (
          <Empty description="暂无回测结果，请先创建任务。" />
        ) : (
          <>
            <div className="home-report-banner">
              <strong>这些卡片不是简单按时间排序，而是按复盘优先级排列</strong>
              <p>首页会优先展示最近有效结果、收益更稳的样本，以及适合作为反向对照的报告，帮助你快速确定复盘顺序。</p>
            </div>
            <div className="home-report-list">
              {spotlightReports.map((report) => {
                const validation = report.summary_metrics.validation ?? {};
                const { netReturn, maxDrawdown } = getValidationMetrics(report);
                const spotlight = buildHomeReportSpotlight(report, latestSucceededReportId);
                const brief =
                  netReturn > 0 && maxDrawdown <= 8
                    ? "该结果收益与波动较为平衡，适合作为优先复盘样本。"
                    : netReturn > 0
                      ? "该结果虽为正收益，但应优先确认回撤与净值波动是否可接受。"
                      : "该结果更适合作为反向对照，用于排除不合适的模板或周期组合。";
                return (
                  <article key={report.id} className="home-report-card">
                    <div className="home-report-card-head">
                      <div>
                        <strong>{report.symbol}，编号 {report.id}</strong>
                        <span>{report.name || "未命名标的"} / {report.interval} / {strategyLabel(report.strategy_kind)}</span>
                      </div>
                      <div className="home-report-card-tags">
                        <Tag color={spotlight.color}>{spotlight.label}</Tag>
                        <Tag>{report.dataset_end}</Tag>
                      </div>
                    </div>
                    <div className="home-report-metrics">
                      <span>单独验证收益 <FormatPercent value={validation.NetReturnPct ?? validation.ReturnPct ?? 0} /></span>
                      <span>最大回撤 {Number(validation.MaxDrawdownPct ?? 0).toFixed(2)}%</span>
                    </div>
                    <div className="home-report-spotlight">
                      <strong>优先级说明</strong>
                      <p>{spotlight.description}</p>
                    </div>
                    <p className="home-report-brief">{brief}</p>
                    <Button type="primary">
                      <Link href={`/reports/${report.id}`}>查看报告</Link>
                    </Button>
                  </article>
                );
              })}
            </div>
          </>
        )}
      </Card>

      <Collapse
        className="maintenance-collapse"
        items={[
          {
            key: "data",
            label: "高级数据明细：数据是否够用",
            children: (
              <Row gutter={[16, 16]}>
                <Col xs={24} xl={10}>
                  <Card title="数据周期覆盖" size="small" className="section-card">
                    <Table
                      size="small"
                      pagination={false}
                      rowKey="interval"
                      dataSource={stats.by_interval}
                      columns={[
                        { title: "周期", dataIndex: "interval", width: 120 },
                        { title: "记录数", dataIndex: "bar_count", render: (value: number) => value.toLocaleString() },
                      ]}
                    />
                  </Card>
                </Col>
                <Col xs={24} xl={14}>
                  <Card title="最近数据更新" size="small" className="section-card">
                    <Table
                      size="small"
                      pagination={false}
                      rowKey="id"
                      dataSource={stats.recent_sync_runs}
                      columns={[
                        { title: "编号", dataIndex: "id", width: 72 },
                        { title: "周期", dataIndex: "interval", width: 90 },
                        { title: "状态", dataIndex: "status", render: (value: string) => <StatusTag value={value} /> },
                        { title: "新增", dataIndex: "bars_inserted" },
                        { title: "更新", dataIndex: "bars_updated" },
                        { title: "完成时间", dataIndex: "completed_at", ellipsis: true },
                      ]}
                    />
                  </Card>
                </Col>
              </Row>
            ),
          },
          {
            key: "jobs",
            label: `高级明细：最近回测记录（已完成 ${succeededJobs} / 失败 ${failedJobs}）`,
            children: (
              <Card
                title="最近几次回测记录"
                size="small"
                className="section-card"
                extra={<span className="toolbar-count"><CheckCircleOutlined /> 已完成 {succeededJobs} / 失败 {failedJobs}</span>}
              >
                <Table
                  size="small"
                  pagination={false}
                  rowKey="id"
                  dataSource={jobs}
                  columns={[
                    { title: "编号", dataIndex: "id", width: 72 },
                    { title: "标的", render: (_, row) => String(row.request_payload.symbol ?? "-") },
                    { title: "周期", render: (_, row) => String(row.request_payload.interval ?? "-"), width: 80 },
                    { title: "策略", render: (_, row) => strategyLabel(String(row.request_payload.strategy_kind ?? "-")), ellipsis: true },
                    { title: "状态", dataIndex: "status", render: (value: string) => <StatusTag value={value} /> },
                  ]}
                />
              </Card>
            ),
          },
        ]}
      />
    </div>
  );
}
