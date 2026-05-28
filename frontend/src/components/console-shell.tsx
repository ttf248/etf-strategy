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
  { key: "/", icon: <FundOutlined />, label: <Link href="/">研究总览</Link> },
  { key: "/backtests", icon: <FormOutlined />, label: <Link href="/backtests">创建回测</Link> },
  { key: "/reports", icon: <FileSearchOutlined />, label: <Link href="/reports">结果库</Link> },
  { key: "/market-data", icon: <DatabaseOutlined />, label: <Link href="/market-data">数据覆盖</Link> },
  { key: "/templates", icon: <SettingOutlined />, label: <Link href="/templates">策略模板</Link> },
];

const supportItems = [
  { key: "/platform", icon: <MonitorOutlined />, label: <Link href="/platform">系统状态</Link> },
];

const routeTitles: Record<string, RouteShellConfig> = {
  "/": {
    title: "研究总览",
    kicker: "研究工作台",
    tipTitle: "默认研究路径",
    tipText: "数据覆盖 -> 创建回测 -> 结果复盘。只有服务异常、任务停滞或同步失败时，再进入系统状态。",
  },
  "/platform": {
    title: "系统状态",
    kicker: "运行状态",
    tipTitle: "用于排障与运行检查",
    tipText: "日常研究优先停留在主路径页面；只有需要确认服务、队列或日志状态时，再查看这里。",
  },
  "/market-data": {
    title: "数据覆盖",
    kicker: "行情覆盖",
    tipTitle: "先确认研究所需周期是否齐备",
    tipText: "通常先补齐目标标的的 1d 或 15m；只有准备扩大标的池时，才需要全量同步。",
  },
  "/templates": {
    title: "策略模板",
    kicker: "配置模板",
    tipTitle: "模板用于固化研究配置",
    tipText: "优先从推荐模板选择基线配置；只有默认口径不匹配时，再进入高级编辑调整参数。",
  },
  "/backtests": {
    title: "创建回测",
    kicker: "任务配置",
    tipTitle: "先定义基线配置，再扩展参数研究",
    tipText: "不确定时直接使用推荐模板；先得到一份可复盘结果，再比较策略、周期和风险收益差异。",
  },
  "/reports": {
    title: "结果库",
    kicker: "结果复盘",
    tipTitle: "先判断结论，再决定对比或重跑",
    tipText: "完成收益、回撤和净值曲线复盘后，再进入同标的对比；无需回到维护页查看内部状态。",
  },
};

export function ConsoleShell({ children }: ConsoleShellProps) {
  const pathname = usePathname();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const selectedKey = pathname.startsWith("/reports/") ? "/reports" : pathname;
  const current = routeTitles[selectedKey] ?? routeTitles["/"];
  const renderMenu = () => (
    <div className="nav-sections">
      <Typography.Text className="nav-section-title">研究主路径</Typography.Text>
      <Menu mode="inline" selectedKeys={[selectedKey]} items={primaryItems} className="platform-nav" onClick={() => setMobileMenuOpen(false)} />
      <Typography.Text className="nav-section-title">运行检查</Typography.Text>
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
              <span className="platform-logo-subtitle">策略研究平台</span>
            </div>
          </div>
          <div className="nav-guide-card">
            <strong>标准研究流程</strong>
            <p>先确认数据覆盖，再提交回测任务，最后复盘结果并做横向对比。</p>
            <div className="nav-guide-steps">
              <Link href="/market-data" onClick={() => setMobileMenuOpen(false)}>1. 数据覆盖</Link>
              <Link href="/backtests" onClick={() => setMobileMenuOpen(false)}>2. 创建回测</Link>
              <Link href="/reports" onClick={() => setMobileMenuOpen(false)}>3. 结果复盘</Link>
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
