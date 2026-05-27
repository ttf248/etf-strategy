"use client";

import { Card, Collapse, Descriptions, Empty, Skeleton, Space, Table, Tag, Typography } from "antd";
import { useEffect, useState } from "react";
import { apiFetch, type ReportDetail } from "@/lib/api";
import { EquityChart } from "@/components/equity-chart";
import { DetailItem, FormatPercent, PageHeader } from "@/components/platform-ui";
import { parameterFieldSpecsByStrategy, strategyLabel } from "@/lib/strategy-template-config";

type ReportDetailViewProps = {
  reportId: string;
};

const baseParameterLabels: Record<string, string> = {
  AnchorDate: "锚定日期",
  BaseUnits: "基础份额",
  benchmark: "对照基准",
  Benchmark: "对照基准",
  commission_bps: "交易佣金",
  cooldown_bars: "停手冷却 K 线数",
  EndDate: "结束时间",
  EntryDate: "入场时间",
  EntryPrice: "入场价格",
  execution_profile: "成交假设",
  force_exit_loss_pct: "强制离场亏损线",
  GridCount: "网格层数",
  GridMode: "网格模式",
  jobs: "并行寻参任务数",
  left_side_policy: "左侧行情处理",
  lookback_days: "回看天数",
  LotSize: "每手数量",
  Market: "市场",
  max_position_ratio: "最大仓位",
  NetPnl: "样本外盈亏",
  parameter_space: "寻参范围",
  PeakDate: "阶段高点时间",
  PeakPrice: "阶段高点价格",
  ReturnPct: "样本外收益",
  Scenario: "回测场景",
  Score: "策略评分",
  slippage_bps: "滑点假设",
  StartDate: "开始时间",
  stop_loss_pct: "停手跌幅",
  Symbol: "标的代码",
  template_id: "模板 ID",
  total_capital: "初始资金",
  validation_ratio: "样本外比例",
  validation_start: "样本外起点",
};

const eventTypeLabels: Record<string, string> = {
  dca_buy: "定投买入",
  dca_skip: "定投跳过",
  force_exit_sell: "强制离场卖出",
  grid_sell: "网格止盈卖出",
  risk_cooldown: "冷却期跳过",
  risk_position_limit: "仓位上限拦截",
  risk_stop_loss: "触发停手线",
};

const payloadFieldLabels: Record<string, string> = {
  CashFlow: "成交金额",
  EventType: "事件类型",
  ExecutionPrice: "估算成交价",
  Level: "网格层",
  Note: "说明",
  Price: "触发价",
  SlippageCost: "滑点成本",
  TransactionCost: "交易费用",
  Units: "数量",
};

const tradeSideLabels: Record<string, string> = {
  buy: "买入",
  sell: "卖出",
};

const tradeTypeLabels: Record<string, string> = {
  dca_buy: "定投买入",
  force_exit_sell: "强制离场",
  grid: "网格交易",
  grid_sell: "网格止盈",
};

