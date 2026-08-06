#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""《新闻联播·世界地图版》每日入口。

用法：
  python run_daily.py                # 抓取今天（如 9:00 前跑，抓前一天）的节目
  python run_daily.py 2026-08-06     # 抓取指定日期
  python run_daily.py --gen-frontend # 仅重新打包前端 data.js（无需重抓）
  python run_daily.py --build-map    # 重建真实世界地图数据（world-map.json）

输出：
  data/briefings/YYYY-MM-DD.json  → 当日简报数据
  data/index.json                 → 日期索引
  frontend/data.js                → 前端可加载的离线数据
"""

import argparse
import sys
from datetime import date
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR / "collector"))

from fetch_xwlb import fetch_daily
from build_page import build_daily, save_daily, gen_frontend_data, export_pending_for_data


def main():
    ap = argparse.ArgumentParser(description="新闻联播·世界地图版 每日入口")
    ap.add_argument("date", nargs="?", help="目标日期 YYYY-MM-DD（默认昨天，因节目当晚 19:00 播出）")
    ap.add_argument("--date", dest="date_flag", help="同上（兼容 flag 写法）")
    ap.add_argument("--gen-frontend", action="store_true",
                    help="仅重新打包前端 data.js（不抓取新数据）")
    ap.add_argument("--build-map", action="store_true",
                    help="重建世界地图（需 node + 已装依赖）")
    args = ap.parse_args()

    target = args.date or args.date_flag
    if target is None:
        # 默认：昨天（节目当晚 19:00 播出，9:00 跑抓到前一天）
        from datetime import timedelta
        target = (date.today() - timedelta(days=1)).isoformat()

    if args.gen_frontend:
        out = gen_frontend_data()
        print(f"[frontend] 已重新打包 {out}")
        return

    if args.build_map:
        import subprocess
        script = BASE_DIR / "scripts" / "build_world_map.mjs"
        r = subprocess.run(["node", str(script)], capture_output=True, text=True)
        print(r.stdout.strip())
        if r.returncode != 0:
            print(r.stderr.strip(), file=sys.stderr)
        return

    # 主流程：采集 → 构建 → 保存 → 生成前端数据
    print(f"[1/3] 抓取 {target} 新闻联播要闻...")
    raw = fetch_daily(target)
    print(f"  → {len(raw['items'])} 条标题已拿到")

    print(f"[2/3] 地区匹配 + 关键字高亮 + 数据组装...")
    data = build_daily(raw, target)
    # 用 data["date"]（CCTV 真实播出日期）作为文件名，避免与历史日期冲突
    path = save_daily(data, data["date"])
    print(f"  → {path}")
    print(f"  → {data['total']} 条要闻 | {len(data['points'])} 个地区光点")

    # 输出待 WebSearch 补充清单（自动化 agent 会用 WebSearch 抓空 body 条目）
    pending, pending_path = export_pending_for_data(data)
    if pending:
        print(f"  → {pending_path}（{len(pending)} 条空 body 待 WebSearch 补充）")
        print(f"  → 提示：自动化 agent 可用 WebSearch 检索每条 search_hint 后回填 body")
    else:
        print(f"  → 所有要闻 body 完整，无需 WebSearch 补充")

    print(f"[3/3] 打包前端 data.js...")
    out = gen_frontend_data()
    print(f"  → {out}")

    print(f"\n✓ 完成！打开 {BASE_DIR}/frontend/index.html 即可浏览")


if __name__ == "__main__":
    main()