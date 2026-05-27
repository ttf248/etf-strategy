"use client";

import {
  BarChartOutlined,
  ClockCircleOutlined,
  DatabaseOutlined,
  FileSearchOutlined,
  FundOutlined,
  MenuOutlined,
  MonitorOutlined,
  SettingOutlined,
} from "@ant-design/icons";
import { Button, Drawer, Layout, Menu } from "antd";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";

const { Header, Sider, Content } = Layout;

type ConsoleShellProps = {
  children: ReactNode;
};

const items = [
  { key: "/", icon: <FundOutlined />, label: <Link href="/">平台概览</Link> },
  { key: "/platform", icon: <MonitorOutlined />, label: <Link href="/platform">平台总控</Link> },
  { key: "/market-data", icon: <DatabaseOutlined />, label: <Link href="/market-data">行情数据</Link> },
  { key: "/templates", icon: <SettingOutlined />, label: <Link href="/templates">参数模板</Link> },
  { key: "/backtests", icon: <BarChartOutlined />, label: <Link href="/backtests">回测任务</Link> },
  { key: "/reports", icon: <FileSearchOutlined />, label: <Link href="/reports">历史报告</Link> },
];

const routeTitles: Record<string, { title: string; kicker: string }> = {
  "/": { title: "平台概览", kicker: "Research Console" },
  "/platform": { title: "平台总控", kicker: "Platform Control" },
  "/market-data": { title: "行情数据", kicker: "Market Data" },
  "/templates": { title: "参数模板", kicker: "Strategy Templates" },
  "/backtests": { title: "回测任务", kicker: "Backtest Jobs" },
  "/reports": { title: "历史报告", kicker: "Reports" },
};

export function ConsoleShell({ children }: ConsoleShellProps) {
  const pathname = usePathname();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const selectedKey = pathname.startsWith("/reports/") ? "/reports" : pathname;
  const current = routeTitles[selectedKey] ?? routeTitles["/"];
  const renderMenu = () => (
    <Menu mode="inline" selectedKeys={[selectedKey]} items={items} className="platform-nav" onClick={() => setMobileMenuOpen(false)} />
  );

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
        {renderMenu()}
      </Sider>
      <Layout className="platform-main">
        <Header className="platform-header">
          <Button className="mobile-menu-trigger" icon={<MenuOutlined />} onClick={() => setMobileMenuOpen(true)} />
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
            <span className="platform-pill compact">API 127.0.0.1:8000</span>
          </div>
        </Header>
        <Content className="platform-content">
          <div className="content-frame">{children}</div>
        </Content>
      </Layout>
      <Drawer
        title="ETF Strategy"
        placement="left"
        width={280}
        open={mobileMenuOpen}
        onClose={() => setMobileMenuOpen(false)}
        className="mobile-nav-drawer"
      >
        {renderMenu()}
      </Drawer>
    </Layout>
  );
}
