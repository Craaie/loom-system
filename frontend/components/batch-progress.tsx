"use client";

import { useEffect, useState } from "react";
import { Progress } from "@/components/ui/progress";
import { loomApi } from "@/lib/api";
import { Loader2, CheckCircle2, AlertCircle } from "lucide-react";

interface BatchProgressProps {
  threadId: string;
  onComplete?: () => void;
}

export function BatchProgress({ threadId, onComplete }: BatchProgressProps) {
  const [data, setData] = useState<{
    progress: number;
    status: string;
    total: number;
    completed: number;
  } | null>(null);

  const [isDoneAlready, setIsDoneAlready] = useState(false);

  useEffect(() => {
    let isInitialFetch = true;
    const poll = async () => {
      try {
        const res = await loomApi.getBatchProgress(threadId);
        setData(res);
        const isCompleted = res.status === "completed" || res.progress >= 100;
        
        if (isCompleted) {
          if (isInitialFetch) {
            // 如果初始加载就是完成状态，不触发 onComplete 回调（防止自动跳转）
            setIsDoneAlready(true);
          } else if (!isDoneAlready) {
            // 只有从非完成状态转变为完成状态时，才触发回调
            if (onComplete) onComplete();
          }
          return;
        }
        
        isInitialFetch = false;
        // 继续轮询
        setTimeout(poll, 5000);
      } catch (error) {
        console.error("Failed to poll batch progress:", error);
      }
    };

    poll();
  }, [threadId]);

  if (!data) return null;

  const isCompleted = data.status === "completed" || data.progress >= 100;
  const isFailed = data.status === "failed";

  return (
    <div className="space-y-3 p-4 border rounded-xl bg-muted/5 shadow-sm">
      <div className="flex justify-between items-center text-sm">
        <div className="flex items-center gap-2 font-medium">
          {isCompleted ? (
            <CheckCircle2 className="w-4 h-4 text-green-500" />
          ) : isFailed ? (
            <AlertCircle className="w-4 h-4 text-destructive" />
          ) : (
            <Loader2 className="w-4 h-4 animate-spin text-primary" />
          )}
          <span>
            {isCompleted ? "分析完成" : 
             isFailed ? "分析失败" : 
             data.status === "initial" ? "正在准备内容与分卷..." : 
             "智慧织造进行中..."}
          </span>
        </div>
        <span className="text-muted-foreground">
          {data.completed} / {data.total} 章节
        </span>
      </div>
      
      <Progress value={data.progress} className="h-2" />
      
      <div className="flex justify-between text-[10px] text-muted-foreground uppercase tracking-widest">
        <span>Batch ID Analysis</span>
        <span>{data.progress}%</span>
      </div>
    </div>
  );
}
