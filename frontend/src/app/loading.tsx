import { Card, Skeleton } from "antd";

export default function Loading() {
  return (
    <div className="page-stack">
      <Card size="small" className="section-card">
        <Skeleton active paragraph={{ rows: 4 }} />
      </Card>
      <Card size="small" className="section-card">
        <Skeleton active paragraph={{ rows: 8 }} />
      </Card>
    </div>
  );
}
