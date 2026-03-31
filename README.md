# SenseAR DAVINCI

把一张照片交给 SenseAR DAVINCI。

它不会先丢给你一长串滤镜名，而是先给你 3 个明显不同的方向，再让你按眼睛选一个。

当前内置两条主线：
- `Leica`：更有氛围，适合纪实、街头、黑白、人像
- `Fuji`：更清透，适合日常、旅行、胶片感

结果默认保存到 `~/Pictures/DAVINCI/`，原图不会被覆盖。

想了解更多有关 SenseAR 特效引擎的功能与完整能力，欢迎访问官网：
https://sensear.softsugar.com/

## 命令行安装

当前只正式支持 `macOS` 的 `davinci` CLI。

### macOS

最省事的方式：

```bash
curl -fsSL "https://raw.githubusercontent.com/SUNRNEHUI/davinci/main/install.sh" | sh
```

或者直接用 `pipx`：

```bash
python3 -m pip install --user pipx
python3 -m pipx ensurepath
python3 -m pipx install "davinci-cli @ https://github.com/SUNRNEHUI/davinci/archive/refs/heads/main.zip"
```

安装完成后运行：

```bash
davinci
```

### 不想装 Python

当前只有 `macOS Apple Silicon` 提供免 Python 的独立下载版：

```bash
curl -fsSL "https://github.com/SUNRNEHUI/davinci/releases/download/v0.1.1/install.sh" | DAVINCI_RELEASE_URL="https://github.com/SUNRNEHUI/davinci/releases/download/v0.1.1/davinci-macos-v1.zip" sh
```

Release 页面：

- [DAVINCI v0.1.1](https://github.com/SUNRNEHUI/davinci/releases/tag/v0.1.1)

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
- `install.sh`：macOS 命令行安装脚本
- 内置风格资源与运行时文件
- `docs/releases/`：外部测试说明文案

## 开发者从源码运行

普通用户优先使用上面的 `install.sh` / `pipx` 安装方式。

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

说明：

- 当前正式支持目标是 `macOS`
- 当前最像通用开源工具的安装方式是 `pipx install ...`
- 免 Python 独立包目前仍然只有 `macOS Apple Silicon`

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

## License

本项目采用 [GNU Affero General Public License v3.0](LICENSE)。

- 这是 OSI 认可的开源许可证
- 允许商业使用
- 如果你修改了程序，并通过网络服务对外提供它，通常也需要向用户提供对应源码

品牌名和 Logo 不跟随 AGPL 自动开放，见 [TRADEMARK.md](TRADEMARK.md)。

## 当前边界

- 当前只正式支持 `macOS` CLI
- 免 Python 的官方独立包目前只支持 `macOS Apple Silicon`
- `Windows` 和 `Linux` 暂不在当前发布范围内
- 首次处理前会做一次官网激活
- 当前仍然是 CLI 产品，不是桌面 GUI App
- 仓库中仍然包含实现层资源；如果后续要进一步收口，需要继续调整公开仓库与发布结构
