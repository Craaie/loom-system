"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { 
  Card, 
  CardContent, 
  CardDescription, 
  CardHeader, 
  CardTitle 
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { 
  Book, 
  ArrowRight,
  FolderPlus,
  Sparkles,
  Trash2
} from "lucide-react";
import { loomApi } from "@/lib/api";
import { toast } from "sonner";
import { Project } from "@/types/project";
import { BatchProgress } from "@/components/batch-progress";

export default function Dashboard() {
  const router = useRouter();
  const [projects, setProjects] = useState<Project[]>([]);
  const [activeThreads, setActiveThreads] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      loomApi.listProjects(),
      loomApi.listActiveJobs()
    ]).then(([pts, { active_threads }]) => {
      setProjects(pts);
      setActiveThreads(active_threads);
    }).catch(e => {
      console.error(e);
      toast.error("加载数据失败");
    }).finally(() => setIsLoading(false));
  }, []);

  const handleDeleteProject = async (id: string, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (window.confirm("确定要删除该项目吗？此操作将永久删除项目下的所有内容。")) {
      try {
        await loomApi.deleteProject(id);
        setProjects(prev => prev.filter(p => p.id !== id));
        toast.success("项目已删除");
      } catch (err) {
        toast.error("删除失败");
      }
    }
  };

  return (
    <div className="max-w-6xl mx-auto p-8 space-y-10 animate-in fade-in slide-in-from-bottom-4">
      <div className="flex justify-between items-end">
        <div className="space-y-1">
          <h1 className="text-3xl font-bold">我的项目库</h1>
          <p className="text-muted-foreground">管理你的小说宇宙与分镜资产</p>
        </div>
        <Button onClick={() => router.push("/projects/new")} className="gap-2 shadow-lg shadow-primary/20">
          <FolderPlus className="w-4 h-4" />
          创建新项目
        </Button>
      </div>

      {activeThreads.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-primary animate-pulse" />
            正在进行的任务...
          </h2>
          <div className="grid gap-4 md:grid-cols-2">
            {activeThreads.map(tid => (
              <BatchProgress key={tid} threadId={tid} />
            ))}
          </div>
        </div>
      )}

      {isLoading ? (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map(i => (
            <Card key={i} className="animate-pulse bg-muted h-[200px]" />
          ))}
        </div>
      ) : projects.length === 0 ? (
        <Card className="border-dashed border-2 bg-muted/20 py-20">
          <CardContent className="flex flex-col items-center justify-center text-center space-y-4">
            <div className="bg-primary/10 p-4 rounded-full">
              <Book className="w-10 h-10 text-primary" />
            </div>
            <div className="space-y-2">
              <h3 className="text-xl font-semibold">还没有项目？</h3>
              <p className="text-muted-foreground max-w-sm">
                创建一个项目来开始你的创作之旅。你可以为一个项目添加多部小说或剧本。
              </p>
            </div>
            <Link href="/projects/new">
              <Button variant="outline" size="lg">立即创建</Button>
            </Link>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {projects.map((project) => (
            <Card key={project.id} className="group hover:border-primary/50 transition-all cursor-pointer shadow-md" onClick={() => router.push(`/projects/${project.id}`)}>
              <CardHeader>
                    <CardTitle className="flex justify-between items-start">
                      <span className="truncate">{project.name}</span>
                      <Button 
                        variant="ghost" 
                        size="icon" 
                        className="text-muted-foreground hover:text-destructive transition-colors -mt-1 -mr-1"
                        onClick={(e) => handleDeleteProject(project.id, e)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </CardTitle>
                <CardDescription className="line-clamp-2">{project.description || "暂无描述"}</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-4 text-xs text-muted-foreground">
                  <div className="flex items-center gap-1">
                    <Book className="w-3 h-3" />
                    2 部作品
                  </div>
                  <span>·</span>
                  <span>创建于 {new Date().toLocaleDateString()}</span>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
