# Loom (织影) 2.0: 重构实施方案参考

## 1. 目录结构重编
为了适配 Next.js 和 FastAPI 的独立部署与开发，我们将原有结构迁移为 Monorepo 模式：

```text
loom-system/
├── backend/                  # 后端项目根目录
│   ├── app/                  # 原包代码 (loom -> app)
│   ├── Dockerfile            # 后端镜像
│   └── requirements.txt      # 依赖：增加 sse-starlette, uvicorn
├── frontend/                 # 前端项目根目录 (Next.js 15)
│   ├── app/                  # 页面与路由
│   ├── components/           # UI 组件 (shadcn)
│   ├── lib/                  # API 客户端
│   └── Dockerfile            # 前端镜像
├── docker-compose.yml        # 一键编排
└── .env                      # 共享环境变量
```

## 2. 关键代码迁移步骤
1. **包重构**: 全局搜索 `from loom.` 并替换为 `from app.`（因当前代码位于 `backend/app/` 之下）。
2. **入口平迁**: `ui/backend.py` 经完善后提升为 `backend/app/main.py`。
3. **SSE 支持**: 
   - 引入 `EventManager` 处理基于 thread_id 的消息分发。
   - 修改 `engine_task` 全程使用 `astream` 捕获中间变量并实时发布。

## 3. 前端交互逻辑
- **TanStack Query**: 用于 `listThreads` 和 `getJobState` 的自动刷新与缓存管理。
- **SSE Listener**: 在 `jobs/[id]` 页面通过 `EventSource` 监听实时推送：
  - `update`: 刷新分镜网格和消耗进度。
  - `end`: 关闭流并提示完成。
  - `error`: 全局 Toast 提示。

## 4. 运行与验证
详见项目根目录下的 [walkthrough_v2.md](walkthrough_v2.md)。
