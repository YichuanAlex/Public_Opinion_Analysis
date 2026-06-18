"use strict";

const STORAGE_KEY = "rednote-heat-judge:v1";

const state = {
  parsed: null,
  model: null,
  lastPrediction: null,
  coverAnalysis: null,
  coverObjectUrl: null,
  llmConfigured: false,
  llmModel: "",
};

const els = {
  fileDrop: document.querySelector("#fileDrop"),
  fileInput: document.querySelector("#fileInput"),
  historyInput: document.querySelector("#historyInput"),
  trainButton: document.querySelector("#trainButton"),
  clearButton: document.querySelector("#clearButton"),
  dataStatus: document.querySelector("#dataStatus"),
  cpeMode: document.querySelector("#cpeMode"),
  customCpeRow: document.querySelector("#customCpeRow"),
  customCpe: document.querySelector("#customCpe"),
  minInteractions: document.querySelector("#minInteractions"),
  strictness: document.querySelector("#strictness"),
  sampleCount: document.querySelector("#sampleCount"),
  successCount: document.querySelector("#successCount"),
  autoCpe: document.querySelector("#autoCpe"),
  medianSpend: document.querySelector("#medianSpend"),
  exportModelButton: document.querySelector("#exportModelButton"),
  trainedPill: document.querySelector("#trainedPill"),
  predictForm: document.querySelector("#predictForm"),
  newTitle: document.querySelector("#newTitle"),
  newBody: document.querySelector("#newBody"),
  coverInput: document.querySelector("#coverInput"),
  coverPreview: document.querySelector("#coverPreview"),
  coverStatus: document.querySelector("#coverStatus"),
  coverMetrics: document.querySelector("#coverMetrics"),
  newPreInteractions: document.querySelector("#newPreInteractions"),
  newLikes: document.querySelector("#newLikes"),
  newCollects: document.querySelector("#newCollects"),
  newComments: document.querySelector("#newComments"),
  newShares: document.querySelector("#newShares"),
  newNoteId: document.querySelector("#newNoteId"),
  demoButton: document.querySelector("#demoButton"),
  postUrl: document.querySelector("#postUrl"),
  fetchPostButton: document.querySelector("#fetchPostButton"),
  fetchPostHint: document.querySelector("#fetchPostHint"),
  cookieToggle: document.querySelector("#cookieToggle"),
  cookieBadge: document.querySelector("#cookieBadge"),
  cookieChevron: document.querySelector("#cookieChevron"),
  cookieBody: document.querySelector("#cookieBody"),
  cookieInput: document.querySelector("#cookieInput"),
  saveCookieButton: document.querySelector("#saveCookieButton"),
  clearCookieButton: document.querySelector("#clearCookieButton"),
  cookieHint: document.querySelector("#cookieHint"),
  appendToggle: document.querySelector("#appendToggle"),
  appendChevron: document.querySelector("#appendChevron"),
  appendBody: document.querySelector("#appendBody"),
  appendFileInput: document.querySelector("#appendFileInput"),
  appendInput: document.querySelector("#appendInput"),
  appendButton: document.querySelector("#appendButton"),
  appendResult: document.querySelector("#appendResult"),
  llmToggle: document.querySelector("#llmToggle"),
  llmBadge: document.querySelector("#llmBadge"),
  llmChevron: document.querySelector("#llmChevron"),
  llmBody: document.querySelector("#llmBody"),
  llmApiKeyInput: document.querySelector("#llmApiKeyInput"),
  llmProviderSelect: document.querySelector("#llmProviderSelect"),
  llmModelInput: document.querySelector("#llmModelInput"),
  llmBaseUrlInput: document.querySelector("#llmBaseUrlInput"),
  llmSendImageToggle: document.querySelector("#llmSendImageToggle"),
  saveLlmButton: document.querySelector("#saveLlmButton"),
  clearLlmButton: document.querySelector("#clearLlmButton"),
  llmHint: document.querySelector("#llmHint"),
  llmPredictButton: document.querySelector("#llmPredictButton"),
  decisionCard: document.querySelector("#decisionCard"),
  tabs: document.querySelectorAll(".tab"),
  panels: {
    signals: document.querySelector("#signalsPanel"),
    neighbors: document.querySelector("#neighborsPanel"),
    data: document.querySelector("#dataPanel"),
  },
  signalList: document.querySelector("#signalList"),
  signalTemplate: document.querySelector("#signalTemplate"),
  neighborsBody: document.querySelector("#neighborsBody"),
  recognizedColumns: document.querySelector("#recognizedColumns"),
  missingCpe: document.querySelector("#missingCpe"),
  missingTitle: document.querySelector("#missingTitle"),
  usableRate: document.querySelector("#usableRate"),
  warningList: document.querySelector("#warningList"),
};

const HEADER_ALIASES = [
  ["publishDate", ["发布日期", "发布时间", "笔记日期", "发布日"]],
  ["endDate", ["投放截止", "截止日期", "结束日期", "投放结束"]],
  ["status", ["状态", "投放状态"]],
  ["channel", ["加热渠道", "渠道"]],
  ["category1", ["一级分类", "分类1", "类型"]],
  ["category2", ["二级分类", "分类2", "子类型"]],
  ["tags", ["标签", "乘车体验详细分类"]],
  ["link", ["链接", "笔记链接", "url"]],
  ["noteId", ["笔记id", "笔记ID", "noteid", "id"]],
  ["adRecords", ["投放记录", "投放明细", "投放过程"]],
  ["title", ["标题", "笔记标题", "题目"]],
  ["body", ["正文", "内容", "笔记正文", "笔记内容", "文案", "帖子正文", "帖子内容"]],
  ["coverScore", ["封面评分", "封面得分", "封面质量", "封面点击评分", "封面吸引力"]],
  ["coverBrightness", ["封面亮度", "图片亮度"]],
  ["coverContrast", ["封面对比度", "图片对比度"]],
  ["coverSaturation", ["封面饱和度", "图片饱和度", "封面色彩"]],
  ["coverSharpness", ["封面清晰度", "图片清晰度"]],
  ["coverInfoDensity", ["封面信息密度", "图片信息密度", "封面文字密度"]],
  ["preInteractions", ["投前互动量", "投前互动", "现有互动量", "当前互动量", "自然互动量", "加热前互动", "加热前互动量"]],
  ["postLikes", ["投放后点赞", "投后点赞", "加热后点赞"]],
  ["postCollects", ["投放后收藏", "投后收藏", "加热后收藏"]],
  ["postComments", ["投放后评论", "投后评论", "加热后评论"]],
  ["postShares", ["投放后分享", "投后分享", "投放后转发", "加热后分享"]],
  ["likes", ["点赞", "点赞量", "赞", "赞数", "当前点赞", "投前点赞"]],
  ["collects", ["收藏", "收藏量", "藏", "藏数", "当前收藏", "投前收藏"]],
  ["comments", ["评论", "评论量", "评", "评数", "当前评论", "投前评论"]],
  ["shares", ["分享", "分享量", "转发", "转发量", "当前分享", "投前分享"]],
  ["postInteractions", ["投后互动量", "投后互动", "加热后互动", "加热后互动量"]],
  ["totalInteractions", ["总互动量", "总互动", "互动总量", "外层互动"]],
  ["spend", ["总投放金额", "投放金额", "消耗金额", "总消耗", "花费", "金额"]],
  ["cpe", ["综合cpe", "cpe", "互动成本", "单次互动成本"]],
];

const KNOWN_KEYWORDS = [
  "打车",
  "司机",
  "姐姐",
  "专车",
  "快车",
  "顺风车",
  "女性",
  "友好",
  "治愈",
  "安全",
  "通勤",
  "上班",
  "下班",
  "机场",
  "高铁",
  "夜晚",
  "女生",
  "服务",
  "体验",
  "真实",
  "避雷",
  "攻略",
  "省钱",
  "优惠",
  "春天",
  "太卷",
  "离谱",
  "暖心",
  "舒服",
  "焦虑",
  "惊喜",
  "故事",
  "日常",
  "测评",
  "对比",
  "推荐",
];

const STOP_CHARS = new Set("的一是在不了和有就人都说而及与着或一个也很被到吧吗呢啊呀哦得比还更最太");

document.addEventListener("DOMContentLoaded", () => {
  bindEvents();
  restoreSavedState();
  toggleCustomCpe();
});

function bindEvents() {
  els.fileInput.addEventListener("change", async (event) => {
    const [file] = event.target.files;
    if (file) {
      const text = await file.text();
      els.historyInput.value = text;
      trainFromInput();
    }
  });

  ["dragenter", "dragover"].forEach((eventName) => {
    els.fileDrop.addEventListener(eventName, (event) => {
      event.preventDefault();
      els.fileDrop.classList.add("is-dragging");
    });
  });

  ["dragleave", "drop"].forEach((eventName) => {
    els.fileDrop.addEventListener(eventName, (event) => {
      event.preventDefault();
      els.fileDrop.classList.remove("is-dragging");
    });
  });

  els.fileDrop.addEventListener("drop", async (event) => {
    const [file] = event.dataTransfer.files;
    if (file) {
      els.fileInput.files = event.dataTransfer.files;
      els.historyInput.value = await file.text();
      trainFromInput();
    }
  });

  els.trainButton.addEventListener("click", trainFromInput);
  els.clearButton.addEventListener("click", clearAll);
  els.exportModelButton.addEventListener("click", exportModelSummary);
  els.demoButton.addEventListener("click", fillDemoPost);
  if (els.llmPredictButton) {
    els.llmPredictButton.addEventListener("click", runLlmHybridPrediction);
  }
  els.predictForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    await runPrediction();
  });
  els.coverInput.addEventListener("change", async (event) => {
    const [file] = event.target.files;
    if (file) {
      await handleCoverFile(file);
    }
  });

  if (els.fetchPostButton) {
    els.fetchPostButton.addEventListener("click", fetchPostFromUrl);
  }
  if (els.postUrl) {
    els.postUrl.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        fetchPostFromUrl();
      }
    });
  }

  if (els.appendToggle) {
    els.appendToggle.addEventListener("click", () => {
      const open = !els.appendBody.hidden;
      els.appendBody.hidden = open;
      els.appendChevron.textContent = open ? "▸" : "▾";
    });
  }
  if (els.appendButton) {
    els.appendButton.addEventListener("click", appendNewData);
  }
  if (els.appendFileInput) {
    els.appendFileInput.addEventListener("change", async (event) => {
      const [file] = event.target.files;
      if (!file) return;
      try {
        els.appendInput.value = await file.text();
        setAppendResult(`已读取文件「${file.name}」，点「追加并重训」。`, "");
      } catch (e) {
        setAppendResult("读取文件失败：" + e.message, "error");
      }
    });
  }

  if (els.cookieToggle) {
    els.cookieToggle.addEventListener("click", toggleCookiePanel);
  }
  if (els.saveCookieButton) {
    els.saveCookieButton.addEventListener("click", saveCookie);
  }
  if (els.clearCookieButton) {
    els.clearCookieButton.addEventListener("click", clearCookie);
  }
  if (els.llmToggle) {
    els.llmToggle.addEventListener("click", toggleLlmPanel);
  }
  if (els.saveLlmButton) {
    els.saveLlmButton.addEventListener("click", saveLlmConfig);
  }
  if (els.clearLlmButton) {
    els.clearLlmButton.addEventListener("click", clearLlmConfig);
  }
  if (els.llmProviderSelect) {
    els.llmProviderSelect.addEventListener("change", updateLlmProviderDefaults);
  }
  checkCookieStatus();
  checkLlmStatus();

  [els.cpeMode, els.customCpe, els.minInteractions, els.strictness].forEach((control) => {
    control.addEventListener("change", () => {
      toggleCustomCpe();
      if (els.historyInput.value.trim()) {
        trainFromInput({ silent: true });
      }
    });
  });

  els.tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      els.tabs.forEach((item) => item.classList.remove("active"));
      tab.classList.add("active");
      Object.values(els.panels).forEach((panel) => panel.classList.remove("active"));
      els.panels[tab.dataset.tab].classList.add("active");
    });
  });
}

function restoreSavedState() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
    if (!saved) {
      renderEmptyQuality();
      return;
    }

    if (saved.historyText) {
      els.historyInput.value = saved.historyText;
    }
    if (saved.settings) {
      els.cpeMode.value = saved.settings.cpeMode || "auto";
      els.customCpe.value = saved.settings.customCpe || "2.0";
      els.minInteractions.value = saved.settings.minInteractions || "0";
      els.strictness.value = saved.settings.strictness || "balanced";
    }
    if (saved.historyText) {
      trainFromInput({ silent: true });
    }
  } catch (error) {
    renderEmptyQuality();
  }
}

