/* 新闻联播 · 世界地图版 — 前端逻辑
 *
 * 数据加载：页面从全局变量 WORLD_MAP / DAILY_INDEX / DAILY_MAP 读取
 * （由 build_page.py 生成 data.js 注入，见 index.html 引入）
 *
 * 交互：
 *  1. 日期 Tab 切换 → 切换当日简报
 *  2. 类别筛选（头条/国内/国际/快讯/全部）
 *  3. 列表卡片点击 → 展开详情（完整正文+关键字标签云+多地区标签+元信息）
 *  4. 地图光点点击 / 地区标签点击 → 过滤列表 + 地图联动高亮
 *  5. 关键字分色高亮展示
 */

"use strict";

// ---------- 状态 ----------
const state = {
  currentDate: null,
  currentCategory: "all",
  currentRegion: null,
};

// ---------- DOM ----------
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];

const els = {
  dateTabs: $("#dateTabs"),
  listTitle: $("#listTitle"),
  newsList: $("#newsList"),
  listEmpty: $("#listEmpty"),
  legendKeywords: $("#legendKeywords"),
  categoryFilter: $("#categoryFilter"),
  worldMap: $("#worldMap"),
  landPath: $("#landPath"),
  countryHighlights: $("#countryHighlights"),
  mapPoints: $("#mapPoints"),
  mapLabels: $("#mapLabels"),
  mapTooltip: $("#mapTooltip"),
  regionCards: $("#regionCards"),
  btnReset: $("#btnReset"),
  fetchInfo: $("#fetchInfo"),
};

const CAT_CLASS = { "头条": "headline", "国内": "domestic", "国际": "intl", "快讯": "flash" };
const HL_LEGEND = [
  ["专业名词", "term"], ["地区", "region"], ["人名", "person"],
  ["日期", "date"], ["关键数字", "num"],
];

const MAP_W = 960, MAP_H = 480;
function project(lon, lat) {
  return [((lon + 180) / 360) * MAP_W, ((90 - lat) / 180) * MAP_H];
}

function init() {
  if (typeof WORLD_MAP === "undefined") {
    els.newsList.innerHTML = '<div class="list-empty">数据未加载：请先运行 python collector/build_page.py --gen-frontend</div>';
    return;
  }
  els.landPath.setAttribute("d", WORLD_MAP.landPath);
  renderDateTabs();
  const dates = DAILY_INDEX?.dates || [];
  if (dates.length) {
    const hashDate = (location.hash || "").replace("#", "");
    const target = (hashDate && DAILY_MAP[hashDate]) ? hashDate : dates[0].date;
    switchDate(target);
    // URL 参数 ?expand=N 自动展开第 N 条详情（调试/截图用）
    const expandIdx = parseInt(new URLSearchParams(location.search).get("expand") || "-1", 10);
    if (expandIdx >= 0) {
      setTimeout(() => {
        const cards = $$(".news-card", els.newsList);
        const card = cards[expandIdx];
        if (card) card.click();
      }, 50);
    }
  }
  bindEvents();
}

// ---------- 日期 Tab ----------
function renderDateTabs() {
  const dates = (DAILY_INDEX?.dates || []).slice(0, 30);
  els.dateTabs.innerHTML = "";
  dates.forEach((d, i) => {
    const b = document.createElement("button");
    b.className = "date-tab" + (i === 0 ? " active" : "");
    b.dataset.date = d.date;
    const [y, m, dd] = d.date.split("-");
    b.textContent = `${m}-${dd}${i === 0 ? " 最新" : ""}`;
    b.title = `${d.date} · ${d.total} 条要闻`;
    els.dateTabs.appendChild(b);
  });
}

function switchDate(dateStr) {
  state.currentDate = dateStr;
  state.currentRegion = null;
  state.currentCategory = "all";
  $$(".date-tab", els.dateTabs).forEach(t => t.classList.toggle("active", t.dataset.date === dateStr));
  $$(".chip", els.categoryFilter).forEach(c => c.classList.toggle("active", c.dataset.cat === "all"));
  const data = DAILY_MAP[dateStr];
  if (!data) return;
  const fetchedHint = data.fetched_at && data.fetched_at !== dateStr
    ? ` <span class="fetched-hint">（抓取于 ${data.fetched_at}）</span>` : "";
  els.listTitle.innerHTML = `节目日期 ${dateStr} · ${data.total} 条要闻${fetchedHint}`;
  renderLegend();
  renderList(data);
  renderMap(data);
  renderRegionCards(data);
}

