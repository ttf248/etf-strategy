"use client";

import Link from "next/link";
import { Button, Card, Collapse, Descriptions, Empty, Skeleton, Space, Table, Tag, Typography } from "antd";
import { useCallback, useEffect, useState } from "react";
import { apiFetchSafe, type ReportDetail, type ReportSummary } from "@/lib/api";
import { EquityChart } from "@/components/equity-chart";
import { DetailItem, FormatPercent, InlineErrorBanner, PageErrorState, PageHeader } from "@/components/platform-ui";
import { parameterFieldSpecsByStrategy, strategyLabel } from "@/lib/strategy-template-config";
import { buildBacktestLaunchHref } from "@/lib/beginner-presets";

type ReportDetailViewProps = {
  reportId: string;
};

type CurvePoint = ReportDetail["equity_curve"][number];
type ParameterHighlight = {
  title: string;
  value: string;
  description: string;
};

type ValidationMetrics = {
  netReturn: number;
  maxDrawdown: number;
  closedTrades: number;
  vsBuyHold: number | null;
  outperformBuyHold: boolean;
};

type PeerComparisonInsight = {
  headline: string;
  description: string;
  guides: Array<{
    title: string;
    value: string;
    description: string;
  }>;
  recommendedCompareIds: number[];
};

const baseParameterLabels: Record<string, string> = {
  AnchorDate: "从哪一天开始对齐",
  BaseUnits: "基础持仓份额",
  band_width: "布林带宽度",
  benchmark: "和谁做对照",
  BandWidth: "布林带宽度",
  Benchmark: "和谁做对照",
  breakout_window: "突破窗口",
  BreakoutWindow: "突破窗口",
  commission_bps: "交易佣金",
  confirm_buffer_pct: "突破确认比例",
  ConfirmBufferPct: "突破确认比例",
  cooldown_bars: "停手后先等多少根 K 线",
  EndDate: "结束时间",
  EntryDate: "入场时间",
  EntryPrice: "入场时价格",
  exit_window: "退出窗口",
  ExitWindow: "退出窗口",
  execution_profile: "成交假设",
  fast_window: "快线窗口",
  force_exit_loss_pct: "达到多大亏损时强制离场",
  GridCount: "最多开几层网格",
  GridMode: "开始时先怎么买",
  HistogramConfirmPct: "柱体确认阈值",
  histogram_confirm_pct: "柱体确认阈值",
  jobs: "同时试几组参数",
  left_side_policy: "行情先走弱时怎么处理",
  lookback_days: "回看多少天历史",
  LotSize: "每次最少按多少份交易",
  LongWindow: "长均线窗口",
  MacdEntryEvents: "MACD 入场次数",
  MacdExitEvents: "MACD 退出次数",
  Market: "在哪个市场交易",
  max_position_ratio: "最大仓位",
  MaxHoldBars: "最大持仓 K 线数",
  ma_window: "布林带窗口",
  NetPnl: "单独验证盈亏",
  parameter_space: "可尝试的参数范围",
  PeakDate: "这轮最高点时间",
  PeakPrice: "这轮最高点价格",
  ReturnPct: "单独验证收益",
  Scenario: "这次测试的场景",
  Score: "这次结果评分",
  slippage_bps: "滑点假设",
  StartDate: "开始时间",
  stop_loss_pct: "停手跌幅",
  ShortWindow: "短均线窗口",
  signal_buffer_pct: "信号缓冲比例",
  SignalBufferPct: "信号缓冲比例",
  SignalWindow: "信号线窗口",
  signal_window: "信号线窗口",
  SlowWindow: "慢线窗口",
  slow_window: "慢线窗口",
  Symbol: "标的代码",
  template_id: "模板编号",
  total_capital: "初始资金",
  validation_ratio: "最后留多少比例做验证",
  validation_start: "从哪一天开始单独验证",
  volume_multiplier: "成交量放大倍数",
  VolumeMultiplier: "成交量放大倍数",
  volume_window: "成交量均值窗口",
  VolumeWindow: "成交量均值窗口",
};

const eventTypeLabels: Record<string, string> = {
  bollinger_buy: "下轨回归买入",
  dca_buy: "定投买入",
  dca_skip: "定投跳过",
  donchian_buy: "突破高点买入",
  donchian_exit_sell: "跌回通道卖出",
  force_exit_sell: "强制离场卖出",
  grid_sell: "网格止盈卖出",
  ma_cross_buy: "均线金叉买入",
  ma_cross_sell: "均线死叉卖出",
  macd_buy: "MACD 金叉买入",
  macd_sell: "MACD 死叉卖出",
  max_hold_sell: "到期离场",
  mean_revert_sell: "回到均值卖出",
  risk_cooldown: "冷却期跳过",
  risk_position_limit: "仓位上限拦截",
  risk_stop_loss: "触发停手线",
  stop_loss_sell: "止损卖出",
  take_profit_sell: "止盈卖出",
  volume_breakout_buy: "放量突破买入",
  volume_breakout_exit_sell: "跌回通道卖出",
};

const payloadFieldLabels: Record<string, string> = {
  CashFlow: "成交金额",
  EventType: "这次发生了什么",
  ExecutionPrice: "大概成交价格",
  Level: "网格层",
  Note: "说明",
  Price: "触发时价格",
  SlippageCost: "滑点成本",
  TransactionCost: "交易费用",
  Units: "数量",
};

const tradeSideLabels: Record<string, string> = {
  buy: "买入",
  sell: "卖出",
};

const tradeTypeLabels: Record<string, string> = {
  bollinger_reversion: "布林带均值回归",
  dca_buy: "定投买入",
  donchian_breakout: "唐奇安突破",
  force_exit_sell: "强制离场",
  grid: "网格交易",
  grid_sell: "网格止盈",
  ma_cross: "双均线趋势",
  macd_trend: "MACD 趋势",
  volume_breakout: "放量突破",
};

