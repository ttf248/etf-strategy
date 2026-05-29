"use client";

import {
  DatabaseOutlined,
  FileSearchOutlined,
  FundOutlined,
  FormOutlined,
  MenuOutlined,
  MonitorOutlined,
  SettingOutlined,
} from "@ant-design/icons";
import { Button, Drawer, Layout, Menu, Typography } from "antd";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { apiFetch, type BacktestJob, type MarketDataStats, type ReportSummary } from "@/lib/api";
import { strategyLabel } from "@/lib/strategy-template-config";

const { Header, Sider, Content } = Layout;

type ConsoleShellProps = {
  children: ReactNode;
};

type RouteShellConfig = {
  title: string;
  kicker: string;
  tipTitle: string;
  tipText: string;
};

type ShellSnapshot = {
  stats: MarketDataStats | null;
  jobs: BacktestJob[];
  reports: ReportSummary[];
  ready: boolean;
};

type ShellGuidance = {
  tone: "ready" | "active" | "attention";
  kicker: string;
  title: string;
  description: string;
  primaryLabel: string;
  primaryHref: string;
  secondaryLabel: string;
  secondaryHref: string;
  recommendedKey: string;
  signals: Array<{
    label: string;
    value: string;
    detail: string;
  }>;
};

type ShellSummaryItem = {
  label: string;
  value: string;
  detail: string;
};

const primaryItems = [
  { key: "/", icon: <FundOutlined />, label: <Link href="/">研究总览</Link> },
  { key: "/market-data", icon: <DatabaseOutlined />, label: <Link href="/market-data">准备数据</Link> },
  { key: "/templates", icon: <SettingOutlined />, label: <Link href="/templates">策略方案</Link> },
  { key: "/backtests", icon: <FormOutlined />, label: <Link href="/backtests">运行回测</Link> },
  { key: "/reports", icon: <FileSearchOutlined />, label: <Link href="/reports">结果复盘</Link> },
];

const supportItems = [
  { key: "/platform", icon: <MonitorOutlined />, label: <Link href="/platform">运行维护</Link> },
];

const routeTitles: Record<string, RouteShellConfig> = {
  "/": {
    title: "研究总览",
    kicker: "工作台首页",
    tipTitle: "主流程始终固定",
    tipText: "准备数据、选择模板、运行回测、复盘结果。维护页只在异常排障时进入。",
  },
  "/platform": {
    title: "运行维护",
    kicker: "排障与检查",
    tipTitle: "不要把维护页当成主工作区",
    tipText: "这里只负责服务状态、队列和日志排查。常规研究应停留在数据、回测和结果页。",
  },
  "/market-data": {
    title: "准备数据",
    kicker: "研究起点",
    tipTitle: "先确认数据够不够",
    tipText: "目标不是一次性补齐全市场，而是先补齐当前研究标的的关键周期。",
  },
  "/templates": {
    title: "策略方案",
    kicker: "模板与参数",
    tipTitle: "默认模板优先",
    tipText: "模板页的职责是快速选出基线方案，只有默认模板不匹配时才进入详细维护。",
  },
  "/backtests": {
    title: "运行回测",
    kicker: "任务执行",
    tipTitle: "先拿到一份能复盘的结果",
    tipText: "先提交基线任务，再根据进度、ETA 和结果结论决定是否继续扩展参数空间。",
  },
  "/reports": {
    title: "结果复盘",
    kicker: "结论判断",
    tipTitle: "先看结论，再读细节",
    tipText: "优先判断收益、回撤和是否跑赢买入持有，再决定是否深入看曲线、交易和事件。",
  },
};

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