// ---------- 关键字图例 ----------
function renderLegend() {
  els.legendKeywords.innerHTML = "";
  HL_LEGEND.forEach(([name, cls]) => {
    const s = document.createElement("span");
    const i = document.createElement("i");
    i.style.background = `var(--hl-${cls})`;
    s.appendChild(i);
    s.appendChild(document.createTextNode(name));
    els.legendKeywords.appendChild(s);
  });
}

// ---------- 列表渲染 ----------
function renderList(data) {
  const items = filterItems(data);
  els.newsList.innerHTML = "";
  els.listEmpty.hidden = items.length > 0;

  items.forEach(it => {
    const card = buildNewsCard(it, data);
    els.newsList.appendChild(card);
  });
}

function buildNewsCard(it, data) {
  const tpl = $("#newsItemTpl").content.cloneNode(true);
  const card = tpl.querySelector(".news-card");
  card.dataset.title = it.title;

  // 类别徽标
  const badge = tpl.querySelector(".cat-badge");
  badge.textContent = it.category;
  badge.classList.add(CAT_CLASS[it.category] || "");

  // 时长
  if (it.length) tpl.querySelector(".card-length").textContent = it.length;

  // 标题 + 高亮摘要
  tpl.querySelector(".card-title").textContent = it.title;

  // 卡顶关键数据点（折叠态可见）
  const kpBox = tpl.querySelector(".key-points");
  (it.key_points || []).slice(0, 4).forEach(p => {
    const tag = document.createElement("span");
    tag.className = "kp";
    tag.textContent = p;
    kpBox.appendChild(tag);
  });

  tpl.querySelector(".card-summary").innerHTML = it.highlighted || it.summary;

  // 地区标签（卡片顶部预览）
  const rc = tpl.querySelector(".card-regions");
  (it.regions || []).slice(0, 4).forEach(r => {
    const tag = document.createElement("span");
    tag.className = "region-tag";
    tag.textContent = r.name;
    rc.appendChild(tag);
  });

  // 展开/收起
  const toggle = tpl.querySelector(".card-toggle");
  const detail = tpl.querySelector(".card-detail");
  toggle.addEventListener("click", (e) => {
    e.stopPropagation();
    toggleDetail(card, toggle, detail, it, data);
  });
  card.addEventListener("click", () => {
    toggleDetail(card, toggle, detail, it, data);
    if (it.regions && it.regions.length) flyToRegion(it.regions[0], data);
  });

  // ----- 详情区填充 -----
  populateDetail(card, it, data);

  // ----- "接着看"按钮 -----
  setupNextButton(card, it, data);

  return card;
}

function populateDetail(card, it, data) {
  // 1. 元信息条
  const meta = card.querySelector(".detail-meta");
  const parts = [];
  if (it.length) parts.push(`<span>时长：${it.length}</span>`);
  if (it.category_detail) parts.push(`<span>栏目：${it.category_detail}</span>`);
  if (it.create_date) parts.push(`<span>播出：${it.create_date}</span>`);
  if (it.url) parts.push(`<a href="${it.url}" target="_blank" rel="noopener">央视网原链接 ↗</a>`);
  meta.innerHTML = parts.join("");

  // 2. 视频封面（如果有）
  const imgWrap = card.querySelector(".detail-image");
  if (it.image) {
    imgWrap.innerHTML = `<img src="${it.image}" alt="封面图" loading="lazy" onerror="this.style.display='none'">`;
    imgWrap.style.display = "block";
  } else {
    imgWrap.style.display = "none";
  }

  // 3. 关键字标签云
  const cloud = card.querySelector(".keyword-cloud");
  cloud.innerHTML = "";
  (it.keywords || []).slice(0, 12).forEach(k => {
    const tag = document.createElement("span");
    tag.className = `kw-tag kw-${k.type}`;
    tag.textContent = k.word;
    cloud.appendChild(tag);
  });

  // 4. 多地区联动标签
  const regBox = card.querySelector(".detail-regions");
  regBox.innerHTML = "";
  (it.regions || []).forEach(r => {
    const tag = document.createElement("button");
    tag.className = "region-link";
    tag.innerHTML = `<i class="rl-dot"></i>${r.name}<span class="rl-kw">"${r.kw}"</span>`;
    tag.addEventListener("click", (e) => {
      e.stopPropagation();
      const regionObj = data.points.find(p => p.name === r.name);
      if (regionObj) {
        state.currentRegion = r.name;
        renderList(data);
        flyToRegion(regionObj, data);
      }
    });
    regBox.appendChild(tag);
  });

  // 5. 完整正文（按段落，保留高亮）
  const body = card.querySelector(".detail-body");
  const paras = it.paragraphs_highlighted && it.paragraphs_highlighted.length
    ? it.paragraphs_highlighted
    : [it.highlighted || it.summary];
  body.innerHTML = paras.map(p => `<p>${p}</p>`).join("");
}