const valueLabels: Record<string, Record<string, string>> = {
  day_rule: {
    first_trading_day: "每期第一个交易日",
  },
  execution_profile: {
    conservative: "保守成交",
    realistic: "实盘口径",
    research: "研究默认",
  },
  frequency: {
    monthly: "每月",
    weekly: "每周",
  },
  left_side_policy: {
    both: "同时对比",
    force_exit: "触发阈值后强制离场",
    hold: "继续持有",
  },
  Benchmark: {
    buy_hold: "买入持有",
    cash_idle: "现金空仓",
  },
  benchmark: {
    buy_hold: "买入持有",
    cash_idle: "现金空仓",
  },
  GridMode: {
    cash: "现金空仓",
    buy_hold: "买入持有",
  },
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

function parameterLabel(strategyKind: string, key: string): string {
  const strategyField = parameterFieldSpecsByStrategy[strategyKind]?.find((item) => item.key === key);
  return strategyField?.label ?? baseParameterLabels[key] ?? key;
}

function formatScalar(key: string, value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  if (typeof value === "number") {
    if (key.endsWith("_bps")) {
      return `${value} bps`;
    }
    if ((key.includes("ratio") || key.includes("spacing") || key.includes("profit")) && Math.abs(value) <= 1) {
      return `${(value * 100).toFixed(2)}%`;
    }
    if (key.endsWith("_pct") || key.endsWith("Pct")) {
      return `${value.toFixed(2)}%`;
    }
    return Number.isInteger(value) ? String(value) : value.toFixed(4).replace(/0+$/, "").replace(/\.$/, "");
  }
  if (typeof value === "boolean") {
    return value ? "是" : "否";
  }
  if (typeof value === "string") {
    return valueLabels[key]?.[value] ?? (key === "EventType" ? eventTypeLabels[value] : value);
  }
  return JSON.stringify(value);
}

function formatParameterValue(strategyKind: string, key: string, value: unknown): string {
  if (Array.isArray(value)) {
    return value.map((item) => formatScalar(key, item)).join("、");
  }
  if (typeof value === "object" && value !== null) {
    return Object.entries(value)
      .map(([itemKey, itemValue]) => `${parameterLabel(strategyKind, itemKey)}：${formatParameterValue(strategyKind, itemKey, itemValue)}`)
      .join("；");
  }
  return formatScalar(key, value);
}

function formatEventDetails(payload: unknown) {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    return <Typography.Text type="secondary">无补充说明</Typography.Text>;
  }
  const payloadEntries = Object.entries(payload as Record<string, unknown>)
    .filter(([key]) => key !== "Date")
    .filter(([, value]) => value !== null && value !== undefined && value !== "");
  if (payloadEntries.length === 0) {
    return <Typography.Text type="secondary">无补充说明</Typography.Text>;
  }
  return (
    <Space size={[6, 6]} wrap>
      {payloadEntries.map(([key, value]) => (
        <Tag key={key} bordered={false}>
          {payloadFieldLabels[key] ?? key}：{formatScalar(key, value)}
        </Tag>
      ))}
    </Space>
  );
}

