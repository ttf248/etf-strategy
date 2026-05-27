"use client";

import { Button, Card, Collapse, Descriptions, Form, Input, InputNumber, message, Select, Space, Table, Typography } from "antd";
import { useEffect, useMemo, useState, type Key } from "react";
import { apiFetch, type BacktestJob, type StrategyTemplate } from "@/lib/api";
import { intervalOptions, strategyLabel, strategyOptions } from "@/lib/strategy-template-config";
import { PageHeader, StatusTag } from "@/components/platform-ui";

export function BacktestsView() {
  const [form] = Form.useForm();
  const [jobs, setJobs] = useState<BacktestJob[]>([]);
  const [templates, setTemplates] = useState<StrategyTemplate[]>([]);
  const [selectedJobIds, setSelectedJobIds] = useState<Key[]>([]);
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

  async function cancelJob(jobId: number) {
    try {
      await apiFetch(`/api/backtests/${jobId}/cancel`, { method: "POST" });
      messageApi.success(`已提交取消请求：${jobId}`);
      await loadJobs();
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "取消失败");
    }
  }

  async function retryJob(jobId: number) {
    try {
      await apiFetch(`/api/backtests/${jobId}/retry`, { method: "POST" });
      messageApi.success(`已重新入队：${jobId}`);
      await loadJobs();
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "重试失败");
    }
  }

  async function bulkCancelJobs() {
    try {
      await apiFetch("/api/backtests/bulk-cancel", {
        method: "POST",
        body: JSON.stringify({ job_ids: selectedJobIds.map(Number) }),
      });
      messageApi.success("已提交批量取消请求");
      setSelectedJobIds([]);
      await loadJobs();
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "批量取消失败");
    }
  }

  async function bulkRetryJobs() {
    try {
      await apiFetch("/api/backtests/bulk-retry", {
        method: "POST",
        body: JSON.stringify({ job_ids: selectedJobIds.map(Number) }),
      });
      messageApi.success("已提交批量重试请求");
      setSelectedJobIds([]);
      await loadJobs();
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "批量重试失败");
    }
  }

  return (
    <div className="page-stack">
      {contextHolder}
      <PageHeader
        eyebrow="Run Backtest"
        title="创建一次回测"
        description="先输入标的，再选择策略模板。高级参数可以保持默认，适合第一次使用时快速跑通。"
        actions={<Button onClick={() => void loadJobs()}>刷新结果</Button>}
      />

      <div className="beginner-steps">
        <Card size="small">
          <strong>1. 输入标的</strong>
          <span>例如港股小米是 1810.HK。</span>
        </Card>
        <Card size="small">
          <strong>2. 选择模板</strong>
          <span>默认模板已经包含常用参数。</span>
        </Card>
        <Card size="small">
          <strong>3. 提交后看报告</strong>
          <span>任务完成后到“查看报告”阅读结果。</span>
        </Card>
      </div>

      <Card title="基础设置" size="small" className="section-card">
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
            <Form.Item name="symbol" label="回测标的" rules={[{ required: true }]} extra="使用 Yahoo 代码，例如 1810.HK、0700.HK、513050.SS。">
              <Input placeholder="例如 1810.HK" />
            </Form.Item>
            <Form.Item name="interval" label="数据周期" extra="第一次建议选择 15m 或 1d。">
              <Select options={intervalOptions} />
            </Form.Item>
            <Form.Item name="strategy_kind" label="策略类型" extra="不确定时先用网格策略。">
              <Select options={strategyOptions} />
            </Form.Item>
            <Form.Item name="template_id" label="参数模板" extra="推荐选择带“默认”的模板。">
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
          </div>
          <Collapse
            className="advanced-collapse"
            items={[
              {
                key: "advanced",
                label: "高级参数，可保持默认",
                children: (
                  <div className="template-form-grid">
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
                ),
              },
            ]}
          />
          <div className="form-action-row">
            <Button type="primary" htmlType="submit" loading={submitting}>
              开始回测
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

      <Card
        title="回测运行记录"
        size="small"
        className="section-card"
        extra={
          <Space>
            <span className="toolbar-count">已选 {selectedJobIds.length} 项</span>
            <Button size="small" disabled={selectedJobIds.length === 0} onClick={() => void bulkCancelJobs()}>
              批量取消
            </Button>
            <Button size="small" disabled={selectedJobIds.length === 0} onClick={() => void bulkRetryJobs()}>
              批量重试
            </Button>
          </Space>
        }
      >
        <Table
          rowKey="id"
          size="small"
          dataSource={jobs}
          rowSelection={{ selectedRowKeys: selectedJobIds, onChange: setSelectedJobIds }}
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
            {
              title: "操作",
              width: 150,
              fixed: "right",
              render: (_, row) => (
                <Space size="small">
                  <Button size="small" disabled={!["queued", "running"].includes(row.status)} onClick={() => void cancelJob(row.id)}>
                    取消
                  </Button>
                  <Button size="small" disabled={row.status !== "failed"} onClick={() => void retryJob(row.id)}>
                    重试
                  </Button>
                </Space>
              ),
            },
          ]}
        />
        <Typography.Paragraph className="table-help">
          任务成功后会自动生成报告，可到“查看报告”页面打开。失败任务通常是标的数据不足、代码写错或参数组合不适用。
        </Typography.Paragraph>
      </Card>
    </div>
  );
}