function filterItems(data) {
  let items = data.items || [];
  if (state.currentRegion) {
    items = items.filter(it => (it.regions || []).some(r => r.name === state.currentRegion));
  }
  if (state.currentCategory !== "all") {
    items = items.filter(it => it.category === state.currentCategory);
  }
  return items;
}

function setupNextButton(card, it, data) {
  const btn = card.querySelector(".next-news-btn");
  if (!btn) return;
  const cards = $$(".news-card", els.newsList);
  const idx = cards.indexOf(card);
  const nextCard = cards[idx + 1];
  if (!nextCard) return;
  const nextTitle = nextCard.querySelector(".card-title")?.textContent || "";
  btn.querySelector(".next-title").textContent = nextTitle.slice(0, 22) + (nextTitle.length > 22 ? "…" : "");
  btn.hidden = false;
  btn.addEventListener("click", (e) => {
    e.stopPropagation();
    nextCard.scrollIntoView({ behavior: "smooth", block: "start" });
    // 600ms 后自动展开下一条详情（滚动 + 展开连贯）
    setTimeout(() => {
      const t = nextCard.querySelector(".card-toggle");
      const d = nextCard.querySelector(".card-detail");
      toggleDetail(nextCard, t, d, null, data);
    }, 600);
  });
}


function toggleDetail(card, toggle, detail, it, data) {
  const isOpen = card.classList.toggle("expanded");
  detail.hidden = !isOpen;
  toggle.setAttribute("aria-expanded", String(isOpen));
  toggle.querySelector(".toggle-label").textContent = isOpen ? "收起详情" : "展开详情";
}

// ---------- 地图渲染 ----------
function renderMap(data) {
  els.countryHighlights.innerHTML = "";
  els.mapPoints.innerHTML = "";
  els.mapLabels.innerHTML = "";

  // 国家轮廓高亮
  const isoSet = new Set();
  (data.points || []).forEach(p => { if (p.iso) isoSet.add(p.iso); });
  if (isoSet.size && WORLD_MAP.countries) {
    WORLD_MAP.countries.forEach(c => {
      if (isoSet.has(c.iso)) {
        const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
        path.setAttribute("d", c.path);
        path.setAttribute("class", "country-hl");
        els.countryHighlights.appendChild(path);
      }
    });
  }

  // 光点（大小按 count）
  const maxC = Math.max(1, ...(data.points || []).map(p => p.count));
  (data.points || []).forEach(p => {
    const [x, y] = project(p.lon, p.lat);
    const r = 5 + (p.count / maxC) * 7;
    const color = p.iso === "CHN" ? "#34d399" : "#f472b6";

    const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
    g.setAttribute("class", "map-point");
    g.dataset.name = p.name;

    const ring = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    ring.setAttribute("cx", x); ring.setAttribute("cy", y); ring.setAttribute("r", r);
    ring.setAttribute("fill", "none"); ring.setAttribute("stroke", color);
    ring.setAttribute("stroke-width", "1.5"); ring.setAttribute("class", "ring");

    const dot = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    dot.setAttribute("cx", x); dot.setAttribute("cy", y); dot.setAttribute("r", r);
    dot.setAttribute("fill", color); dot.setAttribute("opacity", "0.9");
    dot.setAttribute("stroke", "rgba(255,255,255,.35)");

    g.appendChild(ring); g.appendChild(dot);
    g.addEventListener("click", () => selectRegion(p, data));
    g.addEventListener("mousemove", (e) => showTooltip(e, p));
    g.addEventListener("mouseleave", hideTooltip);
    els.mapPoints.appendChild(g);

    const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
    label.setAttribute("x", x); label.setAttribute("y", y - r - 4);
    label.setAttribute("text-anchor", "middle");
    label.setAttribute("class", "map-label");
    label.textContent = `${p.name} ${p.count}`;
    els.mapLabels.appendChild(label);
  });
}

