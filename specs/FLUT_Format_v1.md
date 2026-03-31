# FLUT Format v1 规范（私有 LUT 封装）

## 1. 目标
- 将 `.cube` 内容封装为私有格式，避免被广泛直接复用。
- 支持完整性校验与认证解密。
- 支持元数据携带（skill、滤镜、域、版本）。

## 2. 文件布局（v1）

二进制布局：

1. Header（固定 24 字节）
2. Metadata JSON（变长，`metadata_len` 指定）
3. Ciphertext（变长，AES-GCM 输出，含认证标签）

### 2.1 Header
- `magic` (4 bytes): `FLUT`
- `version` (1 byte): `0x01`
- `algorithm` (1 byte): `0x01`（AES-256-GCM）
- `flags` (1 byte): 预留，当前固定 `0`
- `reserved` (1 byte): 预留，当前固定 `0`
- `metadata_len` (4 bytes, big-endian)
- `nonce` (12 bytes): AES-GCM nonce

## 3. Metadata JSON
UTF-8 编码，建议字段：
- `skill_id`
- `skill_version`
- `filter_id`
- `display_name`
- `lut_domain` (`rawDecoded` / `rec709`)
- `source_format` (`cube`)
- `payload_sha256`（原始 cube 明文 hash）
- `created_at`

说明：
- Metadata 原文作为 AES-GCM AAD（附加认证数据）。
- 修改 Metadata 会导致解密认证失败。

## 4. 加解密
- 算法：AES-256-GCM
- 密钥长度：32 bytes
- nonce：12 bytes（随机生成）
- AAD：metadata bytes
- 明文：原始 `.cube` 文件 bytes
- 密文：`ciphertext || tag`（由库实现）

## 5. 校验
解密后必须执行：
1. `sha256(plaintext)` == `metadata.payload_sha256`
2. 版本与算法号合法
3. Metadata JSON 可解析且关键字段存在

## 6. 安全注意事项
- v1 只定义内容封装，不含许可证系统。
- 生产环境需叠加：设备绑定、短期许可证、吊销、密钥轮换。