function formatCell(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  if (typeof value === "number") {
    return Number.isInteger(value) ? value.toLocaleString() : value.toFixed(4).replace(/0+$/, "").replace(/\.$/, "");
  }
  return String(value);
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
        description={`${report.symbol} / ${report.interval} / ${strategyLabel(report.strategy_kind)}`}
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
          <DetailItem label="策略" value={strategyLabel(report.strategy_kind)} />
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
              <Descriptions.Item key={key} label={parameterLabel(report.strategy_kind, key)}>
                {formatParameterValue(report.strategy_kind, key, value)}
              </Descriptions.Item>
            ))}
        </Descriptions>
      </Card>

      {templateSnapshot ? (
        <Card size="small" title="策略模板来源" className="section-card">
          <Descriptions size="small" column={{ xs: 1, sm: 2, lg: 3 }}>
            <Descriptions.Item label="使用模板">{String(templateSnapshot.template_name ?? "-")}</Descriptions.Item>
            <Descriptions.Item label="策略">{strategyLabel(String(templateSnapshot.strategy_kind ?? report.strategy_kind))}</Descriptions.Item>
            <Descriptions.Item label="周期">{String(templateSnapshot.interval ?? "-")}</Descriptions.Item>
            <Descriptions.Item label="默认模板">{Boolean(templateSnapshot.is_default) ? "是" : "否"}</Descriptions.Item>
          </Descriptions>
          <Collapse
            className="advanced-trace-panel"
            ghost
            items={[
              {
                key: "trace",
                label: "查看高级追踪信息",
                children: (
                  <Descriptions size="small" column={{ xs: 1, sm: 2 }}>
                    <Descriptions.Item label="模板键">{String(templateSnapshot.template_key ?? "-")}</Descriptions.Item>
                    <Descriptions.Item label="模板 ID">{String(templateSnapshot.id ?? "-")}</Descriptions.Item>
                  </Descriptions>
                ),
              },
            ]}
          />
        </Card>
      ) : null}

      <Card size="small" title="交易记录：策略具体买卖了什么" className="section-card">
        {report.trades.length === 0 ? (
          <Empty description="没有交易记录" />
        ) : (
          <div className="trade-mobile-list">
            {report.trades.slice(0, 10).map((trade, index) => (
              <article key={`${String(trade.trade_time)}-${String(trade.trade_type)}-${index}`} className="trade-mobile-card">
                <div className="trade-mobile-card-head">
                  <div>
                    <strong>{tradeSideLabels[String(trade.side)] ?? formatCell(trade.side)}</strong>
                    <span>{formatCell(trade.trade_time)}</span>
                  </div>
                  <Tag>{tradeTypeLabels[String(trade.trade_type)] ?? formatCell(trade.trade_type)}</Tag>
                </div>
                <div className="trade-mobile-metrics">
                  <span>价格 {formatCell(trade.price)}</span>
                  <span>数量 {formatCell(trade.quantity)}</span>
                  <span>金额 {formatCell(trade.amount)}</span>
                  <span>费用 {formatCell(trade.fee)}</span>
                </div>
                {trade.note ? <p>{formatCell(trade.note)}</p> : null}
              </article>
            ))}
            {report.trades.length > 10 ? <Typography.Text type="secondary">移动端先显示前 10 条，桌面表格可查看更多。</Typography.Text> : null}
          </div>
        )}
        {report.trades.length > 0 ? (
          <Table
            className="report-detail-desktop-table"
            rowKey={(row) => `${String(row.trade_time)}-${String(row.trade_type)}-${String(row.price)}`}
            size="small"
            dataSource={report.trades}
            pagination={{ pageSize: 10, showSizeChanger: false }}
            scroll={{ x: 980 }}
            columns={[
              { title: "时间", dataIndex: "trade_time", width: 180, fixed: "left" },
              { title: "方向", dataIndex: "side", width: 90, render: (value: string) => tradeSideLabels[value] ?? value },
              { title: "价格", dataIndex: "price", width: 110 },
              { title: "数量", dataIndex: "quantity", width: 100 },
              { title: "金额", dataIndex: "amount", width: 120 },
              { title: "费用", dataIndex: "fee", width: 100 },
              { title: "类型", dataIndex: "trade_type", width: 160, render: (value: string) => tradeTypeLabels[value] ?? value },
              { title: "备注", dataIndex: "note", ellipsis: true },
            ]}
          />
        ) : null}
      </Card>

      <Card size="small" title="事件流水：策略触发了哪些信号" className="section-card">
        {report.events.length === 0 ? (
          <Empty description="没有事件记录" />
        ) : (
          <div className="event-mobile-list">
            {report.events.slice(0, 10).map((event, index) => (
              <article key={`${String(event.event_time)}-${String(event.event_type)}-${index}`} className="event-mobile-card">
                <div className="event-mobile-card-head">
                  <div>
                    <strong>{eventTypeLabels[String(event.event_type)] ?? formatCell(event.event_type)}</strong>
                    <span>{formatCell(event.event_time)}</span>
                  </div>
                  <Tag>价格 {formatCell(event.price)}</Tag>
                </div>
                <div className="event-mobile-detail">{formatEventDetails(event.payload)}</div>
              </article>
            ))}
            {report.events.length > 10 ? <Typography.Text type="secondary">移动端先显示前 10 条，桌面表格可查看更多。</Typography.Text> : null}
          </div>
        )}
        {report.events.length > 0 ? (
          <Table
            className="report-detail-desktop-table"
            rowKey={(row) => `${String(row.event_time)}-${String(row.event_type)}-${String(row.price)}`}
            size="small"
            dataSource={report.events}
            pagination={{ pageSize: 10, showSizeChanger: false }}
            scroll={{ x: 860 }}
            columns={[
              { title: "时间", dataIndex: "event_time", width: 180, fixed: "left" },
              { title: "事件", dataIndex: "event_type", width: 160, render: (value: string) => eventTypeLabels[value] ?? value },
              { title: "价格", dataIndex: "price", width: 120 },
              {
                title: "明细说明",
                render: (_, row) => formatEventDetails(row.payload),
              },
            ]}
          />
        ) : null}
      </Card>
    </div>
  );
}