function persistState() {
  const payload = {
    historyText: els.historyInput.value,
    settings: getSettings(),
    savedAt: new Date().toISOString(),
  };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
}

function getSettings() {
  return {
    cpeMode: els.cpeMode.value,
    customCpe: Math.max(0.1, parseFloat(els.customCpe.value) || 2),
    minInteractions: Math.max(0, parseFloat(els.minInteractions.value) || 0),
    strictness: els.strictness.value,
  };
}

function toggleCustomCpe() {
  els.customCpeRow.classList.toggle("is-hidden", els.cpeMode.value !== "custom");
}

function trainFromInput(options = {}) {
  const text = els.historyInput.value.trim();
  if (!text) {
    setStatus("请先粘贴或上传历史数据", "error");
    return;
  }

  try {
    const parsed = parseHistoryTable(text);
    const model = trainModel(parsed, getSettings());
    state.parsed = parsed;
    state.model = model;
    persistState();
    renderModel(model, parsed);
    setStatus(`已学习 ${model.records.length} 条`, "ready");
    if (!options.silent && state.lastPrediction) {
      runPrediction();
    }
  } catch (error) {
    state.parsed = null;
    state.model = null;
    renderModel(null, null);
    setStatus(error.message, "error");
  }
}

function parseHistoryTable(text) {
  const candidates = ["\t", ",", ";"].map((delimiter) => {
    const rows = parseDelimited(text, delimiter);
    const firstRow = rows.find((row) => row.some((cell) => cleanCell(cell)));
    return { delimiter, rows, columnCount: firstRow ? firstRow.length : 0 };
  });

  candidates.sort((a, b) => b.columnCount - a.columnCount);
  const best = candidates[0];
  if (!best || best.columnCount < 4) {
    throw new Error("没有识别到表格列。请复制包含表头的整张表，或导出 CSV/TSV。");
  }

  const rows = best.rows.filter((row) => row.some((cell) => cleanCell(cell)));
  if (rows.length < 2) {
    throw new Error("历史数据至少需要表头和 1 行记录。");
  }

  const headerIndex = rows.findIndex((row) => row.some((cell) => mapHeader(cell)));
  if (headerIndex < 0) {
    throw new Error("没有识别到表头。需要包含标题或正文、现有互动量、总投放金额或综合 CPE 等列。");
  }

  const headers = rows[headerIndex].map(cleanCell);
  const columnMap = buildColumnMap(headers);
  const records = rows.slice(headerIndex + 1).map((row, index) => {
    const raw = {};
    headers.forEach((header, cellIndex) => {
      raw[header || `第${cellIndex + 1}列`] = cleanCell(row[cellIndex] || "");
    });
    const normalized = {};
    Object.entries(columnMap).forEach(([field, cellIndex]) => {
      normalized[field] = cleanCell(row[cellIndex] || "");
    });
    return buildRecord(normalized, raw, index + 1);
  });

  const recognized = Object.keys(columnMap);
  return {
    delimiter: best.delimiter,
    headers,
    columnMap,
    recognized,
    records,
    rowCount: records.length,
  };
}

