#!/bin/bash
# deploy.sh — 一键本地更新并推送到 GitHub Pages
#
# 流程：
#  1. 抓取最新一期新闻联播 → 生成 data.js
#  2. 本地 git add/commit（仅本地记录，不推送）
#  3. 通过 GitHub API 上传到远程 main 分支 → GitHub Pages 自动部署
#     （绕开透明代理对 git 协议 push 的 reset，详见 scripts/push_api.py）
#
# 用法：
#  ./scripts/deploy.sh                 # 抓昨天（默认），上传
#  ./scripts/deploy.sh 2026-08-06     # 抓指定日期，上传
#  GITHUB_TOKEN=xxx ./scripts/deploy.sh # 自定义 PAT
#
# 依赖：git、python（已部署，建议用托管 Python）、GITHUB_TOKEN 或 remote 含 token

set -e

# 配置（用户需修改）
GITHUB_REMOTE="${GITHUB_REMOTE:-origin}"
GITHUB_BRANCH="${GITHUB_BRANCH:-main}"
# 优先使用托管 Python（避免依赖系统 python 是否在 PATH）
PY="${PYTHON_BIN:-/c/Users/W_Lba/.workbuddy/binaries/python/versions/3.13.12/python.exe}"

# 默认抓昨天（新闻联播 19:00 播出，9:00 跑抓到前一天）
TARGET_DATE="${1:-$(date -d 'yesterday' +%Y-%m-%d)}"

cd "$(dirname "$0")/.."

echo "=== [1/3] 抓取 $TARGET_DATE 新闻联播 ==="
"$PY" run_daily.py "$TARGET_DATE"

# 同步前端文件到仓库根（GitHub Pages 根部署需要 index.html 在根目录）
echo "=== [1.5/3] 同步前端文件到仓库根 ==="
cp frontend/index.html index.html
cp frontend/style.css style.css
cp frontend/app.js app.js
cp frontend/data.js data.js

# 配置 git 用户（仅本地提交记录；push 已改为 GitHub API 上传）
if ! git config user.email >/dev/null 2>&1; then
    git config user.email "workbuddy@local"
    git config user.name "Daily News Bot"
fi

echo "=== [2/3] 本地 git 提交（仅本地记录，不推送）==="
git add -A 2>/dev/null || true
git status --short
if git diff --cached --quiet; then
    echo "无变更，跳过提交"
else
    git commit -m "update: $TARGET_DATE 简报" || true
fi

echo "=== [3/3] 通过 GitHub API 上传到远程（绕开 git push 被代理 reset）==="
ok=0
for i in 1 2 3; do
    if "$PY" scripts/push_api.py "$TARGET_DATE"; then
        ok=1; break
    fi
    echo "  push_api 第 $i 次未完全成功，3 秒后重试..."
    sleep 3
done
if [ "$ok" -ne 1 ]; then
    echo "✗ push_api 重试 3 次仍失败"
    exit 1
fi

echo "✓ 完成！GitHub Pages 将在 1-2 分钟内自动更新"
echo "  公网地址：https://l3wu.github.io/Fly/"