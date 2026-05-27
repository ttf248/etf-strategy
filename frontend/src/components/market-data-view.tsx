"use client";

import { Button, Card, Empty, Input, Select, Skeleton, Space, Table, message } from "antd";
import { useEffect, useMemo, useState } from "react";
import { apiFetch, type MarketCoverage, type MarketDataStats } from "@/lib/api";
import { MetricCard, PageHeader, ToolbarCount } from "@/components/platform-ui";

export function MarketDataView() {
  const [stats, setStats] = useState<MarketDataStats | null>(null);
  const [keyword, setKeyword] = useState("");
  const [interval, setInterval] = useState<string | undefined>(undefined);
  const [syncInterval, setSyncInterval] = useState("1d");
  const [syncing, setSyncing] = useState(false);
  const [messageApi, contextHolder] = message.useMessage();

  async function fetchStats() {
    return apiFetch<MarketDataStats>("/api/market-data/stats");
  }

  useEffect(() => {
    void fetchStats().then(setStats);
  }, []);

  async function syncAll() {
    setSyncing(true);
    try {
      await apiFetch("/api/market-data/sync", {
        method: "POST",
        body: JSON.stringify({ interval: syncInterval, period: syncInterval === "15m" ? "60d" : syncInterval === "1m" ? "7d" : undefined }),
      });
      messageApi.success("同步已完成");
      setStats(await fetchStats());
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "同步失败");
    } finally {
      setSyncing(false);
    }
  }

  const filteredRows = useMemo(() => {
    if (!stats) {
      return [];
    }
    return stats.coverages.filter((item) => {
      const matchesKeyword =
        !keyword ||
        item.symbol.toLowerCase().includes(keyword.toLowerCase()) ||
        item.name.toLowerCase().includes(keyword.toLowerCase());
      const matchesInterval = !interval || item.interval === interval;
      return matchesKeyword && matchesInterval;
    });
  }, [stats, keyword, interval]);

  if (!stats) {
    return <Skeleton active paragraph={{ rows: 10 }} />;
  }

  return (
    <div className="page-stack">
      {contextHolder}
      <PageHeader
        eyebrow="Market Data"
        title="行情数据"
        description="查看 PostgreSQL 中已入库的标的、周期、覆盖区间和最近同步状态。"
        actions={
          <Space>
            <Select value={syncInterval} options={stats.by_interval.map((item) => ({ label: item.interval, value: item.interval }))} onChange={setSyncInterval} style={{ width: 120 }} />
            <Button loading={syncing} onClick={() => void syncAll()}>
              同步全部
            </Button>
          </Space>
        }
      />

      <div className="summary-grid">
        <MetricCard label="已存标的" value={stats.instrument_count} note="instruments" />
        <MetricCard label="K 线总量" value={stats.total_bars.toLocaleString()} note="price_bars" />
        {stats.by_interval.map((item) => (
          <MetricCard key={item.interval} label={`${item.interval} 周期`} value={item.bar_count.toLocaleString()} note="bars" />
        ))}
      </div>

      <Card size="small" title="存量覆盖" className="section-card">
        <div className="table-toolbar">
          <Space wrap>
            <Input
              placeholder="筛选标的或名称"
              value={keyword}
              onChange={(event) => setKeyword(event.target.value)}
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
          <Table<MarketCoverage>
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
              { title: "记录数", dataIndex: "bar_count", width: 120, render: (value: number) => value.toLocaleString() },
              { title: "起始时间", dataIndex: "start_time", width: 180 },
              { title: "结束时间", dataIndex: "end_time", width: 180 },
              { title: "最近入库", dataIndex: "last_ingested_at", width: 220 },
            ]}
          />
        )}
      </Card>
    </div>
  );
}
