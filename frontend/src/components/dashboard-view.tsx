"use client";

import { ArrowRightOutlined, CheckCircleOutlined, DatabaseOutlined, FileSearchOutlined, PlayCircleOutlined } from "@ant-design/icons";
import { Button, Card, Col, Collapse, Empty, Row, Skeleton, Space, Table, Tag, Typography } from "antd";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { apiFetch, type BacktestJob, type MarketDataStats, type ReportSummary } from "@/lib/api";
import { FormatPercent, MetricCard, PageHeader, StatusTag } from "@/components/platform-ui";
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
      guideItems: [
        {
          title: "为什么现在推荐这一步",
          value: "因为你已经有一条成功路径",
          description: "最近成功任务和报告都已存在，继续沿着它复盘或重跑，比重新从空白表单开始更省时间。",
        },
        {
          title: "为什么不是先看别的页面",
          value: "因为你先缺的是复盘判断",
          description: "先确认上次收益、回撤和交易是否值得继续，再决定去对比、换参数还是换标的。",
        },
      ] satisfies GuideCard[],
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
      guideItems: [
        {
          title: "为什么现在推荐这一步",
          value: "因为你已经有现成首跑组合",
          description: "首页已经找到了同时适合新手和当前数据条件的示例标的，不需要先研究全部功能。",
        },
        {
          title: "为什么不是先补更多数据",
          value: "因为先跑通一次更重要",
          description: "先完成一次提交和读报告，比先补齐一大堆标的更能帮助你理解平台主路径。",
        },
      ] satisfies GuideCard[],
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
      guideItems: [
        {
          title: "为什么现在推荐这一步",
          value: "因为库里有数据，但还没形成现成示例",
          description: "最值得先确认的是你熟悉的标的有没有 1d 或 15m，而不是先看更多模板或报告。",
        },
        {
          title: "为什么不是直接提交",
          value: "因为先确认周期是否齐全更稳妥",
          description: "确认好可用周期后再去创建回测，可以减少第一次提交就因为数据不足而失败的概率。",
        },
      ] satisfies GuideCard[],
    };
  }
  return {
    title: "先准备一个可以回测的标的",
    description: "当前还没有可直接首跑的数据。先去数据准备页补一个熟悉标的的 1d 或 15m，再回到首页开始。",
    primaryLabel: "去准备数据",
    primaryHref: "/market-data",
    secondaryLabel: "查看模板",
    secondaryHref: "/templates",
    guideItems: [
      {
        title: "为什么现在推荐这一步",
        value: "因为还缺可直接回测的数据",
        description: "没有数据时，先看模板或报告都无法真正开始，先补一个熟悉标的最直接。",
      },
      {
        title: "为什么只补一个标的就够",
        value: "因为先跑通主路径比全量建库更重要",
        description: "第一次只需要 1d 或 15m 的一个可用标的，等你确认流程顺畅后再扩展更多数据。",
      },
    ] satisfies GuideCard[],
  };
}

function buildPresetGuides(preset: BeginnerPreset): GuideCard[] {
  const readyForShortCycle = preset.availableIntervals.includes("15m");
  const readyForLongCycle = preset.availableIntervals.includes("1d");
  return [
    {
      title: "为什么优先推荐它",
      value: readyForShortCycle && readyForLongCycle ? "短线和长线都能起步" : readyForShortCycle ? "分钟回测可直接开始" : "日线回测更容易上手",
      description: preset.reason,
    },
    {
      title: "更适合怎么用",
      value: readyForShortCycle ? `先用 ${strategyLabel(preset.strategyKind)} 跑一轮` : "先看长期或日线节奏",
      description:
        readyForShortCycle
          ? "这类示例更适合先把创建回测、提交任务和读报告的完整主路径跑通。"
          : "这类示例更适合先看长期收益和回撤，再决定要不要扩到分钟策略。",
    },
  ];
}

