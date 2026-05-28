"use client";

import Link from "next/link";
import { Button, Card, Collapse, Empty, Input, Select, Skeleton, Space, Table, Tag, Typography, message } from "antd";
import { useEffect, useMemo, useState } from "react";
import { apiFetch, apiFetchSafe, type MarketCoverage, type MarketDataStats } from "@/lib/api";
import { MetricCard, PageErrorState, PageHeader, ToolbarCount } from "@/components/platform-ui";
import { intervalOptions } from "@/lib/strategy-template-config";
import { buildBacktestLaunchHref, buildBacktestPresetHref, buildBeginnerPresets } from "@/lib/beginner-presets";

type IntervalRecommendation = {
  interval: string;
  title: string;
  description: string;
};

type CoverageProfile = {
  symbol: string;
  name: string;
  intervals: Set<string>;
};

type CoverageInsight = {
  key: string;
  value: string;
  title: string;
  description: string;
  recommendation: string;
  examples: CoverageProfile[];
};

type StartDecisionCard = {
  title: string;
  value: string;
  description: string;
};

type SymbolIntervalCard = {
  interval: string;
  title: string;
  value: string;
  description: string;
  ready: boolean;
};

function coverageStage(profile: CoverageProfile) {
  const hasDaily = profile.intervals.has("1d");
  const has15m = profile.intervals.has("15m");
  if (hasDaily && has15m) {
    return 0;
  }
  if (hasDaily) {
    return 1;
  }
  return 2;
}

function compareCoverageProfile(left: CoverageProfile, right: CoverageProfile) {
  const stageDiff = coverageStage(left) - coverageStage(right);
  if (stageDiff !== 0) {
    return stageDiff;
  }
  const intervalDiff = right.intervals.size - left.intervals.size;
  if (intervalDiff !== 0) {
    return intervalDiff;
  }
  return left.symbol.localeCompare(right.symbol);
}

function buildStartDecisionCards(
  checkedSymbol: string,
  symbolRows: MarketCoverage[],
  symbolIntervals: Set<string>,
  intervalRecommendations: IntervalRecommendation[],
  readySymbolCount: number,
): StartDecisionCard[] {
  const normalizedSymbol = checkedSymbol.trim().toUpperCase();
  const hasRows = symbolRows.length > 0;
  const hasDaily = symbolIntervals.has("1d");
  const has15m = symbolIntervals.has("15m");

  let currentDecision: StartDecisionCard;
  let nextAction: StartDecisionCard;
  let syncAllDecision: StartDecisionCard;

  if (!normalizedSymbol) {
    currentDecision = {
      title: "当前状态",
      value: "待确认目标标的",
      description: "输入目标标的代码后，页面会给出覆盖情况与补数建议，无需先浏览完整覆盖表。",
    };
    nextAction = {
      title: "建议动作",
      value: "查看推荐样本",
      description: "若暂时没有明确标的，可先使用页面中的推荐样本，再决定是否检查自定义目标。",
    };
    syncAllDecision = {
      title: "全量同步时机",
      value: "当前通常无需执行",
      description: "建立初始研究样本不需要先做全量建库。只有准备批量扩充标的池时，才需要补全部标的某个周期。",
    };
    return [currentDecision, nextAction, syncAllDecision];
  }

  if (!hasRows) {
    currentDecision = {
      title: "当前状态",
      value: `${normalizedSymbol} 尚无覆盖`,
      description: "当前还没有该标的行情，建议先补齐可用覆盖，再考虑其他标的与更多周期。",
    };
    nextAction = {
      title: "建议动作",
      value: intervalRecommendations[0]?.title ?? "先补日线",
      description: intervalRecommendations[0]?.description ?? "通常先补 1d，再按研究需求补 15m。",
    };
    syncAllDecision = {
      title: "全量同步时机",
      value: "当前不建议全量同步",
      description: "先将当前标的补到可研究状态，比先补全库更直接。只有当前标的已满足需求且准备扩大范围时，再做全量同步。",
    };
    return [currentDecision, nextAction, syncAllDecision];
  }

  if (hasDaily && has15m) {
    currentDecision = {
      title: "当前状态",
      value: `${normalizedSymbol} 可直接进入研究`,
      description: "该标的已同时具备 1d 与 15m 覆盖，足以支撑大多数基线回测场景。",
    };
    nextAction = {
      title: "建议动作",
      value: "进入回测配置",
      description: "当前应优先形成一份结果，再根据复盘结论决定是否补充更多标的或更多周期。",
    };
    syncAllDecision = {
      title: "全量同步时机",
      value: readySymbolCount > 0 ? "扩充标的池时再执行" : "当前无需执行",
      description: "只有准备批量筛选更多标的，或当前可直接研究的标的过少时，才有必要做全量同步。当前该标的已可直接开始。",
    };
    return [currentDecision, nextAction, syncAllDecision];
  }

  currentDecision = {
    title: "当前状态",
    value: `${normalizedSymbol} 覆盖仍可补强`,
    description: "该标的已具备部分数据，可支持部分策略，但尚未覆盖最常用的基线组合。",
  };
  nextAction = {
    title: "建议动作",
    value: intervalRecommendations[0]?.title ?? "先补推荐周期",
    description: intervalRecommendations[0]?.description ?? "先补齐常用周期，再返回回测配置页。",
  };
  syncAllDecision = {
    title: "全量同步时机",
    value: "当前仍应优先补齐单标的覆盖",
    description: "若当前仅研究这一只标的，补齐推荐周期即可。只有准备同步扩展更多标的时，再做全量同步。",
  };
  return [currentDecision, nextAction, syncAllDecision];
}

