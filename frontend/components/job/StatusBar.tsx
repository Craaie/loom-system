"use client";

import { cn } from "@/lib/utils";
import { Separator } from "@/components/ui/separator";
import { Info } from "lucide-react";

interface StatusBarProps {
  isStreaming: boolean;
  lastEventTime: number;
}

export default function StatusBar({ isStreaming, lastEventTime }: StatusBarProps) {
  return (
    <footer className="h-8 border-t border-border bg-background px-6 flex items-center justify-between shrink-0 text-[10px] font-mono tracking-wider">
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-2">
          <div
            className={cn(
              "h-1.5 w-1.5 rounded-full",
              isStreaming ? "bg-green-500 animate-pulse" : "bg-white/20"
            )}
          />
          <span className="text-muted-foreground">ENGINE STATUS:</span>
          <span className={isStreaming ? "text-green-500/80" : "text-white/20"}>
            {isStreaming ? "PROCESSING" : "IDLE"}
          </span>
        </div>
        <Separator orientation="vertical" className="h-3 bg-white/10" />
        <div className="flex items-center gap-2">
          <span className="text-muted-foreground">LAST SYNC:</span>
          <span className="text-white/60">
            {new Date(lastEventTime).toLocaleTimeString()}
          </span>
        </div>
      </div>

      <div className="flex items-center gap-2 text-muted-foreground/60">
        <span className="flex items-center gap-1">
          <Info className="h-3 w-3" /> LOOM ENGINE v3
        </span>
      </div>
    </footer>
  );
}
