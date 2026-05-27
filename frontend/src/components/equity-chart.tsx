"use client";

import dynamic from "next/dynamic";
import { useMemo } from "react";

const ReactECharts = dynamic(() => import("echarts-for-react"), { ssr: false });

type EquityPoint = {
  curve_time: string;
  equity: number;
  drawdown_pct: number;
  return_pct: number;
};

type EquityChartProps = {
  points: EquityPoint[];
};

export function EquityChart({ points }: EquityChartProps) {
  const highestEquityPoint = points.reduce((best, item) => (item.equity > best.equity ? item : best), points[0]);
  const worstDrawdownPoint = points.reduce((best, item) => (Math.abs(item.drawdown_pct) > Math.abs(best.drawdown_pct) ? item : best), points[0]);
  const equitySeries = points.map((item) => item.equity);
  const returnSeries = points.map((item) => item.return_pct);
  const drawdownSeries = points.map((item) => -Math.abs(item.drawdown_pct));
  const percentValues = [...returnSeries, ...drawdownSeries, 0];
  const percentMin = Math.min(...percentValues);
  const percentMax = Math.max(...percentValues);
  const percentPadding = Math.max(1, Math.ceil((percentMax - percentMin) * 0.18));

  const option = useMemo(
    () => ({
      color: ["#1d4ed8", "#0f766e", "#c2413a"],
      tooltip: {
        trigger: "axis",
        backgroundColor: "rgba(15, 23, 42, 0.92)",
        borderWidth: 0,
        textStyle: { color: "#ffffff" },
        formatter: (params: Array<{ axisValueLabel: string; color: string; seriesName: string; data: number }>) => {
          const lines = [params[0]?.axisValueLabel ?? "-"];
          params.forEach((item) => {
            const value = item.seriesName === "权益" ? item.data.toLocaleString() : `${item.data.toFixed(2)}%`;
            lines.push(`${item.seriesName}：${value}`);
          });
          return lines.join("<br/>");
        },
      },
      legend: {
        top: 0,
        data: ["权益", "收益率", "回撤"],
        textStyle: { color: "#64748b" },
      },
      grid: { left: 54, right: 42, top: 46, bottom: 44 },
      xAxis: {
        type: "category",
        data: points.map((item) => item.curve_time),
        axisLabel: {
          color: "#64748b",
          showMaxLabel: true,
          showMinLabel: true,
          formatter: (value: string) => value.slice(5, 16).replace(" ", "\n"),
        },
        axisLine: { lineStyle: { color: "#dbe3ef" } },
        axisTick: { show: false },
      },
      yAxis: [
        {
          type: "value",
          name: "权益",
          nameTextStyle: { color: "#64748b" },
          axisLabel: {
            color: "#64748b",
            formatter: (value: number) => value.toLocaleString(),
          },
          splitLine: { lineStyle: { color: "#eef2f7" } },
        },
        {
          type: "value",
          name: "收益 / 回撤",
          position: "right",
          min: Math.floor(percentMin - percentPadding),
          max: Math.ceil(percentMax + percentPadding),
          nameTextStyle: { color: "#64748b" },
          axisLabel: {
            color: "#64748b",
            formatter: (value: number) => `${value}%`,
          },
          splitLine: { show: false },
        },
      ],
      series: [
        {
          name: "权益",
          type: "line",
          data: equitySeries,
          smooth: true,
          symbol: "none",
          lineStyle: { width: 2 },
          areaStyle: { color: "rgba(29, 78, 216, 0.08)" },
          markPoint: {
            symbolSize: 34,
            label: { color: "#1e293b", formatter: "高点" },
            itemStyle: { color: "#1d4ed8" },
            data: [{ coord: [highestEquityPoint.curve_time, highestEquityPoint.equity] }],
          },
        },
        {
          name: "收益率",
          type: "line",
          yAxisIndex: 1,
          data: returnSeries,
          smooth: true,
          symbol: "none",
          lineStyle: { width: 2 },
          markLine: {
            symbol: "none",
            lineStyle: { color: "rgba(100, 116, 139, 0.5)", type: "dashed" },
            label: { show: false },
            data: [{ yAxis: 0 }],
          },
        },
        {
          name: "回撤",
          type: "line",
          yAxisIndex: 1,
          data: drawdownSeries,
          smooth: true,
          symbol: "none",
          lineStyle: { width: 2 },
          areaStyle: { color: "rgba(194, 65, 58, 0.08)" },
          markPoint: {
            symbolSize: 34,
            label: { color: "#7f1d1d", formatter: "最深" },
            itemStyle: { color: "#c2413a" },
            data: [{ coord: [worstDrawdownPoint.curve_time, -Math.abs(worstDrawdownPoint.drawdown_pct)] }],
          },
        },
      ],
    }),
    [drawdownSeries, equitySeries, highestEquityPoint, percentMax, percentMin, percentPadding, points, returnSeries, worstDrawdownPoint],
  );

  return (
    <div className="chart-frame">
      <ReactECharts style={{ height: "100%", width: "100%" }} option={option} notMerge lazyUpdate />
    </div>
  );
}
