"use client";

import { ArrowRight, CheckCircle2, Circle, Images, Mic2, Sparkles, AlertTriangle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";
import { getWorkbenchSnapshot, type WorkbenchContext } from "@/lib/workbench";

interface WorkflowOverviewProps {
  title: string;
  subtitle: string;
  context: WorkbenchContext;
  onPrimaryAction?: () => void;
  primaryActionLabel?: string;
  primaryActionHint?: string;
  primaryActionDisabled?: boolean;
  secondaryActionLabel?: string;
  onSecondaryAction?: () => void;
  secondaryActionDisabled?: boolean;
}

const toneStyles = {
  default: "border-primary/10 bg-primary/[0.03] text-primary",
  success: "border-emerald-500/20 bg-emerald-500/[0.08] text-emerald-600 dark:text-emerald-400",
  warning: "border-amber-500/20 bg-amber-500/[0.08] text-amber-600 dark:text-amber-400",
  danger: "border-destructive/20 bg-destructive/[0.08] text-destructive",
} as const;

const stageStyles = {
  pending: "border-border bg-background text-muted-foreground",
  current: "border-primary/20 bg-primary/[0.06] text-foreground",
  completed: "border-emerald-500/20 bg-emerald-500/[0.08] text-foreground",
  attention: "border-amber-500/20 bg-amber-500/[0.08] text-foreground",
  failed: "border-destructive/20 bg-destructive/[0.08] text-foreground",
} as const;

export function WorkflowOverview({
  title,
  subtitle,
  context,
  onPrimaryAction,
  primaryActionLabel,
  primaryActionHint,
  primaryActionDisabled,
  secondaryActionLabel,
  onSecondaryAction,
  secondaryActionDisabled,
}: WorkflowOverviewProps) {
  const snapshot = getWorkbenchSnapshot(context);
  const budgetPercent = snapshot.metrics.budget > 0
    ? Math.min(100, Math.round((snapshot.metrics.cost / snapshot.metrics.budget) * 100))
    : 0;

  return (
    <Card className="overflow-hidden border-border/60 bg-card/70 shadow-sm">
      <CardHeader className="gap-5 border-b border-border/60 bg-gradient-to-br from-primary/[0.06] via-background to-background">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-3">
            <Badge variant="outline" className={cn("w-fit rounded-full px-3 py-1 text-[11px] font-semibold", toneStyles[snapshot.summary.tone])}>
              {snapshot.summary.eyebrow}
            </Badge>
            <div className="space-y-1.5">
              <CardTitle className="text-2xl tracking-tight">{title}</CardTitle>
              <CardDescription className="max-w-3xl text-sm leading-6">{subtitle}</CardDescription>
            </div>
          </div>

          <div className="grid min-w-[260px] gap-3 sm:grid-cols-2 lg:w-[360px]">
            <MetricCard label="当前阶段" value={snapshot.currentStageLabel} helper={`${snapshot.progressPercent}% 已推进`} />
            <MetricCard label="预算消耗" value={`$${snapshot.metrics.cost.toFixed(2)} / $${snapshot.metrics.budget.toFixed(2)}`} helper={budgetPercent >= 85 ? "接近预算上限" : "预算仍可继续使用"} />
            <MetricCard label="分镜数量" value={`${snapshot.metrics.storyboardCount}`} helper="可随时进入审阅" icon={<Sparkles className="h-3.5 w-3.5" />} />
            <MetricCard label="素材进度" value={`${snapshot.metrics.imageDone}/${snapshot.metrics.imageTotal || 0} 图 · ${snapshot.metrics.audioDone}/${snapshot.metrics.audioTotal || 0} 音`} helper="按实体素材追踪，而非抽象百分比" icon={<Images className="h-3.5 w-3.5" />} />
          </div>
        </div>

        <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_340px]">
          <div className="space-y-3 rounded-2xl border border-border/60 bg-background/80 p-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-muted-foreground">当前聚焦</p>
                <h3 className="mt-1 text-lg font-semibold">{snapshot.summary.title}</h3>
              </div>
              {snapshot.summary.tone === "danger" ? (
                <AlertTriangle className="h-5 w-5 text-destructive" />
              ) : (
                <CheckCircle2 className="h-5 w-5 text-primary" />
              )}
            </div>
            <p className="text-sm leading-6 text-muted-foreground">{snapshot.summary.description}</p>
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>整体推进</span>
                <span>{snapshot.progressPercent}%</span>
              </div>
              <Progress value={snapshot.progressPercent} className="h-2" />
            </div>
          </div>

          <div className="space-y-3 rounded-2xl border border-border/60 bg-background/80 p-4">
            <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-muted-foreground">建议下一步</p>
            <div className="space-y-1">
              <h3 className="text-base font-semibold">{primaryActionLabel || snapshot.summary.primaryActionLabel}</h3>
              <p className="text-sm leading-6 text-muted-foreground">{primaryActionHint || snapshot.summary.primaryActionHint}</p>
            </div>
            <div className="flex flex-wrap gap-2 pt-1">
              {onPrimaryAction && (
                <Button className="rounded-full px-5" onClick={onPrimaryAction} disabled={primaryActionDisabled}>
                  {primaryActionLabel || snapshot.summary.primaryActionLabel}
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Button>
              )}
              {onSecondaryAction && secondaryActionLabel && (
                <Button variant="outline" className="rounded-full px-5" onClick={onSecondaryAction} disabled={secondaryActionDisabled}>
                  {secondaryActionLabel}
                </Button>
              )}
            </div>
          </div>
        </div>
      </CardHeader>

      <CardContent className="grid gap-3 p-5 md:grid-cols-2 xl:grid-cols-6">
        {snapshot.stages.map((stage) => (
          <div key={stage.key} className={cn("rounded-2xl border p-4 transition-colors", stageStyles[stage.status])}>
            <div className="flex items-center gap-2 text-sm font-semibold">
              {stage.status === "completed" ? (
                <CheckCircle2 className="h-4 w-4 text-emerald-500" />
              ) : stage.status === "current" ? (
                <Sparkles className="h-4 w-4 text-primary" />
              ) : stage.status === "attention" ? (
                <AlertTriangle className="h-4 w-4 text-amber-500" />
              ) : stage.status === "failed" ? (
                <AlertTriangle className="h-4 w-4 text-destructive" />
              ) : (
                <Circle className="h-4 w-4" />
              )}
              <span>{stage.label}</span>
            </div>
            <p className="mt-2 text-xs leading-5 text-muted-foreground">{stage.description}</p>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function MetricCard({ label, value, helper, icon }: { label: string; value: string; helper: string; icon?: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-border/60 bg-background/80 p-3.5">
      <div className="flex items-center justify-between gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
        <span>{label}</span>
        {icon || <Mic2 className="h-3.5 w-3.5 opacity-50" />}
      </div>
      <div className="mt-2 text-sm font-semibold text-foreground">{value}</div>
      <div className="mt-1 text-xs text-muted-foreground">{helper}</div>
    </div>
  );
}
