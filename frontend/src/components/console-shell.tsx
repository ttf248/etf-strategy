"use client";

import {
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

type RouteShellConfig = {
  title: string;
  kicker: string;
  tipTitle: string;
  tipText: string;
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

const routeTitles: Record<string, RouteShellConfig> = {
  "/": {
    title: "新手首页",
    kicker: "开始使用",
    tipTitle: "第一次使用建议按这条路走",
    tipText: "数据准备 -> 创建回测 -> 查看报告。只有页面打不开或任务长期不动时，再去系统状态。",
  },
  "/platform": {
    title: "系统状态",
    kicker: "排障维护",
    tipTitle: "只有排障时才需要来这页",
    tipText: "如果你只是想回测、补数据或看报告，请回到左侧主路径页面，不必长期盯着服务状态。",
  },
  "/market-data": {
    title: "数据准备",
    kicker: "补齐首跑数据",
    tipTitle: "先补首跑需要的数据，不用一开始全量建库",
    tipText: "通常先准备熟悉标的的 1d 或 15m 即可；确认能跑起来后，再决定是否继续补更多周期。",
  },
  "/templates": {
    title: "策略模板",
    kicker: "选择起步模板",
    tipTitle: "模板的作用是帮你少填参数",
    tipText: "优先从推荐模板直接起跑，只有确定方向后，再进入高级编辑微调参数。",
  },
  "/backtests": {
    title: "创建回测",
    kicker: "开始试跑",
    tipTitle: "先跑通一轮，再决定要不要研究高级参数",
    tipText: "不确定时直接使用推荐模板；先拿到第一份报告，再回头比较模板、周期和回撤差异。",
  },
  "/reports": {
    title: "查看报告",
    kicker: "结果复盘",
    tipTitle: "先看结论，再决定重跑还是对比",
    tipText: "读完收益、回撤和曲线后，再去同标的对比区继续比较，不需要回到维护页排查内部状态。",
  },
};

export function ConsoleShell({ children }: ConsoleShellProps) {
  const pathname = usePathname();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const selectedKey = pathname.startsWith("/reports/") ? "/reports" : pathname;
  const current = routeTitles[selectedKey] ?? routeTitles["/"];
  const renderMenu = () => (
    <div className="nav-sections">
      <Typography.Text className="nav-section-title">开始使用</Typography.Text>
      <Menu mode="inline" selectedKeys={[selectedKey]} items={primaryItems} className="platform-nav" onClick={() => setMobileMenuOpen(false)} />
      <Typography.Text className="nav-section-title">排障时再看</Typography.Text>
      <Menu mode="inline" selectedKeys={[selectedKey]} items={supportItems} className="platform-nav" onClick={() => setMobileMenuOpen(false)} />
    </div>
  );

  return (
    <Layout className="platform-shell">
      <Sider width={240} theme="light" className="platform-sider" breakpoint="lg" collapsedWidth="0">
        <div className="platform-side-head">
          <div className="platform-logo">
            <div className="platform-logo-mark">ES</div>
            <div className="platform-logo-text">
              <span className="platform-logo-title">ETF Strategy</span>
              <span className="platform-logo-subtitle">新手回测平台</span>
            </div>
          </div>
          <div className="nav-guide-card">
            <strong>第一次使用建议</strong>
            <p>先准备数据，再提交一轮回测，最后读报告和做对比。</p>
            <div className="nav-guide-steps">
              <Link href="/market-data" onClick={() => setMobileMenuOpen(false)}>1. 数据准备</Link>
              <Link href="/backtests" onClick={() => setMobileMenuOpen(false)}>2. 创建回测</Link>
              <Link href="/reports" onClick={() => setMobileMenuOpen(false)}>3. 查看报告</Link>
            </div>
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
          <div className="platform-header-guide">
            <strong>{current.tipTitle}</strong>
            <span>{current.tipText}</span>
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
