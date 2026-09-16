<div align="center">

# CodexQuotaMonitor 📊

### 把 Codex 额度留在 Windows 系统托盘里

一个轻量、离线运行的 Windows Codex 本地额度监控工具。

从本机 Codex session 日志中提取 `rate_limits`，显示 5 小时（5H）与 7 天（Weekly）剩余额度、重置时间和最近更新时间。

[![Latest Release](https://img.shields.io/github/v/release/CN-Movn/CodexQuotaMonitor?display_name=tag&style=flat-square&label=Latest%20Release)](https://github.com/CN-Movn/CodexQuotaMonitor/releases/latest)
[![GitHub Actions CI](https://img.shields.io/github/actions/workflow/status/CN-Movn/CodexQuotaMonitor/ci.yml?branch=main&style=flat-square&label=CI)](https://github.com/CN-Movn/CodexQuotaMonitor/actions/workflows/ci.yml)
[![Windows 10 / 11](https://img.shields.io/badge/Windows-10%20%2F%2011-0078D4?style=flat-square&logo=windows&logoColor=white)](#环境要求)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)](#环境要求)
[![Runtime: Standard Library](https://img.shields.io/badge/Runtime-Standard%20Library-2F3437?style=flat-square)](#隐私与安全)
[![MIT License](https://img.shields.io/badge/License-MIT-346538?style=flat-square)](./LICENSE)

[为什么有这个工具](#为什么有这个工具) · [核心能力](#核心能力) · [快速开始](#快速开始) · [隐私与安全](#隐私与安全) · [工作原理](#工作原理) · [源码运行](#源码运行) · [构建 EXE](#构建-exe)

</div>

> **Unofficial community project.** This project is not affiliated with or endorsed by OpenAI.

---

## 为什么有这个工具

Codex 的额度信息已经存在于本机 session 日志中，但日常使用时不适合反复打开日志、搜索字段、手工换算。

CodexQuotaMonitor 的目标是：

- 本地读取 Codex session 日志；
- 从 `rate_limits` 中识别 5H / Weekly 窗口；
- 把剩余额度、重置时间、更新时间显示在 Windows 通知区域；
- 不调用 OpenAI API；
- 不需要额外 Token；
- 不主动建立网络连接。

> **核心目标：让“还剩多少 Codex 额度”变成一个随时可见、无需打断工作流的信息。**

## 核心能力

| 能力 | 说明 |
| --- | --- |
| 5H + Weekly 双窗口 | 同时显示 5 小时与 7 天窗口剩余额度 |
| 系统托盘常驻 | 在 Windows 通知区域查看额度 |
| 重置时间 | 显示额度重置时间和最近更新时间 |
| 后台刷新 | 自动扫描本地日志，并支持手动刷新；包含低频强制全量复核 |
| 开机启动 | 支持当前用户开机启动，不修改注册表 |
| 零网络依赖 | 不调用 OpenAI API，也不主动联网 |
| 零运行时第三方依赖 | 源码运行仅依赖 Python 标准库 |
| 独立 EXE | Release 提供 Windows 单文件版本 |

## 快速开始

### 普通用户

前往 [GitHub Releases](https://github.com/CN-Movn/CodexQuotaMonitor/releases/latest)，下载最新的：

```text
CodexQuotaMonitor_v*.exe
```

Release EXE 不需要安装 Python、Conda 或 PyInstaller。双击后，程序会驻留 Windows 通知区域；鼠标悬停托盘图标即可查看额度卡片。

### 源码用户

```powershell
git clone https://github.com/CN-Movn/CodexQuotaMonitor.git
cd CodexQuotaMonitor
py src\main.py
```

只扫描一次并输出当前解析结果：

```powershell
py src\main.py --scan
```

如果系统没有 `py` launcher，可以使用：

```powershell
python src\main.py
```

## 隐私与安全

程序只读取当前用户 Codex 本地 session 日志：

```text
%USERPROFILE%\.codex\sessions\**\*.jsonl
```

程序明确不会：

- 读取 `%USERPROFILE%\.codex\auth.json`；
- 读取、保存或上传 Token、Cookie、API Key；
- 调用 OpenAI API；
- 使用 `requests`、`urllib`、`socket`、WebSocket 或浏览器联网；
- 上传 Codex session 日志或会话正文；
- 修改 Codex 本地数据；
- 修改注册表。

开机启动使用当前用户 Startup 文件夹中的 `CodexQuotaMonitor.vbs`。该文件只保存本地 EXE 启动路径，关闭开机启动时只删除本工具创建的文件。

> 程序本身完全离线。读取 JSONL 只用于本地筛选和额度解析。

## 工作原理

```text
Codex session JSONL
        │
        ▼
逐行筛选包含 rate_limits 的记录
        │
        ▼
按 window_minutes 识别窗口
        │
        ├── 300 分钟   → H / 5 小时窗口
        └── 10080 分钟 → W / Weekly 窗口
        │
        ▼
remaining_percent = 100 - used_percent
        │
        ▼
Windows 通知区域悬停卡片
```

当前支持的典型字段：

```text
record.timestamp
record.payload.type == "token_count"
record.payload.rate_limits.primary.used_percent
record.payload.rate_limits.primary.window_minutes == 300
record.payload.rate_limits.secondary.used_percent
record.payload.rate_limits.secondary.window_minutes == 10080
```

解析器同时兼容：

- 顶层或 payload 中的 `rate_limits`；
- 字段名变化和缺失字段；
- 无关 JSONL 记录；
- Codex 正在写入时产生的不完整尾行；
- 不同 session 文件之间的时间顺序差异。

## 环境要求

- Windows 10 / 11
- Windows x64 推荐
- Python 3.10+（仅源码运行或自行构建需要）
- Release EXE 无 Python 运行时依赖

不需要管理员权限。程序只读取当前用户自己的 Codex 日志目录和 Startup 文件夹。

## 源码运行

运行程序：

```powershell
py src\main.py
```

运行单元测试：

```powershell
py -m unittest discover -s tests -p "test_*.py" -v
```

检查 Python 源码编译：

```powershell
py -m compileall -q src tests
```

运行 Windows UI smoke test：

```powershell
py src\main.py --smoke-test
```

## 构建 EXE

运行时使用 Python 标准库；只有构建 EXE 时需要 PyInstaller。

推荐在项目目录创建独立虚拟环境：

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

构建脚本会：

1. 验证 Python 和 PyInstaller 环境；
2. 运行单元测试与 `compileall`；
3. 生成托盘图标资源；
4. 调用 PyInstaller 构建 onefile EXE；
5. 将结果写入项目同级 Release 目录。

默认构建：

```powershell
.\scripts\build.ps1
```

指定 Release 输出目录：

```powershell
.\scripts\build.ps1 -ReleaseDir "..\CodexQuotaMonitor_release"
```

默认输出：

```text
..\CodexQuotaMonitor_release\CodexQuotaMonitor_v1.4.exe
```

构建期间产生的 `build/`、`dist/`、`__pycache__/` 和 PyInstaller 中间文件均属于本地生成物，不应提交到 Git 仓库。

## 项目结构

```text
CodexQuotaMonitor/
├─ .github/
│  └─ workflows/ci.yml
├─ assets/
│  └─ CodexQuotaMonitor.ico
├─ scripts/
│  ├─ build.ps1
│  └─ create_icon.py
├─ src/
│  ├─ __init__.py
│  ├─ main.py
│  ├─ scanner.py
│  └─ windows_app.py
├─ tests/
│  └─ test_scanner.py
├─ .gitignore
├─ CodexQuotaMonitor.spec
├─ LICENSE
├─ README.md
└─ requirements-dev.txt
```

## 常见问题

### 为什么额度没有立即变化？

程序通常每 3 秒检查一次文件变化，并定期进行强制全量复核。Codex 本身只有在产生新的本地 session 记录后，日志才会出现新的额度状态。

### 是否需要管理员权限？

不需要。程序只访问当前用户目录；开机启动也使用当前用户 Startup 文件夹，不修改注册表。

### 更换电脑或移动 EXE 后，开机启动怎么办？

移动或改名 EXE 后，请先关闭再重新开启开机启动，让 Startup 脚本写入新的绝对路径。

## License

MIT License. See [LICENSE](./LICENSE).
