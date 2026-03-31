# DAVINCI

面向普通用户的本地调色 CLI。

你不需要先懂滤镜名，也不需要先决定 Leica / Fuji / Kodak。
DAVINCI 的目标很简单：
- 给一张照片
- 先看 3 个明显不同的方向
- 再按眼睛选一个

它不会覆盖原图，结果默认保存在 `~/Pictures/DAVINCI/`。

## 1. 本地开箱即用

### 安装依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -U pip
python3 -m pip install -r requirements.txt
python3 -m pip install -e .
```

### 第一次使用，只看这 4 条

```bash
davinci
davinci activate
davinci demo
davinci start
davinci continue
```

- `davinci`：产品首页，告诉你下一步怎么走
- `davinci activate`：手动完成一次性激活
- `davinci demo`：先看内置样片，零准备体验
- `davinci start`：处理自己的照片
- `davinci continue`：继续上一次，或重新打开上次真实存在的结果

### 推荐体验顺序

1. 先运行 `davinci` 看首页
2. 再运行 `davinci demo` 看内置演示
3. 最后运行 `davinci start` 处理自己的照片

### 用户实际会看到什么

`davinci start` 会：
- 让你把照片拖进终端，或直接粘贴路径
- 如果你不知道路径，直接回车就能打开选图窗口
- 首次交互使用时会先打开官网完成一次性激活
- 自动分析更像人像、风景还是纪实
- 直接给你 3 个白话风格方向
- 如果你输入 `莱卡` 或 `富士`，会进入单张滤镜预览窗口
- 让你输入 `1 / 2 / 3` 选一个，或说“更暖 / 更复古 / 更像胶片 / 换一个”

### 风格系列怎么理解

- `Leica`：更纪实、更有层次、更适合氛围和黑白
- `Fuji`：更清透、更日常、更像胶片直出
- `Kodak`：更暖、更复古、更有回忆感

如果你不懂这些名字，也没关系，直接说：
- `帮我调色`
- `更复古`
- `更像胶片`
- `更自然`
- `看莱卡`
- `看富士`

想先看白话解释：

```bash
davinci brands
```

### 处理自己的照片时会发生什么

`davinci start` 会：
- 先让用户把照片路径拖进来，或直接粘贴路径
- 如果直接回车，会弹出系统选图窗口
- 如果输入 `demo`，会直接切到产品演示
- 自动分析场景
- 给出 3 个白话风格方向
- 如果用户直接看 Leica / Fuji，会打开单张滤镜预览窗口
- 让用户直接选一个，或者说“换一个”
- 默认把结果放到 `~/Pictures/DAVINCI/<照片名>/`
- demo 结果默认放到 `~/Pictures/DAVINCI/_demo/<样片名>/`
- 不会覆盖原图

### 常用入口

```bash
davinci
davinci demo
davinci start
davinci continue
davinci help
davinci brands
```

如果你还没有安装 `davinci` 命令，也可以直接这样运行：

```bash
python3 -m scripts.leica_cli
```

### 继续上一次

```bash
davinci continue
```

如果有上次结果，也可以直接重新打开：

```bash
davinci continue --open
```

### 更完整的产品说明

- [DAVINCI Product PRD v1](docs/plans/DAVINCI_Product_PRD_v1.md)
- [DAVINCI Prelaunch Roundtable](docs/plans/DAVINCI_Prelaunch_Roundtable.md)

## 包含内容
- `SKILL.md`：标准 Codex skill 入口
- `agents/openai.yaml`：UI 元数据
- `scripts/leica_cli.py`：统一 CLI 入口
- `flut/leica/`：内置 Leica FLUT 滤镜、索引和运行时 key
- `flut/fuji/`：内置 Fuji Rec709 FLUT 滤镜、索引和运行时 key
- `requirements.txt`：运行依赖

### 其他常用命令

```bash
python3 -m scripts.leica_cli start
python3 -m scripts.leica_cli help
python3 -m scripts.leica_cli brands
python3 -m scripts.leica_cli continue
python3 -m scripts.leica_cli continue --interactive
python3 -m scripts.leica_cli list-catalogs
python3 -m scripts.leica_cli list-filters
python3 -m scripts.leica_cli list-filters --catalog fuji
python3 -m scripts.leica_cli recommend --input /path/to/photo.jpg --top-k 3
python3 -m scripts.leica_cli recommend --input /path/to/photo.jpg --catalog fuji --top-k 3
python3 -m scripts.leica_cli render --input /path/to/photo.jpg --filter "Leica Classic"
python3 -m scripts.leica_cli auto --input /path/to/photo.jpg --mode preview
python3 -m scripts.leica_cli auto --input /path/to/photo.jpg --choose
python3 -m scripts.leica_cli studio --input /path/to/photo.jpg --open
python3 -m scripts.leica_cli studio --input /path/to/photo.jpg --theme cipher --open
python3 -m scripts.leica_cli profile show
python3 -m scripts.leica_cli profile set --default-catalog fuji --top-k 2 --theme cipher
python3 -m scripts.leica_cli favorites add --catalog fuji --filter "Fuji Velvia / VIVID"
python3 -m scripts.leica_cli favorites list --catalog fuji
python3 -m scripts.leica_cli history list --limit 20
python3 -m scripts.leica_cli catalog validate --catalog fuji
python3 -m scripts.leica_cli catalog doctor --catalog fuji
python3 -m scripts.leica_cli workspace switch campaign-a
python3 -m scripts.leica_cli workspace list
python3 -m scripts.leica_cli sessions list --all
python3 -m scripts.leica_cli sessions show --session-id <session_id>
python3 -m scripts.leica_cli cache list
python3 -m scripts.leica_cli session --input /path/to/photo.jpg --catalog fuji
python3 -m scripts.leica_cli session --input /path/to/photo.jpg --catalog fuji --command "preview" --command "apply 1" --json
```

内置 catalog 目前有：
- `leica`
- `fuji`

## 2. 安装成 Codex skill

把仓库发布到 GitHub 后，可以直接从仓库根目录安装：

```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo <owner>/<repo> \
  --path . \
  --name davinci
