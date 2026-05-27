"use client";

import Link from "next/link";
import { Button, Card, Col, Collapse, Empty, Row, Select, Skeleton, Space, Table, Typography, message } from "antd";
import { useEffect, useState } from "react";
import { apiFetch, type PlatformLogs, type PlatformProcess, type PlatformStatus } from "@/lib/api";
import { MetricCard, PageHeader, StatusTag, ToolbarCount } from "@/components/platform-ui";

const logServiceOptions = [
  { label: "API", value: "api" },
  { label: "Worker", value: "worker" },
  { label: "Scheduler", value: "scheduler" },
];

function serviceOk(status: string): boolean {
  return status === "ok" || status === "completed" || status === "succeeded";
}

export function PlatformStatusView() {
  const [status, setStatus] = useState<PlatformStatus | null>(null);
  const [processes, setProcesses] = useState<PlatformProcess[]>([]);
  const [logs, setLogs] = useState<PlatformLogs | null>(null);
  const [logService, setLogService] = useState("api");
  const [loading, setLoading] = useState(true);
  const [messageApi, contextHolder] = message.useMessage();

  async function fetchPlatformPayload(service: string) {
    const [statusPayload, processesPayload, logsPayload] = await Promise.all([
      apiFetch<PlatformStatus>("/api/platform/status"),
      apiFetch<PlatformProcess[]>("/api/platform/processes"),
      apiFetch<PlatformLogs>(`/api/platform/logs?service=${service}&limit=120`),
    ]);
    return { statusPayload, processesPayload, logsPayload };
  }

  async function refreshPlatform() {
    setLoading(true);
    try {
      const payload = await fetchPlatformPayload(logService);
      setStatus(payload.statusPayload);
      setProcesses(payload.processesPayload);
      setLogs(payload.logsPayload);
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "读取平台状态失败");
    } finally {
      setLoading(false);
    }
  }

  async function restartService(serviceName: string) {
    try {
      await apiFetch(`/api/platform/processes/${serviceName}/restart`, { method: "POST" });
      messageApi.success("已提交重启请求");
      await refreshPlatform();
    } catch (error) {
      messageApi.warning(error instanceof Error ? error.message : "当前环境不允许进程控制");
    }
  }

  useEffect(() => {
    let cancelled = false;
    void fetchPlatformPayload(logService)
      .then((payload) => {
        if (cancelled) {
          return;
        }
        setStatus(payload.statusPayload);
        setProcesses(payload.processesPayload);
        setLogs(payload.logsPayload);
      })
      .catch((error) => {
        if (!cancelled) {
          messageApi.error(error instanceof Error ? error.message : "读取平台状态失败");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
    // 仅在日志服务切换时重新加载；手动刷新由按钮触发。
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [logService]);

  if (loading && !status) {
    return <Skeleton active paragraph={{ rows: 10 }} />;
  }

  if (!status) {
    return <Empty description="暂时无法读取平台状态" />;
  }

  const queueTotal = Object.values(status.queue).reduce((sum, value) => sum + Number(value || 0), 0);
  const platformReady = serviceOk(status.api.status) && serviceOk(status.frontend.status) && serviceOk(status.database.status);
  const queuedJobs = Number(status.queue.queued ?? 0);
  const runningJobs = Number(status.queue.running ?? 0);

  return (
    <div className="page-stack">
      {contextHolder}
      <PageHeader
        eyebrow="Maintenance"
        title="系统状态"
        description="这里只在平台出问题时才需要查看。正常创建回测、查看报告时，不需要理解进程、日志或数据库。"
        actions={<Button onClick={() => void refreshPlatform()}>刷新状态</Button>}
      />

      <div className="summary-grid">
        <MetricCard label="平台可用性" value={platformReady ? "可以继续使用" : "需要排查"} note="API、前端、数据库都正常时即可继续回测" />
        <MetricCard label="API 服务" value={<StatusTag value={status.api.status} />} note={serviceOk(status.api.status) ? "接口正常响应" : "先刷新或查看下方日志"} />
        <MetricCard label="页面访问" value={<StatusTag value={status.frontend.status} />} note={serviceOk(status.frontend.status) ? "前端可访问" : "页面可能无法正常打开"} />
        <MetricCard
          label="后台任务"
          value={queueTotal}
          note={runningJobs > 0 || queuedJobs > 0 ? `排队 ${queuedJobs} / 运行中 ${runningJobs}` : "当前没有排队任务"}
        />
      </div>

      <Card size="small" className="section-card maintenance-guide-card">
        <Typography.Title level={4}>先判断你是不是需要看这页</Typography.Title>
        <Typography.Paragraph>
          如果你只是想创建回测、看报告或补数据，优先回主路径页面操作。只有当页面打不开、任务长期不动或同步一直失败时，再展开下面的维护信息。
        </Typography.Paragraph>
      </Card>

      <div className="maintenance-path-grid">
        <Card size="small" className="maintenance-path-card">
          <strong>正常使用时</strong>
          <span>平台可用性显示“可以继续使用”时，直接回到主路径，不需要再看日志或进程。</span>
          <Button type="link">
            <Link href="/backtests">回到创建回测</Link>
          </Button>
        </Card>
        <Card size="small" className="maintenance-path-card">
          <strong>数据有问题时</strong>
          <span>如果回测报数据不足，先去数据准备页检查标的和周期，不必先看系统日志。</span>
          <Button type="link">
            <Link href="/market-data">去检查数据</Link>
          </Button>
        </Card>
        <Card size="small" className="maintenance-path-card">
          <strong>任务没结果时</strong>
          <span>如果任务一直排队或报告没生成，再回来展开心跳、队列和日志，确认后台进程是否正常。</span>
          <Button type="link">
            <Link href="/reports">先看报告列表</Link>
          </Button>
        </Card>
      </div>

      <Collapse
        className="maintenance-collapse"
        items={[
          {
            key: "runtime",
            label: "高级维护信息：心跳与同步调度",
            children: (
              <Row gutter={[16, 16]}>
                <Col xs={24} xl={12}>
                  <Card title="服务心跳" size="small" className="section-card">
                    {status.heartbeats.length === 0 ? (
                      <Empty
                        description={
                          <span>
                            暂无 Worker/Scheduler 心跳。若日志提示心跳表不存在，请先执行 <code>py -3.13 main.py init-db</code>。
                          </span>
                        }
                      />
                    ) : (
                      <Table
                        rowKey="service_name"
                        size="small"
                        pagination={false}
                        dataSource={status.heartbeats}
                        columns={[
                          { title: "服务", dataIndex: "service_name", width: 120 },
                          { title: "状态", dataIndex: "status", width: 100, render: (value: string) => <StatusTag value={value} /> },
                          { title: "PID", dataIndex: "pid", width: 90 },
                          { title: "心跳延迟", dataIndex: "age_seconds", width: 110, render: (value: number) => `${value}s` },
                          { title: "最近心跳", dataIndex: "last_seen_at", ellipsis: true },
                        ]}
                      />
                    )}
                  </Card>
                </Col>
                <Col xs={24} xl={12}>
                  <Card title="同步调度" size="small" className="section-card">
                    <Table
                      rowKey="id"
                      size="small"
                      pagination={false}
                      dataSource={status.sync_schedule}
                      columns={[
                        { title: "任务", dataIndex: "id", ellipsis: true },
                        { title: "周期", dataIndex: "interval", width: 90 },
                        { title: "时间", dataIndex: "cron", width: 190 },
                        { title: "窗口", dataIndex: "period", width: 90, render: (value: string) => value || "-" },
                      ]}
                    />
                  </Card>
                </Col>
              </Row>
            ),
          },
          {
            key: "processes",
            label: "高级维护信息：本机进程",
            children: (
              <Card
                title="本机进程"
                size="small"
                className="section-card"
                extra={<ToolbarCount>进程控制仅供维护使用：{status.process_control_enabled ? "已启用" : "默认关闭"}</ToolbarCount>}
              >
              <Table
                rowKey={(row) => `${row.pid}-${row.service_name}`}
                size="small"
                dataSource={processes}
                pagination={{ pageSize: 8, showSizeChanger: false }}
                scroll={{ x: 1100 }}
                columns={[
                  { title: "服务", dataIndex: "service_name", width: 120 },
                  { title: "PID", dataIndex: "pid", width: 90 },
                  { title: "进程名", dataIndex: "name", width: 120 },
                  { title: "启动时间", dataIndex: "created_at", width: 180 },
                  { title: "命令行", dataIndex: "command_line", ellipsis: true },
                  {
                    title: "操作",
                    width: 110,
                    render: (_, row) => (
                      <Button size="small" disabled={!status.process_control_enabled} onClick={() => void restartService(row.service_name)}>
                        重启
                      </Button>
                    ),
                  },
                ]}
              />
              </Card>
            ),
          },
          {
            key: "logs",
            label: "高级维护信息：最近日志",
            children: (
              <Card
                title="最近日志"
                size="small"
                className="section-card"
                extra={
                  <Space>
                    <Select value={logService} onChange={setLogService} options={logServiceOptions} style={{ width: 130 }} />
                    <Button onClick={() => void refreshPlatform()}>刷新日志</Button>
                  </Space>
                }
              >
                {logs?.lines.length ? (
                  <pre className="log-viewer">{logs.lines.join("\n")}</pre>
                ) : (
                  <Typography.Text type="secondary">暂无匹配日志。</Typography.Text>
                )}
              </Card>
            ),
          },
        ]}
      />
    </div>
  );
}
