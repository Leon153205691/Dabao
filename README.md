# Dabao — Python 一键打包 EXE 工具

![License: PolyForm Noncommercial](https://img.shields.io/badge/License-PolyForm%20Noncommercial%201.0.0-blue.svg)
![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey.svg)

Dabao 是一个带图形弹窗的 PyInstaller 打包助手：选文件、选图标、点几下，就能把任意 `.py` 程序打成单文件 `.exe`，不用再记命令行参数。

> **English:** Dabao is a small GUI wrapper around PyInstaller. Pick a script, optionally pick an icon image, and it builds a single-file `.exe` using the project's own virtual environment. On Windows it can temporarily map a drive letter (via `subst`) to work around non-ASCII path problems, and removes it afterwards.

---

## 功能特性

- 弹窗选择入口 `.py` 文件，文件名不限
- 自动识别项目自己的虚拟环境（`.venv` / `venv`），也可手动指定 `python.exe`，保证用「装好了依赖库的环境」来打包
- 图标可选：选一张 png / jpg / bmp / webp 图片，自动居中裁成正方形并生成 16–256 多尺寸 ICO；点「取消」则使用默认图标
- 可选择 GUI 模式（无黑色命令行窗口）或控制台模式
- 虚拟环境路径含中文时，自动临时映射一个英文盘符（优先 `R:`）以规避 Qt 等库的路径问题，打包结束后自动取消
- 构建临时文件放在系统临时目录，结束后自动清理；EXE 输出到原项目的 `dist` 文件夹并自动打开
- 不会修改、复制或删除你的项目和虚拟环境

## 环境要求

- Windows 10 / 11（目前仅在 Windows 下设计和使用）
- Python 3.8 及以上（建议 3.10+）
- 运行本工具本身只需要 [Pillow](https://pypi.org/project/pillow/)（仅在你选择了图标时才会用到）
- [PyInstaller](https://pyinstaller.org/) 安装在**你要打包的项目环境**里（缺失时本工具会询问是否自动安装）

## 安装

```bash
git clone https://github.com/Leon153205691/Dabao.git
cd Dabao
pip install -r requirements.txt
```

## 使用方法

```bash
python Dabao.py
```

然后按弹窗提示操作：

1. 选择要打包的入口 `.py` 文件
2. 选择 Python 环境（检测到项目 `.venv` 时推荐直接用它）
3. 选择图标图片（不需要图标就点「取消」）
4. 选择窗口模式：GUI 程序选「是」，控制台程序选「否」
5. 等待打包完成，`dist` 文件夹会自动打开

> **重要：** 打包出来的 EXE 只包含「所选 Python 环境」里已安装的库。你的程序用到的第三方库（如 PyQt5、numpy 等）必须先装在那个环境里。

## 工作原理

Dabao 本质上是在帮你调用：

```bash
<目标环境的python> -m PyInstaller --noconfirm --clean -F [-w] [-i icon.ico] your_script.py
```

并额外做了这些事：

- 用目标环境自己的 Python 调用 PyInstaller，而不是当前运行 Dabao 的 Python
- 清除可能干扰的环境变量（`PYTHONPATH`、`PYTHONHOME`、`VIRTUAL_ENV` 等），模拟「在项目终端里激活虚拟环境后再打包」
- 环境路径含非 ASCII 字符时，用 Windows 自带的 `subst` 临时虚拟一个盘符指向该环境，打包结束后执行 `subst X: /d` 取消；该盘符只是一个快捷入口，不会改动里面的任何文件

## 常见问题

**打包后运行报 `No module named 'xxx'`**
说明打包时用的 Python 环境里没有装这个库。请确认弹窗里选择的是装了项目依赖的环境，补装后重新打包。

**路径里有中文，PyInstaller 报 Qt plugin directory does not exist**
这是已知的中文路径兼容问题，Dabao 会尝试用临时盘符绕开。如果仍然失败，可以把虚拟环境建在纯英文路径下，再在弹窗里手动选择它的 `python.exe`。

**临时盘符会残留吗？**
正常结束或报错退出时都会自动取消。若进程被强行结束，可手动运行 `subst R: /d`（把 `R` 换成实际盘符），或重启电脑，`subst` 创建的盘符重启后自动消失。

**杀毒软件报毒**
PyInstaller 打出的单文件 EXE 偶尔会被部分杀毒软件误报，属于常见现象，可自行添加信任或改用 `--onedir` 模式。

## 已知限制

- 仅支持 Windows
- 临时盘符方案对特定库（如 PyQt5）的中文路径问题是否有效，取决于具体环境，欢迎通过 Issue 反馈
- 目前只提供单文件（`-F`）模式

## 项目结构

```
.
├── Dabao.py          # 主程序
├── requirements.txt  # 运行本工具所需依赖
├── LICENSE           # 开源许可证
└── README.md
```

## 参与贡献

欢迎提交 Issue 和 Pull Request。提交贡献即表示你同意按本项目的许可证授权你的贡献，并允许作者在包括商业授权在内的方式下使用它。

## 许可证与版权

本项目源码公开，基于 [PolyForm Noncommercial License 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0) 授权（详见 [LICENSE](./LICENSE)）。

Copyright (c) 2026 Leon153205691

- **允许**：个人学习、研究、兴趣项目，以及教育机构、公益组织等非商业用途下的使用、修改和分发（需保留版权声明和许可证）
- **不允许**：未经许可将本项目用于商业目的，包括出售、放入收费产品或服务中使用
- **商业授权**：如需商用，请联系作者获取单独授权：153205691@qq.com

注意：本项目采用的是「源码公开（source-available）」许可证，**不属于** OSI 定义的开源许可证。本软件按「现状」提供，不附带任何形式的担保。

## 致谢

- [PyInstaller](https://pyinstaller.org/)
- [Pillow](https://python-pillow.org/)
