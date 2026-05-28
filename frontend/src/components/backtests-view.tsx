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
  grid: { scene: "震荡区间内分层低买高卖", beginnerHint: "常用基线策略", risk: "单边下跌阶段回撤可能扩大" },
  dca: { scene: "长期分批建仓", beginnerHint: "适合日线基线研究", risk: "短期收益未必优于买入持有" },
  daily_rebound: { scene: "日线超跌反弹", beginnerHint: "适合验证阶段性反转", risk: "需重点关注止损与持仓时长" },
  minute_rebound: { scene: "分钟级急跌反抽", beginnerHint: "适合分钟级短线研究", risk: "对手续费与滑点更敏感" },
  minute_rebound_with_fade_filter: { scene: "带过滤条件的分钟反抽", beginnerHint: "适合进阶筛选研究", risk: "参数维度更多，配置复杂度更高" },
  minute_index_grid_retrace: { scene: "指数回落后的网格承接", beginnerHint: "适合专项指数研究", risk: "依赖指数与标的数据匹配" },
};

function executionProfileLabel(profile: string): string {
  if (profile === "realistic") {
    return "真实成交口径";
  }
  if (profile === "research") {
    return "理想成交口径";
  }
  return profile;
}

function buildTemplatePickHint(template: StrategyTemplate | null, strategyKind: string, interval: string) {
  if (!template) {
    return {
      title: "当前组合尚无可直接使用的模板",
      description: `当前选择为 ${strategyLabel(strategyKind)} / ${interval}。若该组合没有启用模板，建议优先调整周期，或先到策略模板页启用标准模板。`,
    };
  }
  return {
    title: `推荐使用 ${template.template_name}`,
    description:
      template.description?.trim() ||
      `${strategyLabel(strategyKind)} / ${interval} 已有可用模板。建议先直接采用该配置形成结果，再决定是否展开高级参数调整。`,
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
    return job.reports?.length ? "本次任务已生成报告，建议直接进入结果页复盘收益、回撤与交易记录。" : "本次任务已执行完成；若结果尚未出现，请到结果库刷新确认。";
  }
  if (job.status === "failed") {
    return "本次任务执行失败，建议先查看错误信息；常见原因包括数据覆盖不足、模板不匹配或参数与标的不适配。";
  }
  if (job.status === "queued") {
    return "任务仍在排队，通常无需重复提交；待进入执行阶段后，再判断是否需要取消。";
  }
  if (job.status === "running") {
    return "任务仍在执行中，建议等待结果输出；若长时间无进展，再进入系统状态页排查。";
  }
  if (job.status === "cancelled" || job.status === "cancel_requested") {
    return "任务已取消；若仍需继续验证，可直接按原配置重新提交。";
  }
  return "建议先确认当前状态与错误信息，再决定是重跑、取消，还是进入结果库继续复盘。";
}

function backtestStatusLabel(status: string) {
  if (status === "succeeded") {
    return "已生成结果";
  }
  if (status === "failed") {
    return "执行失败";
  }
  if (status === "queued") {
    return "等待执行";
  }
  if (status === "running") {
    return "执行中";
  }
  if (status === "cancel_requested") {
    return "取消中";
  }
  if (status === "cancelled") {
    return "已取消";
  }
  return status || "-";
}

