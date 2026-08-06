# -*- coding: utf-8 -*-
"""关键字分色高亮 —— 从要闻文本中识别并标记四类关键字。

类型与配色（深色科技风）：
- term   专业名词（高质量发展、污水治理率…）→ 青色 #5DCAA5
- region 地区（伊朗、欧洲、多瑙河…）        → 蓝色 #378ADD
- person 人名（领导人、发言人…）            → 玫红 #D4537E
- date   日期/时间（8月6日、十五五、上半年…）→ 琥珀 #EF9F27

输出：在原文基础上插入 <span class="hl hl-term">…</span> 标记，原文一字不改。
"""

import re

# 四类关键词表（构建期由外部数据源注入，此处为内置基础词表）
TERM_WORDS = [
    "高质量发展", "中国式现代化", "全面深化改革", "乡村振兴", "美丽乡村",
    "基层一线", "污水治理率", "增加值", "营收", "产业结构", "转型升级",
    "机械工业", "经济运行", "吸引外资", "外资结构", "特色产业", "全链升级",
    "核电技术", "华龙一号", "浮式风电平台", "台风", "特高压", "电子信息",
    "外汇贷款", "双枢纽", "标箱", "港航", "农业", "粮食", "工业", "制造业",
    "服务业", "消费", "投资", "出口", "进口", "贸易", "就业", "民生",
    "生态", "环境", "碳排放", "绿色低碳", "新能源", "可再生能源", "光伏",
    "风电", "水电", "氢能", "储能", "芯片", "半导体", "人工智能", "大数据",
    "云计算", "物联网", "数字经济", "网络安全", "航天", "探月", "空间站",
    "量子", "生物医药", "疫苗", "轨道交通", "高铁", "自贸区", "营商环境",
    "营商环境", "一带一路", "亚投行", "金砖", "上合", "RCEP", "APEC",
    "GDP", "CPI", "PMI", "进出口总额", "固定资产投资", "社会消费品零售",
    "五年规划", "十五五", "十四五", "供给侧", "需求侧", "实体经济",
]

# 人名/机构关键词（内置基础，可扩展）
PERSON_WORDS = [
    "习近平", "总书记", "主席", "总理", "委员长", "李强", "王沪宁",
    "蔡奇", "丁薛祥", "李希", "韩正", "胡锦涛", "温家宝", "李克强",
    "拜登", "特朗普", "普京", "泽连斯基", "内塔尼亚胡", "马克龙",
    "朔尔茨", "苏纳克", "莫迪", "岸田文雄", "尹锡悦", "金正恩",
    "古特雷斯", "拉夫罗夫", "布林肯", "发言人", "外交部", "国防部",
    "商务部", "发改委", "工信部", "农业农村部", "生态环境部", "财政部",
]

# 日期/时间关键词
DATE_PATTERNS = [
    r"\d{1,2}月\d{1,2}日", r"\d{1,2}月\d{1,2}号", r"\d{4}年",
    r"上半年", r"下半年", r"一季度", r"二季度", r"三季度", r"四季度",
    r"今年以来", r"去年", r"今年", r"昨日", r"今日", r"近日",
    r"周[一二三四五六日]", r"第\d+届", r"\d+周年", r"十五五",
    r"十四五", r"十三五", r"十一五", r"十二五", r"十九[大届]",
    r"二十[大届]", r"十八[大届]",
]

# 数字（含单位）模式
NUM_PATTERNS = [
    r"[+-]?\d+(?:\.\d+)?%",          # 百分比
    r"[+-]?\d+(?:\.\d+)?万亿",        # 万亿
    r"[+-]?\d+(?:\.\d+)?亿",          # 亿
    r"[+-]?\d+(?:\.\d+)?万",          # 万
    r"[+-]?\d+(?:\.\d+)?千",          # 千
    r"[+-]?\d+(?:\.\d+)?吨",          # 吨
    r"[+-]?\d+(?:\.\d+)?米",          # 米
    r"[+-]?\d+(?:\.\d+)?公里",        # 公里
    r"[+-]?\d+(?:\.\d+)?千米",        # 千米
    r"[+-]?\d+(?:\.\d+)?平方公里",    # 平方公里
    r"[+-]?\d+(?:\.\d+)?人次",        # 人次
    r"[+-]?\d+(?:\.\d+)?人",          # 人
    r"[+-]?\d+(?:\.\d+)?户",          # 户
    r"[+-]?\d+(?:\.\d+)?家",          # 家
    r"[+-]?\d+(?:\.\d+)?个",          # 个
    r"[+-]?\d+(?:\.\d+)?次",          # 次
    r"[+-]?\d+(?:\.\d+)?万标箱",      # 万标箱
    r"[+-]?\d+(?:\.\d+)?亿美元",      # 亿美元
    r"[+-]?\d+(?:\.\d+)?万亿元",      # 万亿元
    r"[+-]?\d+(?:\.\d+)?亿元",        # 亿元
    r"[+-]?\d+(?:\.\d+)?万元",        # 万元
]


