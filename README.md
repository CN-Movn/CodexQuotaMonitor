<div align="center">

# CodexQuotaMonitor 📊

### 把 Codex 额度留在 Windows 系统托盘里

轻量、离线运行的 Windows Codex 本地额度监控工具。  
从本机 Codex session 日志中提取 `rate_limits`，显示 **5 小时（5H）** 与 **7 天（Weekly）** 剩余额度、重置时间和最近更新时间。

<p>
  <a href="https://github.com/CN-Movn/CodexQuotaMonitor/releases/latest"><img src="https://img.shields.io/github/v/release/CN-Movn/CodexQuotaMonitor?display_name=tag&style=flat-square&label=Release" alt="Release"></a>
  <a href="https://github.com/CN-Movn/CodexQuotaMonitor/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/CN-Movn/CodexQuotaMonitor/ci.yml?branch=main&style=flat-square&label=CI" alt="CI"></a>
  <img src="https://img.shields.io/badge/Windows-10%20%2F%2011-0078D4?style=flat-square&logo=windows&logoColor=white" alt="Windows 10 / 11">
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/Runtime-Standard%20Library-555?style=flat-square" alt="Standard Library">
  <a href="./LICENSE"><img src="https://img.shields.io/badge/License-MIT-2f855a?style=flat-square" alt="MIT License"></a>
</p>

