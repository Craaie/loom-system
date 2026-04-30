"use client";

import { useEffect, useRef, useState } from "react";
import { loomApi } from "@/lib/api";
import { 
  CheckCircle2, 
  Circle, 
  Loader2, 
  XCircle, 
  FastForward,
  Play,
  RotateCcw
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";

interface PipelineStageInfo {
  stage: string;
  label: string;
  status: "pending" | "running" | "completed" | "failed" | "skipped";
  error?: string;
}

interface PipelineStatusResponse {
  thread_id: string;
  overall_status: "pending" | "running" | "completed" | "failed" | "in_progress";
  is_active: boolean;
  stages: PipelineStageInfo[];
}

interface PipelineProgressProps {
  threadId: string;
  isStreaming: boolean;
  onRetryStart?: () => void;
}

// 不允许从这些纯逻辑节点回退（回退没有意义）
const NON_RETRYABLE_STAGES = new Set(["batch_analysis", "supervisor"]);

export function PipelineProgress({ threadId, isStreaming, onRetryStart }: PipelineProgressProps) {
  const [data, setData] = useState<PipelineStatusResponse | null>(null);
  const [isRetrying, setIsRetrying] = useState(false);
  const [confirmStage, setConfirmStage] = useState<string | null>(null);

  const shouldPollRef = useRef(false);

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const res = await loomApi.getPipelineStatus(threadId);
        setData(res);
        shouldPollRef.current = 
          isStreaming || 
          res.overall_status === "running" || 
          res.overall_status === "in_progress";
      } catch (e) {
        console.error("Failed to fetch pipeline status", e);
      }
    };

    fetchStatus();
    const interval = setInterval(() => {
      if (shouldPollRef.current) fetchStatus();
    }, 3000);
    return () => clearInterval(interval);
  }, [threadId, isStreaming]);

  const handleRetry = async (stageKey?: string) => {
    try {
      setIsRetrying(true);
      setConfirmStage(null);
      if (onRetryStart) onRetryStart();
      await loomApi.retryPipelineStage(threadId, stageKey);
      toast.success(stageKey ? `已请求从 ${stageKey} 重新执行` : "已请求从失败节点重试");
    } catch (e: any) {
      toast.error(e.message || "重试请求失败");
    } finally {
      setIsRetrying(false);
    }
  };

  if (!data) return null;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-[11px] font-bold text-muted-foreground uppercase tracking-widest">
          流水线追踪
        </h3>
        <Badge 
          className={cn(
            "text-[9px] h-5 border-none",
            data.overall_status === "running" ? "bg-blue-500/10 text-blue-500" :
            data.overall_status === "failed" ? "bg-red-500/10 text-red-500" :
            data.overall_status === "completed" ? "bg-green-500/10 text-green-500" :
            "bg-muted text-muted-foreground"
          )}
        >
          {data.overall_status === "running" ? "生成中" :
           data.overall_status === "failed" ? "已暂停(失败)" :
           data.overall_status === "completed" ? "已完成" : "等待中"}
        </Badge>
      </div>

      <div className="space-y-3">
        {data.stages.map((stage, i) => {
          const canRetryFromHere = 
            stage.status === "completed" && 
            !NON_RETRYABLE_STAGES.has(stage.stage) &&
            !isRetrying &&
            !data.is_active;
          const isConfirming = confirmStage === stage.stage;

          return (
            <div key={stage.stage} className="flex gap-3 relative group/stage">
              {/* 连线 */}
              {i !== data.stages.length - 1 && (
                <div className="absolute left-[9px] top-6 bottom-[-12px] w-[2px] bg-border" />
              )}
              
              <div className="mt-0.5 relative z-10 bg-background">
                {stage.status === "completed" ? (
                  <CheckCircle2 className="w-5 h-5 text-green-500" />
                ) : stage.status === "running" ? (
                  <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />
                ) : stage.status === "failed" ? (
                  <XCircle className="w-5 h-5 text-red-500" />
                ) : stage.status === "skipped" ? (
                  <FastForward className="w-5 h-5 text-muted-foreground" />
                ) : (
                  <Circle className="w-5 h-5 text-muted/50" />
                )}
              </div>
              
              <div className="flex-1 pb-3">
                <div className="flex justify-between items-center">
                  <span className={cn(
                    "text-sm font-medium",
                    stage.status === "pending" ? "text-muted-foreground" : "text-foreground"
                  )}>
                    {stage.label}
                  </span>
                  
                  {/* 已失败节点：直接显示"重试此步" */}
                  {stage.status === "failed" && (
                    <Button 
                      variant="ghost" 
                      size="sm" 
                      className="h-6 text-xs text-red-500 hover:text-red-600 hover:bg-red-500/10 px-2"
                      onClick={() => handleRetry(stage.stage)}
                      disabled={isRetrying}
                    >
                      重试此步
                    </Button>
                  )}

                  {/* 已完成节点：hover 时显示"从此重跑" */}
                  {canRetryFromHere && !isConfirming && (
                    <Button 
                      variant="ghost" 
                      size="sm" 
                      className="h-6 text-xs text-primary/60 hover:text-primary hover:bg-primary/10 px-2 opacity-0 group-hover/stage:opacity-100 transition-opacity"
                      onClick={() => setConfirmStage(stage.stage)}
                    >
                      <RotateCcw className="w-3 h-3 mr-1" />
                      从此重跑
                    </Button>
                  )}

                  {/* 二次确认弹出 */}
                  {isConfirming && (
                    <div className="flex items-center gap-1 animate-in fade-in slide-in-from-right-2 duration-200">
                      <span className="text-[10px] text-amber-500 mr-1">确认？</span>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 text-xs text-amber-500 hover:text-amber-600 hover:bg-amber-500/10 px-2 font-bold"
                        onClick={() => handleRetry(stage.stage)}
                        disabled={isRetrying}
                      >
                        确认重跑
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 text-xs text-muted-foreground hover:bg-muted/50 px-2"
                        onClick={() => setConfirmStage(null)}
                      >
                        取消
                      </Button>
                    </div>
                  )}
                </div>
                
                {stage.error && (
                  <p className="text-xs text-red-400 mt-1 line-clamp-2" title={stage.error}>
                    {stage.error}
                  </p>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {data.overall_status === "failed" && (
        <Button 
          variant="default"
          className="w-full rounded-xl bg-primary text-primary-foreground hover:bg-primary/90 mt-2"
          onClick={() => handleRetry()}
          disabled={isRetrying}
        >
          <Play className="w-4 h-4 mr-2" />
          一键从断点恢复
        </Button>
      )}
    </div>
  );
}
