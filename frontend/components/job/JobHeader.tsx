"use client";

import { useRouter } from "next/navigation";
import { Separator } from "@/components/ui/separator";
import { Button } from "@/components/ui/button";
import { Moon, Sun, History, Settings2, Zap } from "lucide-react";
import { useTheme } from "next-themes";

interface JobHeaderProps {
  jobId: string;
}

export default function JobHeader({ jobId }: JobHeaderProps) {
  const router = useRouter();
  const { theme, setTheme } = useTheme();

  return (
    <header className="h-14 border-b border-white/5 bg-background/40 backdrop-blur-xl flex items-center justify-between px-6 shrink-0 z-50">
      <div className="flex items-center gap-4">
        {/* ... (Logo parts) */}
        <div
          className="flex items-center gap-2 group cursor-pointer"
          onClick={() => router.push("/")}
        >
          <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-primary to-primary/60 flex items-center justify-center shadow-lg shadow-primary/20">
            <Zap className="h-4 w-4 text-white" />
          </div>
          <span className="font-bold tracking-tight text-foreground/90">
            Loom Studio
          </span>
        </div>
        <Separator orientation="vertical" className="h-4 bg-border" />
        <div className="flex items-center gap-2 text-xs font-mono text-muted-foreground">
          <span className="bg-muted px-2 py-0.5 rounded">
            JOB-{jobId.substring(0, 8)}
          </span>
          <span className="flex items-center gap-1.5">
            <History className="h-3 w-3" /> v3.0.4
          </span>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          className="rounded-full w-9 h-9 text-muted-foreground hover:text-foreground"
        >
          <Sun className="h-[1.2rem] w-[1.2rem] rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
          <Moon className="absolute h-[1.2rem] w-[1.2rem] rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
          <span className="sr-only">切换主题</span>
        </Button>

        <Button
          variant="ghost"
          size="sm"
          className="text-muted-foreground hover:text-foreground hover:bg-accent rounded-full px-4 text-xs"
        >
          <Settings2 className="h-3.5 w-3.5 mr-2" />
          设置
        </Button>
        <Button
          size="sm"
          className="rounded-full px-5 text-xs font-bold shadow-lg shadow-primary/10"
        >
          完成导出
        </Button>
      </div>
    </header>
  );
}
