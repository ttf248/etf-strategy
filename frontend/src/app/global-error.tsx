"use client";

import { useEffect } from "react";
import { Button, Result } from "antd";

export default function GlobalError({
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
    <html lang="zh-CN">
      <body>
        <div className="page-stack" style={{ minHeight: "100vh", padding: "32px" }}>
          <div className="section-card state-card">
            <Result
              status="error"
              title="应用暂时不可用"
              subTitle={error.message || "全局渲染过程发生异常，请重新加载。"}
              extra={
                <Button type="primary" onClick={reset}>
                  重新加载应用
                </Button>
              }
            />
          </div>
        </div>
      </body>
    </html>
  );
}
