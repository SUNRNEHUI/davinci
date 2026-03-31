# DAVINCI

把一张照片交给 DAVINCI。

它不会先丢给你一长串滤镜名，而是先给你 3 个明显不同的方向，再让你按眼睛选一个。

当前内置两条主线：
- `Leica`：更有氛围，适合纪实、街头、黑白、人像
- `Fuji`：更清透，适合日常、旅行、胶片感

结果默认保存到 `~/Pictures/DAVINCI/`，原图不会被覆盖。

## 一条命令安装

当前公开发布的是 `macOS Apple Silicon` 独立版，不需要自己装 Python。

```bash
curl -fsSL "https://github.com/SUNRNEHUI/davinci/releases/download/v0.1.0/install.sh" | DAVINCI_RELEASE_URL="https://github.com/SUNRNEHUI/davinci/releases/download/v0.1.0/davinci-macos-v1.zip" sh
```

安装完成后直接运行：

```bash
davinci
```

Release 页面：

- [DAVINCI v0.1.0](https://github.com/SUNRNEHUI/davinci/releases/tag/v0.1.0)

## 第一次使用

你真正只需要记住这 4 条：

```bash
davinci
davinci demo
davinci start
davinci continue
```

- `davinci`：进入首页
- `davinci demo`：先看演示，不用准备照片
- `davinci start`：处理自己的照片
- `davinci continue`：继续上一次

## 用户会经历什么

1. 打开 DAVINCI 首页
2. 直接回车看演示，或者输入 `1` 看 Leica，输入 `2` 看 Fuji
3. 首次真正开始处理前，会打开官网做一次激活
4. 拖入照片或粘贴路径
5. 先看 3 个不同方向，或者直接进入 Leica / Fuji 全量预览
6. 选中一个，直接保存成片

如果你已经知道自己想要什么，也可以直接说：

- `看莱卡`
- `看富士`
- `更复古`
- `更自然`
- `更像胶片`

## 为什么它像产品，而不是工具脚本

- 不要求先懂滤镜名
- 先比较，再决定
- 有首页、演示、继续上一次、激活、预览和保存链路
- 支持键盘选择，也支持自然语言描述
- 保留 CLI 形态，所以人和 agent 都能用

## 适合谁

- 想快速把照片变成 Leica / Fuji 方向的人
- 不想先学一堆 LUT 和命名体系的人
- 想保留 CLI 可调用能力的个人工作流
- 想被 agent 直接调用的本地调色工具链

## 适合 agent / 自动化

DAVINCI 不是 GUI App 壳子，核心仍然是 CLI，所以可以直接被 agent、脚本或别的本地工作流调用。

例如：

```bash
davinci demo
davinci start
davinci render --help
python3 -m scripts.leica_cli auto --input /path/to/photo.jpg --json
```

也可以作为本地 Codex skill 使用：

```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo SUNRNEHUI/davinci \
  --path . \
  --name davinci
```

## 仓库里有什么

- `scripts/leica_cli.py`：统一 CLI 入口
- `scripts/build_standalone.py`：构建独立可执行版
- `scripts/build_release.py`：构建源码发布包
- `install.sh`：一条命令安装器
- `flut/leica/`：Leica 风格滤镜资源
- `flut/fuji/`：Fuji 风格滤镜资源
- `docs/releases/`：外部测试说明文案

## 从源码运行

如果你不是终端用户，而是开发者，可以直接从源码跑：

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -U pip
python3 -m pip install -r requirements.txt
python3 -m pip install -e .
davinci
```

或者不安装命令入口，直接：

```bash
python3 -m scripts.leica_cli
```

## 构建发布物

源码发布包：

```bash
python3 scripts/build_release.py --zip
```

macOS 独立可执行版：

```bash
python3 -m pip install -r requirements.txt -r requirements-build.txt
python3 scripts/build_standalone.py --zip
```

## 文档

- [测试版使用说明](docs/releases/DAVINCI_Test_User_Guide_CN.md)
- [外部测试邀请文案](docs/releases/DAVINCI_External_Invite_Message_CN.md)
- [FLUT 格式说明](specs/FLUT_Format_v1.md)

## 当前边界

- 当前公开独立版只支持 `macOS Apple Silicon`
- 首次处理前会做一次官网激活
- 当前仍然是 CLI 产品，不是桌面 GUI App
- 为了开箱即用，运行时 key 与资源一起分发，所以资产保护强度不是最终商业形态
