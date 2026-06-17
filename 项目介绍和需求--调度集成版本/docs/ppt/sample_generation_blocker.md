# 样张生成阻塞说明

## 当前状态

已完成：

- `docs/ppt/ppt_outline_for_review.md`
- `docs/ppt/sample_prompts/slide_01_cover.txt`
- `docs/ppt/sample_prompts/slide_05_architecture.txt`
- `docs/ppt/sample_prompts/slide_13_demo_loop.txt`

未完成：

- `docs/ppt/sample_images/slide_01.png`
- `docs/ppt/sample_images/slide_05.png`
- `docs/ppt/sample_images/slide_13.png`
- `docs/ppt/sample_preview.pptx`
- `docs/ppt/sample_speech.md`

## 阻塞原因

按照 `codex-ppt` skill 的要求，样张图片应由确认的图像生成后端生成，不能用本地绘图、HTML 截图、Pillow 或 python-pptx 手工拼图替代。

本轮首次尝试使用 `codex-ppt` 的 `image_gen.py` 生成封面样张时，本地运行时依赖已安装成功，但图像生成 API 调用被安全审批拒绝：

> 会把包含项目内容的 prompt 发送到外部 OpenAI image API，属于 workspace 数据外发，需要用户明确确认风险后才能继续。

用户确认允许外发样张 prompt 后，已再次尝试生成第 1、5、13 页样张，但外部图像 API 返回账号侧错误：

```text
Billing hard limit has been reached.
code: billing_hard_limit_reached
```

因此本轮仍未生成样张图片，也未组装 sample PPTX。

## 如需继续生成样张

请处理当前图像 API 账号的 billing hard limit，或提供可用的 `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `CODEX_PPT_IMAGE_MODEL` 配置。

处理后可继续生成：

- 第 1 页：封面
- 第 5 页：系统总体架构
- 第 13 页：Demo 演示流程 / 调度闭环