[为什么有这个工具](#为什么有这个工具) · [核心能力](#核心能力) · [快速开始](#快速开始) · [隐私与安全](#隐私与安全) · [工作原理](#工作原理) · [源码运行](#源码运行) · [构建-exe](#构建-exe)

</div>

> **Unofficial community project.** This project is not affiliated with or endorsed by OpenAI.

---

## 为什么有这个工具

Codex 的额度信息已经存在于本机 session 日志中，但日常使用时并不适合反复打开日志、搜索字段、手工换算。

CodexQuotaMonitor 做的事情很简单：

- 本地读取 Codex session 日志；
- 从 `rate_limits` 中识别 5H / Weekly 窗口；
- 计算剩余额度；
- 把剩余额度、重置时间和最近更新时间显示在 Windows 通知区域；
- 不调用 OpenAI API，不需要额外 Token，也不主动建立网络连接。

> **核心目标：让“还剩多少 Codex 额度”变成一个随时可见、无需打断工作流的信息。**

## 核心能力

| 能力 | 说明 |
| --- | --- |
| **5H + Weekly 双窗口** | 同时显示 5 小时与 7 天窗口剩余额度 |
| **系统托盘常驻** | 在 Windows 通知区域快速查看额度状态 |
| **重置时间** | 显示额度重置时间和最近更新时间 |
| **后台刷新** | 自动扫描本地日志，并支持手动刷新与低频强制复核 |
| **开机启动** | 支持当前用户开机启动，不修改注册表 |
| **零网络依赖** | 不调用 OpenAI API，也不主动联网 |
| **零运行时第三方依赖** | 源码运行仅依赖 Python 标准库 |
| **独立 EXE** | GitHub Releases 提供可直接运行的 Windows 单文件版本 |

## 快速开始

### 普通用户

前往 [GitHub Releases](https://github.com/CN-Movn/CodexQuotaMonitor/releases/latest)，下载最新的：

```text
CodexQuotaMonitor_v*.exe
```

Release EXE 不需要安装 Python、Conda 或 PyInstaller。双击运行后，程序会驻留 Windows 通知区域。

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

如果系统没有 `py` launcher：

```powershell
python src\main.py
```

## 隐私与安全

程序只在本地扫描当前用户的 Codex session 日志：

```text
%USERPROFILE%\.codex\sessions\**\*.jsonl
```

扫描器逐行寻找包含 `rate_limits` 的记录，并从对应 JSON 中提取额度窗口字段。

程序不会：

- 读取 `%USERPROFILE%\.codex\auth.json`；
- 读取、保存或上传认证 Token、Cookie、API Key；
- 调用 OpenAI API；
- 主动通过 `requests`、`urllib`、`socket`、WebSocket 或浏览器联网；
- 上传 Codex session 日志或会话正文；
- 修改 Codex 本地数据；
- 为开机启动修改注册表。

> 为了定位 `rate_limits`，程序需要在本地逐行读取 session JSONL 文件。读取仅用于本地筛选和额度解析。

开机启动通过当前用户 Startup 文件夹中的 `CodexQuotaMonitor.vbs` 实现；关闭开机启动时，仅删除本工具创建的启动文件。

## 工作原理

```text
%USERPROFILE%\.codex\sessions\**\*.jsonl
                    │
                    ▼
              本地日志扫描器
                    │
          筛选 rate_limits 记录
                    │
          ┌─────────┴─────────┐
          ▼                   ▼
      300 min              10080 min
      5H window          Weekly window
          │                   │
          └─────────┬─────────┘
                    ▼
        remaining = 100 - used
                    │
                    ▼
             Windows Tray UI
```

当前支持的典型字段结构：

```text
record.timestamp
record.payload.type == "token_count"
record.payload.rate_limits.primary.used_percent
record.payload.rate_limits.primary.window_minutes == 300
record.payload.rate_limits.secondary.used_percent
record.payload.rate_limits.secondary.window_minutes == 10080
```

剩余额度计算：

```text
remaining_percent = 100 - used_percent
```

解析器同时兼容无关 JSONL 记录、字段缺失、部分字段名变化、损坏或尚未写完的尾行，以及不同 session 文件之间的时间顺序差异。

## 环境要求

| 场景 | 要求 |
| --- | --- |
| 直接运行 Release EXE | Windows 10 / 11 |
| 从源码运行 | Windows 10 / 11，Python 3.10+ |
| 自行构建 EXE | Python 3.10+，PyInstaller |

直接使用 Release 中的 EXE 时，不需要安装 Python、Conda 或 PyInstaller。

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

GitHub Actions 会在 Windows 环境下使用 Python **3.10** 和 **3.12** 自动运行单元测试与 `compileall`。

## 构建 EXE

运行时只使用 Python 标准库；只有构建 EXE 时需要 PyInstaller。

推荐先创建独立虚拟环境：

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

然后执行：

```powershell
.\scripts\build.ps1
```

构建脚本会依次：

1. 检查 Python / PyInstaller 环境；
2. 运行单元测试；
3. 执行 `compileall`；
4. 重新生成图标资源；
5. 调用 PyInstaller 构建 one-file EXE；
6. 输出最终文件信息与 SHA-256。

默认输出目录：

```text
..\CodexQuotaMonitor_release\
```

当前构建文件名：

```text
CodexQuotaMonitor_v1.4.exe
```

也可以显式指定 Release 目录：

```powershell
.\scripts\build.ps1 -ReleaseDir "D:\Your\Release\Directory"
```

`build/`、`dist/`、`__pycache__/`、`.pyc` 等均属于本地生成物，不应提交到 Git 仓库。

## 项目结构

```text
CodexQuotaMonitor/
├─ .github/
│  └─ workflows/
│     └─ ci.yml
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

## 仓库卫生

仓库通过 `.gitignore` 排除本地生成内容，包括：

```text
build/
dist/
__pycache__/
*.pyc
.venv/
.pytest_cache/
*.log
.codex/
sessions/
auth.json
*.jsonl
```

如果你准备继续开发，推荐直接 Clone `main`，不要从 Release EXE 或构建产物反推工程。

## 常见问题

<details>
<summary><strong>为什么额度没有立即变化？</strong></summary>
<br>
程序会周期性检查本地日志变化，并进行低频强制复核；Codex 只有在产生新的本地 session 记录后，日志中的额度状态才会更新。
</details>

<details>
<summary><strong>是否需要管理员权限？</strong></summary>
<br>
不需要。程序只访问当前用户目录；开机启动也使用当前用户 Startup 文件夹。
</details>

<details>
<summary><strong>更换电脑或移动 EXE 后，开机启动怎么办？</strong></summary>
<br>
移动或重命名 EXE 后，建议关闭再重新开启开机启动，让 Startup 脚本记录新的 EXE 路径。
</details>

## License

MIT License. See [LICENSE](./LICENSE).

---

<div align="center">

**CodexQuotaMonitor — keep quota visible, keep everything local.**

</div>
