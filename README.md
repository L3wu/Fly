# 📰 新闻联播 · 世界地图版（Daily News）

> 把央视网《新闻联播》每日要闻，变成**左列表 + 右真实世界地图**的深色科技风交互式简报。手机端与网页端均可访问，每天自动更新。

## 📋 项目简介

本项目是一个**全自动的新闻联播可视化简报系统**。它每天定时抓取央视网《新闻联播》的最新一期节目内容，通过**真实世界地图**（Natural Earth 地理数据）将每条要闻标注到其所属国家/地区，配合**关键字分色高亮**与**完整正文展示**，让读者用最短时间抓住当天最重要的新闻。

- **数据源**：央视网《新闻联播》栏目页 + `zy.api.cntv.cn` 官方内容接口
- **部署**：GitHub Pages 公网访问，`scripts/deploy.sh` 一键更新
- **交互**：地图与列表双向联动、日期切换、详情展开、关键字标签云

---

## ✨ 功能特性

| 特性 | 说明 |
|---|---|
| 🗺️ **真实世界地图** | Natural Earth 110m 国界数据（177 国 + 全球陆地），非卡通手绘轮廓 |
| 📍 **多国自动多点** | 一条要闻含多国时自动点亮多个光点（如"俄乌互袭"→ 俄罗斯 + 乌克兰两点） |
| 🎨 **5 类关键字分色** | 专业名词（青）/ 地区（蓝）/ 人名（玫红）/ 日期（琥珀）/ 数字（荧光绿） |
| 📝 **完整正文 + 高亮** | 详情区按段落展示"央视网消息"原文，全文保留关键字高亮 |
| 🖼️ **视频封面图** | 自动抓取央视网视频封面缩略图 |
| 🔢 **卡顶关键数据点** | 折叠态即见关键数字标签（如"增长6.4%"、"80种产品增长"） |
| 🔗 **多地区联动** | 点地区标签 → 地图飞行缩放 + 列表过滤 |
| ⏭️ **"接着看"按钮** | 详情末尾平滑滚动到下一条要闻并自动展开 |
| 📅 **日期切换** | 按真实播出日期（air_date）归档，支持历史回看 |
| 📱 **响应式** | 桌面双栏并排 / 平板 / 手机地图置顶堆叠 |
| 🔌 **零依赖离线** | 所有数据内嵌 `frontend/data.js`，双击 `index.html` 即可离线浏览 |
| ⚡ **纯 Python 采集** | 无需浏览器，直接调央视网官方接口，稳定可靠 |

---

## 🛠️ 技术栈

| 层 | 技术 | 说明 |
|---|---|---|
| **采集** | Python 3（标准库 `urllib`/`re`/`json`） | 零第三方依赖，抓取央视网栏目页 + 官方内容 API |
| **地图数据** | Node.js + `world-atlas` + `d3-geo` + `topojson-client` | Natural Earth 110m 国界 → 等距圆柱投影 SVG path |
| **前端** | 原生 HTML5 / CSS3 / JavaScript（ES6） | 零框架、零 CDN、零外部依赖 |
| **数据交换** | JSON + `data.js`（全局常量注入） | 浏览器直接读取，无需后端（根目录 + frontend/ 双输出） |
| **部署** | Git + GitHub Pages | `scripts/deploy.sh` 一键构建推送 |
| **自动化** | WorkBuddy 自动化 / cron 定时任务 | 每天定时执行 `run_daily.py` |

---

## 📦 安装步骤

### 前置要求

- Python 3.9+
- Node.js 16+（仅构建地图数据时需要）
- Git

### 1. 克隆仓库

```bash
git clone https://github.com/L3wu/Fly.git daily-news
cd daily-news
```

### 2. 安装地图数据依赖

```bash
# 安装 world-atlas / d3-geo / topojson-client（Natural Earth 真实国界数据）
npm install --no-workspaces
```

> 若在包含 workspace 的父目录下安装，务必加 `--no-workspaces`，避免污染父级 `node_modules`。

### 3. 构建世界地图数据

```bash
node scripts/build_world_map.mjs
# 生成 data/world-map.json（177 国轮廓 + 全球陆地）
```

### 4.（可选）生成前端离线数据

```bash
python run_daily.py --gen-frontend
# 生成 frontend/data.js（内嵌地图 + 当日简报）
```

---

## 🚀 使用方法

### 每日抓取 + 生成页面

```bash
# 默认抓昨天的节目（《新闻联播》每晚 19:00 播出，9:00 跑抓前一天）
python run_daily.py

# 指定日期
python run_daily.py 2026-08-06

# 仅重新打包前端数据（不重新抓取）
python run_daily.py --gen-frontend

# 重建世界地图数据
python run_daily.py --build-map
```

### 本地浏览

```bash
# 方式一：直接双击 frontend/index.html（离线可用）

# 方式二：本地服务器
python -m http.server 8765 -d frontend
# 浏览器打开 http://127.0.0.1:8765/index.html
```

### 公网部署（GitHub Pages）

