"use client";

import { Button, Card, Empty, Input, Select, Space, Table } from "antd";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { apiFetch, type ReportSummary } from "@/lib/api";
import { FormatPercent, PageHeader, ToolbarCount } from "@/components/platform-ui";

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
      <PageHeader
        eyebrow="Reports"
        title="历史报告"
        description="集中查看 Worker 落库的结构化回测报告，按标的、周期和策略快速定位复盘对象。"
      />

      <Card size="small" title="报告列表" className="section-card">
        <div className="table-toolbar">
          <Space wrap>
            <Input placeholder="筛选标的或名称" value={keyword} onChange={(event) => setKeyword(event.target.value)} style={{ width: 240 }} />
            <Select allowClear placeholder="按周期筛选" value={interval} onChange={setInterval} options={intervalOptions} style={{ width: 150 }} />
          </Space>
          <ToolbarCount>共 {filteredReports.length} 份报告</ToolbarCount>
        </div>
        {filteredReports.length === 0 ? (
          <Empty description="暂无报告" />
        ) : (
          <Table
            rowKey="id"
            size="small"
            dataSource={filteredReports}
            pagination={{ pageSize: 12, showSizeChanger: false }}
            scroll={{ x: 980 }}
            columns={[
              { title: "报告ID", dataIndex: "id", width: 88, fixed: "left" },
              { title: "标的", dataIndex: "symbol", width: 120 },
              { title: "名称", dataIndex: "name", ellipsis: true },
              { title: "周期", dataIndex: "interval", width: 90 },
              { title: "策略", dataIndex: "strategy_kind", width: 180, ellipsis: true },
              {
                title: "样本外收益",
                width: 120,
                render: (_, row) => {
                  const validation = row.summary_metrics.validation ?? {};
                  return <FormatPercent value={validation.NetReturnPct ?? validation.ReturnPct ?? 0} />;
                },
              },
              { title: "生成时间", dataIndex: "created_at", width: 180 },
              {
                title: "操作",
                width: 88,
                fixed: "right",
                render: (_, row) => (
                  <Button size="small" type="link">
                    <Link href={`/reports/${row.id}`}>打开</Link>
                  </Button>
                ),
              },
            ]}
          />
        )}
      </Card>
    </div>
  );
}
