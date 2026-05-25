"use client";

import { Card, Empty, Input, Select, Space, Table, Typography } from "antd";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { apiFetch, type ReportSummary } from "@/lib/api";

export function ReportsView() {
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [keyword, setKeyword] = useState("");
  const [interval, setInterval] = useState<string | undefined>(undefined);

  useEffect(() => {
    void apiFetch<ReportSummary[]>("/api/reports?limit=200").then(setReports);
  }, []);

  const intervalOptions = useMemo(
    () => Array.from(new Set(reports.map((item) => item.interval))).map((item) => ({ label: item, value: item })),
    [reports],
  );

  const filteredReports = useMemo(() => {
    return reports.filter((item) => {
      const matchesKeyword =
        !keyword ||
        item.symbol.toLowerCase().includes(keyword.toLowerCase()) ||
        item.name.toLowerCase().includes(keyword.toLowerCase());
      const matchesInterval = !interval || item.interval === interval;
      return matchesKeyword && matchesInterval;
    });
  }, [reports, keyword, interval]);

  return (
    <div className="page-stack">
      <Typography.Title level={3} className="section-title">
        历史报告
      </Typography.Title>
      <Card size="small" title="报告列表">
        <div className="table-toolbar" style={{ marginBottom: 12 }}>
          <Space wrap>
            <Input placeholder="筛选标的或名称" value={keyword} onChange={(event) => setKeyword(event.target.value)} style={{ width: 220 }} />
            <Select allowClear placeholder="按周期筛选" value={interval} onChange={setInterval} options={intervalOptions} style={{ width: 140 }} />
          </Space>
          <span>共 {filteredReports.length} 份报告</span>
        </div>
        {filteredReports.length === 0 ? (
          <Empty description="暂无报告" />
        ) : (
          <Table
            rowKey="id"
            size="small"
            dataSource={filteredReports}
            pagination={{ pageSize: 12 }}
            columns={[
              { title: "报告ID", dataIndex: "id", width: 88 },
              { title: "标的", dataIndex: "symbol", width: 120 },
              { title: "名称", dataIndex: "name" },
              { title: "周期", dataIndex: "interval", width: 90 },
              { title: "策略", dataIndex: "strategy_kind", width: 180 },
              {
                title: "样本外收益",
                render: (_, row) => {
                  const validation = row.summary_metrics.validation ?? {};
                  return `${Number(validation.NetReturnPct ?? validation.ReturnPct ?? 0).toFixed(2)}%`;
                },
              },
              { title: "生成时间", dataIndex: "created_at", width: 180 },
              {
                title: "查看",
                render: (_, row) => <Link href={`/reports/${row.id}`}>打开</Link>,
              },
            ]}
          />
        )}
      </Card>
    </div>
  );
}
