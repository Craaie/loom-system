"use client";

import { Zap } from "lucide-react";

export default function JobLoadingSkeleton() {
  return (
    <div className="h-screen flex flex-col bg-background text-white">
      {/* 顶部导航骨架 */}
      <div className="h-14 border-b border-white/5 bg-black/40 flex items-center px-6">
        <div className="flex items-center gap-3">
          <div className="h-8 w-8 rounded-lg bg-white/5 animate-pulse" />
          <div className="h-4 w-24 rounded bg-white/5 animate-pulse" />
        </div>
      </div>

      {/* 主体骨架 */}
      <div className="flex-1 flex overflow-hidden">
        {/* 左栏骨架 */}
        <div className="w-[28%] border-r border-white/5 p-4 space-y-4">
          <div className="h-4 w-32 bg-white/5 rounded animate-pulse" />
          <div className="flex gap-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="h-2 w-8 bg-white/5 rounded-full animate-pulse" />
            ))}
          </div>
          <div className="h-20 bg-white/5 rounded-xl animate-pulse" />
          <div className="space-y-3 pt-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="h-8 bg-white/[0.03] rounded animate-pulse" />
            ))}
          </div>
        </div>

        {/* 中栏骨架 */}
        <div className="flex-1 p-6">
          <div className="flex items-center justify-center h-full">
            <div className="flex flex-col items-center gap-4">
              <div className="h-12 w-12 rounded-2xl bg-primary/20 flex items-center justify-center animate-bounce">
                <Zap className="h-6 w-6 text-primary" />
              </div>
              <div className="text-sm font-medium animate-pulse text-white/60">
                正在唤醒织影引擎...
              </div>
            </div>
          </div>
        </div>

        {/* 右栏骨架 */}
        <div className="w-[30%] border-l border-white/5 p-6 space-y-6">
          <div className="h-4 w-24 bg-white/5 rounded animate-pulse" />
          <div className="grid grid-cols-2 gap-3">
            <div className="h-20 bg-white/5 rounded-2xl animate-pulse" />
            <div className="h-20 bg-white/5 rounded-2xl animate-pulse" />
          </div>
          <div className="space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="h-14 bg-white/[0.03] rounded-xl animate-pulse" />
            ))}
          </div>
          <div className="h-32 bg-white/5 rounded-3xl animate-pulse" />
        </div>
      </div>

      {/* 底部骨架 */}
      <div className="h-8 border-t border-white/5 bg-black" />
    </div>
  );
}
