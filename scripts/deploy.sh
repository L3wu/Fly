#!/bin/bash
# deploy.sh — 一键本地更新并推送到 GitHub Pages
#
# 流程：
#  1. 抓取最新一期新闻联播 → 生成 data.js
#  2. git add/commit 变更文件
#  3. git push 到远程 main 分支 → GitHub Pages 自动部署
#
# 用法：
#  ./scripts/deploy.sh                 # 抓昨天（默认），推送
#  ./scripts/deploy.sh 2026-08-06     # 抓指定日期，推送
#  GITHUB_TOKEN=xxx ./scripts/deploy.sh # 自定义 PAT
#
# 依赖：git、python（已部署）、GITHUB_TOKEN 或 SSH 配置

set -e

# 配置（用户需修改）
GITHUB_REMOTE="${GITHUB_REMOTE:-origin}"
GITHUB_BRANCH="${GITHUB_BRANCH:-main}"

# 默认抓昨天（新闻联播 19:00 播出，9:00 跑抓到前一天）
TARGET_DATE="${1:-$(date -d 'yesterday' +%Y-%m-%d)}"

cd "$(dirname "$0")/.."

echo "=== [1/3] 抓取 $TARGET_DATE 新闻联播 ==="
python run_daily.py "$TARGET_DATE"

# 同步前端文件到仓库根（GitHub Pages 根部署需要 index.html 在根目录）
echo "=== [1.5/3] 同步前端文件到仓库根 ==="
cp frontend/index.html index.html
cp frontend/style.css style.css
cp frontend/app.js app.js
cp frontend/data.js data.js

# 配置 git 用户（首次提交需要）
if ! git config user.email >/dev/null 2>&1; then
    git config user.email "workbuddy@local"
    git config user.name "Daily News Bot"
fi

echo "=== [2/3] git add + commit ==="
git add data/ frontend/ collector/ scripts/ run_daily.py README.md .gitignore package.json index.html style.css app.js data.js 2>/dev/null || true
git status --short
if git diff --cached --quiet; then
    echo "无变更，跳过提交"
else
    git commit -m "update: $TARGET_DATE 简报"
fi

echo "=== [3/3] git push 到 GitHub ==="
git push "$GITHUB_REMOTE" "$GITHUB_BRANCH"

echo "✓ 完成！GitHub Pages 将在 1-2 分钟内自动更新"
echo "  公网地址：https://$(git config --get remote.${GITHUB_REMOTE}.url | sed 's/.*github.com[:/]\(.*\)\.git/\1/').github.io/$(basename $(git rev-parse --show-toplevel))"