```bash
# 抓最新 + 推送到 GitHub Pages（自动更新公网页面）
./scripts/deploy.sh
# 或指定日期
./scripts/deploy.sh 2026-08-06
```

部署完成后访问：`https://L3wu.github.io/Fly/`

---

## ⚙️ 配置说明

### 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `GITHUB_TOKEN` | 无 | GitHub Personal Access Token（推送时使用，需 `repo` 权限） |
| `GITHUB_REMOTE` | `origin` | Git 远程名 |
| `GITHUB_BRANCH` | `main` | 推送分支 |
| `GITHUB_SSL_NO_VERIFY` | `false` | 设为 `true` 可绕过 Windows schannel SSL 证书吊销检查 |

### 每日自动更新

**方案 A（推荐）：WorkBuddy 自动化**
在 WorkBuddy 中新建每日 9:05 的自动化任务，执行 `bash scripts/deploy.sh`，自动完成"抓取 → 生成 → 推送"全流程。

**方案 B：cron / 计划任务**

```bash
# 每天 09:05 执行
5 9 * * * cd /path/to/daily-news && bash scripts/deploy.sh >> /var/log/daily-news.log 2>&1
```

---

## 📂 目录结构

```
daily-news/
├── run_daily.py                 # 每日入口（抓取→处理→生成→部署）
├── index.html                   # 主页面（GitHub Pages 根部署）
├── style.css                    # 深色科技风样式
├── app.js                       # 交互逻辑
├── data.js                      # 自动生成 · 内嵌地图 + 简报（根 + frontend/）
├── package.json                 # Node 依赖（地图数据构建）
├── requirements.txt             # Python 依赖（当前为零第三方依赖）
├── README.md                    # 本文档
│
├── collector/                   # 采集与处理模块
│   ├── fetch_xwlb.py            # 采集央视网（栏目页 + newContentInfo 接口）
│   ├── region_dict.py           # 地区词典（关键词 → 国家坐标，200+ 词条）
│   ├── highlight.py             # 关键字分色高亮（5 类）
│   └── build_page.py            # 数据组装 + 生成前端 data.js + 历史归档
│
├── frontend/                    # 前端（纯静态，可部署）
│   ├── index.html               # 主页面
│   ├── style.css                # 深色科技风样式
│   ├── app.js                   # 交互逻辑（地图/列表双向联动）
│   └── data.js                  # 自动生成 · 内嵌地图 + 简报数据
│
├── data/                        # 数据目录
│   ├── world-map.json           # 真实世界地图（177 国轮廓）
│   ├── index.json               # 日期索引（近 30 天）
│   ├── pending.json             # 待 WebSearch 补充清单（空 body 条目）
│   └── briefings/               # 每日简报归档
│       └── YYYY-MM-DD.json
│
└── scripts/                     # 工具脚本
    ├── build_world_map.mjs      # TopoJSON → SVG path 投影
    └── deploy.sh                # 一键构建 + 推送 GitHub Pages
```

---

## 🧩 核心数据链路

```
央视网栏目页 tv.cctv.com/lm/xwlb/
   │ 静态 HTML 提取要闻真实链接（VIDE 开头）
   ▼
zy.api.cntv.cn/Article/newContentInfo?id=<VIDE>
   │ 返回完整字段：title / content（央视网消息原文）/ frame_url（封面图）
   │                    / length / category / create_date
   ▼
地区词典匹配（关键词 → 经纬度坐标）→ 多国多点
   │
   ▼
关键字分色高亮（专业名词/地区/人名/日期/数字）
   │
   ▼
data/briefings/YYYY-MM-DD.json + frontend/data.js
   │
   ▼
git push → GitHub Pages 自动部署
```

---

## 🤝 贡献指南

欢迎任何形式的贡献！

### 你可以做的

1. **扩充地区词典**：在 `collector/region_dict.py` 中添加更多国家/城市/大洲关键词及其坐标
2. **丰富关键字词表**：在 `collector/highlight.py` 中补充专业名词 / 人名 / 机构词
3. **优化地图呈现**：调整 `frontend/style.css` / `frontend/app.js` 的视觉与交互
4. **改进采集**：优化 `fetch_xwlb.py` 的容错与快讯补充逻辑
5. **报告问题**：在 GitHub Issues 中提交 bug 或功能建议

### 提交规范

```bash
# 1. Fork 本仓库
# 2. 新建功能分支
git checkout -b feat/your-feature

# 3. 提交并推送
git add .
git commit -m "feat: 添加 xx 功能"
git push origin feat/your-feature

# 4. 提交 Pull Request
```

- 提交信息使用约定式风格：`feat:` / `fix:` / `docs:` / `refactor:` / `perf:`
- 新增功能请附带测试或说明

---

## 📄 开源许可证

本项目采用 **MIT License**。

```
MIT License

Copyright (c) 2026 L3wu

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## 📮 联系方式

- 项目仓库：https://github.com/L3wu/Fly
- 在线预览：https://L3wu.github.io/Fly/

如果这个项目对你有帮助，欢迎 ⭐ Star 支持！
