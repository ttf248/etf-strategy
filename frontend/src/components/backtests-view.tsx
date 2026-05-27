"use client";

import { useSearchParams } from "next/navigation";
import { Button, Card, Collapse, Descriptions, Empty, Form, Input, InputNumber, message, Select, Space, Steps, Table, Tag, Typography } from "antd";
import { useEffect, useMemo, useRef, useState, type Key } from "react";
import Link from "next/link";
import { apiFetch, type BacktestJob, type MarketDataStats, type StrategyTemplate } from "@/lib/api";
import { intervalOptions, strategyLabel, strategyOptions } from "@/lib/strategy-template-config";
import { PageHeader, StatusTag, ToolbarCount } from "@/components/platform-ui";
import { buildBeginnerPresets } from "@/lib/beginner-presets";

const strategyGuide: Record<string, { scene: string; beginnerHint: string; risk: string }> = {
  grid: { scene: "震荡行情里低买高卖", beginnerHint: "第一次回测优先选这个", risk: "单边下跌时回撤可能变大" },
  dca: { scene: "长期分批买入", beginnerHint: "最容易理解，适合日线", risk: "短期不一定跑赢买入持有" },
  daily_rebound: { scene: "日线超跌反弹", beginnerHint: "适合想验证反弹机会", risk: "需要重点看止损和持仓天数" },
  minute_rebound: { scene: "分钟级急跌反抽", beginnerHint: "适合有分钟数据后再试", risk: "对手续费和滑点更敏感" },
  minute_rebound_with_fade_filter: { scene: "带过滤的分钟反抽", beginnerHint: "偏进阶，先理解普通反抽", risk: "参数更多，不适合第一轮" },
  minute_index_grid_retrace: { scene: "指数回落后的网格", beginnerHint: "偏专项策略", risk: "需要匹配指数和标的数据" },
};

function buildTemplatePickHint(template: StrategyTemplate | null, strategyKind: string, interval: string) {
  if (!template) {
    return {
      title: "当前还没有可直接套用的模板",
      description: `现在选的是 ${strategyLabel(strategyKind)} / ${interval}。如果这组组合没有启用模板，优先换一个周期，或者先去策略模板页启用默认模板。`,
    };
  }
  return {
    title: `推荐先用 ${template.template_name}`,
    description:
      template.description?.trim() ||
      `${strategyLabel(strategyKind)} / ${interval} 已经有可用模板。第一次先直接套用它，先验证能不能跑出报告，再决定要不要改高级参数。`,
  };
}

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

