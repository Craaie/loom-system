"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { 
  CirclePlus, 
  History, 
  Settings, 
  LayoutDashboard, 
  Video,
  ChevronRight,
  ChevronDown,
  BookOpen,
  FolderOpen
} from "lucide-react";
import { useEffect, useState } from "react";
import { loomApi } from "@/lib/api";
import { Project, Novel } from "@/types/project";

const sidebarNavItems = [
  {
    title: "仪表盘",
    href: "/",
    icon: LayoutDashboard,
  },
  {
    title: "视频库",
    href: "/video",
    icon: Video,
  },
  {
    title: "设置",
    href: "/settings",
    icon: Settings,
  },
];

export function Sidebar() {
  const pathname = usePathname();
  const [projects, setProjects] = useState<Project[]>([]);
  const [expandedProjects, setExpandedProjects] = useState<Record<string, boolean>>({});

  useEffect(() => {
    // 初始加载项目列表
    loomApi.listProjects().then(async (pts) => {
      // 对每个项目并发获取其小说
      const enriched: Project[] = await Promise.all(pts.map(async p => {
        const novels = await loomApi.listNovels(p.id);
        return { ...p, novels: novels as Novel[] };
      }));
      setProjects(enriched);
    }).catch(console.error);
  }, []);

  const toggleProject = (id: string) => {
    setExpandedProjects(prev => ({ ...prev, [id]: !prev[id] }));
  };

  return (
    <div className="flex flex-col h-full border-r bg-muted/40">
      <div className="p-6">
        <div className="flex items-center gap-2 font-bold text-xl tracking-tight">
          <div className="bg-primary text-primary-foreground p-1 rounded">织</div>
          <span>织影 Loom 2.0</span>
        </div>
      </div>
      
      <div className="px-4 mb-4">
        <Link href="/">
          <Button className="w-full justify-start gap-2" variant="default">
            <CirclePlus className="w-4 h-4" />
            新建创作
          </Button>
        </Link>
      </div>

      <ScrollArea className="flex-1 px-4">
        <div className="space-y-4">
          <div className="py-2">
            <h2 className="mb-2 px-2 text-xs font-semibold tracking-tight text-muted-foreground uppercase">
              主要导航
            </h2>
            <nav className="flex flex-col gap-1">
              {sidebarNavItems.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-all hover:bg-accent",
                    pathname === item.href ? "bg-accent text-accent-foreground" : "text-muted-foreground"
                  )}
                >
                  <item.icon className="h-4 w-4" />
                  {item.title}
                </Link>
              ))}
            </nav>
          </div>

          <div className="py-2">
            <h2 className="mb-2 px-2 text-xs font-semibold tracking-tight text-muted-foreground uppercase">
              项目库
            </h2>
            <nav className="flex flex-col gap-1">
              {projects.length === 0 ? (
                <div className="px-3 py-2 text-xs text-muted-foreground italic">暂无项目</div>
              ) : (
                projects.map((project) => (
                  <div key={project.id} className="space-y-1">
                    <button
                      onClick={() => toggleProject(project.id)}
                      className={cn(
                        "w-full flex items-center justify-between rounded-lg px-3 py-2 text-sm font-medium transition-all hover:bg-accent text-muted-foreground"
                      )}
                    >
                      <div className="flex items-center gap-2">
                        <FolderOpen className="h-4 w-4" />
                        <span className="truncate">{project.name}</span>
                      </div>
                      {expandedProjects[project.id] ? (
                        <ChevronDown className="h-3 w-3" />
                      ) : (
                        <ChevronRight className="h-3 w-3" />
                      )}
                    </button>
                    
                    {expandedProjects[project.id] && project.novels && (
                      <div className="ml-4 pl-2 border-l space-y-1">
                        {project.novels.map((novel) => (
                          <Link
                            key={novel.id}
                            href={`/novels/${novel.id}`}
                            className={cn(
                              "flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-medium transition-all hover:bg-accent truncate",
                              pathname.includes(novel.id) ? "bg-accent text-accent-foreground" : "text-muted-foreground"
                            )}
                          >
                            <BookOpen className="h-3 w-3 flex-shrink-0" />
                            <span className="truncate">{novel.title}</span>
                          </Link>
                        ))}
                      </div>
                    )}
                  </div>
                ))
              )}
            </nav>
          </div>
        </div>
      </ScrollArea>
      
      <div className="mt-auto p-4 border-t">
        <div className="flex items-center gap-3 px-3 py-2 text-sm text-muted-foreground">
          <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
          API 服务已连接
        </div>
      </div>
    </div>
  );
}
