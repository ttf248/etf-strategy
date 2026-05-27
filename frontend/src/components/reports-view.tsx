"use client";

import { StarFilled, StarOutlined } from "@ant-design/icons";
import { Button, Card, Empty, Input, Select, Space, Table, Tag, Typography } from "antd";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { apiFetch, type ReportSummary } from "@/lib/api";
import { FormatPercent, MetricCard, PageHeader, ToolbarCount } from "@/components/platform-ui";
import { strategyLabel } from "@/lib/strategy-template-config";
import { buildBacktestLaunchHref } from "@/lib/beginner-presets";

const FAVORITE_REPORTS_STORAGE_KEY = "etf-strategy.favorite-report-ids";

type Verdict = {
  label: string;
  color: string;
  description: string;
};

function getValidationMetrics(report: ReportSummary) {
  const validation = report.summary_metrics.validation ?? {};
  const netReturn = Number(validation.NetReturnPct ?? validation.ReturnPct ?? 0);
  const maxDrawdown = Number(validation.MaxDrawdownPct ?? 0);
  const closedTrades = Number(validation.ClosedTrades ?? 0);
  return { netReturn, maxDrawdown, closedTrades };
}

function buildVerdict(netReturn: number, maxDrawdown: number): Verdict {
  if (netReturn > 0 && maxDrawdown <= 8) {
    return { label: "表现较稳", color: "green", description: "样本外收益为正，回撤压力相对可控。" };
  }
  if (netReturn > 0) {
    return { label: "有收益但波动大", color: "gold", description: "收益为正，但需要重点检查回撤。" };
  }
  if (netReturn === 0) {
    return { label: "没有触发交易", color: "default", description: "样本外阶段可能没有满足开仓条件。" };
  }
  return { label: "暂不理想", color: "red", description: "样本外收益为负，建议换参数或换标的。" };
}

function buildRerunHref(report: ReportSummary) {
  return buildBacktestLaunchHref({
    symbol: report.symbol,
    interval: report.interval,
    strategyKind: report.strategy_kind,
  });
}

function parseCompareIds(values: string[]): number[] {
  const uniqueIds = new Set<number>();
  for (const value of values) {
    for (const item of value.split(",")) {
      const parsed = Number(item.trim());
      if (Number.isFinite(parsed)) {
        uniqueIds.add(parsed);
      }
    }
  }
  return Array.from(uniqueIds).slice(0, 4);
}

