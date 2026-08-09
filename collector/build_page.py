# -*- coding: utf-8 -*-
"""页面构建模块 —— 把采集数据组装成前端可用的 data.json。

流程：
1. 读取采集结果（fetch_xwlb 输出或手动输入 JSON）
2. 每条要闻：地区匹配（region_dict）→ 关键字分色高亮（highlight）
3. 生成"约100字说明"：正文优先（content），无正文时截取标题
4. 完整正文分段落（按央视网原段落分隔）
5. 汇总所有地区光点（含坐标、国家高亮 iso）
6. 输出 data/briefings/<air_date>.json + 汇总索引 data/index.json
"""

import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

from region_dict import match_region, HIGHLIGHT_EXCLUDE
from highlight import highlight, extract_keywords

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
BRIEF_DIR = DATA_DIR / "briefings"
KEEP_DAYS = 30  # 历史保留天数


def make_summary(body, title, max_len=100):
    """从正文生成约 100 字说明（保留关键信息，句号截断）。"""
    if not body:
        return title
    if len(body) <= max_len:
        return body
    cut = body[:max_len]
    for sep in ("。", "；", "！", "？"):
        idx = cut.rfind(sep)
        if idx > max_len * 0.5:
            return cut[: idx + 1]
    return cut + "…"


def split_paragraphs(body):
    """按央视网原始段落分隔（基于全角句号或连续汉字）。"""
    if not body:
        return []
    # 央视网原文会有段落分隔：可能是 "\n\n" 或长段落用 "。"分隔
    # 优先按 "\n\n" 分；否则按连续长段落（每 ~120 字切一个自然段）
    if "\n\n" in body:
        paras = [p.strip() for p in body.split("\n\n") if p.strip()]
        if len(paras) > 1:
            return paras
    # 按句号/分号切分，每 2-3 句为一段
    sentences = re.split(r"(?<=[。；！？])", body)
    paras = []
    cur = ""
    for s in sentences:
        if not s.strip():
            continue
        cur += s
        if len(cur) >= 120:
            paras.append(cur.strip())
            cur = ""
    if cur.strip():
        paras.append(cur.strip())
    return paras or [body]


def extract_key_points(body, max_points=4):
    """提取正文中的关键数据点（百分比、绝对数字+单位等）。

    策略：
    1. 优先提取短小精炼的"数据+解释"（如"5个产业大类同比增长均在6%以上"）
    2. 跳过开场白（不含数字或过短）
    3. 超过 32 字符的句子截断，避免视觉臃肿
    """
    if not body:
        return []
    points = []
    seen = set()

    # 模式1：精确匹配"X%增长"/"X.X个"/"X万亿"/"X.X%"等数据句
    short_patterns = [
        r"[+\-]?\d+(?:\.\d+)?%[^，。]*?增长[^，。]*",  # "5.0%增长"
        r"[+\-]?\d+(?:\.\d+)?%[^，。]{2,12}",         # 短数据片段
        r"增长\s*[+\-]?\d+(?:\.\d+)?%",
        r"\d+(?:\.\d+)?\s*(?:万亿|亿|万|千|百)(?:元|吨|人|个|次|户|家|公里|米|平方公里|人次)[^，。]*",
        r"\d+(?:\.\d+)?\s*(?:个|家|位|项)\s*(?:国家|地区|城市|产业|行业|大类|企业|项目)[^，。]*",
    ]

    # 先用短模式匹配
    for pat in short_patterns:
        for m in re.finditer(pat, body):
            txt = m.group(0).strip()
            if 4 <= len(txt) <= 32 and txt not in seen:
                seen.add(txt)
                points.append(txt)
                if len(points) >= max_points:
                    return points

    # 兜底：句子级（保留含数字的短句）
    if len(points) < max_points:
        sentences = re.split(r"(?<=[。；！？])", body)
        for s in sentences:
            s = s.strip()
            if not s or len(s) < 6 or not re.search(r"\d", s):
                continue
            if len(s) > 32:
                s = s[:30] + "…"
            if s in seen:
                continue
            seen.add(s)
            points.append(s)
            if len(points) >= max_points:
                break

    return points


