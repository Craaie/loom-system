"use client";

import React, { useState } from "react";
import { User, Shield, Zap, Package, Edit3 } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";

interface CharacterArchiveProps {
  registry?: Record<string, any>;
  onUpdateRegistry?: (newRegistry: Record<string, any>) => Promise<void>;
}

export const CharacterArchive: React.FC<CharacterArchiveProps> = ({ registry, onUpdateRegistry }) => {
  const [editingName, setEditingName] = useState<string | null>(null);
  const [editAppearance, setEditAppearance] = useState("");
  const [editClothing, setEditClothing] = useState("");
  const [editPersonality, setEditPersonality] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  if (!registry || Object.keys(registry).length === 0) {
    return (
      <Card className="rounded-3xl border-border bg-card/50 shadow-sm overflow-hidden mb-4">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <User className="h-4 w-4 text-primary" />
            角色档案
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-[11px] text-muted-foreground italic">暂无提取的角色信息。</p>
        </CardContent>
      </Card>
    );
  }

  const handleEditOpen = (name: string) => {
    const char = registry[name];
    setEditingName(name);
    setEditAppearance(char.appearance || "");
    setEditClothing(char.clothing || "");
    setEditPersonality(char.personality || "");
  };

  const handleSave = async () => {
    if (!editingName || !onUpdateRegistry) return;
    
    setIsSaving(true);
    try {
      const newRegistry = { ...registry };
      newRegistry[editingName] = {
        ...newRegistry[editingName],
        appearance: editAppearance,
        clothing: editClothing,
        personality: editPersonality,
      };
      await onUpdateRegistry(newRegistry);
      setEditingName(null);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Card className="rounded-3xl border-border bg-card/50 shadow-sm overflow-hidden mb-4">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium flex items-center justify-between">
          <div className="flex items-center gap-2">
            <User className="h-4 w-4 text-primary" />
            角色档案
          </div>
          <Badge variant="secondary" className="text-[10px] px-1.5 py-0 rounded-full">
            {Object.keys(registry).length} 位
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 pt-0">
        {Object.entries(registry).map(([name, desc]: [string, any]) => (
          <div key={name} className="p-2.5 rounded-2xl bg-background/40 border border-border/40 space-y-2 group relative">
            <div className="flex items-center justify-between">
              <span className="text-[12px] font-bold text-foreground">{name}</span>
              <Button 
                variant="ghost" 
                size="icon" 
                className="h-6 w-6 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity"
                onClick={() => handleEditOpen(name)}
              >
                <Edit3 className="h-3 w-3 text-muted-foreground" />
              </Button>
            </div>

            {desc.reference_image_url && (
              <div className="w-full relative h-32 mb-2 rounded-xl overflow-hidden border border-border/50 shadow-inner">
                <img src={desc.reference_image_url} alt={name} className="object-cover w-full h-full transition-transform duration-700 hover:scale-105" />
                <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent pointer-events-none" />
                <Badge variant="outline" className="absolute bottom-2 left-2 text-[8px] bg-primary/20 text-primary-foreground border-primary/30 backdrop-blur-md">
                  ★ 圣经锁脸锚点
                </Badge>
              </div>
            )}
            
            <div className="grid grid-cols-1 gap-1.5 text-[11px]">
              {desc.appearance && (
                <div className="flex items-start gap-1.5">
                  <Shield className="h-3 w-3 mt-0.5 text-blue-400/80" />
                  <span className="text-muted-foreground leading-relaxed">
                    <span className="text-foreground/70">外貌:</span> {desc.appearance}
                  </span>
                </div>
              )}
              {desc.clothing && (
                <div className="flex items-start gap-1.5">
                  <Package className="h-3 w-3 mt-0.5 text-orange-400/80" />
                  <span className="text-muted-foreground leading-relaxed">
                    <span className="text-foreground/70">装束:</span> {desc.clothing}
                  </span>
                </div>
              )}
              {desc.personality && (
                <div className="flex items-start gap-1.5">
                  <Zap className="h-3 w-3 mt-0.5 text-yellow-400/80" />
                  <span className="text-muted-foreground leading-relaxed">
                    <span className="text-foreground/70">性格:</span> {desc.personality}
                  </span>
                </div>
              )}
            </div>
          </div>
        ))}
      </CardContent>

      <Dialog open={editingName !== null} onOpenChange={(open) => !open && setEditingName(null)}>
        <DialogContent className="max-w-md bg-card border-border shadow-2xl rounded-3xl p-6">
          <DialogHeader>
            <DialogTitle className="text-lg font-bold">编辑角色: {editingName}</DialogTitle>
          </DialogHeader>
          <div className="space-y-5 py-4">
            <div className="space-y-2">
              <Label className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider px-1">外貌描写 (Appearance)</Label>
              <Textarea 
                value={editAppearance} 
                onChange={(e) => setEditAppearance(e.target.value)}
                className="min-h-[60px] rounded-xl bg-muted/30 border-border/50 text-[12px] leading-relaxed"
              />
            </div>
            <div className="space-y-2">
              <Label className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider px-1">服装打扮 (Clothing)</Label>
              <Textarea 
                value={editClothing} 
                onChange={(e) => setEditClothing(e.target.value)}
                className="min-h-[60px] rounded-xl bg-muted/30 border-border/50 text-[12px] leading-relaxed"
              />
            </div>
            <div className="space-y-2">
              <Label className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider px-1">性格气质 (Personality)</Label>
              <Textarea 
                value={editPersonality} 
                onChange={(e) => setEditPersonality(e.target.value)}
                className="min-h-[60px] rounded-xl bg-muted/30 border-border/50 text-[12px] leading-relaxed"
              />
            </div>
          </div>
          <DialogFooter className="gap-2">
            <Button variant="ghost" onClick={() => setEditingName(null)} className="rounded-xl">取消</Button>
            <Button onClick={handleSave} disabled={isSaving} className="rounded-xl px-8 shadow-lg shadow-primary/20">
              {isSaving ? "保存中..." : "保存更改"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
};
