"use client";

import { Card, Empty, Input, Select, Skeleton, Space, Table, Typography } from "antd";
import { useEffect, useMemo, useState } from "react";
import { apiFetch, type MarketCoverage, type MarketDataStats } from "@/lib/api";

export function MarketDataView() {
  const [stats, setStats] = useState<MarketDataStats | null>(null);
  const [keyword, setKeyword] = useState("");
  const [interval, setInterval] = useState<string | undefined>(undefined);

  useEffect(() => {
    void apiFetch<MarketDataStats>("/api/market-data/stats").then(setStats);
  }, []);

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
      <Typography.Title level={3} className="section-title">
        行情数据统计
      </Typography.Title>
      <div className="summary-grid">
        <Card size="small">
          <div className="metric-kpi">
            <span>已存标的</span>
            <strong>{stats.instrument_count}</strong>
          </div>
        </Card>
        <Card size="small">
          <div className="metric-kpi">
            <span>K 线总量</span>
            <strong>{stats.total_bars.toLocaleString()}</strong>
          </div>
        </Card>
        {stats.by_interval.map((item) => (
          <Card key={item.interval} size="small">
            <div className="metric-kpi">
              <span>{item.interval}</span>
              <strong>{item.bar_count.toLocaleString()}</strong>
            </div>
          </Card>
        ))}
      </div>

      <Card size="small" title="存量覆盖">
        <div className="table-toolbar" style={{ marginBottom: 12 }}>
          <Space wrap>
            <Input
              placeholder="筛选标的或名称"
              value={keyword}
              onChange={(event) => setKeyword(event.target.value)}
              style={{ width: 220 }}
            />
            <Select
              allowClear
              placeholder="按周期筛选"
              value={interval}
              onChange={setInterval}
              options={stats.by_interval.map((item) => ({ label: item.interval, value: item.interval }))}
              style={{ width: 160 }}
            />
          </Space>
          <span>共 {filteredRows.length} 条覆盖记录</span>
        </div>

        {filteredRows.length === 0 ? (
          <Empty description="没有匹配的数据" />
        ) : (
          <Table<MarketCoverage>
            rowKey={(row) => `${row.symbol}-${row.interval}`}
            size="small"
            dataSource={filteredRows}
            pagination={{ pageSize: 20 }}
            columns={[
              { title: "标的", dataIndex: "symbol", width: 120 },
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
