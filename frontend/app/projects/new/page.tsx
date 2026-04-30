"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import { 
  Card, 
  CardContent, 
  CardDescription, 
  CardFooter, 
  CardHeader, 
  CardTitle 
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { loomApi } from "@/lib/api";
import { toast } from "sonner";
import { ChevronRight, FolderPlus, BookPlus } from "lucide-react";

export default function NewProjectPage() {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [projectName, setProjectName] = useState("");
  const [projectDesc, setProjectDesc] = useState("");
  const [novelTitle, setNovelTitle] = useState("");
  const [author, setAuthor] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleCreate = async () => {
    setIsSubmitting(true);
    try {
      // 1. 创建项目
      const project = await loomApi.createProject(projectName, projectDesc);
      
      // 2. 创建关联小说
      if (novelTitle) {
        await loomApi.createNovel({
          project_id: project.id,
          title: novelTitle,
          author: author
        });
      }
      
      toast.success("项目创建成功");
      router.push("/");
      router.refresh();
    } catch (error) {
      console.error(error);
      toast.error("创建失败，请稍后重试");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto py-12 px-4 space-y-8 animate-in fade-in slide-in-from-bottom-4">
      <div className="space-y-2 text-center">
        <h1 className="text-3xl font-bold">创建新项目</h1>
        <p className="text-muted-foreground">通过项目化管理你的小说系列</p>
      </div>

      <div className="flex items-center justify-center gap-4 mb-8">
        <div className={cn(
          "h-2 w-12 rounded-full transition-all",
          step === 1 ? "bg-primary" : "bg-muted"
        )} />
        <div className={cn(
          "h-2 w-12 rounded-full transition-all",
          step === 2 ? "bg-primary" : "bg-muted"
        )} />
      </div>

      <Card className="shadow-xl">
        {step === 1 ? (
          <>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FolderPlus className="w-5 h-5 text-primary" />
                第一步：项目基本信息
              </CardTitle>
              <CardDescription>定义你的创作宇宙或系列名称</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="name">项目名称</Label>
                <Input 
                  id="name" 
                  placeholder="例如：斗罗宇宙" 
                  value={projectName}
                  onChange={(e) => setProjectName(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="desc">描述 (可选)</Label>
                <Textarea 
                  id="desc" 
                  placeholder="简单描述一下这个项目..."
                  value={projectDesc}
                  onChange={(e) => setProjectDesc(e.target.value)}
                />
              </div>
            </CardContent>
            <CardFooter>
              <Button 
                className="w-full gap-2" 
                onClick={() => setStep(2)}
                disabled={!projectName.trim()}
              >
                下一步
                <ChevronRight className="w-4 h-4" />
              </Button>
            </CardFooter>
          </>
        ) : (
          <>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BookPlus className="w-5 h-5 text-primary" />
                第二步：添加首部作品
              </CardTitle>
              <CardDescription>在项目中开启你的第一篇小说</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="novel-title">小说标题</Label>
                <Input 
                  id="novel-title" 
                  placeholder="例如：斗罗大陆 I" 
                  value={novelTitle}
                  onChange={(e) => setNovelTitle(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="author">作者名称</Label>
                <Input 
                  id="author" 
                  placeholder="唐家三少" 
                  value={author}
                  onChange={(e) => setAuthor(e.target.value)}
                />
              </div>
            </CardContent>
            <CardFooter className="flex gap-4">
              <Button variant="outline" className="flex-1" onClick={() => setStep(1)}>
                上一步
              </Button>
              <Button 
                className="flex-[2] gap-2" 
                onClick={handleCreate}
                disabled={!novelTitle.trim() || isSubmitting}
              >
                {isSubmitting ? "正在创建..." : "完成并开启"}
                <FolderPlus className="w-4 h-4" />
              </Button>
            </CardFooter>
          </>
        )}
      </Card>
    </div>
  );
}

