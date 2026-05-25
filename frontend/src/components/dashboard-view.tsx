"use client";

import { Card, Col, Empty, Row, Skeleton, Table, Tag, Typography } from "antd";
import { useEffect, useState } from "react";
import { apiFetch, type BacktestJob, type MarketDataStats, type ReportSummary } from "@/lib/api";

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

  return (
    <div className="page-stack">
      <Typography.Title level={3} className="section-title">
        平台概览
      </Typography.Title>
      <div className="summary-grid">
        <Card size="small">
          <div className="metric-kpi">
            <span>已存标的</span>
            <strong>{stats.instrument_count}</strong>
          </div>
        </Card>
        <Card size="small">
          <div className="metric-kpi">
            <span>K 线总量</span>
            <strong>{stats.total_bars.toLocaleString()}</strong>
          </div>
        </Card>
        <Card size="small">
          <div className="metric-kpi">
            <span>已存周期</span>
            <strong>{stats.by_interval.length}</strong>
          </div>
        </Card>
        <Card size="small">
          <div className="metric-kpi">
            <span>最近同步</span>
            <strong>{stats.recent_sync_runs[0] ? String(stats.recent_sync_runs[0].status) : "暂无"}</strong>
          </div>
        </Card>
      </div>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={12}>
          <Card title="周期分布" size="small">
            <Table
              size="small"
              pagination={false}
              rowKey="interval"
              dataSource={stats.by_interval}
              columns={[
                { title: "周期", dataIndex: "interval" },
                { title: "记录数", dataIndex: "bar_count", render: (value: number) => value.toLocaleString() },
              ]}
            />
          </Card>
        </Col>
        <Col xs={24} xl={12}>
          <Card title="最近同步记录" size="small">
            <Table
              size="small"
              pagination={false}
              rowKey="id"
              dataSource={stats.recent_sync_runs}
              columns={[
                { title: "ID", dataIndex: "id", width: 72 },
                { title: "周期", dataIndex: "interval" },
                {
                  title: "状态",
                  dataIndex: "status",
                  render: (value: string) => <Tag color={value === "succeeded" ? "green" : value === "failed" ? "red" : "blue"}>{value}</Tag>,
                },
                { title: "新增", dataIndex: "bars_inserted" },
                { title: "更新", dataIndex: "bars_updated" },
              ]}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={12}>
          <Card title="最近回测任务" size="small">
            <Table
              size="small"
              pagination={false}
              rowKey="id"
              dataSource={jobs}
              columns={[
                { title: "任务", dataIndex: "id", width: 72 },
                { title: "标的", render: (_, row) => String(row.request_payload.symbol ?? "-") },
                { title: "周期", render: (_, row) => String(row.request_payload.interval ?? "-") },
                { title: "策略", render: (_, row) => String(row.request_payload.strategy_kind ?? "-") },
                {
                  title: "状态",
                  dataIndex: "status",
                  render: (value: string) => <Tag color={value === "succeeded" ? "green" : value === "failed" ? "red" : "blue"}>{value}</Tag>,
                },
              ]}
            />
          </Card>
        </Col>
        <Col xs={24} xl={12}>
          <Card title="最近报告" size="small">
            <Table
              size="small"
              pagination={false}
              rowKey="id"
              dataSource={reports}
              columns={[
                { title: "报告", dataIndex: "id", width: 72 },
                { title: "标的", dataIndex: "symbol" },
                { title: "周期", dataIndex: "interval" },
                { title: "策略", dataIndex: "strategy_kind" },
                {
                  title: "样本外收益",
                  render: (_, row) => {
                    const validation = row.summary_metrics.validation ?? {};
                    return `${Number(validation.NetReturnPct ?? validation.ReturnPct ?? 0).toFixed(2)}%`;
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
