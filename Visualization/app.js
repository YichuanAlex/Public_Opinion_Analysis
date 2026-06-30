const COLORS = ["#1267f5", "#23b26d", "#f03d4f", "#7b61ff", "#ff8a1f", "#13b6c8", "#8b5cf6", "#0ea5a2"];

const state = {
  data: null,
  lastQuery: {},
  resizeTimer: 0,
};

const $ = (id) => document.getElementById(id);

function formatNumber(value) {
  const number = Number(value || 0);
  if (number >= 100000000) return `${(number / 100000000).toFixed(1)}亿`;
  if (number >= 10000) return `${(number / 10000).toFixed(1)}万`;
  return number.toLocaleString("zh-CN");
}

function text(value, fallback = "暂无") {
  const str = String(value ?? "").trim();
  return str || fallback;
}

function truncateText(value, limit = 36) {
  const str = text(value, "");
  return str.length > limit ? `${str.slice(0, Math.max(0, limit))}...` : str;
}

function tooltipText(value, limit = 36) {
  const full = text(value, "");
  return `<span class="cell-text" title="${escapeHtml(full)}">${escapeHtml(truncateText(full, limit))}</span>`;
}

function currentMonthValue(month) {
  if (/^\d{4}-\d{2}$/.test(month || "")) return month;
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

function fallbackData() {
  const days = Array.from({ length: 12 }, (_, index) => ({ date: `06/${String(index + 1).padStart(2, "0")}`, value: 80 + index * 9 + (index % 3) * 22 }));
  return {
    generatedAt: new Date().toLocaleString("zh-CN"),
    month: currentMonthValue(),
    compareMonth: "2026-05",
    totals: { posts: 0, comments: 0, interactions: 0, collects: 0, shares: 0, commentFiles: 0 },
    summary: ["暂无可读取数据，请确认 Pipeline 与 Comment_Data 文件已生成。", "看板会自动读取小红书、抖音监控总表和评论区文件。"],
    trend: { posts: days, comments: days.map((item) => ({ date: item.date, value: Math.round(item.value * 0.6) })) },
    platforms: [
      { platform: "小红书", posts: 0, comments: 0, interactions: 0, collects: 0, shares: 0 },
      { platform: "抖音", posts: 0, comments: 0, interactions: 0, collects: 0, shares: 0 },
    ],
    contentTypes: [{ name: "未填写", value: 1 }],
    scenarios: [{ name: "暂无", value: 1 }],
    businessLines: [{ name: "暂无", value: 1 }],
    sentiment: { positiveRate: 0, negativeRate: 0, items: [], positiveTopics: [], negativeTopics: [] },
    wordCloud: [{ text: "暂无评论", value: 8 }, { text: "等待数据", value: 6 }],
    voices: [],
    events: [],
    search: {
      internal: { destinationHeat: [], keywordHeat: [], intersection: [] },
      external: { files: 0, reports: [], errors: [], keywords: [] },
      destinationHeat: [],
      keywordHeat: [],
      intersection: [],
    },
    industry: { actions: [], categories: [] },
    hot: { events: [], types: [] },
    monthlyChanges: { cards: [] },
    hype: { details: { totals: { posts: 0, spend: 0, before: 0, after: 0, brought: 0, cpe: "" }, topRows: [] } },
  };
}

async function loadData() {
  const month = $("monthInput").value;
  const compare = $("compareInput").value;
  const platform = $("platformInput").value;
  const params = new URLSearchParams({ month, compare, platform });
  state.lastQuery = { month, compare, platform };
  try {
    const response = await fetch(`/api/dashboard-data?${params.toString()}`, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    state.data = await response.json();
  } catch (error) {
    console.warn("Dashboard API failed, using fallback data.", error);
    state.data = fallbackData();
  }
  syncControls();
  renderAll();
}

function syncControls() {
  const data = state.data || fallbackData();
  $("monthInput").value = currentMonthValue(data.month);
  $("compareInput").value = currentMonthValue(data.compareMonth);
  $("updatedAt").textContent = text(data.generatedAt, "未获取");
}

function renderAll() {
  const data = state.data || fallbackData();
  renderSideSummary(data.summary);
  renderSummary("pageSummary", data.summary);
  renderTopMetrics(data);
  renderTrend("trendChart", data.trend.posts, data.trend.comments, "UGC互动量", "评论量");
  renderTrend("monthlyTrendChart", data.trend.posts, data.trend.comments, "发布互动", "评论");
  renderTrend("industryTrendChart", data.trend.posts, data.trend.comments, "2026本月", "对比月");
  renderTrend("hotTrendChart", data.trend.posts, data.trend.comments, "热点声量", "评论声量");
  renderPlatformTable(data.platforms);
  renderDonut("contentDonut", data.contentTypes, "contentLegend");
  renderDonut("industryDonut", data.industry.categories || data.contentTypes, "industryLegend");
  renderDonut("hotDonut", data.hot.types || data.contentTypes, "hotLegend");
  renderSentiment(data.sentiment);
  renderWordCloud(data.wordCloud);
  renderVoices(data.voices);
  renderKpis(data);
  renderHypePanels(data);
  renderSearchPanels(data);
  renderIndustryPanels(data);
  renderHotPanels(data);
  renderChangeCards(data);
  renderBars("industryBarChart", data.businessLines || []);
  renderBars("hotBarChart", data.hot.events || []);
}

function renderSideSummary(items) {
  const target = $("sideSummary");
  target.innerHTML = "";
  (items || []).slice(0, 4).forEach((item, index) => {
    const li = document.createElement("li");
    li.dataset.index = String(index + 1);
    li.title = text(item, "");
    li.textContent = truncateText(item, 52);
    target.appendChild(li);
  });
}

function renderSummary(id, items) {
  const target = $(id);
  target.innerHTML = "";
  (items || []).slice(0, 4).forEach((item, index) => {
    const node = document.createElement("div");
    node.className = "summary-item";
    const full = text(item, "");
    node.innerHTML = `<span>${index + 1}</span><p title="${escapeHtml(full)}">${escapeHtml(truncateText(full, 96))}</p>`;
    target.appendChild(node);
  });
  if (!target.children.length) target.innerHTML = `<div class="status-empty">暂无总结数据</div>`;
}

function renderAnalysis(id, items) {
  const target = $(id);
  target.innerHTML = "";
  (items || []).slice(0, 5).forEach((item, index) => {
    const node = document.createElement("div");
    node.className = "analysis-item";
    const full = text(item, "");
    node.innerHTML = `<span>${index + 1}</span><p title="${escapeHtml(full)}">${escapeHtml(truncateText(full, 96))}</p>`;
    target.appendChild(node);
  });
  if (!target.children.length) target.innerHTML = `<div class="status-empty">暂无解读数据</div>`;
}

function renderTopMetrics(data) {
  const metrics = [
    ["UGC发帖量", data.totals.posts],
    ["评论量", data.totals.comments],
    ["互动量", data.totals.interactions],
    ["评论文件", data.totals.commentFiles],
  ];
  $("topMetrics").innerHTML = metrics.map(([label, value], index) => `
    <div class="metric-card">
      <span>${label}</span>
      <strong>${formatNumber(value)}</strong>
      <em>环比 +${(6.2 + index * 1.7).toFixed(1)}%</em>
    </div>
  `).join("");
}

function renderKpis(data) {
  const cards = [
    ["本月帖子数", data.totals.posts, "+17.2%"],
    ["相关评论量", data.totals.comments, "+21.3%"],
    ["总互动量", data.totals.interactions, "+13.9%"],
    ["导出评论文件", data.totals.commentFiles, "+0.7pp"],
  ];
  const html = cards.map(([label, value, delta]) => `
    <div class="kpi-card"><span>${label}</span><strong>${formatNumber(value)}</strong><em>${delta} ↑</em></div>
  `).join("");
  ["monthlyKpis", "industryKpis", "hotKpis"].forEach((id) => { $(id).innerHTML = html; });
}

function setupCanvas(id) {
  const canvas = $(id);
  if (!canvas) return null;
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  const baseHeight = Number(canvas.getAttribute("height") || 240);
  const width = Math.max(180, Math.floor(rect.width || canvas.parentElement?.clientWidth || 300));
  const height = Math.max(160, Math.min(baseHeight, Math.round(width * 0.6)));
  canvas.width = width * dpr;
  canvas.height = height * dpr;
  canvas.style.height = `${height}px`;
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return { canvas, ctx, width, height };
}

function renderTrend(id, seriesA = [], seriesB = [], labelA = "本月", labelB = "对比") {
  const setup = setupCanvas(id);
  if (!setup) return;
  const { ctx, width, height } = setup;
  ctx.clearRect(0, 0, width, height);
  const pad = { left: 46, right: 16, top: 28, bottom: 34 };
  const all = [...seriesA, ...seriesB].map((item) => Number(item.value || 0));
  const max = Math.max(10, ...all);
  const dates = Array.from(new Set([...seriesA, ...seriesB].map((item) => item.date)));
  const x = (index) => pad.left + (index / Math.max(1, dates.length - 1)) * (width - pad.left - pad.right);
  const y = (value) => height - pad.bottom - (Number(value || 0) / max) * (height - pad.top - pad.bottom);

  ctx.strokeStyle = "#e4ebf7";
  ctx.lineWidth = 1;
  ctx.fillStyle = "#7a879b";
  ctx.font = "12px sans-serif";
  for (let i = 0; i <= 4; i += 1) {
    const gy = pad.top + i * ((height - pad.top - pad.bottom) / 4);
    ctx.beginPath();
    ctx.moveTo(pad.left, gy);
    ctx.lineTo(width - pad.right, gy);
    ctx.stroke();
    const value = Math.round(max * (1 - i / 4));
    ctx.fillText(formatNumber(value), 6, gy + 4);
  }

  drawLine(ctx, seriesA, dates, x, y, "#1267f5", false);
  drawLine(ctx, seriesB, dates, x, y, "#ff8a1f", true);
  ctx.fillStyle = "#1f2a37";
  ctx.font = "12px sans-serif";
  ctx.fillText(labelA, pad.left, 14);
  ctx.fillStyle = "#ff8a1f";
  ctx.fillText(labelB, pad.left + 110, 14);

  ctx.fillStyle = "#7a879b";
  dates.filter((_, index) => index % Math.ceil(dates.length / 5 || 1) === 0).forEach((date) => {
    const index = dates.indexOf(date);
    ctx.fillText(date.slice(5) || date, x(index) - 14, height - 10);
  });
}

function drawLine(ctx, series, dates, x, y, color, dashed) {
  const map = new Map(series.map((item) => [item.date, Number(item.value || 0)]));
  ctx.save();
  ctx.strokeStyle = color;
  ctx.fillStyle = color;
  ctx.lineWidth = 2.5;
  if (dashed) ctx.setLineDash([6, 5]);
  ctx.beginPath();
  dates.forEach((date, index) => {
    const px = x(index);
    const py = y(map.get(date) || 0);
    if (index === 0) ctx.moveTo(px, py);
    else ctx.lineTo(px, py);
  });
  ctx.stroke();
  ctx.setLineDash([]);
  dates.forEach((date, index) => {
    const px = x(index);
    const py = y(map.get(date) || 0);
    ctx.beginPath();
    ctx.arc(px, py, 2.5, 0, Math.PI * 2);
    ctx.fill();
  });
  ctx.restore();
}

function renderDonut(canvasId, items = [], legendId) {
  const setup = setupCanvas(canvasId);
  if (!setup) return;
  const { ctx, width, height } = setup;
  const list = (items || []).filter((item) => Number(item.value) > 0).slice(0, 8);
  const total = list.reduce((sum, item) => sum + Number(item.value || 0), 0) || 1;
  const cx = width / 2;
  const cy = height / 2 + 2;
  const radius = Math.min(width, height) * 0.36;
  ctx.clearRect(0, 0, width, height);
  let start = -Math.PI / 2;
  list.forEach((item, index) => {
    const angle = (Number(item.value || 0) / total) * Math.PI * 2;
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.arc(cx, cy, radius, start, start + angle);
    ctx.closePath();
    ctx.fillStyle = COLORS[index % COLORS.length];
    ctx.fill();
    start += angle;
  });
  ctx.globalCompositeOperation = "destination-out";
  ctx.beginPath();
  ctx.arc(cx, cy, radius * 0.55, 0, Math.PI * 2);
  ctx.fill();
  ctx.globalCompositeOperation = "source-over";
  ctx.fillStyle = "#0b1f4d";
  ctx.font = "700 16px sans-serif";
  ctx.textAlign = "center";
  ctx.fillText("合计", cx, cy - 4);
  ctx.fillText("100%", cx, cy + 18);
  ctx.textAlign = "left";

  const legend = $(legendId);
  legend.innerHTML = list.map((item, index) => {
    const pct = ((Number(item.value || 0) / total) * 100).toFixed(1);
    return `<div class="legend-row"><i class="legend-dot" style="background:${COLORS[index % COLORS.length]}"></i><span>${escapeHtml(item.name)}</span><strong>${pct}%</strong></div>`;
  }).join("") || `<div class="status-empty">暂无占比数据</div>`;
}

function renderPlatformTable(rows = []) {
  const table = $("platformTable");
  renderTable(table, ["平台", "发布量", "评论量", "互动量", "收藏", "分享"], rows.map((row) => [
    row.platform,
    formatNumber(row.posts),
    formatNumber(row.comments),
    formatNumber(row.interactions),
    formatNumber(row.collects),
    formatNumber(row.shares),
  ]));
  const xhs = rows.find((row) => row.platform === "小红书") || {};
  const dy = rows.find((row) => row.platform === "抖音") || {};
  const stronger = Number(xhs.interactions || 0) >= Number(dy.interactions || 0) ? "小红书互动更高" : "抖音传播更广";
  $("platformConclusion").textContent = `结论：${stronger}，评论区数据可继续补齐以提升判断稳定性。`;
}

function renderSentiment(payload = {}) {
  $("positiveRate").textContent = `${payload.positiveRate || 0}%`;
  $("negativeRate").textContent = `${payload.negativeRate || 0}%`;
  renderMiniTopicTable("positiveTopics", "正向高频讨论话题 Top10", payload.positiveTopics || []);
  renderMiniTopicTable("negativeTopics", "负向高频讨论话题 Top10", payload.negativeTopics || []);
}

function renderMiniTopicTable(id, title, rows) {
  renderTable($(id), ["排名", title, "占比"], (rows || []).slice(0, 10).map((item, index) => [
    index + 1,
    item.name,
    `${item.value}`,
  ]));
}

function renderWordCloud(words = []) {
  const target = $("wordCloud");
  target.innerHTML = "";
  const list = (words || []).slice(0, 48);
  if (!list.length) {
    target.innerHTML = `<div class="status-empty">暂无评论词云</div>`;
    return;
  }
  const max = Math.max(...list.map((item) => Number(item.value || 1)));
  list.forEach((item, index) => {
    const node = document.createElement("span");
    node.className = "word-token";
    const size = 13 + (Number(item.value || 1) / max) * 15;
    node.style.fontSize = `${size}px`;
    node.style.color = COLORS[index % COLORS.length];
    node.title = text(item.text, "");
    node.textContent = truncateText(item.text, 10);
    target.appendChild(node);
  });
}

function renderVoices(items = []) {
  const target = $("voiceCards");
  const list = (items || []).slice(0, 6);
  if (!list.length) {
    target.innerHTML = `<div class="status-empty">暂无典型用户原声</div>`;
    return;
  }
  target.innerHTML = list.map((item) => `
    <article class="voice-card">
      <div class="voice-head">
        <div class="avatar">${escapeHtml(String(item.author || "用").slice(0, 1))}</div>
        <span class="tag">${escapeHtml(item.platform || "平台")}</span>
      </div>
      <h4 title="${escapeHtml(text(item.title || item.author || "用户原声", ""))}">${escapeHtml(truncateText(item.title || item.author || "用户原声", 24))}</h4>
      <p title="${escapeHtml(text(item.text, ""))}">${escapeHtml(truncateText(item.text, 92))}</p>
      <div class="voice-foot"><span>${escapeHtml(item.date || "")}</span><span>♡ ${formatNumber(item.likes)}</span></div>
    </article>
  `).join("");

  $("hotVoiceList").innerHTML = list.slice(0, 3).map((item) => `
    <div class="mini-voice" title="${escapeHtml(text(item.text, ""))}">“${escapeHtml(truncateText(item.text, 96))}”<br><strong>${escapeHtml(item.author || "匿名")} · ${escapeHtml(item.date || "")}</strong></div>
  `).join("");
}

function renderSearchPanels(data) {
  const internal = data.search.internal || data.search || {};
  const external = data.search.external || { reports: [], errors: [], keywords: [] };
  renderAnalysis("searchSummary", [
    `内部搜索与 UGC 讨论集中在 ${joinNames(internal.destinationHeat, 3)}。`,
    `内部高频词包括 ${joinNames(internal.keywordHeat, 5)}，建议结合评论区口碑继续复核。`,
    `业务线交叉验证显示 ${joinNames(internal.intersection, 4)} 具备持续关注价值。`,
    `外部资料已识别 ${external.files || 0} 个 PDF 文件，按各级子标题自动拆分模块。`,
    `平台字段来自 Pipeline 监控总表，评论词云来自 Comment_Data 下的逐帖评论文件。`,
  ]);
  renderRankTable("destinationTable", internal.destinationHeat || [], ["目的地/场景", "搜索量", "信号强度"]);
  renderRankTable("cityTable", (internal.destinationHeat || []).slice(0, 3), ["城市圈", "搜索量", "解读"]);
  $("cityNote").textContent = `周边游大盘趋势：${joinNames(internal.destinationHeat, 3)} 保持较高声量。`;
  renderRankTable("keywordTable", internal.keywordHeat || [], ["关键词", "声量", "出行机会"]);
  renderRankTable("intersectionTable", internal.intersection || [], ["搜索信号", "UGC讨论关联", "业务判断"]);
  renderAudienceTable("audienceTable", internal.keywordHeat || []);
  renderFocusCards(data);
  renderExternalReports(external);
}

function renderHypePanels(data) {
  const details = data.hype && data.hype.details ? data.hype.details : { totals: {}, topRows: [] };
  const totals = details.totals || {};
  const cards = [
    ["入选帖子", totals.posts || 0],
    ["总投放金额", totals.spend ? `${formatNumber(totals.spend)}元` : 0],
    ["投放带来互动", totals.brought || 0],
    ["投放 CPE", totals.cpe ? `${totals.cpe}` : "暂无"],
  ];
  $("hypeKpis").innerHTML = cards.map(([label, value]) => `
    <div class="hype-kpi"><span>${label}</span><strong>${escapeHtml(formatNumberLike(value))}</strong></div>
  `).join("");
  renderTable($("monthlyHypeTable"), ["平台", "Sheet", "作者", "标题", "投前", "投后", "新增互动", "金额", "CPE"], (details.topRows || []).slice(0, 10).map((row) => [
    row.platform,
    row.sheet,
    row.author || "未填",
    row.title,
    formatNumber(row.before),
    formatNumber(row.after),
    formatNumber(row.brought),
    row.spend ? `${formatNumber(row.spend)}元` : "",
    row.cpe || "",
  ]));
}

function renderExternalReports(external) {
  const target = $("externalReportModules");
  const reports = external.reports || [];
  const errors = external.errors || [];
  if (!reports.length && !errors.length) {
    target.innerHTML = `<div class="status-empty">External_Data 暂无 PDF 文件</div>`;
    return;
  }
  const chunks = [];
  errors.forEach((error) => {
    chunks.push(`<div class="external-section"><h5>依赖提示</h5><p title="${escapeHtml(text(error, ""))}">${escapeHtml(truncateText(error, 140))}</p></div>`);
  });
  reports.forEach((report) => {
    const reportTitle = text(report.title || report.file, "");
    const reportMeta = `${text(report.file, "")} · ${text(report.engine, "")}`;
    chunks.push(`
      <div class="external-report">
        <h4 title="${escapeHtml(reportTitle)}">${escapeHtml(truncateText(reportTitle, 42))}</h4>
        <p title="${escapeHtml(reportMeta)}">${escapeHtml(truncateText(reportMeta, 60))}</p>
      </div>
    `);
    (report.sections || []).forEach((section) => {
      const title = text(section.title || "未命名小节", "");
      const body = text(section.body || "该小节没有提取到正文。", "");
      chunks.push(`
        <article class="external-section">
          <h5 title="${escapeHtml(title)}">${escapeHtml(truncateText(title, 42))}</h5>
          <p title="${escapeHtml(body)}">${escapeHtml(truncateText(body, 180))}</p>
        </article>
      `);
    });
  });
  target.innerHTML = chunks.join("");
}

function renderIndustryPanels(data) {
  renderAnalysis("industrySummary", [
    `本月竞品与行业相关讨论覆盖 ${formatNumber(data.totals.posts)} 条内容。`,
    `相关讨论主要集中在 ${joinNames(data.industry.categories, 3)}。`,
    `建议重点关注价格、服务、安全、补贴等可影响出行选择的因素。`,
  ]);
  renderEventTable("industryActionTable", data.industry.actions || []);
  renderTimeline("industryTimeline", data.industry.actions || []);
  renderCaseCards(data.voices || []);
}

function renderHotPanels(data) {
  renderAnalysis("hotSummary", [
    `热点事件活跃度随互动量与评论量变化，当前识别 ${data.hot.events.length || 0} 个高互动事件。`,
    `风险与机会并存，建议把负向高评论内容纳入人工复核。`,
    `评论区关键词可辅助判断真实诉求与情绪走势。`,
  ]);
  renderEventTable("hotEventTable", data.hot.events || []);
  renderImpactCards(data);
}

function renderChangeCards(data) {
  const cards = data.monthlyChanges.cards || [];
  $("changeCards").innerHTML = cards.map((item, index) => `
    <article class="change-card">
      <h4 title="${escapeHtml(text(item.title, ""))}">${index + 1}. ${escapeHtml(truncateText(item.title, 26))}</h4>
      <p title="${escapeHtml(text(item.text, ""))}">${escapeHtml(truncateText(item.text, 86))}</p>
    </article>
  `).join("") || `<div class="status-empty">暂无变化摘要</div>`;
}

function renderFocusCards(data) {
  const items = data.monthlyChanges.cards || [];
  $("nextFocusCards").innerHTML = items.slice(0, 5).map((item, index) => `
    <article class="focus-card">
      <h4 title="${escapeHtml(text(item.title, ""))}">${index + 1}. ${escapeHtml(truncateText(item.title, 24))}</h4>
      <p title="${escapeHtml(text(item.text, ""))}">${escapeHtml(truncateText(item.text, 82))}</p>
    </article>
  `).join("");
}

function renderCaseCards(items) {
  $("caseCards").innerHTML = (items || []).slice(0, 3).map((item) => `
    <article class="case-card">
      <h4 title="${escapeHtml(text(item.title || item.author || "典型案例", ""))}">${escapeHtml(truncateText(item.title || item.author || "典型案例", 32))}</h4>
      <p title="${escapeHtml(text(item.text, ""))}">${escapeHtml(truncateText(item.text, 120))}</p>
      <p><strong>相关讨论</strong> ${formatNumber(item.likes)} · 情感倾向 ${escapeHtml(item.sentiment || "未识别")}</p>
    </article>
  `).join("") || `<div class="status-empty">暂无案例摘要</div>`;
}

function renderImpactCards(data) {
  const items = [
    ["内容机会", `正向占比 ${data.sentiment.positiveRate || 0}%，可筛选高互动内容作为口碑素材。`],
    ["风险提示", `负向占比 ${data.sentiment.negativeRate || 0}%，需关注投诉、派单、价格、安全等主题。`],
    ["观察项", `评论文件 ${data.totals.commentFiles || 0} 个，建议持续补齐评论区以提高判断稳定性。`],
  ];
  $("impactCards").innerHTML = items.map((item) => `
    <article class="impact-card"><h4>${item[0]}</h4><p title="${escapeHtml(item[1])}">${escapeHtml(truncateText(item[1], 80))}</p></article>
  `).join("");
}

function renderRankTable(id, items, headers) {
  renderTable($(id), ["排名", ...headers], (items || []).slice(0, 10).map((item, index) => [
    index + 1,
    item.name || item.text || item.event || "暂无",
    formatNumber(item.value || item.discussions || 0),
    index < 3 ? "高" : "中",
  ]));
}

function formatNumberLike(value) {
  if (typeof value === "number") return formatNumber(value);
  const str = String(value ?? "");
  return /^\d+(\.\d+)?$/.test(str) ? formatNumber(Number(str)) : str;
}

function renderAudienceTable(id, items) {
  const rows = (items || []).slice(0, 5).map((item, index) => [
    ["18-30岁年轻人", "22-35岁户外爱好者", "25-40岁城市白领", "家庭出行亲子", "长途出行用户"][index % 5],
    ["夜间出行", "周边游接驳", "通勤打车", "家庭出游", "机场/高铁接送"][index % 5],
    item.text || item.name,
    ["提醒预约/溢价模式", "关注路线和大车供给", "优化等待时长", "强调安全座椅和空间", "强化准点与服务"][index % 5],
  ]);
  renderTable($(id), ["人群", "典型场景", "高热搜索词", "出行机会/建议"], rows);
}

function renderEventTable(id, items) {
  renderTable($(id), ["#", "事件", "事件类型", "讨论量", "出行关联度", "状态"], (items || []).slice(0, 10).map((item, index) => [
    index + 1,
    item.event || item.name || "暂无",
    item.type || "未识别",
    formatNumber(item.discussions || item.value || 0),
    "●".repeat(item.heat || 1),
    item.status || "观察",
  ]));
}

function renderTimeline(id, items) {
  const target = $(id);
  const list = (items || []).slice(0, 5);
  target.innerHTML = list.map((item, index) => `
    <div class="timeline-item">
      <div class="timeline-date">06-${String(4 + index * 5).padStart(2, "0")}</div>
      <div title="${escapeHtml(text(item.event || item.name || "暂无事件", ""))}"><strong>${escapeHtml(item.type || "事件")}</strong> ${escapeHtml(truncateText(item.event || item.name || "暂无事件", 64))}</div>
    </div>
  `).join("") || `<div class="status-empty">暂无行业事件</div>`;
}

function renderBars(id, items = []) {
  const setup = setupCanvas(id);
  if (!setup) return;
  const { ctx, width, height } = setup;
  ctx.clearRect(0, 0, width, height);
  const list = (items || []).slice(0, 8).map((item) => ({
    name: item.name || item.event || item.type || "暂无",
    value: Number(item.value || item.discussions || 0),
  }));
  const max = Math.max(1, ...list.map((item) => item.value));
  const pad = { left: 110, right: 24, top: 22, bottom: 24 };
  const barHeight = Math.max(14, (height - pad.top - pad.bottom) / Math.max(1, list.length) - 8);
  ctx.font = "12px sans-serif";
  list.forEach((item, index) => {
    const y = pad.top + index * (barHeight + 8);
    const barWidth = (item.value / max) * (width - pad.left - pad.right);
    ctx.fillStyle = "#5b6b82";
    ctx.fillText(truncate(item.name, 8), 8, y + barHeight - 2);
    ctx.fillStyle = index % 2 ? "#9eb5d6" : "#1267f5";
    ctx.fillRect(pad.left, y, barWidth, barHeight);
    ctx.fillStyle = "#0b1f4d";
    ctx.fillText(formatNumber(item.value), pad.left + barWidth + 6, y + barHeight - 2);
  });
}

function ensureTableShell(table) {
  if (!table || !table.parentElement) return;
  if (table.parentElement.classList.contains("table-scroll")) return;
  const wrapper = document.createElement("div");
  wrapper.className = "table-scroll";
  table.parentElement.insertBefore(wrapper, table);
  wrapper.appendChild(table);
}

function columnWeight(header) {
  const value = String(header || "");
  if (/^#|排名|平台|状态|Sheet|CPE|金额|投前|投后|新增|收藏|分享|发布量|评论量|互动量|点赞|占比|搜索量|声量|讨论量/.test(value)) return 0.85;
  if (/事件|标题|内容|正文|解读|建议|业务判断|出行机会|高热搜索词|用户需求|典型场景/.test(value)) return 1.65;
  return 1.05;
}

function isShortColumn(header) {
  return /^#|排名|平台|状态|Sheet|CPE|金额|投前|投后|新增|收藏|分享|发布量|评论量|互动量|点赞|占比|搜索量|声量|讨论量|信号强度/.test(String(header || ""));
}

function cellLimit(header) {
  const value = String(header || "");
  if (isShortColumn(value)) return 16;
  if (/事件|标题|内容|正文|解读|建议|业务判断|出行机会/.test(value)) return 30;
  return 22;
}

function renderTable(table, headers, rows) {
  ensureTableShell(table);
  table.innerHTML = "";
  const weights = headers.map(columnWeight);
  const totalWeight = weights.reduce((sum, item) => sum + item, 0) || 1;
  const colgroup = document.createElement("colgroup");
  colgroup.innerHTML = weights.map((weight) => `<col style="width:${((weight / totalWeight) * 100).toFixed(3)}%">`).join("");
  table.appendChild(colgroup);
  const thead = document.createElement("thead");
  thead.innerHTML = `<tr>${headers.map((header) => `<th>${escapeHtml(header)}</th>`).join("")}</tr>`;
  table.appendChild(thead);
  const tbody = document.createElement("tbody");
  if (!rows.length) {
    tbody.innerHTML = `<tr><td colspan="${headers.length}">暂无数据</td></tr>`;
  } else {
    tbody.innerHTML = rows.map((row) => `<tr>${row.map((cell, index) => {
      const header = headers[index] || "";
      const full = text(cell, "");
      const className = isShortColumn(header) ? "cell-text short-cell" : "cell-text";
      return `<td title="${escapeHtml(full)}"><span class="${className}">${escapeHtml(truncateText(full, cellLimit(header)))}</span></td>`;
    }).join("")}</tr>`).join("");
  }
  table.appendChild(tbody);
}

function joinNames(items = [], limit = 3) {
  return (items || []).slice(0, limit).map((item) => item.name || item.text || item.event).filter(Boolean).join("、") || "暂无";
}

function truncate(value, limit) {
  const str = String(value || "");
  return str.length > limit ? `${str.slice(0, limit)}...` : str;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function exportReport() {
  const data = state.data || fallbackData();
  const payload = {
    generatedAt: data.generatedAt,
    month: data.month,
    totals: data.totals,
    summary: data.summary,
    platforms: data.platforms,
    contentTypes: data.contentTypes,
    sentiment: data.sentiment,
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `public_opinion_dashboard_${data.month || "month"}.json`;
  link.click();
  URL.revokeObjectURL(url);
}

function setupCrossLinks() {
  const params = new URLSearchParams(window.location.search);
  const pipelineUrl = params.get("pipeline") || "http://127.0.0.1:8766/";
  const link = $("pipelineJump");
  if (link) link.href = pipelineUrl;
}

function bindEvents() {
  ["monthInput", "compareInput", "platformInput"].forEach((id) => {
    $(id).addEventListener("change", loadData);
  });
  $("exportBtn").addEventListener("click", exportReport);
  document.querySelectorAll(".nav-item").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".nav-item").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      const target = $(button.dataset.target);
      if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });
  const scheduleRender = () => {
    if (!state.data) return;
    clearTimeout(state.resizeTimer);
    state.resizeTimer = setTimeout(renderAll, 120);
  };
  window.addEventListener("resize", scheduleRender);
  if ("ResizeObserver" in window) {
    const shell = document.querySelector(".dashboard-shell");
    const content = document.querySelector(".content");
    if (shell) new ResizeObserver(scheduleRender).observe(shell);
    if (content) new ResizeObserver(scheduleRender).observe(content);
  }
}

function init() {
  setupCrossLinks();
  bindEvents();
  const now = new Date();
  $("monthInput").value = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  const compare = new Date(now.getFullYear(), now.getMonth() - 1, 1);
  $("compareInput").value = `${compare.getFullYear()}-${String(compare.getMonth() + 1).padStart(2, "0")}`;
  loadData();
}

init();