const valueLabels: Record<string, Record<string, string>> = {
  day_rule: {
    first_trading_day: "每期第一个交易日",
  },
  execution_profile: {
    conservative: "保守成交",
    realistic: "真实成交口径",
    research: "理想成交口径",
  },
  frequency: {
    monthly: "每月",
    weekly: "每周",
  },
  left_side_policy: {
    both: "两种处理都跑一遍",
    force_exit: "亏到阈值就清仓停手",
    hold: "先继续拿着，等后面反弹",
  },
  Benchmark: {
    buy_hold: "买入后一直拿着",
    cash_idle: "空仓不买",
  },
  benchmark: {
    buy_hold: "买入后一直拿着",
    cash_idle: "空仓不买",
  },
  GridMode: {
    cash: "先空仓，等触发再买",
    buy_hold: "先买入，再继续持有",
  },
};

function buildVerdict(netReturn: number, maxDrawdown: number, closedTrades: number) {
  if (closedTrades === 0) {
    return {
      label: "没有触发交易",
      color: "default",
      summary: "本次回测在单独验证阶段未满足开仓条件。这并不直接说明策略无效，但需要调整标的、周期或参数后继续验证。",
    };
  }
  if (netReturn > 0 && maxDrawdown <= 8) {
    return {
      label: "收益与风险较平衡",
      color: "green",
      summary: "单独验证收益为正，且最大回撤相对可控，可继续与买入持有或其他策略进行对比。",
    };
  }
  if (netReturn > 0) {
    return {
      label: "正收益但波动较高",
      color: "gold",
      summary: "策略取得正收益，但回撤压力不低。继续采用前应重点评估净值波动是否可接受。",
    };
  }
  return {
    label: "当前样本下表现偏弱",
    color: "red",
    summary: "单独验证收益为负，当前标的、周期或参数组合不建议直接采用。",
  };
}

function readNumberMetric(metrics: Record<string, unknown>, ...keys: string[]): number | null {
  for (const key of keys) {
    const value = metrics[key];
    if (typeof value === "number" && Number.isFinite(value)) {
      return value;
    }
  }
  return null;
}

function readNumberParameter(parameters: Record<string, unknown>, ...keys: string[]): number | null {
  for (const key of keys) {
    const value = parameters[key];
    if (typeof value === "number" && Number.isFinite(value)) {
      return value;
    }
    if (typeof value === "string") {
      const parsed = Number(value);
      if (Number.isFinite(parsed)) {
        return parsed;
      }
    }
  }
  return null;
}

function formatMoney(value: number): string {
  return Math.round(value).toLocaleString();
}

function benchmarkGuide(validation: Record<string, unknown>) {
  const buyHoldReturn = readNumberMetric(validation, "BuyHoldReturnPct");
  const relativeEquity = readNumberMetric(validation, "StrategyVsBuyHold", "GridVsBuyHold");
  const outperform = typeof validation.OutperformBuyHold === "boolean" ? validation.OutperformBuyHold : null;

  if (buyHoldReturn === null && relativeEquity === null && outperform === null) {
    return {
      title: "和买入持有比",
      value: "暂无对照",
      description: "该报告未提供买入持有对照，建议优先检查收益、回撤与交易记录是否符合预期。",
    };
  }

  const parts: string[] = [];
  if (buyHoldReturn !== null) {
    parts.push(`买入持有收益 ${buyHoldReturn.toFixed(2)}%`);
  }
  if (relativeEquity !== null) {
    parts.push(`${relativeEquity >= 0 ? "期末多赚" : "期末少赚"} ${Math.abs(relativeEquity).toFixed(2)}`);
  }
  const value = outperform === null ? "有对照数据" : outperform ? "跑赢买入持有" : "没跑赢买入持有";
  return {
    title: "和买入持有比",
    value,
    description: parts.join("，") || "该报告提供了与买入持有的对照，可用于判断策略是否值得替代最简单的持有方案。",
  };
}

function riskGuide(maxDrawdown: number) {
  if (maxDrawdown <= 5) {
    return {
      title: "回撤怎么看",
      value: "波动较小",
      description: `最大回撤 ${maxDrawdown.toFixed(2)}%，说明账户从阶段高点回落的幅度相对较小。`,
    };
  }
  if (maxDrawdown <= 12) {
    return {
      title: "回撤怎么看",
      value: "中等波动",
      description: `最大回撤 ${maxDrawdown.toFixed(2)}%，继续使用前要结合净值曲线确认自己能否接受中途回撤。`,
    };
  }
  return {
    title: "回撤怎么看",
    value: "波动偏大",
    description: `最大回撤 ${maxDrawdown.toFixed(2)}%，波动暴露偏高，建议优先调整参数、周期或仓位控制。`,
  };
}

function tradeGuide(closedTrades: number, validation: Record<string, unknown>) {
  const winRate = readNumberMetric(validation, "WinRatePct");
  if (closedTrades === 0) {
    return {
      title: "交易活跃度",
      value: "没有成交",
      description: "单独验证阶段没有形成完整交易，先检查标的是否太平、周期是否不匹配，或参数是否过于保守。",
    };
  }
  if (winRate === null) {
    return {
      title: "交易活跃度",
      value: `${closedTrades} 笔成交`,
      description: "先结合交易记录查看买卖节奏，再判断这类频率是否符合你的交易习惯。",
    };
  }
  return {
    title: "交易活跃度",
    value: `${closedTrades} 笔 / 胜率 ${winRate.toFixed(1)}%`,
    description: "胜率不是越高越好，还要结合单笔盈亏和回撤一起看，避免只看命中率。",
  };
}

function nextActionGuide(netReturn: number, maxDrawdown: number, closedTrades: number) {
  if (closedTrades === 0) {
    return {
      title: "下一步建议",
      value: "换标的或周期",
      description: "优先换一个数据更活跃的标的，或把 1d / 15m 切换后再跑一轮，先让策略真正触发交易。",
    };
  }
  if (netReturn > 0 && maxDrawdown <= 8) {
    return {
      title: "下一步建议",
      value: "拿去做对比",
      description: "这份结果可以加入报告对比区，再和同标的其他策略或买入持有方案一起看，确认是否稳定领先。",
    };
  }
  if (netReturn > 0) {
    return {
      title: "下一步建议",
      value: "先压回撤",
      description: "可以先减少仓位、缩短持仓周期，或换更稳的模板，看看能否在保住收益的同时降低波动。",
    };
  }
  return {
    title: "下一步建议",
    value: "重跑一轮",
    description: "这次结果不理想，优先回到创建回测页换模板或周期，再和当前报告做对比，不建议直接采用。",
  };
}

