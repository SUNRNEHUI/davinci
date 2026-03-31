#!/usr/bin/env python3
"""Build a standalone macOS DAVINCI CLI package."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "dist" / "davinci-macos-v1"
DEFAULT_BUILD_ROOT = PROJECT_ROOT / "build" / "standalone"
MANIFEST_NAME = "release-manifest.json"
TESTER_GUIDE_SOURCE = PROJECT_ROOT / "docs" / "releases" / "DAVINCI_Test_User_Guide_CN.md"
INSTALL_SCRIPT_SOURCE = PROJECT_ROOT / "install.sh"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the standalone DAVINCI macOS package.")
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory where the standalone package will be written.",
    )
    parser.add_argument(
        "--build-root",
        default=str(DEFAULT_BUILD_ROOT),
        help="Scratch directory for the PyInstaller build.",
    )
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python interpreter that has runtime deps and PyInstaller installed.",
    )
    parser.add_argument(
        "--zip",
        action="store_true",
        help="Also create a .zip archive next to the output directory.",
    )
    return parser.parse_args()


def _reset_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _pyinstaller_add_data_arg(source: Path, dest: str) -> str:
    return f"{source}{os.pathsep}{dest}"


def _ensure_pyinstaller(python_executable: str) -> None:
    result = subprocess.run(
        [python_executable, "-m", "PyInstaller", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        return
    raise RuntimeError(
        "PyInstaller is not installed for the selected Python. "
        "Run `python3 -m pip install -r requirements-build.txt` first."
    )


def _run_pyinstaller(*, python_executable: str, build_root: Path) -> Path:
    dist_root = build_root / "pyinstaller-dist"
    work_root = build_root / "pyinstaller-work"
    spec_root = build_root / "pyinstaller-spec"
    cache_root = build_root / "pyinstaller-cache"
    _reset_dir(dist_root)
    _reset_dir(work_root)
    _reset_dir(spec_root)
    _reset_dir(cache_root)

    command = [
        python_executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--name",
        "davinci",
        "--onedir",
        "--console",
        "--distpath",
        str(dist_root),
        "--workpath",
        str(work_root),
        "--specpath",
        str(spec_root),
        "--paths",
        str(PROJECT_ROOT),
        "--add-data",
        _pyinstaller_add_data_arg(PROJECT_ROOT / "flut", "flut"),
        "--add-data",
        _pyinstaller_add_data_arg(PROJECT_ROOT / "examples", "examples"),
        str(PROJECT_ROOT / "scripts" / "davinci_entry.py"),
    ]
    env = os.environ.copy()
    env["PYINSTALLER_CONFIG_DIR"] = str(cache_root)
    result = subprocess.run(command, capture_output=True, text=True, check=False, env=env)
    if result.returncode != 0:
        raise RuntimeError(
            "PyInstaller build failed.\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )

    app_dir = dist_root / "davinci"
    if not app_dir.exists():
        raise FileNotFoundError(f"Expected PyInstaller output not found: {app_dir}")
    return app_dir


def _write_launcher(output_dir: Path) -> str:
    launcher_path = output_dir / "DAVINCI.command"
    launcher_path.write_text(
        "\n".join(
            [
                "#!/bin/zsh",
                "set -e",
                'SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"',
                'export DAVINCI_CLI_HOME="${DAVINCI_CLI_HOME:-$HOME/.davinci}"',
                'cd "$SCRIPT_DIR"',
                'exec "$SCRIPT_DIR/davinci" "$@"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    launcher_path.chmod(launcher_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return launcher_path.name


def _write_readme(output_dir: Path) -> str:
    readme_path = output_dir / "README.md"
    readme_path.write_text(
        """# DAVINCI Standalone for macOS

这是不需要安装 Python 的 DAVINCI 独立版。

## 适用平台
- macOS
- Apple Silicon (`arm64`)

## 启动方式

推荐直接双击：

- `DAVINCI.command`

或者在终端里运行：

```bash
./davinci
```

## 一条命令安装

如果你已经把 `install.sh` 和 zip 放到公开地址，用户可以直接运行：

```bash
curl -fsSL "https://你的地址/install.sh" | DAVINCI_RELEASE_URL="https://你的地址/davinci-macos-v1.zip" sh
```

## 首次打开可能遇到的情况

如果 macOS 提示无法打开，请：

