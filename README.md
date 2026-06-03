# 超星学习通 智能刷课助手

自动刷视频 | AI答题 | 免费模型 | 秒过模式 | 交互式菜单

## 功能

- **视频秒过** — 2秒完成一个视频，劫持进度上报防回滚
- **高速播放** — 4x/8x/16x 倍速，JS注入绕过UI限制
- **AI自动答题** — 章节测验、视频弹题，调用免费AI模型回答
- **自动翻章** — 一章完成自动进入下一章
- **课程选择** — 登录后自动获取课程列表，选择即可
- **交互式菜单** — 无需改代码，全部在界面上配置

## 截图

```
╔══════════════════════════════════════════════════════╗
║      超星学习通 智能刷课助手 v2.0                    ║
╚══════════════════════════════════════════════════════╝

  [1] 开始刷课
  [2] 选择课程
  [3] 填写课程URL
  [4] 播放设置 (速度/秒过/防回滚)
  [5] AI答题设置
  [6] 账号设置
  [7] 测试AI
  [8] 检查依赖
  [0] 退出
```

## 快速开始

### 1. 安装依赖

```bash
pip install playwright httpx
playwright install chromium
```

### 2. 安装 AI 后端（可选，用于自动答题）

```bash
npm install -g opencode-ai
```

安装后即可使用 OpenCode 的免费 DeepSeek V4 Flash 模型，零成本。

### 3. 运行

**Windows 用户**：双击 `start.bat`

**命令行**：
```bash
python menu.py
```

**直接运行（跳过菜单）**：
```bash
python chaoxing_auto.py --no-headless
```

## 配置说明

所有配置通过菜单界面修改，也可直接编辑 `chaoxing_auto.py` 顶部的 `CONFIG`。

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `video_speed` | 8 | 播放倍速（推荐 4-16） |
| `video_skip` | False | 秒过模式（2秒/视频） |
| `video_bypass` | True | 劫持上报，服务器认为完整看完 |
| `auto_answer` | True | AI自动答题 |
| `auto_submit` | True | 答完自动提交 |
| `auto_next_chapter` | True | 自动下一章 |

## AI 后端

支持三种免费 AI 后端：

| 后端 | 费用 | 说明 |
|------|------|------|
| **OpenCode CLI** | 免费 | 调用本地 OpenCode 的 DeepSeek V4 Flash |
| **SiliconFlow** | 注册送额度 | 国内直连，DeepSeek V3 |
| **OpenRouter** | 有免费模型 | DeepSeek V3 等 |

默认使用 OpenCode CLI，零成本。

## 技术原理

### 视频秒过

通过 Playwright 控制浏览器，注入 JS 劫持学习通的 `sendTimePack` 进度上报函数。
无论实际播放多久，上报给服务器的 `playingTime` 始终等于视频总时长 `duration`。

### AI 答题

提取页面上的题目文本和选项，调用 AI 模型获取答案，自动点选并提交。
支持选择题、判断题、填空题。视频中途弹出的题目也会自动处理。

## 项目结构

```
├── menu.py              # 交互式菜单（入口）
├── chaoxing_auto.py     # 核心自动化逻辑
├── start.bat            # Windows 一键启动
├── config_example.json  # 配置模板
├── requirements.txt     # Python 依赖
└── README.md
```

## 免责声明

本项目仅供学习和研究自动化技术使用。使用本工具可能违反学校规定和平台服务协议，
请自行评估风险。作者不对任何使用后果负责。

## License

MIT
