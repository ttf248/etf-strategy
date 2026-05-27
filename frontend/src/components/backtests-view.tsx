"use client";

import { useSearchParams } from "next/navigation";
import { Button, Card, Collapse, Descriptions, Form, Input, InputNumber, message, Select, Space, Steps, Table, Tag, Typography } from "antd";
import { useEffect, useMemo, useRef, useState, type Key } from "react";
import Link from "next/link";
import { apiFetch, type BacktestJob, type MarketDataStats, type StrategyTemplate } from "@/lib/api";
import { intervalOptions, strategyLabel, strategyOptions } from "@/lib/strategy-template-config";
import { PageHeader, StatusTag } from "@/components/platform-ui";
import { buildBeginnerPresets } from "@/lib/beginner-presets";

const strategyGuide: Record<string, { scene: string; beginnerHint: string; risk: string }> = {
  grid: { scene: "震荡行情里低买高卖", beginnerHint: "第一次回测优先选这个", risk: "单边下跌时回撤可能变大" },
  dca: { scene: "长期分批买入", beginnerHint: "最容易理解，适合日线", risk: "短期不一定跑赢买入持有" },
  daily_rebound: { scene: "日线超跌反弹", beginnerHint: "适合想验证反弹机会", risk: "需要重点看止损和持仓天数" },
  minute_rebound: { scene: "分钟级急跌反抽", beginnerHint: "适合有分钟数据后再试", risk: "对手续费和滑点更敏感" },
  minute_rebound_with_fade_filter: { scene: "带过滤的分钟反抽", beginnerHint: "偏进阶，先理解普通反抽", risk: "参数更多，不适合第一轮" },
  minute_index_grid_retrace: { scene: "指数回落后的网格", beginnerHint: "偏专项策略", risk: "需要匹配指数和标的数据" },
};

function buildTemplateFieldValues(template: StrategyTemplate) {
  const execution = template.execution_overrides_json ?? {};
  return {
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
  };
}