def process_item(item, region_words):
    """处理单条要闻 → 前端条目。"""
    title = item.get("title", "").replace("[视频]", "").strip()
    body = item.get("body", "") or item.get("content_text", "") or ""
    summary = make_summary(body, title)
    paragraphs = split_paragraphs(body)
    key_points = extract_key_points(body)

    # 地区匹配
    regions = match_region(summary + " " + title + " " + body[:200])
    # 摘要高亮
    summary_hl = highlight(summary, region_words, HIGHLIGHT_EXCLUDE)
    # 完整正文高亮（按段落）
    para_hl = []
    for p in paragraphs:
        para_hl.append(highlight(p, region_words, HIGHLIGHT_EXCLUDE))
    # 关键字汇总
    keywords = extract_keywords(summary + " " + body[:500], region_words, HIGHLIGHT_EXCLUDE, limit=15)

    return {
        "title": title,
        "category": item.get("category", "国内"),
        "category_detail": item.get("category_detail", ""),
        "summary": summary,
        "highlighted": summary_hl,
        "body": body,
        "paragraphs": paragraphs,
        "paragraphs_highlighted": para_hl,
        "key_points": key_points,                # 关键数据点（卡顶展示）
        "keywords": [{"type": k, "word": w} for k, w in keywords],
        "regions": [
            {"name": r[0], "lon": r[1], "lat": r[2], "iso": r[3], "kw": r[4]}
            for r in regions
        ],
        "image": item.get("image", ""),
        "length": item.get("length", ""),
        "url": item.get("url", ""),
        "guid": item.get("guid", ""),
        "source": item.get("source", "央视网"),
        "create_date": item.get("create_date", ""),
        "air_date": item.get("air_date", ""),
    }


def build_daily(raw_data, target_date=None):
    """构建单日 data.json。raw_data: fetch_xwlb 的返回结构。"""
    if target_date is None:
        target_date = raw_data.get("date", date.today().isoformat())

    from region_dict import LOOKUP
    region_words = list(LOOKUP.keys())

    items = [process_item(it, region_words) for it in raw_data.get("items", [])]

    # 以"air_date"为分组键——CCTV 静态页只给最近一期，按真实播出日期归档
    air_date = items[0]["air_date"] if items else target_date

    # 统计空 body 条目（需 WebSearch 补充）
    empty_body_count = sum(1 for it in items if not it.get("body"))

    # 汇总地区光点（去重，按出现次数排序）
    region_map = {}
    for it in items:
        for r in it["regions"]:
            key = (r["name"], r["iso"])
            if key not in region_map:
                region_map[key] = {
                    "name": r["name"], "lon": r["lon"], "lat": r["lat"],
                    "iso": r["iso"], "count": 0, "items": [],
                }
            region_map[key]["count"] += 1
            region_map[key]["items"].append(it["title"])

    points = sorted(region_map.values(), key=lambda p: -p["count"])

    return {
        "date": air_date,                          # 用真实播出日期做主键
        "fetched_at": target_date,                # 抓取日期（用户运行时的日期）
        "generated_at": date.today().isoformat(),
        "total": len(items),
        "empty_body_count": empty_body_count,     # 空 body 数（WebSearch 补充目标）
        "items": items,
        "points": points,
    }


def save_daily(data, date_str=None):
    """保存单日 JSON 到 data/briefings/，并更新 index.json。"""
    BRIEF_DIR.mkdir(parents=True, exist_ok=True)
    if date_str is None:
        date_str = data["date"]
    path = BRIEF_DIR / f"{date_str}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    rebuild_index()
    return path


