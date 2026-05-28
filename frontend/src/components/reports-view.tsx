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

const FAVORITE_REPORTS_STORAGE_KEY = "strategy-studio.favorite-report-ids";

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

type QualityBucket = "all" | "steady_winner" | "beat_buy_hold" | "no_trade" | "needs_review";

function getValidationMetrics(report: ReportSummary) {
  const validation = report.summary_metrics.validation ?? {};
  const netReturn = Number(validation.NetReturnPct ?? validation.ReturnPct ?? 0);
  const maxDrawdown = Number(validation.MaxDrawdownPct ?? 0);
  const closedTrades = Number(validation.ClosedTrades ?? 0);
  const relativeValue = validation.StrategyVsBuyHold ?? validation.GridVsBuyHold;
  const vsBuyHold = typeof relativeValue === "number" && Number.isFinite(relativeValue) ? relativeValue : null;
  const outperformBuyHold =
    typeof validation.OutperformBuyHold === "boolean"
      ? validation.OutperformBuyHold
      : typeof vsBuyHold === "number"
        ? vsBuyHold > 0
        : false;
  return { netReturn, maxDrawdown, closedTrades, vsBuyHold, outperformBuyHold };
}

function buildVerdict(netReturn: number, maxDrawdown: number): Verdict {
  if (netReturn > 0 && maxDrawdown <= 8) {
    return { label: "收益与风险较平衡", color: "green", description: "单独验证收益为正，且回撤暴露相对可控。" };
  }
  if (netReturn > 0) {
    return { label: "正收益但波动较高", color: "gold", description: "收益为正，但应重点检查回撤暴露。" };
  }
  if (netReturn === 0) {
    return { label: "未形成交易", color: "default", description: "单独验证阶段可能未满足开仓条件。" };
  }
  return { label: "当前样本下表现偏弱", color: "red", description: "单独验证收益为负，建议调整参数、周期或标的。" };
}

function buildRerunHref(report: ReportSummary) {
  return buildBacktestLaunchHref({
    symbol: report.symbol,
    interval: report.interval,
    strategyKind: report.strategy_kind,
  });
}

function buildCardHint(report: ReportSummary) {
  const { netReturn, maxDrawdown, closedTrades, outperformBuyHold } = getValidationMetrics(report);
  if (closedTrades === 0) {
    return "该结果更适合先判断触发条件为何未满足，再决定调整标的还是周期。";
  }
  if (netReturn > 0 && maxDrawdown <= 8 && outperformBuyHold) {
    return "该结果已同时体现出正收益、相对可控的回撤，并且跑赢买入持有，适合作为第一优先级复盘对象。";
  }
  if (netReturn > 0 && maxDrawdown <= 8) {
    return "该结果适合优先复盘，再与同标的其他报告做稳健性比较。";
  }
  if (netReturn > 0) {
    return "该结果取得正收益，但应先确认回撤与净值波动是否在可接受范围内。";
  }
  return "该结果更适合作为反向对照，重跑时应优先调整模板、参数或周期。";
}

function matchesQualityBucket(report: ReportSummary, bucket: QualityBucket): boolean {
  const metrics = getValidationMetrics(report);
  if (bucket === "steady_winner") {
    return metrics.closedTrades > 0 && metrics.netReturn > 0 && metrics.maxDrawdown <= 8;
  }
  if (bucket === "beat_buy_hold") {
    return metrics.closedTrades > 0 && metrics.outperformBuyHold;
  }
  if (bucket === "no_trade") {
    return metrics.closedTrades === 0;
  }
  if (bucket === "needs_review") {
    return metrics.closedTrades === 0 || metrics.netReturn < 0 || metrics.maxDrawdown > 12;
  }
  return true;
}

function qualityBucketLabel(bucket: QualityBucket): string {
  if (bucket === "steady_winner") {
    return "稳健正收益";
  }
  if (bucket === "beat_buy_hold") {
    return "跑赢买入持有";
  }
  if (bucket === "no_trade") {
    return "未触发交易";
  }
  if (bucket === "needs_review") {
    return "优先排查";
  }
  return "全部结果";
}

