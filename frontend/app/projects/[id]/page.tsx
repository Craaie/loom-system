"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { 
  Card, 
  CardContent, 
  CardDescription, 
  CardHeader, 
  CardTitle 
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { loomApi } from "@/lib/api";
import { Project, Novel } from "@/types/project";
import { toast } from "sonner";
import { BookPlus, ArrowLeft, BookOpen, Clock, Trash2, Hash, FileText } from "lucide-react";
import Link from "next/link";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function ProjectDetailPage() {
  const { id } = useParams();
  const router = useRouter();
  const [project, setProject] = useState<Project | null>(null);
  const [novels, setNovels] = useState<Novel[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [stats, setStats] = useState<{novel_count: number, chapter_count: number, total_words: number} | null>(null);
  const [isAddNovelOpen, setIsAddNovelOpen] = useState(false);
  const [newNovelTitle, setNewNovelTitle] = useState("");
  const [newNovelAuthor, setNewNovelAuthor] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (!id) return;
    
    Promise.all([
      loomApi.listProjects().then(pts => pts.find(p => p.id === id) || null),
      loomApi.listNovels(id as string),
      loomApi.getProjectStats(id as string)
    ]).then(([p, ns, s]) => {
      setProject(p);
      setNovels(ns);
      setStats(s);
    }).catch(e => {
      console.error(e);
      toast.error("加载项目详情失败");
    }).finally(() => setIsLoading(false));
  }, [id]);

  const handleDeleteNovel = async (novelId: string, title: string, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (window.confirm(`确定要删除小说 "${title}" 吗？此操作不可恢复。`)) {
      try {
        await loomApi.deleteNovel(novelId);
        setNovels(prev => prev.filter(n => n.id !== novelId));
        toast.success("小说已删除");
      } catch (err) {
        toast.error("删除失败");
      }
    }
  };

  const handleDeleteProject = async () => {
    if (window.confirm(`确定要彻底删除项目 "${project?.name}" 及其所有关联作品吗？`)) {
      try {
        await loomApi.deleteProject(id as string);
        toast.success("项目及其关联内容已成功删除");
        router.push("/");
      } catch (err) {
        toast.error("项目删除失败");
      }
    }
  };

  const handleAddNovel = async () => {
    if (!newNovelTitle.trim()) {
      toast.error("请输入小说标题");
      return;
    }
    setIsSubmitting(true);
    try {
      await loomApi.createNovel({
        project_id: id as string,
        title: newNovelTitle,
        author: newNovelAuthor
      });
      toast.success("小说创建成功");
      setIsAddNovelOpen(false);
      setNewNovelTitle("");
      setNewNovelAuthor("");
      // 刷新列表与统计
      const [ns, s] = await Promise.all([
        loomApi.listNovels(id as string),
        loomApi.getProjectStats(id as string)
      ]);
      setNovels(ns);
      setStats(s);
    } catch (err) {
      toast.error("创建失败");
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoading) return <div className="p-8 animate-pulse text-center">加载中...</div>;
  if (!project) return <div className="p-8 text-center text-destructive underline">项目不存在</div>;

  return (
    <div className="max-w-6xl mx-auto p-8 space-y-8 animate-in fade-in slide-in-from-bottom-4">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => router.push("/")}>
          <ArrowLeft className="w-5 h-5" />
        </Button>
        <div className="flex-1 space-y-1">
          <div className="flex justify-between items-start">
            <h1 className="text-3xl font-bold">{project.name}</h1>
            <Button variant="outline" size="sm" className="text-destructive border-destructive hover:bg-destructive hover:text-white" onClick={handleDeleteProject}>
              <Trash2 className="w-4 h-4 mr-2" />
              删除项目
            </Button>
          </div>
          <p className="text-muted-foreground">{project.description || "暂无描述"}</p>
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-4">
        <div className="md:col-span-3 space-y-6">
          <div className="flex justify-between items-center">
            <h2 className="text-xl font-semibold">包含的作品 ({novels.length})</h2>
            <Button size="sm" className="gap-2" onClick={() => setIsAddNovelOpen(true)}>
              <BookPlus className="w-4 h-4" />
              添加新小说
            </Button>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            {novels.length === 0 ? (
              <div className="col-span-full py-20 text-center border-2 border-dashed rounded-xl text-muted-foreground">
                该项目下暂无作品
              </div>
            ) : (
              novels.map(novel => (
                <Card 
                  key={novel.id} 
                  className="group hover:border-primary/50 transition-all cursor-pointer"
                  onClick={() => router.push(`/novels/${novel.id}`)}
                >
                  <CardHeader className="pb-2">
                    <CardTitle className="text-lg flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <BookOpen className="w-4 h-4 text-primary" />
                        {novel.title}
                      </div>
                      <Button 
                        variant="ghost" 
                        size="icon" 
                        className="h-8 w-8 text-muted-foreground hover:text-destructive"
                        onClick={(e) => handleDeleteNovel(novel.id, novel.title, e)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </CardTitle>
                    <CardDescription>作者: {novel.author || "佚名"}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="flex items-center gap-3 text-xs text-muted-foreground">
                      <div className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        最近更新: 2小时前
                      </div>
                      <span>·</span>
                      <span>3 卷</span>
                    </div>
                  </CardContent>
                </Card>
              ))
            )}
          </div>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">项目概览</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">创建时间</span>
                <span>{project.created_at ? new Date(project.created_at).toLocaleDateString() : "2024-03-20"}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">作品总数</span>
                <span className="flex items-center gap-1">
                  <BookOpen className="w-3 h-3" />
                  {stats?.novel_count || novels.length}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">章节总数</span>
                <span className="flex items-center gap-1">
                  <Hash className="w-3 h-3" />
                  {stats?.chapter_count || 0}
                </span>
              </div>
              <div className="flex justify-between border-t pt-2">
                <span className="text-muted-foreground font-semibold">估算总字数</span>
                <span className="text-primary font-bold">
                  {(stats?.total_words || 0).toLocaleString()} 字
                </span>
              </div>
              <Button variant="outline" className="w-full text-xs h-7">编辑项目信息</Button>
            </CardContent>
          </Card>
        </div>
      </div>

      <Dialog open={isAddNovelOpen} onOpenChange={setIsAddNovelOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>添加新小说</DialogTitle>
            <DialogDescription>
              在当前项目中创建一个新的小说作品。
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid grid-cols-4 items-center gap-4">
              <Label htmlFor="title" className="text-right">标题</Label>
              <Input 
                id="title" 
                value={newNovelTitle} 
                onChange={(e) => setNewNovelTitle(e.target.value)}
                placeholder="例如：仙剑奇侠传"
                className="col-span-3" 
              />
            </div>
            <div className="grid grid-cols-4 items-center gap-4">
              <Label htmlFor="author" className="text-right">作者</Label>
              <Input 
                id="author" 
                value={newNovelAuthor} 
                onChange={(e) => setNewNovelAuthor(e.target.value)}
                placeholder="佚名"
                className="col-span-3" 
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsAddNovelOpen(false)}>取消</Button>
            <Button onClick={handleAddNovel} disabled={isSubmitting}>
              {isSubmitting ? "正在创建..." : "确认创建"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