export function BacktestsView() {
  const [form] = Form.useForm();
  const [jobs, setJobs] = useState<BacktestJob[]>([]);
  const [stats, setStats] = useState<MarketDataStats | null>(null);
  const [templates, setTemplates] = useState<StrategyTemplate[]>([]);
  const [selectedJobIds, setSelectedJobIds] = useState<Key[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [activeStep, setActiveStep] = useState(0);
  const [messageApi, contextHolder] = message.useMessage();
  const searchParams = useSearchParams();
  const basePresetAppliedRef = useRef(false);
  const templatePresetAppliedRef = useRef(false);
  const selectedStrategy = Form.useWatch("strategy_kind", form) ?? "grid";
  const selectedInterval = Form.useWatch("interval", form) ?? "15m";
  const selectedTemplateId = Form.useWatch("template_id", form) as number | undefined;

  const filteredTemplates = useMemo(
    () => templates.filter((item) => item.is_active && item.strategy_kind === selectedStrategy && item.interval === selectedInterval),
    [selectedInterval, selectedStrategy, templates],
  );
  const selectedTemplate = filteredTemplates.find((item) => item.id === selectedTemplateId) ?? null;
  const recommendedTemplate = filteredTemplates.find((item) => item.is_default) ?? filteredTemplates[0] ?? null;
  const beginnerPresets = useMemo(() => (stats ? buildBeginnerPresets(stats.coverages) : []), [stats]);
  const queryPreset = useMemo(() => {
    const symbol = searchParams.get("symbol")?.trim().toUpperCase();
    const interval = searchParams.get("interval");
    const strategyKind = searchParams.get("strategy_kind");
    const templateIdRaw = searchParams.get("template_id");
    const templateId = templateIdRaw ? Number(templateIdRaw) : undefined;
    const validIntervals = new Set(intervalOptions.map((item) => item.value));
    const validStrategies = new Set(strategyOptions.map((item) => item.value));
    if (!symbol && !interval && !strategyKind && templateId === undefined) {
      return null;
    }
    return {
      symbol: symbol || undefined,
      interval: interval && validIntervals.has(interval) ? interval : undefined,
      strategy_kind: strategyKind && validStrategies.has(strategyKind) ? strategyKind : undefined,
      template_id: templateId !== undefined && Number.isFinite(templateId) ? templateId : undefined,
    };
  }, [searchParams]);

  async function loadJobs() {
    const payload = await apiFetch<BacktestJob[]>("/api/backtests?limit=100");
    setJobs(payload);
  }

  async function loadTemplates() {
    const payload = await apiFetch<StrategyTemplate[]>("/api/templates?active_only=true");
    setTemplates(payload);
  }

  async function loadStats() {
    const payload = await apiFetch<MarketDataStats>("/api/market-data/stats");
    setStats(payload);
  }

  useEffect(() => {
    async function loadInitialJobs() {
      await Promise.all([loadJobs(), loadTemplates(), loadStats()]);
    }

    void loadInitialJobs();
  }, []);

  useEffect(() => {
    if (basePresetAppliedRef.current || !queryPreset) {
      return;
    }
    const nextValues: Record<string, unknown> = {};
    if (queryPreset.symbol) {
      nextValues.symbol = queryPreset.symbol;
    }
    if (queryPreset.interval) {
      nextValues.interval = queryPreset.interval;
    }
    if (queryPreset.strategy_kind) {
      nextValues.strategy_kind = queryPreset.strategy_kind;
    }
    if (queryPreset.template_id !== undefined) {
      nextValues.template_id = queryPreset.template_id;
    }
    form.setFieldsValue(nextValues);
    basePresetAppliedRef.current = true;
  }, [form, queryPreset]);

  useEffect(() => {
    if (!queryPreset?.template_id || templatePresetAppliedRef.current || templates.length === 0) {
      return;
    }
    const matchedTemplate = templates.find((item) => item.id === queryPreset.template_id) ?? null;
    if (matchedTemplate) {
      form.setFieldsValue(buildTemplateFieldValues(matchedTemplate));
    }
    templatePresetAppliedRef.current = true;
  }, [form, queryPreset, templates]);

  function applyTemplate(template: StrategyTemplate | null) {
    if (!template) {
      form.setFieldValue("template_id", undefined);
      return;
    }
    form.setFieldsValue(buildTemplateFieldValues(template));
  }

  async function goNextStep() {
    if (activeStep === 0) {
      await form.validateFields(["symbol", "interval"]);
    }
    if (activeStep === 1) {
      await form.validateFields(["strategy_kind"]);
      if (!form.getFieldValue("template_id") && recommendedTemplate) {
        applyTemplate(recommendedTemplate);
      }
    }
    setActiveStep((current) => Math.min(current + 1, 2));
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
        description="按 3 步完成：先填标的和周期，再选策略模板，最后确认并提交。"
        actions={<Button onClick={() => void loadJobs()}>刷新结果</Button>}
      />

      <Card title="按步骤创建回测" size="small" className="section-card backtest-wizard-card">
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
          <Steps
            className="backtest-wizard-steps"
            current={activeStep}
            items={[
              { title: "标的" },
              { title: "策略" },
              { title: "提交" },
            ]}
          />

          {activeStep === 0 ? (
            <div className="wizard-step-panel">
              <Typography.Title level={4}>先告诉平台要测哪个标的</Typography.Title>
              <Typography.Paragraph>第一次建议使用已经准备好数据的标的，例如 1810.HK。周期不确定时先用 15m。</Typography.Paragraph>
              {queryPreset ? (
                <div className="wizard-preset-banner">
                  <strong>已带入首页示例</strong>
                  <span>
                    {[queryPreset.symbol, queryPreset.interval, queryPreset.strategy_kind ? strategyLabel(queryPreset.strategy_kind) : undefined]
                      .filter(Boolean)
                      .join(" / ")}
                    ，确认后直接点下一步即可。
                  </span>
                </div>
              ) : null}
              <div className="template-form-grid">
                <Form.Item name="symbol" label="回测标的" rules={[{ required: true, message: "请输入回测标的" }]} extra="使用 Yahoo 代码，例如 1810.HK、0700.HK、513050.SS。">
                  <Input placeholder="例如 1810.HK" />
                </Form.Item>
                <Form.Item name="interval" label="数据周期" extra="第一次建议选择 15m 或 1d。">
                  <Select options={intervalOptions} />
                </Form.Item>
              </div>
              {beginnerPresets.length > 0 ? (
                <div className="wizard-preset-section">
                  <Typography.Text strong>可直接试跑的示例</Typography.Text>
                  <div className="beginner-preset-grid">
                    {beginnerPresets.map((preset) => (
                      <button
                        key={`${preset.symbol}-${preset.interval}`}
                        type="button"
                        className={`beginner-preset-card beginner-preset-button${form.getFieldValue("symbol") === preset.symbol && form.getFieldValue("interval") === preset.interval ? " is-active" : ""}`}
                        onClick={() => {
                          form.setFieldsValue({
                            symbol: preset.symbol,
                            interval: preset.interval,
                            strategy_kind: preset.strategyKind,
                            template_id: undefined,
                          });
                        }}
                      >
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
                          <Tag color="gold">{strategyLabel(preset.strategyKind)}</Tag>
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              ) : null}
            </div>
          ) : null}

          {activeStep === 1 ? (
            <div className="wizard-step-panel">
              <Typography.Title level={4}>选择一个容易理解的策略模板</Typography.Title>
              <Typography.Paragraph>不确定时选“网格”并使用推荐模板。模板已经包含常用参数，后续可以再调整。</Typography.Paragraph>
              <div className="strategy-choice-grid">
                {strategyOptions.map((item) => {
                  const guide = strategyGuide[item.value] ?? { scene: "策略实验", beginnerHint: "按模板说明选择", risk: "先小样本验证" };
                  const hasTemplate = templates.some(
                    (template) => template.is_active && template.strategy_kind === item.value && template.interval === selectedInterval,
                  );
                  const active = selectedStrategy === item.value;
                  return (
                    <button
                      key={item.value}
                      type="button"
                      className={`strategy-choice-card${active ? " is-active" : ""}`}
                      onClick={() => {
                        form.setFieldValue("strategy_kind", item.value);
                        form.setFieldValue("template_id", undefined);
                      }}
                    >
                      <strong>{item.label}</strong>
                      <span>{guide.scene}</span>
                      <small>{guide.beginnerHint}</small>
                      <span>主要风险：{guide.risk}</span>
                      <em>{hasTemplate ? "当前周期有可用模板" : "当前周期暂无模板，建议换周期"}</em>
                    </button>
                  );
                })}
              </div>
              <div className="template-form-grid">
                <Form.Item name="strategy_kind" label="策略类型" extra="也可以直接点上面的策略卡片。">
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
              {recommendedTemplate ? (
                <Space direction="vertical" size={8}>
                  <Typography.Text type="secondary">如果你不想手动挑参数，下一步会自动带入推荐模板。</Typography.Text>
                  <Button onClick={() => applyTemplate(recommendedTemplate)}>使用推荐模板：{recommendedTemplate.template_name}</Button>
                </Space>
              ) : (
                <Typography.Text type="secondary">当前策略和周期没有可用模板，建议换一个周期或先到策略模板页启用模板。</Typography.Text>
              )}
            </div>
          ) : null}

          {activeStep === 2 ? (
            <div className="wizard-step-panel">
              <Typography.Title level={4}>确认后提交任务</Typography.Title>
              <Typography.Paragraph>确认标的、周期和策略无误即可提交。高级参数可以保持默认。</Typography.Paragraph>
              <div className="detail-grid">
                <div className="detail-item"><span className="detail-label">标的</span><span className="detail-value">{form.getFieldValue("symbol") || "-"}</span></div>
                <div className="detail-item"><span className="detail-label">周期</span><span className="detail-value">{selectedInterval}</span></div>
                <div className="detail-item"><span className="detail-label">策略</span><span className="detail-value">{strategyLabel(selectedStrategy)}</span></div>
                <div className="detail-item"><span className="detail-label">模板</span><span className="detail-value">{selectedTemplate?.template_name ?? "未选择模板"}</span></div>
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
            </div>
          ) : null}

          <div className="form-action-row wizard-action-row">
            <Button disabled={activeStep === 0} onClick={() => setActiveStep((current) => Math.max(current - 1, 0))}>
              上一步
            </Button>
            {activeStep < 2 ? (
              <Button type="primary" onClick={() => void goNextStep()}>
                下一步
              </Button>
            ) : (
              <Button type="primary" htmlType="submit" loading={submitting}>
                开始回测
              </Button>
            )}
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
            <Descriptions.Item label="说明">{selectedTemplate.description || "使用模板默认参数"}</Descriptions.Item>
            <Descriptions.Item label="寻参任务数">{selectedTemplate.jobs}</Descriptions.Item>
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
        <div className="job-mobile-list">
          {jobs.map((job) => {
            const payload = job.request_payload;
            const reportId = job.reports?.[0]?.id;
            const templateName = (payload.template_snapshot as { template_name?: string } | undefined)?.template_name;
            return (
              <article key={job.id} className="job-mobile-card">
                <div className="job-mobile-card-head">
                  <div>
                    <strong>任务 #{job.id}</strong>
                    <span>{String(payload.symbol ?? "-")} / {String(payload.interval ?? "-")} / {strategyLabel(String(payload.strategy_kind ?? "-"))}</span>
                  </div>
                  <StatusTag value={job.status} />
                </div>
                <div className="job-mobile-metrics">
                  <span>进度 {job.progress_pct.toFixed(0)}%</span>
                  <span>模板 {templateName ?? "未选择"}</span>
                </div>
                {job.error_message ? <p className="job-mobile-error">{job.error_message}</p> : null}
                <div className="job-mobile-actions">
                  {reportId ? (
                    <Button type="primary">
                      <Link href={`/reports/${reportId}`}>查看报告</Link>
                    </Button>
                  ) : job.status === "succeeded" ? (
                    <Button type="primary">
                      <Link href="/reports">查看报告列表</Link>
                    </Button>
                  ) : (
                    <Button disabled>等待报告</Button>
                  )}
                  <Button disabled={!["queued", "running"].includes(job.status)} onClick={() => void cancelJob(job.id)}>
                    取消
                  </Button>
                  <Button disabled={job.status !== "failed"} onClick={() => void retryJob(job.id)}>
                    重试
                  </Button>
                </div>
              </article>
            );
          })}
        </div>
        <Table
          className="job-desktop-table"
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
            { title: "策略", render: (_, row) => strategyLabel(String(row.request_payload.strategy_kind ?? "-")), width: 160, ellipsis: true },
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
