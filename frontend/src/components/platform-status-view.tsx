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

function formatActiveTaskNote(runningJobs: number, queuedJobs: number, cancelRequestedJobs: number) {
  if (runningJobs === 0 && queuedJobs === 0 && cancelRequestedJobs === 0) {
    return "当前没有正在跑或等待处理的任务";
  }
  const parts = [`运行中 ${runningJobs}`, `排队 ${queuedJobs}`];
  if (cancelRequestedJobs > 0) {
    parts.push(`等待取消 ${cancelRequestedJobs}`);
  }
  return parts.join(" / ");
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

  const platformReady = serviceOk(status.api.status) && serviceOk(status.frontend.status) && serviceOk(status.database.status);
  const queuedJobs = Number(status.queue.queued ?? 0);
  const runningJobs = Number(status.queue.running ?? 0);
  const cancelRequestedJobs = Number(status.queue.cancel_requested ?? 0);
  const activeTaskCount = queuedJobs + runningJobs + cancelRequestedJobs;
  const failedJobs = Number(status.queue.failed ?? 0);
  const unhealthyServices = [
    !serviceOk(status.api.status) ? "API" : null,
    !serviceOk(status.frontend.status) ? "前端页面" : null,
    !serviceOk(status.database.status) ? "数据库" : null,
  ].filter(Boolean) as string[];
  const attentionLabel = !platformReady ? "需要排障" : activeTaskCount > 0 ? "暂时观察任务" : "现在不用处理";
  const attentionNote = !platformReady
    ? `优先确认 ${unhealthyServices.join("、")} 是否异常。`
    : activeTaskCount > 0
      ? formatActiveTaskNote(runningJobs, queuedJobs, cancelRequestedJobs)
      : "页面、接口和数据库都正常，可以回到主路径继续使用。";
  const statusBannerTitle = !platformReady
    ? "先确认是不是服务异常，而不是先翻日志"
    : activeTaskCount > 0
      ? "平台本身正常，先看任务是否只是还在处理"
      : "现在不需要继续停留在这里";
  const statusBannerDescription = !platformReady
    ? `当前最值得先看的不是全部日志，而是 ${unhealthyServices.join("、")}。确认哪个环节异常后，再展开下面对应的高级维护信息。`
    : activeTaskCount > 0
      ? `当前 ${formatActiveTaskNote(runningJobs, queuedJobs, cancelRequestedJobs)}。如果只是任务还在跑，先等待或回报告页刷新，不必立即查看进程和日志。`
      : "页面、接口、数据库都正常，当前也没有等待处理的任务。直接回到创建回测、报告或数据准备页即可。";

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
        <MetricCard label="现在需不需要处理" value={attentionLabel} note={attentionNote} />
        <MetricCard label="当前待处理任务" value={activeTaskCount} note={formatActiveTaskNote(runningJobs, queuedJobs, cancelRequestedJobs)} />
        <MetricCard
          label="服务异常数"
          value={unhealthyServices.length}
          note={unhealthyServices.length > 0 ? `重点先看：${unhealthyServices.join("、")}` : "API、前端页面和数据库都正常"}
        />
        <MetricCard
          label="历史失败任务"
          value={failedJobs}
          note={failedJobs > 0 ? "只表示历史上有失败，不代表当前还在卡住" : "当前没有记录到失败任务"}
        />
      </div>

      <Card size="small" className="section-card maintenance-status-card">
        <div className="maintenance-status-main">
          <strong>{statusBannerTitle}</strong>
          <p>{statusBannerDescription}</p>
        </div>
        <div className="maintenance-status-actions">
          <Button type="primary">
            <Link href="/backtests">回到创建回测</Link>
          </Button>
          <Button>
            <Link href="/reports">去看报告列表</Link>
          </Button>
          <Button>
            <Link href="/market-data">去检查数据</Link>
          </Button>
        </div>
      </Card>

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
            label: "如果页面打不开，再看心跳与同步调度",
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
            label: "如果怀疑后台没跑，再看本机进程",
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
            label: "如果需要贴错误信息，再看最近日志",
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
