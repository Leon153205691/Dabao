# -*- coding: utf-8 -*-
# Required Notice: Copyright (c) 2026 Leon153205691 (153205691@qq.com)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
"""
Dabao.py - 独立 Python EXE 打包工具

功能：
1. 弹窗选择入口 .py 文件
2. 自动寻找项目自己的 .venv / venv，也可手动选择 python.exe
3. 虚拟环境路径含中文时，自动用 subst 临时虚拟一个盘符（优先 R:）指向该环境，
   让 PyInstaller / PyQt5 看到的是纯英文路径；打包结束（无论成功失败）自动取消盘符
4. 图标可选：选图片则生成多尺寸 ICO，点取消则用默认图标
5. 打成单文件 EXE，输出到原项目的 dist 文件夹，并自动打开

安全说明：
- 不会修改、复制、移动、删除你的项目和虚拟环境
- 不会在 C 盘或其他位置创建目录联接
- 只会临时占用一个空闲盘符，结束后自动释放
- 构建临时文件放在系统临时目录，结束后自动清理
"""

import os
import sys
import json
import atexit
import importlib
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path

# ---------- 修复部分电脑上 tkinter 找不到 Tcl 的问题 ----------
_tcl = Path(sys.base_prefix) / "tcl"
if (_tcl / "tcl8.6" / "init.tcl").exists():
    os.environ.setdefault("TCL_LIBRARY", str(_tcl / "tcl8.6"))
    os.environ.setdefault("TK_LIBRARY", str(_tcl / "tk8.6"))

import tkinter as tk
from tkinter import filedialog, messagebox

ICO_SIZES = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
IMAGE_TYPES = [
    ("图片文件", ("*.png", "*.jpg", "*.jpeg", "*.bmp", "*.webp")),
    ("所有文件", "*.*"),
]
IS_WIN = platform.system() == "Windows"

# 候选盘符：优先 R，其次往后/往前，避开 A B C
DRIVE_CANDIDATES = "RSTUVWXYZQPONMLKJIHGFED"


