# 织影系统 (Loom System) - 视听精细化管线优化方案 (TODO)

本方案旨在将现有的“文生视频”自动化管线升级为“影视级精细化生产管线”，重点解决角色一致性、配音缺失和镜头控制力不足的问题。

## 1. 目标业务流程

下表对比了当前架构与目标优化架构的差异：

| 阶段 | 当前实现 (MVP) | 目标优化 (Refinement) |
| :--- | :--- | :--- |
| **故事解析** | GPT-4o 生成分镜 JSON | 增加了多模型自省 + 角色动作指令优化 |
| **视觉基准** | 直接文生视频 (Kling 3.0) | **Image Agent**: 先生成高精角色/场景大图 (Flux/MJ) |
| **视频增强** | - | **I2V Agent**: 以图片为关键帧进行图生视频，确保一致性 |
| **音频合成** | - | **TTS Agent**: 自动生成角色旁白与对白 (OpenAI/ElevenLabs) |
| **后期缝合** | 简单视频拼接 + 软字幕 | **Master Assembler**: 音画同步、BGM 自动混响、SRT 硬压 |

## 2. 待办任务清单 (Roadmap)

### Phase A: 视觉一致性增强 (Visual Consistency)
- [ ] **集成 ImageGen 节点**：在 Storyboard 之后增加 ImageAgent，利用 `character_registry` 生成角色定妆照。
- [ ] **关键帧控制**：修改 `VideoGenerator` 接口，支持将生成的图片作为 `i2v` (Image-to-Video) 的输入。
- [ ] **风格迁移**：引入全局 Style LoRA 参数，确保全书视觉风格统一。

### Phase B: 听觉维度补全 (Audio Integration)
- [ ] **TTS 智能体开发**：创建 `AudioAgent`，支持根据分镜脚本中的 `dialogue` 字段生成音频。
- [ ] **情感标注**：在 Storyboard 输出中增加 `emotion` 字段，指导 TTS 生成带情感的配音。
- [ ] **智能混音**：优化 `FFmpegAssembler`，支持多轨音频（旁白、环境音、BGM） of 动态音量平衡。

### Phase C: 流程编排进阶 (Orchestration)
- [ ] **并发流水线优化**：支持图片生成与视频生成在 LangGraph 中的异步并行处理。
- [ ] **中间产物预览**：在前端 UI 中增加图片关键帧的预览与手动替换功能。

## 3. 技术选型建议
- **Image**: Flux.1 [dev] (本地) / Midjourney API (云端)
- **Audio**: OpenAI `tts-1-hd` / Bert-VITS2 (本地)
- **Control**: ComfyUI API (用于实现更精细的 I2V 控制)
