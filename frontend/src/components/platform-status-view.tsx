"use client";

import Link from "next/link";
import { Button, Card, Col, Collapse, Empty, Row, Select, Skeleton, Space, Table, Typography, message } from "antd";
import { useEffect, useState } from "react";
import { apiFetch, type PlatformLogs, type PlatformProcess, type PlatformStatus } from "@/lib/api";
import { MetricCard, PageHeader, StatusTag, ToolbarCount } from "@/components/platform-ui";

const serviceLabelMap: Record<string, string> = {
  api: "接口服务",
  worker: "回测执行服务",
  scheduler: "定时同步服务",
  frontend: "前端页面",
  database: "数据存储",
};

const logServiceOptions = [
  { label: serviceLabelMap.api, value: "api" },
  { label: serviceLabelMap.worker, value: "worker" },
  { label: serviceLabelMap.scheduler, value: "scheduler" },
];

function serviceOk(status: string): boolean {
  return status === "ok" || status === "completed" || status === "succeeded";
}

function formatServiceLabel(value: string): string {
  return serviceLabelMap[value] ?? value;
}

function formatActiveTaskNote(runningJobs: number, queuedJobs: number, cancelRequestedJobs: number) {
  if (runningJobs === 0 && queuedJobs === 0 && cancelRequestedJobs === 0) {
    return "当前没有正在跑或等待处理的任务";
  }
  const parts = [`运行中 ${runningJobs}`, `等待开始 ${queuedJobs}`];
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
      messageApi.success("已提交服务重启请求");
      await refreshPlatform();
    } catch (error) {
      messageApi.warning(error instanceof Error ? error.message : "当前环境不允许重启本机服务");
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
    !serviceOk(status.api.status) ? serviceLabelMap.api : null,
    !serviceOk(status.frontend.status) ? serviceLabelMap.frontend : null,
    !serviceOk(status.database.status) ? serviceLabelMap.database : null,
  ].filter(Boolean) as string[];
  const attentionLabel = !platformReady ? "需要排障" : activeTaskCount > 0 ? "关注任务进展" : "当前无需处理";
  const attentionNote = !platformReady
    ? `优先确认 ${unhealthyServices.join("、")} 是否异常。`
    : activeTaskCount > 0
      ? formatActiveTaskNote(runningJobs, queuedJobs, cancelRequestedJobs)
      : "前端页面、接口服务和数据存储都正常，可以回到主路径继续使用。";
  const statusBannerTitle = !platformReady
    ? "优先确认是否存在服务异常，而不是直接翻日志"
    : activeTaskCount > 0
      ? "平台本身正常，先确认任务是否仍在处理中"
      : "当前无需继续停留在此页面";
  const statusBannerDescription = !platformReady
    ? `当前更应优先检查 ${unhealthyServices.join("、")}，而不是直接查看全部日志。确认异常环节后，再展开对应的高级维护信息。`
    : activeTaskCount > 0
      ? `当前 ${formatActiveTaskNote(runningJobs, queuedJobs, cancelRequestedJobs)}。若只是任务仍在执行，可先等待或回结果库刷新，无需立即查看本机服务和日志。`
      : "前端页面、接口服务与数据存储均正常，当前也没有等待处理的任务。可直接回到创建回测、结果库或数据覆盖页继续研究。";

  return (
    <div className="page-stack">
      {contextHolder}
      <PageHeader
        eyebrow="运行状态"
        title="系统状态"
        description="该页面用于平台运行检查与排障。日常创建回测、查看结果或补数时，通常无需停留在这里。"
        actions={<Button onClick={() => void refreshPlatform()}>刷新状态</Button>}
      />

      <div className="summary-grid">
        <MetricCard label="现在需不需要处理" value={attentionLabel} note={attentionNote} />
        <MetricCard label="当前待处理任务" value={activeTaskCount} note={formatActiveTaskNote(runningJobs, queuedJobs, cancelRequestedJobs)} />
        <MetricCard
          label="服务异常数"
          value={unhealthyServices.length}
          note={unhealthyServices.length > 0 ? `优先检查：${unhealthyServices.join("、")}` : "接口服务、前端页面和数据存储都正常"}
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
            <Link href="/reports">回到结果库</Link>
          </Button>
          <Button>
            <Link href="/market-data">检查数据覆盖</Link>
          </Button>
        </div>
      </Card>

      <Card size="small" className="section-card maintenance-guide-card">
        <Typography.Title level={4}>先确认当前是否需要进入该页</Typography.Title>
        <Typography.Paragraph>
          如果当前只是创建回测、查看结果或补数，建议优先回主路径页面操作。只有页面不可用、任务长期停滞或同步持续失败时，再查看下方维护信息。
        </Typography.Paragraph>
      </Card>

      <div className="maintenance-path-grid">
        <Card size="small" className="maintenance-path-card">
          <strong>正常使用时</strong>
          <span>当平台可用性显示正常时，直接回到主路径即可，无需继续查看维护日志或本机服务列表。</span>
          <Button type="link">
            <Link href="/backtests">回到创建回测</Link>
          </Button>
        </Card>
        <Card size="small" className="maintenance-path-card">
          <strong>数据异常时</strong>
          <span>如果回测提示数据不足，建议先到数据覆盖页检查标的与周期，无需先查看维护日志。</span>
          <Button type="link">
            <Link href="/market-data">检查数据覆盖</Link>
          </Button>
        </Card>
        <Card size="small" className="maintenance-path-card">
          <strong>任务无结果时</strong>
          <span>如果任务持续排队或报告未生成，再返回此页查看执行状态、等待队列和日志，确认回测执行服务是否正常。</span>
          <Button type="link">
            <Link href="/reports">回到结果库</Link>
          </Button>
        </Card>
      </div>

      <Collapse
        className="maintenance-collapse"
        items={[
          {
            key: "runtime",
            label: "服务不可用时，再看服务心跳与定时同步",
            children: (
              <Row gutter={[16, 16]}>
                <Col xs={24} xl={12}>
                  <Card title="服务心跳" size="small" className="section-card">
                    {status.heartbeats.length === 0 ? (
                      <Empty
                        description={
                          <span>
                            暂无回测执行服务或定时同步服务的心跳。若日志提示心跳表不存在，请先执行 <code>py -3.13 main.py init-db</code>。
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
                          { title: "服务", dataIndex: "service_name", width: 140, render: (value: string) => formatServiceLabel(value) },
                          { title: "状态", dataIndex: "status", width: 100, render: (value: string) => <StatusTag value={value} /> },
                          { title: "进程编号", dataIndex: "pid", width: 100 },
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
            label: "怀疑执行服务未运行时，再看本机服务",
            children: (
              <Card
                title="本机服务"
                size="small"
                className="section-card"
                extra={<ToolbarCount>服务重启仅供维护使用：{status.process_control_enabled ? "已启用" : "默认关闭"}</ToolbarCount>}
              >
              <Table
                rowKey={(row) => `${row.pid}-${row.service_name}`}
                size="small"
                dataSource={processes}
                pagination={{ pageSize: 8, showSizeChanger: false }}
                scroll={{ x: 1100 }}
                columns={[
                  { title: "服务", dataIndex: "service_name", width: 140, render: (value: string) => formatServiceLabel(value) },
                  { title: "进程编号", dataIndex: "pid", width: 100 },
                  { title: "程序名", dataIndex: "name", width: 120 },
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
            label: "需要核对错误提示时，再看最近日志",
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
