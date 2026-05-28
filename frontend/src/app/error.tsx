"use client";

import { useEffect } from "react";
import { PageErrorState } from "@/components/platform-ui";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="page-stack">
      <PageErrorState
        title="页面加载失败"
        description={error.message || "页面在渲染过程中发生异常，请重新加载。"}
        actionLabel="重新加载当前页面"
        onRetry={reset}
      />
    </div>
  );
}
