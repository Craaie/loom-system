"use client";

import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Image, Music, FileVideo, Download, ExternalLink, AlertCircle } from "lucide-react";
import { BACKEND_BASE_URL } from "@/lib/api";
import type { ImageTask, AudioTask } from "@/types/job";

interface AssetLibraryProps {
  imageTasks: ImageTask[];
  audioTasks: AudioTask[];
  threadId: string | null;
}

export function AssetLibrary({ imageTasks, audioTasks, threadId }: AssetLibraryProps) {
  const BACKEND_URL = "http://localhost:8000";

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold flex items-center gap-2">
            <Image className="w-5 h-5 text-primary" />
            素材中心 Asset Library
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            聚合本项目生成的所有视觉与音频素材
          </p>
        </div>
        <Badge variant="outline" className="bg-primary/5 border-primary/20 text-primary">
          {imageTasks.length + audioTasks.length} Assets
        </Badge>
      </div>

      <div className="grid gap-8 md:grid-cols-2 lg:grid-cols-3">
        {/* 图像素材 */}
        <div className="md:col-span-2 space-y-4">
          <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
            内插关键帧 Keyframes
          </h3>
          {imageTasks.length > 0 ? (
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
              {imageTasks.map((task, i) => (
                <Card key={task.task_id} className="group overflow-hidden border-none ring-1 ring-white/10 hover:ring-primary/40 transition-all">
                  <div className="aspect-video relative bg-muted flex items-center justify-center">
                    {task.status === "done" && task.image_path ? (
                      <img 
                        src={`${BACKEND_BASE_URL}${task.image_path}`} 
                        alt={task.task_id}
                        className="w-full h-full object-cover"
                      />
                    ) : task.status === "failed" ? (
                      <div className="flex flex-col items-center gap-2 text-destructive/60">
                        <AlertCircle className="w-6 h-6" />
                        <span className="text-[10px] text-center px-2">{task.error || "生成失败"}</span>
                      </div>
                    ) : (
                      <div className="animate-pulse flex flex-col items-center gap-2">
                        <Image className="w-6 h-6 opacity-20" />
                        <span className="text-[10px] opacity-40">生成中...</span>
                      </div>
                    )}
                    {task.image_path && (
                      <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2">
                         <a 
                           href={`${BACKEND_URL}${task.image_path}`} 
                           target="_blank" 
                           rel="noreferrer"
                           className="p-2 bg-white/10 rounded-full hover:bg-white/20 transition-colors"
                         >
                           <ExternalLink className="w-4 h-4 text-white" />
                         </a>
                      </div>
                    )}
                  </div>
                  <div className="p-2 border-t border-white/5 bg-black/20">
                     <span className="text-[10px] font-mono opacity-40">SCENE #{i+1}</span>
                  </div>
                </Card>
              ))}
            </div>
          ) : (
            <div className="h-40 border border-dashed rounded-2xl flex flex-col items-center justify-center text-muted-foreground opacity-30">
              <Image className="w-8 h-8 mb-2" />
              <p className="text-xs">暂无图像素材</p>
            </div>
          )}
        </div>

        {/* 音频素材 */}
        <div className="space-y-4">
          <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
            配音音频 Narrations
          </h3>
          {audioTasks.length > 0 ? (
            <ScrollArea className="h-[400px] pr-4">
              <div className="space-y-3">
                {audioTasks.map((task, i) => (
                  <div key={task.task_id} className="p-3 rounded-xl bg-muted/30 border border-white/5 space-y-2 group hover:border-primary/20 transition-colors">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-mono opacity-40">AUDIO #{i+1}</span>
                      <Music className="w-3 h-3 opacity-20 group-hover:text-primary group-hover:opacity-100 transition-all" />
                    </div>
                    {task.audio_path ? (
                      <audio 
                        src={`${BACKEND_BASE_URL}${task.audio_path}`} 
                        controls 
                        className="w-full h-8 invert grayscale scale-90 origin-left"
                      />
                    ) : (
                      <div className="h-8 animate-pulse bg-white/5 rounded-lg border border-dashed border-white/10" />
                    )}
                  </div>
                ))}
              </div>
            </ScrollArea>
          ) : (
            <div className="h-40 border border-dashed rounded-2xl flex flex-col items-center justify-center text-muted-foreground opacity-30">
              <Music className="w-8 h-8 mb-2" />
              <p className="text-xs">暂无音频素材</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
