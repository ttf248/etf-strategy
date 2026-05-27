"use client";

import Link from "next/link";
import { Button, Card, Collapse, Empty, Input, Select, Skeleton, Space, Table, Tag, Typography, message } from "antd";
import { useEffect, useMemo, useState } from "react";
import { apiFetch, type MarketCoverage, type MarketDataStats } from "@/lib/api";
import { MetricCard, PageHeader, ToolbarCount } from "@/components/platform-ui";
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
      title: "当前判断",
      value: "先检查一个标的",
      description: "先输入一个你想测的标的代码，页面才会告诉你当前该补什么，不需要先看全部覆盖表。",
    };
    nextAction = {
      title: "现在最该做",
      value: "先看现成示例",
      description: "如果你只想跑通第一轮，优先用页面里的现成示例标的，再决定要不要检查自己的目标标的。",
    };
    syncAllDecision = {
      title: "什么时候才同步全部",
      value: "现在先不用",
      description: "第一次试跑不需要先做全量建库。只有你准备批量扩充标的池时，才需要补全部标的某个周期。",
    };
    return [currentDecision, nextAction, syncAllDecision];
  }

  if (!hasRows) {
    currentDecision = {
      title: "当前判断",
      value: `${normalizedSymbol} 还没数据`,
      description: "当前还没有这个标的的行情，先把它补到可用，再考虑其他标的和更多周期。",
    };
    nextAction = {
      title: "现在最该做",
      value: intervalRecommendations[0]?.title ?? "先补日线",
      description: intervalRecommendations[0]?.description ?? "第一次通常先补 1d，再按需要补 15m。",
    };
    syncAllDecision = {
      title: "什么时候才同步全部",
      value: "先别同步全部",
      description: "先把当前标的补到能回测，比先补全库更直接。只有当前标的已经够用、你还要扩大范围时，再做全量同步。",
    };
    return [currentDecision, nextAction, syncAllDecision];
  }

  if (hasDaily && has15m) {
    currentDecision = {
      title: "当前判断",
      value: `${normalizedSymbol} 已可直接首跑`,
      description: "这个标的已经同时具备 1d 和 15m，足够支撑大多数新手第一轮回测。",
    };
    nextAction = {
      title: "现在最该做",
      value: "直接去创建回测",
      description: "现在更应该先跑出一份报告，再根据结果决定要不要补更多标的或更多周期。",
    };
    syncAllDecision = {
      title: "什么时候才同步全部",
      value: readySymbolCount > 0 ? "只有想扩大标的池时再做" : "暂时不用",
      description: "全量同步只在你准备批量筛更多标的、或者库里可直接首跑的标的太少时才有必要。当前这个标的已经够开始。",
    };
    return [currentDecision, nextAction, syncAllDecision];
  }

  currentDecision = {
    title: "当前判断",
    value: `${normalizedSymbol} 还能继续补`,
    description: "这个标的已经有部分数据，可以开始一些策略，但还没覆盖到最常用的新手组合。",
  };
  nextAction = {
    title: "现在最该做",
    value: intervalRecommendations[0]?.title ?? "先补推荐周期",
    description: intervalRecommendations[0]?.description ?? "先把常用周期补齐，再回到创建回测页。",
  };
  syncAllDecision = {
    title: "什么时候才同步全部",
    value: "当前仍以补这个标的为先",
    description: "如果你只是想验证这一只标的，先补推荐周期就够了。只有你准备同时研究更多标的时，再做全量同步。",
  };
  return [currentDecision, nextAction, syncAllDecision];
}

