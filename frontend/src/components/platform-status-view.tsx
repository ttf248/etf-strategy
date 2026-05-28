"use client";

import Link from "next/link";
import { Button, Card, Col, Collapse, Empty, Row, Select, Skeleton, Space, Table, Typography, message } from "antd";
import { useCallback, useEffect, useState } from "react";
import { apiFetch, apiFetchSafe, type PlatformLogs, type PlatformProcess, type PlatformStatus } from "@/lib/api";
import { InlineErrorBanner, MetricCard, PageErrorState, PageHeader, StatusTag, ToolbarCount } from "@/components/platform-ui";

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

type CapacityGuide = {
  title: string;
  value: string;
  description: string;
};

function readHeartbeatNumber(
  heartbeat: PlatformStatus["heartbeats"][number] | undefined,
  key: string,
): number | null {
  const value = heartbeat?.details?.[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function buildQueuePressureGuide(params: {
  runningJobs: number;
  queuedJobs: number;
  cancelRequestedJobs: number;
}): CapacityGuide {
  const { runningJobs, queuedJobs, cancelRequestedJobs } = params;
  if (runningJobs === 0 && queuedJobs === 0 && cancelRequestedJobs === 0) {
    return {
      title: "任务压力",
      value: "当前无积压",
      description: "当前没有运行中或排队中的回测任务，平台容量没有被占用。",
    };
  }
  if (queuedJobs > runningJobs && queuedJobs > 0) {
    return {
      title: "任务压力",
      value: `排队 ${queuedJobs} / 执行中 ${runningJobs}`,
      description: "排队任务多于运行中任务，说明当前更需要判断容量是否已经吃满，而不是重复提交新任务。",
    };
  }
  return {
    title: "任务压力",
    value: `执行中 ${runningJobs} / 排队 ${queuedJobs}`,
    description:
      cancelRequestedJobs > 0
        ? `当前还有 ${cancelRequestedJobs} 个任务等待取消落地，应先等待 worker 安全释放槽位。`
        : "当前任务主要处于执行阶段，优先确认 ETA 是否持续推进即可。",
  };
}

function buildWorkerCapacityGuide(
  workerHeartbeat: PlatformStatus["heartbeats"][number] | undefined,
  runningJobs: number,
  queuedJobs: number,
): CapacityGuide {
  const maxConcurrentJobs = readHeartbeatNumber(workerHeartbeat, "max_concurrent_jobs");
  const activeJobs = readHeartbeatNumber(workerHeartbeat, "active_jobs");
  const pollIntervalSeconds = readHeartbeatNumber(workerHeartbeat, "poll_interval_seconds");

  if (!workerHeartbeat) {
    return {
      title: "执行容量",
      value: "未检测到 worker 心跳",
      description: "若任务持续排队且这里没有 worker 心跳，优先确认回测执行服务是否正在运行。",
    };
  }

  const usedJobs = activeJobs ?? runningJobs;
  if (maxConcurrentJobs !== null) {
    const remainingSlots = Math.max(0, maxConcurrentJobs - usedJobs);
    return {
      title: "执行容量",
      value: `${usedJobs}/${maxConcurrentJobs} 槽位已用`,
      description:
        queuedJobs > 0 && remainingSlots === 0
          ? `当前执行槽位已满。worker 约每 ${pollIntervalSeconds ?? 5} 秒轮询一次，新任务需要等已有任务释放槽位。`
          : `当前还剩 ${remainingSlots} 个执行槽位。${pollIntervalSeconds !== null ? `worker 轮询间隔约 ${pollIntervalSeconds} 秒。` : ""}`,
    };
  }

  return {
    title: "执行容量",
    value: `${usedJobs} 个任务活跃`,
    description: "已检测到 worker 心跳，但未记录明确的并发上限。可结合任务队列与服务心跳继续判断。",
  };
}

function buildPerJobBudgetGuide(workerHeartbeat: PlatformStatus["heartbeats"][number] | undefined): CapacityGuide {
  const maxOptimizationWorkers = readHeartbeatNumber(workerHeartbeat, "max_optimization_workers");
  const maxConcurrentJobs = readHeartbeatNumber(workerHeartbeat, "max_concurrent_jobs");
  if (!workerHeartbeat) {
    return {
      title: "单任务资源上限",
      value: "等待 worker 心跳",
      description: "未检测到 worker 心跳时，无法判断单任务参数搜索的资源预算。",
    };
  }
  if (maxOptimizationWorkers !== null) {
    return {
      title: "单任务资源上限",
      value: `单任务最多 ${maxOptimizationWorkers} 组并行`,
      description:
        maxConcurrentJobs !== null
          ? `平台会在“同时跑 ${maxConcurrentJobs} 个任务”和“单任务最多 ${maxOptimizationWorkers} 组并行”之间自动收口 CPU 预算。`
          : "这意味着单个回测任务不会无限占满资源，即使请求了更大的参数并发。",
    };
  }
  return {
    title: "单任务资源上限",
    value: "心跳未记录寻参上限",
    description: "若需要进一步确认，可查看任务页里的资源摘要或下方服务心跳信息。",
  };
}

function buildFailureGuide(failedJobs: number, unhealthyServices: string[]): CapacityGuide {
  if (unhealthyServices.length > 0) {
    return {
      title: "当前优先处理",
      value: `先检查 ${unhealthyServices.join("、")}`,
      description: "服务异常优先级高于历史失败任务统计。只要基础服务不正常，先不要花时间解释任务结果。",
    };
  }
  if (failedJobs > 0) {
    return {
      title: "失败记录",
      value: `${failedJobs} 条历史失败`,
      description: "历史失败不代表当前平台仍然异常。若当前服务与队列正常，更应回任务页核对最近失败原因是否重复。",
    };
  }
  return {
    title: "失败记录",
    value: "当前没有失败压力",
    description: "没有服务异常，也没有失败任务压力，通常无需继续停留在维护页。",
  };
}

export function PlatformStatusView() {
  const [status, setStatus] = useState<PlatformStatus | null>(null);
  const [processes, setProcesses] = useState<PlatformProcess[]>([]);
  const [logs, setLogs] = useState<PlatformLogs | null>(null);
  const [logService, setLogService] = useState("api");
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [partialError, setPartialError] = useState<string | null>(null);
  const [messageApi, contextHolder] = message.useMessage();

  async function fetchPlatformPayload(service: string) {
    const [statusResult, processesResult, logsResult] = await Promise.all([
      apiFetchSafe<PlatformStatus>("/api/platform/status"),
      apiFetchSafe<PlatformProcess[]>("/api/platform/processes"),
      apiFetchSafe<PlatformLogs>(`/api/platform/logs?service=${service}&limit=120`),
    ]);
    return { statusResult, processesResult, logsResult };
  }

  const refreshPlatform = useCallback(async () => {
    setLoading(true);
    const payload = await fetchPlatformPayload(logService);
    const issues: string[] = [];

    if (payload.statusResult.ok) {
      setStatus(payload.statusResult.data);
      setLoadError(null);
    } else {
      setLoadError(payload.statusResult.error.message);
      issues.push(`平台状态读取失败：${payload.statusResult.error.message}`);
    }

    if (payload.processesResult.ok) {
      setProcesses(payload.processesResult.data);
    } else {
      setProcesses([]);
      issues.push(`本机服务列表读取失败：${payload.processesResult.error.message}`);
    }

    if (payload.logsResult.ok) {
      setLogs(payload.logsResult.data);
    } else {
      setLogs(null);
      issues.push(`日志读取失败：${payload.logsResult.error.message}`);
    }

    setPartialError(payload.statusResult.ok ? (issues.length > 0 ? issues.join("；") : null) : null);
    setLoading(false);
  }, [logService]);

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
    queueMicrotask(() => {
      void refreshPlatform();
    });
    // 仅在日志服务切换时重新加载；手动刷新由按钮触发。
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [logService]);

  useEffect(() => {
    if (!status) {
      return;
    }
    const queue = status.queue ?? {};
    const shouldPoll =
      !serviceOk(status.api.status) ||
      !serviceOk(status.frontend.status) ||
      !serviceOk(status.database.status) ||
      Number(queue.running ?? 0) > 0 ||
      Number(queue.queued ?? 0) > 0 ||
      Number(queue.cancel_requested ?? 0) > 0;
    if (!shouldPoll) {
      return;
    }
    const timer = window.setInterval(() => {
      void refreshPlatform();
    }, 5000);
    return () => window.clearInterval(timer);
  }, [refreshPlatform, status]);

  if (loading && !status) {
    return <Skeleton active paragraph={{ rows: 10 }} />;
  }

  if (!status) {
    return <PageErrorState title="系统状态页暂时不可用" description={loadError ?? "暂时无法读取平台状态"} onRetry={() => void refreshPlatform()} />;
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
  const workerHeartbeat = status.heartbeats.find((item) => item.service_name === "worker");
  const schedulerHeartbeat = status.heartbeats.find((item) => item.service_name === "scheduler");
  const workerPollInterval = readHeartbeatNumber(workerHeartbeat, "poll_interval_seconds");
  const capacityGuides: CapacityGuide[] = [
    buildQueuePressureGuide({ runningJobs, queuedJobs, cancelRequestedJobs }),
    buildWorkerCapacityGuide(workerHeartbeat, runningJobs, queuedJobs),
    buildPerJobBudgetGuide(workerHeartbeat),
    buildFailureGuide(failedJobs, unhealthyServices),
  ];

  return (
    <div className="page-stack">
      {contextHolder}
      {partialError ? <InlineErrorBanner message={partialError} onRetry={() => void refreshPlatform()} /> : null}
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

      <Card size="small" className="section-card maintenance-capacity-card">
        <div className="maintenance-capacity-main">
          <strong>并发与资源判断</strong>
          <p>这里不只是看服务有没有活着，而是用来判断当前是否卡在执行容量、队列积压，还是已经需要进入排障流程。</p>
          <div className="maintenance-capacity-grid">
            {capacityGuides.map((item) => (
              <article key={item.title} className="maintenance-capacity-guide-card">
                <span>{item.title}</span>
                <strong>{item.value}</strong>
                <p>{item.description}</p>
              </article>
            ))}
          </div>
        </div>
        <div className="maintenance-capacity-side">
          <div className="maintenance-capacity-side-card">
            <span>worker 心跳</span>
            <strong>{workerHeartbeat ? "已检测到回测执行服务" : "未检测到回测执行服务"}</strong>
            <p>
              {workerHeartbeat
                ? `最近心跳延迟 ${workerHeartbeat.age_seconds}s。${workerPollInterval !== null ? `轮询间隔约 ${workerPollInterval} 秒。` : ""}`
                : "如果任务持续排队且这里一直没有 worker 心跳，应优先检查回测执行服务是否运行。"}
            </p>
          </div>
          <div className="maintenance-capacity-side-card">
            <span>调度与维护</span>
            <strong>{schedulerHeartbeat ? "定时同步服务在线" : "未检测到定时同步服务"}</strong>
            <p>
              {schedulerHeartbeat
                ? `当前配置了 ${status.sync_schedule.length} 条同步计划。只有数据更新异常时，才需要继续查看下方调度表。`
                : "若只是回测执行，不一定需要定时同步服务；只有行情自动更新异常时，再重点排查它。"}
            </p>
          </div>
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
