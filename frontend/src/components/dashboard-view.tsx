"use client";

import { ArrowRightOutlined, CheckCircleOutlined, DatabaseOutlined, FileSearchOutlined, PlayCircleOutlined } from "@ant-design/icons";
import { Button, Card, Col, Collapse, Empty, Row, Skeleton, Space, Table, Tag, Typography } from "antd";
import Link from "next/link";
import { useEffect, useState } from "react";
import { apiFetch, type BacktestJob, type MarketDataStats, type ReportSummary } from "@/lib/api";
import { FormatPercent, MetricCard, PageHeader, StatusTag } from "@/components/platform-ui";
import { strategyLabel } from "@/lib/strategy-template-config";

export function DashboardView() {
  const [stats, setStats] = useState<MarketDataStats | null>(null);
  const [jobs, setJobs] = useState<BacktestJob[]>([]);
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [loading, setLoading] = useState(true);

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