function buildSymbolIntervalCards(symbolIntervals: Set<string>, hasRows: boolean): SymbolIntervalCard[] {
  const cards: Array<{
    interval: string;
    title: string;
    purpose: string;
  }> = [
    {
      interval: "1d",
      title: "日线基线",
      purpose: "用于定投、日线择时和更长区间的稳健复盘。",
    },
    {
      interval: "15m",
      title: "分钟级基线",
      purpose: "用于默认网格和大多数分钟级基线策略。",
    },
    {
      interval: "1m",
      title: "更细粒度短线",
      purpose: "只有需要更高频的分钟信号时才值得补。",
    },
  ];

  return cards.map((item) => {
    if (!hasRows) {
      return {
        interval: item.interval,
        title: item.title,
        value: "尚未准备",
        description: item.purpose,
        ready: false,
      };
    }
    const ready = symbolIntervals.has(item.interval);
    return {
      interval: item.interval,
      title: item.title,
      value: ready ? "已覆盖" : "待补齐",
      description: ready ? `当前已经具备 ${item.interval}，${item.purpose}` : `当前还没有 ${item.interval}，${item.purpose}`,
      ready,
    };
  });
}

function buildPrimaryResearchPath(params: {
  checkedSymbol: string;
  hasRows: boolean;
  intervalRecommendations: IntervalRecommendation[];
  symbolIntervals: Set<string>;
}): { title: string; description: string } {
  const normalizedSymbol = params.checkedSymbol.trim().toUpperCase();
  if (!normalizedSymbol) {
    return {
      title: "先输入一个目标标的，确认它是否具备最小研究样本",
      description: "不需要先浏览全库覆盖，先把一个熟悉标的补到可研究状态更直接。",
    };
  }
  if (!params.hasRows) {
    return {
      title: `先把 ${normalizedSymbol} 补到可研究状态`,
      description: `当前还没有 ${normalizedSymbol} 行情。通常先补 ${params.intervalRecommendations[0]?.interval ?? "1d"}，再按研究需求补 ${params.intervalRecommendations[1]?.interval ?? "15m"}。`,
    };
  }
  if (params.symbolIntervals.has("1d") && params.symbolIntervals.has("15m")) {
    return {
      title: `${normalizedSymbol} 已具备最常用研究样本，可直接进入回测`,
      description: "当前更值得做的是先跑出一份结果，再根据复盘结论决定要不要补更多标的或更细周期。",
    };
  }
  return {
    title: `${normalizedSymbol} 已有部分覆盖，建议补齐常用周期后再扩大范围`,
    description: "如果你只研究这一只标的，先把日线和 15m 补齐通常比先做全量同步更有效。",
  };
}

