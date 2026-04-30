# 织影系统 (`loom-system`)

织影系统是一个基于 `LangGraph` 的长文本转视频自动化流水线，目标是把小说/长篇文本拆解为结构化分镜，并串联角色记忆、素材生成、人工审核和最终合成。

## 当前架构

当前主线是前后端分离架构：

- `backend/`：`FastAPI + LangGraph + SQLite/Chroma + FFmpeg`
- `frontend/`：`Next.js`
- 实时进度：`SSE`
- 素材访问路径：统一使用 `/output/...`

## 核心能力

- 长文本章节切分与批量分析
- 角色时序记忆（Temporal RAG）
- 分镜结构化输出（Pydantic 校验）
- 图片 / TTS / 视频多 Provider 生成
- HITL 审核与恢复执行
- 成本熔断与任务状态追踪
- FFmpeg 最终合成

## 环境准备

建议使用 `uv` 或 `venv`。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## 环境变量

复制并填写 `.env`：

```bash
cp .env.example .env
```

至少根据你实际使用的 Provider 配置对应 API Key。

## 本地开发

### 启动后端

```bash
cd backend
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 启动前端

```bash
cd frontend
npm run dev
```

前端默认地址：`http://localhost:3000`  
后端默认地址：`http://localhost:8000`

## 项目结构

- `backend/app/core/`：图编排、状态、路由决策
- `backend/app/agents/`：分镜、图片、音频、视频、摄取分析
- `backend/app/modules/`：成本控制、素材路径、缓存、时间轴、FFmpeg
- `backend/app/routers/`：API 路由
- `frontend/`：任务页、素材页、项目页
- `docs/`：设计文档与演进记录
- `tests/`：自动化测试

## 说明

- `README` 只描述当前可运行主线。
- 历史设计、竞品分析和路线规划请看 `docs/`。
