"use client";

import Link from "next/link";
import { Button, Card, Collapse, Descriptions, Empty, Skeleton, Space, Table, Tag, Typography } from "antd";
import { useEffect, useState } from "react";
import { apiFetch, type ReportDetail } from "@/lib/api";
import { EquityChart } from "@/components/equity-chart";
import { DetailItem, FormatPercent, PageHeader } from "@/components/platform-ui";
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

const baseParameterLabels: Record<string, string> = {
  AnchorDate: "从哪一天开始对齐",
  BaseUnits: "基础持仓份额",
  benchmark: "和谁做对照",
  Benchmark: "和谁做对照",
  commission_bps: "交易佣金",
  cooldown_bars: "停手后先等多少根 K 线",
  EndDate: "结束时间",
  EntryDate: "入场时间",
  EntryPrice: "入场时价格",
  execution_profile: "成交假设",
  force_exit_loss_pct: "达到多大亏损时强制离场",
  GridCount: "最多开几层网格",
  GridMode: "开始时先怎么买",
  jobs: "同时试几组参数",
  left_side_policy: "行情先走弱时怎么处理",
  lookback_days: "回看多少天历史",
  LotSize: "每次最少按多少份交易",
  Market: "在哪个市场交易",
  max_position_ratio: "最大仓位",
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
  Symbol: "标的代码",
  template_id: "模板编号",
  total_capital: "初始资金",
  validation_ratio: "最后留多少比例做验证",
  validation_start: "从哪一天开始单独验证",
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
  const templateId = readTemplateId(report, templateSnapshot);
  const rerunHref = buildBacktestLaunchHref({
    symbol: report.symbol,
    interval: report.interval,
    strategyKind: report.strategy_kind,
    templateId,
  });
  const compareHref = buildCompareHref(report);
  const curveReading = buildCurveReading(report.equity_curve, netReturn, maxDrawdown, closedTrades);
  const parameterHighlights = buildParameterHighlights(report, templateSnapshot, netReturn, maxDrawdown, closedTrades);
  const readingGuides = [
    {
      title: "收益判断",
      value: `${netReturn >= 0 ? "盈利" : "亏损"} ${netReturn.toFixed(2)}%`,
      description:
        netReturn > 0
          ? "应先确认这是单独验证收益，再继续评估回撤是否可接受；仅看盈利与否并不足够。"
          : "单独验证收益为负，说明该组合至少在当前测试区间内尚未证明其有效性。",
    },
    riskGuide(maxDrawdown),
    benchmarkGuide(validation),
    tradeGuide(closedTrades, validation),
    nextActionGuide(netReturn, maxDrawdown, closedTrades),
  ];

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="报告详情"
        title={`回测报告 编号 ${report.id}`}
        description={`${report.symbol} / ${report.interval} / ${strategyLabel(report.strategy_kind)}`}
        actions={
          <Space wrap>
            <Button>
              <Link href="/reports">回到报告列表</Link>
            </Button>
            <Button>
              <Link href={compareHref}>去对比同标的报告</Link>
            </Button>
            <Button type="primary">
              <Link href={rerunHref}>按当前配置重跑</Link>
            </Button>
          </Space>
        }
      />

      <Card size="small" className="section-card result-verdict-card">
        <div className="result-verdict-main">
          <Tag color={verdict.color}>{verdict.label}</Tag>
          <Typography.Title level={3}>本次回测单独验证收益为 {netReturn.toFixed(2)}%，{netReturn >= 0 ? "未出现净亏损" : "当前样本下出现亏损"}</Typography.Title>
          <Typography.Paragraph>{verdict.summary}</Typography.Paragraph>
        </div>
        <div className="result-verdict-metrics">
          <DetailItem label="单独验证收益" value={<FormatPercent value={netReturn} />} tone={returnTone} />
          <DetailItem label="最大回撤" value={`${maxDrawdown.toFixed(2)}%`} tone={maxDrawdown > 0 ? "negative" : undefined} />
          <DetailItem label="成交笔数" value={String(closedTrades)} />
        </div>
      </Card>

      <Card size="small" title="结果概览" className="section-card">
        <div className="detail-grid">
          <DetailItem label="标的" value={`${report.symbol} ${report.name}`} />
          <DetailItem label="策略" value={strategyLabel(report.strategy_kind)} />
          <DetailItem label="周期" value={report.interval} />
          <DetailItem label="这次用到的行情区间" value={`${report.dataset_start} 至 ${report.dataset_end}`} />
          <DetailItem label="报告生成时间" value={report.created_at} />
          <DetailItem label="任务编号" value={report.job_id} />
        </div>
      </Card>

      <Card size="small" title="关键指标解读" className="section-card">
        <div className="reading-guide-grid">
          {readingGuides.map((item) => (
            <article key={item.title} className="reading-guide-card">
              <span className="reading-guide-label">{item.title}</span>
              <strong>{item.value}</strong>
              <p>{item.description}</p>
            </article>
          ))}
        </div>
      </Card>

      <Card size="small" title="后续动作" className="section-card compare-next-card">
        <div className="compare-next-main">
          <strong>建议将该结果带入对比区继续验证</strong>
          <p>系统会预先带入当前报告，并按相同标的和周期筛选结果列表。继续选择 1 到 3 份报告后，即可直接比较收益、回撤和交易次数。</p>
        </div>
        <div className="compare-next-actions">
          <Button type="primary">
            <Link href={compareHref}>去对比同标的报告</Link>
          </Button>
          <Button>
            <Link href={rerunHref}>按当前配置重跑</Link>
          </Button>
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
