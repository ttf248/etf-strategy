"use client";

import { ArrowRightOutlined, CheckCircleOutlined, DatabaseOutlined, FileSearchOutlined, PlayCircleOutlined } from "@ant-design/icons";
import { Button, Card, Col, Collapse, Empty, Row, Skeleton, Space, Table, Tag, Typography } from "antd";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { apiFetch, type BacktestJob, type MarketDataStats, type ReportSummary } from "@/lib/api";
import { FormatPercent, MetricCard, PageHeader, StatusTag } from "@/components/platform-ui";
import { strategyLabel } from "@/lib/strategy-template-config";
import { buildBacktestLaunchHref, buildBacktestPresetHref, buildBeginnerPresets } from "@/lib/beginner-presets";

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
      title: "这次结果值不值得继续看",
      value: netReturn > 0 ? "先继续看" : "先别急着采用",
      description:
        netReturn > 0
          ? `样本外收益 ${netReturn.toFixed(2)}%，说明这套组合至少在这段测试区间里跑出了正收益。`
          : `样本外收益 ${netReturn.toFixed(2)}%，先不要直接采用，优先对比别的模板或周期。`,
    },
    {
      title: "中途波动大不大",
      value: maxDrawdown <= 8 ? "回撤较可控" : maxDrawdown <= 15 ? "回撤中等" : "回撤偏大",
      description:
        maxDrawdown <= 8
          ? `最大回撤 ${maxDrawdown.toFixed(2)}%，对第一次复盘来说更容易接受。`
          : `最大回撤 ${maxDrawdown.toFixed(2)}%，继续使用前要重点看自己是否接受这种波动。`,
    },
    {
      title: "接下来怎么做",
      value: closedTrades === 0 ? "换标的或周期" : netReturn > 0 ? "拿去做对比" : "换参数重跑",
      description:
        closedTrades === 0
          ? "这次没有形成有效成交，优先换一个更活跃的标的或周期。"
          : netReturn > 0
            ? "先打开报告详情，再去对比区和同标的其他结果放在一起看。"
            : "先保留这份结果，再用同一路径换模板或换周期重跑一轮。",
    },
  ];
}

function buildStartRecommendation(params: {
  instrumentCount: number;
  reportCount: number;
  presetCount: number;
  latestSucceededReportId: number | null;
  rerunHref: string | null;
}) {
  if (params.latestSucceededReportId && params.rerunHref) {
    return {
      title: "你已经跑通过一次了，先沿着成功路径继续",
      description: "最省力的做法不是重新填一遍，而是先打开上次成功报告，确认结果含义后，再按同一路径重跑一轮做对比。",
      primaryLabel: "打开最近成功报告",
      primaryHref: `/reports/${params.latestSucceededReportId}`,
      secondaryLabel: "按相同配置再跑一次",
      secondaryHref: params.rerunHref,
    };
  }
  if (params.presetCount > 0) {
    return {
      title: "先用现成示例跑通第一轮",
      description: "你已经有适合首跑的标的和周期，不需要先研究全部功能。直接用示例进入创建回测页最省时间。",
      primaryLabel: "看示例标的",
      primaryHref: "#beginner-presets",
      secondaryLabel: "直接去创建回测",
      secondaryHref: "/backtests",
    };
  }
  if (params.instrumentCount > 0) {
    return {
      title: "先检查一个你熟悉的标的",
      description: "库里已经有数据，但还没形成现成示例。先去数据准备页检查 1d 或 15m 是否齐全，再决定回测。",
      primaryLabel: "去检查数据",
      primaryHref: "/market-data",
      secondaryLabel: "直接去创建回测",
      secondaryHref: "/backtests",
    };
  }
  return {
    title: "先准备一个可以回测的标的",
    description: "当前还没有可直接首跑的数据。先去数据准备页补一个熟悉标的的 1d 或 15m，再回到首页开始。",
    primaryLabel: "去准备数据",
    primaryHref: "/market-data",
    secondaryLabel: "查看模板",
    secondaryHref: "/templates",
  };
}