// ---------- 地图交互 ----------
function selectRegion(region, data) {
  const wasSelected = state.currentRegion === region.name;
  state.currentRegion = wasSelected ? null : region.name;
  $$(".map-point", els.mapPoints).forEach(g => {
    g.classList.toggle("selected", g.dataset.name === state.currentRegion);
  });
  renderList(data);
  renderRegionCards(data);
  if (!wasSelected) flyToRegion(region, data);
  else resetMapView();
}

function flyToRegion(region, data) {
  const [x, y] = project(region.lon, region.lat);
  const zoom = 3.2;
  const nw = MAP_W / zoom, nh = MAP_H / zoom;
  const vx = Math.max(0, Math.min(MAP_W - nw, x - nw / 2));
  const vy = Math.max(0, Math.min(MAP_H - nh, y - nh / 2));
  // 丝滑慢慢放大：1.6s + 平滑缓动（cubic-bezier 双向缓动）
  els.worldMap.style.transition = "viewBox 1.6s cubic-bezier(0.45, 0.05, 0.25, 1)";
  els.worldMap.setAttribute("viewBox", `${vx} ${vy} ${nw} ${nh}`);
}

function resetMapView() {
  // 同步慢速回到全貌，保持动画一致性
  els.worldMap.style.transition = "viewBox 1.4s cubic-bezier(0.45, 0.05, 0.25, 1)";
  els.worldMap.setAttribute("viewBox", `0 0 ${MAP_W} ${MAP_H}`);
}

function showTooltip(e, region) {
  els.mapTooltip.hidden = false;
  const title = region.items ? region.items.slice(0, 3) : [];
  els.mapTooltip.innerHTML = `<b>${region.name}</b>（${region.count} 条）
    ${title.length ? `<ul>${title.map(t => `<li>${esc(t)}</li>`).join("")}</ul>` : ""}`;
  const wrap = $("#mapWrap").getBoundingClientRect();
  els.mapTooltip.style.left = `${e.clientX - wrap.left + 14}px`;
  els.mapTooltip.style.top = `${e.clientY - wrap.top - 10}px`;
}
function hideTooltip() { els.mapTooltip.hidden = true; }
function esc(s) { return (s || "").replace(/[<>&"]/g, c => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;" }[c])); }

// ---------- 地区卡片 ----------
function renderRegionCards(data) {
  els.regionCards.innerHTML = "";
  (data.points || []).forEach(p => {
    const tpl = $("#regionCardTpl").content.cloneNode(true);
    tpl.querySelector(".rc-name").textContent = p.name;
    tpl.querySelector(".rc-count").textContent = `${p.count} 条`;
    const ul = tpl.querySelector(".rc-items");
    (p.items || []).slice(0, 4).forEach(t => {
      const li = document.createElement("li");
      li.textContent = t;
      ul.appendChild(li);
    });
    const card = tpl.querySelector(".region-card");
    card.style.cursor = "pointer";
    card.addEventListener("click", () => selectRegion(p, data));
    els.regionCards.appendChild(tpl);
  });
}

// ---------- 事件绑定 ----------
function bindEvents() {
  els.dateTabs.addEventListener("click", (e) => {
    const tab = e.target.closest(".date-tab");
    if (!tab) return;
    switchDate(tab.dataset.date);
  });
  els.categoryFilter.addEventListener("click", (e) => {
    const chip = e.target.closest(".chip");
    if (!chip) return;
    state.currentCategory = chip.dataset.cat;
    $$(".chip", els.categoryFilter).forEach(c => c.classList.toggle("active", c === chip));
    const data = DAILY_MAP[state.currentDate];
    if (data) renderList(data);
  });
  els.btnReset.addEventListener("click", () => {
    state.currentRegion = null;
    $$(".map-point", els.mapPoints).forEach(g => g.classList.remove("selected"));
    const data = DAILY_MAP[state.currentDate];
    if (data) { renderList(data); renderRegionCards(data); }
    resetMapView();
  });
}

document.addEventListener("DOMContentLoaded", init);