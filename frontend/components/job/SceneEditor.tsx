"use client";

import React, { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { RefreshCw, Scissors, Sparkles } from "lucide-react";
import type { Storyboard } from "@/types/job";
import { SceneCard } from "./SceneCard";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface SceneEditorProps {
  threadId?: string;
  storyboards: Storyboard[];
  finalVideoPath?: string | null;
  onUpdateStoryboard?: (newStoryboards: Storyboard[]) => Promise<void>;
  onDeleteScene?: (index: number) => void;
}

export default function SceneEditor({
  threadId,
  storyboards,
  finalVideoPath,
  onUpdateStoryboard,
  onDeleteScene,
}: SceneEditorProps) {
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [editingScene, setEditingScene] = useState<Storyboard | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  const handleEditOpen = (index: number) => {
    setEditingIndex(index);
    setEditingScene({ ...storyboards[index] });
  };

  const handleSave = async () => {
    if (editingIndex === null || !editingScene || !onUpdateStoryboard) return;
    
    setIsSaving(true);
    try {
      const newStoryboards = [...storyboards];
      newStoryboards[editingIndex] = {
        ...editingScene,
        // 如果修改了提示词，通常需要重置状态以重新生成图片/音频
        status: "pending"
      };
      await onUpdateStoryboard(newStoryboards);
      setEditingIndex(null);
      setEditingScene(null);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <section className="flex-1 bg-black flex flex-col relative">
      {/* 工具栏 */}
      <div className="h-12 border-b border-white/5 bg-black/40 flex items-center justify-between px-6 shrink-0">
        <div className="flex items-center gap-4">
          <h2 className="text-xs font-bold uppercase tracking-widest text-white/80">
            分镜编辑器 Editor
          </h2>
          <Badge className="bg-white/5 text-[10px] hover:bg-white/5 cursor-default rounded-full">
            {storyboards.length} Scenes
          </Badge>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 rounded-lg text-white/40 hover:text-white hover:bg-white/5"
          >
            <RefreshCw className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 rounded-lg text-white/40 hover:text-white hover:bg-white/5"
          >
            <Scissors className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* 最终合成视频展示 */}
      {finalVideoPath && (
        <div className="px-6 py-6 pb-2 shrink-0 flex flex-col items-center animate-in fade-in slide-in-from-top-4 duration-700">
          <div className="w-full max-w-4xl bg-black rounded-3xl overflow-hidden border border-white/10 shadow-[0_0_50px_-12px_rgba(var(--primary),0.3)] relative group">
            <div className="absolute top-4 left-4 z-10 transition-opacity duration-300">
              <Badge className="bg-primary/90 hover:bg-primary backdrop-blur-md text-white border-none shadow-lg px-3 py-1 text-xs">
                <Sparkles className="w-3.5 h-3.5 mr-1.5 inline animate-pulse" /> Final Masterpiece
              </Badge>
            </div>
            {/* The actual video player */}
            <video 
              src={finalVideoPath} 
              controls 
              autoPlay
              playsInline
              className="w-full h-auto max-h-[60vh] object-contain bg-black/50"
            >
              Your browser does not support the video tag.
            </video>
          </div>
          <div className="w-full max-w-4xl mt-6">
            <div className="h-px bg-gradient-to-r from-transparent via-white/10 to-transparent w-full" />
          </div>
        </div>
      )}

      {/* 分镜网格 / 空状态 */}
      <div className="flex-1 overflow-auto p-6">
        {storyboards.length > 0 ? (
          <div className="grid grid-cols-1 2xl:grid-cols-2 gap-6 pb-20">
            {storyboards.map((sb, i) => (
              <SceneCard
                key={i}
                scene={sb}
                index={i}
                threadId={threadId}
                onEdit={() => handleEditOpen(i)}
                onDelete={onDeleteScene}
                onAssetRegenerated={(idx, newScene) => {
                  if (!onUpdateStoryboard) return;
                  const newStoryboards = [...storyboards];
                  newStoryboards[idx] = newScene;
                  onUpdateStoryboard(newStoryboards);
                }}
              />
            ))}
          </div>
        ) : (
          <EmptyState />
        )}
      </div>

      <Dialog open={editingIndex !== null} onOpenChange={(open) => !open && setEditingIndex(null)}>
        <DialogContent className="max-w-xl bg-card border-border shadow-2xl rounded-3xl p-6">
          <DialogHeader>
            <DialogTitle className="text-lg font-bold">编辑场景 #{editingIndex !== null ? editingIndex + 1 : ""}</DialogTitle>
          </DialogHeader>
          <div className="space-y-6 py-4">
            {/* 小说原文 */}
            <div className="space-y-2">
              <Label className="text-xs font-bold text-muted-foreground uppercase tracking-widest">小说原文片段 Source Text</Label>
              <Textarea
                value={editingScene?.source_text || ""}
                onChange={(e) => setEditingScene(prev => prev ? { ...prev, source_text: e.target.value } : null)}
                className="min-h-[60px] rounded-2xl bg-muted/30 border-border/50 focus:border-primary/50 text-sm italic leading-relaxed"
                placeholder="该分镜对应的小说原文..."
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              {/* 画面描述 (Prompt) */}
              <div className="space-y-2 col-span-2">
                <Label className="text-xs font-bold text-muted-foreground uppercase tracking-widest">画面提示词 (AI Image Prompt)</Label>
                <Textarea
                  value={editingScene?.image_prompt || ""}
                  onChange={(e) => setEditingScene(prev => prev ? { ...prev, image_prompt: e.target.value } : null)}
                  className="min-h-[80px] rounded-2xl bg-muted/30 border-border/50 focus:border-primary/50 text-sm leading-relaxed"
                  placeholder="描述你想要的画面细节..."
                />
              </div>

              {/* 视觉风格 */}
              <div className="space-y-2">
                <Label className="text-xs font-bold text-muted-foreground uppercase tracking-widest">视觉风格 Style</Label>
                <Input
                  value={editingScene?.visual_style || ""}
                  onChange={(e) => setEditingScene(prev => prev ? { ...prev, visual_style: e.target.value } : null)}
                  className="rounded-2xl bg-muted/30 border-border/50 focus:border-primary/50 text-sm"
                  placeholder="如: 中景, 赛博朋克..."
                />
              </div>

              {/* 镜头运动 */}
              <div className="space-y-2">
                <Label className="text-xs font-bold text-muted-foreground uppercase tracking-widest">镜头运动 Camera</Label>
                <Input
                  value={editingScene?.camera_movement || ""}
                  onChange={(e) => setEditingScene(prev => prev ? { ...prev, camera_movement: e.target.value } : null)}
                  className="rounded-2xl bg-muted/30 border-border/50 focus:border-primary/50 text-sm"
                  placeholder="如: 推进, 横摇..."
                />
              </div>
            </div>

            {/* 旁白 */}
            <div className="space-y-2">
              <Label className="text-xs font-bold text-muted-foreground uppercase tracking-widest">旁白文本 (Narration)</Label>
              <Textarea
                value={editingScene?.narration || ""}
                onChange={(e) => setEditingScene(prev => prev ? { ...prev, narration: e.target.value } : null)}
                className="min-h-[80px] rounded-2xl bg-muted/30 border-border/50 focus:border-primary/50 text-sm font-serif leading-relaxed"
                placeholder="输入场景的配音文本..."
              />
            </div>
          </div>
          <DialogFooter className="gap-2">
            <Button variant="ghost" onClick={() => {setEditingIndex(null); setEditingScene(null);}} className="rounded-xl">取消</Button>
            <Button onClick={handleSave} disabled={isSaving} className="rounded-xl px-8 shadow-lg shadow-primary/20">
              {isSaving ? "保存中..." : "应用更改"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
}

function EmptyState() {
  return (
    <div className="h-[60vh] flex flex-col items-center justify-center gap-6">
      <div className="relative">
        <div className="absolute inset-0 bg-primary/20 rounded-full blur-3xl animate-pulse" />
        <div className="relative h-20 w-20 rounded-3xl bg-gradient-to-br from-primary/40 to-primary/10 border border-primary/30 flex items-center justify-center group overflow-hidden">
          <Sparkles className="h-10 w-10 text-primary animate-shimmer" />
          <div className="absolute inset-0 bg-gradient-to-t from-primary/20 to-transparent translate-y-20 group-hover:translate-y-0 transition-transform duration-700" />
        </div>
      </div>
      <div className="text-center space-y-2 max-w-sm">
        <h3 className="text-xl font-bold text-white/90">正在解析剧本蓝图...</h3>
        <p className="text-sm text-white/40 leading-relaxed">
          Agent 正在将你的小说转化为场景级的分镜描述，这通常需要 10-20 秒。
        </p>
      </div>
    </div>
  );
}
