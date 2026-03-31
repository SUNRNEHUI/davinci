# Runtime 独立 M2 实现说明

## 1. 模块划分
- `flut_codec.py`：私有格式 pack/unpack
- `cube_runtime.py`：CUBE 解析与 LUT 插值算法
- `apply_flut_image.py`：图片处理 CLI，连接格式层与算法层

## 2. 处理流程
1. 读取 `.flut`
2. 用 key 解密得到 cube bytes
3. 解析为 LUT3D 数据结构
4. 读取输入图片（RGB/RGBA）
5. 执行 LUT 插值（tetrahedral / trilinear）
6. 按 intensity 混合后输出

## 3. 性能与准确性
- tetrahedral 通常在相同 LUT 分辨率下较 trilinear 有更平滑的色彩过渡。
- v1 实现以可读性和可验证性为主；若要上生产可考虑：
  - NumPy 向量化进一步优化
  - C++/Rust 扩展
  - GPU 实现

## 4. 安全说明
- v1 仍属于“提高门槛”方案。
- 若对抗高强度逆向，需要叠加许可证、设备绑定、密钥轮换和风控。