```

然后重启 Codex。

安装完成后，可以直接说：
- `帮我给这张图调个莱卡感`
- `帮我给这张图来个富士味`
- `给这张照片一点胶片感`
- `先给我看几个推荐滤镜`
- `直接用 Leica Classic`

说明：
- 这个 skill 会优先使用 `python3 -m scripts.leica_cli`
- 如果用户没有给图片本地路径，agent 仍然需要先问路径

## 3. 生成发布包

如果你要产出一个可直接打包分发的独立下载目录：

```bash
python3 scripts/build_release.py --zip
```

默认会生成：
- `dist/davinci-v1/`
- `dist/davinci-v1.zip`

这个发布包里会带上：
- `SKILL.md`
- `agents/openai.yaml`
- `requirements.txt`
- `pyproject.toml`
- `examples/input_demo.png`
- `scripts/*.py`
- `flut/leica/*.flut`
- `flut/leica/runtime.key.b64`
- `flut/fuji/*.flut`
- `flut/fuji/runtime.key.b64`

## 4. 生成 macOS 独立可执行版

如果你要产出“不需要用户自己装 Python”的 macOS 独立版：

```bash
python3 -m pip install -r requirements.txt -r requirements-build.txt
python3 scripts/build_standalone.py --zip
```

默认会生成：
- `dist/davinci-macos-v1/`
- `dist/davinci-macos-v1.zip`

这个包里会有：
- `davinci`：CLI 可执行文件
- `DAVINCI.command`：双击启动器
- `README.md`
- `TESTER_GUIDE_CN.md`

当前默认产物是：
- macOS
- Apple Silicon (`arm64`)

如果你想给用户做成“一条命令安装”，可以把仓库根目录的 `install.sh` 和 `dist/davinci-macos-v1.zip` 一起发布到公开地址，然后让用户运行：

```bash
curl -fsSL "https://你的地址/install.sh" | DAVINCI_RELEASE_URL="https://你的地址/davinci-macos-v1.zip" sh
```

安装器会：
- 下载 zip
- 解压到 `~/.local/share/davinci/`
- 把 `davinci` 链接到 `~/.local/bin/davinci`
- 写一个 `~/Applications/DAVINCI.command`

对外测试文案可直接参考：
- `docs/releases/DAVINCI_Test_User_Guide_CN.md`
- `docs/releases/DAVINCI_External_Invite_Message_CN.md`

## 5. 技术结构

- `scripts/flut_codec.py`：FLUT 编解码
- `scripts/cube_runtime.py`：CUBE 解析和 LUT 插值
- `scripts/apply_flut_image.py`：单图渲染
- `scripts/leica_pipeline.py`：沉浸式流程和 contact sheet
- `scripts/leica_cli.py`：统一命令面
- `scripts/build_release.py`：构建独立发布包
- `scripts/build_standalone.py`：构建 macOS 独立可执行包
- `scripts/blackroom_console.py`：Blackroom Studio 终端体验层
- `scripts/leica_product_store.py`：profile、workspace、history、session 状态存储
- `scripts/leica_session.py`：交互式 session workbench
- `scripts/leica_catalog_validate.py`：catalog validate / doctor
- `scripts/leica_render_cache.py`：contact sheet / top1 render 缓存
- `scripts/pack_catalog_flut.py`：通用 cube -> flut catalog 打包器
- `flut/*/index.json`：内置滤镜目录

## 6. 依赖

- `numpy`
- `Pillow`
- `cryptography`
- `PyInstaller`（仅独立版打包时需要，见 `requirements-build.txt`）

## 7. 测试

```bash
python3 -m pytest -q
```

## 8. 保护边界

当前仓库为了“下载即可用”，默认把 `runtime.key.b64` 和滤镜一起分发。

这意味着：
- 用户不需要手工提供 key
- 但资产保护强度会明显下降

如果你后面要做商业版，建议把公开版和商业版拆开：
- 公开版：开源 runtime + skill
- 商业版：服务端授权 / 设备绑定 / 密钥轮换 / 私有滤镜包

## 8. 增加新品牌滤镜

未来增加 Kodak 或其他风格时，建议走同一条路径：

```bash
python3 scripts/pack_catalog_flut.py \
  --catalog-dir /path/to/cube_dir \
  --output-dir /path/to/flut/catalog_name \
  --index-file /path/to/flut/catalog_name/index.json \
  --manifest /path/to/catalog_name/manifest.json \
  --filter-prefix catalog_name \
  --skill-id catalog_name.skill.rec709 \
  --key-file /path/to/runtime.key.b64
