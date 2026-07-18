# AutoXuexiPlaywright

基于 Playwright 的学习任务自动化工具，提供 Windows 图形界面、系统托盘控制、浏览器登录状态复用、文章与视频学习、答题及 OpenAI 兼容接口兜底等功能。

[![Release](https://img.shields.io/github/v/release/sk856/AutoXuexiPlaywright)](https://github.com/sk856/AutoXuexiPlaywright/releases)
[![Python](https://img.shields.io/badge/Python-3.12%20%7C%203.13-blue)](https://www.python.org/)
[![License](https://img.shields.io/github/license/sk856/AutoXuexiPlaywright)](./LICENCE)

## 下载

### Windows 图形版

当前 Windows 发布版：**v4.0.0**

- [进入 Releases 页面](https://github.com/sk856/AutoXuexiPlaywright/releases)
- [下载 AutoXuexiPlaywright-v4.0.0-windows-x64.zip](https://github.com/sk856/AutoXuexiPlaywright/releases/download/v4.0.0/AutoXuexiPlaywright-v4.0.0-windows-x64.zip)

SHA256：

```text
F902E32F0AB6C932121BC3B845FD2D8D3EADA83A84E19000F187EA2106211794
```

下载后请**完整解压 ZIP**，然后运行：

```text
AutoXuexiPlaywright.exe
```

发布包采用目录模式，必须保留以下结构：

```text
AutoXuexiPlaywright-v4.0.0-windows-x64/
├─ AutoXuexiPlaywright.exe
└─ _internal/
```

不要只复制 EXE，也不要删除或移动 `_internal` 目录。

## 主要功能

### 图形界面与托盘

- 中文 GUI，显示当前状态、积分和运行日志；
- 设置页按常规、浏览器、AI 答题、滑块处理和网络代理分类；
- 支持保存设置并直接覆盖当前配置文件；
- 支持启动程序后自动开始任务；
- 支持最小化到系统托盘；
- 托盘右键菜单提供显示、开始、暂停/继续、设置和退出操作；
- 登录时可在界面内显示二维码。

### 登录与浏览器

- 使用持久化浏览器数据目录保存 Cookie 和站点状态；
- 登录状态有效时自动免登录；
- Cookie 失效时自动回退到二维码登录；
- 支持 Firefox、Chromium 和 WebKit；
- Chromium 可选择 Edge、Chrome 或 Chromium Channel；
- 支持自定义浏览器可执行文件；
- 支持 HTTP、HTTPS、SOCKS4 和 SOCKS5 代理；
- 常规任务默认在无头浏览器中执行，视频任务失败时可使用临时有头浏览器重试，避免主浏览器长期占用前台。

### 学习任务

当前 v4 核心流程包括：

- 登录；
- 文章阅读；
- 视频学习；
- 每日答题。

程序会从积分页读取当前可用任务并按配置跳过指定任务。其他答题类型只有在当前构建包含对应任务模块且网站页面仍兼容时才会执行，不作为 v4 核心流程的固定功能。

### AI 兜底答题

支持接入 OpenAI 兼容的 Chat Completions 接口，包括 OpenAI、DeepSeek 及其他实现兼容协议的服务。

AI 不会优先覆盖现有答案。答题流程会依次尝试：

1. 本地答案源；
2. 页面提示或解析结果；
3. 已启用并完成配置的 AI 接口。

设置页支持：

- 开启或关闭 AI 答题；
- 填写 Base URL、API Key 和模型名称；
- 从远端 `/models` 接口获取模型列表；
- 从下拉列表选择模型；
- 直接手动填写模型名称；
- 测试当前接口和模型是否可用。

常见 Base URL 示例：

```text
https://api.openai.com/v1
https://api.deepseek.com/v1
```

程序会自动补全 `/chat/completions` 和 `/models` 路径。API Key 只保存在用户本机配置文件中，不包含在公开发布包内。

### 已读历史

- 自动记录已完成的文章和视频标题；
- 在保留周期内跳过已经读过的内容；
- 默认保留 **7 天**；
- 可在设置中选择 **3 天、7 天、15 天或 30 天**；
- 损坏或格式异常的历史记录会被忽略，不会使用字符串子串方式误判已读内容。

### 滑块处理

- 内置基于页面轨迹的滑块拖动处理；
- 支持答题完成阶段出现的滑块；
- Windows GUI 构建可配置本地滑块识别服务，包括服务地址、Token 和请求超时；
- 本地服务未启用或调用失败时，仍可继续尝试内置拖动流程。

网站页面和验证机制可能变化，滑块处理结果以实际页面为准。

## Windows 图形版使用

1. 从 Releases 下载 ZIP；
2. 解压到一个有写入权限的普通目录；
3. 运行 `AutoXuexiPlaywright.exe`；
4. 打开“设置”，选择浏览器并配置需要跳过的任务；
5. 如需 AI 兜底，填写接口信息后先点击“测试接口”；
6. 点击“开始”；
7. 首次运行时扫描界面中的登录二维码；
8. 后续运行会优先复用浏览器登录状态。

建议每次升级都解压到新的完整目录，不要把新版 EXE 单独覆盖到旧版 `_internal` 目录中。

## 配置与用户数据

程序使用系统用户目录保存配置、日志、缓存、浏览器状态和阅读历史，不会把个人配置写入程序发布包。

Windows 下配置文件通常位于 `%LOCALAPPDATA%` 中的 `AutoXuexiPlaywright` 目录。也可以通过命令行显式指定配置文件：

```powershell
autoxuexiplaywright --gui --config "D:\path\to\config.json"
```

主要数据包括：

| 数据 | 用途 |
| --- | --- |
| `config.json` | GUI 和任务配置 |
| 浏览器数据目录 | Cookie、Local Storage 等登录状态 |
| `read_history.json` | 文章和视频已读记录 |
| 日志文件 | 任务执行过程与详细错误 |
| 缓存目录 | 二维码及运行时临时文件 |

公开提交代码或发布压缩包时，不要加入个人 `config.json`、Cookie、浏览器数据、日志、二维码或 API Key。

## 从源码运行

### 环境要求

- Python `>=3.12,<3.14`；
- [PDM](https://pdm-project.org/)；
- Windows、Linux 或 macOS；
- 可正常访问目标站点的网络环境。

### 安装

```bash
git clone https://github.com/sk856/AutoXuexiPlaywright.git
cd AutoXuexiPlaywright
pdm install -G gui
pdm run playwright install firefox
```

如需 Chromium：

```bash
pdm run playwright install chromium
```

### 启动 GUI

```bash
pdm run python -m autoxuexiplaywright --gui
```

### 启动终端界面

```bash
pdm run python -m autoxuexiplaywright --no-gui
```

### 指定配置文件

```bash
pdm run python -m autoxuexiplaywright --gui --config ./config.json
```

### 调试日志

```bash
pdm run python -m autoxuexiplaywright --gui --debug
```

## 开发与测试

安装开发依赖：

```bash
pdm install -G gui -G build -G test
```

运行测试：

```bash
pdm run pytest
```

构建 Python 包：

```bash
pdm build
```

构建完成后可在 `dist/` 中获得 wheel 和源码包。

项目采用模块化架构，任务、阅读器、答案源、滑块处理器和配置解析器均可通过 SDK 扩展。模块开发说明位于 [`docs/modules`](./docs/modules/README.md)。

## 常见问题

### 双击 EXE 后无法启动

确认 EXE 与 `_internal` 目录来自同一个 ZIP，且没有只复制 EXE、混用旧版依赖或在解压过程中丢失文件。

### 每次启动都需要重新登录

确认程序对用户缓存目录有写入权限，不要在任务运行时删除浏览器数据目录。切换浏览器类型、浏览器通道或可执行文件后，会使用不同的浏览器状态目录，可能需要重新登录。

### AI 已开启但没有自动调用

依次检查：

1. Base URL、API Key 和模型名称是否完整；
2. “测试接口”是否成功；
3. 当前问题是否已经被本地答案源或页面提示处理；
4. 日志中是否出现“正在尝试 AI 答题”或对应的接口错误；
5. 接口是否实现 OpenAI 兼容的 `/v1/chat/completions`。

AI 仅作为最后兜底，因此并非每道题都会请求接口。

### 获取模型失败

部分兼容接口没有实现 `/v1/models`，此时仍可手动填写模型名称，并使用“测试接口”验证 Chat Completions 是否可用。

### 升级后仍显示旧界面

删除旧解压目录后重新完整解压最新 ZIP，并确认启动的是新目录中的 `AutoXuexiPlaywright.exe`。不要从旧快捷方式或旧备份目录启动。

## 版本与变更

- 当前版本：`4.0.0`
- 更新记录：[`CHANGELOG.md`](./CHANGELOG.md)
- 发布页面：[GitHub Releases](https://github.com/sk856/AutoXuexiPlaywright/releases)

## 许可证

本项目使用 [GPL-3.0-or-later](./LICENCE) 许可证。
