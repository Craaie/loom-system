"use client";

import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { 
  CheckCircle2, 
  Circle, 
  Clock, 
  ArrowRight, 
  Activity, 
  ShieldAlert,
  Play
} from "lucide-react";
import { NODE_LABELS, WORKFLOW_NODES } from "@/types/job";
import { useRouter } from "next/navigation";

interface WorkflowStatusProps {
  activeNode: string | null;
  threadId: string | null;
  isPendingApproval: boolean;
}

export function WorkflowStatus({ activeNode, threadId, isPendingApproval }: WorkflowStatusProps) {
  const router = useRouter();
  
  const currentNodeIndex = WORKFLOW_NODES.indexOf(activeNode as any);
  
  return (
    <Card className="p-8 border-none bg-white/[0.02] ring-1 ring-white/10 space-y-10">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-primary/10 rounded-xl">
             <Activity className="w-5 h-5 text-primary" />
          </div>
          <div>
            <h2 className="text-xl font-bold">工作流状态 Pipeline Status</h2>
            <p className="text-sm text-muted-foreground">实时监控引擎执行进度与当前瓶颈</p>
          </div>
        </div>
        {activeNode && (
          <Badge className="px-4 py-1.5 rounded-full bg-primary text-primary-foreground animate-pulse font-bold tracking-wider">
            正在运行: {NODE_LABELS[activeNode as keyof typeof NODE_LABELS] || activeNode}
          </Badge>
        )}
      </div>

      {/* 节点水平时间轴 */}
      <div className="relative flex justify-between items-start max-w-4xl mx-auto px-10">
        {/* 连接线 */}
        <div className="absolute top-5 left-20 right-20 h-[2px] bg-white/5 -z-0" />
        
        {WORKFLOW_NODES.map((node, i) => {
          const isActive = activeNode === node;
          const isDone = currentNodeIndex > i;
          const isUpcoming = currentNodeIndex < i;
          
          return (
            <div key={node} className="relative z-10 flex flex-col items-center gap-4 group">
              <div className={cn(
                "h-10 w-10 rounded-full flex items-center justify-center transition-all duration-700 border-2",
                isActive ? "bg-primary border-primary shadow-[0_0_20px_rgba(var(--primary),0.3)] scale-110" : 
                isDone ? "bg-green-500/20 border-green-500/40 text-green-500" : 
                "bg-black border-white/10 text-white/20"
              )}>
                {isDone ? <CheckCircle2 className="w-6 h-6" /> : 
                 isActive ? <Play className="w-5 h-5 fill-current" /> :
                 <Circle className="w-4 h-4 fill-current opacity-20" />}
              </div>
              <div className="text-center">
                 <p className={cn(
                   "text-xs font-bold uppercase tracking-widest",
                   isActive ? "text-primary" : "text-white/20"
                 )}>
                   {NODE_LABELS[node as keyof typeof NODE_LABELS]}
                 </p>
              </div>
            </div>
          );
        })}
      </div>

      {/* 状态详情卡片 */}
      <div className="bg-white/[0.03] rounded-3xl p-8 border border-white/5 flex items-center justify-between">
        <div className="flex items-center gap-6">
          <div className={cn(
            "h-16 w-16 rounded-2xl flex items-center justify-center transition-colors",
            isPendingApproval ? "bg-yellow-500/10 text-yellow-500" : "bg-primary/10 text-primary"
          )}>
             {isPendingApproval ? <ShieldAlert className="w-8 h-8" /> : <Clock className="w-8 h-8" />}
          </div>
          <div className="space-y-1">
            <h3 className="text-lg font-bold">
              {isPendingApproval ? "等待人工审批" : activeNode ? `正在执行: ${NODE_LABELS[activeNode as keyof typeof NODE_LABELS]}` : "引擎就绪"}
            </h3>
            <p className="text-sm text-white/40 max-w-md">
              {isPendingApproval ? "分镜剧本已生成，请进入工作台进行画面审阅与确认。只有审批通过后，系统才会开始生成视频。" : 
               activeNode === 'ingestion' ? "正在深入解析小说文本，提取关键角色与场景设定..." :
               activeNode === 'storyboard' ? "Agent 正在构思每一帧的视觉描述与旁白对白..." :
               "一切正常运行中。"}
            </p>
          </div>
        </div>

        {threadId && (
          <Button 
            size="lg" 
            className="rounded-2xl px-8 h-14 font-bold shadow-xl shadow-primary/20"
            onClick={() => router.push(`/jobs/${threadId}`)}
          >
            {isPendingApproval ? "立即进入审批" : "查看执行详情"}
            <ArrowRight className="ml-2 w-5 h-5" />
          </Button>
        )}
      </div>
    </Card>
  );
}
