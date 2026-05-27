import { Suspense } from "react";
import { Skeleton } from "antd";
import { BacktestsView } from "@/components/backtests-view";

export default function BacktestsPage() {
  return (
    <Suspense fallback={<Skeleton active paragraph={{ rows: 8 }} />}>
      <BacktestsView />
    </Suspense>
  );
}