function buildJobPrimaryAction(job: BacktestJob) {
  const reportId = job.reports?.[0]?.id;
  if (reportId) {
    return {
      disabled: false,
      href: `/reports/${reportId}`,
      label: "查看结果",
    };
  }
  if (job.status === "succeeded") {
    return {
      disabled: false,
      href: "/reports",
      label: "进入结果库",
    };
  }
  if (job.status === "failed") {
    return {
      disabled: true,
      href: null,
      label: "未生成结果",
    };
  }
  if (job.status === "cancelled" || job.status === "cancel_requested") {
    return {
      disabled: true,
      href: null,
      label: "任务已取消",
    };
  }
  return {
    disabled: true,
    href: null,
    label: "等待结果生成",
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
      messageApi.success(`任务已提交，编号 ${result.job_id}`);
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
      messageApi.success(`已请求取消任务，编号 ${jobId}`);
      await loadJobs();
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "取消失败");
    }
  }

  async function retryJob(jobId: number) {
    try {
      await apiFetch(`/api/backtests/${jobId}/retry`, { method: "POST" });
      messageApi.success(`任务已重新安排，编号 ${jobId}`);
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
        eyebrow="回测配置"
        title="创建回测任务"
        description="按三步完成任务配置：定义标的与周期、选择策略模板、确认执行口径后提交。"
        actions={<Button onClick={() => void loadJobs()}>看一下最新进展</Button>}
      />

      <Card title="任务配置流程" size="small" className="section-card backtest-wizard-card">
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
            <strong>基线研究建议</strong>
            <p>可直接使用现成样本，优先选择 15m 或 1d，策略使用网格或定投，模板保持推荐项。先形成一份可复盘结果，比一开始扩展大量高级参数更有效。</p>
            <div className="wizard-first-run-tags">
              <span>1. 选择标准样本</span>
              <span>2. 使用推荐模板</span>
              <span>3. 复盘最近结果</span>
            </div>
          </div>

          <Steps
            className="backtest-wizard-steps"
            current={activeStep}
            items={[
              { title: "标的与周期" },
              { title: "策略与模板" },
              { title: "确认提交" },
            ]}
          />

          {activeStep === 0 ? (
            <div className="wizard-step-panel">
              <Typography.Title level={4}>定义研究标的与数据周期</Typography.Title>
              <Typography.Paragraph>建议优先使用已具备覆盖的数据标的，例如 1810.HK。若暂无明确偏好，可先以 15m 作为分钟级基线周期。</Typography.Paragraph>
              {queryPreset ? (
                <div className="wizard-preset-banner">
                  <strong>已带入推荐样本</strong>
                  <span>
                    {[queryPreset.symbol, queryPreset.interval, queryPreset.strategy_kind ? strategyLabel(queryPreset.strategy_kind) : undefined]
                      .filter(Boolean)
                      .join(" / ")}
                    ，确认无误后可直接进入下一步。
                  </span>
                </div>
              ) : null}
              <div className="template-form-grid">
                <Form.Item name="symbol" label="回测标的" rules={[{ required: true, message: "请输入回测标的" }]} extra="使用 Yahoo 代码，例如 1810.HK、0700.HK、513050.SS。">
                  <Input placeholder="例如 1810.HK" />
                </Form.Item>
                <Form.Item name="interval" label="数据周期" extra="常用基线周期为 15m 或 1d。">
                  <Select options={intervalOptions} />
                </Form.Item>
              </div>
              {beginnerPresets.length > 0 ? (
                <div className="wizard-preset-section">
                  <Typography.Text strong>可直接使用的研究样本</Typography.Text>
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
              <Typography.Title level={4}>选择策略与模板</Typography.Title>
              <Typography.Paragraph>若暂无明确偏好，可先使用“网格”及推荐模板作为基线配置。模板已包含常用参数，后续再按结果调整。</Typography.Paragraph>
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
                <Form.Item name="strategy_kind" label="策略类型" extra="也可以直接选择上方策略卡片。">
                  <Select options={strategyOptions} />
                </Form.Item>
                <Form.Item name="template_id" label="参数模板" extra="推荐优先使用标准默认模板。">
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
                  <Typography.Text type="secondary">若不准备手动筛选参数，下一步会自动带入推荐模板。</Typography.Text>
                  <Button onClick={() => applyTemplate(recommendedTemplate)}>应用推荐模板：{recommendedTemplate.template_name}</Button>
                </Space>
              ) : (
                <Typography.Text type="secondary">当前策略与周期暂无可用模板，建议调整周期或先到策略模板页启用模板。</Typography.Text>
              )}
            </div>
          ) : null}

          {activeStep === 2 ? (
            <div className="wizard-step-panel">
              <Typography.Title level={4}>确认执行配置并提交</Typography.Title>
              <Typography.Paragraph>确认标的、周期、策略与模板无误后即可提交。若无专项需求，高级参数可保持默认。</Typography.Paragraph>
              <div className="detail-grid">
                <div className="detail-item"><span className="detail-label">标的</span><span className="detail-value">{form.getFieldValue("symbol") || "-"}</span></div>
                <div className="detail-item"><span className="detail-label">周期</span><span className="detail-value">{selectedInterval}</span></div>
                <div className="detail-item"><span className="detail-label">策略</span><span className="detail-value">{strategyLabel(selectedStrategy)}</span></div>
                <div className="detail-item"><span className="detail-label">模板</span><span className="detail-value">{selectedTemplate?.template_name ?? "未选择模板"}</span></div>
              </div>
              <div className="submit-reading-grid">
                <article className="submit-reading-card">
                  <span>提交后</span>
                  <strong>系统会为该配置创建任务</strong>
                  <p>正常情况下，提交成功后数秒内即可在下方“最近回测任务”看到记录，无需重复提交。</p>
                </article>
                <article className="submit-reading-card">
                  <span>任务跟踪</span>
                  <strong>优先关注最近一条记录</strong>
                  <p>若最新任务已完成并生成报告，可直接进入结果页；在结果输出前，无需翻阅完整历史。</p>
                </article>
                <article className="submit-reading-card">
                  <span>何时排障</span>
                  <strong>仅在异常时进入系统状态</strong>
                  <p>只有任务长期无进展、连续失败或页面提示异常时，再前往系统状态页排查；平时直接回结果页查看输出更有效。</p>
                </article>
              </div>
              <Collapse
                className="advanced-collapse"
                items={[
                  {
                    key: "advanced",
                    label: "高级参数，默认可保持不变",
                    children: (
                      <div className="template-form-grid">
                        <Form.Item name="execution_profile" label="成交假设">
                          <Select options={[{ label: "真实成交口径", value: "realistic" }, { label: "理想成交口径", value: "research" }]} />
                        </Form.Item>
                        <Form.Item name="lookback_days" label="先回看多少天历史">
                          <InputNumber min={1} style={{ width: "100%" }} />
                        </Form.Item>
                        <Form.Item name="validation_ratio" label="最后留多少比例做验证">
                          <InputNumber min={0.05} max={0.95} step={0.05} style={{ width: "100%" }} />
                        </Form.Item>
                        <Form.Item name="jobs" label="同时试几组参数">
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
                        <Form.Item name="left_side_policy" label="左侧行情时怎么处理">
                          <Select
                            allowClear
                            options={[
                              { label: "持有", value: "hold" },
                              { label: "强制离场", value: "force_exit" },
                              { label: "两种都保留", value: "both" },
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
                提交回测任务
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
            <Descriptions.Item label="成交假设">{executionProfileLabel(selectedTemplate.execution_profile)}</Descriptions.Item>
            <Descriptions.Item label="说明">{selectedTemplate.description || "使用模板默认参数"}</Descriptions.Item>
            <Descriptions.Item label="同时试几组参数">{selectedTemplate.jobs}</Descriptions.Item>
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
          <Empty description="当前还没有回测任务，提交后结果会显示在这里。" />
        ) : (
          <>
            <div className="job-summary-banner">
              <div className="job-summary-main">
                <strong>优先检查最近任务，再决定是否展开完整历史</strong>
                <p>当前最重要的是确认是否已生成报告、失败原因是否重复，以及是否仍有任务在执行，而不是直接浏览全部历史记录。</p>
              </div>
              <div className="job-summary-metrics">
                <span>执行中 {runningJobs.length}</span>
                <span>排队中 {queuedJobs.length}</span>
                <span>失败 {failedJobs.length}</span>
                <span>已完成 {succeededJobs.length}</span>
              </div>
              <div className="job-summary-actions">
                {latestSucceededJob?.reports?.[0]?.id ? (
                  <Button type="primary">
                    <Link href={`/reports/${latestSucceededJob.reports[0].id}`}>查看最新结果</Link>
                  </Button>
                ) : null}
                <Button>
                  <Link href="/reports">进入结果库</Link>
                </Button>
              </div>
            </div>

            <div className="job-mobile-list">
              {recentJobs.map((job) => {
                const payload = job.request_payload;
                const templateName = (payload.template_snapshot as { template_name?: string } | undefined)?.template_name;
                const primaryAction = buildJobPrimaryAction(job);
                return (
                  <article key={job.id} className="job-mobile-card">
                    <div className="job-mobile-card-head">
                      <div>
                        <strong>任务 #{job.id}</strong>
                        <span>{String(payload.symbol ?? "-")} / {String(payload.interval ?? "-")} / {strategyLabel(String(payload.strategy_kind ?? "-"))}</span>
                      </div>
                      <StatusTag value={job.status} label={backtestStatusLabel(job.status)} />
                    </div>
                    <p>{buildJobReadingHint(job)}</p>
                    <div className="job-mobile-metrics">
                      <span>进度 {job.progress_pct.toFixed(0)}%</span>
                      <span>模板 {templateName ?? "未选择"}</span>
                    </div>
                    {job.error_message ? <p className="job-mobile-error">{job.error_message}</p> : null}
                    <div className="job-mobile-actions">
                      {primaryAction.href ? (
                        <Button type="primary">
                          <Link href={primaryAction.href}>{primaryAction.label}</Link>
                        </Button>
                      ) : (
                        <Button disabled={primaryAction.disabled}>{primaryAction.label}</Button>
                      )}
                      <Button disabled={!["queued", "running"].includes(job.status)} onClick={() => void cancelJob(job.id)}>
                        取消任务
                      </Button>
                      <Button disabled={job.status !== "failed"} onClick={() => void retryJob(job.id)}>
                        按原配置重跑
                      </Button>
                    </div>
                  </article>
                );
              })}
            </div>
            <div className="detail-secondary-hint">
              <strong>只有在需要逐条核对或批量处理时，再展开下面的完整历史</strong>
              <p>如果你只是确认是否成功生成报告、是否仍有任务在执行，以及失败原因是否重复，前面的任务卡通常已经足够。</p>
            </div>

            <Collapse
              className="advanced-table-panel"
              ghost
              items={[
                {
                  key: "history",
                  label: (
                    <div className="advanced-trace-label">
                      <strong>批量处理或逐条核对时，再看完整历史</strong>
                      <span>这里更适合批量取消、批量重试，或按列核对每条任务的状态、时间与错误信息。</span>
                    </div>
                  ),
                  children: (
                    <>
                      <div className="table-toolbar">
                        <ToolbarCount>已选 {selectedJobIds.length} 条，仅在需要批量处理时再操作。</ToolbarCount>
                        <Space>
                          <Button size="small" disabled={selectedJobIds.length === 0} onClick={() => void bulkCancelJobs()}>
                            取消所选任务
                          </Button>
                          <Button size="small" disabled={selectedJobIds.length === 0} onClick={() => void bulkRetryJobs()}>
                            重跑所选任务
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
                          { title: "回测编号", dataIndex: "id", width: 88, fixed: "left" },
                          { title: "标的", render: (_, row) => String(row.request_payload.symbol ?? "-"), width: 120 },
                          { title: "周期", render: (_, row) => String(row.request_payload.interval ?? "-"), width: 90 },
                          { title: "策略", render: (_, row) => strategyLabel(String(row.request_payload.strategy_kind ?? "-")), width: 160, ellipsis: true },
                          { title: "模板", render: (_, row) => String((row.request_payload.template_snapshot as { template_name?: string } | undefined)?.template_name ?? "-"), ellipsis: true },
                          { title: "状态", dataIndex: "status", width: 110, render: (value: string) => <StatusTag value={value} label={backtestStatusLabel(value)} /> },
                          { title: "进度", dataIndex: "progress_pct", width: 90, render: (value: number) => `${value.toFixed(0)}%` },
                          { title: "提交时间", dataIndex: "submitted_at", width: 180 },
                          { title: "完成时间", dataIndex: "completed_at", width: 180 },
                          { title: "错误信息", dataIndex: "error_message", ellipsis: true },
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
                                  重跑
                                </Button>
                              </Space>
                            ),
                          },
                        ]}
                      />
                      <Typography.Paragraph className="table-help">
                        任务完成后会自动生成结果，可直接进入结果库查看；若执行失败，常见原因通常是覆盖不足、模板不匹配或参数组合不适应当前样本。
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