export function DashboardView() {
  const [stats, setStats] = useState<MarketDataStats | null>(null);
  const [jobs, setJobs] = useState<BacktestJob[]>([]);
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const beginnerPresets = useMemo(() => (stats ? buildBeginnerPresets(stats.coverages) : []), [stats]);

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const [statsPayload, jobsPayload, reportsPayload] = await Promise.all([
          apiFetch<MarketDataStats>("/api/market-data/stats"),
          apiFetch<BacktestJob[]>("/api/backtests?limit=8"),
          apiFetch<ReportSummary[]>("/api/reports?limit=8"),
        ]);
        setStats(statsPayload);
        setJobs(jobsPayload);
        setReports(reportsPayload);
      } finally {
        setLoading(false);
      }
    }

    void load();
  }, []);

  if (loading && !stats) {
    return <Skeleton active paragraph={{ rows: 8 }} />;
  }

  if (!stats) {
    return <Empty description="暂时无法读取平台数据" />;
  }

  const latestSync = stats.recent_sync_runs[0] as { status?: string; interval?: string; completed_at?: string } | undefined;
  const succeededJobs = jobs.filter((item) => item.status === "succeeded").length;
  const failedJobs = jobs.filter((item) => item.status === "failed").length;
  const latestSyncStatus = latestSync?.status === "completed" ? "已完成" : latestSync?.status === "failed" ? "失败" : latestSync?.status ?? "暂无";
  const latestSucceededJob = jobs.find((item) => item.status === "succeeded") ?? null;
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
      })
    : null;
  const startRecommendation = buildStartRecommendation({
    instrumentCount: stats.instrument_count,
    reportCount: reports.length,
    presetCount: beginnerPresets.length,
    latestSucceededReportId,
    rerunHref: latestSucceededRerunHref,
  });

  return (
    <div className="page-stack">
      <section className="hero-panel beginner-hero">
        <div className="beginner-hero-copy">
          <PageHeader
            eyebrow="Backtest Lab"
            title="从一个标的开始，跑出第一份回测报告"
            description="不用先理解数据库、Worker 或调度器。选择标的、套用策略模板、提交回测，然后在报告里看收益、回撤和交易记录。"
          />
          <Space wrap className="hero-actions">
            <Button type="primary" size="large" icon={<PlayCircleOutlined />}>
              <Link href="/backtests">开始一次回测</Link>
            </Button>
            <Button size="large" icon={<FileSearchOutlined />}>
              <Link href="/reports">查看历史报告</Link>
            </Button>
          </Space>
        </div>
        <div className="readiness-card">
          <span className="readiness-label">当前准备情况</span>
          <strong>{stats.instrument_count > 0 ? "可以开始" : "需要先准备数据"}</strong>
          <span>{stats.instrument_count.toLocaleString()} 个标的，{stats.total_bars.toLocaleString()} 条 K 线</span>
        </div>
      </section>

      <Card size="small" className="section-card start-path-card">
        <div className="start-path-main">
          <strong>{startRecommendation.title}</strong>
          <p>{startRecommendation.description}</p>
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

      <Row gutter={[16, 16]}>
        <Col xs={24} md={8}>
          <Card className="action-card" size="small">
            <div className="action-card-icon"><PlayCircleOutlined /></div>
            <Typography.Title level={4}>1. 创建回测</Typography.Title>
            <p>输入 Yahoo 标的代码，选择一个默认策略模板，先跑通完整流程。</p>
            <Button type="link">
              <Link href="/backtests">去创建 <ArrowRightOutlined /></Link>
            </Button>
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card className="action-card" size="small">
            <div className="action-card-icon"><FileSearchOutlined /></div>
            <Typography.Title level={4}>2. 阅读结果</Typography.Title>
            <p>优先看样本外收益、最大回撤、净值曲线和交易记录。</p>
            <Button type="link">
              <Link href="/reports">看报告 <ArrowRightOutlined /></Link>
            </Button>
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card className="action-card" size="small">
            <div className="action-card-icon"><DatabaseOutlined /></div>
            <Typography.Title level={4}>3. 准备数据</Typography.Title>
            <p>如果标的不存在或数据不够，再进入数据准备页同步行情。</p>
            <Button type="link">
              <Link href="/market-data">检查数据 <ArrowRightOutlined /></Link>
            </Button>
          </Card>
        </Col>
      </Row>

      <Card id="beginner-presets" title="现成示例标的" size="small" className="section-card">
        {beginnerPresets.length === 0 ? (
          <Typography.Text type="secondary">当前还没有适合直接试跑的示例标的，先到数据准备页补 15m 或 1d 数据。</Typography.Text>
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
                <Button type="primary">
                  <Link href={buildBacktestPresetHref(preset)}>用这个示例开始</Link>
                </Button>
              </article>
            ))}
          </div>
        )}
      </Card>

      <Card title="最近一次成功路径" size="small" className="section-card">
        {!latestSucceededJob || !latestSucceededPayload ? (
          <Typography.Text type="secondary">还没有成功跑通的回测任务。先用上面的示例标的完成第一次回测，之后这里会保留可复用入口。</Typography.Text>
        ) : (
          <div className="recent-success-card">
            <div className="recent-success-head">
              <div>
                <strong>任务 #{latestSucceededJob.id} 已成功完成</strong>
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
            <p>如果这次结果值得继续看，先打开报告；如果只是想再换参数或重跑同一路径，可以直接按原标的和周期重新带入创建页。</p>
            <div className="recent-success-actions">
              {latestSucceededReportId ? (
                <Button type="primary">
                  <Link href={`/reports/${latestSucceededReportId}`}>打开这份报告</Link>
                </Button>
              ) : (
                <Button type="primary">
                  <Link href="/reports">去报告列表查找</Link>
                </Button>
              )}
              <Button>
                <Link href={latestSucceededRerunHref ?? "/backtests"}>
                  按相同配置再跑一次
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
        <MetricCard label="最近数据同步" value={latestSyncStatus} note={latestSync?.completed_at ?? latestSync?.interval ?? "等待同步记录"} />
      </div>

      <Card title="最近生成的报告" size="small" className="section-card">
        {reports.length === 0 ? (
          <Empty description="暂无报告，先创建一次回测。" />
        ) : (
          <div className="home-report-list">
            {reports.slice(0, 4).map((report) => {
              const validation = report.summary_metrics.validation ?? {};
              const { netReturn, maxDrawdown } = getValidationMetrics(report);
              const brief =
                netReturn > 0 && maxDrawdown <= 8
                  ? "这份结果更稳，适合先打开看看为什么能赚钱。"
                  : netReturn > 0
                    ? "这份结果虽然赚钱，但要先看回撤自己是否能接受。"
                    : "这份结果不理想，适合拿来和别的模板或周期做反面对比。";
              return (
                <article key={report.id} className="home-report-card">
                  <div className="home-report-card-head">
                    <div>
                      <strong>#{report.id} {report.symbol}</strong>
                      <span>{report.name || "未命名标的"} / {report.interval} / {strategyLabel(report.strategy_kind)}</span>
                    </div>
                    <Tag>{report.dataset_end}</Tag>
                  </div>
                  <div className="home-report-metrics">
                    <span>样本外收益 <FormatPercent value={validation.NetReturnPct ?? validation.ReturnPct ?? 0} /></span>
                    <span>最大回撤 {Number(validation.MaxDrawdownPct ?? 0).toFixed(2)}%</span>
                  </div>
                  <p className="home-report-brief">{brief}</p>
                  <Button type="primary">
                    <Link href={`/reports/${report.id}`}>打开报告</Link>
                  </Button>
                </article>
              );
            })}
          </div>
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
                        { title: "ID", dataIndex: "id", width: 72 },
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
            label: `高级运行明细：最近回测任务（成功 ${succeededJobs} / 失败 ${failedJobs}）`,
            children: (
              <Card
                title="最近运行的回测"
                size="small"
                className="section-card"
                extra={<span className="toolbar-count"><CheckCircleOutlined /> 成功 {succeededJobs} / 失败 {failedJobs}</span>}
              >
                <Table
                  size="small"
                  pagination={false}
                  rowKey="id"
                  dataSource={jobs}
                  columns={[
                    { title: "任务", dataIndex: "id", width: 72 },
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