# ============================================================
# 通用工具
# ============================================================
def pip_install(python: str, pkg: str) -> bool:
    try:
        subprocess.run([python, "-m", "pip", "install", pkg], check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def has_module(python: str, module: str) -> bool:
    r = subprocess.run(
        [python, "-c", f"import {module}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return r.returncode == 0


def ensure_pillow() -> None:
    try:
        importlib.import_module("PIL")
        return
    except ImportError:
        pass
    if not messagebox.askyesno("缺少依赖", "未检测到 Pillow，是否现在自动安装？"):
        sys.exit(1)
    if not pip_install(sys.executable, "pillow"):
        messagebox.showerror("安装失败", "请手动执行：\npip install pillow")
        sys.exit(1)
    importlib.invalidate_caches()


def select_file(title, filetypes) -> Path:
    path = filedialog.askopenfilename(title=title, filetypes=filetypes)
    if not path:
        print("未选择文件，程序退出")
        sys.exit(0)
    return Path(path).resolve()


# ============================================================
# 选择目标 Python 环境
# ============================================================
def find_project_python(entry_py: Path):
    rel = ("Scripts", "python.exe") if IS_WIN else ("bin", "python")
    folder = entry_py.parent
    for _ in range(5):
        for name in (".venv", "venv"):
            cand = folder.joinpath(name, *rel)
            if cand.exists():
                return cand
        if folder.parent == folder:
            break
        folder = folder.parent
    return None


def choose_target_python(entry_py: Path) -> str:
    found = find_project_python(entry_py)
    if found and messagebox.askyesno(
        "选择 Python 环境",
        f"检测到项目虚拟环境：\n{found}\n\n是否使用该环境打包？（推荐）",
    ):
        return str(found)

    if messagebox.askyesno(
        "选择 Python 环境",
        "是否手动选择 python.exe？\n\n"
        "请选择已安装好项目所需库的 Python 环境。\n"
        "选「否」则使用运行本工具的 Python。",
    ):
        p = filedialog.askopenfilename(
            title="选择 python.exe",
            filetypes=[("Python 解释器", "python.exe" if IS_WIN else "python*"), ("所有文件", "*.*")],
        )
        if p:
            return str(Path(p).resolve())
    return sys.executable


def ensure_pyinstaller(python: str) -> None:
    if has_module(python, "PyInstaller"):
        return
    if not messagebox.askyesno(
        "缺少 PyInstaller", f"目标环境里没有 PyInstaller：\n{python}\n\n是否自动安装到该环境？"
    ):
        sys.exit(1)
    if not pip_install(python, "pyinstaller"):
        messagebox.showerror("安装失败", "PyInstaller 安装失败，请检查网络或手动安装。")
        sys.exit(1)


# ============================================================
# 临时盘符（subst）
# ============================================================
def get_python_info(python: str) -> dict:
    """读取目标 Python 的 prefix / executable（json 转成纯 ASCII，避免乱码）。"""
    code = (
        "import sys,json;"
        "print(json.dumps({'prefix':sys.prefix,'executable':sys.executable}))"
    )
    r = subprocess.run([python, "-c", code], capture_output=True, text=True, check=True)
    return json.loads(r.stdout.strip().splitlines()[-1])


def find_free_drive():
    for letter in DRIVE_CANDIDATES:
        if not os.path.exists(f"{letter}:\\"):
            return letter
    return None


def subst_map(letter: str, target: Path) -> bool:
    subprocess.run(["subst", f"{letter}:", str(target)], capture_output=True)
    return os.path.exists(f"{letter}:\\")


def subst_remove(letter: str) -> None:
    subprocess.run(["subst", f"{letter}:", "/d"], capture_output=True)


def prepare_ascii_python(python: str):
    """
    若目标环境路径含中文，则用 subst 映射成临时盘符。
    返回 (用于打包的 python 路径, 盘符或 None)。
    任何一步失败都会安静地回退到原始 python，不影响正常打包。
    """
    if not IS_WIN:
        return python, None

    try:
        info = get_python_info(python)
        prefix = Path(info["prefix"])
        exe = Path(info["executable"])
        if str(prefix).isascii():
            return python, None  # 路径本来就是英文，无需映射
        rel_exe = exe.relative_to(prefix)
    except Exception as e:
        print(f"[提示] 无法判断环境路径，使用原路径打包：{e}")
        return python, None

    letter = find_free_drive()
    if not letter:
        print("[提示] 没有空闲盘符，使用原路径打包")
        return python, None

    if not subst_map(letter, prefix):
        print("[提示] 临时盘符创建失败，使用原路径打包")
        return python, None

    alias_python = Path(f"{letter}:\\") / rel_exe
    if not alias_python.exists():
        subst_remove(letter)
        print("[提示] 临时盘符下找不到 Python，使用原路径打包")
        return python, None

    print(f"[提示] 已临时使用 {letter}: 盘代替虚拟环境路径，打包结束后自动取消")
    return str(alias_python), letter


# ============================================================
# 图片转 ICO
# ============================================================
def image_to_ico(input_img: Path, output_ico: Path) -> None:
    from PIL import Image

    try:
        resample = Image.Resampling.LANCZOS
    except AttributeError:
        resample = Image.LANCZOS

    with Image.open(input_img) as src:
        img = src.convert("RGBA")

    w, h = img.size
    edge = min(w, h)
    x0, y0 = (w - edge) // 2, (h - edge) // 2
    img = img.crop((x0, y0, x0 + edge, y0 + edge)).resize((256, 256), resample)
    img.save(output_ico, format="ICO", sizes=ICO_SIZES)
    print("ICO 已生成")


def open_folder(folder: Path) -> None:
    if not folder.exists():
        return
    try:
        if IS_WIN:
            os.startfile(str(folder))
        elif platform.system() == "Darwin":
            subprocess.run(["open", str(folder)])
        else:
            subprocess.run(["xdg-open", str(folder)])
    except Exception as e:
        print("无法打开文件夹：", e)


# ============================================================
# 核心打包
# ============================================================
def run_pyinstaller(python: str, entry_py: Path, ico, windowed: bool, tmp: Path) -> Path:
    work_dir = entry_py.parent
    dist_dir = work_dir / "dist"
    dist_dir.mkdir(exist_ok=True)

    build_python, drive = prepare_ascii_python(python)
    if drive:
        atexit.register(subst_remove, drive)  # 万一中途被强制退出，也尽量释放盘符

    try:
        cmd = [
            build_python, "-m", "PyInstaller",
            "--noconfirm", "--clean", "-F",
            "-w" if windowed else "--console",
        ]
        if ico:
            cmd += ["-i", str(ico)]
        cmd += [
            "--distpath", str(dist_dir),
            "--workpath", str(tmp / "build"),
            "--specpath", str(tmp),
            str(entry_py),
        ]

        print("\n========== 开始打包 ==========")
        print("入口文件：", entry_py)
        print("打包 Python：", build_python)
        print("输出目录：", dist_dir)

        # 模拟「激活目标 venv 后再打包」，并去掉外部环境变量的干扰
        env = os.environ.copy()
        for key in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "PYTHONUTF8", "PYTHONIOENCODING"):
            env.pop(key, None)
        scripts_dir = Path(build_python).parent
        if (scripts_dir.parent / "pyvenv.cfg").exists():
            env["VIRTUAL_ENV"] = str(scripts_dir.parent)
        env["PATH"] = str(scripts_dir) + os.pathsep + env.get("PATH", "")

        subprocess.run(cmd, cwd=str(work_dir), check=True, env=env)

        exe = dist_dir / (entry_py.stem + (".exe" if IS_WIN else ""))
        if not exe.exists():
            raise RuntimeError("PyInstaller 已结束，但没有找到生成的 EXE。")
        return exe

    finally:
        if drive:
            subst_remove(drive)
            print(f"[提示] 临时盘符 {drive}: 已取消")


# ============================================================
# 主程序
# ============================================================
def main() -> None:
    print("========== Dabao 独立打包工具 ==========")
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    tmp = Path(tempfile.mkdtemp(prefix="dabao_"))
    try:
        entry_py = select_file("选择需要打包的 Python 入口文件", [("Python 文件", "*.py")])
        print("入口文件：", entry_py)

        python = choose_target_python(entry_py)
        if not Path(python).exists():
            raise RuntimeError("所选 Python 解释器不存在：\n" + python)
        ensure_pyinstaller(python)

        icon_path = filedialog.askopenfilename(
            title="选择 EXE 图标图片（点「取消」则使用默认图标）",
            filetypes=IMAGE_TYPES,
        )
        ico = None
        if icon_path:
            ensure_pillow()
            ico = tmp / "icon.ico"
            image_to_ico(Path(icon_path), ico)
        else:
            print("未选择图标，使用默认图标")

        windowed = messagebox.askyesno(
            "窗口模式",
            "你的程序是带界面的 GUI 程序吗？\n\n是：不显示黑色命令行窗口\n否：保留命令行窗口",
        )

        exe = run_pyinstaller(python, entry_py, ico, windowed, tmp)

        print("\n========== 打包成功 ==========")
        print("EXE 文件：", exe)
        open_folder(exe.parent)
        messagebox.showinfo("打包成功", f"EXE 已生成：\n\n{exe}")

    except subprocess.CalledProcessError as e:
        print("\n打包失败，返回代码：", e.returncode)
        messagebox.showerror("打包失败", "PyInstaller 打包失败。\n\n请查看命令行窗口中的完整错误日志。")
    except Exception as e:
        print("\n发生错误：", repr(e))
        messagebox.showerror("发生错误", str(e))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        root.destroy()


if __name__ == "__main__":
    main()
