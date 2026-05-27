"use client";

import {
  BarChartOutlined,
  ClockCircleOutlined,
  DatabaseOutlined,
  FileSearchOutlined,
  FundOutlined,
  SettingOutlined,
} from "@ant-design/icons";
import { Layout, Menu } from "antd";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

const { Header, Sider, Content } = Layout;

type ConsoleShellProps = {
  children: ReactNode;
};

const items = [
  { key: "/", icon: <FundOutlined />, label: <Link href="/">平台概览</Link> },
  { key: "/market-data", icon: <DatabaseOutlined />, label: <Link href="/market-data">行情数据</Link> },
  { key: "/templates", icon: <SettingOutlined />, label: <Link href="/templates">参数模板</Link> },
  { key: "/backtests", icon: <BarChartOutlined />, label: <Link href="/backtests">回测任务</Link> },
  { key: "/reports", icon: <FileSearchOutlined />, label: <Link href="/reports">历史报告</Link> },
];

const routeTitles: Record<string, { title: string; kicker: string }> = {
  "/": { title: "平台概览", kicker: "Research Console" },
  "/market-data": { title: "行情数据", kicker: "Market Data" },
  "/templates": { title: "参数模板", kicker: "Strategy Templates" },
  "/backtests": { title: "回测任务", kicker: "Backtest Jobs" },
  "/reports": { title: "历史报告", kicker: "Reports" },
};

export function ConsoleShell({ children }: ConsoleShellProps) {
  const pathname = usePathname();
  const selectedKey = pathname.startsWith("/reports/") ? "/reports" : pathname;
  const current = routeTitles[selectedKey] ?? routeTitles["/"];

  return (
    <Layout className="platform-shell">
      <Sider width={240} theme="light" className="platform-sider" breakpoint="lg" collapsedWidth="0">
        <div className="platform-logo">
          <div className="platform-logo-mark">ES</div>
          <div className="platform-logo-text">
            <span className="platform-logo-title">ETF Strategy</span>
            <span className="platform-logo-subtitle">Quant Research Platform</span>
          </div>
        </div>
        <Menu mode="inline" selectedKeys={[selectedKey]} items={items} className="platform-nav" />
      </Sider>
      <Layout className="platform-main">
        <Header className="platform-header">
          <div className="platform-header-title">
            <span className="platform-header-kicker">{current.kicker}</span>
            <span className="platform-header-name">{current.title}</span>
          </div>
          <div className="platform-header-meta">
            <span className="platform-pill">
              <DatabaseOutlined />
              PostgreSQL
            </span>
            <span className="platform-pill">
              <ClockCircleOutlined />
              Asia/Shanghai
            </span>
            <span className="platform-pill">API 127.0.0.1:8000</span>
          </div>
        </Header>
        <Content className="platform-content">
          <div className="content-frame">{children}</div>
        </Content>
      </Layout>
    </Layout>
  );
}
