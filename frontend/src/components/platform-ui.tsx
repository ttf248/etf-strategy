"use client";

import { Card, Space, Tag, Typography } from "antd";
import type { ReactNode } from "react";

type PageHeaderProps = {
  eyebrow: string;
  title: string;
  description?: string;
  actions?: ReactNode;
};

type MetricCardProps = {
  label: string;
  value: ReactNode;
  note?: ReactNode;
};

type DetailItemProps = {
  label: string;
  value: ReactNode;
  tone?: "positive" | "negative";
};

export function PageHeader({ eyebrow, title, description, actions }: PageHeaderProps) {
  return (
    <div className="page-heading">
      <div className="page-heading-main">
        <span className="eyebrow">{eyebrow}</span>
        <Typography.Title level={2} className="page-title">
          {title}
        </Typography.Title>
        {description ? <p className="page-description">{description}</p> : null}
      </div>
      {actions ? <div>{actions}</div> : null}
    </div>
  );
}

export function MetricCard({ label, value, note }: MetricCardProps) {
  return (
    <Card size="small" className="metric-card">
      <div className="metric-kpi">
        <span className="metric-label">{label}</span>
        <strong className="metric-value">{value}</strong>
        {note ? <span className="metric-note">{note}</span> : null}
      </div>
    </Card>
  );
}

export function DetailItem({ label, value, tone }: DetailItemProps) {
  const toneClass = tone === "positive" ? " positive-value" : tone === "negative" ? " negative-value" : "";
  return (
    <div className="detail-item">
      <span className="detail-label">{label}</span>
      <span className={`detail-value${toneClass}`}>{value}</span>
    </div>
  );
}

export function StatusTag({ value, label }: { value: string; label?: ReactNode }) {
  const color =
    value === "succeeded" || value === "ok" || value === "completed"
      ? "green"
      : value === "failed" || value === "down"
        ? "red"
        : value === "running"
          ? "blue"
          : value === "queued" || value === "cancel_requested"
            ? "gold"
            : value === "cancelled"
              ? "default"
              : "default";
  return <Tag color={color}>{label ?? value ?? "-"}</Tag>;
}

export function FormatPercent({ value }: { value: unknown }) {
  const numeric = Number(value ?? 0);
  const toneClass = numeric > 0 ? "positive-value" : numeric < 0 ? "negative-value" : "";
  return <span className={toneClass}>{`${numeric.toFixed(2)}%`}</span>;
}

export function ToolbarCount({ children }: { children: ReactNode }) {
  return <span className="toolbar-count">{children}</span>;
}

export function CompactActions({ children }: { children: ReactNode }) {
  return <Space size={8} wrap>{children}</Space>;
}