export function ReportsView() {
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [keyword, setKeyword] = useState("");
  const [interval, setInterval] = useState<string | undefined>(undefined);
  const [selectedReportIds, setSelectedReportIds] = useState<number[]>([]);
  const [favoriteReportIds, setFavoriteReportIds] = useState<number[]>([]);
  const [showFavoritesOnly, setShowFavoritesOnly] = useState(false);
  const [favoritesHydrated, setFavoritesHydrated] = useState(false);
  const searchParams = useSearchParams();
  const searchPresetAppliedRef = useRef(false);

  useEffect(() => {
    void apiFetch<ReportSummary[]>("/api/reports?limit=200").then(setReports);
  }, []);

  useEffect(() => {
    queueMicrotask(() => {
      if (typeof window === "undefined") {
        setFavoritesHydrated(true);
        return;
      }
      try {
        const storedValue = window.localStorage.getItem(FAVORITE_REPORTS_STORAGE_KEY);
        if (!storedValue) {
          setFavoritesHydrated(true);
          return;
        }
        const parsed = JSON.parse(storedValue);
        if (Array.isArray(parsed)) {
          setFavoriteReportIds(parsed.map(Number).filter(Number.isFinite));
        }
      } catch {
        window.localStorage.removeItem(FAVORITE_REPORTS_STORAGE_KEY);
      } finally {
        setFavoritesHydrated(true);
      }
    });
  }, []);

  const queryPreset = useMemo(() => {
    const compareIds = parseCompareIds(searchParams.getAll("compare"));
    const keywordValue = searchParams.get("keyword")?.trim().toUpperCase();
    const intervalValue = searchParams.get("interval")?.trim();
    if (compareIds.length === 0 && !keywordValue && !intervalValue) {
      return null;
    }
    return {
      compareIds,
      keyword: keywordValue || undefined,
      interval: intervalValue || undefined,
    };
  }, [searchParams]);

  useEffect(() => {
    if (searchPresetAppliedRef.current || !queryPreset) {
      return;
    }
    queueMicrotask(() => {
      if (queryPreset.keyword) {
        setKeyword(queryPreset.keyword);
      }
      if (queryPreset.interval) {
        setInterval(queryPreset.interval);
      }
      if (queryPreset.compareIds.length > 0) {
        setSelectedReportIds(queryPreset.compareIds);
      }
      searchPresetAppliedRef.current = true;
    });
  }, [queryPreset]);

  const validFavoriteReportIds = useMemo(
    () => favoriteReportIds.filter((reportId) => reports.some((item) => item.id === reportId)),
    [favoriteReportIds, reports],
  );

  useEffect(() => {
    if (!favoritesHydrated || typeof window === "undefined") {
      return;
    }
    window.localStorage.setItem(FAVORITE_REPORTS_STORAGE_KEY, JSON.stringify(validFavoriteReportIds));
  }, [validFavoriteReportIds, favoritesHydrated]);

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
      const matchesFavorite = !showFavoritesOnly || validFavoriteReportIds.includes(item.id);
      return matchesKeyword && matchesInterval && matchesFavorite;
    });
  }, [reports, keyword, interval, showFavoritesOnly, validFavoriteReportIds]);

  const latestReport = filteredReports[0];
  const positiveReports = filteredReports.filter((item) => getValidationMetrics(item).netReturn > 0).length;
  const favoriteReports = useMemo(
    () => reports.filter((item) => validFavoriteReportIds.includes(item.id)),
    [reports, validFavoriteReportIds],
  );
  const bestReport = filteredReports.reduce<ReportSummary | null>((best, current) => {
    if (!best) {
      return current;
    }
    return getValidationMetrics(current).netReturn > getValidationMetrics(best).netReturn ? current : best;
  }, null);
  const comparedReports = useMemo(
    () => reports.filter((item) => selectedReportIds.includes(item.id)),
    [reports, selectedReportIds],
  );
  const bestComparedReport = useMemo(
    () =>
      comparedReports.reduce<ReportSummary | null>((best, current) => {
        if (!best) {
          return current;
        }
        return getValidationMetrics(current).netReturn > getValidationMetrics(best).netReturn ? current : best;
      }, null),
    [comparedReports],
  );
  const safestComparedReport = useMemo(
    () =>
      comparedReports.reduce<ReportSummary | null>((best, current) => {
        if (!best) {
          return current;
        }
        return getValidationMetrics(current).maxDrawdown < getValidationMetrics(best).maxDrawdown ? current : best;
      }, null),
    [comparedReports],
  );
  const queryComparedReports = useMemo(
    () => reports.filter((item) => queryPreset?.compareIds.includes(item.id) && selectedReportIds.includes(item.id)),
    [queryPreset, reports, selectedReportIds],
  );

  function toggleCompare(reportId: number) {
    setSelectedReportIds((current) => {
      if (current.includes(reportId)) {
        return current.filter((item) => item !== reportId);
      }
      return [...current, reportId].slice(-4);
    });
  }

  function toggleFavorite(reportId: number) {
    setFavoriteReportIds((current) => {
      if (current.includes(reportId)) {
        return current.filter((item) => item !== reportId);
      }
      return [reportId, ...current];
    });
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Results"
        title="查看回测报告"
        description="先看结论和风险，再打开详情看净值曲线、交易记录和参数。"
      />

      <div className="summary-grid">
        <MetricCard label="报告数量" value={filteredReports.length} note="当前筛选范围" />
        <MetricCard label="收益为正" value={positiveReports} note="样本外收益 > 0" />
        <MetricCard label="已收藏" value={favoriteReports.length} note="保存在当前浏览器" />
        <MetricCard
          label="最佳样本外收益"
          value={bestReport ? <FormatPercent value={getValidationMetrics(bestReport).netReturn} /> : "-"}
          note={bestReport ? `${bestReport.symbol} / ${bestReport.interval}` : "暂无报告"}
        />
        <MetricCard label="最近报告" value={latestReport?.symbol ?? "-"} note={latestReport?.created_at ?? "暂无报告"} />
      </div>

      <Card
        size="small"
        title="报告对比"
        className="section-card report-compare-card"
        extra={selectedReportIds.length ? <Button size="small" onClick={() => setSelectedReportIds([])}>清空对比</Button> : null}
      >
        {queryComparedReports.length > 0 ? (
          <div className="compare-prefill-banner">
            <strong>已从详情页带入报告</strong>
            <span>
              {queryComparedReports.map((item) => `#${item.id} ${item.symbol}`).join("、")} 已经加入对比区。
              {selectedReportIds.length < 2 ? " 再勾选 1 到 3 份报告，就能直接比较收益、回撤和交易次数。" : " 现在已经可以直接查看对比结果。"}
            </span>
          </div>
        ) : null}
        {comparedReports.length === 0 ? (
          <Typography.Text type="secondary">从报告列表中选择 2 到 4 份报告，对比样本外收益、最大回撤和交易次数。</Typography.Text>
        ) : (
          <div className="report-compare-stack">
            <div className="report-compare-grid">
              {comparedReports.map((report) => {
                const { netReturn, maxDrawdown, closedTrades } = getValidationMetrics(report);
                return (
                  <article key={report.id} className="report-compare-item">
                    <div className="report-compare-head">
                      <strong>
                        #{report.id} {report.symbol}
                        {validFavoriteReportIds.includes(report.id) ? " · 已收藏" : ""}
                      </strong>
                      <Button size="small" type="link" onClick={() => toggleCompare(report.id)}>移除</Button>
                    </div>
                    <span>{report.interval} / {strategyLabel(report.strategy_kind)}</span>
                    <div className="report-compare-metrics">
                      <span>收益 <FormatPercent value={netReturn} /></span>
                      <span>回撤 {maxDrawdown.toFixed(2)}%</span>
                      <span>交易 {closedTrades}</span>
                    </div>
                    <div className="report-compare-actions">
                      <Button size="small" type="primary">
                        <Link href={`/reports/${report.id}`}>看详情</Link>
                      </Button>
                      <Button size="small">
                        <Link href={buildRerunHref(report)}>按此配置重跑</Link>
                      </Button>
                    </div>
                  </article>
                );
              })}
            </div>
            <div className="report-compare-summary">
              <strong>对比后下一步</strong>
              <p>
                {comparedReports.length === 1
                  ? `当前只带入了 #${comparedReports[0].id} ${comparedReports[0].symbol}，先再选 1 到 3 份报告，才能真正比较哪套策略更稳或更赚钱。`
                  : bestComparedReport
                  ? `收益最高的是 #${bestComparedReport.id} ${bestComparedReport.symbol}。`
                  : "先选出你最关心的那份报告。"}
                {comparedReports.length > 1 && safestComparedReport
                  ? ` 回撤最小的是 #${safestComparedReport.id} ${safestComparedReport.symbol}。`
                  : ""}
                {comparedReports.length > 1
                  ? " 如果你更看重赚钱效率，先打开收益最高那份；如果你更看重稳健，先看回撤最小那份，再决定要不要重跑。"
                  : ""}
              </p>
              <div className="report-compare-summary-actions">
                {comparedReports.length > 1 && bestComparedReport ? (
                  <Button type="primary">
                    <Link href={`/reports/${bestComparedReport.id}`}>打开收益最高报告</Link>
                  </Button>
                ) : null}
                {comparedReports.length > 1 && safestComparedReport ? (
                  <Button>
                    <Link href={buildRerunHref(safestComparedReport)}>按低回撤配置重跑</Link>
                  </Button>
                ) : null}
              </div>
            </div>
          </div>
        )}
      </Card>

      <Card size="small" title="报告列表" className="section-card">
        <div className="table-toolbar">
          <Space wrap>
            <Input placeholder="筛选标的或名称" value={keyword} onChange={(event) => setKeyword(event.target.value)} style={{ width: 240 }} />
            <Select allowClear placeholder="按周期筛选" value={interval} onChange={setInterval} options={intervalOptions} style={{ width: 150 }} />
            <Button
              icon={showFavoritesOnly ? <StarFilled /> : <StarOutlined />}
              type={showFavoritesOnly ? "primary" : "default"}
              onClick={() => setShowFavoritesOnly((current) => !current)}
            >
              {showFavoritesOnly ? "只看收藏中" : "只看收藏"}
            </Button>
          </Space>
          <ToolbarCount>共 {filteredReports.length} 份报告，收藏 {favoriteReports.length} 份</ToolbarCount>
        </div>
        {filteredReports.length === 0 ? (
          <Empty description={showFavoritesOnly ? "暂无收藏报告" : "暂无报告"} />
        ) : (
          <>
            <div className="report-mobile-list">
              {filteredReports.map((report) => {
                const { netReturn, maxDrawdown, closedTrades } = getValidationMetrics(report);
                const verdict = buildVerdict(netReturn, maxDrawdown);
                const isFavorite = validFavoriteReportIds.includes(report.id);
                const isCompared = selectedReportIds.includes(report.id);
                return (
                  <article key={report.id} className="report-mobile-card">
                    <div className="report-mobile-card-head">
                      <div>
                        <strong>#{report.id} {report.symbol}</strong>
                        <span>{report.name || "未命名标的"} / {report.interval}</span>
                      </div>
                      <div className="report-mobile-card-tags">
                        {isFavorite ? <Tag color="gold">已收藏</Tag> : null}
                        <Tag color={verdict.color}>{verdict.label}</Tag>
                      </div>
                    </div>
                    <p>{verdict.description}</p>
                    <div className="report-mobile-metrics">
                      <span>收益 <FormatPercent value={netReturn} /></span>
                      <span>回撤 {maxDrawdown.toFixed(2)}%</span>
                      <span>交易 {closedTrades}</span>
                    </div>
                    <div className="report-mobile-actions">
                      <Button block icon={isFavorite ? <StarFilled /> : <StarOutlined />} onClick={() => toggleFavorite(report.id)}>
                        {isFavorite ? "取消收藏" : "收藏报告"}
                      </Button>
                      <Button block onClick={() => toggleCompare(report.id)}>
                        {isCompared ? "已加入对比" : "加入对比"}
                      </Button>
                    </div>
                    <Button type="primary" block>
                      <Link href={`/reports/${report.id}`}>打开报告详情</Link>
                    </Button>
                    <Button block>
                      <Link href={buildRerunHref(report)}>按此配置重跑</Link>
                    </Button>
                  </article>
                );
              })}
            </div>
            <Table
              className="report-desktop-table"
              rowKey="id"
              size="small"
              dataSource={filteredReports}
              rowSelection={{
                selectedRowKeys: selectedReportIds,
                onChange: (keys) => setSelectedReportIds(keys.map(Number).slice(-4)),
              }}
              pagination={{ pageSize: 12, showSizeChanger: false }}
              scroll={{ x: 980 }}
              columns={[
                { title: "报告", dataIndex: "id", width: 88, fixed: "left", render: (value: number) => `#${value}` },
                { title: "标的", dataIndex: "symbol", width: 120 },
                { title: "名称", dataIndex: "name", ellipsis: true },
                { title: "周期", dataIndex: "interval", width: 90 },
                { title: "策略", dataIndex: "strategy_kind", width: 180, ellipsis: true, render: (value: string) => strategyLabel(value) },
                {
                  title: "结论",
                  width: 150,
                  render: (_, row) => {
                    const { netReturn, maxDrawdown } = getValidationMetrics(row);
                    const verdict = buildVerdict(netReturn, maxDrawdown);
                    return <Tag color={verdict.color}>{verdict.label}</Tag>;
                  },
                },
                {
                  title: "样本外收益",
                  width: 120,
                  render: (_, row) => <FormatPercent value={getValidationMetrics(row).netReturn} />,
                },
                {
                  title: "最大回撤",
                  width: 120,
                  render: (_, row) => `${getValidationMetrics(row).maxDrawdown.toFixed(2)}%`,
                },
                {
                  title: "怎么理解",
                  width: 260,
                  render: (_, row) => {
                    const { netReturn, maxDrawdown } = getValidationMetrics(row);
                    const verdict = buildVerdict(netReturn, maxDrawdown);
                    return <Typography.Text type="secondary">{verdict.description}</Typography.Text>;
                  },
                },
                { title: "生成时间", dataIndex: "created_at", width: 180, ellipsis: true },
                {
                  title: "收藏",
                  width: 110,
                      render: (_, row) => (
                        <Button
                          size="small"
                          type={validFavoriteReportIds.includes(row.id) ? "primary" : "default"}
                          icon={validFavoriteReportIds.includes(row.id) ? <StarFilled /> : <StarOutlined />}
                          onClick={() => toggleFavorite(row.id)}
                        >
                          {validFavoriteReportIds.includes(row.id) ? "已收藏" : "收藏"}
                        </Button>
                      ),
                    },
                {
                  title: "操作",
                  width: 180,
                  fixed: "right",
                  render: (_, row) => (
                    <Space size="small">
                      <Button size="small" type="link">
                        <Link href={`/reports/${row.id}`}>打开</Link>
                      </Button>
                      <Button size="small">
                        <Link href={buildRerunHref(row)}>重跑</Link>
                      </Button>
                    </Space>
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