function getValidationMetrics(report: ReportSummary | null): {
  netReturn: number;
  maxDrawdown: number;
  closedTrades: number;
  outperformBuyHold: boolean;
} {
  const validation = report?.summary_metrics.validation ?? {};
  const netReturn = Number(validation.NetReturnPct ?? validation.ReturnPct ?? 0);
  const maxDrawdown = Number(validation.MaxDrawdownPct ?? 0);
  const closedTrades = Number(validation.ClosedTrades ?? 0);
  const relativeValue = validation.StrategyVsBuyHold ?? validation.GridVsBuyHold;
  const outperformBuyHold =
    typeof validation.OutperformBuyHold === "boolean"
      ? validation.OutperformBuyHold
      : typeof relativeValue === "number" && Number.isFinite(relativeValue)
        ? relativeValue > 0
        : false;
  return { netReturn, maxDrawdown, closedTrades, outperformBuyHold };
}

function buildShellGuidance(snapshot: ShellSnapshot): ShellGuidance {
  if (!snapshot.ready) {
    return {
      tone: "ready",
      kicker: "正在整理主路径",
      title: "先等系统读出当前研究状态",
      description: "稍后这里会直接告诉你下一步该去哪一页，而不是让你自己判断。",
      primaryLabel: "回到研究总览",
      primaryHref: "/",
      secondaryLabel: "先看创建回测",
      secondaryHref: "/backtests",
      recommendedKey: "/",
      signals: [
        { label: "数据覆盖", value: "读取中", detail: "稍后判断是否已具备可直接研究的标的。" },
        { label: "执行状态", value: "读取中", detail: "稍后判断是否已有运行中或排队中的任务。" },
        { label: "结果库", value: "读取中", detail: "稍后判断是否已有值得优先复盘的结果。" },
      ],
    };
  }

  const sortedJobs = [...snapshot.jobs].sort((left, right) => right.id - left.id);
  const sortedReports = [...snapshot.reports].sort((left, right) => right.id - left.id);
  const instrumentCount = snapshot.stats?.instrument_count ?? 0;
  const latestRunningJob = sortedJobs.find((item) => item.status === "running") ?? null;
  const latestQueuedJob = sortedJobs.find((item) => item.status === "queued") ?? null;
  const latestFailedJob = sortedJobs.find((item) => item.status === "failed") ?? null;
  const latestReport = sortedReports[0] ?? null;
  const latestReportMetrics = getValidationMetrics(latestReport);
  const latestReportGroupCount = latestReport
    ? sortedReports.filter((item) => item.symbol === latestReport.symbol && item.interval === latestReport.interval).length
    : 0;

  if (latestRunningJob) {
    return {
      tone: "active",
      kicker: "现在最该盯的是执行进度",
      title: `先看任务 #${latestRunningJob.id} 的进度、ETA 和资源收口`,
      description: `当前已有任务在执行中。比起再切换更多页面，先确认“进度是否推进、预计还要多久、资源有没有被收口”更重要。`,
      primaryLabel: "进入回测页看实时进度",
      primaryHref: "/backtests",
      secondaryLabel: latestReport ? "顺手打开最近结果" : "查看结果库",
      secondaryHref: latestReport ? `/reports/${latestReport.id}` : "/reports",
      recommendedKey: "/backtests",
      signals: [
        {
          label: "当前阶段",
          value: latestRunningJob.runtime_details.stage_label ?? "执行中",
          detail: latestRunningJob.runtime_details.stage_message ?? "任务仍在推进，无需重复提交。",
        },
        {
          label: "预计剩余",
          value: formatDuration(latestRunningJob.runtime_details.eta_seconds),
          detail: `已运行 ${formatDuration(latestRunningJob.runtime_details.elapsed_seconds)}。`,
        },
        {
          label: "资源安排",
          value: latestRunningJob.runtime_details.resource_summary ?? "按平台预算执行",
          detail: "平台会按 worker 并发与单任务上限自动收口资源。",
        },
      ],
    };
  }

  if (latestQueuedJob) {
    return {
      tone: "active",
      kicker: "现在最该盯的是排队情况",
      title: `先等任务 #${latestQueuedJob.id} 开始，不必重复提交同类配置`,
      description: "当前已有任务在等待执行。此时最重要的不是再提一份相似任务，而是确认队列位置和是否已经接近开始。",
      primaryLabel: "进入回测页看排队位置",
      primaryHref: "/backtests",
      secondaryLabel: latestReport ? "查看最近结果" : "回到研究总览",
      secondaryHref: latestReport ? `/reports/${latestReport.id}` : "/",
      recommendedKey: "/backtests",
      signals: [
        {
          label: "等待位置",
          value: latestQueuedJob.runtime_details.queue_position ? `第 ${latestQueuedJob.runtime_details.queue_position} 位` : "已入队",
          detail: latestQueuedJob.runtime_details.stage_message ?? "worker 会按当前并发上限依次领取任务。",
        },
        {
          label: "等待中的任务",
          value: `${sortedJobs.filter((item) => item.status === "queued").length} 个`,
          detail: "已有任务在前面时，通常无需再重复提交流程相近的配置。",
        },
        {
          label: "最近结果",
          value: latestReport ? `编号 ${latestReport.id}` : "尚无结果",
          detail: latestReport ? "等待期间可以先复盘最近一份结果，不会浪费当前排队时间。" : "当前还没有可直接复盘的结果样本。",
        },
      ],
    };
  }

  if (latestFailedJob) {
    return {
      tone: "attention",
      kicker: "现在最该处理的是失败任务",
      title: `先判断任务 #${latestFailedJob.id} 为什么没跑通，再决定是否重跑`,
      description: "当最近一条任务失败时，继续盲目提交新任务通常只会重复同样的问题。先定位是数据覆盖、模板不匹配，还是运行环境异常。",
      primaryLabel: "进入回测页看失败任务",
      primaryHref: "/backtests",
      secondaryLabel: "必要时进入运行维护",
      secondaryHref: "/platform",
      recommendedKey: "/backtests",
      signals: [
        {
          label: "失败任务",
          value: `编号 ${latestFailedJob.id}`,
          detail: String(latestFailedJob.request_payload.symbol ?? "未提供标的"),
        },
        {
          label: "失败原因",
          value: latestFailedJob.error_message ? "已记录错误信息" : "需进一步排查",
          detail: latestFailedJob.error_message || "如果回测页里也看不到原因，再进入运行维护页检查服务状态。",
        },
        {
          label: "下一步边界",
          value: "先看回测页，再决定是否排障",
          detail: "只有当错误信息不足、任务长时间卡住或服务明显异常时，才需要进入运行维护页。",
        },
      ],
    };
  }

  if (instrumentCount <= 0) {
    return {
      tone: "attention",
      kicker: "现在最该补的是数据样本",
      title: "先补齐一个熟悉标的的关键周期，再进入回测主流程",
      description: "当前还没有可直接研究的行情覆盖。先准备 1d 或 15m 的最小样本，比直接浏览模板或结果页更有效。",
      primaryLabel: "进入数据准备页",
      primaryHref: "/market-data",
      secondaryLabel: "先看策略模板",
      secondaryHref: "/templates",
      recommendedKey: "/market-data",
      signals: [
        {
          label: "可研究标的",
          value: "0 个",
          detail: "至少准备一个熟悉标的的关键周期，才能形成第一份有效结果。",
        },
        {
          label: "当前阻塞点",
          value: "缺少最小可研究样本",
          detail: "此时不必先看复杂参数，先让主流程能跑通更重要。",
        },
        {
          label: "建议顺序",
          value: "准备数据 -> 运行回测",
          detail: "先补样本，再用默认模板跑一份基线结果。",
        },
      ],
    };
  }

  if (!latestReport) {
    return {
      tone: "ready",
      kicker: "现在最该做的是先跑出第一份结果",
      title: "数据已经具备，下一步直接提交一份基线回测",
      description: "当前已有可研究标的，但还没有生成结果。最有价值的动作不是继续逛页面，而是尽快拿到第一份可复盘样本。",
      primaryLabel: "进入回测页开始提交",
      primaryHref: "/backtests",
      secondaryLabel: "先挑一套模板",
      secondaryHref: "/templates",
      recommendedKey: "/backtests",
      signals: [
        {
          label: "可研究标的",
          value: `${instrumentCount} 个`,
          detail: "当前已经具备进入主流程的基础条件。",
        },
        {
          label: "结果库状态",
          value: "尚无结果",
          detail: "先形成一份基线报告，后续才有对比、复盘和调参依据。",
        },
        {
          label: "建议策略",
          value: "默认模板优先",
          detail: "先跑通，再根据结果决定是否进入模板页改详细设置。",
        },
      ],
    };
  }

  const verdictValue =
    latestReportMetrics.closedTrades === 0
      ? "先查为何没成交"
      : latestReportMetrics.netReturn > 0 && latestReportMetrics.maxDrawdown <= 8
        ? latestReportMetrics.outperformBuyHold
          ? "已值得优先复盘"
          : "先确认是否稳定领先"
        : latestReportMetrics.netReturn > 0
          ? "先判断回撤能否接受"
          : "先作为反向对照";

  return {
    tone: "ready",
    kicker: "现在最该做的是先判断最新结果值不值得继续",
    title: `先看报告编号 ${latestReport.id} 的结论，再决定对比、重跑还是换方向`,
    description: "当前已经有结果样本。下一步不应回到表单重新填，而是先确认收益、回撤、成交情况和是否跑赢买入持有，再决定是否继续投入时间。",
    primaryLabel: "打开最新结果",
    primaryHref: `/reports/${latestReport.id}`,
    secondaryLabel: latestReportGroupCount > 1 ? "打开同标的结果组" : "进入结果库总览",
    secondaryHref:
      latestReportGroupCount > 1
        ? `/reports?keyword=${encodeURIComponent(latestReport.symbol)}&interval=${encodeURIComponent(latestReport.interval)}`
        : "/reports",
    recommendedKey: "/reports",
    signals: [
      {
        label: "单独验证结论",
        value: verdictValue,
        detail: `${latestReport.symbol} / ${latestReport.interval} / ${strategyLabel(latestReport.strategy_kind)}`,
      },
      {
        label: "收益与回撤",
        value: `${latestReportMetrics.netReturn.toFixed(2)}% / ${latestReportMetrics.maxDrawdown.toFixed(2)}%`,
        detail: latestReportMetrics.closedTrades === 0 ? "当前这份结果还没有形成完整成交。" : `共 ${latestReportMetrics.closedTrades} 笔成交。`,
      },
      {
        label: "后续路径",
        value: latestReportGroupCount > 1 ? `同组还有 ${latestReportGroupCount - 1} 份结果` : "先看这一份是否值得扩展",
        detail: latestReportGroupCount > 1 ? "看完结论后可直接切到同标的结果组继续横向比较。" : "如果这份结果不成立，再回到回测页或模板页调整配置。",
      },
    ],
  };
}

