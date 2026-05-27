"use client";

import { Card, Descriptions, Empty, Skeleton, Table, Tag, Typography } from "antd";
import { useEffect, useState } from "react";
import { apiFetch, type ReportDetail } from "@/lib/api";
import { EquityChart } from "@/components/equity-chart";
import { DetailItem, FormatPercent, PageHeader } from "@/components/platform-ui";

type ReportDetailViewProps = {
  reportId: string;
};

function buildVerdict(netReturn: number, maxDrawdown: number, closedTrades: number) {
  if (closedTrades === 0) {
    return {
      label: "没有触发交易",
      color: "default",
      summary: "这次回测在样本外阶段没有满足策略开仓条件，不能说明策略一定无效，但需要换标的、周期或参数继续验证。",
    };
  }
  if (netReturn > 0 && maxDrawdown <= 8) {
    return {
      label: "表现较稳",
      color: "green",
      summary: "样本外收益为正，最大回撤相对可控，可以继续和买入持有、其他策略做对比。",
    };
  }
  if (netReturn > 0) {
    return {
      label: "有收益但波动大",
      color: "gold",
      summary: "策略赚到了钱，但回撤压力不小。继续使用前要重点看净值曲线是否能接受。",
    };
  }
  return {
    label: "暂不理想",
    color: "red",
    summary: "样本外收益为负，当前标的、周期或参数组合不建议直接采用。",
  };
}

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
  const maxDrawdown = Number(validation.MaxDrawdownPct ?? 0);
  const closedTrades = Number(validation.ClosedTrades ?? 0);
  const verdict = buildVerdict(netReturn, maxDrawdown, closedTrades);
  const returnTone = netReturn > 0 ? "positive" : netReturn < 0 ? "negative" : undefined;

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Result Detail"
        title={`回测报告 #${report.id}`}
        description={`${report.symbol} / ${report.interval} / ${report.strategy_kind}`}
      />

      <Card size="small" className="section-card result-verdict-card">
        <div className="result-verdict-main">
          <Tag color={verdict.color}>{verdict.label}</Tag>
          <Typography.Title level={3}>这次回测{netReturn >= 0 ? "没有亏损" : "出现亏损"}，样本外收益为 {netReturn.toFixed(2)}%</Typography.Title>
          <Typography.Paragraph>{verdict.summary}</Typography.Paragraph>
        </div>
        <div className="result-verdict-metrics">
          <DetailItem label="样本外收益" value={<FormatPercent value={netReturn} />} tone={returnTone} />
          <DetailItem label="最大回撤" value={`${maxDrawdown.toFixed(2)}%`} tone={maxDrawdown > 0 ? "negative" : undefined} />
          <DetailItem label="成交笔数" value={String(closedTrades)} />
        </div>
      </Card>

      <Card size="small" title="先看这几项" className="section-card">
        <div className="detail-grid">
          <DetailItem label="标的" value={`${report.symbol} ${report.name}`} />
          <DetailItem label="策略" value={report.strategy_kind} />
          <DetailItem label="周期" value={report.interval} />
          <DetailItem label="样本区间" value={`${report.dataset_start} 至 ${report.dataset_end}`} />
          <DetailItem label="报告生成时间" value={report.created_at} />
          <DetailItem label="任务ID" value={report.job_id} />
        </div>
      </Card>

      <Card size="small" title="净值与回撤" className="section-card">
        {report.equity_curve.length === 0 ? <Empty description="无净值数据" /> : <EquityChart points={report.equity_curve} />}
      </Card>

      <Card size="small" title="本次使用的关键参数" className="section-card">
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
        <Card size="small" title="策略模板来源" className="section-card">
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

      <Card size="small" title="交易记录：策略具体买卖了什么" className="section-card">
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

      <Card size="small" title="事件流水：策略触发了哪些信号" className="section-card">
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