function parseDelimited(text, delimiter) {
  const normalized = String(text || "").replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  const rows = [];
  let row = [];
  let field = "";
  let inQuotes = false;

  for (let index = 0; index < normalized.length; index += 1) {
    const char = normalized[index];
    const next = normalized[index + 1];

    if (char === '"') {
      if (inQuotes && next === '"') {
        field += '"';
        index += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }

    if (!inQuotes && char === delimiter) {
      row.push(field);
      field = "";
      continue;
    }

    if (!inQuotes && char === "\n") {
      row.push(field);
      rows.push(row);
      row = [];
      field = "";
      continue;
    }

    field += char;
  }

  row.push(field);
  rows.push(row);
  return rows;
}

function buildColumnMap(headers) {
  const map = {};
  headers.forEach((header, index) => {
    const field = mapHeader(header);
    if (field && map[field] === undefined) {
      map[field] = index;
    }
  });
  return map;
}

function mapHeader(header) {
  const normalized = normalizeHeader(header);
  if (!normalized) {
    return "";
  }

  for (const [field, aliases] of HEADER_ALIASES) {
    if (aliases.some((alias) => normalized.includes(normalizeHeader(alias)))) {
      return field;
    }
  }
  return "";
}

function normalizeHeader(header) {
  return String(header || "")
    .replace(/\s+/g, "")
    .replace(/[："“”"'`*（）()\/\\_\-]/g, "")
    .toLowerCase();
}

function cleanCell(value) {
  return String(value ?? "")
    .replace(/^\uFEFF/, "")
    .replace(/\u00a0/g, " ")
    .trim();
}

function buildRecord(values, raw, index) {
  const title = cleanCell(values.title);
  const body = cleanCell(values.body);
  const interactionParts = {
    likes: parseNumber(values.likes),
    collects: parseNumber(values.collects),
    comments: parseNumber(values.comments),
    shares: parseNumber(values.shares),
  };
  const preInteractions = parseNumber(values.preInteractions) ?? sumInteractionParts(interactionParts);
  const postInteractions = parseNumber(values.postInteractions);
  const totalInteractions = parseNumber(values.totalInteractions) ?? postInteractions;
  const spendFromRecords = parseAdSpend(values.adRecords);
  const spend = parseNumber(values.spend) ?? spendFromRecords;
  const cpe = parseNumber(values.cpe) ?? calculateCpe(spend, totalInteractions);
  const publishDate = parseDate(values.publishDate);
  const cover = buildCoverFromValues(values);
  const titleTokens = tokenizeText(title);
  const bodyTokens = tokenizeText(body);
  const tokens = uniqueTokens([...titleTokens, ...bodyTokens]);
  const shape = getContentShape(title, body);

  return {
    index,
    raw,
    title,
    body,
    publishDate,
    publishDateText: values.publishDate || "",
    status: cleanCell(values.status),
    channel: cleanCell(values.channel),
    category1: cleanCell(values.category1),
    category2: cleanCell(values.category2),
    tags: cleanCell(values.tags),
    link: cleanCell(values.link),
    noteId: cleanCell(values.noteId),
    adRecords: cleanCell(values.adRecords),
    preInteractions,
    interactionParts,
    postInteractions,
    totalInteractions,
    spend,
    cpe,
    cover,
    titleTokens,
    bodyTokens,
    tokens,
    shape,
    label: false,
    outcomeScore: 0,
  };
}

function parseNumber(value) {
  const text = cleanCell(value);
  if (!text || /^[-—/\\]+$/.test(text)) {
    return null;
  }
  const normalized = text
    .replace(/[,，]/g, "")
    .replace(/[￥¥元]/g, "")
    .replace(/\s+/g, "");
  const match = normalized.match(/-?\d+(?:\.\d+)?/);
  if (!match) {
    return null;
  }
  const number = Number(match[0]);
  return Number.isFinite(number) ? number : null;
}

function parseAdSpend(value) {
  const text = cleanCell(value).replace(/[,，]/g, "");
  if (!text) {
    return null;
  }
  let total = 0;
  let found = false;
  const regex = /(\d+(?:\.\d+)?)\s*元/g;
  let match = regex.exec(text);
  while (match) {
    total += Number(match[1]);
    found = true;
    match = regex.exec(text);
  }
  return found ? total : null;
}

function calculateCpe(spend, interactions) {
  if (!isPositive(spend) || !isPositive(interactions)) {
    return null;
  }
  return spend / interactions;
}

function buildCoverFromValues(values) {
  const rawScore = parseNumber(values.coverScore);
  const metrics = {
    brightness: parseRatioMetric(values.coverBrightness),
    contrast: parseRatioMetric(values.coverContrast),
    saturation: parseRatioMetric(values.coverSaturation),
    sharpness: parseRatioMetric(values.coverSharpness),
    infoDensity: parseRatioMetric(values.coverInfoDensity),
  };
  const hasMetrics = Object.values(metrics).some((value) => Number.isFinite(value));
  if (!Number.isFinite(rawScore) && !hasMetrics) {
    return null;
  }

  const score = Number.isFinite(rawScore)
    ? normalizeCoverScore(rawScore)
    : estimateCoverScoreFromMetrics(metrics);
  return {
    score,
    ...metrics,
    source: "table",
  };
}

function parseRatioMetric(value) {
  const number = parseNumber(value);
  if (!Number.isFinite(number)) {
    return null;
  }
  return number > 1 ? clamp(number / 100, 0, 1) : clamp(number, 0, 1);
}

function normalizeCoverScore(value) {
  return value <= 1 ? clamp(value * 100, 0, 100) : clamp(value, 0, 100);
}

function estimateCoverScoreFromMetrics(metrics) {
  const brightness = Number.isFinite(metrics.brightness) ? metrics.brightness : 0.58;
  const contrast = Number.isFinite(metrics.contrast) ? metrics.contrast : 0.22;
  const saturation = Number.isFinite(metrics.saturation) ? metrics.saturation : 0.38;
  const sharpness = Number.isFinite(metrics.sharpness) ? metrics.sharpness : 0.42;
  const infoDensity = Number.isFinite(metrics.infoDensity) ? metrics.infoDensity : 0.42;
  const score =
    100 *
    (0.23 * bellScore(brightness, 0.58, 0.36) +
      0.2 * clamp(contrast / 0.26, 0, 1) +
      0.2 * clamp(saturation / 0.48, 0, 1) +
      0.2 * sharpness +
      0.17 * infoDensity);
  return clamp(score, 0, 100);
}

function parseDate(value) {
  const text = cleanCell(value);
  if (!text) {
    return null;
  }
  const ymd = text.match(/(20\d{2})[\/.-](\d{1,2})[\/.-](\d{1,2})/);
  if (ymd) {
    return new Date(Number(ymd[1]), Number(ymd[2]) - 1, Number(ymd[3]));
  }
  const parsed = new Date(text);
  if (Number.isNaN(parsed.getTime())) {
    return null;
  }
  return parsed;
}

function trainModel(parsed, settings) {
  const candidates = parsed.records.filter((record) => (record.title || record.body) && isPositive(record.cpe));
  if (candidates.length < 4) {
    throw new Error("可训练样本少于 4 条。至少需要标题或正文，以及综合 CPE。");
  }

  const cpeValues = sortedNumbers(candidates.map((record) => record.cpe));
  const interactionValues = sortedNumbers(candidates.map((record) => record.totalInteractions));
  const spendValues = sortedNumbers(candidates.map((record) => record.spend));
  const autoQuantile = settings.strictness === "strict" ? 0.35 : settings.strictness === "growth" ? 0.55 : 0.45;
  const autoCpe = quantile(cpeValues, autoQuantile);
  const cpeThreshold = settings.cpeMode === "custom" ? settings.customCpe : autoCpe;

  candidates.forEach((record) => {
    const cpeScore = 1 - percentileRank(cpeValues, record.cpe);
    const volumeScore = isPositive(record.totalInteractions)
      ? percentileRank(interactionValues, record.totalInteractions)
      : 0.5;
    const thresholdBonus = record.cpe <= cpeThreshold ? 1 : 0;
    record.outcomeScore = clamp(0.68 * cpeScore + 0.22 * volumeScore + 0.1 * thresholdBonus, 0, 1);
    record.label = record.cpe <= cpeThreshold && (record.totalInteractions || 0) >= settings.minInteractions;
  });

  const successCount = candidates.filter((record) => record.label).length;
  const baseline = clamp(successCount / candidates.length, 0.04, 0.96);
  const featureStats = buildFeatureStats(candidates, baseline);

  return {
    records: candidates,
    allRecords: parsed.records,
    baseline,
    featureStats,
    cpeValues,
    interactionValues,
    spendValues,
    autoCpe,
    cpeThreshold,
    medianSpend: quantile(spendValues, 0.5),
    successCount,
    recognized: parsed.recognized,
    quality: getDataQuality(parsed, candidates),
    settings,
    trainedAt: new Date().toISOString(),
  };
}

function buildFeatureStats(records, baseline) {
  const stats = new Map();
  records.forEach((record) => {
    getRecordFeatures(record).forEach((feature) => {
      if (!stats.has(feature.key)) {
        stats.set(feature.key, {
          key: feature.key,
          label: feature.label,
          group: feature.group,
          count: 0,
          success: 0,
          cpeSum: 0,
          outcomeSum: 0,
        });
      }
      const item = stats.get(feature.key);
      item.count += 1;
      item.success += record.label ? 1 : 0;
      item.cpeSum += record.cpe || 0;
      item.outcomeSum += record.outcomeScore || 0;
    });
  });

  stats.forEach((item) => {
    item.rate = smoothedRate(item.success, item.count, baseline, 3);
    item.avgCpe = item.count ? item.cpeSum / item.count : null;
    item.avgOutcome = item.count ? item.outcomeSum / item.count : 0;
    item.effect = item.rate - baseline;
  });
  return stats;
}

function getRecordFeatures(record) {
  const features = [];
  const shape = record.shape || getContentShape(record.title, record.body);
  const interactionParts = record.interactionParts || {};
  
  if (record.category1) {
    features.push({ key: `cat1:${record.category1}`, label: `一级分类「${record.category1}」`, group: "分类" });
  }
  if (record.category2) {
    features.push({ key: `cat2:${record.category2}`, label: `二级分类「${record.category2}」`, group: "分类" });
  }
  if (record.tags) {
    const tagList = record.tags.split(/[,\/，、]/);
    tagList.forEach((tag) => {
      const t = tag.trim();
      if (t) features.push({ key: `tag:${t}`, label: `标签「${t}」`, group: "分类" });
    });
  }
  if (record.channel) {
    features.push({ key: `channel:${record.channel}`, label: `渠道「${record.channel}」`, group: "渠道" });
  }

  features.push({ key: `current:${interactionBin(record.preInteractions)}`, label: `现有互动 ${interactionBin(record.preInteractions)}`, group: "现有互动" });
  features.push({ key: `titleLength:${shape.titleLengthBin}`, label: `标题${shape.titleLengthBin}`, group: "标题形态" });
  if (shape.bodyLengthBin !== "缺失") {
    features.push({ key: `bodyLength:${shape.bodyLengthBin}`, label: `正文${shape.bodyLengthBin}`, group: "正文形态" });
  }

  if (shape.hasEmoji) {
    features.push({ key: "shape:emoji", label: "内容含表情", group: "内容形态" });
  }
  if (shape.hasQuestion) {
    features.push({ key: "shape:question", label: "内容含疑问", group: "内容形态" });
  }
  if (shape.hasExclamation) {
    features.push({ key: "shape:exclamation", label: "内容含感叹", group: "内容形态" });
  }
  if (shape.hasNumber) {
    features.push({ key: "shape:number", label: "内容含数字", group: "内容形态" });
  }
  if (shape.hasMoneyWord) {
    features.push({ key: "shape:money", label: "内容含价格/省钱", group: "内容形态" });
  }
  if (shape.hasStoryWord) {
    features.push({ key: "shape:story", label: "正文有故事场景", group: "正文形态" });
  }
  if (shape.hasPainWord) {
    features.push({ key: "shape:pain", label: "正文有痛点表达", group: "正文形态" });
  }
  if (shape.hasActionWord) {
    features.push({ key: "shape:action", label: "正文有行动引导", group: "正文形态" });
  }
  if (record.cover) {
    getCoverFeatures(record.cover).forEach((feature) => features.push(feature));
  }

  getInteractionRatioFeatures(interactionParts).forEach((feature) => features.push(feature));

  (record.titleTokens || tokenizeText(record.title)).forEach((token) => {
    features.push({ key: `titleToken:${token}`, label: `标题词「${token}」`, group: "标题词" });
  });
  (record.bodyTokens || tokenizeText(record.body)).forEach((token) => {
    features.push({ key: `bodyToken:${token}`, label: `正文词「${token}」`, group: "正文词" });
  });
  (record.tokens || uniqueTokens([...(record.titleTokens || []), ...(record.bodyTokens || [])])).slice(0, 18).forEach((token) => {
    features.push({ key: `contentToken:${token}`, label: `内容词「${token}」`, group: "整体内容" });
  });
  return features;
}

function getCoverFeatures(cover) {
  if (!cover) {
    return [];
  }
  const features = [];
  if (Number.isFinite(cover.score)) {
    features.push({ key: `coverScore:${coverScoreBin(cover.score)}`, label: `封面质量${coverScoreBin(cover.score)}`, group: "封面" });
  }
  if (Number.isFinite(cover.brightness)) {
    features.push({ key: `coverBrightness:${metricBin(cover.brightness, 0.42, 0.7)}`, label: `封面亮度${metricBin(cover.brightness, 0.42, 0.7)}`, group: "封面" });
  }
  if (Number.isFinite(cover.contrast)) {
    features.push({ key: `coverContrast:${metricBin(cover.contrast, 0.16, 0.32)}`, label: `封面对比${metricBin(cover.contrast, 0.16, 0.32)}`, group: "封面" });
  }
  if (Number.isFinite(cover.saturation)) {
    features.push({ key: `coverSaturation:${metricBin(cover.saturation, 0.28, 0.58)}`, label: `封面色彩${metricBin(cover.saturation, 0.28, 0.58)}`, group: "封面" });
  }
  if (Number.isFinite(cover.sharpness)) {
    features.push({ key: `coverSharpness:${metricBin(cover.sharpness, 0.3, 0.7)}`, label: `封面清晰${metricBin(cover.sharpness, 0.3, 0.7)}`, group: "封面" });
  }
  if (Number.isFinite(cover.infoDensity)) {
    features.push({ key: `coverInfo:${metricBin(cover.infoDensity, 0.28, 0.66)}`, label: `封面信息密度${metricBin(cover.infoDensity, 0.28, 0.66)}`, group: "封面" });
  }
  if (Number.isFinite(cover.skinRatio) && cover.skinRatio > 0.04) {
    features.push({ key: "cover:people", label: "封面疑似有人物", group: "封面" });
  }
  return features;
}

function getInteractionRatioFeatures(parts) {
  const values = ["likes", "collects", "comments", "shares"].map((field) => parts[field]);
  const knownValues = values.filter((value) => Number.isFinite(value));
  if (!knownValues.length) {
    return [];
  }
  const total = knownValues.reduce((sum, value) => sum + Math.max(0, value), 0);
  if (!total) {
    return [{ key: "mix:none", label: "互动结构全为 0", group: "互动结构" }];
  }

  const ratios = {
    likes: safeRatio(parts.likes, total),
    collects: safeRatio(parts.collects, total),
    comments: safeRatio(parts.comments, total),
    shares: safeRatio(parts.shares, total),
  };

  const features = [];
  if (Number.isFinite(ratios.collects)) {
    features.push({ key: `collectRatio:${ratioBin(ratios.collects)}`, label: `收藏占比${ratioBin(ratios.collects)}`, group: "互动结构" });
  }
  if (Number.isFinite(ratios.comments)) {
    features.push({ key: `commentRatio:${ratioBin(ratios.comments)}`, label: `评论占比${ratioBin(ratios.comments)}`, group: "互动结构" });
  }
  if (Number.isFinite(ratios.shares)) {
    features.push({ key: `shareRatio:${ratioBin(ratios.shares)}`, label: `分享占比${ratioBin(ratios.shares)}`, group: "互动结构" });
  }
  return features;
}

function tokenizeText(textValue) {
  const text = cleanCell(textValue)
    .replace(/https?:\/\/\S+/g, " ")
    .replace(/[【】《》「」“”"'`]/g, " ")
    .toLowerCase();
  const tokens = new Set();

  KNOWN_KEYWORDS.forEach((keyword) => {
    if (text.includes(keyword.toLowerCase())) {
      tokens.add(keyword);
    }
  });

  const cjkSegments = text.match(/[\u4e00-\u9fff]{2,}/g) || [];
  cjkSegments.forEach((segment) => {
    const chars = [...segment].filter((char) => !STOP_CHARS.has(char));
    const compact = chars.join("");
    if (compact.length >= 2 && compact.length <= 8) {
      tokens.add(compact);
    }
    [2, 3].forEach((size) => {
      for (let index = 0; index <= compact.length - size; index += 1) {
        const token = compact.slice(index, index + size);
        if (!/^[的一是在不了和有就人都]+$/.test(token)) {
          tokens.add(token);
        }
      }
    });
  });

  const latinTokens = text.match(/[a-z0-9]{2,}/g) || [];
  latinTokens.forEach((token) => tokens.add(token));
  return [...tokens].slice(0, 36);
}

function uniqueTokens(tokens) {
  return [...new Set(tokens.filter(Boolean))].slice(0, 64);
}

function getContentShape(title, body) {
  const titleText = cleanCell(title);
  const bodyText = cleanCell(body);
  const text = `${titleText}\n${bodyText}`.trim();
  const titleLength = [...titleText].length;
  const bodyLength = [...bodyText].length;
  return {
    titleLength,
    bodyLength,
    titleLengthBin: titleLength <= 6 ? "很短" : titleLength <= 14 ? "短" : titleLength <= 24 ? "中等" : "长",
    bodyLengthBin: bodyLength === 0 ? "缺失" : bodyLength <= 60 ? "短" : bodyLength <= 180 ? "中等" : "长",
    hasEmoji: /[\u{1F000}-\u{1FAFF}\u2600-\u27BF]/u.test(text),
    hasQuestion: /[?？]/.test(text),
    hasExclamation: /[!！]/.test(text),
    hasNumber: /\d/.test(text),
    hasMoneyWord: /省钱|优惠|便宜|贵|价格|元|券|折/.test(text),
    hasStoryWord: /遇到|经历|今天|刚刚|一次|没想到|原来|后来|结果|发现|真的/.test(bodyText),
    hasPainWord: /担心|害怕|焦虑|不安全|麻烦|尴尬|踩雷|避雷|痛点|问题|难受/.test(bodyText),
    hasActionWord: /建议|推荐|记得|一定|可以|适合|收藏|评论|试试|安排/.test(bodyText),
  };
}

async function runPrediction(options = {}) {
  if (!state.model) {
    renderDecisionMessage("请先导入历史数据并点击“学习历史数据”。", "error");
    return null;
  }

  const title = cleanCell(els.newTitle.value);
  const body = cleanCell(els.newBody.value);
  if (!title || !body) {
    renderDecisionMessage("请输入新帖标题和正文。这个版本会把标题、正文和现有互动一起判断。", "error");
    return null;
  }
  const interactionParts = {
    likes: parseNumber(els.newLikes.value),
    collects: parseNumber(els.newCollects.value),
    comments: parseNumber(els.newComments.value),
    shares: parseNumber(els.newShares.value),
  };

  const input = {
    title,
    body,
    preInteractions: parseNumber(els.newPreInteractions.value) ?? sumInteractionParts(interactionParts) ?? 0,
    interactionParts,
    cover: state.coverAnalysis,
    noteId: cleanCell(els.newNoteId.value),
  };

  const prediction = predict(input, state.model);
  state.lastPrediction = prediction;
  if (!options.skipRender) {
    renderPrediction(prediction);
  }
  return prediction;
}

function predict(input, model) {
  const recordLike = {
    title: input.title,
    body: input.body,
    preInteractions: input.preInteractions,
    interactionParts: input.interactionParts || {},
    cover: input.cover || null,
    titleTokens: tokenizeText(input.title),
    bodyTokens: tokenizeText(input.body),
    tokens: uniqueTokens([...tokenizeText(input.title), ...tokenizeText(input.body)]),
    shape: getContentShape(input.title, input.body),
    channel: input.channel || "薯条", // 预测新笔记时默认使用薯条渠道
  };
  const features = getRecordFeatures(recordLike);
  const baselineLogit = logit(model.baseline);
  let featureLogit = baselineLogit;
  const contributions = [];

  features.forEach((feature) => {
    const stat = model.featureStats.get(feature.key);
    if (!stat) {
      return;
    }
    const typeWeight = getFeatureWeight(feature.key);
    const countWeight = Math.min(1, stat.count / 5);
    const delta = clamp(logit(stat.rate) - baselineLogit, -1.4, 1.4) * typeWeight * countWeight;
    featureLogit += delta;
    contributions.push({
      label: stat.label,
      group: stat.group,
      count: stat.count,
      rate: stat.rate,
      avgCpe: stat.avgCpe,
      effect: stat.effect,
      delta,
    });
  });

  const featureProbability = sigmoid(featureLogit);
  const neighbors = findNeighbors(recordLike, model.records);
  const topNeighbors = neighbors.slice(0, 8);
  const weighted = weightedNeighborMetrics(topNeighbors, model);

  // 优化：用 feature 模型微调 CPE 预测——featureProbability 越高，特征越支持"值得加热"，CPE 应越低
  const featureCpeAdjustment = model.cpeThreshold * (0.5 - featureProbability) * 0.20;
  const adjustedPredictedCpe = Math.max(0.05, weighted.predictedCpe + featureCpeAdjustment);

  const cpeProbability = cpeToProbability(weighted.predictedCpe, model.cpeThreshold);
  const coverAssessment = assessCover(input.cover);
  const blendedProbability = blendProbabilities(featureProbability, weighted.successRate, cpeProbability, coverAssessment);
  const confidence = estimateConfidence(model, topNeighbors, contributions, featureProbability, weighted.successRate);
  const decision = classifyDecision(blendedProbability, model.settings.strictness);
  const budget = suggestBudget(decision.key, adjustedPredictedCpe, model);

  return {
    input,
    recordLike,
    features,
    contributions: contributions.sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta)),
    neighbors: topNeighbors,
    featureProbability,
    cpeProbability,
    coverAssessment,
    probability: blendedProbability,
    confidence,
    decision,
    budget,
    predictedCpe: adjustedPredictedCpe,
    predictedInteractions: weighted.predictedInteractions,
    neighborSuccessRate: weighted.successRate,
    model,
  };
}

function findNeighbors(recordLike, records) {
  const inputTokens = new Set(recordLike.tokens);
  const inputTitleTokens = new Set(recordLike.titleTokens || []);
  const inputBodyTokens = new Set(recordLike.bodyTokens || []);
  const inputMetaTokens = new Set([
    recordLike.channel ? `channel:${recordLike.channel}` : null,
    recordLike.category1 ? `cat1:${recordLike.category1}` : null,
    recordLike.category2 ? `cat2:${recordLike.category2}` : null,
    ...(recordLike.tags ? recordLike.tags.split(/[,\/，、]/).map(t => t.trim() ? `tag:${t.trim()}` : null) : [])
  ].filter(Boolean));

  const inputTitleLengthIndex = lengthBinIndex(recordLike.shape.titleLengthBin);
  const inputBodyLengthIndex = bodyLengthBinIndex(recordLike.shape.bodyLengthBin);

  const channelDecay = {
    "薯条": 1.0,
    "合作广场": 0.85,
    "口碑通": 0.7,
  };

  return records
    .map((record) => {
      const recordMetaTokens = new Set([
        record.channel ? `channel:${record.channel}` : null,
        record.category1 ? `cat1:${record.category1}` : null,
        record.category2 ? `cat2:${record.category2}` : null,
        ...(record.tags ? record.tags.split(/[,\/，、]/).map(t => t.trim() ? `tag:${t.trim()}` : null) : [])
      ].filter(Boolean));

      const contentScore = jaccard(inputTokens, new Set(record.tokens));
      const titleScore = jaccard(inputTitleTokens, new Set(record.titleTokens || []));
      const bodyScore = jaccard(inputBodyTokens, new Set(record.bodyTokens || []));
      const metaScore = jaccard(inputMetaTokens, recordMetaTokens);
      const interactionScore = interactionSimilarity(recordLike.preInteractions, record.preInteractions);
      const titleLengthScore = 1 / (1 + Math.abs(inputTitleLengthIndex - lengthBinIndex(record.shape.titleLengthBin)));
      const bodyLengthScore = 1 / (1 + Math.abs(inputBodyLengthIndex - bodyLengthBinIndex(record.shape.bodyLengthBin)));
      const mixScore = interactionMixSimilarity(recordLike.interactionParts || {}, record.interactionParts || {});
      const coverScore = coverSimilarity(recordLike.cover, record.cover);
      
      // 优化：提升 interaction 与 meta 权重（对 CPE 预测更关键），降低 content/cover 权重
      const score =
        0.14 * contentScore +
        0.12 * titleScore +
        0.12 * bodyScore +
        0.22 * metaScore +
        0.26 * interactionScore +
        0.06 * mixScore +
        0.05 * coverScore +
        0.015 * titleLengthScore +
        0.015 * bodyLengthScore;
      
      let finalScore = score;
      if (record.channel) {
        finalScore *= (channelDecay[record.channel] || 0.4);
      } else {
        finalScore *= 0.4;
      }

      return { record, score: finalScore };
    })
    .sort((a, b) => b.score - a.score);
}

function weightedNeighborMetrics(neighbors, model) {
  if (!neighbors.length) {
    return {
      predictedCpe: model.cpeThreshold,
      predictedInteractions: quantile(model.interactionValues, 0.5),
      successRate: model.baseline,
    };
  }

  // 优化：指数衰减 + IQR 异常值过滤
  const neighborCpes = neighbors.map((n) => n.record.cpe).filter(Number.isFinite);
  const sortedCpes = [...neighborCpes].sort((a, b) => a - b);
  const q1 = quantile(sortedCpes, 0.25);
  const q3 = quantile(sortedCpes, 0.75);
  const iqr = (q3 || 0) - (q1 || 0);
  const lowerBound = (q1 || 0) - 1.5 * iqr;
  const upperBound = (q3 || 0) + 1.5 * iqr;

  const weights = neighbors.map((item, index) => {
    let w = Math.max(0.02, item.score) * Math.pow(0.88, index);
    const cpe = item.record.cpe;
    if (Number.isFinite(cpe) && iqr > 0 && (cpe < lowerBound || cpe > upperBound)) {
      w *= 0.5; // 异常值邻居降权
    }
    return w;
  });
  const cpe = weightedAverage(neighbors.map((item) => item.record.cpe), weights);
  const interactions = weightedAverage(neighbors.map((item) => item.record.totalInteractions || 0), weights);
  const success = weightedAverage(neighbors.map((item) => (item.record.label ? 1 : 0)), weights);
  return {
    predictedCpe: Number.isFinite(cpe) ? cpe : model.cpeThreshold,
    predictedInteractions: Number.isFinite(interactions) ? interactions : quantile(model.interactionValues, 0.5),
    successRate: Number.isFinite(success) ? success : model.baseline,
  };
}

function cpeToProbability(predictedCpe, threshold) {
  if (!isPositive(predictedCpe) || !isPositive(threshold)) {
    return 0.5;
  }
  const scale = Math.max(0.25, threshold * 0.42);
  return sigmoid((threshold - predictedCpe) / scale);
}

function assessCover(cover) {
  if (!cover || !Number.isFinite(cover.score)) {
    return null;
  }
  const strengths = [];
  const risks = [];
  if (cover.brightness < 0.34) {
    risks.push("画面偏暗");
  } else if (cover.brightness > 0.82) {
    risks.push("画面过曝");
  } else {
    strengths.push("亮度可读");
  }
  if (cover.contrast >= 0.18) {
    strengths.push("主体层次清楚");
  } else {
    risks.push("对比度偏低");
  }
  if (cover.sharpness >= 0.36) {
    strengths.push("清晰度较好");
  } else {
    risks.push("画面可能偏糊");
  }
  if (cover.infoDensity >= 0.28 && cover.infoDensity <= 0.72) {
    strengths.push("信息密度适中");
  } else if (cover.infoDensity > 0.72) {
    risks.push("信息可能过密");
  } else {
    risks.push("封面信息偏少");
  }
  if (cover.saturation >= 0.26) {
    strengths.push("色彩有记忆点");
  }
  if (cover.skinRatio > 0.04) {
    strengths.push("疑似有人物元素");
  }

  return {
    score: cover.score,
    probability: clamp(cover.score / 100, 0.08, 0.92),
    strengths,
    risks,
  };
}

function blendProbabilities(featureProbability, neighborSuccessRate, cpeProbability, coverAssessment) {
  // 优化：根据 feature 与 neighbor 信号一致性动态调整权重
  const agreement = 1 - Math.abs(featureProbability - neighborSuccessRate);

  if (!coverAssessment) {
    const neighborWeight = 0.40 + 0.06 * (1 - agreement);
    const featureWeight = 0.45 - 0.06 * (1 - agreement);
    return clamp(featureProbability * featureWeight + neighborSuccessRate * neighborWeight + cpeProbability * 0.15, 0, 1);
  }
  // 动态权重优化：封面评估越极端（极高分或极低分），其权重越大，反之则降低封面干扰
  const coverCertainty = Math.abs(coverAssessment.probability - 0.5) * 2; // 0~1
  const coverWeight = 0.10 + 0.08 * coverCertainty;
  const remaining = 1 - coverWeight;
  const neighborWeight = remaining * (0.40 + 0.05 * (1 - agreement));
  const featureWeight = remaining * (0.45 - 0.05 * (1 - agreement));
  const cpeWeight = remaining * 0.15;
  return clamp(
    featureProbability * featureWeight +
      neighborSuccessRate * neighborWeight +
      cpeProbability * cpeWeight +
      coverAssessment.probability * coverWeight,
    0,
    1,
  );
}

function classifyDecision(probability, strictness) {
  const cutoffs = {
    strict: { worth: 0.75, test: 0.6 },
    balanced: { worth: 0.7, test: 0.55 },
    growth: { worth: 0.64, test: 0.48 },
  }[strictness] || { worth: 0.7, test: 0.55 };

  if (probability >= cutoffs.worth) {
    return {
      key: "worth",
      title: "值得加热",
      tone: "good",
      summary: "标题、正文、封面和现有互动信号整体偏正向，可以进入加热测试。",
    };
  }
  if (probability >= cutoffs.test) {
    return {
      key: "test",
      title: "建议小额测试",
      tone: "watch",
      summary: "内容、封面或互动里有一部分正向信号，但不够稳定，适合先用小预算验证 CPE。",
    };
  }
  return {
    key: "hold",
    title: "暂不建议加热",
    tone: "bad",
    summary: "按当前历史模型看，预期 CPE 或相似样本表现不占优。",
  };
}

function suggestBudget(decisionKey, predictedCpe, model) {
  const medianSpend = isPositive(model.medianSpend) ? model.medianSpend : 100;
  const ratio = isPositive(predictedCpe) ? model.cpeThreshold / predictedCpe : 1;

  if (decisionKey === "worth") {
    const base = clamp(medianSpend * (ratio > 1.2 ? 0.32 : 0.24), 60, 260);
    return {
      amount: `${roundBudget(base)}-${roundBudget(base * 1.8)} 元`,
      action: `先跑 12-24 小时，若 CPE 低于 ${formatNumber(model.cpeThreshold)} 再加码。`,
    };
  }

  if (decisionKey === "test") {
    const base = clamp(medianSpend * 0.16, 30, 120);
    return {
      amount: `${roundBudget(base)}-${roundBudget(base * 1.6)} 元`,
      action: `只做验证，达到 ${formatNumber(model.cpeThreshold)} 左右的 CPE 再继续。`,
    };
  }

  return {
    amount: "0-30 元",
    action: "优先观察自然互动或改标题，再决定是否测试。",
  };
}

function estimateConfidence(model, neighbors, contributions, featureProbability, neighborSuccessRate) {
  const sampleScore = Math.min(1, model.records.length / 150);
  const neighborScore = neighbors.length
    ? clamp(neighbors.slice(0, 5).reduce((sum, item) => sum + item.score, 0) / Math.min(5, neighbors.length), 0, 1)
    : 0;
  const signalScore = Math.min(1, contributions.filter((item) => item.count >= 2).length / 5);
  // 优化：信号一致性越高，置信度越高
  const agreement = 1 - Math.abs((featureProbability || 0.5) - (neighborSuccessRate || 0.5));
  return clamp(Math.round((0.36 * sampleScore + 0.32 * neighborScore + 0.18 * signalScore + 0.14 * agreement) * 100), 18, 92);
}

function renderModel(model, parsed) {
  if (!model || !parsed) {
    els.sampleCount.textContent = "0";
    els.successCount.textContent = "0";
    els.autoCpe.textContent = "--";
    els.medianSpend.textContent = "--";
    els.exportModelButton.disabled = true;
    els.trainedPill.textContent = "模型未训练";
    els.trainedPill.className = "trained-pill";
    renderEmptyQuality();
    return;
  }

  els.sampleCount.textContent = model.records.length;
  els.successCount.textContent = model.successCount;
  els.autoCpe.textContent = formatNumber(model.autoCpe);
  els.medianSpend.textContent = formatMoney(model.medianSpend);
  els.exportModelButton.disabled = false;
  els.trainedPill.textContent = `已训练 ${model.records.length} 条`;
  els.trainedPill.className = "trained-pill ready";
  renderQuality(model.quality, model);
  renderTrainingSignals(model);
}

function renderTrainingSignals(model) {
  const topStats = [...model.featureStats.values()]
    .filter((item) => item.count >= 2 && Math.abs(item.effect) >= 0.08)
    .sort((a, b) => Math.abs(b.effect) - Math.abs(a.effect))
    .slice(0, 8);

  els.signalList.innerHTML = "";
  if (!topStats.length) {
    addSignal("训练完成", "样本已导入。预测后这里会显示标题、正文、封面、互动和相似样本带来的判断依据。", "中性", "neutral");
    return;
  }

  topStats.forEach((item) => {
    const label = item.effect >= 0 ? "正向" : "负向";
    const tone = item.effect >= 0 ? "positive" : "negative";
    addSignal(
      item.label,
      `${item.group}信号，历史出现 ${item.count} 次，成功率 ${formatPercent(item.rate)}，平均 CPE ${formatNumber(item.avgCpe)}。`,
      label,
      tone,
    );
  });
}

function renderPrediction(prediction) {
  const score = Math.round(prediction.probability * 100);
  const color = prediction.decision.tone === "good" ? "var(--green)" : prediction.decision.tone === "watch" ? "var(--amber)" : "var(--rose)";

  els.decisionCard.innerHTML = `
    <div class="decision-result">
      <div class="decision-main">
        <div class="decision-text">
          <h3>${escapeHtml(prediction.decision.title)}</h3>
          <p>${escapeHtml(prediction.decision.summary)}</p>
        </div>
        <div class="score-ring" style="--score:${score};--score-color:${color}">
          <div>
            <strong>${score}</strong>
            <span>值得分</span>
          </div>
        </div>
      </div>
      <div class="recommend-grid">
        <div class="recommend-item">
          <span>预测 CPE</span>
          <strong>${formatNumber(prediction.predictedCpe)}</strong>
        </div>
        <div class="recommend-item">
          <span>建议金额</span>
          <strong>${escapeHtml(prediction.budget.amount)}</strong>
        </div>
        <div class="recommend-item">
          <span>置信度</span>
          <strong>${prediction.confidence}%</strong>
        </div>
      </div>
      <p class="decision-note">${escapeHtml(prediction.budget.action)} 预测总互动约 ${formatInteger(prediction.predictedInteractions)}，相似样本成功率 ${formatPercent(prediction.neighborSuccessRate)}。</p>
    </div>
  `;

  renderPredictionSignals(prediction);
  renderNeighbors(prediction.neighbors);
}

function renderPredictionSignals(prediction) {
  els.signalList.innerHTML = "";
  addSignal(
    "目标 CPE",
    `当前口径下，低于 ${formatNumber(prediction.model.cpeThreshold)} 视为优秀。该帖预测 CPE 为 ${formatNumber(prediction.predictedCpe)}。`,
    prediction.predictedCpe <= prediction.model.cpeThreshold ? "正向" : "偏高",
    prediction.predictedCpe <= prediction.model.cpeThreshold ? "positive" : "negative",
  );
  if (prediction.coverAssessment) {
    const coverTone = prediction.coverAssessment.score >= 68 ? "positive" : prediction.coverAssessment.score < 48 ? "negative" : "neutral";
    const coverNotes = [
      ...prediction.coverAssessment.strengths.slice(0, 3),
      ...prediction.coverAssessment.risks.slice(0, 2),
    ].join("、");
    addSignal(
      "封面识别",
      coverNotes || "已完成封面图本地视觉分析。",
      `${Math.round(prediction.coverAssessment.score)}分`,
      coverTone,
    );
  } else {
    addSignal("封面未纳入", "未上传封面图，本次预测只使用标题、正文和现有互动。", "缺失", "neutral");
  }
  addSignal(
    "相似历史",
    `最相似的 ${Math.min(8, prediction.neighbors.length)} 条历史样本成功率为 ${formatPercent(prediction.neighborSuccessRate)}。`,
    "参考",
    "neutral",
  );

  const visible = prediction.contributions
    .filter((item) => item.count >= 1)
    .slice(0, 8);

  if (!visible.length) {
    addSignal("内容信号不足", "历史样本里没有找到明显相似的标题或正文表达，判断会更依赖现有互动和相似样本。", "中性", "neutral");
    return;
  }

  visible.forEach((item) => {
    const tone = item.delta >= 0 ? "positive" : "negative";
    addSignal(
      item.label,
      `历史出现 ${item.count} 次，成功率 ${formatPercent(item.rate)}，平均 CPE ${formatNumber(item.avgCpe)}。`,
      item.delta >= 0 ? "加分" : "减分",
      tone,
    );
  });
}

function addSignal(title, description, value, tone) {
  const node = els.signalTemplate.content.firstElementChild.cloneNode(true);
  node.querySelector("h3").textContent = title;
  node.querySelector("p").textContent = description;
  node.querySelector("strong").textContent = value;
  if (tone === "negative") {
    node.classList.add("negative");
  } else if (tone === "neutral") {
    node.classList.add("neutral");
  }
  els.signalList.appendChild(node);
}

function renderNeighbors(neighbors) {
  if (!neighbors.length) {
    els.neighborsBody.innerHTML = `<tr><td colspan="7" class="muted-cell">没有可展示的相似样本</td></tr>`;
    return;
  }

  els.neighborsBody.innerHTML = neighbors
    .slice(0, 8)
    .map(({ record, score }) => {
      const tagClass = record.label ? "good" : "bad";
      const result = record.label ? "优秀" : "普通";
      return `
        <tr>
          <td>${Math.round(score * 100)}%</td>
          <td class="content-cell">
            <strong>${escapeHtml(record.title || "无标题")}</strong>
            <span>${escapeHtml(shortText(record.body, 72) || "无正文")}</span>
          </td>
          <td>${formatInteger(record.preInteractions)}</td>
          <td>${formatInteger(record.totalInteractions)}</td>
          <td>${formatMoney(record.spend)}</td>
          <td>${formatNumber(record.cpe)}</td>
          <td><span class="result-tag ${tagClass}">${result}</span></td>
        </tr>
      `;
    })
    .join("");
}

function renderQuality(quality, model) {
  els.recognizedColumns.textContent = model.recognized.length ? model.recognized.map(fieldLabel).join(" / ") : "--";
  els.missingCpe.textContent = quality.missingCpe;
  els.missingTitle.textContent = `${quality.missingTitle}/${quality.missingBody}`;
  els.usableRate.textContent = formatPercent(quality.usableRate);
  els.warningList.innerHTML = "";

  if (quality.warnings.length) {
    quality.warnings.forEach((warning) => {
      const item = document.createElement("div");
      item.className = `warning-item ${warning.type || ""}`;
      item.textContent = warning.message;
      els.warningList.appendChild(item);
    });
  } else {
    const item = document.createElement("div");
    item.className = "warning-item ok";
    item.textContent = "数据列识别正常，可以开始预测。";
    els.warningList.appendChild(item);
  }
}

function renderEmptyQuality() {
  els.recognizedColumns.textContent = "--";
  els.missingCpe.textContent = "--";
  els.missingTitle.textContent = "--";
  els.usableRate.textContent = "--";
  els.warningList.innerHTML = `<div class="warning-item">导入历史数据后，这里会显示字段识别、缺失值和可用样本比例。</div>`;
}

function renderDecisionMessage(message, type) {
  const className = type === "error" ? "warning-item error" : "warning-item";
  els.decisionCard.innerHTML = `<div class="${className}">${escapeHtml(message)}</div>`;
}

async function handleCoverFile(file) {
  try {
    els.coverStatus.textContent = "正在识别封面...";
    els.coverMetrics.innerHTML = "";
    const analysis = await analyzeCoverImage(file);
    state.coverAnalysis = analysis;
    renderCoverAnalysis(analysis);
    if (state.model && cleanCell(els.newTitle.value) && cleanCell(els.newBody.value)) {
      await runPrediction();
    }
  } catch (error) {
    state.coverAnalysis = null;
    els.coverStatus.textContent = "封面识别失败，请换一张图片";
    els.coverMetrics.innerHTML = `<span class="cover-chip">${escapeHtml(error.message)}</span>`;
  }
}

function renderCoverAnalysis(analysis) {
  if (state.coverObjectUrl) {
    URL.revokeObjectURL(state.coverObjectUrl);
  }
  state.coverObjectUrl = analysis.previewUrl;
  els.coverPreview.src = analysis.previewUrl;
  els.coverStatus.textContent = `封面识别 ${Math.round(analysis.score)} 分`;
  els.coverMetrics.innerHTML = [
    `亮度 ${formatMetricPercent(analysis.brightness)}`,
    `对比 ${formatMetricPercent(analysis.contrast)}`,
    `色彩 ${formatMetricPercent(analysis.saturation)}`,
    `清晰 ${formatMetricPercent(analysis.sharpness)}`,
    `信息 ${formatMetricPercent(analysis.infoDensity)}`,
  ]
    .map((label) => `<span class="cover-chip">${label}</span>`)
    .join("");
}

async function analyzeCoverImage(file) {
  if (!file.type.startsWith("image/")) {
    throw new Error("请上传图片文件");
  }
  const { image, url } = await loadImage(file);
  const maxSide = 420;
  const scale = Math.min(1, maxSide / Math.max(image.naturalWidth, image.naturalHeight));
  const width = Math.max(1, Math.round(image.naturalWidth * scale));
  const height = Math.max(1, Math.round(image.naturalHeight * scale));
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d", { willReadFrequently: true });
  context.drawImage(image, 0, 0, width, height);
  const pixels = context.getImageData(0, 0, width, height).data;
  const total = width * height;
  const luminance = new Float32Array(total);
  let lumSum = 0;
  let satSum = 0;
  let darkCount = 0;
  let brightCount = 0;
  let skinCount = 0;

  for (let pixel = 0, index = 0; pixel < pixels.length; pixel += 4, index += 1) {
    const red = pixels[pixel];
    const green = pixels[pixel + 1];
    const blue = pixels[pixel + 2];
    const lum = (0.2126 * red + 0.7152 * green + 0.0722 * blue) / 255;
    const max = Math.max(red, green, blue);
    const min = Math.min(red, green, blue);
    const saturation = max ? (max - min) / max : 0;
    luminance[index] = lum;
    lumSum += lum;
    satSum += saturation;
    if (lum < 0.18) {
      darkCount += 1;
    }
    if (lum > 0.9) {
      brightCount += 1;
    }
    if (looksLikeSkin(red, green, blue)) {
      skinCount += 1;
    }
  }

  const brightness = lumSum / total;
  const saturation = satSum / total;
  let variance = 0;
  let edgeSum = 0;
  let highEdgeCount = 0;
  for (let index = 0; index < luminance.length; index += 1) {
    const lum = luminance[index];
    variance += (lum - brightness) ** 2;
    const x = index % width;
    const y = Math.floor(index / width);
    if (x > 0) {
      edgeSum += Math.abs(lum - luminance[index - 1]);
    }
    if (y > 0) {
      edgeSum += Math.abs(lum - luminance[index - width]);
    }
    if ((x > 0 && Math.abs(lum - luminance[index - 1]) > 0.22) || (y > 0 && Math.abs(lum - luminance[index - width]) > 0.22)) {
      highEdgeCount += 1;
    }
  }

  const contrast = Math.sqrt(variance / total);
  const edgeDensity = edgeSum / (total * 2);
  const highEdgeRatio = highEdgeCount / total;
  const sharpness = rangeScore(edgeDensity, 0.015, 0.085, 0.2);
  const infoDensity = rangeScore(highEdgeRatio, 0.018, 0.11, 0.28);
  const exposurePenalty = clamp((darkCount + brightCount) / total / 0.42, 0, 1);
  const aspectRatio = width / height;
  const aspectScore = aspectRatio >= 0.62 && aspectRatio <= 1.45 ? 1 : 0.72;
  const score =
    100 *
    aspectScore *
    (0.24 * bellScore(brightness, 0.58, 0.35) +
      0.2 * clamp(contrast / 0.26, 0, 1) +
      0.2 * clamp(saturation / 0.48, 0, 1) +
      0.2 * sharpness +
      0.16 * infoDensity) *
    (1 - exposurePenalty * 0.18);

  return {
    score: clamp(score + Math.min(6, (skinCount / total) * 80), 0, 100),
    brightness,
    contrast,
    saturation,
    sharpness,
    infoDensity,
    skinRatio: skinCount / total,
    darkRatio: darkCount / total,
    brightRatio: brightCount / total,
    aspectRatio,
    previewUrl: url,
    imageDataUrl: canvas.toDataURL("image/jpeg", 0.82),
    source: "image",
  };
}

function loadImage(file) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const image = new Image();
    image.onload = () => resolve({ image, url });
    image.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("图片读取失败"));
    };
    image.src = url;
  });
}