export function MarketDataView() {
  const [stats, setStats] = useState<MarketDataStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [checkInput, setCheckInput] = useState("1810.HK");
  const [checkedSymbol, setCheckedSymbol] = useState("1810.HK");
  const [tableKeyword, setTableKeyword] = useState("");
  const [interval, setInterval] = useState<string | undefined>(undefined);
  const [syncInterval, setSyncInterval] = useState("1d");
  const [syncing, setSyncing] = useState(false);
  const [syncingSymbol, setSyncingSymbol] = useState(false);
  const [messageApi, contextHolder] = message.useMessage();

  async function loadStatsData(showSpinner: boolean = true) {
    if (showSpinner) {
      setLoading(true);
    }
    const result = await apiFetchSafe<MarketDataStats>("/api/market-data/stats");
    if (result.ok) {
      setStats(result.data);
      setLoadError(null);
    } else {
      setLoadError(result.error.message);
    }
    setLoading(false);
  }

  useEffect(() => {
    queueMicrotask(() => {
      void loadStatsData();
    });
  }, []);

  function syncPeriodForInterval(targetInterval: string) {
    return targetInterval === "15m" ? "60d" : targetInterval === "1m" ? "7d" : undefined;
  }

  async function syncAll() {
    setSyncing(true);
    try {
      await apiFetch("/api/market-data/sync", {
        method: "POST",
        body: JSON.stringify({ interval: syncInterval, period: syncPeriodForInterval(syncInterval) }),
      });
      messageApi.success("同步已完成");
      await loadStatsData(false);
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "同步失败");
    } finally {
      setSyncing(false);
    }
  }

  async function syncCheckedSymbol() {
    await syncSymbolForInterval(syncInterval);
  }

  async function syncSymbolForInterval(targetInterval: string) {
    const targetSymbol = checkedSymbol.trim().toUpperCase();
    if (!targetSymbol) {
      messageApi.warning("请先输入并检查一个标的");
      return;
    }
    setSyncingSymbol(true);
    setSyncInterval(targetInterval);
    try {
      await apiFetch("/api/market-data/sync", {
        method: "POST",
        body: JSON.stringify({ symbol: targetSymbol, interval: targetInterval, period: syncPeriodForInterval(targetInterval) }),
      });
      messageApi.success(`${targetSymbol} ${targetInterval} 同步完成`);
      await loadStatsData(false);
      setTableKeyword(targetSymbol);
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "同步失败");
    } finally {
      setSyncingSymbol(false);
    }
  }

  const filteredRows = useMemo(() => {
    if (!stats) {
      return [];
    }
    return stats.coverages.filter((item) => {
      const matchesKeyword =
        !tableKeyword ||
        item.symbol.toLowerCase().includes(tableKeyword.toLowerCase()) ||
        item.name.toLowerCase().includes(tableKeyword.toLowerCase());
      const matchesInterval = !interval || item.interval === interval;
      return matchesKeyword && matchesInterval;
    });
  }, [stats, tableKeyword, interval]);

  const beginnerPresets = useMemo(() => (stats ? buildBeginnerPresets(stats.coverages) : []), [stats]);

  const coverageProfiles = useMemo<CoverageProfile[]>(() => {
    if (!stats) {
      return [];
    }
    const grouped = new Map<string, CoverageProfile>();
    for (const item of stats.coverages) {
      const current =
        grouped.get(item.symbol) ??
        {
          symbol: item.symbol,
          name: item.name || item.symbol,
          intervals: new Set<string>(),
        };
      current.name = current.name || item.name || item.symbol;
      current.intervals.add(item.interval);
      grouped.set(item.symbol, current);
    }
    return Array.from(grouped.values());
  }, [stats]);

  const coverageInsights = useMemo<CoverageInsight[]>(() => {
    const sortedProfiles = [...coverageProfiles].sort(compareCoverageProfile);
    const readyProfiles = sortedProfiles.filter((item) => item.intervals.has("1d") && item.intervals.has("15m"));
    const dailyOnlyProfiles = sortedProfiles.filter((item) => item.intervals.has("1d") && !item.intervals.has("15m"));
    const partialProfiles = sortedProfiles.filter((item) => !item.intervals.has("1d"));

    return [
      {
        key: "ready",
        value: `${readyProfiles.length} 个`,
        title: "可直接开展研究",
        description: "同时具备 1d 和 15m，适合作为标准研究样本。",
        recommendation: "优先从这类标的中选择，不需要额外补数。",
        examples: readyProfiles.slice(0, 3),
      },
      {
        key: "daily-only",
        value: `${dailyOnlyProfiles.length} 个`,
        title: "只适合长周期",
        description: "目前只有日线，适合先做定投或日线策略验证。",
        recommendation: "可以先跑日线或定投，再决定要不要继续补 15m。",
        examples: dailyOnlyProfiles.slice(0, 3),
      },
      {
        key: "partial",
        value: `${partialProfiles.length} 个`,
        title: "还需补关键周期",
        description: "只有分钟线或缺少 1d / 15m，建议先补齐再开始。",
        recommendation: "先补 1d 或 15m，再回到创建回测页。",
        examples: partialProfiles.slice(0, 3),
      },
    ];
  }, [coverageProfiles]);
  const readySymbolCount = useMemo(
    () => coverageProfiles.filter((item) => item.intervals.has("1d") && item.intervals.has("15m")).length,
    [coverageProfiles],
  );

  const symbolRows = useMemo(() => {
    if (!stats || !checkedSymbol.trim()) {
      return [];
    }
    const normalizedKeyword = checkedSymbol.trim().toLowerCase();
    return stats.coverages.filter((item) => item.symbol.toLowerCase() === normalizedKeyword);
  }, [stats, checkedSymbol]);

  const symbolIntervals = useMemo(() => new Set(symbolRows.map((item) => item.interval)), [symbolRows]);

  const readiness = useMemo(() => {
    if (!checkedSymbol.trim()) {
      return { label: "待输入标的", color: "default", description: "例如 1810.HK、0700.HK、513050.SS。" };
    }
    if (symbolRows.length === 0) {
      return { label: "未找到覆盖", color: "red", description: "当前还没有该标的行情。可先确认代码格式，再执行同步。" };
    }
    const daily = symbolIntervals.has("1d");
    const intraday = Array.from(symbolIntervals).some((item) => item !== "1d");
    if (daily && intraday) {
      return { label: "覆盖可用", color: "green", description: "该标的已同时具备日线和分钟级数据，可直接创建回测。" };
    }
    return { label: "覆盖有限", color: "gold", description: "该标的已有部分周期数据，建议先确认策略所需周期是否齐备。" };
  }, [checkedSymbol, symbolRows, symbolIntervals]);

  const intervalRecommendations = useMemo<IntervalRecommendation[]>(() => {
    if (!checkedSymbol.trim()) {
      return [];
    }
    if (symbolRows.length === 0) {
      return [
        {
          interval: "1d",
          title: "先补日线",
          description: "建议先补 1d，用于长期回测、定投研究和基础可用性检查。",
        },
        {
          interval: "15m",
          title: "再补 15m",
          description: "若计划运行网格或短周期反弹策略，再补 15m 即可覆盖大部分分钟级研究。",
        },
      ];
    }

    const recommendations: IntervalRecommendation[] = [];
    if (!symbolIntervals.has("1d")) {
      recommendations.push({
        interval: "1d",
        title: "补日线",
        description: "补 1d 后可以做定投、日线择时和更长区间的稳健复盘。",
      });
    }
    if (!symbolIntervals.has("15m")) {
      recommendations.push({
        interval: "15m",
        title: "补 15m",
        description: "补齐 15m 后，可直接覆盖默认分钟网格与大多数分钟级基线策略。",
      });
    }
    if (symbolIntervals.has("15m") && !symbolIntervals.has("1m")) {
      recommendations.push({
        interval: "1m",
        title: "补 1m",
        description: "只有当你需要更细粒度的分钟信号时，再补 1m 做更高频的研究。",
      });
    }
    return recommendations;
  }, [checkedSymbol, symbolRows, symbolIntervals]);

  const checkedSymbolLaunchHref = useMemo(() => {
    const normalizedSymbol = checkedSymbol.trim().toUpperCase();
    if (!normalizedSymbol || symbolRows.length === 0) {
      return null;
    }
    if (symbolIntervals.has("15m")) {
      return buildBacktestLaunchHref({ symbol: normalizedSymbol, interval: "15m", strategyKind: "grid" });
    }
    if (symbolIntervals.has("1d")) {
      return buildBacktestLaunchHref({ symbol: normalizedSymbol, interval: "1d", strategyKind: "dca" });
    }
    if (symbolIntervals.has("1m")) {
      return buildBacktestLaunchHref({ symbol: normalizedSymbol, interval: "1m", strategyKind: "grid" });
    }
    return null;
  }, [checkedSymbol, symbolIntervals, symbolRows.length]);
  const startDecisionCards = useMemo(
    () => buildStartDecisionCards(checkedSymbol, symbolRows, symbolIntervals, intervalRecommendations, readySymbolCount),
    [checkedSymbol, intervalRecommendations, readySymbolCount, symbolIntervals, symbolRows],
  );
  const symbolIntervalCards = useMemo(
    () => buildSymbolIntervalCards(symbolIntervals, symbolRows.length > 0),
    [symbolIntervals, symbolRows.length],
  );
  const primaryResearchPath = useMemo(
    () =>
      buildPrimaryResearchPath({
        checkedSymbol,
        hasRows: symbolRows.length > 0,
        intervalRecommendations,
        symbolIntervals,
      }),
    [checkedSymbol, intervalRecommendations, symbolIntervals, symbolRows.length],
  );

  function applyCheckedSymbol(targetSymbol: string) {
    const normalizedSymbol = targetSymbol.trim().toUpperCase();
    setCheckInput(normalizedSymbol);
    setCheckedSymbol(normalizedSymbol);
    setTableKeyword(normalizedSymbol);
  }

  function checkSymbol() {
    applyCheckedSymbol(checkInput);
  }

  if (loading && !stats) {
    return <Skeleton active paragraph={{ rows: 10 }} />;
  }

  if (!stats) {
    return <PageErrorState title="数据准备页暂时不可用" description={loadError ?? "暂时无法读取数据覆盖状态"} onRetry={() => void loadStatsData()} />;
  }

  return (
    <div className="page-stack">
      {contextHolder}
      <PageHeader
        eyebrow="数据覆盖"
        title="数据覆盖检查"
        description="先确认目标标的是否具备可研究行情覆盖；缺少关键周期时再同步，无需先浏览全部明细。"
      />

      <Card size="small" className="section-card data-check-card">
        <div className="data-check-main">
          <Typography.Title level={4}>检查标的覆盖情况</Typography.Title>
          <Typography.Paragraph>输入 Yahoo 标的代码，系统会展示当前可用周期以及覆盖截止时间。</Typography.Paragraph>
          <Space.Compact className="data-check-input">
            <Input
              value={checkInput}
              onChange={(event) => setCheckInput(event.target.value)}
              onPressEnter={checkSymbol}
              placeholder="例如 1810.HK"
            />
            <Button type="primary" onClick={checkSymbol}>
              检查
            </Button>
          </Space.Compact>
        </div>
        <div className="data-check-result">
          <Tag color={readiness.color}>{readiness.label}</Tag>
          <strong>{symbolRows[0]?.name ?? (checkedSymbol || "等待输入")}</strong>
          {checkedSymbol ? <small>最近检查：{checkedSymbol}</small> : null}
          <span>{readiness.description}</span>
          {intervalRecommendations.length > 0 ? (
            <div className="data-recommend-list">
              {intervalRecommendations.map((item) => (
                <div key={item.interval} className="data-recommend-item">
                  <div>
                    <b>{item.title}</b>
                    <small>{item.description}</small>
                  </div>
                  <Button size="small" loading={syncingSymbol && syncInterval === item.interval} onClick={() => void syncSymbolForInterval(item.interval)}>
                    同步 {item.interval}
                  </Button>
                </div>
              ))}
            </div>
          ) : null}
          <div className="data-check-actions">
            <Button loading={syncingSymbol} onClick={() => void syncCheckedSymbol()}>
              同步当前标的 {syncInterval}
            </Button>
            <small>若不确定补数顺序，优先按上方推荐周期执行；分钟级基线研究通常先补 15m。</small>
          </div>
        </div>
      </Card>

      <Card size="small" className="section-card start-path-card">
        <div className="start-path-main">
          <strong>{primaryResearchPath.title}</strong>
          <p>{primaryResearchPath.description}</p>
          <div className="start-path-guide-grid">
            {startDecisionCards.map((item) => (
              <article key={item.title} className="start-path-guide-card">
                <span>{item.title}</span>
                <strong>{item.value}</strong>
                <p>{item.description}</p>
              </article>
            ))}
          </div>
        </div>
        <div className="start-path-actions">
          {checkedSymbolLaunchHref ? (
            <Button type="primary">
              <Link href={checkedSymbolLaunchHref}>基于当前标的创建回测</Link>
            </Button>
          ) : null}
          {beginnerPresets[0] ? (
            <Button>
              <Link href={buildBacktestPresetHref(beginnerPresets[0])}>使用推荐样本创建回测</Link>
            </Button>
          ) : null}
          {intervalRecommendations[0] ? (
            <Button loading={syncingSymbol && syncInterval === intervalRecommendations[0].interval} onClick={() => void syncSymbolForInterval(intervalRecommendations[0].interval)}>
              先补 {intervalRecommendations[0].interval}
            </Button>
          ) : null}
        </div>
      </Card>

      <Card size="small" title="当前标的下一步" className="section-card">
        <div className="data-next-step-grid">
          <div className="data-next-step-main">
            <div className="data-next-step-banner">
              <strong>
                {checkedSymbol.trim()
                  ? `${checkedSymbol.trim().toUpperCase()} 的研究准备情况`
                  : "先输入一个标的，页面会告诉你最短研究路径"}
              </strong>
              <p>
                目标不是一次性补齐所有周期，而是先回答两个问题：这只标的现在能不能直接跑？如果不能，最先该补哪个周期？
              </p>
            </div>
            <div className="data-next-step-card-grid">
              {symbolIntervalCards.map((item) => (
                <article key={item.interval} className={`data-next-step-card${item.ready ? " is-ready" : ""}`}>
                  <div className="data-next-step-card-head">
                    <Tag color={item.ready ? "green" : "default"}>{item.interval}</Tag>
                    <span>{item.title}</span>
                  </div>
                  <strong>{item.value}</strong>
                  <p>{item.description}</p>
                  {!item.ready && checkedSymbol.trim() ? (
                    <Button
                      size="small"
                      loading={syncingSymbol && syncInterval === item.interval}
                      onClick={() => void syncSymbolForInterval(item.interval)}
                    >
                      补 {item.interval}
                    </Button>
                  ) : null}
                </article>
              ))}
            </div>
          </div>
          <div className="data-next-step-side">
            <div className="data-next-step-side-card">
              <span>最短路径</span>
              <strong>
                {checkedSymbolLaunchHref
                  ? "当前可以直接进入回测"
                  : intervalRecommendations[0]
                    ? `先补 ${intervalRecommendations[0].interval}`
                    : "先检查一个标的"}
              </strong>
              <p>
                {checkedSymbolLaunchHref
                  ? "已经具备主流程所需覆盖，下一步应先创建回测，而不是继续停留在覆盖明细页。"
                  : intervalRecommendations[0]
                    ? intervalRecommendations[0].description
                    : "输入目标标的后，系统会直接给出最先该补的周期。"}
              </p>
            </div>
            <div className="data-next-step-side-card">
              <span>何时看高级明细</span>
              <strong>只有筛选多个标的或排查异常时再看</strong>
              <p>如果你当前只是想把一个标的跑起来，上面的状态卡和推荐动作通常已经足够，不需要先读完整覆盖表。</p>
            </div>
          </div>
        </div>
      </Card>

      <Card size="small" title="推荐研究样本" className="section-card">
        {beginnerPresets.length === 0 ? (
          <Typography.Text type="secondary">当前尚无可直接使用的推荐样本。可先在上方检查目标标的，并补齐 1d 或 15m。</Typography.Text>
        ) : (
          <div className="beginner-preset-grid">
            {beginnerPresets.map((preset) => (
              <article key={`${preset.symbol}-${preset.interval}`} className="beginner-preset-card">
                <div className="beginner-preset-head">
                  <div>
                    <strong>{preset.symbol}</strong>
                    <span>{preset.name || "未命名标的"}</span>
                  </div>
                  <Tag color={preset.interval === "1d" ? "blue" : "cyan"}>{preset.interval}</Tag>
                </div>
                <p>{preset.reason}</p>
                <div className="beginner-preset-tags">
                  {preset.availableIntervals.map((item) => (
                    <Tag key={item}>{item}</Tag>
                  ))}
                </div>
                <div className="beginner-preset-actions">
                  <Button onClick={() => applyCheckedSymbol(preset.symbol)}>检查该标的</Button>
                  <Button type="primary">
                    <Link href={buildBacktestPresetHref(preset)}>直接创建回测</Link>
                  </Button>
                </div>
              </article>
            ))}
          </div>
        )}
      </Card>

      <Card size="small" title="如果你还没定标的，可先从这里开始" className="section-card">
        <div className="quality-hint-grid">
          {coverageInsights.map((item) => (
            <article key={item.key} className="quality-hint-card">
              <strong>{item.value}</strong>
              <b>{item.title}</b>
              <span>{item.description}</span>
              <small>{item.recommendation}</small>
              <div className="quality-hint-examples">
                {item.examples.length > 0 ? (
                  item.examples.map((profile) => (
                    <Button key={`${item.key}-${profile.symbol}`} size="small" onClick={() => applyCheckedSymbol(profile.symbol)}>
                      先检查 {profile.symbol}
                    </Button>
                  ))
                ) : (
                  <Typography.Text type="secondary">当前还没有这一类标的。</Typography.Text>
                )}
              </div>
            </article>
          ))}
        </div>
        <Typography.Paragraph className="quality-hint-note">
          无需先将全部标的同步完毕。优先选择同时具备 1d 和 15m 的标的建立研究样本，待主流程验证完成后，再逐步扩展更多周期与更多标的。只有需要核对全部覆盖细节时，再展开下方高级明细。
        </Typography.Paragraph>
      </Card>

      {symbolRows.length > 0 ? (
        <Card size="small" title="当前标的覆盖明细" className="section-card">
          <div className="coverage-card-grid">
            {symbolRows.map((item) => (
              <div key={`${item.symbol}-${item.interval}`} className="coverage-card">
                <Tag color={item.interval === "1d" ? "blue" : "cyan"}>{item.interval}</Tag>
                <strong>{item.bar_count.toLocaleString()} 条 K 线</strong>
                <span>{item.start_time} 至 {item.end_time}</span>
              </div>
            ))}
          </div>
        </Card>
      ) : null}

      <div className="summary-grid">
        <MetricCard label="已覆盖标的" value={stats.instrument_count} note="可直接进入研究流程" />
        <MetricCard label="行情记录" value={stats.total_bars.toLocaleString()} note="当前已入库 K 线" />
        {stats.by_interval.map((item) => (
          <MetricCard key={item.interval} label={`${item.interval} 覆盖`} value={item.bar_count.toLocaleString()} note="可用于对应研究周期" />
        ))}
      </div>

      <Card size="small" title="数据覆盖高级明细" className="section-card">
        <div className="data-library-banner">
          <strong>只有在需要核对全部覆盖细节时，再展开完整明细</strong>
          <p>大多数情况下，上方的覆盖检查、当前标的下一步与推荐样本已足以支持决策。只有在筛选多个标的、核对更新时间或排查覆盖异常时，再查看完整表格。</p>
        </div>
        <div className="data-maintenance-banner">
          <div>
            <strong>高级补数：仅在准备扩充标的池时，再补全部标的某个周期</strong>
            <p>如果当前只需建立单标的研究样本，通常无需执行这里的操作。全量补数更适合扩大标的池或当前可直接研究标的过少的场景。</p>
          </div>
          <Space wrap>
            <Select value={syncInterval} options={intervalOptions} onChange={setSyncInterval} style={{ width: 120 }} />
            <Button loading={syncing} onClick={() => void syncAll()}>
              同步全部标的当前周期
            </Button>
          </Space>
        </div>
        <Collapse
          className="advanced-table-panel"
          ghost
          items={[
            {
              key: "coverage-table",
              label: "高级明细：全部标的覆盖、筛选与更新时间",
              children: (
                <>
                  <div className="table-toolbar">
                    <Space wrap>
                      <Input
                        placeholder="筛选标的或名称"
                        value={tableKeyword}
                        onChange={(event) => setTableKeyword(event.target.value)}
                        style={{ width: 240 }}
                      />
                      <Select
                        allowClear
                        placeholder="按周期筛选"
                        value={interval}
                        onChange={setInterval}
                        options={intervalOptions}
                        style={{ width: 150 }}
                      />
                    </Space>
                    <ToolbarCount>共 {filteredRows.length} 条覆盖记录</ToolbarCount>
                  </div>

                  {filteredRows.length === 0 ? (
                    <Empty description="没有匹配的数据" />
                  ) : (
                    <>
                      <div className="coverage-mobile-list">
                        {filteredRows.slice(0, 20).map((row) => (
                          <article key={`${row.symbol}-${row.interval}`} className="coverage-mobile-card">
                            <div className="coverage-mobile-card-head">
                              <div>
                                <strong>{row.symbol}</strong>
                                <span>{row.name || "未命名标的"} / {row.exchange}</span>
                              </div>
                              <Tag color={row.interval === "1d" ? "blue" : "cyan"}>{row.interval}</Tag>
                            </div>
                            <div className="coverage-mobile-metrics">
                              <span>{row.bar_count.toLocaleString()} 条 K 线</span>
                              <span>{row.start_time} 至 {row.end_time}</span>
                            </div>
                            <small>最近更新：{row.last_ingested_at || "-"}</small>
                          </article>
                        ))}
                        {filteredRows.length > 20 ? <Typography.Text type="secondary">移动端先显示前 20 条，可用筛选缩小范围。</Typography.Text> : null}
                      </div>
                      <Table<MarketCoverage>
                        className="coverage-desktop-table"
                        rowKey={(row) => `${row.symbol}-${row.interval}`}
                        size="small"
                        dataSource={filteredRows}
                        pagination={{ pageSize: 20, showSizeChanger: false }}
                        scroll={{ x: 1160 }}
                        columns={[
                          { title: "标的", dataIndex: "symbol", width: 120, fixed: "left" },
                          { title: "名称", dataIndex: "name", ellipsis: true },
                          { title: "交易所", dataIndex: "exchange", width: 90 },
                          { title: "周期", dataIndex: "interval", width: 90 },
                          { title: "K 线数量", dataIndex: "bar_count", width: 120, render: (value: number) => value.toLocaleString() },
                          { title: "开始日期", dataIndex: "start_time", width: 180 },
                          { title: "结束日期", dataIndex: "end_time", width: 180 },
                          { title: "最近更新", dataIndex: "last_ingested_at", width: 220 },
                        ]}
                      />
                    </>
                  )}
                </>
              ),
            },
          ]}
        />
      </Card>
    </div>
  );
}
