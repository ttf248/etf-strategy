"use client";

import { Button, Card, Form, Input, InputNumber, message, Select, Space, Table, Tag, Typography } from "antd";
import { useEffect, useState } from "react";
import { apiFetch, type BacktestJob } from "@/lib/api";

const intervalOptions = ["1d", "15m", "1m"].map((item) => ({ label: item, value: item }));
const strategyOptions = [
  { label: "网格", value: "grid" },
  { label: "日线超跌反弹", value: "daily_rebound" },
  { label: "分钟急跌反抽", value: "minute_rebound" },
  { label: "分钟反抽+冲高回落过滤", value: "minute_rebound_with_fade_filter" },
  { label: "指数回落反弹网格", value: "minute_index_grid_retrace" },
];

export function BacktestsView() {
  const [jobs, setJobs] = useState<BacktestJob[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [messageApi, contextHolder] = message.useMessage();

  async function loadJobs() {
    const payload = await apiFetch<BacktestJob[]>("/api/backtests?limit=100");
    setJobs(payload);
  }

  useEffect(() => {
    async function loadInitialJobs() {
      await loadJobs();
    }

    void loadInitialJobs();
  }, []);

  async function onFinish(values: Record<string, unknown>) {
    setSubmitting(true);
    try {
      const result = await apiFetch<{ job_id: number }>("/api/backtests", {
        method: "POST",
        body: JSON.stringify(values),
      });
      messageApi.success(`任务已提交，ID=${result.job_id}`);
      await loadJobs();
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "提交失败");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="page-stack">
      {contextHolder}
      <Typography.Title level={3} className="section-title">
        回测任务
      </Typography.Title>
      <Card title="发起回测" size="small">
        <Form layout="vertical" onFinish={onFinish} initialValues={{ interval: "15m", strategy_kind: "grid", execution_profile: "realistic", jobs: 1 }}>
          <Space wrap style={{ display: "flex" }}>
            <Form.Item name="symbol" label="标的" rules={[{ required: true }]}>
              <Input placeholder="例如 1810.HK" style={{ width: 180 }} />
            </Form.Item>
            <Form.Item name="interval" label="周期">
              <Select options={intervalOptions} style={{ width: 120 }} />
            </Form.Item>
            <Form.Item name="strategy_kind" label="策略">
              <Select options={strategyOptions} style={{ width: 220 }} />
            </Form.Item>
            <Form.Item name="execution_profile" label="执行口径">
              <Select options={[{ label: "实盘口径", value: "realistic" }, { label: "研究口径", value: "research" }]} style={{ width: 140 }} />
            </Form.Item>
            <Form.Item name="lookback_days" label="日线样本内天数">
              <InputNumber min={1} style={{ width: 150 }} />
            </Form.Item>
            <Form.Item name="validation_ratio" label="分钟线样本外比例">
              <InputNumber min={0.05} max={0.95} step={0.05} style={{ width: 160 }} />
            </Form.Item>
            <Form.Item name="jobs" label="并行数">
              <InputNumber min={1} max={16} style={{ width: 120 }} />
            </Form.Item>
          </Space>
          <Button type="primary" htmlType="submit" loading={submitting}>
            提交任务
          </Button>
        </Form>
      </Card>

      <Card title="任务中心" size="small" extra={<Button onClick={() => void loadJobs()}>刷新</Button>}>
        <Table
          rowKey="id"
          size="small"
          dataSource={jobs}
          pagination={{ pageSize: 12 }}
          columns={[
            { title: "任务ID", dataIndex: "id", width: 88 },
            { title: "标的", render: (_, row) => String(row.request_payload.symbol ?? "-") },
            { title: "周期", render: (_, row) => String(row.request_payload.interval ?? "-") },
            { title: "策略", render: (_, row) => String(row.request_payload.strategy_kind ?? "-") },
            {
              title: "状态",
              dataIndex: "status",
              render: (value: string) => <Tag color={value === "succeeded" ? "green" : value === "failed" ? "red" : "blue"}>{value}</Tag>,
            },
            { title: "进度", dataIndex: "progress_pct", render: (value: number) => `${value.toFixed(0)}%` },
            { title: "提交时间", dataIndex: "submitted_at", width: 180 },
            { title: "完成时间", dataIndex: "completed_at", width: 180 },
            { title: "错误", dataIndex: "error_message", ellipsis: true },
          ]}
        />
      </Card>
    </div>
  );
}
