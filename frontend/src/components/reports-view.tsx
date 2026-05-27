"use client";

import { Button, Card, Empty, Input, Select, Space, Table, Tag, Typography } from "antd";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { apiFetch, type ReportSummary } from "@/lib/api";
import { FormatPercent, MetricCard, PageHeader, ToolbarCount } from "@/components/platform-ui";

type Verdict = {
  label: string;
  color: string;
  description: string;
};

function getValidationMetrics(report: ReportSummary) {
  const validation = report.summary_metrics.validation ?? {};
  const netReturn = Number(validation.NetReturnPct ?? validation.ReturnPct ?? 0);
  const maxDrawdown = Number(validation.MaxDrawdownPct ?? 0);
  const closedTrades = Number(validation.ClosedTrades ?? 0);
  return { netReturn, maxDrawdown, closedTrades };
}

function buildVerdict(netReturn: number, maxDrawdown: number): Verdict {
  if (netReturn > 0 && maxDrawdown <= 8) {
    return { label: "表现较稳", color: "green", description: "样本外收益为正，回撤压力相对可控。" };
  }
  if (netReturn > 0) {
    return { label: "有收益但波动大", color: "gold", description: "收益为正，但需要重点检查回撤。" };
  }
  if (netReturn === 0) {
    return { label: "没有触发交易", color: "default", description: "样本外阶段可能没有满足开仓条件。" };
  }
  return { label: "暂不理想", color: "red", description: "样本外收益为负，建议换参数或换标的。" };
}

export function ReportsView() {
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [keyword, setKeyword] = useState("");
  const [interval, setInterval] = useState<string | undefined>(undefined);

  useEffect(() => {
    void apiFetch<ReportSummary[]>("/api/reports?limit=200").then(setReports);
  }, []);

  const intervalOptions = useMemo(
    () => Array.from(new Set(reports.map((item) => item.interval))).map((item) => ({ label: item, value: item })),
    [reports],
  );

  const filteredReports = useMemo(() => {
    return reports.filter((item) => {
      const matchesKeyword =
        !keyword ||
        item.symbol.toLowerCase().includes(keyword.toLowerCase()) ||
        item.name.toLowerCase().includes(keyword.toLowerCase());
      const matchesInterval = !interval || item.interval === interval;
      return matchesKeyword && matchesInterval;
    });
  }, [reports, keyword, interval]);

  const latestReport = filteredReports[0];
  const positiveReports = filteredReports.filter((item) => getValidationMetrics(item).netReturn > 0).length;
  const bestReport = filteredReports.reduce<ReportSummary | null>((best, current) => {
    if (!best) {
      return current;
    }
    return getValidationMetrics(current).netReturn > getValidationMetrics(best).netReturn ? current : best;
  }, null);

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Results"
        title="查看回测报告"
        description="先看结论和风险，再打开详情看净值曲线、交易记录和参数。"
      />

      <div className="summary-grid">
        <MetricCard label="报告数量" value={filteredReports.length} note="当前筛选范围" />
        <MetricCard label="收益为正" value={positiveReports} note="样本外收益 > 0" />
        <MetricCard
          label="最佳样本外收益"
          value={bestReport ? <FormatPercent value={getValidationMetrics(bestReport).netReturn} /> : "-"}
          note={bestReport ? `${bestReport.symbol} / ${bestReport.interval}` : "暂无报告"}
        />
        <MetricCard label="最近报告" value={latestReport?.symbol ?? "-"} note={latestReport?.created_at ?? "暂无报告"} />
      </div>

      <Card size="small" title="报告列表" className="section-card">
        <div className="table-toolbar">
          <Space wrap>
            <Input placeholder="筛选标的或名称" value={keyword} onChange={(event) => setKeyword(event.target.value)} style={{ width: 240 }} />
            <Select allowClear placeholder="按周期筛选" value={interval} onChange={setInterval} options={intervalOptions} style={{ width: 150 }} />
          </Space>
          <ToolbarCount>共 {filteredReports.length} 份报告</ToolbarCount>
        </div>
        {filteredReports.length === 0 ? (
          <Empty description="暂无报告" />
        ) : (
          <Table
            rowKey="id"
            size="small"
            dataSource={filteredReports}
            pagination={{ pageSize: 12, showSizeChanger: false }}
            scroll={{ x: 980 }}
            columns={[
              { title: "报告", dataIndex: "id", width: 88, fixed: "left", render: (value: number) => `#${value}` },
              { title: "标的", dataIndex: "symbol", width: 120 },
              { title: "名称", dataIndex: "name", ellipsis: true },
              { title: "周期", dataIndex: "interval", width: 90 },
              { title: "策略", dataIndex: "strategy_kind", width: 180, ellipsis: true },
              {
                title: "结论",
                width: 150,
                render: (_, row) => {
                  const { netReturn, maxDrawdown } = getValidationMetrics(row);
                  const verdict = buildVerdict(netReturn, maxDrawdown);
                  return <Tag color={verdict.color}>{verdict.label}</Tag>;
                },
              },
              {
                title: "样本外收益",
                width: 120,
                render: (_, row) => <FormatPercent value={getValidationMetrics(row).netReturn} />,
              },
              {
                title: "最大回撤",
                width: 120,
                render: (_, row) => `${getValidationMetrics(row).maxDrawdown.toFixed(2)}%`,
              },
              {
                title: "怎么理解",
                width: 260,
                render: (_, row) => {
                  const { netReturn, maxDrawdown } = getValidationMetrics(row);
                  const verdict = buildVerdict(netReturn, maxDrawdown);
                  return <Typography.Text type="secondary">{verdict.description}</Typography.Text>;
                },
              },
              { title: "生成时间", dataIndex: "created_at", width: 180, ellipsis: true },
              {
                title: "操作",
                width: 88,
                fixed: "right",
                render: (_, row) => (
                  <Button size="small" type="link">
                    <Link href={`/reports/${row.id}`}>打开</Link>
                  </Button>
                ),
              },
            ]}
          />
        )}
      </Card>
    </div>
  );
}
