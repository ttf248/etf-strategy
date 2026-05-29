import type { MarketCoverage } from "@/lib/api";

export type BeginnerPreset = {
  symbol: string;
  name: string;
  interval: string;
  strategyKind: string;
  reason: string;
  availableIntervals: string[];
};

export type BacktestLaunchPreset = {
  symbol?: string;
  interval?: string;
  strategyKind?: string;
  templateId?: number;
  marketDataProvider?: string;
  marketDataAdjustmentKind?: string;
};

type GroupedCoverage = {
  symbol: string;
  name: string;
  availableIntervals: Set<string>;
  totalBars: number;
};

const intervalRank: Record<string, number> = { "15m": 0, "1d": 1, "1m": 2 };

function recommendedReason(group: GroupedCoverage): string {
  const hasDaily = group.availableIntervals.has("1d");
  const has15m = group.availableIntervals.has("15m");
  const has1m = group.availableIntervals.has("1m");
  if (hasDaily && has15m) {
    return "已具备日线与 15m 覆盖，可直接作为标准研究样本。";
  }
  if (has15m) {
    return "已具备 15m 覆盖，适合直接开展分钟级基线回测。";
  }
  if (hasDaily) {
    return "已具备日线覆盖，适合开展定投或日线节奏研究。";
  }
  if (has1m) {
    return "当前仅有 1m 覆盖，更适合细粒度分钟研究。";
  }
  return "已有基础覆盖，可按研究需求继续补齐更多周期。";
}

function recommendedInterval(group: GroupedCoverage): string {
  if (group.availableIntervals.has("15m")) {
    return "15m";
  }
  if (group.availableIntervals.has("1d")) {
    return "1d";
  }
  if (group.availableIntervals.has("1m")) {
    return "1m";
  }
  return Array.from(group.availableIntervals)[0] ?? "1d";
}

function recommendedStrategy(interval: string): string {
  return interval === "1d" ? "dca" : "grid";
}

function coverageScore(group: GroupedCoverage): number {
  const hasDaily = group.availableIntervals.has("1d") ? 1000 : 0;
  const has15m = group.availableIntervals.has("15m") ? 1200 : 0;
  const has1m = group.availableIntervals.has("1m") ? 100 : 0;
  return hasDaily + has15m + has1m + group.totalBars / 1000;
}

export function buildBeginnerPresets(coverages: MarketCoverage[]): BeginnerPreset[] {
  const grouped = new Map<string, GroupedCoverage>();
  for (const item of coverages) {
    const current =
      grouped.get(item.symbol) ??
      {
        symbol: item.symbol,
        name: item.name || item.symbol,
        availableIntervals: new Set<string>(),
        totalBars: 0,
      };
    current.name = current.name || item.name || item.symbol;
    current.availableIntervals.add(item.interval);
    current.totalBars += item.bar_count;
    grouped.set(item.symbol, current);
  }

  return Array.from(grouped.values())
    .filter((item) => item.availableIntervals.has("1d") || item.availableIntervals.has("15m") || item.availableIntervals.has("1m"))
    .sort((left, right) => coverageScore(right) - coverageScore(left))
    .slice(0, 3)
    .map((item) => {
      const interval = recommendedInterval(item);
      return {
        symbol: item.symbol,
        name: item.name,
        interval,
        strategyKind: recommendedStrategy(interval),
        reason: recommendedReason(item),
        availableIntervals: Array.from(item.availableIntervals).sort(
          (left, right) => (intervalRank[left] ?? 99) - (intervalRank[right] ?? 99),
        ),
      };
    });
}

export function buildBacktestPresetHref(preset: BeginnerPreset): string {
  return buildBacktestLaunchHref({
    symbol: preset.symbol,
    interval: preset.interval,
    strategyKind: preset.strategyKind,
  });
}

export function buildBacktestLaunchHref(preset: BacktestLaunchPreset): string {
  const searchParams = new URLSearchParams();
  if (preset.symbol) {
    searchParams.set("symbol", preset.symbol);
  }
  if (preset.interval) {
    searchParams.set("interval", preset.interval);
  }
  if (preset.strategyKind) {
    searchParams.set("strategy_kind", preset.strategyKind);
  }
  if (preset.templateId !== undefined) {
    searchParams.set("template_id", String(preset.templateId));
  }
  if (preset.marketDataProvider) {
    searchParams.set("market_data_provider", preset.marketDataProvider);
  }
  if (preset.marketDataAdjustmentKind) {
    searchParams.set("market_data_adjustment_kind", preset.marketDataAdjustmentKind);
  }
  return `/backtests?${searchParams.toString()}`;
}