function buildJobReadingHint(job: BacktestJob) {
  if (job.status === "succeeded") {
    return job.reports?.length ? "这次已经生成报告，优先打开结果看收益、回撤和交易记录。" : "任务执行完成，但报告还没挂上时，先去报告列表刷新确认。";
  }
  if (job.status === "failed") {
    return "这次失败先看错误提示，通常是数据不足、模板不匹配，或参数不适合当前标的。";
  }
  if (job.status === "queued") {
    return "这次回测还在等待开始，先不用重复提交；等它真正开始后，再决定是否取消。";
  }
  if (job.status === "running") {
    return "任务正在执行，先等待结果；如果长时间不动，再去系统状态页排查。";
  }
  if (job.status === "cancelled" || job.status === "cancel_requested") {
    return "这次任务已经取消。如果你还想继续验证，直接按原配置重跑就行。";
  }
  return "先看状态和错误提示，再决定是重跑、取消，还是去报告页看结果。";
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
  const runningJobs = useMemo(() => jobs.filter((item) => item.status === "running"), [jobs]);
  const queuedJobs = useMemo(() => jobs.filter((item) => item.status === "queued"), [jobs]);
  const failedJobs = useMemo(() => jobs.filter((item) => item.status === "failed"), [jobs]);
  const succeededJobs = useMemo(() => jobs.filter((item) => item.status === "succeeded"), [jobs]);
  const recentJobs = useMemo(() => jobs.slice(0, 6), [jobs]);
  const latestSucceededJob = useMemo(() => succeededJobs.find((item) => item.reports?.length), [succeededJobs]);
  const templatePickHint = useMemo(
    () => buildTemplatePickHint(recommendedTemplate, selectedStrategy, selectedInterval),
    [recommendedTemplate, selectedInterval, selectedStrategy],
  );
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

  async function onFinish() {
    setSubmitting(true);
    try {
      const submittedValues = form.getFieldsValue(true);
      const result = await apiFetch<{ job_id: number }>("/api/backtests", {
        method: "POST",
        body: JSON.stringify({
          ...submittedValues,
          parameter_space: selectedTemplate?.parameter_space_json,
        }),
      });
      messageApi.success(`任务已提交，编号=${result.job_id}`);
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
      messageApi.success("已提交所选任务的取消请求");
      setSelectedJobIds([]);
      await loadJobs();
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "取消所选任务失败");
    }
  }

  async function bulkRetryJobs() {
    try {
      await apiFetch("/api/backtests/bulk-retry", {
        method: "POST",
        body: JSON.stringify({ job_ids: selectedJobIds.map(Number) }),
      });
      messageApi.success("已重新提交所选失败任务");
      setSelectedJobIds([]);
      await loadJobs();
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "重试所选任务失败");
    }
  }

  return (
    <div className="page-stack">
      {contextHolder}
      <PageHeader
        eyebrow="创建回测"
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
          <div className="wizard-first-run-banner">
            <strong>如果你只是想先跑通第一轮</strong>
            <p>直接用现成示例标的，周期优先选 15m 或 1d，策略先试网格或定投，模板保持推荐项即可。第一次先跑出一份能读懂的报告，比一开始就改很多高级参数更重要。</p>
            <div className="wizard-first-run-tags">
              <span>1. 选示例标的</span>
              <span>2. 用推荐模板</span>
              <span>3. 提交后看最近任务第一条</span>
            </div>
          </div>

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
              <div className="wizard-template-banner">
                <strong>{templatePickHint.title}</strong>
                <p>{templatePickHint.description}</p>
              </div>
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
              <div className="submit-reading-grid">
                <article className="submit-reading-card">
                  <span>提交后会发生什么</span>
                  <strong>系统会先安排这次回测</strong>
                  <p>正常情况下，提交成功后几秒内就会在下面的“最近回测任务”出现，不需要重复点提交。</p>
                </article>
                <article className="submit-reading-card">
                  <span>什么时候看任务区</span>
                  <strong>刚提交时，只看第一条就够了</strong>
                  <p>如果第一条已经成功并生成报告，直接点进去看结果；没有生成前，不用急着翻完整历史。</p>
                </article>
                <article className="submit-reading-card">
                  <span>什么时候不用停留</span>
                  <strong>没有卡住就不用盯着这页</strong>
                  <p>只有任务长时间不动、连续失败或页面提示异常时，再去系统状态页排查；平时直接回报告页看结果更有价值。</p>
                </article>
              </div>
              <Collapse
                className="advanced-collapse"
                items={[
                  {
                    key: "advanced",
                    label: "高级参数，可保持默认",
                    children: (
                      <div className="template-form-grid">
                        <Form.Item name="execution_profile" label="成交假设">
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
                        <Form.Item name="commission_bps" label="手续费（万分比）">
                          <InputNumber min={0} step={0.5} style={{ width: "100%" }} />
                        </Form.Item>
                        <Form.Item name="slippage_bps" label="滑点（万分比）">
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
            <Descriptions.Item label="成交假设">{selectedTemplate.execution_profile}</Descriptions.Item>
            <Descriptions.Item label="说明">{selectedTemplate.description || "使用模板默认参数"}</Descriptions.Item>
            <Descriptions.Item label="同时尝试的参数组数">{selectedTemplate.jobs}</Descriptions.Item>
            <Descriptions.Item label="默认模板">{selectedTemplate.is_default ? "是" : "否"}</Descriptions.Item>
            <Descriptions.Item label="状态">{selectedTemplate.is_active ? "启用" : "停用"}</Descriptions.Item>
          </Descriptions>
        </Card>
      ) : null}

      <Card
        title="最近回测任务"
        size="small"
        className="section-card"
      >
        {jobs.length === 0 ? (
          <Empty description="还没有回测任务，先按上面的步骤提交第一轮。" />
        ) : (
          <>
            <div className="job-summary-banner">
              <div className="job-summary-main">
                <strong>先看最近几次任务，再决定要不要展开完整历史</strong>
                <p>新手更需要先确认“有没有成功生成报告、失败是不是同一个原因、现在还有没有任务在跑”，而不是直接翻完整任务表。刚提交成功时，只看最近任务里的第一条就够了。</p>
              </div>
              <div className="job-summary-metrics">
                <span>处理中 {runningJobs.length}</span>
                <span>等待开始 {queuedJobs.length}</span>
                <span>失败 {failedJobs.length}</span>
                <span>已完成 {succeededJobs.length}</span>
              </div>
              <div className="job-summary-actions">
                {latestSucceededJob?.reports?.[0]?.id ? (
                  <Button type="primary">
                    <Link href={`/reports/${latestSucceededJob.reports[0].id}`}>打开最近成功报告</Link>
                  </Button>
                ) : null}
                <Button>
                  <Link href="/reports">去看报告列表</Link>
                </Button>
              </div>
            </div>

            <div className="job-mobile-list">
              {recentJobs.map((job) => {
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
                    <p>{buildJobReadingHint(job)}</p>
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

            <Collapse
              className="advanced-table-panel"
              ghost
              items={[
                {
                  key: "history",
                  label: "高级明细：多选处理与完整历史",
                  children: (
                    <>
                      <div className="table-toolbar">
                        <ToolbarCount>已选 {selectedJobIds.length} 条，只有在确实需要一次处理多条任务时再操作。</ToolbarCount>
                        <Space>
                          <Button size="small" disabled={selectedJobIds.length === 0} onClick={() => void bulkCancelJobs()}>
                            取消所选
                          </Button>
                          <Button size="small" disabled={selectedJobIds.length === 0} onClick={() => void bulkRetryJobs()}>
                            重试所选
                          </Button>
                        </Space>
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
                          { title: "任务编号", dataIndex: "id", width: 88, fixed: "left" },
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
                        任务成功后会自动生成报告，可到“查看报告”页面打开。失败通常是标的数据不足、模板不匹配，或参数组合不适合当前行情。
                      </Typography.Paragraph>
                    </>
                  ),
                },
              ]}
            />
          </>
        )}
      </Card>
    </div>
  );
}