function looksLikeSkin(red, green, blue) {
  return red > 95 && green > 40 && blue > 20 && red > green && red > blue && Math.max(red, green, blue) - Math.min(red, green, blue) > 15;
}

function getDataQuality(parsed, validRecords) {
  const missingCpe = parsed.records.filter((record) => !isPositive(record.cpe)).length;
  const missingTitle = parsed.records.filter((record) => !record.title).length;
  const missingBody = parsed.records.filter((record) => !record.body).length;
  const usableRate = parsed.records.length ? validRecords.length / parsed.records.length : 0;
  const warnings = [];

  if (!parsed.recognized.includes("title")) {
    warnings.push({ type: "error", message: "没有识别到标题列。请确认表头包含“标题”。" });
  }
  if (!parsed.recognized.includes("body")) {
    warnings.push({ message: "没有识别到正文/内容列。模型仍会使用标题和互动数据，但建议后续补充正文列，判断会更贴近真实投前决策。" });
  }
  if (!parsed.recognized.includes("cpe") && !parsed.recognized.includes("spend")) {
    warnings.push({ type: "error", message: "没有识别到综合 CPE 或总投放金额列，无法学习投放结果。" });
  }
  if (!parsed.recognized.includes("preInteractions")) {
    warnings.push({ message: "没有识别到现有互动量/投前互动量列，工具会主要依赖内容特征。若有点赞、收藏、评论、分享列，也可以直接导入。" });
  }
  if (usableRate < 0.7) {
    warnings.push({ message: `可训练样本比例为 ${formatPercent(usableRate)}，建议补齐标题和 CPE。` });
  }
  if (validRecords.length < 30) {
    warnings.push({ message: "可训练样本偏少，结论更适合做初筛，不建议直接大额加热。" });
  }

  return {
    missingCpe,
    missingTitle,
    missingBody,
    usableRate,
    warnings,
  };
}

