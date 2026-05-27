"use client";

import { Button, Card, Col, Empty, Row, Select, Skeleton, Space, Table, Typography, message } from "antd";
import { useEffect, useState } from "react";
import { apiFetch, type PlatformLogs, type PlatformProcess, type PlatformStatus } from "@/lib/api";
import { MetricCard, PageHeader, StatusTag, ToolbarCount } from "@/components/platform-ui";

const logServiceOptions = [
  { label: "API", value: "api" },
  { label: "Worker", value: "worker" },
  { label: "Scheduler", value: "scheduler" },
];

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

  return (
    <div className="page-stack">
      {contextHolder}
      <PageHeader
        eyebrow="Platform Control"
        title="平台总控"
        description="统一查看 API、前端、Worker、Scheduler、数据库、任务队列、同步调度和最近日志。"
        actions={<Button onClick={() => void refreshPlatform()}>刷新状态</Button>}
      />

      <div className="summary-grid">
        <MetricCard label="API" value={<StatusTag value={status.api.status} />} note={status.api.base_url} />
        <MetricCard label="Frontend" value={<StatusTag value={status.frontend.status} />} note={status.frontend.base_url} />
        <MetricCard label="Database" value={<StatusTag value={status.database.status} />} note={status.database.url} />
        <MetricCard label="任务总数" value={queueTotal} note={`queued ${status.queue.queued ?? 0} / running ${status.queue.running ?? 0}`} />
      </div>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={12}>
          <Card title="服务心跳" size="small" className="section-card">
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

      <Card
        title="本机进程"
        size="small"
        className="section-card"
        extra={<ToolbarCount>进程控制：{status.process_control_enabled ? "已启用" : "默认关闭"}</ToolbarCount>}
      >
        <Table
          rowKey={(row) => `${row.pid}-${row.service_name}`}
          size="small"
          dataSource={processes}
          pagination={{ pageSize: 8, showSizeChanger: false }}
          scroll={{ x: 1100 }}
          columns={[
            { title: "服务", dataIndex: "service_name", width: 120, fixed: "left" },
            { title: "PID", dataIndex: "pid", width: 90 },
            { title: "进程名", dataIndex: "name", width: 120 },
            { title: "启动时间", dataIndex: "created_at", width: 180 },
            { title: "命令行", dataIndex: "command_line", ellipsis: true },
            {
              title: "操作",
              width: 110,
              fixed: "right",
              render: (_, row) => (
                <Button size="small" disabled={!status.process_control_enabled} onClick={() => void restartService(row.service_name)}>
                  重启
                </Button>
              ),
            },
          ]}
        />
      </Card>

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
    </div>
  );
}
