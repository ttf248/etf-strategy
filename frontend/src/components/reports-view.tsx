"use client";

import { StarFilled, StarOutlined } from "@ant-design/icons";
import { Button, Card, Collapse, Empty, Input, Select, Space, Table, Tag, Typography } from "antd";
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

type ReportSpotlight = {
  rank: number;
  label: string;
  color: string;
  reason: string;
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
    return { label: "表现较稳", color: "green", description: "单独验证收益为正，回撤压力相对可控。" };
  }
  if (netReturn > 0) {
    return { label: "有收益但波动大", color: "gold", description: "收益为正，但需要重点检查回撤。" };
  }
  if (netReturn === 0) {
    return { label: "没有触发交易", color: "default", description: "单独验证阶段可能没有满足开仓条件。" };
  }
  return { label: "暂不理想", color: "red", description: "单独验证收益为负，建议换参数或换标的。" };
}

function buildRerunHref(report: ReportSummary) {
  return buildBacktestLaunchHref({
    symbol: report.symbol,
    interval: report.interval,
    strategyKind: report.strategy_kind,
  });
}

function buildCardHint(report: ReportSummary) {
  const { netReturn, maxDrawdown, closedTrades } = getValidationMetrics(report);
  if (closedTrades === 0) {
    return "这份结果更适合先判断为什么没成交，再决定换标的还是换周期。";
  }
  if (netReturn > 0 && maxDrawdown <= 8) {
    return "这份结果适合优先细看，再和同标的其他报告做稳健性对比。";
  }
  if (netReturn > 0) {
    return "这份结果有收益，但要先看回撤和净值曲线是否在你的承受范围内。";
  }
  return "这份结果更适合当作反面对照，重跑时优先换模板、参数或周期。";
}

