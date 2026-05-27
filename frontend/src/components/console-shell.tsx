"use client";

import {
  ClockCircleOutlined,
  DatabaseOutlined,
  FileSearchOutlined,
  FundOutlined,
  FormOutlined,
  MenuOutlined,
  MonitorOutlined,
  SettingOutlined,
} from "@ant-design/icons";
import { Button, Drawer, Layout, Menu, Typography } from "antd";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";

const { Header, Sider, Content } = Layout;

type ConsoleShellProps = {
  children: ReactNode;
};

const primaryItems = [
  { key: "/", icon: <FundOutlined />, label: <Link href="/">新手首页</Link> },
  { key: "/backtests", icon: <FormOutlined />, label: <Link href="/backtests">创建回测</Link> },
  { key: "/reports", icon: <FileSearchOutlined />, label: <Link href="/reports">查看报告</Link> },
  { key: "/market-data", icon: <DatabaseOutlined />, label: <Link href="/market-data">数据准备</Link> },
  { key: "/templates", icon: <SettingOutlined />, label: <Link href="/templates">策略模板</Link> },
];

const supportItems = [
  { key: "/platform", icon: <MonitorOutlined />, label: <Link href="/platform">系统状态</Link> },
];

const routeTitles: Record<string, { title: string; kicker: string }> = {
  "/": { title: "新手首页", kicker: "Start Here" },
  "/platform": { title: "系统状态", kicker: "System Status" },
  "/market-data": { title: "数据准备", kicker: "Data Setup" },
  "/templates": { title: "策略模板", kicker: "Strategy Presets" },
  "/backtests": { title: "创建回测", kicker: "Run Backtest" },
  "/reports": { title: "查看报告", kicker: "Results" },
};

export function ConsoleShell({ children }: ConsoleShellProps) {
  const pathname = usePathname();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const selectedKey = pathname.startsWith("/reports/") ? "/reports" : pathname;
  const current = routeTitles[selectedKey] ?? routeTitles["/"];
  const renderMenu = () => (
    <div className="nav-sections">
      <Typography.Text className="nav-section-title">常用流程</Typography.Text>
      <Menu mode="inline" selectedKeys={[selectedKey]} items={primaryItems} className="platform-nav" onClick={() => setMobileMenuOpen(false)} />
      <Typography.Text className="nav-section-title">维护</Typography.Text>
      <Menu mode="inline" selectedKeys={[selectedKey]} items={supportItems} className="platform-nav" onClick={() => setMobileMenuOpen(false)} />
    </div>
  );

  return (
    <Layout className="platform-shell">
      <Sider width={240} theme="light" className="platform-sider" breakpoint="lg" collapsedWidth="0">
        <div className="platform-logo">
          <div className="platform-logo-mark">ES</div>
          <div className="platform-logo-text">
            <span className="platform-logo-title">ETF Strategy</span>
            <span className="platform-logo-subtitle">Backtest Lab</span>
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
            <span className="platform-pill compact">本地运行</span>
          </div>
        </Header>
        <Content className="platform-content">
          <div className="content-frame">{children}</div>
        </Content>
      </Layout>
      <Drawer
        title="ETF Strategy"
        placement="left"
        size="default"
        open={mobileMenuOpen}
        onClose={() => setMobileMenuOpen(false)}
        className="mobile-nav-drawer"
      >
        {renderMenu()}
      </Drawer>
    </Layout>
  );
}
