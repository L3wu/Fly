# -*- coding: utf-8 -*-
"""《新闻联播》采集模块 —— 纯 Python 抓取央视网，零浏览器依赖。

数据链路（2026-08-06 验证）：
1. 抓栏目页 https://tv.cctv.com/lm/xwlb/ 静态 HTML → 提取当日要闻真实链接
   （静态 HTML 含约 7 条；国内/国际联播快讯为懒加载，需 WebSearch 补充）
2. 逐条调 https://zy.api.cntv.cn/Article/newContentInfo?id=<VIDE id>&serviceId=tvcctv
   → 返回完整字段：title / content（完整播报文字稿，含 HTML 标签）/ frame_url（封面图）
     / length（时长）/ fc+sc（分类）/ create_date / guid
3. 输出结构化 JSON：{date, source, items: [{title, url, image, length, category,
   category_detail, content_text, summary}]}

关键发现：
- 单条新闻页 HTML 与期节目页均无静态简介（改版后 JS 动态加载）
- 文字稿来自 zy.api.cntv.cn 的 newContentInfo 接口的 content 字段（"央视网消息（新闻联播）…"）
- 部分条目（如快讯/部分普通新闻）content 可能为空 → 由 run_daily.py 用 WebSearch 补充
"""

import json
import re
import sys
import urllib.request
from datetime import date
from pathlib import Path

COLUMN_URL = "https://tv.cctv.com/lm/xwlb/"
API_INFO = "https://zy.api.cntv.cn/Article/newContentInfo?serviceId=tvcctv&id={vid}&cb=cb"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

LINK_RE = re.compile(r"https://tv\.cctv\.com/\d{4}/\d{2}/\d{2}/VIDE\w+\.shtml")
HTML_TAG_RE = re.compile(r"<[^>]+>")
MDASH_RE = re.compile(r"&[a-zA-Z]+;|&#\d+;|&mdash;|&ldquo;|&rdquo;|&hellip;")

# 栏目页中的期节目链接（tv.cctv.cn 域名）也纳入候选
EPISODE_LINK_RE = re.compile(r"https://tv\.cctv\.cn/\d{4}/\d{2}/\d{2}/VIDE\w+\.shtml")


def http_get(url, timeout=15):
    """抓取页面文本，失败抛异常。"""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "ignore")


def _clean_text(html_text):
    """去 HTML 标签与实体，压缩空白。"""
    t = HTML_TAG_RE.sub(" ", html_text or "")
    t = t.replace("&mdash;", "—").replace("&ldquo;", "“").replace("&rdquo;", "”")
    t = t.replace("&hellip;", "…").replace("&nbsp;", " ")
    t = re.sub(r"\s+", " ", t).strip()
    return t


def extract_column_items(html):
    """从栏目页 HTML 提取 (url, title) 列表，保持页面顺序，去重。"""
    items = []
    seen = set()
    for m in LINK_RE.finditer(html):
        url = m.group(0)
        if url in seen:
            continue
        seen.add(url)
        idx = html.find(url)
        ctx = html[max(0, idx - 300):idx + 300]
        title = None
        for attr in ("title=", "alt="):
            t = re.findall(attr + r'"([^"]+)"', ctx)
            if t:
                title = t[0]
                break
        if title:
            title = re.sub(r"^\[视频\]\s*", "", title).strip()
        items.append({"url": url, "title": title or ""})
    return items


def fetch_content_info(vid, timeout=15):
    """调 newContentInfo 接口拿单条新闻完整数据。失败返回 None。"""
    try:
        html = http_get(API_INFO.format(vid=vid), timeout)
        raw = html[html.find("(") + 1:html.rfind(")")]
        data = json.loads(raw).get("data", {})
        if not data or data.get("id") != vid:
            return None
        content_text = _clean_text(data.get("content", ""))
        # 去掉"央视网消息（新闻联播）："前缀，作为正文
        body = re.sub(r"^央视网消息\s*（新闻联播）\s*[:：]\s*", "", content_text)
        brief = _clean_text(data.get("brief", ""))
        return {
            "title": data.get("title", ""),
            "image": data.get("frame_url", ""),
            "length": data.get("length", ""),
            "category_detail": f"{data.get('fc','')}/{data.get('sc','')}",
            "content_text": content_text,
            "brief": brief,
            "body": body or brief,  # 正文优先，brief 兜底
            "guid": data.get("guid", ""),
            "create_date": data.get("create_date", ""),
            "source": data.get("source", "央视网"),
        }
    except Exception:
        return None


