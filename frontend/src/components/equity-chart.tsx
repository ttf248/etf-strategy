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
      tooltip: { trigger: "axis" },
      legend: { data: ["权益", "收益率", "回撤"] },
      grid: { left: 48, right: 32, top: 40, bottom: 48 },
      xAxis: {
        type: "category",
        data: points.map((item) => item.curve_time),
        axisLabel: { showMaxLabel: true, showMinLabel: true },
      },
      yAxis: [
        { type: "value", name: "权益" },
        { type: "value", name: "百分比", position: "right" },
      ],
      series: [
        { name: "权益", type: "line", data: points.map((item) => item.equity), smooth: true, symbol: "none" },
        { name: "收益率", type: "line", yAxisIndex: 1, data: points.map((item) => item.return_pct), smooth: true, symbol: "none" },
        { name: "回撤", type: "line", yAxisIndex: 1, data: points.map((item) => item.drawdown_pct), smooth: true, symbol: "none" },
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
