"use client";

import { useState, useCallback } from "react";
import { loomApi } from "@/lib/api";
import { toast } from "sonner";

interface JobActionsResult {
  /** 批准分镜 */
  approve: () => Promise<void>;
  /** 恢复/重试任务 */
  resume: () => Promise<void>;
  /** 提交修改意见 */
  requestRevision: (feedback: string) => Promise<void>;
  /** 手动更新状态 */
  updateState: (updates: any) => Promise<void>;
  /** 是否正在执行操作 */
  isActing: boolean;
}

/**
 * 任务操作命令 Hook
 * 
 * 封装 approve / resume / revision 等 API 调用，
 * 统一处理 loading 状态与用户反馈。
 */
export function useJobActions(threadId: string): JobActionsResult {
  const [isActing, setIsActing] = useState(false);

  const approve = useCallback(async () => {
    setIsActing(true);
    try {
      await loomApi.approveJob(threadId, "approved");
      toast.success("已批准，继续生成视频");
    } catch {
      toast.error("操作失败，请重试");
    } finally {
      setIsActing(false);
    }
  }, [threadId]);

  const resume = useCallback(async () => {
    setIsActing(true);
    try {
      await loomApi.resumeJob(threadId);
      toast.success("已尝试恢复执行");
    } catch {
      toast.error("恢复失败");
    } finally {
      setIsActing(false);
    }
  }, [threadId]);

  const requestRevision = useCallback(async (feedback: string) => {
    setIsActing(true);
    try {
      await loomApi.approveJob(threadId, "revision_requested", feedback);
      toast.success("修改意见已提交");
    } catch {
      toast.error("操作失败");
    } finally {
      setIsActing(false);
    }
  }, [threadId]);

  const updateState = useCallback(async (updates: any) => {
    setIsActing(true);
    try {
      await loomApi.updateJobState(threadId, updates);
      toast.success("状态已同步到服务器");
    } catch {
      toast.error("同步失败");
    } finally {
      setIsActing(false);
    }
  }, [threadId]);

  return { approve, resume, requestRevision, updateState, isActing };
}
