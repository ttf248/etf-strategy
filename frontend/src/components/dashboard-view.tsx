"use client";

import { Card, Col, Empty, Row, Skeleton, Table } from "antd";
import { useEffect, useState } from "react";
import { apiFetch, type BacktestJob, type MarketDataStats, type ReportSummary } from "@/lib/api";
import { FormatPercent, MetricCard, PageHeader, StatusTag } from "@/components/platform-ui";

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

  const latestSync = stats.recent_sync_runs[0] as { status?: string; interval?: string } | undefined;
  const succeededJobs = jobs.filter((item) => item.status === "succeeded").length;
  const failedJobs = jobs.filter((item) => item.status === "failed").length;

  return (
    <div className="page-stack">
      <section className="hero-panel">
        <PageHeader
          eyebrow="Platform Overview"
          title="ETF 策略研究控制台"
          description="集中管理行情入库、策略参数模板、异步回测任务和结构化报告，适合持续复盘与批量研究。"
        />
        <div className="summary-grid" style={{ marginTop: 20 }}>
          <MetricCard label="已存标的" value={stats.instrument_count} note="PostgreSQL instruments" />
          <MetricCard label="K 线总量" value={stats.total_bars.toLocaleString()} note="price_bars" />
          <MetricCard label="已存周期" value={stats.by_interval.length} note={stats.by_interval.map((item) => item.interval).join(" / ") || "-"} />
          <MetricCard label="最近同步" value={latestSync?.status ?? "暂无"} note={latestSync?.interval ?? "等待同步记录"} />
        </div>
      </section>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={10}>
          <Card title="周期分布" size="small" className="section-card">
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
          <Card title="最近同步" size="small" className="section-card">
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

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={12}>
          <Card
            title="最近回测任务"
            size="small"
            className="section-card"
            extra={<span className="toolbar-count">成功 {succeededJobs} / 失败 {failedJobs}</span>}
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
                { title: "策略", render: (_, row) => String(row.request_payload.strategy_kind ?? "-"), ellipsis: true },
                { title: "状态", dataIndex: "status", render: (value: string) => <StatusTag value={value} /> },
              ]}
            />
          </Card>
        </Col>
        <Col xs={24} xl={12}>
          <Card title="最近报告" size="small" className="section-card">
            <Table
              size="small"
              pagination={false}
              rowKey="id"
              dataSource={reports}
              columns={[
                { title: "报告", dataIndex: "id", width: 72 },
                { title: "标的", dataIndex: "symbol", width: 110 },
                { title: "周期", dataIndex: "interval", width: 80 },
                { title: "策略", dataIndex: "strategy_kind", ellipsis: true },
                {
                  title: "样本外收益",
                  width: 120,
                  render: (_, row) => {
                    const validation = row.summary_metrics.validation ?? {};
                    return <FormatPercent value={validation.NetReturnPct ?? validation.ReturnPct ?? 0} />;
                  },
                },
              ]}
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
}
