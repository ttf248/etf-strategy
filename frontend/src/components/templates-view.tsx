"use client";

import Link from "next/link";
import { Button, Card, Drawer, Form, Input, InputNumber, message, Select, Space, Switch, Table, Tag, Typography } from "antd";
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

const executionProfiles = [
  { label: "实盘口径", value: "realistic" },
  { label: "研究口径", value: "research" },
];

const strategyGuide: Record<string, { scene: string; level: string }> = {
  grid: { scene: "震荡行情，低买高卖", level: "新手可先用" },
  dca: { scene: "长期分批买入", level: "最容易理解" },
  daily_rebound: { scene: "日线超跌反弹", level: "需要看回撤" },
  minute_rebound: { scene: "分钟级急跌反抽", level: "偏进阶" },
  minute_rebound_with_fade_filter: { scene: "带过滤的分钟反抽", level: "偏进阶" },
  minute_index_grid_retrace: { scene: "指数回落后的网格", level: "偏进阶" },
};

export function TemplatesView() {
  const [form] = Form.useForm<TemplateFormValues>();
  const [templates, setTemplates] = useState<StrategyTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState<StrategyTemplate | null>(null);
  const [filters, setFilters] = useState<{ strategy_kind?: string; interval?: string; active?: string }>({});
  const [messageApi, contextHolder] = message.useMessage();
  const strategyKind = Form.useWatch("strategy_kind", form) ?? "grid";
  const parameterSpecs = parameterFieldSpecsByStrategy[strategyKind] ?? [];

  const filteredTemplates = useMemo(() => {
    return templates.filter((item) => {
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
    });
  }, [filters, templates]);

  const recommendedTemplates = useMemo(() => {
    return templates
      .filter((item) => item.is_active)
      .sort((left, right) => {
        const defaultScore = Number(right.is_default) - Number(left.is_default);
        if (defaultScore !== 0) {
          return defaultScore;
        }
        return left.updated_at < right.updated_at ? 1 : -1;
      })
      .slice(0, 4);
  }, [templates]);

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

  return (
    <div className="page-stack">
      {contextHolder}
      <PageHeader
        eyebrow="Strategy Presets"
        title="策略模板"
        description="模板是预设好的回测参数。第一次使用建议直接选默认模板，不需要先理解每一个参数。"
        actions={
          <Space>
            <Button onClick={() => void loadTemplates()}>刷新</Button>
            <Button type="primary" onClick={openCreateDrawer}>
              新建高级模板
            </Button>
          </Space>
        }
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

      <Card title="推荐模板" size="small" className="section-card">
        {recommendedTemplates.length === 0 ? (
          <Typography.Text type="secondary">当前没有启用的模板，先到下方启用一个默认模板，再去创建回测。</Typography.Text>
        ) : (
          <div className="template-recommend-grid">
            {recommendedTemplates.map((template) => {
              const guide = strategyGuide[template.strategy_kind] ?? { scene: "自定义策略", level: "自定义" };
              return (
                <article key={template.id} className="template-recommend-card">
                  <div className="template-recommend-head">
                    <div>
                      <strong>{template.template_name}</strong>
                      <span>{strategyLabel(template.strategy_kind)} / {template.interval} / {template.execution_profile}</span>
                    </div>
                    <Tag color={template.is_default ? "gold" : "green"}>{template.is_default ? "默认推荐" : "可直接使用"}</Tag>
                  </div>
                  <p>{template.description || guide.scene}</p>
                  <div className="template-recommend-meta">
                    <span>适合：{guide.scene}</span>
                    <span>难度：{guide.level}</span>
                  </div>
                  <div className="template-recommend-actions">
                    <Button type="primary">
                      <Link href={buildBacktestLaunchHref({ interval: template.interval, strategyKind: template.strategy_kind, templateId: template.id })}>用这个模板去回测</Link>
                    </Button>
                    <Button onClick={() => openEditDrawer(template)}>查看高级参数</Button>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </Card>

      <Card size="small" title="策略模板库" className="section-card">
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
                    <span>{strategyLabel(template.strategy_kind)} / {template.interval} / {template.execution_profile}</span>
                  </div>
                  <Tag color={template.is_default ? "gold" : template.is_active ? "green" : "default"}>
                    {template.is_default ? "默认" : template.is_active ? "启用" : "停用"}
                  </Tag>
                </div>
                <p>{template.description || guide.scene}</p>
                <div className="template-mobile-meta">
                  <span>适合：{guide.scene}</span>
                  <span>难度：{guide.level}</span>
                </div>
                <div className="template-mobile-actions">
                  <Button size="small" type="primary">
                    <Link href={buildBacktestLaunchHref({ interval: template.interval, strategyKind: template.strategy_kind, templateId: template.id })}>去回测</Link>
                  </Button>
                  <Button size="small" onClick={() => openEditDrawer(template)}>
                    编辑高级参数
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
            { title: "口径", dataIndex: "execution_profile", width: 100 },
            { title: "默认", dataIndex: "is_default", width: 90, render: (value: boolean) => <Tag color={value ? "gold" : "default"}>{value ? "默认" : "-"}</Tag> },
            { title: "状态", dataIndex: "is_active", width: 90, render: (value: boolean) => <Tag color={value ? "green" : "default"}>{value ? "启用" : "停用"}</Tag> },
            { title: "说明", dataIndex: "description", ellipsis: true },
            {
              title: "操作",
              width: 250,
              fixed: "right",
              render: (_, row) => (
                <Space size="small">
                  <Button size="small" type="primary">
                    <Link href={buildBacktestLaunchHref({ interval: row.interval, strategyKind: row.strategy_kind, templateId: row.id })}>去回测</Link>
                  </Button>
                  <Button size="small" onClick={() => openEditDrawer(row)}>
                    编辑
                  </Button>
                  <Button size="small" onClick={() => void toggleTemplate(row, !row.is_active)}>
                    {row.is_active ? "停用" : "启用"}
                  </Button>
                </Space>
              ),
            },
          ]}
        />
      </Card>

      <Drawer
        title={editingTemplate ? `编辑高级模板 #${editingTemplate.id}` : "新建高级模板"}
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
            <Form.Item name="template_key" label="模板键" rules={[{ required: true }]}>
              <Input />
            </Form.Item>
            <Form.Item name="strategy_kind" label="策略" rules={[{ required: true }]}>
              <Select options={strategyOptions} />
            </Form.Item>
            <Form.Item name="interval" label="周期" rules={[{ required: true }]}>
              <Select options={intervalOptions} />
            </Form.Item>
            <Form.Item name="execution_profile" label="执行口径">
              <Select options={executionProfiles} />
            </Form.Item>
            <Form.Item name="jobs" label="并行数">
              <InputNumber min={1} max={32} style={{ width: "100%" }} />
            </Form.Item>
            <Form.Item name="validation_start" label="样本外起点">
              <Input placeholder="日线模板使用" />
            </Form.Item>
            <Form.Item name="lookback_days" label="样本内天数">
              <InputNumber min={1} style={{ width: "100%" }} />
            </Form.Item>
            <Form.Item name="validation_ratio" label="样本外比例">
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

          <Typography.Title level={5}>执行口径</Typography.Title>
          <div className="template-form-grid">
            <Form.Item name="commission_bps" label="手续费 bps">
              <InputNumber min={0} step={0.5} style={{ width: "100%" }} />
            </Form.Item>
            <Form.Item name="slippage_bps" label="滑点 bps">
              <InputNumber min={0} step={0.5} style={{ width: "100%" }} />
            </Form.Item>
            <Form.Item name="max_position_ratio" label="最大仓位">
              <InputNumber min={0} max={1} step={0.05} style={{ width: "100%" }} />
            </Form.Item>
            <Form.Item name="stop_loss_pct" label="停手跌幅">
              <InputNumber min={0} step={0.01} style={{ width: "100%" }} />
            </Form.Item>
            <Form.Item name="cooldown_bars" label="冷却 Bar">
              <InputNumber min={0} style={{ width: "100%" }} />
            </Form.Item>
            <Form.Item name="benchmark" label="基准">
              <Select options={[{ label: "买入持有", value: "buy_hold" }, { label: "现金空仓", value: "cash_idle" }]} />
            </Form.Item>
            <Form.Item name="left_side_policy" label="左侧处理">
              <Select
                options={[
                  { label: "持有", value: "hold" },
                  { label: "强平", value: "force_exit" },
                  { label: "双口径", value: "both" },
                ]}
              />
            </Form.Item>
            <Form.Item name="force_exit_loss_pct" label="强平阈值">
              <InputNumber min={0} step={0.01} style={{ width: "100%" }} />
            </Form.Item>
          </div>

          <Typography.Title level={5}>参数空间</Typography.Title>
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
