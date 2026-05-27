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
  const option = useMemo(
    () => ({
      color: ["#1d4ed8", "#0f766e", "#c2413a"],
      tooltip: {
        trigger: "axis",
        backgroundColor: "rgba(15, 23, 42, 0.92)",
        borderWidth: 0,
        textStyle: { color: "#ffffff" },
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
        axisLabel: { color: "#64748b", showMaxLabel: true, showMinLabel: true },
        axisLine: { lineStyle: { color: "#dbe3ef" } },
        axisTick: { show: false },
      },
      yAxis: [
        {
          type: "value",
          name: "权益",
          nameTextStyle: { color: "#64748b" },
          axisLabel: { color: "#64748b" },
          splitLine: { lineStyle: { color: "#eef2f7" } },
        },
        {
          type: "value",
          name: "百分比",
          position: "right",
          nameTextStyle: { color: "#64748b" },
          axisLabel: { color: "#64748b" },
          splitLine: { show: false },
        },
      ],
      series: [
        { name: "权益", type: "line", data: points.map((item) => item.equity), smooth: true, symbol: "none", lineStyle: { width: 2 } },
        { name: "收益率", type: "line", yAxisIndex: 1, data: points.map((item) => item.return_pct), smooth: true, symbol: "none", lineStyle: { width: 2 } },
        { name: "回撤", type: "line", yAxisIndex: 1, data: points.map((item) => item.drawdown_pct), smooth: true, symbol: "none", lineStyle: { width: 2 } },
      ],
    }),
    [points],
  );

  return (
    <div className="chart-frame">
      <ReactECharts style={{ height: "100%", width: "100%" }} option={option} notMerge lazyUpdate />
    </div>
  );
}
