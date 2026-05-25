"use client";

import { Card, Descriptions, Empty, Skeleton, Table, Typography } from "antd";
import { useEffect, useState } from "react";
import { apiFetch, type ReportDetail } from "@/lib/api";
import { EquityChart } from "@/components/equity-chart";

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

  return (
    <div className="page-stack">
      <Typography.Title level={3} className="section-title">
        报告详情 #{report.id}
      </Typography.Title>

      <Card size="small" title={`${report.symbol} ${report.interval} ${report.strategy_kind}`}>
        <Descriptions size="small" column={3}>
          <Descriptions.Item label="标的">{report.symbol}</Descriptions.Item>
          <Descriptions.Item label="名称">{report.name}</Descriptions.Item>
          <Descriptions.Item label="任务ID">{report.job_id}</Descriptions.Item>
          <Descriptions.Item label="样本起始">{report.dataset_start}</Descriptions.Item>
          <Descriptions.Item label="样本结束">{report.dataset_end}</Descriptions.Item>
          <Descriptions.Item label="生成时间">{report.created_at}</Descriptions.Item>
          <Descriptions.Item label="样本外收益">{`${Number(validation.NetReturnPct ?? validation.ReturnPct ?? 0).toFixed(2)}%`}</Descriptions.Item>
          <Descriptions.Item label="最大回撤">{`${Number(validation.MaxDrawdownPct ?? 0).toFixed(2)}%`}</Descriptions.Item>
          <Descriptions.Item label="成交笔数">{String(validation.ClosedTrades ?? "-")}</Descriptions.Item>
        </Descriptions>
      </Card>

      <Card size="small" title="净值与回撤">
        {report.equity_curve.length === 0 ? <Empty description="无净值数据" /> : <EquityChart points={report.equity_curve} />}
      </Card>

      <Card size="small" title="参数摘要">
        <Descriptions size="small" column={3}>
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
        <Card size="small" title="模板快照">
          <Descriptions size="small" column={3}>
            <Descriptions.Item label="模板">{String(templateSnapshot.template_name ?? "-")}</Descriptions.Item>
            <Descriptions.Item label="模板键">{String(templateSnapshot.template_key ?? "-")}</Descriptions.Item>
            <Descriptions.Item label="模板ID">{String(templateSnapshot.id ?? "-")}</Descriptions.Item>
            <Descriptions.Item label="策略">{String(templateSnapshot.strategy_kind ?? "-")}</Descriptions.Item>
            <Descriptions.Item label="周期">{String(templateSnapshot.interval ?? "-")}</Descriptions.Item>
            <Descriptions.Item label="默认模板">{Boolean(templateSnapshot.is_default) ? "是" : "否"}</Descriptions.Item>
          </Descriptions>
        </Card>
      ) : null}

      <Card size="small" title="交易记录">
        <Table
          rowKey={(row) => `${String(row.trade_time)}-${String(row.trade_type)}`}
          size="small"
          dataSource={report.trades}
          pagination={{ pageSize: 10 }}
          columns={[
            { title: "时间", dataIndex: "trade_time", width: 180 },
            { title: "方向", dataIndex: "side", width: 90 },
            { title: "价格", dataIndex: "price" },
            { title: "数量", dataIndex: "quantity" },
            { title: "金额", dataIndex: "amount" },
            { title: "费用", dataIndex: "fee" },
            { title: "类型", dataIndex: "trade_type", width: 160 },
            { title: "备注", dataIndex: "note" },
          ]}
        />
      </Card>

      <Card size="small" title="事件流水">
        <Table
          rowKey={(row) => `${String(row.event_time)}-${String(row.event_type)}`}
          size="small"
          dataSource={report.events}
          pagination={{ pageSize: 10 }}
          columns={[
            { title: "时间", dataIndex: "event_time", width: 180 },
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
