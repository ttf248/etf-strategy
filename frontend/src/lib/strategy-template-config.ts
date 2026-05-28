export const intervalOptions = ["1d", "15m", "1m"].map((item) => ({ label: item, value: item }));

export const strategyOptions = [
  { label: "网格", value: "grid" },
  { label: "定投", value: "dca" },
  { label: "双均线趋势", value: "ma_cross" },
  { label: "布林带均值回归", value: "bollinger_reversion" },
  { label: "日线超跌反弹", value: "daily_rebound" },
  { label: "分钟急跌反抽", value: "minute_rebound" },
  { label: "分钟反抽+冲高回落过滤", value: "minute_rebound_with_fade_filter" },
  { label: "指数回落反弹网格", value: "minute_index_grid_retrace" },
];

export type ParameterFieldSpec = {
  key: string;
  label: string;
  kind: "int" | "float" | "string";
};

const gridDefaults = {
  "1d": {
    spacings: [0.03, 0.04, 0.05, 0.06, 0.07],
    grid_counts: [4, 5, 6, 7],
    take_profits: [0.03, 0.05, 0.07],
  },
  intraday: {
    spacings: [0.01, 0.015, 0.02, 0.03, 0.04],
    grid_counts: [4, 5, 6, 7],
    take_profits: [0.01, 0.015, 0.02, 0.03],
  },
};

const strategyDefaults: Record<string, Record<string, number[]>> = {
  dca: {
    investment_amount: [5000, 10000],
    max_position_ratio: [0.95],
  },
  ma_cross: {
    short_window: [5, 10, 20],
    long_window: [20, 30, 60],
    signal_buffer_pct: [0, 0.002, 0.005],
  },
  bollinger_reversion: {
    ma_window: [10, 20],
    band_width: [1.5, 2, 2.5],
    rsi_entry: [25, 30, 35],
    take_profit_pct: [3, 5, 8],
    stop_loss_pct: [4, 6, 8],
    max_hold_bars: [5, 8, 10],
  },
  daily_rebound: {
    rsi_window: [6, 8, 10, 14],
    rsi_entry: [20, 25, 30, 35],
    ma_window: [10, 20],
    deviation_entry_pct: [-8, -6, -4],
    take_profit_pct: [3, 5, 8],
    stop_loss_atr: [1.5, 2, 2.5],
    max_hold_bars: [5, 8, 10],
  },
  minute_rebound: {
    lookback_bars: [8, 12],
    drop_entry_pct: [-2, -1.5],
    rsi_entry: [20, 25],
    take_profit_pct: [0.6, 0.8, 1],
    stop_loss_pct: [0.8, 1],
    max_hold_bars: [4, 8],
  },
  minute_rebound_with_fade_filter: {
    lookback_bars: [8, 12],
    drop_entry_pct: [-2, -1.5],
    rsi_entry: [20, 25],
    take_profit_pct: [0.6, 0.8, 1],
    stop_loss_pct: [0.8, 1],
    max_hold_bars: [4, 8],
    fade_filter_upper_shadow_pct: [1, 1.5],
    fade_filter_block_bars: [2],
  },
  minute_index_grid_retrace: {},
};

const stringStrategyDefaults: Record<string, Record<string, string[]>> = {
  dca: {
    frequency: ["weekly", "monthly"],
    day_rule: ["first_trading_day"],
  },
};

export const parameterFieldSpecsByStrategy: Record<string, ParameterFieldSpec[]> = {
  grid: [
    { key: "spacings", label: "网格间距", kind: "float" },
    { key: "grid_counts", label: "网格层数", kind: "int" },
    { key: "take_profits", label: "止盈比例", kind: "float" },
  ],
  dca: [
    { key: "investment_amount", label: "每期金额", kind: "float" },
    { key: "frequency", label: "定投频率", kind: "string" },
    { key: "day_rule", label: "触发日规则", kind: "string" },
    { key: "max_position_ratio", label: "最大仓位", kind: "float" },
  ],
  ma_cross: [
    { key: "short_window", label: "短均线窗口", kind: "int" },
    { key: "long_window", label: "长均线窗口", kind: "int" },
    { key: "signal_buffer_pct", label: "信号缓冲比例", kind: "float" },
  ],
  bollinger_reversion: [
    { key: "ma_window", label: "布林带窗口", kind: "int" },
    { key: "band_width", label: "布林带宽度", kind: "float" },
    { key: "rsi_entry", label: "RSI 入场", kind: "float" },
    { key: "take_profit_pct", label: "止盈比例", kind: "float" },
    { key: "stop_loss_pct", label: "止损比例", kind: "float" },
    { key: "max_hold_bars", label: "最大持仓 K 线数", kind: "int" },
  ],
  daily_rebound: [
    { key: "rsi_window", label: "RSI 窗口", kind: "int" },
    { key: "rsi_entry", label: "RSI 入场", kind: "float" },
    { key: "ma_window", label: "均线窗口", kind: "int" },
    { key: "deviation_entry_pct", label: "偏离入场", kind: "float" },
    { key: "take_profit_pct", label: "止盈比例", kind: "float" },
    { key: "stop_loss_atr", label: "ATR 止损", kind: "float" },
    { key: "max_hold_bars", label: "最大持仓 K 线数", kind: "int" },
  ],
  minute_rebound: [
    { key: "lookback_bars", label: "回看 K 线数", kind: "int" },
    { key: "drop_entry_pct", label: "跌幅入场", kind: "float" },
    { key: "rsi_entry", label: "RSI 入场", kind: "float" },
    { key: "take_profit_pct", label: "止盈比例", kind: "float" },
    { key: "stop_loss_pct", label: "止损比例", kind: "float" },
    { key: "max_hold_bars", label: "最大持仓 K 线数", kind: "int" },
  ],
  minute_rebound_with_fade_filter: [
    { key: "lookback_bars", label: "回看 K 线数", kind: "int" },
    { key: "drop_entry_pct", label: "跌幅入场", kind: "float" },
    { key: "rsi_entry", label: "RSI 入场", kind: "float" },
    { key: "take_profit_pct", label: "止盈比例", kind: "float" },
    { key: "stop_loss_pct", label: "止损比例", kind: "float" },
    { key: "max_hold_bars", label: "最大持仓 K 线数", kind: "int" },
    { key: "fade_filter_upper_shadow_pct", label: "上影线过滤", kind: "float" },
    { key: "fade_filter_block_bars", label: "过滤屏蔽 K 线数", kind: "int" },
  ],
  minute_index_grid_retrace: [],
};

export function buildDefaultParameterSpace(strategyKind: string, interval: string): Record<string, Array<number | string>> {
  if (strategyKind === "grid") {
    return interval === "1d" ? gridDefaults["1d"] : gridDefaults.intraday;
  }
  return { ...(strategyDefaults[strategyKind] ?? {}), ...(stringStrategyDefaults[strategyKind] ?? {}) };
}

export function encodeParameterSpace(parameterSpace: Record<string, unknown>): Record<string, string> {
  return Object.fromEntries(Object.entries(parameterSpace).map(([key, value]) => [key, Array.isArray(value) ? value.join(",") : ""]));
}

export function decodeNumericArray(raw: string, kind: "int" | "float" | "string"): Array<number | string> {
  return raw
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => (kind === "string" ? item : kind === "int" ? parseInt(item, 10) : parseFloat(item)))
    .filter((item) => (typeof item === "string" ? item.length > 0 : Number.isFinite(item)));
}

export function strategyLabel(strategyKind: string): string {
  return strategyOptions.find((item) => item.value === strategyKind)?.label ?? strategyKind;
}
