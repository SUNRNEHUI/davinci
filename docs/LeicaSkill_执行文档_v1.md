# Leica Skills 保护方案执行文档（v1，独立 Runtime 路线）

## 1. 目标与边界

### 1.1 目标
- 支持用户下载 Skill 后在本地离线实时处理图片。
- 不分发可直接复用的 `.cube` 明文文件。
- 核心资产保护目标是“提升逆向门槛、防扩散”。
- 本项目作为独立工程运行，不依赖手机 App 工程。

### 1.2 非目标
- 不承诺 100% 防破解。
- 不在 v1 实现完整账号系统与设备风控。
- 不在 v1 实现云端渲染。

## 2. 关键结论
- 离线实时与绝对防提取不可同时成立。
- 可行折中：
  - 本地执行滤镜（体验）
  - 私有加密格式分发（防扩散）
  - 后续按需叠加许可证/设备绑定（商业控制）

## 3. 独立技术方案

### 3.1 资源层
- 新格式：`.flut`（私有封装）
- 内含：Header + metadata + AES-GCM 密文（原始 cube）

### 3.2 运行层
- 独立 Runtime（Python CLI）
- 输入：`image + .flut + key + intensity`
- 输出：处理后的图片

### 3.3 算法层（替换策略）
- 与常见 trilinear 不同，v1 默认使用 `tetrahedral interpolation`。
- 保留 `trilinear` 作为可选对照算法。
- 目的：独立实现路线，便于后续持续迭代私有渲染行为。

## 4. 用户交互（独立技能场景）

### 4.1 技能下载
- 下载 `skill 包`（含 `.flut` 与 metadata）。

### 4.2 技能调用
- 大模型仅做“意图解析与参数生成”，例如：
  - “莱卡风，强度 0.7，亮一点”
- Runtime 负责真实图像处理：
  - `apply_flut_image.py --flut ... --input ... --output ...`

### 4.3 离线
- v1 不强制联网，密钥通过本地配置注入。
- 后续可升级到许可证与离线有效期。

## 5. 数据结构（v1）

### 5.1 FLUT metadata 关键字段
- `skill_id`
- `skill_version`
- `filter_id`
- `display_name`
- `lut_domain`
- `payload_sha256`
- `created_at`

### 5.2 输入输出契约
- 输入图像：`jpg/png/webp/tiff`（由 Pillow 支持）
- 输出图像：按目标后缀写出
- 强度：`0.0 ~ 1.0`

## 6. 里程碑

### M1（已完成）
- `.flut` 私有封装格式
- pack/unpack 工具
- 基础安全测试（篡改、错密钥、回环）

### M2（本次开始，独立 Runtime）
- 新增 cube 解析器（独立实现）
- 新增 tetrahedral LUT 应用算法
- 新增图片处理 CLI（可直接用 `.flut` 处理图片）
- 新增运行时测试用例

### M3（可选）
- 增加 license token 与本地过期控制
- 增加设备绑定（Keychain/TPM/平台能力）

### M4（可选）
- 差异化 LUT（水印追踪）
- 反调试与混淆增强

## 7. 验收标准（v1+M2）
- `.flut` 不能被通用 LUT 工具直接消费。
- 使用正确密钥可处理图片并得到输出。
- 错密钥/篡改文件时运行失败。
- 算法单测通过（identity LUT 与基本一致性验证）。

