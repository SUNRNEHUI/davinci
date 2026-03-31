---
name: davinci
description: Use this skill when users want local photo color grading, Leica or Fuji looks, film-like previews, contact sheets, or direct FLUT rendering. Triggers on: 调色, 滤镜, 莱卡滤镜, 富士滤镜, Leica look, Fuji look, 胶片感, film look, color grade.
---

# DAVINCI

## When to use
- User wants to color grade a local image.
- User asks for a Leica look, Fuji look, film look, contact sheet, or filter recommendation.
- User wants a specific filter, stronger/weaker intensity, or a preview before final render.

## Preconditions
- The skill is self-contained: shipped filters live in `flut/leica/`, runtime scripts live in `scripts/`.
- Fuji assets also ship inside `flut/fuji/`.
- Install Python dependencies from `requirements.txt` if the runtime is not ready.
- If the user shared an image but did not provide a local file path, ask for the path before running commands.

## Default workflow
1. Parse intent.
2. Prefer the unified CLI from the skill root:

```bash
python3 -m scripts.leica_cli auto --input <IMAGE_PATH> --open
```

3. Return the generated contact sheet path and final image path.

## Intent mapping
- Broad request like “帮我调色” or “来点莱卡味”: use `auto`.
- “先看看效果” or “给我推荐几个”: use `recommend`.
- “列出有哪些滤镜”: use `list-filters`.
- “用 Classic” or “第 3 个”: use `render --filter <selection>`.
- “只要预览，不要出最终图”: use `auto --mode preview`.
- “浓一点 / 淡一点”: map roughly to `0.95 / 0.55`; default is `0.85`.

## Commands

Full auto preview + top1 render:

```bash
python3 -m scripts.leica_cli auto --input <IMAGE_PATH> --open
```

Preview only:

```bash
python3 -m scripts.leica_cli auto --input <IMAGE_PATH> --mode preview
```

Recommend filters:

```bash
python3 -m scripts.leica_cli recommend --input <IMAGE_PATH> --top-k 3
```

Apply one exact filter:

```bash
python3 -m scripts.leica_cli render --input <IMAGE_PATH> --filter "Leica Classic" --intensity 0.85
```

Stable machine-readable output:

```bash
python3 -m scripts.leica_cli auto --input <IMAGE_PATH> --json
```

## Notes
- The shipped package auto-discovers `runtime.key.b64` beside the filter index, so end users do not need to pass a key manually.
- If the user wants a custom `.flut` outside the shipped package, fall back to `scripts/apply_flut_image.py` with explicit `--flut`.
