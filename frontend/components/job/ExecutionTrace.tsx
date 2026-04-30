"use client";

import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Activity, ScrollText, Timer } from "lucide-react";
import type { ExecutionLog } from "@/types/job";
import { NODE_LABELS, WORKFLOW_NODES } from "@/types/job";

interface ExecutionTraceProps {
  activeNode: string | null;
  pipelineStatus?: Record<string, any> | null;
  logs: ExecutionLog[];
  isStreaming: boolean;
}

export default function ExecutionTrace({ activeNode, pipelineStatus, logs, isStreaming }: ExecutionTraceProps) {
  return (
    <div className="h-full bg-background flex flex-col">
      {/* 区域标题 */}
      <div className="p-4 border-b border-white/5 flex items-center justify-between bg-black/40">
        <div className="flex items-center gap-2">
          <Activity className="h-4 w-4 text-primary" />
          <h2 className="text-xs font-bold uppercase tracking-widest text-foreground/80">
            执行踪迹 Trace
          </h2>
        </div>
        {isStreaming && (
          <Badge
            variant="outline"
            className="text-[10px] bg-primary/10 border-primary/20 text-primary animate-pulse"
          >
            LIVE
          </Badge>
        )}
      </div>

      <div className="flex-1 overflow-hidden flex flex-col">
        {/* 节点流程图 */}
        <div className="p-4 space-y-4">
          <div className="flex items-center justify-between px-1">
             {WORKFLOW_NODES.map((node, i) => {
              const isActive = activeNode === node;
              
              // 判断是否已完成（要么位于 activeNode 之前，要么在 DB 状态中是 completed/skipped）
              const statusInfo = pipelineStatus?.[node];
              let isDone = false;
              if (statusInfo?.status === "completed" || statusInfo?.status === "skipped" || statusInfo?.status === "done") {
                  isDone = true;
              } else if (activeNode && WORKFLOW_NODES.indexOf(activeNode as any) > i) {
                  isDone = true;
              }

              return (
                <div key={node} className="flex flex-col items-center gap-2">
                  <div
                    className={cn(
                      "h-2 w-8 rounded-full transition-all duration-500",
                      isActive
                        ? "bg-primary shadow-[0_0_10px_rgba(var(--primary),0.5)]"
                        : isDone
                          ? "bg-green-500"
                          : "bg-white/5"
                    )}
                  />
                  <span className="text-[8px] uppercase tracking-tighter text-foreground/30 font-bold">
                    {NODE_LABELS[node]}
                  </span>
                </div>
              );
            })}
          </div>

          {/* 动态进度摘要 */}
          {(() => {
            const allNodes = WORKFLOW_NODES as readonly string[];
            const completedCount = allNodes.filter(
              (n) => ["completed", "done", "skipped"].includes(pipelineStatus?.[n]?.status)
            ).length;
            const pct = allNodes.length > 0 ? Math.round((completedCount / allNodes.length) * 100) : 0;
            return (
              <div className="bg-white/5 rounded-xl p-4 border border-white/5 space-y-3">
                <div className="flex justify-between items-center text-xs">
                  <span className="text-foreground/40 flex items-center gap-1.5">
                    <Timer className="h-3 w-3" /> 流程进度
                  </span>
                  <span className="font-mono text-primary">
                    {completedCount}/{allNodes.length} 完成
                  </span>
                </div>
                <Progress value={pct} className="h-1 bg-white/5" />
              </div>
            );
          })()}
        </div>

        <Separator className="bg-white/5" />

        {/* 日志终端 */}
        <ScrollArea className="flex-1 px-4 py-2">
          <div className="space-y-4 font-mono text-[11px]">
            {logs.length > 0 ? (
              logs.map((log, i) => (
                <div
                  key={i}
                  className="space-y-1 animate-in fade-in slide-in-from-left duration-300"
                >
                  <div className="flex items-center gap-2 text-white/30">
                    <span className="text-[9px] bg-white/5 px-1 rounded">
                      [{log.source || "SYSTEM"}]
                    </span>
                    <span>
                      {log.ts
                        ? new Date(log.ts * 1000).toLocaleTimeString()
                        : "--:--:--"}
                    </span>
                  </div>
                  <p
                    className={cn(
                      "leading-relaxed",
                      log.level === "error"
                        ? "text-red-500"
                        : log.level === "warning"
                          ? "text-yellow-600 dark:text-yellow-400"
                          : "text-foreground/70"
                    )}
                  >
                    {log.message}
                  </p>
                </div>
              ))
            ) : (
              <div className="py-20 text-center space-y-3 opacity-20 text-foreground">
                <ScrollText className="h-8 w-8 mx-auto" />
                <p className="text-xs">等待引擎输出日志...</p>
              </div>
            )}
            <div className="h-4" />
          </div>
        </ScrollArea>
      </div>
    </div>
  );
}