def rebuild_index():
    """重建 index.json：按日期倒序列出近 KEEP_DAYS 天的简报元数据，清理过期。"""
    index = {"dates": [], "keep_days": KEEP_DAYS}
    today = date.today()
    for p in sorted(BRIEF_DIR.glob("*.json")):
        dstr = p.stem
        try:
            d = date.fromisoformat(dstr)
        except ValueError:
            continue
        if (today - d).days > KEEP_DAYS:
            p.unlink(missing_ok=True)
            continue
        try:
            j = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        index["dates"].append({
            "date": dstr,
            "total": j.get("total", 0),
            "fetched_at": j.get("fetched_at", dstr),
            "points": j.get("points", []),
        })
    index["dates"].sort(key=lambda x: x["date"], reverse=True)
    (DATA_DIR / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    return index


def load_dates(limit=30):
    dates = []
    for p in sorted(BRIEF_DIR.glob("*.json"), reverse=True):
        dates.append(p.stem)
    return dates[:limit]


def gen_frontend_data():
    """生成 frontend/data.js：内嵌世界地图 + 日期索引 + 全部简报数据。"""
    map_path = DATA_DIR / "world-map.json"
    if not map_path.exists():
        raise FileNotFoundError(f"缺少世界地图数据：{map_path}，请先运行 scripts/build_world_map.mjs")

    world_map = json.loads(map_path.read_text(encoding="utf-8"))

    index = json.loads((DATA_DIR / "index.json").read_text(encoding="utf-8")) \
        if (DATA_DIR / "index.json").exists() else {"dates": []}

    daily_map = {}
    for d in index.get("dates", []):
        p = BRIEF_DIR / f"{d['date']}.json"
        if p.exists():
            daily_map[d["date"]] = json.loads(p.read_text(encoding="utf-8"))

    js = (
        "/* 自动生成 —— 由 collector/build_page.py gen_frontend_data 输出，请���手改 */\n"
        "const WORLD_MAP = " + json.dumps(world_map, ensure_ascii=False) + ";\n"
        "const DAILY_INDEX = " + json.dumps(index, ensure_ascii=False) + ";\n"
        "const DAILY_MAP = " + json.dumps(daily_map, ensure_ascii=False) + ";\n"
    )
    # 同时输出到 frontend/data.js 和仓库根 data.js（GitHub Pages 根部署）
    outs = [BASE_DIR / "frontend" / "data.js", BASE_DIR / "data.js"]
    for out in outs:
        out.write_text(js, encoding="utf-8")
    return outs[0]


def export_pending_for_data(data):
    """为已构建的 data 生成 pending.json（空 body 待 WebSearch 补充清单）。"""
    pending = []
    for it in data.get("items", []):
        if not it.get("body"):
            pending.append({
                "title": it["title"],
                "category": it.get("category", ""),
                "url": it.get("url", ""),
                "air_date": it.get("air_date", data.get("date", "")),
                "search_hint": f"《新闻联播》 {it.get('air_date', '')} {it['title'][:30]} 内容提要",
            })
    out = DATA_DIR / "pending.json"
    out.write_text(
        json.dumps({"date": data.get("date", ""), "pending": pending},
                   ensure_ascii=False, indent=2),
        encoding="utf-8")
    return pending, out


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", help="采集 JSON 文件路径（默认 stdin）")
    ap.add_argument("--date", help="目标日期 YYYY-MM-DD（默认今天）")
    ap.add_argument("--gen-frontend", action="store_true", help="仅生成前端 data.js")
    args = ap.parse_args()

    if args.gen_frontend:
        out = gen_frontend_data()
        print(f"OK: {out} 已生成")
        sys.exit(0)

    if args.input:
        raw = json.loads(Path(args.input).read_text(encoding="utf-8"))
    else:
        raw = json.load(sys.stdin)
    d = build_daily(raw, args.date)
    path = save_daily(d, d["date"])
    print(f"OK: {path} | air_date={d['date']} | {d['total']} 条要闻 | {len(d['points'])} 个地区光点")