export function ConsoleShell({ children }: ConsoleShellProps) {
  const pathname = usePathname();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [snapshot, setSnapshot] = useState<ShellSnapshot>({
    stats: null,
    jobs: [],
    reports: [],
    ready: false,
  });
  const selectedKey = pathname.startsWith("/reports/") ? "/reports" : pathname;
  const current = routeTitles[selectedKey] ?? routeTitles["/"];

  useEffect(() => {
    let cancelled = false;

    async function loadShellSnapshot() {
      try {
        const [statsPayload, jobsPayload, reportsPayload] = await Promise.all([
          apiFetch<MarketDataStats>("/api/market-data/stats"),
          apiFetch<BacktestJob[]>("/api/backtests?limit=12"),
          apiFetch<ReportSummary[]>("/api/reports?limit=12"),
        ]);
        if (cancelled) {
          return;
        }
        setSnapshot({
          stats: statsPayload,
          jobs: jobsPayload,
          reports: reportsPayload,
          ready: true,
        });
      } catch {
        if (cancelled) {
          return;
        }
        setSnapshot((currentSnapshot) => ({ ...currentSnapshot, ready: true }));
      }
    }

    void loadShellSnapshot();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const hasActiveJobs = snapshot.jobs.some((item) => ["queued", "running", "cancel_requested"].includes(item.status));
    if (!hasActiveJobs) {
      return;
    }
    const timer = window.setInterval(async () => {
      try {
        const jobsPayload = await apiFetch<BacktestJob[]>("/api/backtests?limit=12");
        setSnapshot((currentSnapshot) => ({ ...currentSnapshot, jobs: jobsPayload, ready: true }));
      } catch {
        // 保持最近一次成功快照，避免壳层因短暂请求失败抖动。
      }
    }, 4000);
    return () => window.clearInterval(timer);
  }, [snapshot.jobs]);

  const shellGuidance = useMemo(() => buildShellGuidance(snapshot), [snapshot]);
  const shellSummaryItems = useMemo<ShellSummaryItem[]>(() => shellGuidance.signals.slice(0, 3), [shellGuidance.signals]);

  const renderMenu = () => (
    <div className="nav-sections">
      <Typography.Text className="nav-section-title">研究主路径</Typography.Text>
      <Menu mode="inline" selectedKeys={[selectedKey]} items={primaryItems} className="platform-nav" onClick={() => setMobileMenuOpen(false)} />
      <Typography.Text className="nav-section-title">运行检查</Typography.Text>
      <Menu mode="inline" selectedKeys={[selectedKey]} items={supportItems} className="platform-nav" onClick={() => setMobileMenuOpen(false)} />
    </div>
  );

  return (
    <Layout className="platform-shell">
      <Sider width={236} theme="light" className="platform-sider" breakpoint="lg" collapsedWidth="0">
        <div className="platform-sider-inner">
          <div className="platform-side-head">
            <div className="platform-logo">
              <div className="platform-logo-mark">SS</div>
              <div className="platform-logo-text">
                <span className="platform-logo-title">Strategy Studio</span>
                <span className="platform-logo-subtitle">策略研究工作台</span>
              </div>
            </div>
          </div>
          {renderMenu()}
        </div>
      </Sider>
      <Layout className="platform-main">
        <Header className="platform-header">
          <Button className="mobile-menu-trigger" icon={<MenuOutlined />} onClick={() => setMobileMenuOpen(true)} />
          <div className="platform-header-main">
            <div className="platform-header-title">
              <span className="platform-header-kicker">{current.kicker}</span>
              <span className="platform-header-name">{current.title}</span>
            </div>
            <p className="platform-header-copy">
              <strong>{current.tipTitle}</strong>
              <span>{current.tipText}</span>
            </p>
          </div>
        </Header>
        <div className="platform-meta-strip">
          <div className={`shell-banner tone-${shellGuidance.tone}`}>
            <div className="shell-banner-main">
              <div className="shell-banner-copy">
                <span className="research-guidance-kicker">{shellGuidance.kicker}</span>
                <strong>{shellGuidance.title}</strong>
                <p>{shellGuidance.description}</p>
              </div>
            </div>
            <div className="shell-banner-summary" aria-label="当前研究摘要">
              {shellSummaryItems.map((item) => (
                <article key={item.label} className="shell-summary-item">
                  <span>{item.label}</span>
                  <strong>{item.value}</strong>
                  <p>{item.detail}</p>
                </article>
              ))}
            </div>
            <div className="shell-banner-actions-panel">
              <div className="shell-banner-actions-copy">
                <strong>现在先做这一件</strong>
                <p>先按主动作推进；只有主线不成立时，再切到次动作继续判断。</p>
              </div>
              <div className="shell-banner-actions">
                <Button type="primary">
                  <Link href={shellGuidance.primaryHref}>{shellGuidance.primaryLabel}</Link>
                </Button>
                <Button>
                  <Link href={shellGuidance.secondaryHref}>{shellGuidance.secondaryLabel}</Link>
                </Button>
              </div>
            </div>
          </div>
        </div>
        <Content className="platform-content">
          <div className="content-frame">{children}</div>
        </Content>
      </Layout>
      <Drawer
        title="Strategy Studio 工作台"
        placement="left"
        size="default"
        open={mobileMenuOpen}
        onClose={() => setMobileMenuOpen(false)}
        className="mobile-nav-drawer"
      >
        {renderMenu()}
      </Drawer>
    </Layout>
  );
}