function clearAll() {
  els.historyInput.value = "";
  els.fileInput.value = "";
  state.parsed = null;
  state.model = null;
  state.lastPrediction = null;
  state.coverAnalysis = null;
  if (state.coverObjectUrl) {
    URL.revokeObjectURL(state.coverObjectUrl);
    state.coverObjectUrl = null;
  }
  localStorage.removeItem(STORAGE_KEY);
  els.coverInput.value = "";
  els.coverPreview.removeAttribute("src");
  els.coverStatus.textContent = "上传封面图后参与判断";
  els.coverMetrics.innerHTML = "";
  if (els.postUrl) els.postUrl.value = "";
  setFetchHint(
    "需要先在终端运行 node server.js，再访问 http://localhost:5173 打开本工具。",
    ""
  );
  setStatus("待导入", "");
  renderModel(null, null);
  els.decisionCard.innerHTML = `
    <div class="empty-decision">
      <div class="empty-bars" aria-hidden="true"><span></span><span></span><span></span></div>
      <p>训练模型后，这里会显示是否值得加热、预测 CPE、建议测试金额和原因。</p>
    </div>
  `;
  els.neighborsBody.innerHTML = `<tr><td colspan="7" class="muted-cell">训练并预测后显示相似历史样本</td></tr>`;
  els.signalList.innerHTML = "";
}