function buildHomeReportSpotlight(report: ReportSummary, latestSucceededReportId: number | null): { label: string; color: string; description: string } {
  const { netReturn, maxDrawdown, closedTrades } = getValidationMetrics(report);
  if (report.id === latestSucceededReportId) {
    return {
      label: "刚跑通的成功样本",
      color: "blue",
      description: "这份报告和最近一次成功路径直接对应，最适合先确认你刚跑通的结果到底值不值得继续。",
    };
  }
  if (closedTrades === 0) {
    return {
      label: "先查为什么没成交",
      color: "default",
      description: "这份结果更适合用来判断是标的不活跃、周期不合适，还是模板条件太苛刻。",
    };
  }
  if (netReturn > 0 && maxDrawdown <= 8) {
    return {
      label: "适合先看",
      color: "green",
      description: "它既赚钱又相对稳，更适合作为首页第一批先读的参考样本。",
    };
  }
  if (netReturn > 0) {
    return {
      label: "重点看波动",
      color: "gold",
      description: "它能赚钱，但更需要确认回撤和净值波动是不是你能接受的节奏。",
    };
  }
  return {
    label: "适合做反面对照",
    color: "red",
    description: "这份结果更像对照组，适合帮助你判断哪些模板、参数或周期该优先排除。",
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
    presetCount: beginnerPresets.length,
    latestSucceededReportId,
    rerunHref: latestSucceededRerunHref,
  });
  const spotlightReports = [...reports]
    .sort((left, right) => {
      const leftSpotlight = buildHomeReportSpotlight(left, latestSucceededReportId);
      const rightSpotlight = buildHomeReportSpotlight(right, latestSucceededReportId);
      const leftPriority =
        leftSpotlight.label === "刚跑通的成功样本" ? 4 :
        leftSpotlight.label === "适合先看" ? 3 :
        leftSpotlight.label === "重点看波动" ? 2 :
        leftSpotlight.label === "适合做反面对照" ? 1 : 0;
      const rightPriority =
        rightSpotlight.label === "刚跑通的成功样本" ? 4 :
        rightSpotlight.label === "适合先看" ? 3 :
        rightSpotlight.label === "重点看波动" ? 2 :
        rightSpotlight.label === "适合做反面对照" ? 1 : 0;
      if (leftPriority !== rightPriority) {
        return rightPriority - leftPriority;
      }
      return right.id - left.id;
    })
    .slice(0, 4);

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

      <Card title="现在更适合先看的报告" size="small" className="section-card">
        {reports.length === 0 ? (
          <Empty description="暂无报告，先创建一次回测。" />
        ) : (
          <>
            <div className="home-report-banner">
              <strong>这些卡片不是只按时间堆出来，而是按“更值得先读”排序</strong>
              <p>首页优先把刚跑通的成功样本、收益更稳的结果，以及适合当反面对照的报告放在前面，帮助你先决定先读哪一份，而不是自己盲猜。</p>
            </div>
            <div className="home-report-list">
              {spotlightReports.map((report) => {
              const validation = report.summary_metrics.validation ?? {};
              const { netReturn, maxDrawdown } = getValidationMetrics(report);
              const spotlight = buildHomeReportSpotlight(report, latestSucceededReportId);
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
                    <div className="home-report-card-tags">
                      <Tag color={spotlight.color}>{spotlight.label}</Tag>
                      <Tag>{report.dataset_end}</Tag>
                    </div>
                  </div>
                  <div className="home-report-metrics">
                    <span>样本外收益 <FormatPercent value={validation.NetReturnPct ?? validation.ReturnPct ?? 0} /></span>
                    <span>最大回撤 {Number(validation.MaxDrawdownPct ?? 0).toFixed(2)}%</span>
                  </div>
                  <div className="home-report-spotlight">
                    <strong>为什么现在先看它</strong>
                    <p>{spotlight.description}</p>
                  </div>
                  <p className="home-report-brief">{brief}</p>
                  <Button type="primary">
                    <Link href={`/reports/${report.id}`}>打开报告</Link>
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
