"use client";

import { BarChartOutlined, DatabaseOutlined, FileSearchOutlined, FundOutlined } from "@ant-design/icons";
import { Layout, Menu, Typography } from "antd";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

const { Header, Sider, Content } = Layout;

type ConsoleShellProps = {
  children: ReactNode;
};

const items = [
  { key: "/", icon: <FundOutlined />, label: <Link href="/">概览</Link> },
  { key: "/market-data", icon: <DatabaseOutlined />, label: <Link href="/market-data">行情数据</Link> },
  { key: "/backtests", icon: <BarChartOutlined />, label: <Link href="/backtests">回测任务</Link> },
  { key: "/reports", icon: <FileSearchOutlined />, label: <Link href="/reports">历史报告</Link> },
];

export function ConsoleShell({ children }: ConsoleShellProps) {
  const pathname = usePathname();
  const selectedKey = pathname.startsWith("/reports/") ? "/reports" : pathname;

  return (
    <Layout className="platform-shell">
      <Sider width={220} theme="light" className="platform-sider" breakpoint="lg" collapsedWidth="0">
        <div className="platform-logo">ETF Strategy</div>
        <Menu mode="inline" selectedKeys={[selectedKey]} items={items} />
      </Sider>
      <Layout>
        <Header
          style={{
            background: "#ffffff",
            borderBottom: "1px solid var(--panel-border)",
            padding: "0 24px",
            display: "flex",
            alignItems: "center",
          }}
        >
          <Typography.Title level={5} style={{ margin: 0 }}>
            内网回测控制台
          </Typography.Title>
        </Header>
        <Content className="platform-content">{children}</Content>
      </Layout>
    </Layout>
  );
}
