"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { loomApi } from "@/lib/api";
import { getWorkbenchSnapshot } from "@/lib/workbench";
import { Novel, Volume } from "@/types/project";
import { toast } from "sonner";
import { BatchProgress } from "@/components/batch-progress";
import { useJobState } from "@/hooks/useJobState";
import { useJobActions } from "@/hooks/useJobActions";
import { WorkflowStatus } from "@/components/project/WorkflowStatus";
import { AssetLibrary } from "@/components/project/AssetLibrary";
import SceneEditor from "@/components/job/SceneEditor";
import { CharacterArchive } from "@/components/job/CharacterArchive";
import ExecutionTrace from "@/components/job/ExecutionTrace";
import { WorkflowOverview } from "@/components/workbench/WorkflowOverview";
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  Clock,
  FileText,
  Layers,
  Play,
  Plus,
  Sparkles,
  Trash2,
  Upload,
  Wand2,
} from "lucide-react";

type WorkspaceTab = "overview" | "storyboards" | "library" | "logs";

export default function NovelDetailPage() {
  const { id } = useParams();
  const router = useRouter();
  const [novel, setNovel] = useState<Novel | null>(null);
  const [volumes, setVolumes] = useState<Volume[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [activeVolume, setActiveVolume] = useState<Volume | null>(null);
  const [novelContent, setNovelContent] = useState("");
  const [isWeaving, setIsWeaving] = useState(false);
  const [currentThreadId, setCurrentThreadId] = useState<string | null>(null);
  const [analysisPrompt, setAnalysisPrompt] = useState("");
  const [costLimit, setCostLimit] = useState(10);
  const [workspaceTab, setWorkspaceTab] = useState<WorkspaceTab>("overview");

  const { activeNode, isPendingApproval, imageTasks, audioTasks, storyboards, state, logs, isStreaming, executionError, finalVideoUrl, cost, budget } = useJobState(currentThreadId || "");
  const actions = useJobActions(currentThreadId || "");
  const [selectedProvider, setSelectedProvider] = useState("google");
  const [selectedModel, setSelectedModel] = useState("gemini-2.5-flash");
  const [selectedImageProvider, setSelectedImageProvider] = useState("wanx");
  const [selectedTTSProvider, setSelectedTTSProvider] = useState("dashscope");
  const [selectedVideoProvider, setSelectedVideoProvider] = useState("hailuo");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [isAddVolumeOpen, setIsAddVolumeOpen] = useState(false);
  const [newVolumeTitle, setNewVolumeTitle] = useState("");
  const [isSubmittingVolume, setIsSubmittingVolume] = useState(false);

  useEffect(() => {
    if (!id) return;

    const fetchData = async () => {
      try {
        const novelResponse = (await loomApi.getNovel(id as string)) as Novel & {
          detail?: string;
          error?: unknown;
        };
        if (novelResponse.detail === "Novel not found" || novelResponse.error) {
          setNovel(null);
        } else {
          setNovel(novelResponse);
        }

        const vs = await loomApi.listVolumes(id as string);
        setVolumes(vs);
        if (vs.length > 0) {
          setActiveVolume(vs[0]);
          if (vs[0].latest_thread_id) {
            setCurrentThreadId(vs[0].latest_thread_id);
          }
        }
      } catch (err) {
        console.error(err);
        setNovel(null);
      } finally {
        setIsLoading(false);
      }
    };

    const fetchSettings = async () => {
      try {
        const settings = await loomApi.getSettings();
        if (settings) {
          setSelectedProvider(settings.default_llm_provider || "dashscope");
          setSelectedModel(settings.default_llm_model || "qwen-plus");
          setSelectedImageProvider(settings.image_provider || "wanx");
          setSelectedTTSProvider(settings.tts_provider || "dashscope");
          setSelectedVideoProvider(settings.video_provider || "hailuo");
        }
      } catch (err) {
        console.error("Failed to load settings:", err);
      }
    };

    fetchData();
    fetchSettings();
  }, [id]);

  useEffect(() => {
    if (activeVolume?.latest_thread_id && !isWeaving) {
      setCurrentThreadId(activeVolume.latest_thread_id);
    }
  }, [activeVolume, isWeaving]);

  const snapshot = useMemo(
    () =>
      getWorkbenchSnapshot({
        threadId: currentThreadId,
        activeNode,
        isPendingApproval,
        isStreaming,
        executionError,
        finalVideoUrl,
        storyboardCount: storyboards.length,
        imageTotal: imageTasks.length,
        imageDone: imageTasks.filter((task) => task.status === "done").length,
        audioTotal: audioTasks.length,
        audioDone: audioTasks.filter((task) => task.status === "done").length,
        budget,
        cost,
      }),
    [activeNode, audioTasks, budget, cost, currentThreadId, executionError, finalVideoUrl, imageTasks, isPendingApproval, isStreaming, storyboards.length]
  );

  useEffect(() => {
    if (!currentThreadId) {
      setWorkspaceTab("overview");
      return;
    }

    if (snapshot.summary.focusTarget === "storyboard") {
      setWorkspaceTab("storyboards");
      return;
    }
    if (snapshot.summary.focusTarget === "logs") {
      setWorkspaceTab("logs");
      return;
    }
    if (snapshot.summary.focusTarget === "assets") {
      setWorkspaceTab("library");
      return;
    }
    setWorkspaceTab("overview");
  }, [currentThreadId, snapshot.summary.focusTarget]);

  const handleStartWeaving = async () => {
    if (!activeVolume) return;

    setIsWeaving(true);
    try {
      let thread_id;

      if (novelContent.trim()) {
        const file = new File([novelContent], "pasted_content.txt", { type: "text/plain" });
        const formData = new FormData();
        formData.append("file", file);
        formData.append("novel_id", id as string);
        formData.append("volume_id", activeVolume.id);
        formData.append("title", activeVolume.title);
        const res = await loomApi.uploadNovel(formData, selectedProvider, selectedModel, analysisPrompt, selectedImageProvider, selectedTTSProvider, selectedVideoProvider, costLimit);
        thread_id = res.thread_id;
        toast.success(`文本已提交分析 (${selectedModel})`);
      } else if (selectedFile) {
        const formData = new FormData();
        formData.append("file", selectedFile);
        formData.append("novel_id", id as string);
        formData.append("volume_id", activeVolume.id);
        formData.append("title", activeVolume.title);
        const res = await loomApi.uploadNovel(formData, selectedProvider, selectedModel, analysisPrompt, selectedImageProvider, selectedTTSProvider, selectedVideoProvider, costLimit);
        thread_id = res.thread_id;
        toast.success(`文件 ${selectedFile.name} 已开始分析 (${selectedModel})`);
      } else if (activeVolume.file_path) {
        const res = await loomApi.startVolumeAnalysis(activeVolume.id, selectedProvider, selectedModel, analysisPrompt, selectedImageProvider, selectedTTSProvider, selectedVideoProvider, costLimit);
        thread_id = res.thread_id;
        toast.success(`正在重新分析现有文件 (${selectedModel})`);
      } else {
        toast.error("请输入文本内容或选择文件并启动分析");
        setIsWeaving(false);
        return;
      }

      setCurrentThreadId(thread_id);
      setWorkspaceTab("overview");
    } catch (error) {
      console.error(error);
      toast.error("分析启动失败");
    } finally {
      setIsWeaving(false);
      setSelectedFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleDeleteNovel = async () => {
    if (window.confirm(`确定要删除小说 "${novel?.title}" 吗？此操作将物理删除其下的所有卷次和章节内容。`)) {
      try {
        await loomApi.deleteNovel(id as string);
        toast.success("小说已成功删除");
        router.push(`/projects/${novel?.project_id}`);
      } catch {
        toast.error("小说删除失败");
      }
    }
  };

  const handleDeleteVolume = async (vId: string, vTitle: string, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (window.confirm(`确定要删除卷次 "${vTitle}" 吗？其下所属的章节内容将一并删除。`)) {
      try {
        await loomApi.deleteVolume(vId);
        setVolumes((prev) => prev.filter((v) => v.id !== vId));
        if (activeVolume?.id === vId) setActiveVolume(null);
        toast.success("卷次已删除");
      } catch {
        toast.error("卷次删除失败");
      }
    }
  };

  const handleAddVolume = async () => {
    if (!newVolumeTitle.trim()) {
      toast.error("请输入卷次名称");
      return;
    }

    setIsSubmittingVolume(true);
    try {
      const volume = (await loomApi.createVolume({
        novel_id: id as string,
        title: newVolumeTitle,
        index: volumes.length,
      })) as Volume;
      setVolumes((prev) => [...prev, volume]);
      setNewVolumeTitle("");
      setIsAddVolumeOpen(false);
      toast.success("卷次添加成功");
      if (!activeVolume) setActiveVolume(volume);
    } catch {
      toast.error("添加卷次失败");
    } finally {
      setIsSubmittingVolume(false);
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !activeVolume) return;

    if (!file.name.endsWith(".txt")) {
      toast.error("仅支持 .txt 文件");
      if (fileInputRef.current) fileInputRef.current.value = "";
      return;
    }

    setSelectedFile(file);
    toast.info(`已选中文件: ${file.name}，点击“开始分析文稿”即可启动`);
  };

  if (isLoading) return <div className="p-8 text-center animate-pulse">加载中...</div>;

  if (!novel)
    return (
      <div className="flex flex-col items-center justify-center space-y-4 p-20">
        <AlertCircle className="h-12 w-12 text-destructive opacity-30" />
        <div className="text-xl font-medium text-destructive">作品不存在或加载中</div>
        <Button variant="outline" onClick={() => router.push("/")}>返回项目库</Button>
      </div>
    );

  const canStartWeaving = !!activeVolume && (!!novelContent.trim() || !!selectedFile || !!activeVolume.file_path);

  const handleOverviewAction = () => {
    switch (snapshot.summary.focusTarget) {
      case "storyboard":
        setWorkspaceTab("storyboards");
        break;
      case "assets":
        setWorkspaceTab("library");
        break;
      case "logs":
        setWorkspaceTab("logs");
        break;
      case "video":
        if (currentThreadId) router.push(`/jobs/${currentThreadId}`);
        break;
      case "input":
      default:
        document.getElementById("content-composer")?.scrollIntoView({ behavior: "smooth", block: "start" });
        break;
    }
  };

  return (
    <div className="mx-auto flex max-w-[1600px] flex-col gap-6 px-4 py-6 lg:px-6">
      <div className="flex flex-col gap-4 rounded-3xl border border-border/60 bg-card/70 p-5 shadow-sm lg:flex-row lg:items-start lg:justify-between">
        <div className="flex items-start gap-4">
          <Button variant="ghost" size="icon" className="mt-0.5 rounded-full" onClick={() => router.push(`/projects/${novel.project_id}`)}>
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-3xl font-bold tracking-tight">{novel.title}</h1>
              <Badge variant="outline" className="rounded-full px-3 py-1 text-xs">
                {volumes.length} 卷
              </Badge>
            </div>
            <p className="text-muted-foreground">作者：{novel.author || "佚名"}</p>
            <p className="max-w-2xl text-sm leading-6 text-muted-foreground">
              这里不再把流程拆成多个零散页面，而是围绕“输入内容 → 看进度 → 审分镜 → 出成片”组织整个创作工作台。
            </p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {currentThreadId && (
            <Button variant="outline" className="rounded-full px-5" onClick={() => router.push(`/jobs/${currentThreadId}`)}>
              打开专注任务台
              <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
          )}
          <Button variant="outline" size="sm" className="rounded-full border-destructive text-destructive hover:bg-destructive hover:text-white" onClick={handleDeleteNovel}>
            <Trash2 className="mr-2 h-4 w-4" />
            删除小说
          </Button>
        </div>
      </div>

      <WorkflowOverview
        title="创作流水线工作台"
        subtitle="让你始终知道流程走到哪一步：顶部给出阶段、建议下一步、预算与实体素材进度。"
        context={{
          threadId: currentThreadId,
          activeNode,
          isPendingApproval,
          isStreaming,
          executionError,
          finalVideoUrl,
          storyboardCount: storyboards.length,
          imageTotal: imageTasks.length,
          imageDone: imageTasks.filter((task) => task.status === "done").length,
          audioTotal: audioTasks.length,
          audioDone: audioTasks.filter((task) => task.status === "done").length,
          budget,
          cost,
        }}
        onPrimaryAction={handleOverviewAction}
        secondaryActionLabel={currentThreadId ? "打开专注任务台" : undefined}
        onSecondaryAction={currentThreadId ? () => router.push(`/jobs/${currentThreadId}`) : undefined}
      />

      <div className="grid gap-6 xl:grid-cols-[280px_minmax(0,1fr)_320px]">
        <section className="space-y-4">
          <Card className="border-border/60 bg-card/70 shadow-sm">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-3">
              <div>
                <CardTitle className="text-base">卷次导航</CardTitle>
                <CardDescription>先选一个卷，再启动或续跑任务</CardDescription>
              </div>
              <Button variant="ghost" size="icon" className="h-8 w-8 rounded-full" onClick={() => setIsAddVolumeOpen(true)}>
                <Plus className="h-4 w-4" />
              </Button>
            </CardHeader>
            <CardContent className="space-y-2">
              {volumes.length > 0 ? (
                volumes.map((v) => (
                  <div
                    key={v.id}
                    role="button"
                    tabIndex={0}
                    onClick={() => setActiveVolume(v)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        setActiveVolume(v);
                      }
                    }}
                    className={cn(
                      "group flex w-full items-center justify-between rounded-2xl border px-3 py-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary",
                      activeVolume?.id === v.id ? "border-primary/30 bg-primary/[0.08]" : "border-border/60 bg-background/80 hover:border-primary/20"
                    )}
                  >
                    <div className="min-w-0">
                      <div className="truncate text-sm font-semibold">{v.title}</div>
                      <div className="mt-1 flex flex-wrap gap-2 text-xs text-muted-foreground">
                        {v.latest_thread_id ? <span>有历史任务</span> : <span>尚未运行</span>}
                        {v.file_path && <span>已绑定文件</span>}
                      </div>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 rounded-full text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100 hover:text-destructive"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDeleteVolume(v.id, v.title, e);
                      }}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                ))
              ) : (
                <div className="rounded-2xl border border-dashed border-border px-4 py-10 text-center text-sm text-muted-foreground">
                  还没有卷次，先创建一个。
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="border-border/60 bg-card/70 shadow-sm">
            <CardHeader className="pb-3">
              <CardTitle className="text-base">工作台原则</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm text-muted-foreground">
              <div className="rounded-2xl border border-border/60 bg-background/80 p-3">
                1. 先跑一卷，确认风格后再扩大范围。
              </div>
              <div className="rounded-2xl border border-border/60 bg-background/80 p-3">
                2. 分镜一出来就审，避免素材阶段返工。
              </div>
              <div className="rounded-2xl border border-border/60 bg-background/80 p-3">
                3. 出错先断点恢复，不要一键全重跑。
              </div>
            </CardContent>
          </Card>
        </section>

        <section className="min-w-0 space-y-6">
          <Card id="content-composer" className="border-border/60 bg-card/70 shadow-sm">
            <CardHeader className="space-y-3 border-b border-border/60 pb-4">
              <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                <div>
                  <CardTitle className="flex items-center gap-2 text-xl">
                    <Wand2 className="h-5 w-5 text-primary" />
                    内容输入与启动区
                  </CardTitle>
                  <CardDescription className="mt-1">
                    一屏完成输入、上传和启动。高级模型设置折叠收纳，不干扰主流程。
                  </CardDescription>
                </div>
                {activeVolume && (
                  <Badge variant="outline" className="w-fit rounded-full px-3 py-1 text-xs">
                    当前卷：{activeVolume.title}
                  </Badge>
                )}
              </div>
            </CardHeader>
            <CardContent className="space-y-4 pt-5">
              <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_220px]">
                <div className="space-y-2">
                  <Label htmlFor="novel-content" className="text-sm font-semibold">文稿内容</Label>
                  <Textarea
                    id="novel-content"
                    placeholder="在此粘贴要分析的正文内容，建议按卷或按章节批次输入。"
                    className="min-h-[360px] resize-y bg-background/80 text-base leading-7"
                    value={novelContent}
                    onChange={(e) => setNovelContent(e.target.value)}
                  />
                </div>

                <div className="space-y-4">
                  <Card className="border-border/60 bg-background/80 shadow-none">
                    <CardContent className="space-y-3 p-4">
                      <div className="text-sm font-semibold">启动前检查</div>
                      <InfoRow label="输入方式" value={novelContent.trim() ? "粘贴文本" : selectedFile ? `文件：${selectedFile.name}` : activeVolume?.file_path ? "服务器已有文件" : "未准备"} />
                      <InfoRow label="预算上限" value={`$${costLimit.toFixed(1)}`} />
                      <InfoRow label="分析模型" value={selectedModel} />
                    </CardContent>
                  </Card>

                  <input type="file" ref={fileInputRef} className="hidden" accept=".txt" onChange={handleFileUpload} />
                  <Button variant="outline" className="w-full rounded-2xl" onClick={() => fileInputRef.current?.click()} disabled={isWeaving || !activeVolume}>
                    <Upload className="mr-2 h-4 w-4" />
                    {selectedFile ? `已选 ${selectedFile.name}` : "选择 TXT 文件"}
                  </Button>

                  <Button className="w-full rounded-2xl py-6 text-base" onClick={handleStartWeaving} disabled={isWeaving || !canStartWeaving}>
                    {isWeaving ? "正在提交任务..." : "开始分析文稿"}
                    <Play className="ml-2 h-4 w-4 fill-current" />
                  </Button>

                  <p className="text-xs leading-5 text-muted-foreground">
                    启动后不会自动跳页。你可以留在当前工作台持续看进度，也可以进入专注任务台处理细节。
                  </p>
                </div>
              </div>

              <details className="group rounded-2xl border border-border/60 bg-background/70 p-4">
                <summary className="cursor-pointer list-none text-sm font-semibold text-foreground">
                  <div className="flex items-center justify-between">
                    <span>高级设置</span>
                    <span className="text-xs text-muted-foreground group-open:hidden">展开</span>
                    <span className="hidden text-xs text-muted-foreground group-open:inline">收起</span>
                  </div>
                </summary>
                <div className="mt-4 grid gap-4 lg:grid-cols-2">
                  <SelectField
                    label="分析模型"
                    value={`${selectedProvider}:${selectedModel}`}
                    onChange={(value) => {
                      const parts = value.split(":");
                      setSelectedProvider(parts[0]);
                      setSelectedModel(parts.slice(1).join(":"));
                    }}
                    options={[
                      { value: "google:gemini-2.5-flash", label: "Gemini 2.5 Flash (推荐)" },
                      { value: "deepseek:deepseek-chat", label: "DeepSeek V3 (备选)" },
                      { value: "ollama:qwen3:4b", label: "Ollama: Qwen3 4B (本地)" },
                    ]}
                  />
                  <SelectField
                    label="图片提供商"
                    value={selectedImageProvider}
                    onChange={setSelectedImageProvider}
                    options={[
                      { value: "cogview", label: "CogView-4 (智谱)" },
                      { value: "wanx", label: "Wanx 2.5 (通义)" },
                      { value: "flux", label: "FLUX.1 [dev]" },
                      { value: "mock", label: "无 (Mock)" },
                    ]}
                  />
                  <SelectField
                    label="配音提供商"
                    value={selectedTTSProvider}
                    onChange={setSelectedTTSProvider}
                    options={[
                      { value: "dashscope", label: "CosyVoice (阿里通义)" },
                      { value: "fish", label: "Fish TTS" },
                      { value: "minimax_speech", label: "Speech-02 (MiniMax)" },
                      { value: "mock", label: "无 (Mock)" },
                    ]}
                  />
                  <SelectField
                    label="视频提供商"
                    value={selectedVideoProvider}
                    onChange={setSelectedVideoProvider}
                    options={[
                      { value: "hailuo", label: "Hailuo 2.3 (海螺)" },
                      { value: "seedance", label: "Seedance 2.0" },
                      { value: "kling", label: "Kling 2.0 (可灵)" },
                      { value: "mock", label: "无 (Mock)" },
                    ]}
                  />
                  <div className="space-y-2">
                    <Label htmlFor="cost-limit" className="text-sm font-semibold">单任务预算上限 (USD)</Label>
                    <Input
                      id="cost-limit"
                      type="number"
                      min={0.1}
                      step={0.1}
                      value={costLimit}
                      onChange={(e) => setCostLimit(Math.max(0.1, Number(e.target.value) || 0.1))}
                    />
                  </div>
                  <div className="space-y-2 lg:col-span-2">
                    <Label htmlFor="analysis-prompt" className="text-sm font-semibold">自定义剧情分析指令</Label>
                    <Textarea
                      id="analysis-prompt"
                      placeholder="例如：强调心理戏；风格偏黑暗悬疑；旁白保持简短有力。"
                      className="min-h-[96px] bg-background/80"
                      value={analysisPrompt}
                      onChange={(e) => setAnalysisPrompt(e.target.value)}
                    />
                  </div>
                </div>
              </details>
            </CardContent>
            <CardFooter className="flex flex-wrap items-center justify-between gap-3 border-t border-border/60 bg-muted/20 px-6 py-4 text-sm text-muted-foreground">
              <div className="flex items-center gap-2">
                <Clock className="h-4 w-4" />
                建议先用 1 卷验证流程，再扩大范围。
              </div>
              <div className="flex items-center gap-2 text-primary">
                <Sparkles className="h-4 w-4" />
                预算与阶段会实时回写到顶部工作台摘要
              </div>
            </CardFooter>
          </Card>

          <Card className="border-border/60 bg-card/70 shadow-sm">
            <CardContent className="p-4">
              <Tabs value={workspaceTab} onValueChange={(value) => setWorkspaceTab(value as WorkspaceTab)} className="gap-4">
                <TabsList className="h-auto w-full flex-wrap gap-2 rounded-2xl border border-border/60 bg-background/80 p-2">
                  <TabsTrigger value="overview" className="min-w-[140px] rounded-xl px-4 py-2.5 data-active:bg-primary/10 data-active:text-primary">
                    <Layers className="h-4 w-4" />
                    当前待办
                  </TabsTrigger>
                  <TabsTrigger value="storyboards" className="min-w-[140px] rounded-xl px-4 py-2.5 data-active:bg-primary/10 data-active:text-primary">
                    <Sparkles className="h-4 w-4" />
                    分镜审阅
                  </TabsTrigger>
                  <TabsTrigger value="library" className="min-w-[140px] rounded-xl px-4 py-2.5 data-active:bg-primary/10 data-active:text-primary">
                    <FileText className="h-4 w-4" />
                    角色与素材
                  </TabsTrigger>
                  <TabsTrigger value="logs" className="min-w-[140px] rounded-xl px-4 py-2.5 data-active:bg-primary/10 data-active:text-primary">
                    <Wand2 className="h-4 w-4" />
                    执行记录
                  </TabsTrigger>
                </TabsList>

                <TabsContent value="overview">
                  {currentThreadId ? (
                    <div className="space-y-4">
                      <div className="rounded-2xl border border-border/60 bg-background/80 p-4">
                        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                          <div>
                            <h2 className="text-lg font-semibold">当前任务总览</h2>
                            <p className="mt-1 text-sm text-muted-foreground">
                              这里专门回答三个问题：现在在哪一步、是否需要你处理、下一步应该做什么。
                            </p>
                          </div>
                          <div className="flex flex-wrap gap-2">
                            {currentThreadId && (
                              <Button variant="outline" className="rounded-full px-5" onClick={() => router.push(`/jobs/${currentThreadId}`)}>
                                打开专注任务台
                              </Button>
                            )}
                            {isPendingApproval && (
                              <Button className="rounded-full px-5" onClick={actions.approve} disabled={actions.isActing}>
                                批准并继续
                              </Button>
                            )}
                          </div>
                        </div>
                      </div>
                      <WorkflowStatus activeNode={activeNode} threadId={currentThreadId} isPendingApproval={isPendingApproval} />
                    </div>
                  ) : (
                    <EmptyWorkbenchState />
                  )}
                </TabsContent>

                <TabsContent value="storyboards">
                  {currentThreadId ? (
                    <SceneEditor
                      threadId={currentThreadId}
                      storyboards={storyboards}
                      finalVideoPath={finalVideoUrl}
                      onUpdateStoryboard={(newStoryboards) => actions.updateState({ storyboard_json: newStoryboards })}
                    />
                  ) : (
                    <EmptyWorkbenchState />
                  )}
                </TabsContent>

                <TabsContent value="library">
                  {currentThreadId ? (
                    <div className="space-y-4">
                      <CharacterArchive
                        registry={state?.values?.character_registry || {}}
                        onUpdateRegistry={(newReg) => actions.updateState({ character_registry: newReg })}
                      />
                      <AssetLibrary imageTasks={imageTasks} audioTasks={audioTasks} threadId={currentThreadId} />
                    </div>
                  ) : (
                    <EmptyWorkbenchState />
                  )}
                </TabsContent>

                <TabsContent value="logs">
                  {currentThreadId ? (
                    <div className="h-[680px] overflow-hidden rounded-2xl border border-border/60 bg-background/80">
                      <ExecutionTrace
                        activeNode={activeNode}
                        pipelineStatus={state?.values?.pipeline_status}
                        logs={logs}
                        isStreaming={isStreaming}
                      />
                    </div>
                  ) : (
                    <EmptyWorkbenchState />
                  )}
                </TabsContent>
              </Tabs>
            </CardContent>
          </Card>
        </section>

        <section className="space-y-4">
          <Card className="border-border/60 bg-card/70 shadow-sm">
            <CardHeader className="pb-3">
              <CardTitle className="text-base">任务脉搏</CardTitle>
              <CardDescription>这里给出最短路径：进度、风险、下一步。</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {currentThreadId ? (
                <>
                  <BatchProgress threadId={currentThreadId} />
                  <div className="rounded-2xl border border-border/60 bg-background/80 p-4 text-sm">
                    <div className="font-semibold">当前建议</div>
                    <p className="mt-2 leading-6 text-muted-foreground">{snapshot.summary.description}</p>
                    <div className="mt-3 grid gap-2">
                      <Button className="w-full rounded-xl" onClick={handleOverviewAction}>
                        {snapshot.summary.primaryActionLabel}
                      </Button>
                      {executionError && (
                        <Button variant="outline" className="w-full rounded-xl" onClick={actions.resume} disabled={actions.isActing}>
                          从断点恢复
                        </Button>
                      )}
                    </div>
                  </div>
                </>
              ) : (
                <div className="rounded-2xl border border-dashed border-border px-4 py-10 text-center text-sm text-muted-foreground">
                  启动一次任务后，这里会持续显示进度和建议下一步。
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="border-border/60 bg-card/70 shadow-sm">
            <CardHeader className="pb-3">
              <CardTitle className="text-base">当前卷摘要</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm text-muted-foreground">
              <InfoRow label="当前卷" value={activeVolume?.title || "未选择"} />
              <InfoRow label="最新线程" value={currentThreadId ? currentThreadId.slice(0, 10) : "尚未启动"} />
              <InfoRow label="分镜数量" value={`${storyboards.length}`} />
              <InfoRow label="图片素材" value={`${imageTasks.filter((task) => task.status === "done").length}/${imageTasks.length || 0}`} />
              <InfoRow label="配音素材" value={`${audioTasks.filter((task) => task.status === "done").length}/${audioTasks.length || 0}`} />
              <InfoRow label="预算使用" value={`$${cost.toFixed(2)} / $${budget.toFixed(2)}`} />
            </CardContent>
          </Card>
        </section>
      </div>

      <Dialog open={isAddVolumeOpen} onOpenChange={setIsAddVolumeOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>新建卷次</DialogTitle>
            <DialogDescription>
              为小说《{novel?.title}》创建一个新的卷次，例如“第一卷：起源”。
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="title">卷次名称</Label>
              <Input
                id="title"
                placeholder="请输入卷次名称"
                value={newVolumeTitle}
                onChange={(e) => setNewVolumeTitle(e.target.value)}
                autoFocus
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsAddVolumeOpen(false)}>取消</Button>
            <Button onClick={handleAddVolume} disabled={isSubmittingVolume}>
              {isSubmittingVolume ? "正在创建..." : "确认创建"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-3 rounded-2xl border border-border/60 bg-background/80 px-3 py-2.5">
      <span className="text-muted-foreground">{label}</span>
      <span className="text-right font-medium text-foreground">{value}</span>
    </div>
  );
}

function SelectField({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: Array<{ value: string; label: string }>;
}) {
  return (
    <div className="space-y-2">
      <Label className="text-sm font-semibold">{label}</Label>
      <select
        className="flex h-10 w-full rounded-xl border border-input bg-background px-3 text-sm outline-none ring-offset-background transition-colors focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  );
}

function EmptyWorkbenchState() {
  return (
    <div className="flex min-h-[420px] flex-col items-center justify-center gap-4 rounded-2xl border border-dashed border-border bg-background/80 text-center">
      <CheckCircle2 className="h-10 w-10 text-muted-foreground/30" />
      <div className="space-y-1">
        <div className="text-lg font-semibold">先启动一条流水线</div>
        <p className="max-w-md text-sm leading-6 text-muted-foreground">
          提交文本后，这里会自动切换成可持续使用的工作台，而不是让你在多个零散页面之间来回跳。
        </p>
      </div>
    </div>
  );
}
