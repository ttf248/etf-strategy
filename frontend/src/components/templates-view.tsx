"use client";

import Link from "next/link";
import { Button, Card, Collapse, Drawer, Form, Input, InputNumber, message, Select, Space, Switch, Table, Tag, Typography } from "antd";
import { useEffect, useMemo, useState } from "react";
import { apiFetch, type StrategyTemplate } from "@/lib/api";
import {
  buildDefaultParameterSpace,
  decodeNumericArray,
  encodeParameterSpace,
  intervalOptions,
  parameterFieldSpecsByStrategy,
  strategyLabel,
  strategyOptions,
} from "@/lib/strategy-template-config";
import { PageHeader, ToolbarCount } from "@/components/platform-ui";
import { buildBacktestLaunchHref } from "@/lib/beginner-presets";

type TemplateFormValues = {
  template_key?: string;
  template_name?: string;
  strategy_kind?: string;
  interval?: string;
  execution_profile?: string;
  validation_start?: string;
  lookback_days?: number;
  validation_ratio?: number;
  jobs?: number;
  description?: string;
  is_active?: boolean;
  is_default?: boolean;
  commission_bps?: number;
  slippage_bps?: number;
  max_position_ratio?: number;
  stop_loss_pct?: number;
  cooldown_bars?: number;
  benchmark?: string;
  left_side_policy?: string;
  force_exit_loss_pct?: number;
  parameter_fields?: Record<string, string>;
};

type StrategyGuide = {
  scene: string;
  level: string;
  audience: string;
  starterRank: number;
};

type TemplateQuickPick = {
  key: string;
  title: string;
  description: string;
  strategyKind: string;
  interval: string;
};

type TemplateRecommendationSpotlight = {
  label: string;
  color: string;
  reason: string;
};

const executionProfiles = [
  { label: "实盘口径", value: "realistic" },
  { label: "研究口径", value: "research" },
];

function executionProfileLabel(profile: string): string {
  return executionProfiles.find((item) => item.value === profile)?.label ?? profile;
}

const strategyGuide: Record<string, StrategyGuide> = {
  grid: { scene: "震荡行情，低买高卖", level: "新手可先用", audience: "第一次短线试跑", starterRank: 0 },
  dca: { scene: "长期分批买入", level: "最容易理解", audience: "想先看长期持有", starterRank: 1 },
  daily_rebound: { scene: "日线超跌反弹", level: "需要看回撤", audience: "想验证日线择时", starterRank: 2 },
  minute_rebound: { scene: "分钟级急跌反抽", level: "偏进阶", audience: "已经能接受短线波动", starterRank: 3 },
  minute_rebound_with_fade_filter: { scene: "带过滤的分钟反抽", level: "偏进阶", audience: "想进一步过滤噪音", starterRank: 4 },
  minute_index_grid_retrace: { scene: "指数回落后的网格", level: "偏进阶", audience: "专项指数策略研究", starterRank: 5 },
};

const templateQuickPicks: TemplateQuickPick[] = [
  {
    key: "starter",
    title: "第一次先跑一轮",
    description: "优先看 15m 网格默认模板，先把回测流程和报告阅读跑通。",
    strategyKind: "grid",
    interval: "15m",
  },
  {
    key: "long-term",
    title: "想看长期持有",
    description: "先看日线定投模板，最接近日常理解，也最容易和买入持有对照。",
    strategyKind: "dca",
    interval: "1d",
  },
  {
    key: "daily-timing",
    title: "想试日线择时",
    description: "先看日线超跌反弹模板，重点比较收益和回撤是否值得承担。",
    strategyKind: "daily_rebound",
    interval: "1d",
  },
  {
    key: "intraday",
    title: "已经会看分钟波动",
    description: "再看分钟反抽类模板，适合已经理解滑点、回撤和频繁交易的人。",
    strategyKind: "minute_rebound",
    interval: "15m",
  },
];

function templateSortKey(template: StrategyTemplate): [number, number, number, number, string] {
  const guide = strategyGuide[template.strategy_kind] ?? {
    scene: "自定义策略",
    level: "自定义",
    audience: "自定义",
    starterRank: 99,
  };
  const intervalRank = template.interval === "15m" ? 0 : template.interval === "1d" ? 1 : 2;
  return [
    template.is_default ? 0 : 1,
    guide.starterRank,
    intervalRank,
    template.is_active ? 0 : 1,
    template.template_name,
  ];
}

