"use client";

import { Card, Descriptions, Empty, Skeleton, Table } from "antd";
import { useEffect, useState } from "react";
import { apiFetch, type ReportDetail } from "@/lib/api";
import { EquityChart } from "@/components/equity-chart";
import { DetailItem, FormatPercent, PageHeader } from "@/components/platform-ui";

type ReportDetailViewProps = {
  reportId: string;
};

export function ReportDetailView({ reportId }: ReportDetailViewProps) {
  const [report, setReport] = useState<ReportDetail | null>(null);

  useEffect(() => {
    void apiFetch<ReportDetail>(`/api/reports/${reportId}`).then(setReport);
  }, [reportId]);

  if (!report) {
    return <Skeleton active paragraph={{ rows: 12 }} />;
  }

  const validation = report.summary_metrics.validation ?? {};
  const templateSnapshot = report.artifacts.template_snapshot as Record<string, unknown> | undefined;
  const netReturn = Number(validation.NetReturnPct ?? validation.ReturnPct ?? 0);
  const returnTone = netReturn > 0 ? "positive" : netReturn < 0 ? "negative" : undefined;

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Report Detail"
        title={`报告详情 #${report.id}`}
        description={`${report.symbol} / ${report.interval} / ${report.strategy_kind}`}
      />

      <Card size="small" title="复盘摘要" className="section-card">
        <div className="detail-grid">
          <DetailItem label="标的" value={`${report.symbol} ${report.name}`} />
          <DetailItem label="任务ID" value={report.job_id} />
          <DetailItem label="样本区间" value={`${report.dataset_start} - ${report.dataset_end}`} />
          <DetailItem label="生成时间" value={report.created_at} />
          <DetailItem label="样本外收益" value={<FormatPercent value={netReturn} />} tone={returnTone} />
          <DetailItem label="最大回撤" value={`${Number(validation.MaxDrawdownPct ?? 0).toFixed(2)}%`} tone="negative" />
          <DetailItem label="成交笔数" value={String(validation.ClosedTrades ?? "-")} />
          <DetailItem label="策略" value={report.strategy_kind} />
        </div>
      </Card>

      <Card size="small" title="净值与回撤" className="section-card">
        {report.equity_curve.length === 0 ? <Empty description="无净值数据" /> : <EquityChart points={report.equity_curve} />}
      </Card>

      <Card size="small" title="参数摘要" className="section-card">
        <Descriptions size="small" column={{ xs: 1, sm: 2, lg: 3 }}>
          {Object.entries(report.parameters)
            .slice(0, 18)
            .map(([key, value]) => (
              <Descriptions.Item key={key} label={key}>
                {String(value)}
              </Descriptions.Item>
            ))}
        </Descriptions>
      </Card>

      {templateSnapshot ? (
        <Card size="small" title="模板快照" className="section-card">
          <Descriptions size="small" column={{ xs: 1, sm: 2, lg: 3 }}>
            <Descriptions.Item label="模板">{String(templateSnapshot.template_name ?? "-")}</Descriptions.Item>
            <Descriptions.Item label="模板键">{String(templateSnapshot.template_key ?? "-")}</Descriptions.Item>
            <Descriptions.Item label="模板ID">{String(templateSnapshot.id ?? "-")}</Descriptions.Item>
            <Descriptions.Item label="策略">{String(templateSnapshot.strategy_kind ?? "-")}</Descriptions.Item>
            <Descriptions.Item label="周期">{String(templateSnapshot.interval ?? "-")}</Descriptions.Item>
            <Descriptions.Item label="默认模板">{Boolean(templateSnapshot.is_default) ? "是" : "否"}</Descriptions.Item>
          </Descriptions>
        </Card>
      ) : null}

      <Card size="small" title="交易记录" className="section-card">
        <Table
          rowKey={(row) => `${String(row.trade_time)}-${String(row.trade_type)}-${String(row.price)}`}
          size="small"
          dataSource={report.trades}
          pagination={{ pageSize: 10, showSizeChanger: false }}
          scroll={{ x: 980 }}
          columns={[
            { title: "时间", dataIndex: "trade_time", width: 180, fixed: "left" },
            { title: "方向", dataIndex: "side", width: 90 },
            { title: "价格", dataIndex: "price", width: 110 },
            { title: "数量", dataIndex: "quantity", width: 100 },
            { title: "金额", dataIndex: "amount", width: 120 },
            { title: "费用", dataIndex: "fee", width: 100 },
            { title: "类型", dataIndex: "trade_type", width: 160 },
            { title: "备注", dataIndex: "note", ellipsis: true },
          ]}
        />
      </Card>

      <Card size="small" title="事件流水" className="section-card">
        <Table
          rowKey={(row) => `${String(row.event_time)}-${String(row.event_type)}-${String(row.price)}`}
          size="small"
          dataSource={report.events}
          pagination={{ pageSize: 10, showSizeChanger: false }}
          scroll={{ x: 860 }}
          columns={[
            { title: "时间", dataIndex: "event_time", width: 180, fixed: "left" },
            { title: "事件", dataIndex: "event_type", width: 160 },
            { title: "价格", dataIndex: "price", width: 120 },
            {
              title: "明细",
              render: (_, row) => <span>{JSON.stringify(row.payload)}</span>,
            },
          ]}
        />
      </Card>
    </div>
  );
}
