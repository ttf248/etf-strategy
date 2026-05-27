"use client";

import { Button, Card, Empty, Input, Select, Skeleton, Space, Table, Tag, Typography, message } from "antd";
import { useEffect, useMemo, useState } from "react";
import { apiFetch, type MarketCoverage, type MarketDataStats } from "@/lib/api";
import { MetricCard, PageHeader, ToolbarCount } from "@/components/platform-ui";

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
    const targetSymbol = checkedSymbol.trim().toUpperCase();
    if (!targetSymbol) {
      messageApi.warning("请先输入并检查一个标的");
      return;
    }
    setSyncingSymbol(true);
    try {
      await apiFetch("/api/market-data/sync", {
        method: "POST",
        body: JSON.stringify({ symbol: targetSymbol, interval: syncInterval, period: syncPeriodForInterval(syncInterval) }),
      });
      messageApi.success(`${targetSymbol} ${syncInterval} 同步完成`);
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

  const symbolRows = useMemo(() => {
    if (!stats || !checkedSymbol.trim()) {
      return [];
    }
    const normalizedKeyword = checkedSymbol.trim().toLowerCase();
    return stats.coverages.filter((item) => item.symbol.toLowerCase() === normalizedKeyword);
  }, [stats, checkedSymbol]);

  const readiness = useMemo(() => {
    if (!checkedSymbol.trim()) {
      return { label: "输入标的开始检查", color: "default", description: "例如 1810.HK、0700.HK、513050.SS。" };
    }
    if (symbolRows.length === 0) {
      return { label: "暂未找到数据", color: "red", description: "当前数据库没有这个标的。可以先检查代码格式，再同步行情。" };
    }
    const daily = symbolRows.find((item) => item.interval === "1d");
    const intraday = symbolRows.find((item) => item.interval !== "1d");
    if (daily && intraday) {
      return { label: "适合开始回测", color: "green", description: "该标的同时有日线和分钟线数据，可以创建回测。" };
    }
    return { label: "可回测但数据有限", color: "gold", description: "该标的已有部分周期数据，建议确认策略所需周期是否存在。" };
  }, [checkedSymbol, symbolRows]);

  function checkSymbol() {
    const normalizedSymbol = checkInput.trim().toUpperCase();
    setCheckedSymbol(normalizedSymbol);
    setTableKeyword(normalizedSymbol);
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
            <Select value={syncInterval} options={stats.by_interval.map((item) => ({ label: item.interval, value: item.interval }))} onChange={setSyncInterval} style={{ width: 120 }} />
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
          <div className="data-check-actions">
            <Button loading={syncingSymbol} onClick={() => void syncCheckedSymbol()}>
              同步当前标的 {syncInterval}
            </Button>
            <small>缺少周期时，先选周期再同步当前标的。</small>
          </div>
        </div>
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
              options={stats.by_interval.map((item) => ({ label: item.interval, value: item.interval }))}
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