1. 右键 `DAVINCI.command`
2. 选择“打开”
3. 再确认一次

这是因为当前包还没有做开发者签名和 notarization。

## 使用说明

启动后会先看到 DAVINCI 首页，然后：

- 直接回车：看演示
- 输入 `1`：看 Leica
- 输入 `2`：看 Fuji
- 拖入照片或粘贴文件路径：直接开始

首次开始处理前会要求打开官网页面完成一次激活。

## 输出位置

- 正式处理结果：`~/Pictures/DAVINCI/`
- 演示结果：`~/Pictures/DAVINCI/_demo/`

## 适合 agent 调用

这个包仍然保留 CLI 形态，所以也可以直接从其他 agent 或脚本里调用：

```bash
./davinci start
./davinci demo
./davinci render --help
```
""",
        encoding="utf-8",
    )
    return readme_path.name


def _copy_tester_guide(output_dir: Path) -> str | None:
    if not TESTER_GUIDE_SOURCE.exists():
        return None
    dest = output_dir / "TESTER_GUIDE_CN.md"
    shutil.copy2(TESTER_GUIDE_SOURCE, dest)
    return dest.name


def _copy_install_script(output_dir: Path) -> str | None:
    if not INSTALL_SCRIPT_SOURCE.exists():
        return None
    dest = output_dir / "install.sh"
    shutil.copy2(INSTALL_SCRIPT_SOURCE, dest)
    dest.chmod(dest.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return dest.name


def _best_effort_codesign(binary_path: Path) -> tuple[bool, str | None]:
    if sys.platform != "darwin":
        return False, None
    result = subprocess.run(
        ["codesign", "--force", "--deep", "--sign", "-", str(binary_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        return True, None
    error = (result.stderr or result.stdout).strip() or "codesign failed"
    return False, error


def _write_manifest(
    output_dir: Path,
    copied_files: list[str],
    *,
    executable_name: str,
    signed: bool,
    sign_error: str | None,
) -> str:
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "package_name": output_dir.name,
        "platform": platform.system(),
        "architecture": platform.machine(),
        "executable": executable_name,
        "signed": signed,
        "sign_error": sign_error,
        "file_count": len(copied_files),
        "files": sorted(copied_files),
    }
    manifest_path = output_dir / MANIFEST_NAME
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return MANIFEST_NAME


def build_standalone(
    output_dir: Path,
    *,
    build_root: Path,
    python_executable: str,
    make_zip: bool = False,
) -> dict[str, str | int | bool | None]:
    output_dir = output_dir.expanduser().resolve()
    build_root = build_root.expanduser().resolve()

    _ensure_pyinstaller(python_executable)
    _reset_dir(build_root)

    pyinstaller_app = _run_pyinstaller(python_executable=python_executable, build_root=build_root)
    _reset_dir(output_dir)
    shutil.copytree(pyinstaller_app, output_dir, dirs_exist_ok=True)

    copied_files: list[str] = []
    for path in sorted(output_dir.rglob("*")):
        if path.is_file():
            copied_files.append(path.relative_to(output_dir).as_posix())

    copied_files.append(_write_launcher(output_dir))
    copied_files.append(_write_readme(output_dir))
    tester_guide = _copy_tester_guide(output_dir)
    if tester_guide is not None:
        copied_files.append(tester_guide)
    install_script = _copy_install_script(output_dir)
    if install_script is not None:
        copied_files.append(install_script)

    signed, sign_error = _best_effort_codesign(output_dir / "davinci")
    copied_files.append(
        _write_manifest(
            output_dir,
            copied_files,
            executable_name="davinci",
            signed=signed,
            sign_error=sign_error,
        )
    )

    result: dict[str, str | int | bool | None] = {
        "output_dir": str(output_dir),
        "file_count": len(copied_files),
        "platform": platform.system(),
        "architecture": platform.machine(),
        "signed": signed,
        "sign_error": sign_error,
    }
    if make_zip:
        archive_path = shutil.make_archive(
            str(output_dir),
            "zip",
            root_dir=output_dir.parent,
            base_dir=output_dir.name,
        )
        result["zip_path"] = archive_path
    return result


def main() -> int:
    args = parse_args()
    result = build_standalone(
        Path(args.output_dir),
        build_root=Path(args.build_root),
        python_executable=str(args.python),
        make_zip=args.zip,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
