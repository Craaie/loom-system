"use client";

import { useEffect, useState } from "react";
import { 
  Card, 
  CardContent, 
  CardDescription, 
  CardHeader, 
  CardTitle 
} from "@/components/ui/card";
import { 
  Video, 
  Film, 
  Download, 
  ExternalLink,
  PlayCircle,
  Trash2,
  CheckSquare,
  Square
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { loomApi } from "@/lib/api";
import { toast } from "sonner";

interface VideoTask {
  task_id: string;
  status: string;
  video_path: string;
  error?: string;
}

export default function VideoLibrary() {
  const [threads, setThreads] = useState<string[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [isLoading, setIsLoading] = useState(true);
  const [isDeleting, setIsDeleting] = useState(false);

  const fetchThreads = async () => {
    try {
      setIsLoading(true);
      const data = await loomApi.listThreads();
      setThreads(data);
    } catch (error) {
      console.error("Failed to fetch threads:", error);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchThreads();
  }, []);

  const toggleSelect = (id: string) => {
    const next = new Set(selectedIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelectedIds(next);
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === threads.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(threads));
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("确定要删除这个视频任务吗？")) return;
    try {
      setIsDeleting(true);
      await loomApi.deleteThread(id);
      toast.success("删除成功");
      setThreads(prev => prev.filter(t => t !== id));
      const nextSelected = new Set(selectedIds);
      nextSelected.delete(id);
      setSelectedIds(nextSelected);
    } catch (e) {
      toast.error("删除失败");
    } finally {
      setIsDeleting(false);
    }
  };

  const handleBatchDelete = async () => {
    if (selectedIds.size === 0) return;
    if (!confirm(`确定要删除选中的 ${selectedIds.size} 个任务吗？`)) return;

    try {
      setIsDeleting(true);
      await loomApi.batchDeleteThreads(Array.from(selectedIds));
      toast.success("批量删除成功");
      setThreads(prev => prev.filter(t => !selectedIds.has(t)));
      setSelectedIds(new Set());
    } catch (e) {
      toast.error("批量删除失败");
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto space-y-8 animate-in fade-in duration-500">
      <header className="flex items-center justify-between">
        <div className="space-y-1">
          <h1 className="text-3xl font-bold tracking-tight">视频库</h1>
          <p className="text-muted-foreground">管理你创作的所有 AI 视频作品</p>
        </div>
        <div className="flex gap-2">
          {selectedIds.size > 0 && (
            <Button 
              variant="destructive" 
              className="gap-2 animate-in zoom-in duration-200"
              onClick={handleBatchDelete}
              disabled={isDeleting}
            >
              <Trash2 className="w-4 h-4" />
              批量删除 ({selectedIds.size})
            </Button>
          )}
          <Button variant="outline" className="gap-2" onClick={toggleSelectAll}>
            {selectedIds.size === threads.length && threads.length > 0 ? (
              <CheckSquare className="w-4 h-4" />
            ) : (
              <Square className="w-4 h-4" />
            )}
            {selectedIds.size === threads.length && threads.length > 0 ? "取消全选" : "全选"}
          </Button>
          <Button variant="outline" className="gap-2">
            <Download className="w-4 h-4" />
            全量导出
          </Button>
        </div>
      </header>

      {isLoading ? (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-64 bg-muted animate-pulse rounded-xl" />
          ))}
        </div>
      ) : threads.length === 0 ? (
        <Card className="border-dashed py-20 text-center">
          <CardContent className="space-y-4">
            <div className="mx-auto w-12 h-12 rounded-full bg-muted flex items-center justify-center">
              <Film className="w-6 h-6 text-muted-foreground" />
            </div>
            <div className="space-y-2">
              <p className="text-xl font-medium">还没有创作？</p>
              <p className="text-muted-foreground">去仪表盘开启你的第一个小说视频化任务吧。</p>
            </div>
            <Button onClick={() => window.location.href = "/"}>开始创作</Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {threads.map((id) => (
            <Card key={id} className={`overflow-hidden hover:shadow-md transition-all relative ${selectedIds.has(id) ? 'ring-2 ring-primary border-primary/50 bg-primary/5' : ''}`}>
              <div 
                className="absolute top-2 left-2 z-10 cursor-pointer" 
                onClick={(e) => { e.stopPropagation(); toggleSelect(id); }}
              >
                {selectedIds.has(id) ? (
                  <CheckSquare className="w-5 h-5 text-primary fill-primary/10" />
                ) : (
                  <Square className="w-5 h-5 text-white/50 hover:text-white transition-colors" />
                )}
              </div>
              <div className="aspect-video bg-muted relative group cursor-pointer" onClick={() => toggleSelect(id)}>
                <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity bg-black/40">
                  <PlayCircle className="w-12 h-12 text-white" />
                </div>
                {/* 实际项目中这里应显示视频封面 */}
                <div className="absolute bottom-2 right-2 bg-black/60 text-white text-[10px] px-2 py-0.5 rounded">
                  00:15
                </div>
              </div>
              <CardHeader className="p-4">
                <CardTitle className="text-sm truncate">任务 ID: {id}</CardTitle>
                <CardDescription className="text-xs">创建于 2026-03-20</CardDescription>
              </CardHeader>
              <CardContent className="p-4 pt-0 flex justify-between gap-2">
                <Button variant="secondary" size="sm" className="flex-1 gap-1" onClick={() => window.location.href = `/jobs/${id}`}>
                  详情
                  <ExternalLink className="w-3 h-3" />
                </Button>
                <Button 
                  variant="ghost" 
                  size="sm" 
                  className="text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                  onClick={() => handleDelete(id)}
                  disabled={isDeleting}
                >
                  <Trash2 className="w-4 h-4" />
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
