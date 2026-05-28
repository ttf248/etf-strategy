"use client";

import {
  BarChartOutlined,
  DatabaseOutlined,
  FileSearchOutlined,
  FundOutlined,
  FormOutlined,
  MenuOutlined,
  MonitorOutlined,
  SettingOutlined,
} from "@ant-design/icons";
import { Button, Drawer, Layout, Menu, Tag, Typography } from "antd";
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

type WorkflowStep = {
  key: string;
  href: string;
  title: string;
  summary: string;
  detail: string;
  status: "ready" | "active" | "waiting";
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

function buildShellStatusLabel(snapshot: ShellSnapshot): { title: string; description: string } {
  if (!snapshot.ready) {
    return {
      title: "正在读取当前研究状态",
      description: "稍后会显示数据覆盖、运行中任务和最近结果入口。",
    };
  }

  const runningJobs = snapshot.jobs.filter((item) => item.status === "running");
  const queuedJobs = snapshot.jobs.filter((item) => item.status === "queued");
  const latestReport = snapshot.reports[0] ?? null;

  if (runningJobs.length > 0) {
    const latestRunning = runningJobs[0];
    const stage = latestRunning.runtime_details.stage_label ?? "执行中";
    return {
      title: `有 ${runningJobs.length} 个任务正在推进`,
      description: `最新任务 #${latestRunning.id} 当前阶段为“${stage}”，预计还需 ${formatDuration(latestRunning.runtime_details.eta_seconds)}。`,
    };
  }
  if (queuedJobs.length > 0) {
    return {
      title: `有 ${queuedJobs.length} 个任务等待执行`,
      description: "队列中已有待执行任务，通常无需重复提交相同配置。",
    };
  }
  if (latestReport) {
    return {
      title: "已有结果可直接复盘",
      description: `最近结果来自 ${latestReport.symbol} / ${latestReport.interval} / ${strategyLabel(latestReport.strategy_kind)}。`,
    };
  }
  if ((snapshot.stats?.instrument_count ?? 0) > 0) {
    return {
      title: "数据已具备，可直接进入回测主流程",
      description: "建议先基于默认模板提交一份基线任务，再回到结果页判断结论。",
    };
  }
  return {
    title: "当前仍需先补齐数据覆盖",
    description: "至少准备一个熟悉标的的 1d 或 15m，才能进入完整回测流程。",
  };
}

function buildWorkflowSteps(snapshot: ShellSnapshot): WorkflowStep[] {
  const instrumentCount = snapshot.stats?.instrument_count ?? 0;
  const totalBars = snapshot.stats?.total_bars ?? 0;
  const activeTemplateHint = snapshot.ready
    ? "优先选默认模板，只有默认不匹配时再改详细参数。"
    : "读取模板入口中。";
  const runningJobs = snapshot.jobs.filter((item) => item.status === "running");
  const queuedJobs = snapshot.jobs.filter((item) => item.status === "queued");
  const latestReport = snapshot.reports[0] ?? null;
  const latestRunning = runningJobs[0] ?? queuedJobs[0] ?? null;

  return [
    {
      key: "/market-data",
      href: "/market-data",
      title: "准备数据",
      summary: instrumentCount > 0 ? `${instrumentCount} 个标的可研究` : "尚未形成可研究样本",
      detail:
        instrumentCount > 0
          ? `当前共 ${totalBars.toLocaleString()} 条 K 线，先确认目标标的具备 1d 或 15m。`
          : "先补齐至少一个熟悉标的的关键周期，避免后续回测因覆盖不足失败。",
      status: instrumentCount > 0 ? "ready" : "waiting",
    },
    {
      key: "/templates",
      href: "/templates",
      title: "选择模板",
      summary: snapshot.ready ? "默认模板优先" : "正在读取模板建议",
      detail: activeTemplateHint,
      status: instrumentCount > 0 ? "ready" : "waiting",
    },
    {
      key: "/backtests",
      href: "/backtests",
      title: "运行回测",
      summary:
        latestRunning && latestRunning.status === "running"
          ? `任务 #${latestRunning.id} 进行中`
          : queuedJobs.length > 0
            ? `${queuedJobs.length} 个任务排队中`
            : "可直接发起新任务",
      detail:
        latestRunning && latestRunning.status === "running"
          ? `${latestRunning.runtime_details.stage_label ?? "执行中"}，预计还需 ${formatDuration(latestRunning.runtime_details.eta_seconds)}。`
          : queuedJobs.length > 0
            ? "已有任务等待 worker 执行，通常无需重复提交同一套配置。"
            : "提交后会实时看到阶段、进度、ETA 和资源占用摘要。",
      status: latestRunning ? "active" : instrumentCount > 0 ? "ready" : "waiting",
    },
    {
      key: "/reports",
      href: "/reports",
      title: "结果复盘",
      summary: latestReport ? `最近结果 #${latestReport.id}` : "尚无结果可复盘",
      detail: latestReport
        ? `${latestReport.symbol} / ${latestReport.interval} / ${strategyLabel(latestReport.strategy_kind)}，建议先判断收益和回撤结论。`
        : "当第一份结果生成后，这里会成为默认的下一步入口。",
      status: latestReport ? "active" : "waiting",
    },
  ];
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

  const workflowSteps = useMemo(() => buildWorkflowSteps(snapshot), [snapshot]);
  const shellStatus = useMemo(() => buildShellStatusLabel(snapshot), [snapshot]);
  const runningJobs = useMemo(() => snapshot.jobs.filter((item) => item.status === "running"), [snapshot.jobs]);
  const queuedJobs = useMemo(() => snapshot.jobs.filter((item) => item.status === "queued"), [snapshot.jobs]);
  const failedJobs = useMemo(() => snapshot.jobs.filter((item) => item.status === "failed"), [snapshot.jobs]);
  const latestRunningJob = useMemo(() => runningJobs[0] ?? queuedJobs[0] ?? null, [queuedJobs, runningJobs]);
  const latestReport = snapshot.reports[0] ?? null;
  const instrumentCount = snapshot.stats?.instrument_count ?? 0;

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
      <Sider width={292} theme="light" className="platform-sider" breakpoint="lg" collapsedWidth="0">
        <div className="platform-side-head">
          <div className="platform-logo">
            <div className="platform-logo-mark">SS</div>
            <div className="platform-logo-text">
              <span className="platform-logo-title">Strategy Studio</span>
              <span className="platform-logo-subtitle">策略研究工作台</span>
            </div>
          </div>
          <div className="nav-workbench-card">
            <span className="nav-workbench-label">当前研究状态</span>
            <strong>{shellStatus.title}</strong>
            <p>{shellStatus.description}</p>
            <div className="nav-workbench-pills">
              <span>可研究标的 {instrumentCount}</span>
              <span>运行中 {runningJobs.length}</span>
              <span>排队 {queuedJobs.length}</span>
              <span>失败 {failedJobs.length}</span>
            </div>
          </div>
          <div className="workflow-rail">
            <div className="workflow-rail-head">
              <strong>标准研究路径</strong>
              <span>不需要记忆入口，按这条顺序推进即可。</span>
            </div>
            <div className="workflow-rail-list">
              {workflowSteps.map((step, index) => {
                const isCurrent = selectedKey === step.key;
                return (
                  <Link
                    key={step.key}
                    href={step.href}
                    className={`workflow-rail-item status-${step.status}${isCurrent ? " is-current" : ""}`}
                    onClick={() => setMobileMenuOpen(false)}
                  >
                    <div className="workflow-rail-index">{index + 1}</div>
                    <div className="workflow-rail-body">
                      <div className="workflow-rail-title-row">
                        <strong>{step.title}</strong>
                        <span className={`workflow-badge status-${step.status}`}>
                          {step.status === "active" ? "当前重点" : step.status === "ready" ? "可直接进入" : "待准备"}
                        </span>
                      </div>
                      <span className="workflow-rail-summary">{step.summary}</span>
                      <p>{step.detail}</p>
                    </div>
                  </Link>
                );
              })}
            </div>
          </div>
        </div>
        {renderMenu()}
      </Sider>
      <Layout className="platform-main">
        <Header className="platform-header">
          <Button className="mobile-menu-trigger" icon={<MenuOutlined />} onClick={() => setMobileMenuOpen(true)} />
          <div className="platform-header-title">
            <span className="platform-header-kicker">{current.kicker}</span>
            <span className="platform-header-name">{current.title}</span>
          </div>
          <div className="platform-header-guide">
            <strong>{current.tipTitle}</strong>
            <span>{current.tipText}</span>
          </div>
          <div className="header-quick-strip">
            {latestRunningJob ? (
              <Link href="/backtests" className="header-quick-card">
                <div className="header-quick-icon">
                  <BarChartOutlined />
                </div>
                <div className="header-quick-body">
                  <strong>
                    {latestRunningJob.status === "running" ? `任务 #${latestRunningJob.id} 执行中` : `任务 #${latestRunningJob.id} 排队中`}
                  </strong>
                  <span>
                    {latestRunningJob.status === "running"
                      ? `${latestRunningJob.runtime_details.stage_label ?? "执行中"} · 预计还需 ${formatDuration(latestRunningJob.runtime_details.eta_seconds)}`
                      : latestRunningJob.runtime_details.queue_position
                        ? `队列第 ${latestRunningJob.runtime_details.queue_position} 位`
                        : "等待 worker 领取"}
                  </span>
                </div>
              </Link>
            ) : null}
            {latestReport ? (
              <Link href={`/reports/${latestReport.id}`} className="header-quick-card">
                <div className="header-quick-icon">
                  <FileSearchOutlined />
                </div>
                <div className="header-quick-body">
                  <strong>打开最新结果</strong>
                  <span>{latestReport.symbol} / {latestReport.interval} / {strategyLabel(latestReport.strategy_kind)}</span>
                </div>
              </Link>
            ) : (
              <Link href={instrumentCount > 0 ? "/backtests" : "/market-data"} className="header-quick-card">
                <div className="header-quick-icon">
                  {instrumentCount > 0 ? <FormOutlined /> : <DatabaseOutlined />}
                </div>
                <div className="header-quick-body">
                  <strong>{instrumentCount > 0 ? "进入回测主流程" : "先补齐一个研究样本"}</strong>
                  <span>{instrumentCount > 0 ? "已有数据覆盖，建议直接提交基线任务。" : "优先准备一个熟悉标的的 1d 或 15m。"} </span>
                </div>
              </Link>
            )}
          </div>
        </Header>
        <div className="platform-meta-strip">
          <Tag color={instrumentCount > 0 ? "green" : "default"}>{instrumentCount > 0 ? `数据已就绪 ${instrumentCount} 个标的` : "数据待补齐"}</Tag>
          <Tag color={runningJobs.length > 0 ? "blue" : "default"}>{runningJobs.length > 0 ? `执行中 ${runningJobs.length}` : "当前无运行中任务"}</Tag>
          <Tag color={queuedJobs.length > 0 ? "gold" : "default"}>{queuedJobs.length > 0 ? `排队 ${queuedJobs.length}` : "当前无排队任务"}</Tag>
          <Tag color={latestReport ? "green" : "default"}>{latestReport ? `最近结果 #${latestReport.id}` : "尚无结果"}</Tag>
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
        <div className="mobile-shell-summary">
          <strong>{shellStatus.title}</strong>
          <p>{shellStatus.description}</p>
        </div>
        <div className="workflow-rail mobile-workflow-rail">
          <div className="workflow-rail-list">
            {workflowSteps.map((step, index) => (
              <Link
                key={step.key}
                href={step.href}
                className={`workflow-rail-item status-${step.status}${selectedKey === step.key ? " is-current" : ""}`}
                onClick={() => setMobileMenuOpen(false)}
              >
                <div className="workflow-rail-index">{index + 1}</div>
                <div className="workflow-rail-body">
                  <div className="workflow-rail-title-row">
                    <strong>{step.title}</strong>
                    <span className={`workflow-badge status-${step.status}`}>
                      {step.status === "active" ? "当前重点" : step.status === "ready" ? "可直接进入" : "待准备"}
                    </span>
                  </div>
                  <span className="workflow-rail-summary">{step.summary}</span>
                </div>
              </Link>
            ))}
          </div>
        </div>
        {renderMenu()}
      </Drawer>
    </Layout>
  );
}