function buildReportSpotlight(report: ReportSummary, isFavorite: boolean): ReportSpotlight {
  const { netReturn, maxDrawdown, closedTrades } = getValidationMetrics(report);
  if (isFavorite) {
    return {
      rank: 0,
      label: "已收藏，优先回看",
      color: "gold",
      reason: "你已经手动收藏了这份结果，所以默认排在最前，方便反复比较、复盘和重跑。",
    };
  }
  if (closedTrades === 0) {
    return {
      rank: 3,
      label: "先查为什么没成交",
      color: "default",
      reason: "这类结果会排在正收益报告后面，先确认是不是条件过严，再决定要不要换标的、周期或模板。",
    };
  }
  if (netReturn > 0 && maxDrawdown <= 8) {
    return {
      rank: 1,
      label: "适合先看",
      color: "green",
      reason: "单独验证收益为正，回撤也相对可控，适合作为第一批重点复盘的候选结果。",
    };
  }
  if (netReturn > 0) {
    return {
      rank: 2,
      label: "重点看波动",
      color: "gold",
      reason: "虽然收益为正，但波动和回撤更大，所以排在更稳的正收益结果后面，先判断你能否接受。",
    };
  }
  return {
    rank: 4,
    label: "适合做反面对照",
    color: "red",
    reason: "这份结果默认排在后面，更适合拿来和前面的候选结果做反面对照，判断该避开什么配置。",
  };
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
  const sortedCardReports = useMemo(() => {
    return [...filteredReports].sort((left, right) => {
      const leftSpotlight = buildReportSpotlight(left, validFavoriteReportIds.includes(left.id));
      const rightSpotlight = buildReportSpotlight(right, validFavoriteReportIds.includes(right.id));
      if (leftSpotlight.rank !== rightSpotlight.rank) {
        return leftSpotlight.rank - rightSpotlight.rank;
      }
      const leftMetrics = getValidationMetrics(left);
      const rightMetrics = getValidationMetrics(right);
      if (leftMetrics.netReturn !== rightMetrics.netReturn) {
        return rightMetrics.netReturn - leftMetrics.netReturn;
      }
      if (leftMetrics.maxDrawdown !== rightMetrics.maxDrawdown) {
        return leftMetrics.maxDrawdown - rightMetrics.maxDrawdown;
      }
      return right.id - left.id;
    });
  }, [filteredReports, validFavoriteReportIds]);

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
        eyebrow="查看报告"
        title="查看回测报告"
        description="先看结论和风险，再打开详情看净值曲线、交易记录和参数。"
      />

      <div className="summary-grid">
        <MetricCard label="报告数量" value={filteredReports.length} note="当前筛选范围" />
        <MetricCard label="收益为正" value={positiveReports} note="单独验证收益 > 0" />
        <MetricCard label="已收藏" value={favoriteReports.length} note="保存在当前浏览器" />
        <MetricCard
          label="最佳单独验证收益"
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
              {queryComparedReports.map((item) => `编号 ${item.id} ${item.symbol}`).join("、")} 已经加入对比区。
              {selectedReportIds.length < 2 ? " 再勾选 1 到 3 份报告，就能直接比较收益、回撤和交易次数。" : " 现在已经可以直接查看对比结果。"}
            </span>
          </div>
        ) : null}
        {comparedReports.length === 0 ? (
          <div className="report-compare-empty">
            <strong>先从下面的报告卡片挑 2 到 4 份</strong>
            <p>先别急着看表格。先挑你最想比较的几份结果，再一起看收益、回撤和交易次数，更符合第一次复盘的阅读顺序。</p>
            <div className="report-compare-empty-actions">
              {bestReport ? (
                <Button type="primary">
                  <Link href={`/reports/${bestReport.id}`}>先打开收益最高报告</Link>
                </Button>
              ) : null}
              {latestReport ? (
                <Button>
                  <Link href={`/reports/${latestReport.id}`}>打开最近生成报告</Link>
                </Button>
              ) : null}
            </div>
          </div>
        ) : (
          <div className="report-compare-stack">
            <div className="report-compare-grid">
              {comparedReports.map((report) => {
                const { netReturn, maxDrawdown, closedTrades } = getValidationMetrics(report);
                return (
                  <article key={report.id} className="report-compare-item">
                    <div className="report-compare-head">
                      <strong>
                        编号 {report.id} {report.symbol}
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
                  ? `当前只带入了编号 ${comparedReports[0].id} ${comparedReports[0].symbol}，先再选 1 到 3 份报告，才能真正比较哪套策略更稳或更赚钱。`
                  : bestComparedReport
                  ? `收益最高的是编号 ${bestComparedReport.id} ${bestComparedReport.symbol}。`
                  : "先选出你最关心的那份报告。"}
                {comparedReports.length > 1 && safestComparedReport
                  ? ` 回撤最小的是编号 ${safestComparedReport.id} ${safestComparedReport.symbol}。`
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

      <Card size="small" title="先挑几份值得细看的报告" className="section-card">
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
            <div className="report-library-banner">
              <strong>报告默认不是按时间堆叠，而是按更适合先看的顺序排好</strong>
              <p>排序顺序固定为：先看收藏，再看回撤更可控的正收益结果，然后看高波动正收益、没成交结果，最后再看反面对照。只有当你需要同时勾选几份报告，或者细看全部字段时，再展开下面的高级表格视图。</p>
              <div className="report-reading-order-tags">
                <span>1. 先看收藏</span>
                <span>2. 稳健正收益</span>
                <span>3. 高波动正收益</span>
                <span>4. 没成交结果</span>
                <span>5. 反面对照</span>
              </div>
            </div>
            <div className="report-mobile-list">
              {sortedCardReports.map((report) => {
                const { netReturn, maxDrawdown, closedTrades } = getValidationMetrics(report);
                const verdict = buildVerdict(netReturn, maxDrawdown);
                const isFavorite = validFavoriteReportIds.includes(report.id);
                const isCompared = selectedReportIds.includes(report.id);
                const spotlight = buildReportSpotlight(report, isFavorite);
                return (
                  <article key={report.id} className="report-mobile-card">
                    <div className="report-mobile-card-head">
                      <div>
                        <strong>编号 {report.id} {report.symbol}</strong>
                        <span>{report.name || "未命名标的"} / {report.interval}</span>
                      </div>
                      <div className="report-mobile-card-tags">
                        {isFavorite ? <Tag color="gold">已收藏</Tag> : null}
                        <Tag color={verdict.color}>{verdict.label}</Tag>
                      </div>
                    </div>
                    <div className="report-spotlight">
                      <div className="report-spotlight-head">
                        <Tag color={spotlight.color}>{spotlight.label}</Tag>
                        <span>{strategyLabel(report.strategy_kind)} / {report.interval}</span>
                      </div>
                      <p>{spotlight.reason}</p>
                    </div>
                    <p className="report-card-hint">{buildCardHint(report)}</p>
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
            <Collapse
              className="advanced-table-panel"
              ghost
              items={[
                {
                  key: "desktop-table",
                  label: "高级表格视图：多选比较与精细筛选",
                  children: (
                    <Table
                      className="report-desktop-table"
                      rowKey="id"
                      size="small"
                      dataSource={sortedCardReports}
                      rowSelection={{
                        selectedRowKeys: selectedReportIds,
                        onChange: (keys) => setSelectedReportIds(keys.map(Number).slice(-4)),
                      }}
                      pagination={{ pageSize: 12, showSizeChanger: false }}
                      scroll={{ x: 980 }}
                      columns={[
                        { title: "报告编号", dataIndex: "id", width: 88, fixed: "left", render: (value: number) => String(value) },
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
                          title: "单独验证收益",
                          width: 120,
                          render: (_, row) => <FormatPercent value={getValidationMetrics(row).netReturn} />,
                        },
                        {
                          title: "最大回撤",
                          width: 120,
                          render: (_, row) => `${getValidationMetrics(row).maxDrawdown.toFixed(2)}%`,
                        },
                        {
                          title: "为什么先看",
                          width: 240,
                          render: (_, row) => {
                            const spotlight = buildReportSpotlight(row, validFavoriteReportIds.includes(row.id));
                            return (
                              <Space direction="vertical" size={4}>
                                <Tag color={spotlight.color}>{spotlight.label}</Tag>
                                <Typography.Text type="secondary">{spotlight.reason}</Typography.Text>
                              </Space>
                            );
                          },
                        },
                        {
                          title: "怎么理解",
                          width: 260,
                          render: (_, row) => <Typography.Text type="secondary">{buildCardHint(row)}</Typography.Text>,
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