function setAppendResult(message, type) {
  if (!els.appendResult) return;
  els.appendResult.textContent = message;
  els.appendResult.classList.remove("hint-error", "hint-success");
  if (type === "error") els.appendResult.classList.add("hint-error");
  else if (type === "success") els.appendResult.classList.add("hint-success");
}

// 按发布日期推断加热渠道（与 merge_data.js 的口径一致）
// 2026-03-01 前 → 口碑通；2026-03-01 ~ 04-27 → 合作广场；>= 2026-04-28 → 薯条
function inferChannelFromDate(dateObj) {
  if (!(dateObj instanceof Date) || isNaN(dateObj.getTime())) return "";
  if (dateObj < new Date("2026-03-01")) return "口碑通";
  if (dateObj < new Date("2026-04-28")) return "合作广场";
  return "薯条";
}

// 从小红书链接里提取笔记ID
function extractNoteIdFromLink(link) {
  const text = String(link || "");
  const m = text.match(/(?:explore|item|discovery\/item)\/([0-9a-fA-F]{12,32})/);
  return m ? m[1] : "";
}

// 去重 key：优先笔记ID，其次链接，最后标题+CPE
function recordDedupKey(record) {
  const noteId = record.noteId || extractNoteIdFromLink(record.link);
  if (noteId) return "id:" + noteId;
  if (record.link) return "url:" + record.link.split("?")[0];
  const cpe = Number.isFinite(record.cpe) ? record.cpe.toFixed(2) : "";
  return "tc:" + (record.title || "").trim() + "|" + cpe;
}

function csvEscape(value) {
  const s = String(value == null ? "" : value);
  return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
}

// 把解析后的记录序列化成工具能识别的规范 CSV
const APPEND_CANONICAL_HEADERS = [
  "发布日期", "加热渠道", "一级分类", "二级分类", "标签",
  "标题", "正文", "投前互动量", "总互动量", "总投放金额", "综合CPE", "链接", "笔记ID",
];
function serializeRecordsToCsv(records) {
  const lines = [APPEND_CANONICAL_HEADERS.join(",")];
  for (const r of records) {
    lines.push([
      r.publishDateText || "",
      r.channel || "",
      r.category1 || "",
      r.category2 || "",
      r.tags || "",
      r.title || "",
      r.body || "",
      Number.isFinite(r.preInteractions) ? r.preInteractions : "",
      Number.isFinite(r.totalInteractions) ? r.totalInteractions : "",
      Number.isFinite(r.spend) ? r.spend : "",
      Number.isFinite(r.cpe) ? r.cpe : "",
      r.link || "",
      r.noteId || extractNoteIdFromLink(r.link),
    ].map(csvEscape).join(","));
  }
  return lines.join("\n");
}

// 补全记录的渠道和笔记ID
function enrichRecord(record) {
  if (!record.channel) {
    record.channel = inferChannelFromDate(record.publishDate);
  }
  if (!record.noteId) {
    record.noteId = extractNoteIdFromLink(record.link);
  }
  return record;
}

function appendNewData() {
  const newText = (els.appendInput.value || "").trim();
  if (!newText) {
    setAppendResult("请先粘贴或上传本月新数据。", "error");
    return;
  }

  let newParsed;
  try {
    newParsed = parseHistoryTable(newText);
  } catch (e) {
    setAppendResult("新数据解析失败：" + e.message, "error");
    return;
  }
  if (!newParsed.records.length) {
    setAppendResult("新数据里没有识别到记录行。", "error");
    return;
  }

  // 现有训练集（可能为空）
  let existingRecords = [];
  const existingText = (els.historyInput.value || "").trim();
  if (existingText) {
    try {
      existingRecords = parseHistoryTable(existingText).records;
    } catch (e) {
      existingRecords = [];
    }
  }

  // 合并 + 去重（新数据覆盖同 key 的旧记录）
  const merged = new Map();
  for (const r of existingRecords) {
    enrichRecord(r);
    merged.set(recordDedupKey(r), r);
  }
  let added = 0;
  let updated = 0;
  for (const r of newParsed.records) {
    enrichRecord(r);
    // 跳过完全空的行
    if (!r.title && !r.body) continue;
    const key = recordDedupKey(r);
    if (merged.has(key)) updated += 1;
    else added += 1;
    merged.set(key, r);
  }

  const mergedRecords = Array.from(merged.values());
  const canonicalCsv = serializeRecordsToCsv(mergedRecords);

  // 渠道分布统计
  const channelCounts = {};
  for (const r of mergedRecords) {
    const ch = r.channel || "未知";
    channelCounts[ch] = (channelCounts[ch] || 0) + 1;
  }
  const channelSummary = Object.entries(channelCounts)
    .sort((a, b) => b[1] - a[1])
    .map(([ch, n]) => `${ch} ${n}`)
    .join("，");

  // 写回主训练框并重训
  els.historyInput.value = canonicalCsv;
  trainFromInput({ silent: true });

  if (state.model) {
    els.appendInput.value = "";
    if (els.appendFileInput) els.appendFileInput.value = "";
    setAppendResult(
      `已并入：新增 ${added} 条，更新 ${updated} 条，去重后共 ${mergedRecords.length} 条。渠道分布：${channelSummary}。模型已重训。`,
      "success"
    );
  } else {
    setAppendResult("并入后重训失败，请检查数据格式。", "error");
  }
}

function toggleCookiePanel() {
  const open = !els.cookieBody.hidden;
  els.cookieBody.hidden = open;
  els.cookieChevron.textContent = open ? "▸" : "▾";
}

function setCookieBadge(configured, preview) {
  if (!els.cookieBadge) return;
  if (configured) {
    els.cookieBadge.textContent = "已配置";
    els.cookieBadge.className = "cookie-badge badge-ok";
  } else {
    els.cookieBadge.textContent = "未配置";
    els.cookieBadge.className = "cookie-badge badge-none";
  }
  if (els.cookieInput && configured && preview && !els.cookieInput.value.trim()) {
    els.cookieInput.placeholder = preview + " （已保存，重新粘贴可更新）";
  }
}

async function checkCookieStatus() {
  try {
    const resp = await fetch("/api/cookie");
    if (!resp.ok) return;
    const data = await resp.json();
    setCookieBadge(data.configured, data.preview);
    if (els.saveCookieButton && data.lockedByEnv) {
      els.saveCookieButton.disabled = true;
      els.clearCookieButton.disabled = true;
      els.cookieHint.textContent = "Cookie 由环境变量 XHS_COOKIE 锁定，界面不可修改。";
    }
  } catch (e) {
    if (els.cookieBadge) {
      els.cookieBadge.textContent = "Server 未运行";
      els.cookieBadge.className = "cookie-badge badge-none";
    }
  }
}

async function saveCookie() {
  const cookie = els.cookieInput ? els.cookieInput.value.trim() : "";
  if (!cookie) {
    els.cookieHint.textContent = "请先粘贴 Cookie 内容。";
    return;
  }
  els.saveCookieButton.disabled = true;
  els.cookieHint.textContent = "保存中...";
  try {
    const resp = await fetch("/api/cookie", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cookie }),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || "保存失败");
    setCookieBadge(data.configured, data.preview);
    els.cookieHint.textContent = `已保存（长度 ${data.length}）。下次抓取会自动带上，无需重启 server。`;
    els.cookieInput.value = "";
  } catch (err) {
    els.cookieHint.textContent = "保存失败：" + (err.message || "未知错误");
  } finally {
    els.saveCookieButton.disabled = false;
  }
}

async function clearCookie() {
  els.clearCookieButton.disabled = true;
  try {
    const resp = await fetch("/api/cookie", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cookie: "" }),
    });
    const data = await resp.json();
    setCookieBadge(false, "");
    els.cookieHint.textContent = "Cookie 已清空。";
    if (els.cookieInput) {
      els.cookieInput.value = "";
      els.cookieInput.placeholder = "a1=...; webId=...; web_session=...; （粘贴完整 Cookie 值）";
    }
  } catch (err) {
    els.cookieHint.textContent = "清空失败：" + (err.message || "未知错误");
  } finally {
    els.clearCookieButton.disabled = false;
  }
}

function toggleLlmPanel() {
  const open = !els.llmBody.hidden;
  els.llmBody.hidden = open;
  els.llmChevron.textContent = open ? "▸" : "▾";
}

function setLlmBadge(configured, config = {}) {
  state.llmConfigured = !!configured;
  state.llmModel = config.model || "";
  if (els.llmBadge) {
    els.llmBadge.textContent = configured ? "已配置" : "未配置";
    els.llmBadge.className = configured ? "cookie-badge badge-ok" : "cookie-badge badge-none";
  }
  if (els.llmProviderSelect && config.provider) {
    els.llmProviderSelect.value = config.provider;
  }
  if (els.llmModelInput && config.model && !els.llmModelInput.value.trim()) {
    els.llmModelInput.value = config.model;
  }
  if (els.llmBaseUrlInput && config.baseUrl && !els.llmBaseUrlInput.value.trim()) {
    els.llmBaseUrlInput.value = config.baseUrl;
  }
  if (els.llmSendImageToggle && typeof config.sendImage === "boolean") {
    els.llmSendImageToggle.checked = config.sendImage;
  }
  if (els.llmPredictButton) {
    els.llmPredictButton.disabled = !configured;
  }
  updateLlmProviderDefaults({ preserveModel: true, preserveBaseUrl: true, preserveImage: true });
}

async function checkLlmStatus() {
  try {
    const resp = await fetch("/api/llm-status");
    if (!resp.ok) return;
    const data = await resp.json();
    setLlmBadge(data.configured, data);
    if (els.llmHint) {
      els.llmHint.textContent = data.configured
        ? `已连接：${providerLabel(data.provider)} / ${data.model}`
        : "未配置 API Key。可以在这里临时保存，或启动前设置 OPENAI_API_KEY。";
    }
    if (data.lockedByEnv && els.clearLlmButton) {
      els.clearLlmButton.disabled = true;
    }
  } catch (e) {
    if (els.llmBadge) {
      els.llmBadge.textContent = "Server 未运行";
      els.llmBadge.className = "cookie-badge badge-none";
    }
    if (els.llmPredictButton) {
      els.llmPredictButton.disabled = true;
    }
  }
}