```

推荐把 catalog 元数据直接写进 `manifest.json`，这样未来增加 Kodak、Agfa、电影风格时，不需要再改 Python 映射。

最小 manifest 结构：

```json
{
  "catalog": "kodak",
  "display_name": "Kodak Rec709",
  "skill_id": "kodak.skill.rec709",
  "skill_version": "1.0.0",
  "lut_domain": "rec709",
  "scene_filters": {
    "portrait": ["kodak_portra_400"],
    "landscape": ["kodak_ektar_100"],
    "general": ["kodak_portra_400", "kodak_gold_200"]
  },
  "filters": [
    {
      "source_cube": "Portra400.cube",
      "filter_id": "kodak_portra_400",
      "display_name": "Kodak Portra 400",
      "reason": "Soft pastel color for daylight portraits.",
      "aliases": ["portra 400"]
    }
  ]
}
```

硬性约束：
- `manifest.json` 里的 `filters` 必须是非空数组
- 每个滤镜至少要有 `source_cube`、`filter_id`、`display_name`
- `filter_id` 不能重复
- `scene_filters` 里只能写 `filter_id`
- `scene_filters` 里引用的每个 `filter_id` 都必须真的存在于 `filters`
- `aliases` 如果提供，必须是字符串数组

打包完成后：
- `flut/<catalog>/index.json` 给渲染层读取
- `flut/<catalog>/manifest.json` 给 CLI 推荐系统读取
- 运行时会优先用 manifest 里的 `display_name`、`aliases`、`reason`、`scene_filters`
- 如果 CLI 使用 `--index /path/to/index.json`，也会优先读取同目录的 `manifest.json`
