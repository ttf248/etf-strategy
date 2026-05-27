import { Skeleton } from "antd";
import { Suspense } from "react";
import { ReportsView } from "@/components/reports-view";

export default function ReportsPage() {
  return (
    <Suspense fallback={<Skeleton active paragraph={{ rows: 8 }} />}>
      <ReportsView />
    </Suspense>
  );
}