async function saveLlmConfig() {
  const apiKey = els.llmApiKeyInput ? els.llmApiKeyInput.value.trim() : "";
  let provider = els.llmProviderSelect ? els.llmProviderSelect.value : "openai";
  if (/^AIza[0-9A-Za-z_-]+/.test(apiKey) && provider !== "gemini") {
    provider = "gemini";
    if (els.llmProviderSelect) els.llmProviderSelect.value = "gemini";
    updateLlmProviderDefaults();
    els.llmHint.textContent = "检测到 Gemini API Key，已自动切换到 Gemini。正在保存...";
  }
  const model = els.llmModelInput ? els.llmModelInput.value.trim() : "";
  const baseUrl = els.llmBaseUrlInput ? els.llmBaseUrlInput.value.trim() : "";
  const sendImage = els.llmSendImageToggle ? els.llmSendImageToggle.checked : true;
  if (!apiKey && !model) {
    els.llmHint.textContent = "请先填写 API Key 或模型名。";
    return;
  }
  els.saveLlmButton.disabled = true;
  els.llmHint.textContent = "保存中...";
  try {
    const resp = await fetch("/api/llm-config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ apiKey, provider, model, baseUrl, sendImage }),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || "保存失败");
    setLlmBadge(data.configured, data);
    els.llmHint.textContent = data.configured ? `已保存：${providerLabel(data.provider)} / ${data.model}` : "未配置 API Key。";
    if (els.llmApiKeyInput) els.llmApiKeyInput.value = "";
  } catch (err) {
    els.llmHint.textContent = "保存失败：" + (err.message || "未知错误");
  } finally {
    els.saveLlmButton.disabled = false;
  }
}

async function clearLlmConfig() {
  els.clearLlmButton.disabled = true;
  try {
    const resp = await fetch("/api/llm-config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        apiKey: "",
        clearKey: true,
        provider: els.llmProviderSelect ? els.llmProviderSelect.value : "openai",
        model: els.llmModelInput ? els.llmModelInput.value.trim() : "",
        baseUrl: els.llmBaseUrlInput ? els.llmBaseUrlInput.value.trim() : "",
        sendImage: els.llmSendImageToggle ? els.llmSendImageToggle.checked : true,
      }),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || "清空失败");
    setLlmBadge(data.configured, data);
    if (els.llmApiKeyInput) els.llmApiKeyInput.value = "";
    els.llmHint.textContent = "API Key 已从本地服务内存清空。";
  } catch (err) {
    els.llmHint.textContent = "清空失败：" + (err.message || "未知错误");
  } finally {
    els.clearLlmButton.disabled = false;
  }
}

async function runLlmHybridPrediction() {
  if (!state.llmConfigured) {
    renderDecisionMessage("请先在左侧 LLM 设置里配置 API Key。", "error");
    return;
  }
  const localPrediction = await runPrediction({ skipRender: true });
  if (!localPrediction) return;
  renderPrediction(localPrediction);

  const originalHtml = els.llmPredictButton.innerHTML;
  els.llmPredictButton.disabled = true;
  els.llmPredictButton.innerHTML = '<span class="button-icon llm-icon" aria-hidden="true"></span>LLM分析中...';
  appendLlmLoadingSignal();

  try {
    const payload = buildLlmRequestPayload(localPrediction);
    const resp = await fetch("/api/llm-predict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      throw new Error(data.error || `LLM 服务返回 ${resp.status}`);
    }
    renderLlmPrediction(data, localPrediction);
  } catch (err) {
    addSignal("LLM 混合判断失败", err.message || "未知错误", "失败", "negative");
  } finally {
    els.llmPredictButton.disabled = !state.llmConfigured;
    els.llmPredictButton.innerHTML = originalHtml;
  }
}

function buildLlmRequestPayload(prediction) {
  const input = prediction.input;
  return {
    post: {
      title: input.title,
      body: input.body,
      noteId: input.noteId,
      currentInteractions: input.preInteractions,
      likes: input.interactionParts.likes,
      collects: input.interactionParts.collects,
      comments: input.interactionParts.comments,
      shares: input.interactionParts.shares,
      cover: compactCover(input.cover),
      coverImage: input.cover && input.cover.imageDataUrl ? input.cover.imageDataUrl : null,
    },
    localPrediction: {
      decision: prediction.decision.title,
      score: Math.round(prediction.probability * 100),
      predictedCpe: prediction.predictedCpe,
      predictedInteractions: prediction.predictedInteractions,
      neighborSuccessRate: prediction.neighborSuccessRate,
      cpeThreshold: prediction.model.cpeThreshold,
      confidence: prediction.confidence,
      signals: prediction.contributions.slice(0, 10).map((item) => ({
        label: item.label,
        group: item.group,
        direction: item.delta >= 0 ? "positive" : "negative",
        count: item.count,
        successRate: item.rate,
        avgCpe: item.avgCpe,
      })),
    },
    similarHistory: prediction.neighbors.slice(0, 8).map(({ record, score }) => ({
      similarity: Math.round(score * 100),
      title: record.title,
      body: shortText(record.body, 160),
      preInteractions: record.preInteractions,
      totalInteractions: record.totalInteractions,
      spend: record.spend,
      cpe: record.cpe,
      result: record.label ? "优秀" : "普通",
    })),
    modelSummary: {
      sampleCount: prediction.model.records.length,
      cpeThreshold: prediction.model.cpeThreshold,
      medianSpend: prediction.model.medianSpend,
      baselineSuccessRate: prediction.model.baseline,
      strictness: prediction.model.settings.strictness,
    },
  };
}

function compactCover(cover) {
  if (!cover) return null;
  return {
    score: cover.score,
    brightness: cover.brightness,
    contrast: cover.contrast,
    saturation: cover.saturation,
    sharpness: cover.sharpness,
    infoDensity: cover.infoDensity,
    skinRatio: cover.skinRatio,
    darkRatio: cover.darkRatio,
    brightRatio: cover.brightRatio,
    aspectRatio: cover.aspectRatio,
  };
}

function appendLlmLoadingSignal() {
  addSignal("LLM 混合判断", "正在结合新帖、封面、相似历史和本地预测做二次判断。", "进行中", "neutral");
}

function renderLlmPrediction(data, localPrediction) {
  const llm = data.prediction || data;
  const rawScore = Number(llm.score);
  const score = clamp(Number.isFinite(rawScore) ? Math.round(rawScore) : Math.round(localPrediction.probability * 100), 0, 100);
  const decisionTitle = llm.decision || localPrediction.decision.title;
  const tone = decisionTitle.includes("值得") && !decisionTitle.includes("不") ? "good" : decisionTitle.includes("小额") ? "watch" : "bad";
  const color = tone === "good" ? "var(--green)" : tone === "watch" ? "var(--amber)" : "var(--rose)";
  const reasons = Array.isArray(llm.reasons) ? llm.reasons : [];
  const risks = Array.isArray(llm.risks) ? llm.risks : [];
  const actions = Array.isArray(llm.actions) ? llm.actions : [];
  const cpeRange = llm.predicted_cpe_range || llm.predictedCpeRange || `${formatNumber(localPrediction.predictedCpe)}`;
  const budget = llm.suggested_budget || llm.suggestedBudget || localPrediction.budget.amount;
  const confidence = Number.isFinite(Number(llm.confidence)) ? `${Math.round(Number(llm.confidence))}%` : `${localPrediction.confidence}%`;

  els.decisionCard.innerHTML = `
    <div class="decision-result">
      <div class="decision-main">
        <div class="decision-text">
          <span class="llm-badge-inline">LLM 混合预测 · ${escapeHtml(providerLabel(data.provider))} / ${escapeHtml(data.model || state.llmModel || "")}</span>
          <h3>${escapeHtml(decisionTitle)}</h3>
          <p>${escapeHtml(llm.summary || "已结合本地相似历史和 LLM 语义判断。")}</p>
        </div>
        <div class="score-ring" style="--score:${score};--score-color:${color}">
          <div>
            <strong>${score}</strong>
            <span>值得分</span>
          </div>
        </div>
      </div>
      <div class="recommend-grid">
        <div class="recommend-item">
          <span>预测 CPE</span>
          <strong>${escapeHtml(cpeRange)}</strong>
        </div>
        <div class="recommend-item">
          <span>建议金额</span>
          <strong>${escapeHtml(budget)}</strong>
        </div>
        <div class="recommend-item">
          <span>置信度</span>
          <strong>${escapeHtml(confidence)}</strong>
        </div>
      </div>
      ${renderLlmList("主要理由", reasons)}
      ${renderLlmList("主要风险", risks)}
      ${renderLlmList("操作建议", actions)}
      <p class="decision-note">本地模型参考：${escapeHtml(localPrediction.decision.title)}，预测 CPE ${formatNumber(localPrediction.predictedCpe)}，相似样本成功率 ${formatPercent(localPrediction.neighborSuccessRate)}。</p>
    </div>
  `;

  els.signalList.innerHTML = "";
  addSignal("LLM 混合预测", llm.calibration_notes || "LLM 已基于相似历史、本地预测和内容/封面完成校准。", "完成", "positive");
  reasons.slice(0, 5).forEach((reason) => addSignal("LLM 理由", reason, "加权", "positive"));
  risks.slice(0, 5).forEach((risk) => addSignal("LLM 风险", risk, "注意", "negative"));
  renderNeighbors(localPrediction.neighbors);
}

function updateLlmProviderDefaults(options = {}) {
  if (!els.llmProviderSelect) return;
  const provider = els.llmProviderSelect.value;
  const defaults = {
    openai: { model: "gpt-5.1", baseUrl: "https://api.openai.com/v1", image: true },
    deepseek: { model: "deepseek-chat", baseUrl: "https://api.deepseek.com", image: false },
    gemini: { model: "gemini-2.5-flash", baseUrl: "https://generativelanguage.googleapis.com", image: true },
    compatible: { model: "", baseUrl: "", image: false },
  }[provider] || {};
  if (els.llmModelInput && !options.preserveModel) {
    els.llmModelInput.value = defaults.model || "";
  }
  if (els.llmBaseUrlInput && !options.preserveBaseUrl) {
    els.llmBaseUrlInput.value = provider === "compatible" ? "" : defaults.baseUrl || "";
  }
  if (els.llmSendImageToggle && !options.preserveImage) {
    els.llmSendImageToggle.checked = !!defaults.image;
  }
}

function providerLabel(provider) {
  return {
    openai: "OpenAI",
    deepseek: "DeepSeek",
    gemini: "Gemini",
    compatible: "OpenAI兼容",
  }[provider] || "LLM";
}

function renderLlmList(title, items) {
  if (!Array.isArray(items) || !items.length) return "";
  return `
    <div>
      <p class="section-title">${escapeHtml(title)}</p>
      <ul class="llm-list">
        ${items.slice(0, 5).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
      </ul>
    </div>
  `;
}

