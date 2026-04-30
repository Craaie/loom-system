"use client";

import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Edit3, Image as ImageIcon, Trash2, Users, Volume2, Loader2 } from "lucide-react";
import type { Storyboard } from "@/types/job";
import { BACKEND_BASE_URL, loomApi } from "@/lib/api";
import { toast } from "sonner";

interface SceneCardProps {
  scene: Storyboard;
  index: number;
  threadId?: string;
  onEdit?: (index: number) => void;
  onDelete?: (index: number) => void;
  onAssetRegenerated?: (index: number, newScene: Storyboard) => void;
}

export function SceneCard({ scene, index, threadId, onEdit, onDelete, onAssetRegenerated }: SceneCardProps) {
  const [isRegeneratingImage, setIsRegeneratingImage] = useState(false);
  const [isRegeneratingAudio, setIsRegeneratingAudio] = useState(false);

  const handleRegenerate = async (target: "image" | "audio") => {
    if (!threadId) return;

    if (target === "image") {
      setIsRegeneratingImage(true);
    } else {
      setIsRegeneratingAudio(true);
    }

    try {
      const newPrompt = target === "image" ? scene.image_prompt : scene.narration;
      const res = await loomApi.regenerateSceneAsset(threadId, index, target, newPrompt);
      if (onAssetRegenerated) {
        onAssetRegenerated(index, {
          ...scene,
          ...(target === "image" ? { image_path: res.url } : { audio_path: res.url }),
        });
      }
      toast.success(`Scene ${index + 1} ${target} updated`);
    } catch (error) {
      const message = error instanceof Error ? error.message : `Failed to regenerate ${target}`;
      toast.error(message);
    } finally {
      if (target === "image") {
        setIsRegeneratingImage(false);
      } else {
        setIsRegeneratingAudio(false);
      }
    }
  };
  return (
    <Card className="group overflow-hidden border-none bg-white/[0.02] ring-1 ring-white/10 hover:ring-primary/40 transition-all duration-500 hover:bg-white/[0.04] rounded-2xl">
      <div className="aspect-video relative bg-white/5">
        {/* 场景标签 */}
        <div className="absolute top-3 left-3 z-20 flex items-center gap-2">
          <Badge className="bg-black/60 backdrop-blur-md border border-white/10 text-[10px] px-2 h-6">
            SCENE {String(index + 1).padStart(2, "0")}
          </Badge>
          <Badge
            variant="outline"
            className="bg-white/5 border-white/10 text-[10px] h-6"
          >
            {scene.duration || 5}s
          </Badge>
        </div>

        {/* 操作悬浮条 */}
        <div className="absolute top-3 right-3 z-30 opacity-0 group-hover:opacity-100 transition-all duration-300 translate-y-1 group-hover:translate-y-0">
          <div className="flex items-center gap-1.5 p-1 bg-black/60 backdrop-blur-xl rounded-xl border border-white/10 shadow-2xl">
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 rounded-lg hover:bg-white/10 text-white/60 hover:text-white"
              onClick={() => onEdit?.(index)}
            >
              <Edit3 className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 rounded-lg hover:bg-white/10 text-white/60 hover:text-primary"
              onClick={() => handleRegenerate("image")}
              disabled={isRegeneratingImage || !threadId}
            >
              {isRegeneratingImage ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <ImageIcon className="h-3.5 w-3.5" />}
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 rounded-lg hover:bg-destructive/20 text-white/60 hover:text-destructive"
              onClick={() => onDelete?.(index)}
            >
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>

        {/* 背景图片渲染 */}
        {scene.image_path ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img 
            src={`${BACKEND_BASE_URL}${scene.image_path}?t=${Date.now()}`} 
            alt={scene.image_prompt}
            className="absolute inset-0 w-full h-full object-cover transition-transform duration-700 group-hover:scale-105"
          />
        ) : (
          <div className="absolute inset-0 bg-gradient-to-br from-black/40 to-black/80 flex items-center justify-center">
            <p className="text-[13px] text-white/40 px-8 text-center">
              图片生成中...
            </p>
          </div>
        )}

        {/* 画面描述 (Hover 显示) */}
        <div className="absolute inset-0 flex items-end p-4 bg-gradient-to-t from-black/80 via-black/20 to-transparent opacity-0 group-hover:opacity-100 transition-all duration-500">
          <p className="text-[11px] text-white/90 font-medium leading-relaxed italic line-clamp-3 drop-shadow-lg">
            {scene.image_prompt}
          </p>
        </div>

        {/* 覆盖层 (用于增加对比度) */}
        <div className="absolute inset-0 bg-black/10 group-hover:bg-transparent transition-all duration-500" />
      </div>

      <CardContent className="p-4 space-y-4">
        {/* 小说原文 (新增) */}
        {scene.source_text && (
          <div className="space-y-1.5 p-2.5 rounded-xl bg-primary/5 border border-primary/10">
            <div className="flex items-center gap-1.5 text-[10px] font-bold text-primary/60 uppercase tracking-tight">
              <span className="h-1 w-1 rounded-full bg-primary/60" />
              小说原文 Source Text
            </div>
            <p className="text-[11px] text-foreground/70 leading-relaxed font-serif italic">
              {`“${scene.source_text}”`}
            </p>
          </div>
        )}

        {/* 画面提示词 (从 Hover 移出，变为常驻) */}
        <div className="space-y-1.5">
          <div className="flex items-center gap-1.5 text-[10px] font-bold text-foreground/30 uppercase tracking-tight">
             <span className="h-1 w-1 rounded-full bg-foreground/30" />
             画面描述 Image Prompt
          </div>
          <p className="text-[11px] text-foreground/80 leading-relaxed bg-white/5 p-2.5 rounded-xl border border-white/5">
            {scene.image_prompt}
          </p>
        </div>

        {/* 提示词元数据 (新增) */}
        {(scene.visual_style || scene.camera_movement) && (
          <div className="flex flex-wrap gap-1.5">
            {scene.visual_style && (
              <Badge variant="secondary" className="text-[9px] bg-white/5 hover:bg-white/10 text-foreground/40 font-normal px-2 py-0">
                风格: {scene.visual_style}
              </Badge>
            )}
            {scene.camera_movement && (
              <Badge variant="secondary" className="text-[9px] bg-white/5 hover:bg-white/10 text-foreground/40 font-normal px-2 py-0">
                镜头: {scene.camera_movement}
              </Badge>
            )}
          </div>
        )}

        <div className="h-px bg-white/5 w-full" />

        <div className="flex items-start gap-3">
          <div className="mt-1.5 h-1.5 w-1.5 rounded-full bg-primary/40 shrink-0" />
          <div className="flex-1 space-y-3">
            <div className="space-y-1">
              <div className="flex items-center gap-1.5 text-[10px] font-bold text-foreground/30 uppercase tracking-tight">
                <span className="h-1 w-1 rounded-full bg-foreground/30" />
                旁白配音 Narration
              </div>
              <p className="text-[12px] text-foreground/60 leading-relaxed font-serif py-1">
                {scene.narration}
              </p>
            </div>
            
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                {scene.characters?.map((char) => (
                  <Badge
                    key={char}
                    variant="ghost"
                    className="text-[9px] p-0 hover:bg-transparent text-foreground/30 hover:text-primary transition-colors cursor-pointer"
                  >
                    <Users className="h-2.5 w-2.5 mr-1" /> {char}
                  </Badge>
                ))}
              </div>
              
              {/* 音频预览控制 */}
              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6 rounded hover:bg-white/10 text-white/40 hover:text-primary"
                  onClick={() => handleRegenerate("audio")}
                  disabled={isRegeneratingAudio || !threadId}
                >
                  {isRegeneratingAudio ? <Loader2 className="h-3 w-3 animate-spin"/> : <Volume2 className="h-3 w-3"/>}
                </Button>
                {scene.audio_path && (
                  <>
                    <div className="h-4 w-px bg-white/10" />
                    <audio 
                      src={`${BACKEND_BASE_URL}${scene.audio_path}?t=${Date.now()}`}
                      controls
                      className="h-6 scale-75 origin-right invert grayscale"
                    />
                  </>
                )}
              </div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
 