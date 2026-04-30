"use client";

import { useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { Film, LayoutGrid, ScrollText, Wand2 } from "lucide-react";
import { useJobState } from "@/hooks/useJobState";
import { useJobActions } from "@/hooks/useJobActions";
import JobHeader from "@/components/job/JobHeader";
import ExecutionTrace from "@/components/job/ExecutionTrace";
import SceneEditor from "@/components/job/SceneEditor";
import ControlCenter from "@/components/job/ControlCenter";
import JobLoadingSkeleton from "@/components/job/JobLoadingSkeleton";
import { ErrorBoundary } from "@/components/error-boundary";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { WorkflowOverview } from "@/components/workbench/WorkflowOverview";
import { getWorkbenchSnapshot } from "@/lib/workbench";

type TabKey = "scenes" | "video" | "logs";

export default function JobDetailPage() {
  const { id } = useParams() as { id: string };
  const job = useJobState(id);
  const actions = useJobActions(id);
  const [manualTab, setManualTab] = useState<TabKey | null>(null);

  const snapshot = useMemo(
    () =>
      getWorkbenchSnapshot({
        threadId: id,
        activeNode: job.activeNode,
        isPendingApproval: job.isPendingApproval,
        isStreaming: job.isStreaming,
        executionError: job.executionError,
        finalVideoUrl: job.finalVideoUrl,
        storyboardCount: job.storyboards.length,
        imageTotal: job.imageTasks.length,
        imageDone: job.imageTasks.filter((task) => task.status === "done").length,
        audioTotal: job.audioTasks.length,
        audioDone: job.audioTasks.filter((task) => task.status === "done").length,
        budget: job.budget,
        cost: job.cost,
      }),
    [
      id,
      job.activeNode,
      job.audioTasks,
      job.budget,
      job.cost,
      job.executionError,
      job.finalVideoUrl,
      job.imageTasks,
      job.isPendingApproval,
      job.isStreaming,
      job.storyboards.length,
    ]
  );

  const suggestedTab: TabKey = job.finalVideoUrl
    ? "video"
    : job.executionError
      ? "logs"
      : "scenes";
  const activeTab = manualTab ?? suggestedTab;

  if (job.isLoading) return <JobLoadingSkeleton />;

  const handlePrimaryAction = () => {
    switch (snapshot.summary.focusTarget) {
      case "video":
        setManualTab("video");
        break;
      case "storyboard":
        setManualTab("scenes");
        break;
      case "logs":
      case "assets":
      case "input":
      default:
        setManualTab("logs");
        break;
    }
  };

  return (
    <ErrorBoundary>
      <div className="min-h-screen bg-background text-foreground">
        <JobHeader jobId={id} />

        <main className="mx-auto flex max-w-[1600px] flex-col gap-6 px-4 py-6 lg:px-6">
          <WorkflowOverview
            title="创作流水线工作台"
            subtitle="围绕当前任务阶段组织信息：先知道系统走到哪，再决定现在该做什么。"
            context={{
              threadId: id,
              activeNode: job.activeNode,
              isPendingApproval: job.isPendingApproval,
              isStreaming: job.isStreaming,
              executionError: job.executionError,
              finalVideoUrl: job.finalVideoUrl,
              storyboardCount: job.storyboards.length,
              imageTotal: job.imageTasks.length,
              imageDone: job.imageTasks.filter((task) => task.status === "done").length,
              audioTotal: job.audioTasks.length,
              audioDone: job.audioTasks.filter((task) => task.status === "done").length,
              budget: job.budget,
              cost: job.cost,
            }}
            onPrimaryAction={handlePrimaryAction}
            secondaryActionLabel={job.executionError ? "从断点恢复" : job.isPendingApproval ? "批准并继续" : undefined}
            onSecondaryAction={job.executionError ? actions.resume : job.isPendingApproval ? actions.approve : undefined}
            secondaryActionDisabled={actions.isActing}
          />

          <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
            <section className="min-w-0 space-y-4">
              <Card className="border-border/60 bg-card/70 shadow-sm">
                <CardContent className="p-4">
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                    <div>
                      <div className="flex items-center gap-2 text-sm font-semibold">
                        <Wand2 className="h-4 w-4 text-primary" />
                        当前任务视图
                      </div>
                      <p className="mt-1 text-sm text-muted-foreground">
                        默认优先展示你现在最需要处理的工作区：分镜、成片或日志。
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Badge variant="outline" className="rounded-full px-3 py-1 text-xs">
                        当前节点：{job.activeNode || "等待启动"}
                      </Badge>
                      {job.connectionError && (
                        <Badge variant="outline" className="rounded-full border-destructive/20 bg-destructive/[0.08] px-3 py-1 text-xs text-destructive">
                          SSE 连接异常
                        </Badge>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Tabs value={activeTab} onValueChange={(value) => setManualTab(value as TabKey)} className="gap-4">
                <TabsList className="h-auto w-full flex-wrap gap-2 rounded-2xl border border-border/60 bg-card/70 p-2">
                  <TabsTrigger value="scenes" className="min-w-[140px] rounded-xl px-4 py-2.5 data-active:bg-primary/10 data-active:text-primary">
                    <LayoutGrid className="h-4 w-4" />
                    分镜审阅
                  </TabsTrigger>
                  <TabsTrigger value="video" className="min-w-[140px] rounded-xl px-4 py-2.5 data-active:bg-primary/10 data-active:text-primary">
                    <Film className="h-4 w-4" />
                    成片输出
                  </TabsTrigger>
                  <TabsTrigger value="logs" className="min-w-[140px] rounded-xl px-4 py-2.5 data-active:bg-primary/10 data-active:text-primary">
                    <ScrollText className="h-4 w-4" />
                    执行踪迹
                  </TabsTrigger>
                </TabsList>

                <TabsContent value="scenes">
                  <Card className="overflow-hidden border-border/60 bg-card/70 shadow-sm">
                    <CardContent className="space-y-4 p-4">
                      <div className="flex flex-col gap-3 rounded-2xl border border-border/60 bg-background/80 p-4 md:flex-row md:items-center md:justify-between">
                        <div>
                          <h2 className="text-lg font-semibold">分镜审阅台</h2>
                          <p className="mt-1 text-sm text-muted-foreground">
                            先确认镜头、角色和旁白是否对，再批准进入素材与视频阶段。
                          </p>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          {job.isPendingApproval && (
                            <Button onClick={actions.approve} disabled={actions.isActing} className="rounded-full px-5">
                              批准并继续
                            </Button>
                          )}
                          {job.executionError && (
                            <Button variant="outline" onClick={actions.resume} disabled={actions.isActing} className="rounded-full px-5">
                              从断点恢复
                            </Button>
                          )}
                        </div>
                      </div>

                      <SceneEditor
                        threadId={id}
                        storyboards={job.storyboards}
                        onUpdateStoryboard={(newStoryboards) => actions.updateState({ storyboard_json: newStoryboards })}
                      />
                    </CardContent>
                  </Card>
                </TabsContent>

                <TabsContent value="video">
                  <Card className="border-border/60 bg-card/70 shadow-sm">
                    <CardContent className="p-6">
                      {job.finalVideoUrl ? (
                        <div className="space-y-5">
                          <div>
                            <h2 className="text-lg font-semibold">最终成片</h2>
                            <p className="mt-1 text-sm text-muted-foreground">
                              成片已经输出。你可以直接预览，也可以回到分镜继续做定向修正。
                            </p>
                          </div>
                          <video
                            src={job.finalVideoUrl}
                            controls
                            playsInline
                            className="w-full rounded-3xl border border-border bg-black shadow-sm"
                          >
                            Your browser does not support the video tag.
                          </video>
                        </div>
                      ) : (
                        <div className="flex min-h-[420px] flex-col items-center justify-center gap-4 text-center">
                          <Film className="h-12 w-12 text-muted-foreground/40" />
                          <div className="space-y-1">
                            <h2 className="text-lg font-semibold">成片还未完成</h2>
                            <p className="text-sm text-muted-foreground">
                              当前重点仍在前序流程。你可以先去查看分镜或执行日志，确认系统卡在哪一段。
                            </p>
                          </div>
                          <Button variant="outline" className="rounded-full px-5" onClick={() => setManualTab(job.storyboards.length > 0 ? "scenes" : "logs")}>
                            返回当前重点阶段
                          </Button>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                </TabsContent>

                <TabsContent value="logs">
                  <Card className="overflow-hidden border-border/60 bg-card/70 shadow-sm">
                    <CardContent className="p-0">
                      <div className="h-[720px]">
                        <ExecutionTrace
                          activeNode={job.activeNode}
                          pipelineStatus={job.state?.values?.pipeline_status}
                          logs={job.logs}
                          isStreaming={job.isStreaming}
                        />
                      </div>
                    </CardContent>
                  </Card>
                </TabsContent>
              </Tabs>
            </section>

            <ControlCenter
              threadId={id}
              cost={job.cost}
              budget={job.budget}
              values={job.state?.values ?? null}
              activeNode={job.activeNode}
              isPendingApproval={job.isPendingApproval}
              isStreaming={job.isStreaming}
              executionError={job.executionError}
              finalVideoUrl={job.finalVideoUrl}
              onApprove={actions.approve}
              onResume={actions.resume}
              onUpdateState={actions.updateState}
              isActing={actions.isActing}
              onShowScenes={() => setManualTab("scenes")}
              onShowVideo={() => setManualTab("video")}
              onShowLogs={() => setManualTab("logs")}
            />
          </div>
        </main>
      </div>
    </ErrorBoundary>
  );
}