function extractXhsUrl(raw) {
  if (!raw) return "";
  const text = String(raw).trim();
  const match = text.match(/https?:\/\/[\w.\-]+(?:xiaohongshu|xhslink)\.com[^\s，,)）"]*/i);
  if (match) return match[0];
  if (/^https?:\/\//i.test(text)) return text;
  return "";
}

function setFetchHint(message, type) {
  if (!els.fetchPostHint) return;
  els.fetchPostHint.textContent = message;
  els.fetchPostHint.classList.remove("hint-error", "hint-success", "hint-loading");
  if (type === "error") els.fetchPostHint.classList.add("hint-error");
  else if (type === "success") els.fetchPostHint.classList.add("hint-success");
  else if (type === "loading") els.fetchPostHint.classList.add("hint-loading");
}

async function fetchPostFromUrl() {
  if (!els.postUrl || !els.fetchPostButton) return;
  const target = extractXhsUrl(els.postUrl.value);
  if (!target) {
    setFetchHint("没识别到链接，请粘贴完整的小红书笔记链接。", "error");
    return;
  }

  const restoreLabel = els.fetchPostButton.innerHTML;
  els.fetchPostButton.disabled = true;
  els.fetchPostButton.innerHTML = '<span class="button-icon fetch-icon" aria-hidden="true"></span>抓取中...';
  setFetchHint("正在抓取笔记内容...", "loading");

  let data;
  try {
    const resp = await fetch(`/api/fetch-post?url=${encodeURIComponent(target)}`);
    data = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      throw new Error(data && data.error ? data.error : `服务返回 ${resp.status}`);
    }
  } catch (err) {
    setFetchHint(
      (err && err.message ? err.message : "抓取失败") +
        "。若提示无法连接，请确认终端里已执行 node server.js 并通过 http://localhost:5173 访问本工具。",
      "error"
    );
    els.fetchPostButton.disabled = false;
    els.fetchPostButton.innerHTML = restoreLabel;
    return;
  }

  applyFetchedPost(data);

  els.fetchPostButton.disabled = false;
  els.fetchPostButton.innerHTML = restoreLabel;
}

function applyFetchedPost(data) {
  const filled = [];
  if (data.title) {
    els.newTitle.value = data.title;
    filled.push("标题");
  }
  if (data.body) {
    els.newBody.value = data.body;
    filled.push("正文");
  }
  if (data.noteId && !els.newNoteId.value) {
    els.newNoteId.value = data.noteId;
  }

  const likes = Number.isFinite(data.likes) ? data.likes : null;
  const collects = Number.isFinite(data.collects) ? data.collects : null;
  const comments = Number.isFinite(data.comments) ? data.comments : null;
  const shares = Number.isFinite(data.shares) ? data.shares : null;
  if (likes !== null) els.newLikes.value = likes;
  if (collects !== null) els.newCollects.value = collects;
  if (comments !== null) els.newComments.value = comments;
  if (shares !== null) els.newShares.value = shares;
  const parts = [likes, collects, comments, shares].filter((x) => Number.isFinite(x));
  if (parts.length) {
    const sum = parts.reduce((a, b) => a + b, 0);
    els.newPreInteractions.value = sum;
    filled.push("当前互动");
  }

  if (data.cover) {
    fetchAndAnalyzeCover(data.cover).catch(() => {});
    filled.push("封面");
  }

  if (filled.length) {
    setFetchHint(`已抓取：${filled.join(" / ")}。请人工核对一下再判断。`, "success");
  } else {
    setFetchHint("抓到了页面，但没解析出可用字段。可能是风控页或非笔记页。", "error");
  }
}

async function fetchAndAnalyzeCover(coverUrl) {
  try {
    els.coverStatus.textContent = "正在下载封面...";
    els.coverMetrics.innerHTML = "";
    const resp = await fetch(`/api/image-proxy?url=${encodeURIComponent(coverUrl)}`);
    if (!resp.ok) throw new Error("封面下载失败");
    const blob = await resp.blob();
    if (!blob.type || !blob.type.startsWith("image/")) {
      const renamed = new Blob([blob], { type: "image/jpeg" });
      await handleCoverFile(renamed);
    } else {
      await handleCoverFile(blob);
    }
    els.coverInput.value = "";
  } catch (err) {
    els.coverStatus.textContent = "封面识别失败：" + (err && err.message ? err.message : "未知错误");
  }
}

function fillDemoPost() {
  els.newTitle.value = "现在的专车也太卷了吧！";
  els.newBody.value = "今天下班打专车，司机提前确认路线，还主动提醒我坐后排更方便。车里很干净，女生晚上出门这种安全感真的很重要。";
  els.newPreInteractions.value = "6";
  els.newLikes.value = "4";
  els.newCollects.value = "1";
  els.newComments.value = "1";
  els.newShares.value = "0";
  els.newNoteId.value = "";
  if (state.model) {
    runPrediction();
  }
}

function exportModelSummary() {
  if (!state.model) {
    return;
  }
  const model = state.model;
  const payload = {
    trainedAt: model.trainedAt,
    samples: model.records.length,
    successCount: model.successCount,
    baselineSuccessRate: model.baseline,
    cpeThreshold: model.cpeThreshold,
    autoCpe: model.autoCpe,
    medianSpend: model.medianSpend,
    recognizedColumns: model.recognized,
    topPositiveSignals: [...model.featureStats.values()]
      .filter((item) => item.count >= 2 && item.effect > 0)
      .sort((a, b) => b.effect - a.effect)
      .slice(0, 12),
    topNegativeSignals: [...model.featureStats.values()]
      .filter((item) => item.count >= 2 && item.effect < 0)
      .sort((a, b) => a.effect - b.effect)
      .slice(0, 12),
    settings: model.settings,
  };
  downloadText(`小红书加热模型摘要-${dateStamp()}.json`, JSON.stringify(payload, null, 2));
}

function setStatus(message, type) {
  els.dataStatus.textContent = message;
  els.dataStatus.className = `status-dot ${type || ""}`.trim();
  if (type === "error") {
    els.trainedPill.textContent = "训练失败";
    els.trainedPill.className = "trained-pill error";
  }
}

function fieldLabel(field) {
  return {
    publishDate: "发布日期",
    endDate: "投放截止",
    status: "状态",
    link: "链接",
    noteId: "笔记ID",
    adRecords: "投放记录",
    title: "标题",
    body: "正文",
    coverScore: "封面评分",
    coverBrightness: "封面亮度",
    coverContrast: "封面对比",
    coverSaturation: "封面色彩",
    coverSharpness: "封面清晰",
    coverInfoDensity: "封面信息",
    preInteractions: "现有互动",
    likes: "点赞",
    collects: "收藏",
    comments: "评论",
    shares: "分享",
    postLikes: "投后点赞",
    postCollects: "投后收藏",
    postComments: "投后评论",
    postShares: "投后分享",
    postInteractions: "投后互动",
    totalInteractions: "总互动",
    spend: "金额",
    cpe: "CPE",
  }[field] || field;
}

function interactionBin(value) {
  if (!Number.isFinite(value)) {
    return "未知";
  }
  if (value <= 2) {
    return "0-2";
  }
  if (value <= 5) {
    return "3-5";
  }
  if (value <= 15) {
    return "6-15";
  }
  if (value <= 50) {
    return "16-50";
  }
  return "51+";
}

function lengthBinIndex(bin) {
  return { "很短": 0, "短": 1, "中等": 2, "长": 3 }[bin] ?? 1;
}

function bodyLengthBinIndex(bin) {
  return { "缺失": 0, "短": 1, "中等": 2, "长": 3 }[bin] ?? 0;
}

function interactionSimilarity(a, b) {
  if (!Number.isFinite(a) || !Number.isFinite(b)) {
    return 0.55;
  }
  // 优化：使用相对差异 + 高斯衰减，对大数值差异更敏感
  const max = Math.max(a, b);
  if (max === 0) return 0.5;
  const relDiff = Math.abs(a - b) / max;
  return Math.exp(-relDiff * 2.5);
}

function interactionMixSimilarity(a, b) {
  const fields = ["likes", "collects", "comments", "shares"];
  const totalA = sumInteractionParts(a);
  const totalB = sumInteractionParts(b);
  if (!isPositive(totalA) || !isPositive(totalB)) {
    return 0.5;
  }
  const distance = fields.reduce((sum, field) => {
    return sum + Math.abs(safeRatio(a[field], totalA) - safeRatio(b[field], totalB));
  }, 0);
  return clamp(1 - distance / 2, 0, 1);
}

function sumInteractionParts(parts) {
  if (!parts) {
    return null;
  }
  const values = ["likes", "collects", "comments", "shares"]
    .map((field) => parts[field])
    .filter((value) => Number.isFinite(value));
  if (!values.length) {
    return null;
  }
  return values.reduce((sum, value) => sum + Math.max(0, value), 0);
}

function safeRatio(value, total) {
  if (!Number.isFinite(value) || !isPositive(total)) {
    return NaN;
  }
  return Math.max(0, value) / total;
}

function ratioBin(value) {
  if (!Number.isFinite(value)) {
    return "未知";
  }
  if (value < 0.05) {
    return "低";
  }
  if (value < 0.18) {
    return "中";
  }
  return "高";
}

function bellScore(value, ideal, tolerance) {
  if (!Number.isFinite(value)) {
    return 0.5;
  }
  return clamp(1 - Math.abs(value - ideal) / tolerance, 0, 1);
}

function rangeScore(value, min, ideal, max) {
  if (!Number.isFinite(value)) {
    return 0.5;
  }
  if (value <= min || value >= max) {
    return 0;
  }
  if (value === ideal) {
    return 1;
  }
  if (value < ideal) {
    return (value - min) / (ideal - min);
  }
  return (max - value) / (max - ideal);
}

function getFeatureWeight(key) {
  if (key.startsWith("cover")) {
    return 0.5;
  }
  if (key.startsWith("current:")) {
    return 0.82;
  }
  if (key.startsWith("cat1:") || key.startsWith("cat2:")) {
    return 0.6;
  }
  if (key.startsWith("tag:")) {
    return 0.5;
  }
  if (key.startsWith("channel:")) {
    return 0.7;
  }
  if (key.startsWith("collectRatio:") || key.startsWith("commentRatio:") || key.startsWith("shareRatio:")) {
    return 0.46;
  }
  if (key.startsWith("titleToken:")) {
    return 0.44;
  }
  if (key.startsWith("bodyToken:")) {
    return 0.38;
  }
  if (key.startsWith("contentToken:")) {
    return 0.34;
  }
  if (key.startsWith("bodyLength:") || key === "shape:story" || key === "shape:pain" || key === "shape:action") {
    return 0.34;
  }
  return 0.28;
}

function coverSimilarity(a, b) {
  if (!a || !b || !Number.isFinite(a.score) || !Number.isFinite(b.score)) {
    return 0.5;
  }
  const scoreDistance = Math.abs(a.score - b.score) / 100;
  const brightnessDistance = metricDistance(a.brightness, b.brightness);
  const saturationDistance = metricDistance(a.saturation, b.saturation);
  const sharpnessDistance = metricDistance(a.sharpness, b.sharpness);
  return clamp(1 - (0.48 * scoreDistance + 0.18 * brightnessDistance + 0.16 * saturationDistance + 0.18 * sharpnessDistance), 0, 1);
}

function metricDistance(a, b) {
  if (!Number.isFinite(a) || !Number.isFinite(b)) {
    return 0.4;
  }
  return Math.abs(a - b);
}

function coverScoreBin(score) {
  if (score < 45) {
    return "偏弱";
  }
  if (score < 65) {
    return "中等";
  }
  if (score < 80) {
    return "较强";
  }
  return "很强";
}

function metricBin(value, low, high) {
  if (!Number.isFinite(value)) {
    return "未知";
  }
  if (value < low) {
    return "低";
  }
  if (value > high) {
    return "高";
  }
  return "适中";
}

function jaccard(a, b) {
  if (!a.size && !b.size) {
    return 0;
  }
  let intersection = 0;
  a.forEach((item) => {
    if (b.has(item)) {
      intersection += 1;
    }
  });
  const union = new Set([...a, ...b]).size;
  return union ? intersection / union : 0;
}

function sortedNumbers(values) {
  return values.filter(isPositive).sort((a, b) => a - b);
}

function quantile(sorted, q) {
  if (!sorted.length) {
    return null;
  }
  const position = (sorted.length - 1) * q;
  const base = Math.floor(position);
  const rest = position - base;
  if (sorted[base + 1] !== undefined) {
    return sorted[base] + rest * (sorted[base + 1] - sorted[base]);
  }
  return sorted[base];
}

function percentileRank(sorted, value) {
  if (!sorted.length || !Number.isFinite(value)) {
    return 0.5;
  }
  let lower = 0;
  while (lower < sorted.length && sorted[lower] < value) {
    lower += 1;
  }
  return sorted.length === 1 ? 0.5 : lower / (sorted.length - 1);
}

function weightedAverage(values, weights) {
  let weightedSum = 0;
  let weightSum = 0;
  values.forEach((value, index) => {
    if (Number.isFinite(value)) {
      const weight = Number.isFinite(weights[index]) ? weights[index] : 0;
      weightedSum += value * weight;
      weightSum += weight;
    }
  });
  return weightSum ? weightedSum / weightSum : NaN;
}

function smoothedRate(success, count, baseline, prior) {
  return (success + baseline * prior) / (count + prior);
}

function sigmoid(value) {
  return 1 / (1 + Math.exp(-value));
}

function logit(value) {
  const safe = clamp(value, 0.01, 0.99);
  return Math.log(safe / (1 - safe));
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function isPositive(value) {
  return Number.isFinite(value) && value > 0;
}

function roundBudget(value) {
  if (!Number.isFinite(value)) {
    return 50;
  }
  if (value < 50) {
    return Math.round(value / 5) * 5;
  }
  return Math.round(value / 10) * 10;
}

function formatNumber(value) {
  if (!Number.isFinite(value)) {
    return "--";
  }
  return value.toLocaleString("zh-CN", {
    minimumFractionDigits: value < 10 ? 2 : 1,
    maximumFractionDigits: value < 10 ? 2 : 1,
  });
}

function formatInteger(value) {
  if (!Number.isFinite(value)) {
    return "--";
  }
  return Math.round(value).toLocaleString("zh-CN");
}

function formatMoney(value) {
  if (!Number.isFinite(value)) {
    return "--";
  }
  return `${Math.round(value).toLocaleString("zh-CN")} 元`;
}

function formatPercent(value) {
  if (!Number.isFinite(value)) {
    return "--";
  }
  return `${Math.round(value * 100)}%`;
}

function formatMetricPercent(value) {
  if (!Number.isFinite(value)) {
    return "--";
  }
  return `${Math.round(value * 100)}%`;
}

function dayName(day) {
  return ["日", "一", "二", "三", "四", "五", "六"][day] || "";
}

function shortText(value, maxLength) {
  const text = cleanCell(value).replace(/\s+/g, " ");
  if (text.length <= maxLength) {
    return text;
  }
  return `${text.slice(0, maxLength)}...`;
}

function todayInputValue() {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function dateStamp() {
  return todayInputValue().replace(/-/g, "");
}

function downloadText(filename, content) {
  const blob = new Blob([content], { type: "application/json;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}
