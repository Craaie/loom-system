"use client";

import { AlertTriangle, ArrowRight, Check, Cpu, Edit3, Film, LayoutGrid, Play, RotateCcw, ScrollText, Wallet } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";
import { CharacterArchive } from "./CharacterArchive";
import { PipelineProgress } from "./PipelineProgress";
import type { JobValues } from "@/types/job";
import { getWorkbenchSnapshot } from "@/lib/workbench";

interface ControlCenterProps {
  threadId: string;
  cost: number;
  budget?: number;
  values: JobValues | null;
  activeNode?: string | null;
  isPendingApproval: boolean;
  isStreaming: boolean;
  executionError: string | null;
  finalVideoUrl?: string | null;
  onApprove: () => void;
  onResume: () => void;
  isActing: boolean;
  onUpdateState?: (updates: Partial<JobValues>) => Promise<void>;
  onShowScenes?: () => void;
  onShowVideo?: () => void;
  onShowLogs?: () => void;
}

export default function ControlCenter({
  threadId,
  cost,
  budget = 10,
  values,
  activeNode,
  isPendingApproval,
  isStreaming,
  executionError,
  finalVideoUrl,
  onApprove,
  onResume,
  isActing,
  onUpdateState,
  onShowScenes,
  onShowVideo,
  onShowLogs,
}: ControlCenterProps) {
  const imageTasks = values?.image_tasks || [];
  const audioTasks = values?.audio_tasks || [];
  const snapshot = getWorkbenchSnapshot({
    threadId,
    activeNode,
    isPendingApproval,
    isStreaming,
    executionError,
    finalVideoUrl,
    storyboardCount: values?.storyboard_json?.length || 0,
    imageTotal: imageTasks.length,
    imageDone: imageTasks.filter((task) => task.status === "done").length,
    audioTotal: audioTasks.length,
    audioDone: audioTasks.filter((task) => task.status === "done").length,
    budget,
    cost,
  });

  const budgetUsage = budget > 0 ? Math.min(100, Math.round((cost / budget) * 100)) : 0;
  const remainingBudget = Math.max(0, budget - cost);

  const handleFocus = () => {
    if (executionError) {
      onShowLogs?.();
      return;
    }
    if (isPendingApproval) {
      onShowScenes?.();
      return;
    }
    if (finalVideoUrl) {
      onShowVideo?.();
      return;
    }
    if (snapshot.summary.focusTarget === "storyboard") {
      onShowScenes?.();
      return;
    }
    if (snapshot.summary.focusTarget === "video") {
      onShowVideo?.();
      return;
    }
    onShowLogs?.();
  };

  return (
    <aside className="w-full max-w-[360px] border-l border-border bg-background/95 shrink-0">
      <div className="sticky top-0 flex h-screen flex-col">
        <div className="border-b border-border bg-muted/20 px-5 py-4">
          <div className="flex items-center gap-2">
            <Cpu className="h-4 w-4 text-primary" />
            <div>
              <h2 className="text-sm font-semibold">当前待办</h2>
              <p className="text-xs text-muted-foreground">所有辅助信息都围绕下一步动作展开</p>
            </div>
          </div>
        </div>

        <div className="flex-1 space-y-4 overflow-auto p-5">
          <Card className="border-border/60">
            <CardHeader className="space-y-3 pb-3">
              <div className="flex items-center justify-between gap-3">
                <Badge
                  variant="outline"
                  className={cn(
                    "rounded-full px-3 py-1 text-[11px] font-semibold",
                    executionError
                      ? "border-destructive/20 bg-destructive/[0.08] text-destructive"
                      : isPendingApproval
                        ? "border-amber-500/20 bg-amber-500/[0.08] text-amber-600 dark:text-amber-400"
                        : finalVideoUrl
                          ? "border-emerald-500/20 bg-emerald-500/[0.08] text-emerald-600 dark:text-emerald-400"
                          : "border-primary/20 bg-primary/[0.08] text-primary"
                  )}
                >
                  {snapshot.summary.eyebrow}
                </Badge>
                <span className="text-xs text-muted-foreground">{snapshot.progressPercent}%</span>
              </div>
              <div>
                <CardTitle className="text-base leading-6">{snapshot.summary.title}</CardTitle>
                <p className="mt-1 text-sm leading-6 text-muted-foreground">{snapshot.summary.description}</p>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <Progress value={snapshot.progressPercent} className="h-2" />
              <div className="grid gap-2">
                <Button className="w-full rounded-xl" onClick={handleFocus} disabled={isActing}>
                  {executionError ? "查看错误上下文" : snapshot.summary.primaryActionLabel}
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Button>
                <div className="grid grid-cols-2 gap-2">
                  <Button variant="outline" className="rounded-xl" onClick={onShowScenes} disabled={isActing}>
                    <LayoutGrid className="mr-2 h-4 w-4" />
                    分镜
                  </Button>
                  <Button variant="outline" className="rounded-xl" onClick={onShowLogs} disabled={isActing}>
                    <ScrollText className="mr-2 h-4 w-4" />
                    日志
                  </Button>
                </div>
                {finalVideoUrl && (
                  <Button variant="outline" className="w-full rounded-xl" onClick={onShowVideo}>
                    <Film className="mr-2 h-4 w-4" />
                    打开成片预览
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>

          <Card className="border-border/60">
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-sm">
                <Wallet className="h-4 w-4 text-primary" />
                资源与产出
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-sm">
              <div className="grid grid-cols-2 gap-3">
                <InfoTile label="已产出分镜" value={`${snapshot.metrics.storyboardCount}`} />
                <InfoTile label="剩余预算" value={`$${remainingBudget.toFixed(2)}`} />
                <InfoTile label="图片进度" value={`${snapshot.metrics.imageDone}/${snapshot.metrics.imageTotal || 0}`} />
                <InfoTile label="音频进度" value={`${snapshot.metrics.audioDone}/${snapshot.metrics.audioTotal || 0}`} />
              </div>
              <div className="space-y-2">
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span>预算使用率</span>
                  <span>{budgetUsage}%</span>
                </div>
                <Progress value={budgetUsage} className="h-2" />
              </div>
            </CardContent>
          </Card>

          <PipelineProgress threadId={threadId} isStreaming={isStreaming} onRetryStart={onResume} />

          <HitlApprovalPanel
            isPendingApproval={isPendingApproval}
            onApprove={onApprove}
            isActing={isActing}
            onShowScenes={onShowScenes}
          />

          <CharacterArchive
            registry={values?.character_registry}
            onUpdateRegistry={onUpdateState ? (newReg) => onUpdateState({ character_registry: newReg }) : undefined}
          />

          <Card className="border-border/60">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm">快捷操作</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-2">
              <Button
                variant={executionError ? "default" : "outline"}
                className="w-full rounded-xl"
                onClick={onResume}
                disabled={(isStreaming && !executionError) || isActing}
              >
                {executionError ? <RotateCcw className="mr-2 h-4 w-4" /> : <Play className="mr-2 h-4 w-4" />}
                {executionError ? "从断点恢复" : "继续执行"}
              </Button>
              <Button variant="outline" className="w-full rounded-xl" onClick={handleFocus} disabled={isActing}>
                {isPendingApproval ? <Edit3 className="mr-2 h-4 w-4" /> : <AlertTriangle className="mr-2 h-4 w-4" />}
                {isPendingApproval ? "先去审阅分镜" : "查看当前阶段详情"}
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </aside>
  );
}

function InfoTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-border/60 bg-muted/20 p-3">
      <div className="text-[11px] text-muted-foreground">{label}</div>
      <div className="mt-1 text-sm font-semibold">{value}</div>
    </div>
  );
}

function HitlApprovalPanel({
  isPendingApproval,
  onApprove,
  isActing,
  onShowScenes,
}: {
  isPendingApproval: boolean;
  onApprove: () => void;
  isActing: boolean;
  onShowScenes?: () => void;
}) {
  return (
    <Card className={cn("border-border/60", isPendingApproval && "border-amber-500/30 bg-amber-500/[0.05]")}>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm">人工审阅</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm leading-6 text-muted-foreground">
          {isPendingApproval
            ? "分镜已经生成完毕。先审，再批准，比成片后返工更省时。"
            : "当前无需人工审批，系统会继续推进后续阶段。"}
        </p>
        <div className="grid gap-2">
          <Button className="w-full rounded-xl" disabled={!isPendingApproval || isActing} onClick={onApprove}>
            <Check className="mr-2 h-4 w-4" />
            批准并继续
          </Button>
          <Button variant="outline" className="w-full rounded-xl" disabled={!isPendingApproval} onClick={onShowScenes}>
            <Edit3 className="mr-2 h-4 w-4" />
            先去修改分镜
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