function compareTemplateSort(left: StrategyTemplate, right: StrategyTemplate): number {
  const leftKey = templateSortKey(left);
  const rightKey = templateSortKey(right);
  for (let index = 0; index < leftKey.length; index += 1) {
    if (leftKey[index] < rightKey[index]) {
      return -1;
    }
    if (leftKey[index] > rightKey[index]) {
      return 1;
    }
  }
  return 0;
}

function buildTemplateRecommendationSpotlight(template: StrategyTemplate): TemplateRecommendationSpotlight {
  const guide = strategyGuide[template.strategy_kind] ?? {
    scene: "自定义策略",
    level: "自定义",
    audience: "自定义",
    starterRank: 99,
  };
  if (template.is_default) {
    return {
      label: "默认推荐，优先先试",
      color: "gold",
      reason: "这类模板默认排在最前，适合先把回测流程和报告阅读跑通，再决定要不要改高级参数。",
    };
  }
  if (guide.starterRank <= 1) {
    return {
      label: "适合先上手",
      color: "green",
      reason: `这类模板更容易理解，适合 ${guide.audience}，通常比分钟进阶模板更适合作为第一批候选。`,
    };
  }
  if (template.interval === "1d") {
    return {
      label: "适合先看长期节奏",
      color: "blue",
      reason: "这类模板更适合先理解长期持有或日线节奏，再决定要不要进一步尝试分钟级策略。",
    };
  }
  return {
    label: "更适合进阶再试",
    color: "purple",
    reason: "这类模板通常需要你已经接受更高波动、更多参数或更频繁的交易节奏，所以默认排在后面。",
  };
}