def _merge_spans(spans):
    """合并重叠区间，返回不重叠的 (start, end, kind) 列表（按 start 排序）。"""
    spans.sort(key=lambda s: (s[0], -(s[1] - s[0])))
    merged = []
    for s, e, k in spans:
        if not merged or s >= merged[-1][1]:
            merged.append([s, e, k])
        elif e > merged[-1][1]:
            # 重叠且更长：按优先级保留，简单策略取先到的
            pass
    return [(a, b, c) for a, b, c in merged]


def highlight(text, region_words=None, exclude_words=None):
    """对文本进行四类关键字分色标记。

    region_words: 从地区词典注入的"关键词 → 地区名"映射，命中的标为 region 类。
    exclude_words: 仅用于归属、不作为地名高亮的词（如领导人名）。
    返回：标记后的 HTML 字符串（原文内容一字不改，仅包 <span>）。
    """
    if not text:
        return ""

    spans = []
    seen_texts = set()
    exclude = set(exclude_words or [])

    # 1) 地区词（词典注入，优先，排除归属专用词）
    if region_words:
        for kw in region_words:
            if kw in exclude:
                continue
            for m in re.finditer(re.escape(kw), text):
                # 避免在长词内部重复匹配（例如"俄罗斯"包含"俄"）
                if kw in seen_texts:
                    continue
                spans.append((m.start(), m.end(), "region"))
                seen_texts.add(kw)

    # 2) 专业名词
    for w in TERM_WORDS:
        for m in re.finditer(re.escape(w), text):
            if w in seen_texts:
                continue
            spans.append((m.start(), m.end(), "term"))
            seen_texts.add(w)

    # 3) 人名
    for w in PERSON_WORDS:
        for m in re.finditer(re.escape(w), text):
            if w in seen_texts:
                continue
            spans.append((m.start(), m.end(), "person"))
            seen_texts.add(w)

    # 4) 日期时间
    for pat in DATE_PATTERNS:
        for m in re.finditer(pat, text):
            w = m.group(0)
            if w in seen_texts:
                continue
            spans.append((m.start(), m.end(), "date"))
            seen_texts.add(w)

    # 5) 数字（关键数据）
    for pat in NUM_PATTERNS:
        for m in re.finditer(pat, text):
            w = m.group(0)
            if w in seen_texts:
                continue
            spans.append((m.start(), m.end(), "num"))
            seen_texts.add(w)

    merged = _merge_spans(spans)

    # 组装 HTML（逐段拼接）
    parts = []
    last = 0
    for s, e, k in merged:
        if s > last:
            parts.append(text[last:s])
        parts.append(f'<span class="hl hl-{k}">{text[s:e]}</span>')
        last = e
    if last < len(text):
        parts.append(text[last:])
    return "".join(parts)


def extract_keywords(text, region_words=None, exclude_words=None, limit=8):
    """提取文本中的关键字清单（用于前端高亮图例/筛选）。"""
    words = []
    exclude = set(exclude_words or [])
    for w in TERM_WORDS:
        if w in text:
            words.append(("term", w))
    if region_words:
        for kw in region_words:
            if kw in exclude:
                continue
            if kw in text:
                words.append(("region", kw))
    for w in PERSON_WORDS:
        if w in text:
            words.append(("person", w))
    for pat in DATE_PATTERNS:
        m = re.search(pat, text)
        if m and (m.group(0),) not in [(x,) for x in words]:
            words.append(("date", m.group(0)))
    for pat in NUM_PATTERNS:
        m = re.search(pat, text)
        if m and (m.group(0),) not in [(x,) for x in words]:
            words.append(("num", m.group(0)))
    # 去重并截断
    seen = set()
    out = []
    for k, w in words:
        if w not in seen:
            seen.add(w)
            out.append((k, w))
        if len(out) >= limit:
            break
    return out


if __name__ == "__main__":
    sample = ("今年上半年我国机械工业经济运行稳中有进，增加值同比增长5.0%，"
              "营收11.2万亿元。习近平主席近日在德国访问时强调高质量发展。"
              "8月6日，俄罗斯与乌克兰在黑海发生冲突，美国国务卿布林肯表示关注。")
    from region_dict import LOOKUP, HIGHLIGHT_EXCLUDE
    region_keys = [k for k in LOOKUP]
    html = highlight(sample, region_keys, HIGHLIGHT_EXCLUDE)
    print(html)
    print()
    for k, w in extract_keywords(sample, region_keys, HIGHLIGHT_EXCLUDE):
        print(f"{k}: {w}")
