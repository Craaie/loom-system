"use client";

import { useState, useEffect } from "react";
import { loomApi } from "@/lib/api";
import { 
  Card, 
  CardContent, 
  CardDescription, 
  CardHeader, 
  CardTitle,
  CardFooter
} from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { 
  Settings, 
  Save, 
  ShieldCheck, 
  Cpu, 
  Globe,
  Wallet
} from "lucide-react";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import { toast } from "sonner";

export default function SettingsPage() {
  const [isSaving, setIsSaving] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [config, setConfig] = useState({
    default_llm_provider: "google",
    default_llm_model: "gemini-2.0-flash",
    image_provider: "wanx",
    tts_provider: "dashscope",
    video_provider: "hailuo"
  });

  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const data = await loomApi.getSettings();
        setConfig(prev => ({ ...prev, ...data }));
      } catch (err) {
        toast.error("加载配置失败");
      } finally {
        setIsLoading(false);
      }
    };
    fetchSettings();
  }, []);

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await loomApi.updateSettings(config);
      toast.success("全局配置已保存");
    } catch (err) {
      toast.error("保存配置失败");
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) return <div className="p-8 text-center animate-pulse">加载配置中...</div>;

  return (
    <div className="max-w-4xl mx-auto space-y-8 animate-in fade-in duration-500">
      <header className="space-y-1">
        <h1 className="text-3xl font-bold tracking-tight">系统设置</h1>
        <p className="text-muted-foreground">配置你的 Loom 引擎核心参数与 API 令牌</p>
      </header>

      <div className="grid gap-6">
        <Card className="border-primary/20 shadow-lg overflow-hidden">
          <CardHeader className="bg-primary/5 border-b border-primary/10">
            <CardTitle className="flex items-center gap-2">
              <Cpu className="w-5 h-5 text-primary" />
              生成策略 (Generation Strategy)
            </CardTitle>
            <CardDescription>配置全局默认的 AI 供应商组合 (Combo)</CardDescription>
          </CardHeader>
          <CardContent className="pt-6 grid gap-6 md:grid-cols-2">
            <div className="space-y-2">
              <Label>默认 LLM 供应商</Label>
              <select 
                className="w-full h-10 px-3 py-2 bg-background border rounded-md text-sm focus:ring-2 focus:ring-primary outline-none"
                value={config.default_llm_provider}
                onChange={(e) => setConfig({ ...config, default_llm_provider: e.target.value })}
              >
                <option value="google">Google Gemini</option>
                <option value="deepseek">DeepSeek</option>
                <option value="ollama">Ollama (Local)</option>
              </select>
            </div>
            <div className="space-y-2">
              <Label>默认图像引擎</Label>
              <select 
                className="w-full h-10 px-3 py-2 bg-background border rounded-md text-sm focus:ring-2 focus:ring-primary outline-none"
                value={config.image_provider}
                onChange={(e) => setConfig({ ...config, image_provider: e.target.value })}
              >
                <option value="cogview">CogView-4 (智谱)</option>
                <option value="wanx">Wanx 2.5 (通义)</option>
                <option value="flux">FLUX.1 [dev]</option>
                <option value="mock">Mock Mode</option>
              </select>
            </div>
            <div className="space-y-2">
              <Label>默认声音引擎</Label>
              <select 
                className="w-full h-10 px-3 py-2 bg-background border rounded-md text-sm focus:ring-2 focus:ring-primary outline-none"
                value={config.tts_provider}
                onChange={(e) => setConfig({ ...config, tts_provider: e.target.value })}
              >
                <option value="dashscope">CosyVoice (阿里通义)</option>
                <option value="fish">Fish TTS</option>
                <option value="minimax_speech">Speech-02 (MiniMax)</option>
                <option value="mock">Mock Mode</option>
              </select>
            </div>
            <div className="space-y-2">
              <Label>默认视频引擎</Label>
              <select 
                className="w-full h-10 px-3 py-2 bg-background border rounded-md text-sm focus:ring-2 focus:ring-primary outline-none"
                value={config.video_provider}
                onChange={(e) => setConfig({ ...config, video_provider: e.target.value })}
              >
                <option value="hailuo">Hailuo 2.3 (海螺)</option>
                <option value="seedance">Seedance 2.0</option>
                <option value="kling">Kling 2.0 (可灵)</option>
                <option value="mock">Mock Mode</option>
              </select>
            </div>
          </CardContent>
          <CardFooter className="bg-muted/30 py-3 block text-center">
             <div className="flex justify-center gap-4">
               <Button variant="ghost" size="sm" className="text-xs" onClick={() => setConfig({
                 ...config,
                 default_llm_provider: "google",
                 image_provider: "cogview",
                 tts_provider: "fish",
                 video_provider: "hailuo"
               })}>平衡模式 (Balanced)</Button>
               <Button variant="ghost" size="sm" className="text-xs" onClick={() => setConfig({
                 ...config,
                 default_llm_provider: "deepseek",
                 image_provider: "wanx",
                 tts_provider: "minimax_speech",
                 video_provider: "mock"
               })}>省钱模式 (Budget)</Button>
             </div>
          </CardFooter>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Cpu className="w-5 h-5 text-primary" />
              本地计算 (Ollama)
            </CardTitle>
            <CardDescription>配置本地降级兜底服务的终端地址</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <Label>启用本地兜底</Label>
                <p className="text-xs text-muted-foreground">当云端服务繁忙或欠费时自动切换</p>
              </div>
              <Switch defaultChecked />
            </div>
            <Separator />
            <div className="grid gap-2">
              <Label htmlFor="ollama_url">Ollama Base URL</Label>
              <Input id="ollama_url" placeholder="http://localhost:11434" defaultValue="http://localhost:11434" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Wallet className="w-5 h-5 text-primary" />
              成本控制
            </CardTitle>
            <CardDescription>全局默认熔断阈值</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-2">
              <Label htmlFor="max_cost">默认最大消耗 (USD/任务)</Label>
              <Input id="max_cost" type="number" defaultValue={20} />
            </div>
          </CardContent>
        </Card>

        <div className="flex justify-end">
          <Button size="lg" className="px-10 gap-2" onClick={handleSave} disabled={isSaving}>
            {isSaving ? "正在保存..." : "保存更改"}
            <Save className="w-4 h-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
