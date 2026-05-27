"use client";

import { Button, Card, Descriptions, Form, Input, InputNumber, message, Select, Table } from "antd";
import { useEffect, useMemo, useState } from "react";
import { apiFetch, type BacktestJob, type StrategyTemplate } from "@/lib/api";
import { intervalOptions, strategyLabel, strategyOptions } from "@/lib/strategy-template-config";
import { PageHeader, StatusTag } from "@/components/platform-ui";

export function BacktestsView() {
  const [form] = Form.useForm();
  const [jobs, setJobs] = useState<BacktestJob[]>([]);
  const [templates, setTemplates] = useState<StrategyTemplate[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [messageApi, contextHolder] = message.useMessage();
  const selectedStrategy = Form.useWatch("strategy_kind", form) ?? "grid";
  const selectedInterval = Form.useWatch("interval", form) ?? "15m";
  const selectedTemplateId = Form.useWatch("template_id", form) as number | undefined;

  const filteredTemplates = useMemo(
    () => templates.filter((item) => item.is_active && item.strategy_kind === selectedStrategy && item.interval === selectedInterval),
    [selectedInterval, selectedStrategy, templates],
  );
  const selectedTemplate = filteredTemplates.find((item) => item.id === selectedTemplateId) ?? null;

  async function loadJobs() {
    const payload = await apiFetch<BacktestJob[]>("/api/backtests?limit=100");
    setJobs(payload);
  }

  async function loadTemplates() {
    const payload = await apiFetch<StrategyTemplate[]>("/api/templates?active_only=true");
    setTemplates(payload);
  }

  useEffect(() => {
    async function loadInitialJobs() {
      await Promise.all([loadJobs(), loadTemplates()]);
    }

    void loadInitialJobs();
  }, []);

  function applyTemplate(template: StrategyTemplate | null) {
    if (!template) {
      form.setFieldValue("template_id", undefined);
      return;
    }
    const execution = template.execution_overrides_json ?? {};
    form.setFieldsValue({
      template_id: template.id,
      strategy_kind: template.strategy_kind,
      interval: template.interval,
      execution_profile: template.execution_profile,
      validation_start: template.validation_start || undefined,
      lookback_days: template.lookback_days ?? undefined,
      validation_ratio: template.validation_ratio ?? undefined,
      jobs: template.jobs,
      commission_bps: execution.commission_bps,
      slippage_bps: execution.slippage_bps,
      max_position_ratio: execution.max_position_ratio,
      stop_loss_pct: execution.stop_loss_pct,
      cooldown_bars: execution.cooldown_bars,
      benchmark: execution.benchmark,
      left_side_policy: execution.left_side_policy,
      force_exit_loss_pct: execution.force_exit_loss_pct,
    });
  }

  async function onFinish(values: Record<string, unknown>) {
    setSubmitting(true);
    try {
      const result = await apiFetch<{ job_id: number }>("/api/backtests", {
        method: "POST",
        body: JSON.stringify({
          ...values,
          parameter_space: selectedTemplate?.parameter_space_json,
        }),
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
      <PageHeader
        eyebrow="Backtest Jobs"
        title="回测任务"
        description="通过参数模板或手工参数提交回测任务，由 Worker 异步执行并写入结构化报告。"
        actions={<Button onClick={() => void loadJobs()}>刷新任务</Button>}
      />

      <Card title="发起回测" size="small" className="section-card">
        <Form
          form={form}
          layout="vertical"
          onFinish={onFinish}
          initialValues={{ interval: "15m", strategy_kind: "grid", execution_profile: "realistic", jobs: 1 }}
          onValuesChange={(changedValues) => {
            if ("strategy_kind" in changedValues || "interval" in changedValues) {
              const currentId = form.getFieldValue("template_id");
              const currentTemplate = templates.find((item) => item.id === currentId);
              if (currentTemplate && (currentTemplate.strategy_kind !== form.getFieldValue("strategy_kind") || currentTemplate.interval !== form.getFieldValue("interval"))) {
                form.setFieldValue("template_id", undefined);
              }
            }
          }}
        >
          <div className="template-form-grid">
            <Form.Item name="symbol" label="标的" rules={[{ required: true }]}>
              <Input placeholder="例如 1810.HK" />
            </Form.Item>
            <Form.Item name="interval" label="周期">
              <Select options={intervalOptions} />
            </Form.Item>
            <Form.Item name="strategy_kind" label="策略">
              <Select options={strategyOptions} />
            </Form.Item>
            <Form.Item name="template_id" label="参数模板">
              <Select
                allowClear
                placeholder="按当前策略/周期筛选"
                options={filteredTemplates.map((item) => ({ label: `${item.template_name}${item.is_default ? " · 默认" : ""}`, value: item.id }))}
                onChange={(value) => {
                  const template = filteredTemplates.find((item) => item.id === value) ?? null;
                  applyTemplate(template);
                }}
              />
            </Form.Item>
            <Form.Item name="execution_profile" label="执行口径">
              <Select options={[{ label: "实盘口径", value: "realistic" }, { label: "研究口径", value: "research" }]} />
            </Form.Item>
            <Form.Item name="lookback_days" label="日线样本内天数">
              <InputNumber min={1} style={{ width: "100%" }} />
            </Form.Item>
            <Form.Item name="validation_ratio" label="分钟线样本外比例">
              <InputNumber min={0.05} max={0.95} step={0.05} style={{ width: "100%" }} />
            </Form.Item>
            <Form.Item name="jobs" label="并行数">
              <InputNumber min={1} max={16} style={{ width: "100%" }} />
            </Form.Item>
            <Form.Item name="commission_bps" label="手续费 bps">
              <InputNumber min={0} step={0.5} style={{ width: "100%" }} />
            </Form.Item>
            <Form.Item name="slippage_bps" label="滑点 bps">
              <InputNumber min={0} step={0.5} style={{ width: "100%" }} />
            </Form.Item>
            <Form.Item name="max_position_ratio" label="最大仓位">
              <InputNumber min={0} max={1} step={0.05} style={{ width: "100%" }} />
            </Form.Item>
            <Form.Item name="left_side_policy" label="左侧处理">
              <Select
                allowClear
                options={[
                  { label: "持有", value: "hold" },
                  { label: "强平", value: "force_exit" },
                  { label: "双口径", value: "both" },
                ]}
              />
            </Form.Item>
          </div>
          <div className="form-action-row">
            <Button type="primary" htmlType="submit" loading={submitting}>
              提交任务
            </Button>
          </div>
        </Form>
      </Card>

      {selectedTemplate ? (
        <Card size="small" title="模板摘要" className="section-card">
          <Descriptions size="small" column={{ xs: 1, sm: 2, xl: 4 }}>
            <Descriptions.Item label="模板">{selectedTemplate.template_name}</Descriptions.Item>
            <Descriptions.Item label="策略">{strategyLabel(selectedTemplate.strategy_kind)}</Descriptions.Item>
            <Descriptions.Item label="周期">{selectedTemplate.interval}</Descriptions.Item>
            <Descriptions.Item label="执行口径">{selectedTemplate.execution_profile}</Descriptions.Item>
            <Descriptions.Item label="模板键">{selectedTemplate.template_key}</Descriptions.Item>
            <Descriptions.Item label="并行数">{selectedTemplate.jobs}</Descriptions.Item>
            <Descriptions.Item label="默认模板">{selectedTemplate.is_default ? "是" : "否"}</Descriptions.Item>
            <Descriptions.Item label="状态">{selectedTemplate.is_active ? "启用" : "停用"}</Descriptions.Item>
          </Descriptions>
        </Card>
      ) : null}

      <Card title="任务中心" size="small" className="section-card">
        <Table
          rowKey="id"
          size="small"
          dataSource={jobs}
          pagination={{ pageSize: 12, showSizeChanger: false }}
          scroll={{ x: 1180 }}
          columns={[
            { title: "任务ID", dataIndex: "id", width: 88, fixed: "left" },
            { title: "标的", render: (_, row) => String(row.request_payload.symbol ?? "-"), width: 120 },
            { title: "周期", render: (_, row) => String(row.request_payload.interval ?? "-"), width: 90 },
            { title: "策略", render: (_, row) => String(row.request_payload.strategy_kind ?? "-"), width: 160, ellipsis: true },
            { title: "模板", render: (_, row) => String((row.request_payload.template_snapshot as { template_name?: string } | undefined)?.template_name ?? "-"), ellipsis: true },
            { title: "状态", dataIndex: "status", width: 110, render: (value: string) => <StatusTag value={value} /> },
            { title: "进度", dataIndex: "progress_pct", width: 90, render: (value: number) => `${value.toFixed(0)}%` },
            { title: "提交时间", dataIndex: "submitted_at", width: 180 },
            { title: "完成时间", dataIndex: "completed_at", width: 180 },
            { title: "错误", dataIndex: "error_message", ellipsis: true },
          ]}
        />
      </Card>
    </div>
  );
}