function buildReportSpotlight(report: ReportSummary, isFavorite: boolean): ReportSpotlight {
  const { netReturn, maxDrawdown, closedTrades } = getValidationMetrics(report);
  if (isFavorite) {
    return {
      rank: 0,
      label: "已收藏，优先复盘",
      color: "gold",
      reason: "你已手动收藏该结果，因此默认排在最前，便于持续比较、复盘和重跑。",
    };
  }
  if (closedTrades === 0) {
    return {
      rank: 3,
      label: "优先检查触发条件",
      color: "default",
      reason: "这类结果排在正收益样本之后，建议先确认是否因条件过严导致未触发，再决定是否调整标的、周期或模板。",
    };
  }
  if (netReturn > 0 && maxDrawdown <= 8) {
    return {
      rank: 1,
      label: "优先复盘",
      color: "green",
      reason: "单独验证收益为正且回撤相对可控，适合作为第一批重点复盘样本。",
    };
  }
  if (netReturn > 0) {
    return {
      rank: 2,
      label: "关注波动暴露",
      color: "gold",
      reason: "虽然收益为正，但波动和回撤更高，因此排在更稳健的正收益结果之后，需先判断能否接受。",
    };
  }
  return {
    rank: 4,
    label: "作为反向对照",
    color: "red",
    reason: "该结果默认排在后面，更适合作为反向对照，用于识别应避开的配置组合。",
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
  const [qualityBucket, setQualityBucket] = useState<QualityBucket>("all");
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

  const baseFilteredReports = useMemo(() => {
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

  const filteredReports = useMemo(
    () => baseFilteredReports.filter((item) => matchesQualityBucket(item, qualityBucket)),
    [baseFilteredReports, qualityBucket],
  );

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
  const quickFilterStats = useMemo(
    () => ({
      steady_winner: baseFilteredReports.filter((item) => matchesQualityBucket(item, "steady_winner")).length,
      beat_buy_hold: baseFilteredReports.filter((item) => matchesQualityBucket(item, "beat_buy_hold")).length,
      no_trade: baseFilteredReports.filter((item) => matchesQualityBucket(item, "no_trade")).length,
      needs_review: baseFilteredReports.filter((item) => matchesQualityBucket(item, "needs_review")).length,
    }),
    [baseFilteredReports],
  );
  const recommendedReport = sortedCardReports[0] ?? null;
  const recommendedMetrics = recommendedReport ? getValidationMetrics(recommendedReport) : null;

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
        eyebrow="结果库"
        title="回测结果库"
        description="先判断验证结论与风险收益特征，再进入详情查看净值曲线、交易记录和参数快照。"
      />

      <div className="detail-secondary-hint">
        <strong>这些指标用于快速了解当前结果池分布</strong>
        <p>如果当前目标是先定位最值得复盘的报告，无需逐项理解这些指标；更自然的顺序通常是先浏览下方卡片，再回头用指标确认整体分布。</p>
      </div>
      <div className="summary-grid">
        <MetricCard label="当前结果数" value={filteredReports.length} note="按当前筛选条件计算" />
        <MetricCard label="正收益样本" value={positiveReports} note="更适合优先复盘" />
        <MetricCard label="已收藏报告" value={favoriteReports.length} note="保存在当前浏览器" />
        <MetricCard
          label="当前最高收益"
          value={bestReport ? <FormatPercent value={getValidationMetrics(bestReport).netReturn} /> : "-"}
          note={bestReport ? `${bestReport.symbol} / ${bestReport.interval}` : "暂无报告"}
        />
        <MetricCard label="最近生成" value={latestReport?.symbol ?? "-"} note={latestReport?.created_at ?? "暂无报告"} />
      </div>

      <Card size="small" title="结果快筛" className="section-card">
        <div className="detail-secondary-hint">
          <strong>先按判断目标收窄结果，再决定要不要通读全部卡片</strong>
          <p>如果你当前只想找“最值得先看”的结果，通常不需要浏览完整列表。先切到更贴近当前判断目标的视角，能更快得到可执行结论。</p>
        </div>
        <div className="template-persona-grid">
          {[
            {
              key: "all" as const,
              title: "全部结果",
              count: baseFilteredReports.length,
              description: "保留当前关键词、周期与收藏条件，只是不额外按表现分层。",
            },
            {
              key: "steady_winner" as const,
              title: "稳健正收益",
              count: quickFilterStats.steady_winner,
              description: "优先看正收益且回撤相对可控的样本，更适合作为第一批复盘对象。",
            },
            {
              key: "beat_buy_hold" as const,
              title: "跑赢买入持有",
              count: quickFilterStats.beat_buy_hold,
              description: "优先筛出已证明自己优于最简单持有方案的结果。",
            },
            {
              key: "no_trade" as const,
              title: "未触发交易",
              count: quickFilterStats.no_trade,
              description: "集中排查为什么没成交，避免把时间花在无效样本上。",
            },
            {
              key: "needs_review" as const,
              title: "优先排查",
              count: quickFilterStats.needs_review,
              description: "把负收益、深回撤或未触发交易结果集中出来，便于做反向对照。",
            },
          ].map((item) => (
            <article key={item.key} className="template-persona-card">
              <strong>{item.title}</strong>
              <span>当前 {item.count} 份</span>
              <p>{item.description}</p>
              <Button type={qualityBucket === item.key ? "primary" : "default"} onClick={() => setQualityBucket(item.key)}>
                {qualityBucket === item.key ? `当前视角：${item.title}` : `切到${item.title}`}
              </Button>
            </article>
          ))}
        </div>
      </Card>

      {recommendedReport && recommendedMetrics ? (
        <Card size="small" title="当前推荐先看" className="section-card">
          <div className="start-path-main">
            <strong>
              编号 {recommendedReport.id} {recommendedReport.symbol} / {strategyLabel(recommendedReport.strategy_kind)} / {recommendedReport.interval}
            </strong>
            <p>{buildCardHint(recommendedReport)}</p>
            <div className="start-path-guide-grid">
              <article className="start-path-guide-card">
                <span>当前视角</span>
                <strong>{qualityBucketLabel(qualityBucket)}</strong>
                <p>当前推荐结果是按这个视角下的优先级排序挑出来的，不是简单按时间取第一条。</p>
              </article>
              <article className="start-path-guide-card">
                <span>收益与回撤</span>
                <strong>
                  收益 <FormatPercent value={recommendedMetrics.netReturn} /> / 回撤 {recommendedMetrics.maxDrawdown.toFixed(2)}%
                </strong>
                <p>如果这里已经不符合你的风险预期，通常无需再深入读交易细节。</p>
              </article>
              <article className="start-path-guide-card">
                <span>相对买入持有</span>
                <strong>
                  {typeof recommendedMetrics.vsBuyHold === "number"
                    ? recommendedMetrics.outperformBuyHold
                      ? `期末多赚 ${Math.abs(recommendedMetrics.vsBuyHold).toFixed(2)}`
                      : `期末少赚 ${Math.abs(recommendedMetrics.vsBuyHold).toFixed(2)}`
                    : "暂无对照"}
                </strong>
                <p>这能直接回答“这套策略值不值得替代最简单持有方案”。</p>
              </article>
            </div>
          </div>
          <div className="start-path-actions">
            <Button type="primary">
              <Link href={`/reports/${recommendedReport.id}`}>先打开这份结果</Link>
            </Button>
            <Button>
              <Link href={buildRerunHref(recommendedReport)}>按这套配置重跑</Link>
            </Button>
          </div>
        </Card>
      ) : null}

      <Card
        size="small"
        title="报告对比"
        className="section-card report-compare-card"
        extra={selectedReportIds.length ? <Button size="small" onClick={() => setSelectedReportIds([])}>清空对比</Button> : null}
      >
        <div className="detail-secondary-hint">
          <strong>建议在形成多个候选结果后再进入对比区</strong>
          <p>更自然的顺序通常是：先从下方挑选一份值得复盘的报告打开，确认其结论与风险，再回到这里做并排比较。</p>
        </div>
        {queryComparedReports.length > 0 ? (
          <div className="compare-prefill-banner">
            <strong>已从详情页带入报告</strong>
            <span>
              {queryComparedReports.map((item) => `编号 ${item.id} ${item.symbol}`).join("、")} 已经加入对比区。
              {selectedReportIds.length < 2 ? " 再选择 1 到 3 份报告，即可直接比较收益、回撤和交易次数。" : " 当前已经可以直接查看对比结果。"}
            </span>
          </div>
        ) : null}
        {comparedReports.length === 0 ? (
          <div className="report-compare-empty">
            <strong>先从下方选择候选结果，再决定是否进入对比</strong>
            <p>如果你还没有打开过任何报告，建议先从下方卡片开始。待形成 2 到 4 份候选结果后，再回到这里比较收益、回撤和交易次数。</p>
            <div className="report-compare-empty-actions">
              {bestReport ? (
                <Button type="primary">
                  <Link href={`/reports/${bestReport.id}`}>查看最高收益报告</Link>
                </Button>
              ) : null}
              {latestReport ? (
                <Button>
                  <Link href={`/reports/${latestReport.id}`}>查看最近生成报告</Link>
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
                        <Link href={`/reports/${report.id}`}>查看详情</Link>
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
              <strong>对比结论</strong>
              <p>
                {comparedReports.length === 1
                  ? `当前仅带入编号 ${comparedReports[0].id} ${comparedReports[0].symbol}。继续加入 1 到 3 份报告后，才能比较不同配置的稳健性与收益效率。`
                  : bestComparedReport
                  ? `收益最高的是编号 ${bestComparedReport.id} ${bestComparedReport.symbol}。`
                  : "请先选择当前最关注的报告。"}
                {comparedReports.length > 1 && safestComparedReport
                  ? ` 回撤最小的是编号 ${safestComparedReport.id} ${safestComparedReport.symbol}。`
                  : ""}
                {comparedReports.length > 1
                  ? " 如果更看重收益效率，可优先打开收益最高的样本；如果更看重稳健性，可先查看回撤最小的样本，再决定是否重跑。"
                  : ""}
              </p>
              <div className="report-compare-summary-actions">
                {comparedReports.length > 1 && bestComparedReport ? (
                  <Button type="primary">
                    <Link href={`/reports/${bestComparedReport.id}`}>查看最高收益报告</Link>
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

      <Card size="small" title="结果列表" className="section-card">
        <div className="table-toolbar">
          <Space wrap>
            <Input placeholder="按标的或名称筛选" value={keyword} onChange={(event) => setKeyword(event.target.value)} style={{ width: 240 }} />
            <Select allowClear placeholder="按周期筛选" value={interval} onChange={setInterval} options={intervalOptions} style={{ width: 150 }} />
            <Button
              icon={showFavoritesOnly ? <StarFilled /> : <StarOutlined />}
              type={showFavoritesOnly ? "primary" : "default"}
              onClick={() => setShowFavoritesOnly((current) => !current)}
            >
              {showFavoritesOnly ? "仅显示收藏报告" : "只看收藏报告"}
            </Button>
            {qualityBucket !== "all" ? <Button onClick={() => setQualityBucket("all")}>清除结果快筛</Button> : null}
          </Space>
          <ToolbarCount>
            当前结果 {filteredReports.length} 份
            {qualityBucket !== "all" ? `，当前视角：${qualityBucketLabel(qualityBucket)}` : ""}
            ，已收藏 {favoriteReports.length} 份
          </ToolbarCount>
        </div>
        {filteredReports.length === 0 ? (
          <Empty description={showFavoritesOnly ? "当前筛选下暂无收藏报告" : qualityBucket === "all" ? "暂无报告" : `当前没有“${qualityBucketLabel(qualityBucket)}”结果`} />
        ) : (
          <>
            <div className="report-library-banner">
              <strong>报告默认按复盘优先级排序，而非简单按时间堆叠</strong>
              <p>排序顺序固定为：收藏报告优先，其次是回撤更可控的正收益结果，然后是高波动正收益、未触发交易结果，最后是反向对照。只有在需要同时勾选多份报告或查看完整字段时，再展开下方高级表格。</p>
              <div className="report-reading-order-tags">
                <span>1. 收藏报告</span>
                <span>2. 稳健正收益</span>
                <span>3. 高波动正收益</span>
                <span>4. 未触发交易</span>
                <span>5. 反向对照</span>
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
                        <strong>{report.symbol}，编号 {report.id}</strong>
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
                    <Button type="primary" block>
                      <Link href={`/reports/${report.id}`}>查看详情</Link>
                    </Button>
                    <div className="report-mobile-actions">
                      <Button block onClick={() => toggleCompare(report.id)}>
                        {isCompared ? "已加入对比" : "加入对比"}
                      </Button>
                      <Button block icon={isFavorite ? <StarFilled /> : <StarOutlined />} onClick={() => toggleFavorite(report.id)}>
                        {isFavorite ? "取消收藏" : "加入收藏"}
                      </Button>
                    </div>
                    <Button block>
                      <Link href={buildRerunHref(report)}>按该配置重跑</Link>
                    </Button>
                  </article>
                );
              })}
            </div>
            <div className="detail-secondary-hint">
              <strong>只有在需要逐列核对或同时勾选多份结果时，再展开下面的完整表</strong>
              <p>如果当前只是浏览这批结果，前面的卡片通常已经足够。完整表格更适合对照字段、批量勾选和核查生成时间等细节。</p>
            </div>
            <Collapse
              className="advanced-table-panel"
              ghost
              items={[
                {
                  key: "desktop-table",
                  label: (
                    <div className="advanced-trace-label">
                      <strong>需要逐列核对时，再看完整表格</strong>
                      <span>这里更适合多选比较、按列查看全部字段，或确认每份结果的生成时间、策略与编号。</span>
                    </div>
                  ),
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
                          title: "优先级说明",
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
