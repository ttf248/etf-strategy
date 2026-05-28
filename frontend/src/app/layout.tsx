import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { AntdRegistry } from "@ant-design/nextjs-registry";
import { ConfigProvider } from "antd";
import "./globals.css";
import { ConsoleShell } from "@/components/console-shell";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "ETF Strategy Backtest Lab",
  description: "面向策略研究与回测复盘的 ETF 平台",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN" className={`${geistSans.variable} ${geistMono.variable}`}>
      <body>
        <AntdRegistry>
          <ConfigProvider
            theme={{
              token: {
                colorPrimary: "#1d4ed8",
                colorInfo: "#1d4ed8",
                colorSuccess: "#138a50",
                colorWarning: "#b7791f",
                colorError: "#c2413a",
                colorText: "#172033",
                colorTextSecondary: "#64748b",
                colorBorder: "#dbe3ef",
                colorBgLayout: "#f5f7fb",
                colorBgContainer: "#ffffff",
                borderRadius: 8,
                fontFamily: "var(--font-geist-sans), Arial, Helvetica, sans-serif",
                boxShadowSecondary: "0 10px 28px rgba(15, 23, 42, 0.08)",
              },
              components: {
                Button: {
                  controlHeight: 34,
                  borderRadius: 8,
                },
                Card: {
                  borderRadiusLG: 8,
                  headerFontSize: 15,
                },
                Form: {
                  itemMarginBottom: 12,
                },
                Input: {
                  borderRadius: 8,
                  controlHeight: 34,
                },
                InputNumber: {
                  borderRadius: 8,
                  controlHeight: 34,
                },
                Select: {
                  borderRadius: 8,
                  controlHeight: 34,
                },
                Table: {
                  cellPaddingBlockSM: 8,
                  cellPaddingInlineSM: 10,
                  headerBg: "#f8fafc",
                },
              },
            }}
          >
            <ConsoleShell>{children}</ConsoleShell>
          </ConfigProvider>
        </AntdRegistry>
      </body>
    </html>
  );
}