export function TemplatesView() {
  const [form] = Form.useForm<TemplateFormValues>();
  const [templates, setTemplates] = useState<StrategyTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState<StrategyTemplate | null>(null);
  const [filters, setFilters] = useState<{ strategy_kind?: string; interval?: string; active?: string }>({});
  const [selectedTemplateIds, setSelectedTemplateIds] = useState<number[]>([]);
  const [messageApi, contextHolder] = message.useMessage();
  const strategyKind = Form.useWatch("strategy_kind", form) ?? "grid";
  const parameterSpecs = parameterFieldSpecsByStrategy[strategyKind] ?? [];

  const filteredTemplates = useMemo(() => {
    return templates
      .filter((item) => {
        if (filters.strategy_kind && item.strategy_kind !== filters.strategy_kind) {
          return false;
        }
        if (filters.interval && item.interval !== filters.interval) {
          return false;
        }
        if (filters.active === "active" && !item.is_active) {
          return false;
        }
        if (filters.active === "inactive" && item.is_active) {
          return false;
        }
        return true;
      })
      .sort(compareTemplateSort);
  }, [filters, templates]);

  const recommendedTemplates = useMemo(() => {
    return templates
      .filter((item) => item.is_active)
      .sort(compareTemplateSort)
      .slice(0, 4);
  }, [templates]);

  const comparedTemplates = useMemo(
    () => templates.filter((item) => selectedTemplateIds.includes(item.id)).sort(compareTemplateSort),
    [selectedTemplateIds, templates],
  );

  const easiestComparedTemplate = useMemo(() => comparedTemplates[0] ?? null, [comparedTemplates]);
  const longTermComparedTemplate = useMemo(
    () => comparedTemplates.find((item) => item.interval === "1d") ?? null,
    [comparedTemplates],
  );
  const intradayComparedTemplate = useMemo(
    () => comparedTemplates.find((item) => item.interval !== "1d") ?? null,
    [comparedTemplates],
  );
  const hasActiveFilters = Boolean(filters.strategy_kind || filters.interval || filters.active);
  const defaultRecommendedTemplate = useMemo(
    () => recommendedTemplates.find((item) => item.is_default) ?? recommendedTemplates[0] ?? null,
    [recommendedTemplates],
  );

  async function loadTemplates(showSpinner: boolean = true) {
    if (showSpinner) {
      setLoading(true);
    }
    try {
      const payload = await apiFetch<StrategyTemplate[]>("/api/templates");
      setTemplates(payload);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let cancelled = false;
    void apiFetch<StrategyTemplate[]>("/api/templates").then((payload) => {
      if (cancelled) {
        return;
      }
      setTemplates(payload);
      setLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  function openCreateDrawer() {
    const initialStrategy = "grid";
    const initialInterval = "15m";
    setEditingTemplate(null);
    form.resetFields();
    form.setFieldsValue({
      strategy_kind: initialStrategy,
      interval: initialInterval,
      execution_profile: "realistic",
      validation_ratio: 0.25,
      jobs: 1,
      is_active: true,
      is_default: false,
      parameter_fields: encodeParameterSpace(buildDefaultParameterSpace(initialStrategy, initialInterval)),
    });
    setDrawerOpen(true);
  }

  function openEditDrawer(template: StrategyTemplate) {
    setEditingTemplate(template);
    form.resetFields();
    form.setFieldsValue({
      template_key: template.template_key,
      template_name: template.template_name,
      strategy_kind: template.strategy_kind,
      interval: template.interval,
      execution_profile: template.execution_profile,
      validation_start: template.validation_start || undefined,
      lookback_days: template.lookback_days ?? undefined,
      validation_ratio: template.validation_ratio ?? undefined,
      jobs: template.jobs,
      description: template.description,
      is_active: template.is_active,
      is_default: template.is_default,
      commission_bps: Number(template.execution_overrides_json.commission_bps ?? 0),
      slippage_bps: Number(template.execution_overrides_json.slippage_bps ?? 0),
      max_position_ratio: Number(template.execution_overrides_json.max_position_ratio ?? 0),
      stop_loss_pct: Number(template.execution_overrides_json.stop_loss_pct ?? 0),
      cooldown_bars: Number(template.execution_overrides_json.cooldown_bars ?? 0),
      benchmark: String(template.execution_overrides_json.benchmark ?? "buy_hold"),
      left_side_policy: String(template.execution_overrides_json.left_side_policy ?? "both"),
      force_exit_loss_pct: Number(template.execution_overrides_json.force_exit_loss_pct ?? 0),
      parameter_fields: encodeParameterSpace(template.parameter_space_json),
    });
    setDrawerOpen(true);
  }

  function buildPayload(values: TemplateFormValues) {
    const parameterSpace = Object.fromEntries(
      parameterSpecs.map((item) => [item.key, decodeNumericArray(values.parameter_fields?.[item.key] ?? "", item.kind)]),
    );
    return {
      template_key: values.template_key,
      template_name: values.template_name,
      strategy_kind: values.strategy_kind,
      interval: values.interval,
      execution_profile: values.execution_profile,
      validation_start: values.validation_start,
      lookback_days: values.lookback_days,
      validation_ratio: values.validation_ratio,
      jobs: values.jobs,
      execution_overrides_json: {
        commission_bps: values.commission_bps,
        slippage_bps: values.slippage_bps,
        max_position_ratio: values.max_position_ratio,
        stop_loss_pct: values.stop_loss_pct,
        cooldown_bars: values.cooldown_bars,
        benchmark: values.benchmark,
        left_side_policy: values.left_side_policy,
        force_exit_loss_pct: values.force_exit_loss_pct,
      },
      parameter_space_json: parameterSpace,
      description: values.description ?? "",
      is_active: values.is_active ?? true,
      is_default: values.is_default ?? false,
    };
  }

  async function onFinish(values: TemplateFormValues) {
    setSaving(true);
    try {
      const payload = buildPayload(values);
      if (editingTemplate) {
        await apiFetch(`/api/templates/${editingTemplate.id}`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        });
        messageApi.success("模板已更新");
      } else {
        await apiFetch("/api/templates", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        messageApi.success("模板已创建");
      }
      setDrawerOpen(false);
      await loadTemplates();
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }

  async function toggleTemplate(template: StrategyTemplate, isActive: boolean) {
    try {
      await apiFetch(`/api/templates/${template.id}`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: isActive }),
      });
      await loadTemplates();
      messageApi.success(isActive ? "模板已启用" : "模板已停用");
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "更新状态失败");
    }
  }

  function toggleCompare(templateId: number) {
    setSelectedTemplateIds((current) => {
      if (current.includes(templateId)) {
        return current.filter((item) => item !== templateId);
      }
      return [...current, templateId].slice(-4);
    });
  }

  function applyQuickPick(pick: TemplateQuickPick) {
    setFilters({
      strategy_kind: pick.strategyKind,
      interval: pick.interval,
      active: "active",
    });
  }

  return (
    <div className="page-stack">
      {contextHolder}
      <PageHeader
        eyebrow="策略模板"
        title="策略模板"
        description="模板是预设好的回测参数。第一次使用建议直接选默认模板，不需要先理解每一个参数。"
      />

      <div className="template-guide-grid">
        <Card size="small">
          <strong>新手怎么选</strong>
          <span>先选择名称里带“默认模板”的项目，跑通后再对比其他策略。</span>
        </Card>
        <Card size="small">
          <strong>什么时候需要改模板</strong>
          <span>只有当默认参数不适合你的标的、周期或手续费假设时，才需要编辑。</span>
        </Card>
        <Card size="small">
          <strong>模板会被保存快照</strong>
          <span>提交回测时会记录当时参数，后续改模板不会影响历史报告。</span>
        </Card>
      </div>

      <Card size="small" className="section-card start-path-card">
        <div className="start-path-main">
          <strong>
            {defaultRecommendedTemplate
              ? "先从推荐模板里挑一个开始，不要一上来新建高级模板"
              : "当前没有可直接使用的模板，先到高级管理里启用一个默认模板"}
          </strong>
          <p>
            {defaultRecommendedTemplate
              ? "新手更需要先把回测流程和报告阅读跑通，而不是先改参数。只有当默认模板明显不适合你的标的、周期或手续费假设时，再去编辑或新建模板。"
              : "如果当前没有启用模板，先在下方高级管理区启用默认模板，或者在确实需要时新建高级模板。"}
          </p>
          <div className="start-path-guide-grid">
            <article className="start-path-guide-card">
              <span>现在最该做</span>
              <strong>{defaultRecommendedTemplate ? "先用默认模板去回测" : "先启用一个默认模板"}</strong>
              <p>{defaultRecommendedTemplate ? "先把主路径跑通，再回来比较别的模板。" : "当前还没有可直接使用的模板，先保证至少有一个启用模板可选。"}</p>
            </article>
            <article className="start-path-guide-card">
              <span>为什么不先新建</span>
              <strong>先确认默认模板哪里不够用</strong>
              <p>只有当默认模板明显不适合你的标的、周期或手续费假设时，新建或编辑高级模板才有明确价值。</p>
            </article>
            <article className="start-path-guide-card">
              <span>什么时候进高级管理</span>
              <strong>需要维护时再进去</strong>
              <p>例如当前没有启用模板、默认模板不适合当前场景，或者你确实要新增自己的参数范围。</p>
            </article>
          </div>
        </div>
        <div className="start-path-actions">
          {defaultRecommendedTemplate ? (
            <Button type="primary">
              <Link
                href={buildBacktestLaunchHref({
                  interval: defaultRecommendedTemplate.interval,
                  strategyKind: defaultRecommendedTemplate.strategy_kind,
                  templateId: defaultRecommendedTemplate.id,
                })}
              >
                先用默认模板去回测
              </Link>
            </Button>
          ) : null}
          <Button onClick={() => applyQuickPick(templateQuickPicks[0])}>只看第一次先跑一轮</Button>
          {!defaultRecommendedTemplate ? (
            <Button onClick={openCreateDrawer}>确实需要时再新建高级模板</Button>
          ) : null}
        </div>
      </Card>

      <Card title="按你的目标找模板" size="small" className="section-card">
        <div className="template-persona-grid">
          {templateQuickPicks.map((pick) => (
            <article key={pick.key} className="template-persona-card">
              <strong>{pick.title}</strong>
              <span>{pick.description}</span>
              <Button onClick={() => applyQuickPick(pick)}>只看这类模板</Button>
            </article>
          ))}
        </div>
      </Card>

      <Card title="推荐模板" size="small" className="section-card">
        {recommendedTemplates.length === 0 ? (
          <Typography.Text type="secondary">当前没有启用的模板。先展开下方高级管理，启用一个默认模板或新建高级模板，再回到这里选择。</Typography.Text>
        ) : (
          <>
            <div className="template-order-banner">
              <strong>这些模板默认已经按更适合先试的顺序排好</strong>
              <p>排序顺序固定为：先看默认模板，再看更容易上手的长期或基础模板，最后再看分钟进阶和专项模板。这样能避免你一上来就掉进高级参数和复杂节奏里。</p>
              <div className="template-order-tags">
                <span>1. 默认模板</span>
                <span>2. 更易上手</span>
                <span>3. 长期或基础节奏</span>
                <span>4. 分钟进阶与专项</span>
              </div>
            </div>
            <div className="template-recommend-grid">
              {recommendedTemplates.map((template) => {
                const guide = strategyGuide[template.strategy_kind] ?? { scene: "自定义策略", level: "自定义" };
                const spotlight = buildTemplateRecommendationSpotlight(template);
                return (
                  <article key={template.id} className="template-recommend-card">
                    <div className="template-recommend-head">
                      <div>
                        <strong>{template.template_name}</strong>
                        <span>{strategyLabel(template.strategy_kind)} / {template.interval} / {executionProfileLabel(template.execution_profile)}</span>
                      </div>
                      <Tag color={template.is_default ? "gold" : "green"}>{template.is_default ? "默认推荐" : "可直接使用"}</Tag>
                    </div>
                    <div className="template-spotlight">
                      <div className="template-spotlight-head">
                        <Tag color={spotlight.color}>{spotlight.label}</Tag>
                        <span>{strategyLabel(template.strategy_kind)} / {template.interval}</span>
                      </div>
                      <p>{spotlight.reason}</p>
                    </div>
                    <p>{template.description || guide.scene}</p>
                    <div className="template-recommend-meta">
                      <span>适合谁：{guide.audience}</span>
                      <span>适合：{guide.scene}</span>
                      <span>难度：{guide.level}</span>
                    </div>
                    <div className="template-recommend-actions">
                      <Button type="primary">
                        <Link href={buildBacktestLaunchHref({ interval: template.interval, strategyKind: template.strategy_kind, templateId: template.id })}>用这个模板去回测</Link>
                      </Button>
                      <Button onClick={() => toggleCompare(template.id)}>{selectedTemplateIds.includes(template.id) ? "已加入对比" : "加入对比"}</Button>
                      <Button onClick={() => openEditDrawer(template)}>看详细设置</Button>
                    </div>
                  </article>
                );
              })}
            </div>
          </>
        )}
      </Card>

      <Card
        title="模板对比"
        size="small"
        className="section-card template-compare-card"
        extra={selectedTemplateIds.length > 0 ? <Button size="small" onClick={() => setSelectedTemplateIds([])}>清空对比</Button> : null}
      >
        {comparedTemplates.length === 0 ? (
          <Typography.Text type="secondary">先从推荐模板或模板库里选 2 到 4 个模板，对比“适合谁用、周期、难度和下一步建议”。</Typography.Text>
        ) : (
          <div className="template-compare-stack">
            <div className="template-compare-grid">
              {comparedTemplates.map((template) => {
                const guide = strategyGuide[template.strategy_kind] ?? {
                  scene: "自定义策略",
                  level: "自定义",
                  audience: "自定义",
                  starterRank: 99,
                };
                return (
                  <article key={template.id} className="template-compare-item">
                    <div className="template-compare-head">
                      <strong>{template.template_name}</strong>
                      <Button size="small" type="link" onClick={() => toggleCompare(template.id)}>移除</Button>
                    </div>
                    <span>{strategyLabel(template.strategy_kind)} / {template.interval} / {executionProfileLabel(template.execution_profile)}</span>
                    <div className="template-compare-metrics">
                      <span>适合谁：{guide.audience}</span>
                      <span>难度：{guide.level}</span>
                      <span>{template.is_default ? "默认推荐" : template.is_active ? "可直接使用" : "需先启用"}</span>
                    </div>
                    <p>{template.description || guide.scene}</p>
                    <div className="template-compare-actions">
                      <Button size="small" type="primary">
                        <Link href={buildBacktestLaunchHref({ interval: template.interval, strategyKind: template.strategy_kind, templateId: template.id })}>用这个去回测</Link>
                      </Button>
                      <Button size="small" onClick={() => openEditDrawer(template)}>看详细设置</Button>
                    </div>
                  </article>
                );
              })}
            </div>
            <div className="template-compare-summary">
              <strong>对比后怎么选</strong>
              <p>
                {comparedTemplates.length === 1
                  ? `当前只选了 ${comparedTemplates[0].template_name}。再加 1 到 3 个模板，才能更清楚地比较谁更适合第一次试跑、谁更适合长期或分钟策略。`
                  : ""}
                {comparedTemplates.length > 1 && easiestComparedTemplate
                  ? `如果你是第一次跑回测，优先试 ${easiestComparedTemplate.template_name}。`
                  : ""}
                {comparedTemplates.length > 1 && longTermComparedTemplate
                  ? ` 如果你更想看长期持有或日线节奏，可以先试 ${longTermComparedTemplate.template_name}。`
                  : ""}
                {comparedTemplates.length > 1 && intradayComparedTemplate
                  ? ` 如果你已经接受分钟波动，再看 ${intradayComparedTemplate.template_name} 这类短周期模板。`
                  : ""}
              </p>
              <div className="template-compare-summary-actions">
                {easiestComparedTemplate ? (
                  <Button type="primary">
                    <Link
                      href={buildBacktestLaunchHref({
                        interval: easiestComparedTemplate.interval,
                        strategyKind: easiestComparedTemplate.strategy_kind,
                        templateId: easiestComparedTemplate.id,
                      })}
                    >
                      先用最容易上手的模板
                    </Link>
                  </Button>
                ) : null}
                {easiestComparedTemplate ? (
                  <Button onClick={() => openEditDrawer(easiestComparedTemplate)}>看这份模板的详细设置</Button>
                ) : null}
              </div>
            </div>
          </div>
        )}
      </Card>

      <Card size="small" title="高级模板管理" className="section-card">
        <div className="template-management-banner">
          <strong>只有在你需要维护模板时，再展开完整模板库和高级参数编辑</strong>
          <p>日常使用优先在上面的推荐模板和对比区做选择。启用停用、新建模板、完整筛选表和参数编辑都保留在这里，但不再作为首屏主路径。</p>
        </div>
        <div className="template-management-grid">
          <article className="template-management-card">
            <span>什么时候要进这里</span>
            <strong>当前没有可直接用的模板</strong>
            <p>如果推荐区为空，或者你要跑的策略/周期没有启用模板，才需要先来这里启用或新建。</p>
          </article>
          <article className="template-management-card">
            <span>什么时候值得编辑</span>
            <strong>默认模板不适合你的实际条件</strong>
            <p>例如手续费、滑点、仓位或参数范围明显不符合你的标的和交易方式，这时再改高级参数更有意义。</p>
          </article>
          <article className="template-management-card">
            <span>什么时候不用碰</span>
            <strong>只想先跑通和读懂报告时</strong>
            <p>如果你当前只是第一次试跑，优先回到上面的推荐模板和对比区，不需要先维护完整模板库。</p>
          </article>
        </div>
        <Collapse
          className="advanced-table-panel"
          ghost
          items={[
            {
              key: "template-library",
              label: "高级管理：启用停用、新建模板和完整模板库",
              children: (
                <>
                  <div className="table-toolbar">
                    <Space wrap>
                      <Button onClick={() => void loadTemplates()}>刷新模板库</Button>
                      <Button type="primary" onClick={openCreateDrawer}>
                        新建高级模板
                      </Button>
                    </Space>
                    <ToolbarCount>当前共 {filteredTemplates.length} 个模板；只有在需要维护时再处理这里。</ToolbarCount>
                  </div>
                  <div className="table-toolbar">
                    <Space wrap>
                      <Select
                        allowClear
                        placeholder="策略"
                        style={{ width: 220 }}
                        options={strategyOptions}
                        onChange={(value) => setFilters((current) => ({ ...current, strategy_kind: value }))}
                      />
                      <Select
                        allowClear
                        placeholder="周期"
                        style={{ width: 130 }}
                        options={intervalOptions}
                        onChange={(value) => setFilters((current) => ({ ...current, interval: value }))}
                      />
                      <Select
                        allowClear
                        placeholder="状态"
                        style={{ width: 130 }}
                        options={[
                          { label: "启用", value: "active" },
                          { label: "停用", value: "inactive" },
                        ]}
                        onChange={(value) => setFilters((current) => ({ ...current, active: value }))}
                      />
                      {hasActiveFilters ? (
                        <Button onClick={() => setFilters({})}>清空筛选</Button>
                      ) : null}
                    </Space>
                    <ToolbarCount>共 {filteredTemplates.length} 个模板</ToolbarCount>
                  </div>
                  <div className="template-mobile-list">
                    {filteredTemplates.map((template) => {
                      const guide = strategyGuide[template.strategy_kind] ?? { scene: "自定义策略", level: "自定义" };
                      return (
                        <article key={template.id} className="template-mobile-card">
                          <div className="template-mobile-card-head">
                            <div>
                              <strong>{template.template_name}</strong>
                              <span>{strategyLabel(template.strategy_kind)} / {template.interval} / {executionProfileLabel(template.execution_profile)}</span>
                            </div>
                            <Tag color={template.is_default ? "gold" : template.is_active ? "green" : "default"}>
                              {template.is_default ? "默认" : template.is_active ? "启用" : "停用"}
                            </Tag>
                          </div>
                          <p>{template.description || guide.scene}</p>
                          <div className="template-mobile-meta">
                            <span>适合谁：{guide.audience}</span>
                            <span>适合：{guide.scene}</span>
                            <span>难度：{guide.level}</span>
                          </div>
                          <div className="template-mobile-actions">
                            <Button size="small" type="primary">
                              <Link href={buildBacktestLaunchHref({ interval: template.interval, strategyKind: template.strategy_kind, templateId: template.id })}>去回测</Link>
                            </Button>
                            <Button size="small" onClick={() => toggleCompare(template.id)}>
                              {selectedTemplateIds.includes(template.id) ? "已加入对比" : "加入对比"}
                            </Button>
                            <Button size="small" onClick={() => openEditDrawer(template)}>
                              改详细设置
                            </Button>
                            <Button size="small" onClick={() => void toggleTemplate(template, !template.is_active)}>
                              {template.is_active ? "停用" : "启用"}
                            </Button>
                          </div>
                        </article>
                      );
                    })}
                  </div>
                  <Table
                    className="template-desktop-table"
                    rowKey="id"
                    size="small"
                    loading={loading}
                    dataSource={filteredTemplates}
                    pagination={{ pageSize: 12, showSizeChanger: false }}
                    scroll={{ x: 1240 }}
                    columns={[
                      { title: "名称", dataIndex: "template_name", width: 240, fixed: "left" },
                      { title: "策略", dataIndex: "strategy_kind", render: (value: string) => strategyLabel(value), width: 220 },
                      {
                        title: "适合谁",
                        dataIndex: "strategy_kind",
                        width: 180,
                        render: (value: string) => strategyGuide[value]?.audience ?? "自定义策略",
                      },
                      {
                        title: "适合什么",
                        dataIndex: "strategy_kind",
                        width: 220,
                        render: (value: string) => strategyGuide[value]?.scene ?? "自定义策略",
                      },
                      {
                        title: "难度",
                        dataIndex: "strategy_kind",
                        width: 120,
                        render: (value: string) => strategyGuide[value]?.level ?? "自定义",
                      },
                      { title: "周期", dataIndex: "interval", width: 90 },
                      {
                        title: "成交假设",
                        dataIndex: "execution_profile",
                        width: 120,
                        render: (value: string) => executionProfileLabel(value),
                      },
                      { title: "默认", dataIndex: "is_default", width: 90, render: (value: boolean) => <Tag color={value ? "gold" : "default"}>{value ? "默认" : "-"}</Tag> },
                      { title: "状态", dataIndex: "is_active", width: 90, render: (value: boolean) => <Tag color={value ? "green" : "default"}>{value ? "启用" : "停用"}</Tag> },
                      { title: "说明", dataIndex: "description", ellipsis: true },
                      {
                        title: "操作",
                        width: 340,
                        fixed: "right",
                        render: (_, row) => (
                          <Space size="small">
                            <Button size="small" type="primary">
                              <Link href={buildBacktestLaunchHref({ interval: row.interval, strategyKind: row.strategy_kind, templateId: row.id })}>去回测</Link>
                            </Button>
                            <Button size="small" onClick={() => toggleCompare(row.id)}>
                              {selectedTemplateIds.includes(row.id) ? "已对比" : "加入对比"}
                            </Button>
                            <Button size="small" onClick={() => openEditDrawer(row)}>
                              改设置
                            </Button>
                            <Button size="small" onClick={() => void toggleTemplate(row, !row.is_active)}>
                              {row.is_active ? "停用" : "启用"}
                            </Button>
                          </Space>
                        ),
                      },
                    ]}
                  />
                </>
              ),
            },
          ]}
        />
      </Card>

      <Drawer
        title={editingTemplate ? `编辑高级模板，编号 ${editingTemplate.id}` : "新建高级模板"}
        size="large"
        open={drawerOpen}
        destroyOnHidden
        onClose={() => setDrawerOpen(false)}
      >
        <Card size="small" className="advanced-editor-note">
          这里是高级编辑区。新手用户通常不需要修改模板，直接在“创建回测”页选择默认模板即可。
        </Card>
        <Form
          form={form}
          layout="vertical"
          onFinish={onFinish}
          onValuesChange={(changedValues) => {
            if ("strategy_kind" in changedValues || "interval" in changedValues) {
              const nextStrategy = form.getFieldValue("strategy_kind") ?? "grid";
              const nextInterval = form.getFieldValue("interval") ?? "15m";
              form.setFieldValue("parameter_fields", encodeParameterSpace(buildDefaultParameterSpace(nextStrategy, nextInterval)));
            }
          }}
        >
          <Typography.Title level={5}>基础信息</Typography.Title>
          <div className="template-form-grid">
            <Form.Item name="template_name" label="模板名称" rules={[{ required: true }]}>
              <Input />
            </Form.Item>
            <Form.Item name="template_key" label="模板标识" rules={[{ required: true }]}>
              <Input />
            </Form.Item>
            <Form.Item name="strategy_kind" label="策略" rules={[{ required: true }]}>
              <Select options={strategyOptions} />
            </Form.Item>
            <Form.Item name="interval" label="周期" rules={[{ required: true }]}>
              <Select options={intervalOptions} />
            </Form.Item>
            <Form.Item name="execution_profile" label="成交假设">
              <Select options={executionProfiles} />
            </Form.Item>
            <Form.Item name="jobs" label="同时尝试的参数组数">
              <InputNumber min={1} max={32} style={{ width: "100%" }} />
            </Form.Item>
            <Form.Item name="validation_start" label="从哪一天开始算样本外">
              <Input placeholder="日线模板使用" />
            </Form.Item>
            <Form.Item name="lookback_days" label="样本内天数">
              <InputNumber min={1} style={{ width: "100%" }} />
            </Form.Item>
            <Form.Item name="validation_ratio" label="留给样本外验证的比例">
              <InputNumber min={0.05} max={0.95} step={0.05} style={{ width: "100%" }} />
            </Form.Item>
            <Form.Item name="description" label="说明">
              <Input />
            </Form.Item>
            <Form.Item name="is_active" label="启用" valuePropName="checked">
              <Switch />
            </Form.Item>
            <Form.Item name="is_default" label="默认模板" valuePropName="checked">
              <Switch />
            </Form.Item>
          </div>

          <Typography.Title level={5}>成交假设</Typography.Title>
          <div className="template-form-grid">
            <Form.Item name="commission_bps" label="手续费（万分比）">
              <InputNumber min={0} step={0.5} style={{ width: "100%" }} />
            </Form.Item>
            <Form.Item name="slippage_bps" label="滑点（万分比）">
              <InputNumber min={0} step={0.5} style={{ width: "100%" }} />
            </Form.Item>
            <Form.Item name="max_position_ratio" label="最大仓位">
              <InputNumber min={0} max={1} step={0.05} style={{ width: "100%" }} />
            </Form.Item>
            <Form.Item name="stop_loss_pct" label="停手跌幅">
              <InputNumber min={0} step={0.01} style={{ width: "100%" }} />
            </Form.Item>
            <Form.Item name="cooldown_bars" label="冷却 K 线数">
              <InputNumber min={0} style={{ width: "100%" }} />
            </Form.Item>
            <Form.Item name="benchmark" label="默认对照">
              <Select options={[{ label: "买入持有", value: "buy_hold" }, { label: "现金空仓", value: "cash_idle" }]} />
            </Form.Item>
            <Form.Item name="left_side_policy" label="左侧行情时怎么处理">
              <Select
                options={[
                  { label: "持有", value: "hold" },
                  { label: "强制离场", value: "force_exit" },
                  { label: "两种都保留", value: "both" },
                ]}
              />
            </Form.Item>
            <Form.Item name="force_exit_loss_pct" label="达到多大亏损时强制离场">
              <InputNumber min={0} step={0.01} style={{ width: "100%" }} />
            </Form.Item>
          </div>

          <Typography.Title level={5}>可尝试的参数范围</Typography.Title>
          <div className="template-form-grid">
            {parameterSpecs.length === 0 ? (
              <Card size="small">当前策略不需要自定义寻参空间。</Card>
            ) : (
              parameterSpecs.map((field) => (
                <Form.Item key={field.key} name={["parameter_fields", field.key]} label={field.label} rules={[{ required: true }]}>
                  <Input placeholder="逗号分隔，例如 0.01,0.02,0.03" />
                </Form.Item>
              ))
            )}
          </div>

          <div className="form-action-row">
            <Button onClick={() => setDrawerOpen(false)}>取消</Button>
            <Button type="primary" htmlType="submit" loading={saving}>
              保存
            </Button>
          </div>
        </Form>
      </Drawer>
    </div>
  );
}
