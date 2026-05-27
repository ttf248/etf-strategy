"use client";

import Link from "next/link";
import { Button, Card, Empty, Input, Select, Skeleton, Space, Table, Tag, Typography, message } from "antd";
import { useEffect, useMemo, useState } from "react";
import { apiFetch, type MarketCoverage, type MarketDataStats } from "@/lib/api";
import { MetricCard, PageHeader, ToolbarCount } from "@/components/platform-ui";
import { intervalOptions } from "@/lib/strategy-template-config";
import { buildBacktestPresetHref, buildBeginnerPresets } from "@/lib/beginner-presets";

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
};

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
    let readyCount = 0;
    let dailyOnlyCount = 0;
    let partialCount = 0;

    for (const item of coverageProfiles) {
      const hasDaily = item.intervals.has("1d");
      const has15m = item.intervals.has("15m");
      const has1m = item.intervals.has("1m");
      if (hasDaily && has15m) {
        readyCount += 1;
      } else if (hasDaily) {
        dailyOnlyCount += 1;
      } else if (has15m || has1m) {
        partialCount += 1;
      }
    }

    return [
      {
        key: "ready",
        value: `${readyCount} 个`,
        title: "可直接首跑",
        description: "同时具备 1d 和 15m，最适合第一次完整试跑。",
      },
      {
        key: "daily-only",
        value: `${dailyOnlyCount} 个`,
        title: "只适合长周期",
        description: "目前只有日线，适合先做定投或日线策略验证。",
      },
      {
        key: "partial",
        value: `${partialCount} 个`,
        title: "还需补关键周期",
        description: "只有分钟线或缺少 1d / 15m，建议先补齐再开始。",
      },
    ];
  }, [coverageProfiles]);

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
      return { label: "暂未找到数据", color: "red", description: "当前数据库没有这个标的。可以先检查代码格式，再同步行情。" };
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
        eyebrow="Data Setup"
        title="数据准备"
        description="先检查一个标的是否已有可回测行情。缺数据时再同步，不需要先理解数据库表。"
        actions={
          <Space>
            <Select value={syncInterval} options={intervalOptions} onChange={setSyncInterval} style={{ width: 120 }} />
            <Button loading={syncing} onClick={() => void syncAll()}>
              同步全部
            </Button>
          </Space>
        }
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

      <Card size="small" title="当前数据准备提示" className="section-card">
        <div className="quality-hint-grid">
          {coverageInsights.map((item) => (
            <article key={item.key} className="quality-hint-card">
              <strong>{item.value}</strong>
              <b>{item.title}</b>
              <span>{item.description}</span>
            </article>
          ))}
        </div>
        <Typography.Paragraph className="quality-hint-note">
          第一次试跑不需要先把全部标的都同步完。优先选一个同时有 1d 和 15m 的标的，跑通回测流程后，再逐步补更多周期和更多标的。
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
        <MetricCard label="行情记录" value={stats.total_bars.toLocaleString()} note="已入库 K 线" />
        {stats.by_interval.map((item) => (
          <MetricCard key={item.interval} label={`${item.interval} 数据`} value={item.bar_count.toLocaleString()} note="该周期可用于对应策略" />
        ))}
      </div>

      <Card size="small" title="全部数据覆盖" className="section-card">
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
      </Card>
    </div>
  );
}
