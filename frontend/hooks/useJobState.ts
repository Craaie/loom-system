"use client";

import { useEffect, useState, useCallback } from "react";
import { BACKEND_BASE_URL, loomApi } from "@/lib/api";
import { useSSE } from "@/hooks/useSSE";
import type { AudioTask, ExecutionLog, ImageTask, JobState, Storyboard, VideoTask } from "@/types/job";

export interface JobStateResult {
  /** 原始任务状态 */
  state: JobState | null;
  /** 是否正在加载初始数据 */
  isLoading: boolean;
  /** 加载错误 */
  loadError: string | null;
  /** SSE 是否已连接 */
  isStreaming: boolean;
  /** 最后事件时间 */
  lastEventTime: number;
  /** SSE 连接错误 */
  connectionError: string | null;
  /** 手动重连 */
  reconnect: () => void;
  /** 当前激活节点 */
  activeNode: string | null;
  /** 是否等待人工审批 */
  isPendingApproval: boolean;
  /** 分镜列表 */
  storyboards: Storyboard[];
  /** 执行日志 */
  logs: ExecutionLog[];
  /** 当前成本 */
  cost: number;
  /** 执行错误 */
  executionError: string | null;
  /** 最终合成视频 URL */
  finalVideoUrl: string | null;
  /** 当前预算 */
  budget: number;
  /** 原始素材任务列表 */
  imageTasks: ImageTask[];
  audioTasks: AudioTask[];
}

interface StreamUpdatePayload {
  cost?: number;
  next?: string[];
  error?: string;
}

interface StreamEventPayload {
  event?: string;
  data?: unknown;
}

type StoryboardWithLegacyFields = Storyboard & {
  description?: string;
  dialogue?: string;
};

const hasThreadId = (threadId?: string) => Boolean(threadId && threadId.trim());

/**
 * 任务状态聚合 Hook
 * 
 * 合并 REST 初始数据 + SSE 增量更新，对外暴露统一的状态接口。
 */
export function useJobState(threadId?: string): JobStateResult {
  const [state, setState] = useState<JobState | null>(null);
  const [isLoading, setIsLoading] = useState(() => hasThreadId(threadId));
  const [loadError, setLoadError] = useState<string | null>(null);
  const [lastActiveNode, setLastActiveNode] = useState<string | null>(null);
  const [executionError, setExecutionError] = useState<string | null>(null);
  const [cost, setCost] = useState(0);

  // 1. 获取初始状态
  useEffect(() => {
    const activeThreadId = threadId?.trim();
    if (!activeThreadId) {
      return;
    }

    const loadInitialState = async () => {
      setIsLoading(true);
      setLoadError(null);

      try {
        const data = await loomApi.getJobState(activeThreadId);
        setState(data);
        setCost(data?.values?.cost_accumulator || 0);
      } catch (error) {
        const message = error instanceof Error ? error.message : "加载任务状态失败";
        setLoadError(message);
      } finally {
        setIsLoading(false);
      }
    };

    loadInitialState();
  }, [threadId]);

  // 2. SSE 消息处理
  const handleSSEMessage = useCallback((data: StreamEventPayload) => {
    if (data.event === "update") {
      const payload = (data.data ?? {}) as StreamUpdatePayload;
      
      // 更新成本
      if (payload.cost !== undefined) {
        setCost(payload.cost);
      }

      // 更新激活节点
      const nextNodes = payload.next ?? [];
      if (nextNodes.length > 0) {
        setLastActiveNode(nextNodes[0]);
      }

      // 捕获执行错误
      if (payload.error) {
        setExecutionError(payload.error);
      }

      // 增量刷新完整状态
      if (threadId) {
        loomApi.getJobState(threadId).then(setState).catch(console.error);
      }
    } else if (data.event === "error") {
      setExecutionError(typeof data.data === "string" ? data.data : "执行错误");
    } else if (data.event === "ping") {
      // 保持连接心跳
    }
  }, [threadId]);

  const handleSSEEnd = useCallback(() => {
    // 流结束时做最终状态刷新
    if (threadId) {
      loomApi.getJobState(threadId).then(setState).catch(console.error);
    }
  }, [threadId]);

  // 3. SSE 连接
  const sse = useSSE({
    url: threadId ? loomApi.getStreamUrl(threadId) : "",
    onMessage: handleSSEMessage,
    onEnd: handleSSEEnd,
    enabled: !!threadId,
  });

  // 4. 派生状态
  const currentNodes = state?.next || [];
  const activeNode = currentNodes.length > 0 ? currentNodes[0] : lastActiveNode;
  const isPendingApproval = currentNodes.includes("hitl_approval") || currentNodes.includes("hitl_storyboard");
  const rawStoryboards = (state?.values?.storyboard_json || []) as StoryboardWithLegacyFields[];
  const imageTasks = (state?.values?.image_tasks || []) as ImageTask[];
  const audioTasks = (state?.values?.audio_tasks || []) as AudioTask[];

  // 合并资产任务到分镜对象中
  const storyboards = rawStoryboards.map((sb, i) => {
    const imgTask = imageTasks.find((task) => task.task_id === `img_${i}`);
    const audTask = audioTasks.find((task) => task.task_id === `audio_${i}`);

    return {
      ...sb,
      image_prompt: sb.image_prompt || sb.description || "",
      narration: sb.narration || sb.dialogue || "",
      image_path: imgTask?.image_path || sb.image_path,
      audio_path: audTask?.audio_path || sb.audio_path,
      status: imgTask?.status || sb.status || "pending",
    };
  });
  const logs = (state?.values?.execution_logs || []) as ExecutionLog[];

  // 最终视频 URL 派生
  const finalAssembly = ((state?.values?.video_tasks || []) as VideoTask[]).find(
    (task) => task.task_id === "final_assembly" && task.video_path
  );
  const finalVideoUrl = finalAssembly?.video_path
    ? `${BACKEND_BASE_URL}${finalAssembly.video_path}`
    : null;
  const budget = state?.values?.cost_limit || 10;

  return {
    state,
    isLoading: hasThreadId(threadId) ? isLoading : false,
    loadError,
    isStreaming: sse.isConnected,
    lastEventTime: sse.lastEventTime,
    connectionError: sse.error,
    reconnect: sse.reconnect,
    activeNode,
    isPendingApproval,
    storyboards,
    logs,
    cost,
    executionError,
    finalVideoUrl,
    budget,
    imageTasks,
    audioTasks,
  };
}