def classify_title(title):
    """按标题关键词粗分类别：头条/国内/国际/快讯。"""
    if not title:
        return "国内"
    if any(k in title for k in ("总书记", "习近平", "治国理政", "政府工作报告",
                                "党的二十大", "中央经济工作")):
        return "头条"
    if any(k in title for k in ("国际", "美国", "俄罗斯", "欧洲", "伊朗",
                                "联合国", "世界", "欧盟", "非洲", "亚洲",
                                "中东", "拉美", "亚太")):
        return "国际"
    if any(k in title for k in ("快讯", "联播")):
        return "快讯"
    return "国内"


def fetch_daily(target_date=None, timeout=15):
    """抓取《新闻联播》最新一期节目。

    注意：CCTV 栏目页静态 HTML 只展示最近一期节目，无按日期的存档接口。
    返回数据里每条要闻带有从 URL 提取的"真实播出日期" air_date，
    调用方应以 air_date 而非 target_date 作为数据存档的 key。

    返回: {"date": "YYYY-MM-DD" (抓取日期), "source": "cctv", "items": [
        {title, url, air_date, image, length, category, category_detail,
         content_text, body, brief, guid, create_date}
    ]}
    """
    if target_date is None:
        target_date = date.today().isoformat()

    col_html = http_get(COLUMN_URL, timeout)
    col_items = extract_column_items(col_html)

    # 从 URL 提取每条要闻的真实播出日期，过滤掉非今日（或历史）的链接
    date_re = re.compile(r"/(\d{4}/\d{2}/\d{2})/")
    items = []
    for it in col_items:
        m = date_re.search(it["url"])
        air_date = m.group(1).replace("/", "-") if m else target_date
        it["air_date"] = air_date
        # 只保留与请求日期同一天的（多数情况下 CCTV 给的链接日期≠请求日期）
        # —— 此处取所有，按 air_date 归档。
        items.append(it)

    # 过滤期节目页总览条目（标题为"《新闻联播》 YYYYMMDD HH:MM"）
    items = [it for it in items if not re.match(r"^《新闻联播》\s*\d{8}\s*\d", it["title"])]

    # 逐条补全
    for it in items:
        vid = it["url"].split("/")[-1].replace(".shtml", "")
        info = fetch_content_info(vid, timeout)
        if info:
            it.update(info)
            it["category"] = classify_title(info["title"])
        else:
            it.update({
                "image": "", "length": "", "category_detail": "",
                "content_text": "", "body": "", "brief": "",
                "guid": "", "create_date": "",
            })
            it["category"] = classify_title(it["title"])

    return {"date": target_date, "source": "cctv", "items": items}


def load_today_items():
    """兼容命令行入口：python fetch_xwlb.py [YYYY-MM-DD]"""
    target = sys.argv[1] if len(sys.argv) > 1 else None
    data = fetch_daily(target)
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return data


def export_pending_enrich(data, out_path=None):
    """导出"待 WebSearch 补充"清单到 data/pending.json。

    每条要闻 body 为空时，agent 可根据清单调用 WebSearch
    检索 "新闻联播 YYYYMMDD 标题 内容提要" 抓约 100 字说明回填。
    """
    from pathlib import Path
    if out_path is None:
        out_path = Path(__file__).resolve().parent.parent / "data" / "pending.json"
    pending = []
    for it in data.get("items", []):
        if not it.get("body"):
            pending.append({
                "title": it["title"],
                "category": it.get("category", ""),
                "url": it.get("url", ""),
                "air_date": it.get("air_date", data.get("date", "")),
                "search_hint": f"《新闻联播��� {it.get('air_date', '')} {it['title'][:30]} 内容提要",
            })
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(
        __import__("json").dumps({"date": data.get("date", ""), "pending": pending},
                                ensure_ascii=False, indent=2),
        encoding="utf-8")
    return pending, out_path


if __name__ == "__main__":
    load_today_items()