function buildDecisionSummary(params: {
  netReturn: number;
  maxDrawdown: number;
  closedTrades: number;
  vsBuyHold: number | null;
}): { title: string; description: string } {
  const { netReturn, maxDrawdown, closedTrades, vsBuyHold } = params;
  if (closedTrades === 0) {
    return {
      title: "当前还不能判断这套策略优不优，先让它真正触发交易",
      description: "这轮单独验证没有形成成交，因此最重要的问题不是赚了多少，而是当前标的、周期和参数组合为什么没有触发。应先让策略真正成交，再讨论收益和稳健性。",
    };
  }
  if (netReturn > 0 && maxDrawdown <= 8 && (vsBuyHold === null || vsBuyHold >= 0)) {
    return {
      title: vsBuyHold !== null && vsBuyHold > 0 ? "当前结果值得继续研究，且已经跑赢买入持有" : "当前结果值得继续研究，下一步确认是否能稳定跑赢买入持有",
      description: "这份结果已经同时满足正收益与相对可控的回撤，说明它至少值得进入下一轮横向比较。接下来重点不是再看更多明细，而是确认它是否稳定优于同标的其他方案。",
    };
  }
  if (netReturn > 0) {
    return {
      title: "当前结果能赚钱，但还不能直接采用",
      description: "这份结果说明策略方向未必有问题，但回撤偏高，首要任务应是判断净值波动是否可接受，再决定是否通过仓位、节奏或模板调整把回撤压下来。",
    };
  }
  return {
    title: "当前结果不建议直接采用，应优先作为反向对照",
    description: "这轮单独验证收益为负，说明这套组合至少在当前样本里没有证明自己。与其继续死磕同一组参数，不如把它保留为对照样本，再换模板、周期或标的重跑。",
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
      return `万分之 ${value}`;
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

function readTemplateId(report: ReportDetail, templateSnapshot?: Record<string, unknown>): number | undefined {
  const candidates = [templateSnapshot?.id, report.parameters.template_id];
  for (const value of candidates) {
    if (typeof value === "number" && Number.isFinite(value)) {
      return value;
    }
    if (typeof value === "string") {
      const parsed = Number(value);
      if (Number.isFinite(parsed)) {
        return parsed;
      }
    }
  }
  return undefined;
}

function buildCompareHref(report: ReportDetail): string {
  const searchParams = new URLSearchParams();
  searchParams.set("compare", String(report.id));
  searchParams.set("keyword", report.symbol);
  searchParams.set("interval", report.interval);
  return `/reports?${searchParams.toString()}`;
}

function buildCompareHrefWithPeers(report: ReportDetail, peerIds: number[]): string {
  const searchParams = new URLSearchParams();
  [report.id, ...peerIds]
    .filter((value, index, values) => values.indexOf(value) === index)
    .slice(0, 4)
    .forEach((value) => searchParams.append("compare", String(value)));
  searchParams.set("keyword", report.symbol);
  searchParams.set("interval", report.interval);
  return `/reports?${searchParams.toString()}`;
}

function getValidationMetrics(report: ReportSummary | ReportDetail): ValidationMetrics {
  const validation = report.summary_metrics.validation ?? {};
  const netReturn = Number(validation.NetReturnPct ?? validation.ReturnPct ?? 0);
  const maxDrawdown = Number(validation.MaxDrawdownPct ?? 0);
  const closedTrades = Number(validation.ClosedTrades ?? 0);
  const relativeValue = validation.StrategyVsBuyHold ?? validation.GridVsBuyHold;
  const vsBuyHold = typeof relativeValue === "number" && Number.isFinite(relativeValue) ? relativeValue : null;
  const outperformBuyHold =
    typeof validation.OutperformBuyHold === "boolean"
      ? validation.OutperformBuyHold
      : typeof vsBuyHold === "number"
        ? vsBuyHold > 0
        : false;
  return { netReturn, maxDrawdown, closedTrades, vsBuyHold, outperformBuyHold };
}

function comparePeerReports(left: ReportSummary, right: ReportSummary): number {
  const leftMetrics = getValidationMetrics(left);
  const rightMetrics = getValidationMetrics(right);
  if (leftMetrics.closedTrades === 0 && rightMetrics.closedTrades > 0) {
    return 1;
  }
  if (leftMetrics.closedTrades > 0 && rightMetrics.closedTrades === 0) {
    return -1;
  }
  if (leftMetrics.netReturn !== rightMetrics.netReturn) {
    return rightMetrics.netReturn - leftMetrics.netReturn;
  }
  if (leftMetrics.maxDrawdown !== rightMetrics.maxDrawdown) {
    return leftMetrics.maxDrawdown - rightMetrics.maxDrawdown;
  }
  if ((leftMetrics.vsBuyHold ?? 0) !== (rightMetrics.vsBuyHold ?? 0)) {
    return (rightMetrics.vsBuyHold ?? 0) - (leftMetrics.vsBuyHold ?? 0);
  }
  return right.id - left.id;
}

function reportDetailAsSummary(report: ReportDetail): ReportSummary {
  return {
    id: report.id,
    job_id: report.job_id,
    symbol: report.symbol,
    name: report.name,
    interval: report.interval,
    strategy_kind: report.strategy_kind,
    report_name: report.report_name,
    dataset_start: report.dataset_start,
    dataset_end: report.dataset_end,
    created_at: report.created_at,
    summary_metrics: report.summary_metrics,
  };
}

function buildPeerComparisonInsight(report: ReportDetail, reports: ReportSummary[]): PeerComparisonInsight | null {
  const currentSummary = reportDetailAsSummary(report);
  const universe = reports.some((item) => item.id === report.id) ? reports : [currentSummary, ...reports];
  const peers = universe.filter((item) => item.symbol === report.symbol && item.interval === report.interval);
  if (peers.length <= 1) {
    return null;
  }

  const sortedPeers = [...peers].sort(comparePeerReports);
  const currentRank = sortedPeers.findIndex((item) => item.id === report.id) + 1;
  if (currentRank <= 0) {
    return null;
  }

  const sameStrategyPeers = sortedPeers.filter((item) => item.strategy_kind === report.strategy_kind);
  const sameStrategyRank = sameStrategyPeers.findIndex((item) => item.id === report.id) + 1;
  const bestAlternativePeer = sortedPeers.find((item) => item.id !== report.id && item.strategy_kind !== report.strategy_kind) ?? sortedPeers.find((item) => item.id !== report.id) ?? null;
  const bestSameStrategyPeer = sameStrategyPeers[0] ?? null;
  const currentMetrics = getValidationMetrics(currentSummary);

  let headline = `同标的同周期共有 ${sortedPeers.length} 份结果，当前这份处于中游`;
  let description = "这组横向定位按是否有成交、验证收益、最大回撤和相对买入持有的表现综合排序，目的是先判断当前配置值不值得继续投入时间。";
  if (currentRank === 1) {
    headline = `同标的同周期共有 ${sortedPeers.length} 份结果，当前这份排在最前`;
    description = currentMetrics.closedTrades > 0
      ? "当前结果已经是这组样本里最值得先复盘的候选。下一步应优先确认它领先的原因，避免只看到单次好运。"
      : "虽然当前排在最前，但这通常只是因为可比较样本很少。应继续补更多同标的报告，避免过早下结论。";
  } else if (currentRank <= Math.min(3, sortedPeers.length)) {
    headline = `同标的同周期共有 ${sortedPeers.length} 份结果，当前这份已经进入前列`;
    description = "当前结果已经值得纳入重点复盘对象，但还需要和领先样本并排比较，确认差距究竟来自收益、回撤还是交易频率。";
  } else if (currentRank > Math.ceil(sortedPeers.length / 2)) {
    headline = `同标的同周期共有 ${sortedPeers.length} 份结果，当前这份暂时落后`;
    description = "当前结果更适合作为反向对照。与其继续单看细节，不如直接和领先样本对比，找出差距是出在策略方向还是参数设定。";
  }

  const recommendedCompareIds = [bestAlternativePeer?.id, bestSameStrategyPeer?.id]
    .filter((value): value is number => typeof value === "number" && value !== report.id)
    .filter((value, index, values) => values.indexOf(value) === index)
    .slice(0, 3);

  return {
    headline,
    description,
    guides: [
      {
        title: "当前排位",
        value: `第 ${currentRank} / ${sortedPeers.length} 名`,
        description:
          currentRank === 1
            ? "在同标的、同周期结果里，当前这份综合位置最高。"
            : `同组里还有 ${currentRank - 1} 份结果排在它前面，建议优先看这些样本为什么更靠前。`,
      },
      {
        title: "同策略位置",
        value:
          sameStrategyPeers.length <= 1
            ? "当前仅此一份"
            : `第 ${sameStrategyRank} / ${sameStrategyPeers.length} 名`,
        description:
          sameStrategyPeers.length <= 1
            ? "当前标的和周期下还没有其他同策略样本，后续可以继续补同策略不同模板或参数范围的对照。"
            : sameStrategyRank === 1
              ? "在同策略结果里已经是当前最优样本，下一步更适合拿去和其他策略比较。"
              : "同策略内部还有更好的样本，先确认差距来自模板、参数，还是市场阶段。 ",
      },
      {
        title: "最该马上对比",
        value:
          bestAlternativePeer === null
            ? "暂无其他候选"
            : `${strategyLabel(bestAlternativePeer.strategy_kind)} / 编号 ${bestAlternativePeer.id}`,
        description:
          bestAlternativePeer === null
            ? "当前还没有其他同标的候选结果，建议先回到结果库补更多对照样本。"
            : `这份结果是当前最适合并排看的参照。它的验证收益 ${getValidationMetrics(bestAlternativePeer).netReturn.toFixed(2)}%，最大回撤 ${getValidationMetrics(bestAlternativePeer).maxDrawdown.toFixed(2)}%。`,
      },
      {
        title: "当前最该问的问题",
        value:
          currentRank === 1
            ? "领先是否稳定"
            : currentRank <= Math.min(3, sortedPeers.length)
              ? "差距能否补齐"
              : "是否该换方向",
        description:
          currentRank === 1
            ? "先确认领先是否来自更高收益、较低回撤，还是仅仅因为样本数还不够。"
            : currentRank <= Math.min(3, sortedPeers.length)
              ? "重点看领先样本是不是只多赚了一点，还是在收益、回撤、交易活跃度上都明显更好。"
              : "重点判断当前策略逻辑是否不适合这个标的，避免只在参数上反复微调。",
      },
    ],
    recommendedCompareIds,
  };
}

function formatCurveTime(value: string): string {
  return value.replace("T", " ").slice(0, 16);
}

function formatSignedPercent(value: number): string {
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function buildCurveReading(points: CurvePoint[], netReturn: number, maxDrawdown: number, closedTrades: number) {
  if (points.length === 0) {
    return null;
  }

  const startPoint = points[0];
  const endPoint = points[points.length - 1];
  const highestEquityPoint = points.reduce((best, item) => (item.equity > best.equity ? item : best), startPoint);
  const worstDrawdownPoint = points.reduce((best, item) => (Math.abs(item.drawdown_pct) > Math.abs(best.drawdown_pct) ? item : best), startPoint);
  const flatCurve =
    Math.abs(endPoint.return_pct - startPoint.return_pct) < 0.2 &&
    Math.abs(worstDrawdownPoint.drawdown_pct) < 0.2 &&
    Math.abs((highestEquityPoint.equity - startPoint.equity) / Math.max(startPoint.equity, 1)) < 0.002;

  let headline = "观察顺序：先判断权益曲线方向，再评估回撤深度";
  let description = `单独验证从 ${formatCurveTime(startPoint.curve_time)} 跑到 ${formatCurveTime(endPoint.curve_time)}，账户最终停在 ${Math.round(endPoint.equity).toLocaleString()}。`;

  if (closedTrades === 0 || flatCurve) {
    headline = "这张图几乎是一条平线，重点不是走势判断，而是确认为何没有成交";
    description = `从 ${formatCurveTime(startPoint.curve_time)} 到 ${formatCurveTime(endPoint.curve_time)}，账户权益几乎停在 ${Math.round(endPoint.equity).toLocaleString()}。这和“没有触发交易”一致，优先回去换标的、周期或参数。`;
  } else if (netReturn > 0 && maxDrawdown <= 8) {
    headline = "权益曲线整体抬升，且回撤线未长时间停留在深回撤区间";
    description = `这类曲线通常说明收益和波动比较平衡。先确认高点后的回落是否还能接受，再拿去和同标的其他策略对比。`;
  } else if (netReturn > 0) {
    headline = "权益曲线最终向上，但中途回撤较深";
    description = "这类曲线不是不能用，而是要重点看赚钱主要集中在哪一段，以及红线是否长时间贴着深回撤区域。";
  } else {
    headline = "权益曲线未形成稳定上升趋势，应先确认亏损集中区间";
    description = "如果亏损主要集中在少数几段行情，就优先换模板或周期重跑；如果全程都偏弱，说明这套组合本身不适合当前样本。";
  }

  return {
    headline,
    description,
    guides: [
      {
        title: "整体走势",
        value: flatCurve ? "几乎走平" : netReturn > 0 ? "整体向上" : "整体走弱",
        description: flatCurve
          ? `期末收益 ${formatSignedPercent(netReturn)}，蓝线几乎没有离开初始资金线。`
          : `账户权益从 ${Math.round(startPoint.equity).toLocaleString()} 走到 ${Math.round(endPoint.equity).toLocaleString()}，期末收益 ${formatSignedPercent(netReturn)}。`,
      },
      {
        title: "最该留意的时点",
        value: flatCurve ? "几乎没有波动" : formatCurveTime(highestEquityPoint.curve_time),
        description: flatCurve
          ? "高点和期末几乎重合，说明这轮单独验证没有形成可分析的趋势。"
          : `最高权益出现在 ${formatCurveTime(highestEquityPoint.curve_time)}；最大回撤 ${maxDrawdown.toFixed(2)}%，最深回落出现在 ${formatCurveTime(worstDrawdownPoint.curve_time)}。`,
      },
      {
        title: "读图顺序",
        value: closedTrades === 0 ? "先确认为何未开仓" : "先判断权益，再评估回撤",
        description:
          closedTrades === 0
            ? "权益曲线不动、回撤接近 0%，说明主要问题不在止损，而在入场条件、标的活跃度或周期选择。"
            : "蓝线代表账户权益，红线代表距离阶段高点的回落幅度。应先判断收益方向，再评估中途回撤是否可接受。",
      },
    ],
  };
}

function strategyBeginnerSummary(strategyKind: string, interval: string): string {
  if (strategyKind === "dca") {
    return "用固定节奏慢慢买入，更适合长期积累和低频复盘。";
  }
  if (strategyKind === "ma_cross") {
    return "用短长均线的金叉和死叉跟随中期趋势，适合先判断这只标的更像趋势市还是震荡市。";
  }
  if (strategyKind === "macd_trend") {
    return "用 MACD 金叉和柱体转强确认动量，适合先判断这只标的的趋势延续性是否足够稳定。";
  }
  if (strategyKind === "donchian_breakout") {
    return "专门等价格突破一段时间内的高点再顺势跟随，更适合判断这只标的是否具备持续性趋势。";
  }
  if (strategyKind === "volume_breakout") {
    return "不仅要等价格突破高点，还要求成交量同步放大，更适合判断突破是否有资金参与确认。";
  }
  if (strategyKind === "bollinger_reversion") {
    return "专门等价格跌到布林带下轨附近再尝试回归，适合先判断这只标的更像震荡市还是单边市。";
  }
  if (strategyKind === "daily_rebound") {
    return "专门找日线级别的超跌反弹，适合慢节奏观察阶段性拐点。";
  }
  if (strategyKind === "minute_rebound" || strategyKind === "minute_rebound_with_fade_filter") {
    return interval === "1m"
      ? "盯分钟级急跌后的短线反抽，节奏快，通常更适合已经能接受频繁波动的人。"
      : "盯短线快速回落后的反弹机会，适合想做日内到短波段试验的人。";
  }
  if (strategyKind === "minute_index_grid_retrace") {
    return "围绕指数 ETF 的回落反弹做分层试探，更强调分批进出和节奏控制。";
  }
  return "这套配置会按固定规则寻找可重复的进出场机会，重点不在猜消息，而在验证规则是否稳定。";
}

function rerunFocusGuide(strategyKind: string): string {
  if (strategyKind === "dca") {
    return "优先改定投频率、每期金额和最大仓位。";
  }
  if (strategyKind === "ma_cross") {
    return "优先改短长均线窗口，以及金叉确认时的信号缓冲比例。";
  }
  if (strategyKind === "macd_trend") {
    return "优先改快慢线窗口、信号线窗口、柱体确认阈值，以及固定止损比例。";
  }
  if (strategyKind === "donchian_breakout") {
    return "优先改突破窗口、退出窗口、突破确认比例，以及固定止损阈值。";
  }
  if (strategyKind === "volume_breakout") {
    return "优先改突破窗口、成交量均值窗口、放量倍数，以及退出窗口和固定止损阈值。";
  }
  if (strategyKind === "bollinger_reversion") {
    return "优先改布林带窗口、带宽、RSI 入场阈值，以及止盈止损和最长持仓时长。";
  }
  if (strategyKind === "daily_rebound") {
    return "优先改入场阈值、止盈止损和最长持有时间。";
  }
  if (strategyKind === "minute_rebound" || strategyKind === "minute_rebound_with_fade_filter") {
    return "优先改入场跌幅、RSI 条件和最大持仓 K 线数。";
  }
  if (strategyKind === "minute_index_grid_retrace" || strategyKind === "grid") {
    return "优先改网格间距、层数和止盈节奏。";
  }
  return "优先改入场条件和风险控制参数。";
}

function buildParameterHighlights(
  report: ReportDetail,
  templateSnapshot: Record<string, unknown> | undefined,
  netReturn: number,
  maxDrawdown: number,
  closedTrades: number,
): ParameterHighlight[] {
  const parameters = report.parameters;
  const templateName = String(templateSnapshot?.template_name ?? strategyLabel(report.strategy_kind));
  const templateDescription =
    typeof templateSnapshot?.description === "string" && templateSnapshot.description.trim().length > 0
      ? templateSnapshot.description.trim()
      : strategyBeginnerSummary(report.strategy_kind, report.interval);
  const maxPositionRatio = readNumberParameter(parameters, "max_position_ratio");
  const totalCapital = readNumberParameter(parameters, "total_capital");
  const commissionBps = readNumberParameter(parameters, "commission_bps");
  const slippageBps = readNumberParameter(parameters, "slippage_bps");
  const frequency = typeof parameters.frequency === "string" ? formatScalar("frequency", parameters.frequency) : null;
  const investmentAmount = readNumberParameter(parameters, "investment_amount");
  const takeProfitPct = readNumberParameter(parameters, "take_profit_pct", "TakeProfitPct");
  const stopLossPct = readNumberParameter(parameters, "stop_loss_pct", "force_exit_loss_pct");

  let paceValue = `${report.interval} 节奏`;
  let paceDescription =
    report.interval === "1d"
      ? "更适合观察阶段性趋势与回撤，无需持续盯盘。"
      : report.interval === "15m"
        ? "属于中短线节奏，通常一天内会比日线更容易触发交易。"
        : "节奏很快，更适合已经接受高频波动和更密集信号的人。";
  if (report.strategy_kind === "dca" && frequency) {
    paceValue = `${frequency} 定投`;
    paceDescription = investmentAmount
      ? `每次计划投入 ${formatMoney(investmentAmount)}，节奏比择时交易更稳定，重点看长期执行是否舒服。`
      : "这套定投更强调固定节奏执行，而不是短线择时。";
  } else if (closedTrades === 0) {
    paceDescription += " 这次没有成交，说明当前节奏和入场条件还没有对上样本里的行情。";
  } else if (closedTrades <= 3) {
    paceDescription += " 这次触发次数不多，更适合把它当成偏谨慎的配置。";
  } else {
    paceDescription += ` 这次单独验证已经触发 ${closedTrades} 笔成交，说明它并不是只会长期空转。`;
  }

  let riskValue = "仓位与成本约束";
  const riskParts: string[] = [];
  if (totalCapital !== null) {
    riskParts.push(`初始资金约 ${formatMoney(totalCapital)}`);
  }
  if (maxPositionRatio !== null) {
    riskParts.push(`最多使用 ${(maxPositionRatio * 100).toFixed(0)}% 仓位`);
  }
  if (riskParts.length > 0) {
    riskValue = riskParts.join(" / ");
  }
  const costParts: string[] = [];
  if (commissionBps !== null) {
      costParts.push(`佣金万分之 ${commissionBps}`);
  }
  if (slippageBps !== null) {
      costParts.push(`滑点万分之 ${slippageBps}`);
  }
  let riskDescription = costParts.length > 0 ? `成交假设按 ${costParts.join("，")} 计入。` : "这份报告没有额外展示成交成本假设。";
  if (takeProfitPct !== null || stopLossPct !== null) {
    const bounds: string[] = [];
    if (takeProfitPct !== null) {
      bounds.push(`止盈 ${formatScalar("take_profit_pct", takeProfitPct)}`);
    }
    if (stopLossPct !== null) {
      bounds.push(`止损 ${formatScalar("stop_loss_pct", stopLossPct)}`);
    }
    riskDescription += ` 当前还带有 ${bounds.join("，")} 这类风险边界。`;
  }

  let rerunValue = "先去做对比";
  let rerunDescription = "这份结果已经够完整，先和同标的其他报告对比，再决定值不值得改参数。";
  if (closedTrades === 0) {
    rerunValue = "先放宽触发条件";
    rerunDescription = `这次最大的信号是“没有成交”。${rerunFocusGuide(report.strategy_kind)} 先让策略真正触发，再讨论优不优秀。`;
  } else if (netReturn > 0 && maxDrawdown > 8) {
    rerunValue = "先压回撤";
    rerunDescription = `这次已经赚到钱，但回撤有 ${maxDrawdown.toFixed(2)}%。${rerunFocusGuide(report.strategy_kind)} 如果能接受收益稍降，优先换更稳的配置。`;
  } else if (netReturn <= 0) {
    rerunValue = "先换模板或周期";
    rerunDescription = `这次单独验证收益为 ${netReturn.toFixed(2)}%。${rerunFocusGuide(report.strategy_kind)} 如果连续几次都偏弱，就优先换周期或模板而不是死磕同一组数字。`;
  }

  return [
    {
      title: "模板定位",
      value: templateName,
      description: templateDescription,
    },
    {
      title: "交易节奏",
      value: paceValue,
      description: paceDescription,
    },
    {
      title: "仓位与成本",
      value: riskValue,
      description: riskDescription,
    },
    {
      title: "如果要重跑",
      value: rerunValue,
      description: rerunDescription,
    },
  ];
}

export function ReportDetailView({ reportId }: ReportDetailViewProps) {
  const [report, setReport] = useState<ReportDetail | null>(null);
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [partialError, setPartialError] = useState<string | null>(null);

  const loadReportDetail = useCallback(async () => {
    const detailResult = await apiFetchSafe<ReportDetail>(`/api/reports/${reportId}`);
    if (detailResult.ok) {
      setReport(detailResult.data);
      setLoadError(null);
    } else {
      setLoadError(detailResult.error.message);
      return;
    }

    const reportsResult = await apiFetchSafe<ReportSummary[]>("/api/reports?limit=200");
    if (reportsResult.ok) {
      setReports(reportsResult.data);
      setPartialError(null);
    } else {
      setReports([]);
      setPartialError(`同标的对比列表读取失败：${reportsResult.error.message}`);
    }
  }, [reportId]);

  useEffect(() => {
    queueMicrotask(() => {
      void loadReportDetail();
    });
  }, [loadReportDetail]);

  if (!report) {
    if (loadError) {
      return <PageErrorState title="报告详情暂时不可用" description={loadError} onRetry={() => void loadReportDetail()} />;
    }
    return <Skeleton active paragraph={{ rows: 12 }} />;
  }

  const validation = report.summary_metrics.validation ?? {};
  const templateSnapshot = report.artifacts.template_snapshot as Record<string, unknown> | undefined;
  const netReturn = Number(validation.NetReturnPct ?? validation.ReturnPct ?? 0);
  const maxDrawdown = Number(validation.MaxDrawdownPct ?? 0);
  const closedTrades = Number(validation.ClosedTrades ?? 0);
  const finalEquity = Number(validation.FinalEquity ?? 0);
  const vsBuyHold = readNumberMetric(validation, "StrategyVsBuyHold", "GridVsBuyHold");
  const verdict = buildVerdict(netReturn, maxDrawdown, closedTrades);
  const returnTone = netReturn > 0 ? "positive" : netReturn < 0 ? "negative" : undefined;
  const vsBuyHoldTone = vsBuyHold === null ? undefined : vsBuyHold > 0 ? "positive" : vsBuyHold < 0 ? "negative" : undefined;
  const templateId = readTemplateId(report, templateSnapshot);
  const rerunHref = buildBacktestLaunchHref({
    symbol: report.symbol,
    interval: report.interval,
    strategyKind: report.strategy_kind,
    templateId,
  });
  const peerComparison = buildPeerComparisonInsight(report, reports);
  const compareHref = buildCompareHref(report);
  const recommendedCompareHref = buildCompareHrefWithPeers(report, peerComparison?.recommendedCompareIds ?? []);
  const curveReading = buildCurveReading(report.equity_curve, netReturn, maxDrawdown, closedTrades);
  const parameterHighlights = buildParameterHighlights(report, templateSnapshot, netReturn, maxDrawdown, closedTrades);
  const templateName = String(templateSnapshot?.template_name ?? "未记录模板");
  const decisionSummary = buildDecisionSummary({ netReturn, maxDrawdown, closedTrades, vsBuyHold });
  const nextAction = nextActionGuide(netReturn, maxDrawdown, closedTrades);
  const decisionGuides = [
    riskGuide(maxDrawdown),
    benchmarkGuide(validation),
    tradeGuide(closedTrades, validation),
    nextAction,
  ];

  return (
    <div className="page-stack">
      {partialError ? <InlineErrorBanner message={partialError} onRetry={() => void loadReportDetail()} retryLabel="重新读取对比列表" /> : null}
      <PageHeader
        eyebrow="报告详情"
        title={`回测报告 编号 ${report.id}`}
        description={`${report.symbol} / ${report.interval} / ${strategyLabel(report.strategy_kind)}`}
        actions={
          <Space wrap>
            <Button>
              <Link href="/reports">回到报告列表</Link>
            </Button>
          </Space>
        }
      />

      <Card size="small" className="section-card report-decision-card">
        <div className="report-decision-main">
          <div className="report-decision-tags">
            <Tag color={verdict.color}>{verdict.label}</Tag>
            <Tag>{strategyLabel(report.strategy_kind)}</Tag>
            <Tag>{report.interval}</Tag>
            <Tag>{templateName}</Tag>
          </div>
          <Typography.Title level={3}>
            当前结论：这套策略在验证区间里 {netReturn >= 0 ? "赚了" : "亏了"} {Math.abs(netReturn).toFixed(2)}%，{decisionSummary.title}
          </Typography.Title>
          <Typography.Paragraph>
            {verdict.summary} {decisionSummary.description}
          </Typography.Paragraph>
          <div className="report-decision-metric-grid">
            <DetailItem label="单独验证收益" value={<FormatPercent value={netReturn} />} tone={returnTone} />
            <DetailItem label="最大回撤" value={`${maxDrawdown.toFixed(2)}%`} tone={maxDrawdown > 0 ? "negative" : undefined} />
            <DetailItem label="期末权益" value={finalEquity > 0 ? formatMoney(finalEquity) : "-"} tone={returnTone} />
            <DetailItem
              label="相对买入持有"
              value={vsBuyHold === null ? "-" : `${vsBuyHold >= 0 ? "+" : "-"}${Math.abs(vsBuyHold).toFixed(2)}`}
              tone={vsBuyHoldTone}
            />
          </div>
          <div className="report-decision-guide-grid">
            {decisionGuides.map((item) => (
              <article key={item.title} className="report-decision-guide-card">
                <span>{item.title}</span>
                <strong>{item.value}</strong>
                <p>{item.description}</p>
              </article>
            ))}
          </div>
        </div>
        <div className="report-decision-side">
          <div className="report-decision-side-card">
            <span>这次回测是什么</span>
            <strong>{report.symbol} / {strategyLabel(report.strategy_kind)} / {report.interval}</strong>
            <p>{strategyBeginnerSummary(report.strategy_kind, report.interval)}</p>
            <div className="report-decision-side-list">
              <span>样本区间：{report.dataset_start} 至 {report.dataset_end}</span>
              <span>报告时间：{report.created_at}</span>
              <span>成交笔数：{closedTrades}</span>
            </div>
          </div>
          <div className="report-decision-side-card">
            <span>现在最合适的动作</span>
            <strong>{nextAction.value}</strong>
            <p>{nextAction.description}</p>
          </div>
          {peerComparison ? (
            <div className="report-decision-side-card">
              <span>同标的横向位置</span>
              <strong>{peerComparison.guides[0]?.value ?? "暂无可比样本"}</strong>
              <p>{peerComparison.description}</p>
            </div>
          ) : null}
          <div className="report-decision-actions">
            <Button type="primary">
              <Link href={peerComparison ? recommendedCompareHref : compareHref}>{peerComparison ? "带上最该比的结果继续判断" : "带入对比区继续判断"}</Link>
            </Button>
            <Button>
              <Link href={rerunHref}>按当前配置重跑</Link>
            </Button>
            <Button>
              <Link href="/reports">回到结果库</Link>
            </Button>
          </div>
        </div>
      </Card>

      {peerComparison ? (
        <Card size="small" title="同标的横向定位" className="section-card">
          <div className="curve-reading-banner">
            <strong>{peerComparison.headline}</strong>
            <p>{peerComparison.description}</p>
          </div>
          <div className="report-decision-guide-grid">
            {peerComparison.guides.map((item) => (
              <article key={item.title} className="report-decision-guide-card">
                <span>{item.title}</span>
                <strong>{item.value}</strong>
                <p>{item.description}</p>
              </article>
            ))}
          </div>
          <div className="report-decision-actions">
            <Button type="primary">
              <Link href={recommendedCompareHref}>把这几份带去对比</Link>
            </Button>
            <Button>
              <Link href={compareHref}>只带当前结果去结果库</Link>
            </Button>
          </div>
        </Card>
      ) : null}

      <Card size="small" title="结果背景" className="section-card">
        <div className="detail-grid">
          <DetailItem label="标的" value={`${report.symbol} ${report.name}`} />
          <DetailItem label="策略" value={strategyLabel(report.strategy_kind)} />
          <DetailItem label="周期" value={report.interval} />
          <DetailItem label="使用模板" value={templateName} />
          <DetailItem label="这次用到的行情区间" value={`${report.dataset_start} 至 ${report.dataset_end}`} />
          <DetailItem label="报告生成时间" value={report.created_at} />
        </div>
      </Card>

      <Card size="small" title="净值与回撤" className="section-card">
        {report.equity_curve.length === 0 || !curveReading ? (
          <Empty description="无净值数据" />
        ) : (
          <div className="curve-reading-stack">
            <div className="curve-reading-banner">
              <strong>{curveReading.headline}</strong>
              <p>{curveReading.description}</p>
            </div>
            <div className="curve-reading-grid">
              {curveReading.guides.map((item) => (
                <article key={item.title} className="curve-reading-card">
                  <span>{item.title}</span>
                  <strong>{item.value}</strong>
                  <p>{item.description}</p>
                </article>
              ))}
            </div>
            <div className="curve-legend-note">
              <strong>图例说明：</strong>
              <span>蓝线表示账户权益，绿线表示累计收益率，红线表示距离阶段高点的回落幅度。建议先判断权益方向，再确认回撤线是否长时间停留在深回撤区域。</span>
            </div>
            <EquityChart points={report.equity_curve} />
          </div>
        )}
      </Card>

      <Card size="small" title="配置解读" className="section-card">
        <div className="parameter-summary-banner">
          <strong>优先理解模板定位、交易节奏与风险假设，无需先通读全部参数名</strong>
          <p>对结果复盘而言，通常应先理解四件事：策略试图捕捉什么行情、以怎样的节奏交易、最大仓位约束如何设定，以及重跑时应优先调整哪一类参数。</p>
        </div>
        <div className="parameter-summary-grid">
          {parameterHighlights.map((item) => (
            <article key={item.title} className="parameter-summary-card">
              <span>{item.title}</span>
              <strong>{item.value}</strong>
              <p>{item.description}</p>
            </article>
          ))}
        </div>
        <div className="parameter-advanced-hint">
          <strong>只有在需要核对模板来源或逐项排查参数时，再展开下面这块</strong>
          <p>如果当前目标只是判断该结果是否值得继续研究，上方四张解释卡与收益、回撤、成交情况通常已经足够。</p>
        </div>
        <Collapse
          className="advanced-trace-panel"
          ghost
          items={[
            {
              key: "parameters",
              label: (
                <div className="advanced-trace-label">
                  <strong>排查细节时，再看全部参数和模板来源</strong>
                  <span>这里主要用来核对模板快照、逐字段比对和排查为什么这次结果和预期不同。</span>
                </div>
              ),
              children: (
                <div className="parameter-advanced-stack">
                  <div className="parameter-advanced-section">
                    <strong>全部参数</strong>
                    <Descriptions size="small" column={{ xs: 1, sm: 2, lg: 3 }}>
                      {Object.entries(report.parameters).map(([key, value]) => (
                        <Descriptions.Item key={key} label={parameterLabel(report.strategy_kind, key)}>
                          {formatParameterValue(report.strategy_kind, key, value)}
                        </Descriptions.Item>
                      ))}
                    </Descriptions>
                  </div>
                  {templateSnapshot ? (
                    <div className="parameter-advanced-section">
                      <strong>模板来源快照</strong>
                      {typeof templateSnapshot.description === "string" && templateSnapshot.description.trim().length > 0 ? (
                        <Typography.Paragraph>{templateSnapshot.description.trim()}</Typography.Paragraph>
                      ) : null}
                      <Descriptions size="small" column={{ xs: 1, sm: 2, lg: 3 }}>
                        <Descriptions.Item label="使用模板">{String(templateSnapshot.template_name ?? "-")}</Descriptions.Item>
                        <Descriptions.Item label="策略">{strategyLabel(String(templateSnapshot.strategy_kind ?? report.strategy_kind))}</Descriptions.Item>
                        <Descriptions.Item label="周期">{String(templateSnapshot.interval ?? "-")}</Descriptions.Item>
                        <Descriptions.Item label="默认模板">{Boolean(templateSnapshot.is_default) ? "是" : "否"}</Descriptions.Item>
                        <Descriptions.Item label="模板标识">{String(templateSnapshot.template_key ?? "-")}</Descriptions.Item>
                        <Descriptions.Item label="模板编号">{String(templateSnapshot.id ?? "-")}</Descriptions.Item>
                      </Descriptions>
                    </div>
                  ) : null}
                </div>
              ),
            },
          ]}
        />
      </Card>

      <Card size="small" title="交易记录" className="section-card">
        <div className="detail-secondary-hint">
          <strong>如果当前只需判断该配置是否值得继续研究，前面的收益、回撤与成交笔数通常已经足够</strong>
          <p>只有在需要核对具体成交点位、费用开销，或确认策略是否按预期节奏执行时，再展开下面这块。</p>
        </div>
        {report.trades.length === 0 ? (
          <Empty description="本次未形成逐笔成交记录" />
        ) : (
          <Collapse
            className="advanced-trace-panel"
            ghost
            items={[
              {
                key: "trades",
                label: (
                  <div className="advanced-trace-label">
                    <strong>逐笔明细：成交记录与费用结构</strong>
                    <span>展开后会看到前 10 条交易卡片和完整分页表，适合核对成交时间、价格、数量、费用与备注。</span>
                  </div>
                ),
                children: (
                  <>
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
                  </>
                ),
              },
            ]}
          />
        )}
      </Card>

      <Card size="small" title="事件流水" className="section-card">
        <div className="detail-secondary-hint">
          <strong>如果已经确认收益与回撤特征，事件流水通常无需立即细看</strong>
          <p>只有在需要追溯“为何开仓”“为何未成交”或“为何触发停手”时，再展开下方信号明细。</p>
        </div>
        {report.events.length === 0 ? (
          <Empty description="本次没有额外事件记录" />
        ) : (
          <Collapse
            className="advanced-trace-panel"
            ghost
            items={[
              {
                key: "events",
                label: (
                  <div className="advanced-trace-label">
                    <strong>信号明细：事件触发与附加说明</strong>
                    <span>展开后会看到前 10 条事件卡片和完整分页表，适合核对触发价格、事件类型与 payload 说明。</span>
                  </div>
                ),
                children: (
                  <>
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
                  </>
                ),
              },
            ]}
          />
        )}
      </Card>
    </div>
  );
}