export function MarketDataView() {
  const [stats, setStats] = useState<MarketDataStats | null>(null);
  const [checkInput, setCheckInput] = useState("1810.HK");
  const [checkedSymbol, setCheckedSymbol] = useState("1810.HK");
  const [tableKeyword, setTableKeyword] = useState("");
  const [interval, setInterval] = useState<string | undefined>(undefined);
  const [syncInterval, setSyncInterval] = useState("1d");
  const [syncing, setSyncing] = useState(false);
  const [syncingSymbol, setSyncingSymbol] = useState(false);
  const [messageApi, contextHolder] = message.useMessage();

  async function fetchStats() {
    return apiFetch<MarketDataStats>("/api/market-data/stats");
  }

  useEffect(() => {
    void fetchStats().then(setStats);
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
      setStats(await fetchStats());
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
      setStats(await fetchStats());
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
        title: "可直接首跑",
        description: "同时具备 1d 和 15m，最适合第一次完整试跑。",
        recommendation: "优先从这类里挑一个开始，不需要先做额外补数。",
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
      return { label: "输入标的开始检查", color: "default", description: "例如 1810.HK、0700.HK、513050.SS。" };
    }
    if (symbolRows.length === 0) {
      return { label: "暂未找到数据", color: "red", description: "当前还没有这个标的的行情。可以先检查代码格式，再同步数据。" };
    }
    const daily = symbolIntervals.has("1d");
    const intraday = Array.from(symbolIntervals).some((item) => item !== "1d");
    if (daily && intraday) {
      return { label: "适合开始回测", color: "green", description: "该标的同时有日线和分钟线数据，可以创建回测。" };
    }
    return { label: "可回测但数据有限", color: "gold", description: "该标的已有部分周期数据，建议确认策略所需周期是否存在。" };
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
          description: "第一次建库先补 1d，最适合做长期回测、定投和基础可用性检查。",
        },
        {
          interval: "15m",
          title: "再补 15m",
          description: "如果你准备跑网格或短周期反弹策略，再补 15m 就能开始大部分分钟研究。",
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
        description: "补 15m 后可以直接跑默认分钟网格和大多数新手第一轮短线策略。",
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

  function applyCheckedSymbol(targetSymbol: string) {
    const normalizedSymbol = targetSymbol.trim().toUpperCase();
    setCheckInput(normalizedSymbol);
    setCheckedSymbol(normalizedSymbol);
    setTableKeyword(normalizedSymbol);
  }

  function checkSymbol() {
    applyCheckedSymbol(checkInput);
  }

  if (!stats) {
    return <Skeleton active paragraph={{ rows: 10 }} />;
  }

  return (
    <div className="page-stack">
      {contextHolder}
      <PageHeader
        eyebrow="数据准备"
        title="数据准备"
        description="先检查一个标的是否已有可回测行情。缺数据时再同步，不需要先研究完整数据明细。"
      />

      <Card size="small" className="section-card data-check-card">
        <div className="data-check-main">
          <Typography.Title level={4}>检查标的是否能回测</Typography.Title>
          <Typography.Paragraph>输入 Yahoo 标的代码，系统会告诉你当前有哪些周期、覆盖到哪一天。</Typography.Paragraph>
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
            <small>不会补数据时，优先按上面的推荐周期同步；第一次短线研究建议先补 15m。</small>
          </div>
        </div>
      </Card>

      <Card size="small" className="section-card start-path-card">
        <div className="start-path-main">
          <strong>
            {symbolRows.length === 0
              ? "先补一个能用的标的，再决定要不要同步全部数据"
              : intervalRecommendations.length === 0
                ? "当前这个标的已经够开始，不需要继续翻完整覆盖表"
                : "这个标的可以先开始，但补齐常用周期会更稳妥"}
          </strong>
          <p>
            {symbolRows.length === 0
              ? "你现在更需要先把一个标的补到可用，而不是先看完整覆盖表。第一次通常先补 1d，再按需要补 15m。"
              : intervalRecommendations.length === 0
                ? "这个标的已经具备当前常用周期，可以直接去创建回测；只有想核对更多标的时，再展开下面的高级明细。"
                : "当前标的已经有部分数据，可以先开始回测；如果你准备长期复盘或默认分钟策略，再把缺的推荐周期补齐。"}
          </p>
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
              <Link href={checkedSymbolLaunchHref}>用当前标的开始回测</Link>
            </Button>
          ) : null}
          {beginnerPresets[0] ? (
            <Button>
              <Link href={buildBacktestPresetHref(beginnerPresets[0])}>先用现成示例标的开始</Link>
            </Button>
          ) : null}
          {intervalRecommendations[0] ? (
            <Button loading={syncingSymbol && syncInterval === intervalRecommendations[0].interval} onClick={() => void syncSymbolForInterval(intervalRecommendations[0].interval)}>
              先补 {intervalRecommendations[0].interval}
            </Button>
          ) : null}
        </div>
      </Card>

      <Card size="small" title="新手建议先用这些标的" className="section-card">
        {beginnerPresets.length === 0 ? (
          <Typography.Text type="secondary">当前还没有同时适合首跑的示例标的。可以先在上方输入一个标的检查，再补 1d 或 15m。</Typography.Text>
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
                  <Button onClick={() => applyCheckedSymbol(preset.symbol)}>先检查这个标的</Button>
                  <Button type="primary">
                    <Link href={buildBacktestPresetHref(preset)}>直接去回测</Link>
                  </Button>
                </div>
              </article>
            ))}
          </div>
        )}
      </Card>

      <Card size="small" title="先按准备程度选一个标的，不需要先翻完整覆盖表" className="section-card">
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
          第一次试跑不需要先把全部标的都同步完。优先选一个同时有 1d 和 15m 的标的，跑通回测流程后，再逐步补更多周期和更多标的。只有当你需要核对全部覆盖细节时，再展开下面的高级明细。
        </Typography.Paragraph>
      </Card>

      {symbolRows.length > 0 ? (
        <Card size="small" title="这个标的已有数据" className="section-card">
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
        <MetricCard label="已准备标的" value={stats.instrument_count} note="可以在创建回测时选择" />
        <MetricCard label="行情记录" value={stats.total_bars.toLocaleString()} note="已准备的 K 线" />
        {stats.by_interval.map((item) => (
          <MetricCard key={item.interval} label={`${item.interval} 数据`} value={item.bar_count.toLocaleString()} note="该周期可用于对应策略" />
        ))}
      </div>

      <Card size="small" title="数据覆盖高级明细" className="section-card">
        <div className="data-library-banner">
          <strong>只有在你需要核对全部覆盖细节时，再展开完整明细</strong>
          <p>大多数时候，上面的检查结果、准备程度分层和推荐周期已经足够决定下一步。只有当你要筛多个标的、核对更新时间或排查覆盖异常时，再看完整表格。</p>
        </div>
        <div className="data-maintenance-banner">
          <div>
            <strong>高级补数：只有准备扩大量级时，再补全部标的某个周期</strong>
            <p>如果你现在只是想跑通一个标的，不需要点这里。全量补数更适合“准备扩大标的池”或“当前可直接首跑的标的太少”的场景。</p>
          </div>
          <Space wrap>
            <Select value={syncInterval} options={intervalOptions} onChange={setSyncInterval} style={{ width: 120 }} />
            <Button loading={syncing} onClick={() => void syncAll()}>
              补全部标的当前周期
            </Button>
          </Space>
        </div>
        <Collapse
          className="advanced-table-panel"
          ghost
          items={[
            {
              key: "coverage-table",
              label: "高级明细：全部标的覆盖、筛选和更新时间",
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
