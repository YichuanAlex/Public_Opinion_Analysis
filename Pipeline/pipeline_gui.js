"use strict";

const PRESET_KEYWORDS = [
  "滴滴打车",
  "滴滴快车",
  "滴滴司机",
  "滴滴宠物",
  "滴滴安全",
  "滴滴女司机",
  "滴滴专车",
  "滴滴特惠",
  "滴滴巴士",
  "滴滴香卡",
  "滴滴豪华车",
  "滴滴拼车",
  "滴滴车站",
  "滴滴海外打车",
  "滴滴轻享",
  "滴滴出租车",
  "滴滴特快",
  "滴滴 AI 打车",
  "滴滴 AI 叫车",
  "滴滴IP彩蛋车",
];

const PLATFORM_INFO = {
  xhs: {
    name: "小红书",
    shortName: "Rednote",
    mark: "R",
    brand: "Rednote Export",
    origin: "Pipeline/xhs_origin_data.csv",
    table: "Pipeline/xhs_Data_Table_on_Channel_Public_Opinion_Monitoring_2026.csv",
    comments: "Pipeline/xhs_comments.csv",
    workbook: "Hype_Something/2026_Didi_Xiaohongshu_Daily_Word-of-Mouth_Amplification.xlsx",
    placeholder: "可键盘输入，也可粘贴整段小红书分享文案。",
  },
  dy: {
    name: "抖音",
    shortName: "Douyin",
    mark: "D",
    brand: "Douyin Export",
    origin: "Pipeline/dy_origin_data.csv",
    table: "Pipeline/dy_Data_Table_on_Channel_Public_Opinion_Monitoring_2026.csv",
    comments: "Pipeline/dy_comments.csv",
    workbook: "Hype_Something/2026_Didi_Douyin_Daily_Word-of-Mouth_Amplification.xlsx",
    placeholder: "可键盘输入，也可粘贴整段抖音分享文案或视频链接。",
  },
};

let selectedPlatform = "xhs";
const platformBusy = { xhs: false, dy: false };
const platformBusyTask = { xhs: "", dy: "" };
const localTaskActive = { xhs: false, dy: false };

const filterState = {
  sortBy: "综合",
  noteType: "不限",
  publishTime: "不限",
  searchScope: "不限",
  location: "不限",
};

const els = {
  brandMark: document.querySelector("#brandMark"),
  brandTitle: document.querySelector("#brandTitle"),
  platformButtons: document.querySelectorAll(".platform-option"),
  keywordGrid: document.querySelector("#keywordGrid"),
  keywordInput: document.querySelector("#keywordInput"),
  maxNotes: document.querySelector("#maxNotes"),
  scrollRounds: document.querySelector("#scrollRounds"),
  searchButton: document.querySelector("#searchButton"),
  searchAllButton: document.querySelector("#searchAllButton"),
  aiModelSelect: document.querySelector("#aiModelSelect"),
  aiFillLimit: document.querySelector("#aiFillLimit"),
  aiFillConcurrency: document.querySelector("#aiFillConcurrency"),
  aiFillButton: document.querySelector("#aiFillButton"),
  aiFillAllButton: document.querySelector("#aiFillAllButton"),
  backfillOnlyButton: document.querySelector("#backfillOnlyButton"),
  backfillAllButton: document.querySelector("#backfillAllButton"),
  ampStartDate: document.querySelector("#ampStartDate"),
  ampEndDate: document.querySelector("#ampEndDate"),
  ampLimit: document.querySelector("#ampLimit"),
  ampMinDecision: document.querySelector("#ampMinDecision"),
  ampDryRun: document.querySelector("#ampDryRun"),
  ampHypeButton: document.querySelector("#ampHypeButton"),
  ampAiButton: document.querySelector("#ampAiButton"),
  openHypeButton: document.querySelector("#openHypeButton"),
  noteInput: document.querySelector("#noteInput"),
  pasteNoteButton: document.querySelector("#pasteNoteButton"),
  noteButton: document.querySelector("#noteButton"),
  commentButton: document.querySelector("#commentButton"),
  pasteCommentButton: document.querySelector("#pasteCommentButton"),
  cleanCurrentButton: document.querySelector("#cleanCurrentButton"),
  cleanAllButton: document.querySelector("#cleanAllButton"),
  openDirButton: document.querySelector("#openDirButton"),
  statusMessage: document.querySelector("#statusMessage"),
  runPill: document.querySelector("#runPill"),
  logOutput: document.querySelector("#logOutput"),
  filterGroups: document.querySelectorAll(".filter-group"),
  appendPathHint: document.querySelector("#appendPathHint"),
  searchPathHint: document.querySelector("#searchPathHint"),
  ampPathHint: document.querySelector("#ampPathHint"),
};

renderKeywords();
setDefaultAmpDates();
bindEvents();
updatePlatformUi();
refreshBackendBusy();
window.setInterval(refreshBackendBusy, 3000);

function renderKeywords() {
  els.keywordGrid.innerHTML = "";
  PRESET_KEYWORDS.forEach((keyword) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "keyword-chip";
    button.textContent = keyword;
    button.addEventListener("click", () => {
      els.keywordInput.value = keyword;
      markActiveKeyword(keyword);
      const running = busySummary();
      setStatus(
        running
          ? `已选择关键词：${keyword}\n后台仍在运行：${running}`
          : `已选择关键词：${keyword}\n点击「导出当前关键词」开始追加。`,
        running ? "running" : "ready"
      );
      els.keywordInput.focus();
    });
    els.keywordGrid.appendChild(button);
  });
  markActiveKeyword(els.keywordInput.value);
}

function bindEvents() {
  els.platformButtons.forEach((button) => {
    button.addEventListener("click", () => {
      selectedPlatform = button.dataset.platform || "xhs";
      updatePlatformUi();
      setPlatformSwitchStatus();
    });
  });
  els.keywordInput.addEventListener("input", () => markActiveKeyword(els.keywordInput.value.trim()));
  els.keywordInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      runSearch();
    }
  });
  els.searchButton.addEventListener("click", runSearch);
  els.searchAllButton.addEventListener("click", runSearchAll);
  els.aiFillButton.addEventListener("click", () => runAiFill(false));
  els.aiFillAllButton.addEventListener("click", () => runAiFillAll(false));
  els.backfillOnlyButton.addEventListener("click", () => runAiFill(true));
  els.backfillAllButton.addEventListener("click", () => runAiFillAll(true));
  els.ampHypeButton.addEventListener("click", () => runAmplification("hype"));
  els.ampAiButton.addEventListener("click", () => runAmplification("ai"));
  els.openHypeButton.addEventListener("click", openHype);
  els.noteButton.addEventListener("click", runNote);
  els.pasteNoteButton.addEventListener("click", pasteAndRunNote);
  els.commentButton.addEventListener("click", runComments);
  els.pasteCommentButton.addEventListener("click", pasteAndRunComments);
  els.cleanCurrentButton.addEventListener("click", () => runCleanData("current"));
  els.cleanAllButton.addEventListener("click", () => runCleanData("all"));
  els.filterGroups.forEach((group) => {
    const groupName = group.dataset.filterGroup;
    group.querySelectorAll(".filter-option").forEach((button) => {
      button.addEventListener("click", () => {
        filterState[groupName] = button.dataset.value || button.textContent.trim();
        group.querySelectorAll(".filter-option").forEach((item) => {
          item.classList.toggle("is-active", item === button);
        });
      });
    });
  });
  els.openDirButton.addEventListener("click", async () => {
    await fetch("/api/open-dir", { method: "POST" });
  });
}

function platformInfo() {
  return PLATFORM_INFO[selectedPlatform] || PLATFORM_INFO.xhs;
}

function updatePlatformUi() {
  const info = platformInfo();
  els.platformButtons.forEach((button) => {
    button.classList.toggle("is-active", button.dataset.platform === selectedPlatform);
  });
  els.brandMark.textContent = info.mark;
  els.brandTitle.textContent = info.brand;
  els.noteInput.placeholder = info.placeholder;
  els.appendPathHint.innerHTML = `全量字段追加到 <code>${info.origin}</code>，10 个监控字段追加到 <code>${info.table}</code>。评论数据追加到 <code>${info.comments}</code>。`;
  els.searchPathHint.textContent = `使用左侧「最多笔记」控制批量条数，0 表示不限制当前保守滚动可加载结果。${info.name}关键词搜索会使用可见 Chrome 慢速加载；所有结果同样追加到当前平台两张 Pipeline 总表。`;
  els.ampPathHint.innerHTML = `只允许 <code>正负向=正向</code> 的内容进入加热判断；按发布时间筛选当前平台总表，写入 <code>${info.workbook}</code> 对应月份 sheet。`;
  updateBusyUi();
}

function platformName(key) {
  const info = PLATFORM_INFO[key] || PLATFORM_INFO.xhs;
  return info.name;
}

function normalizePlatformKey(value) {
  if (value === "douyin" || value === "抖音") {
    return "dy";
  }
  return value === "dy" ? "dy" : "xhs";
}

function jobPlatforms(payload) {
  const value = payload && payload.platform ? payload.platform : selectedPlatform;
  if (value === "all") {
    return ["xhs", "dy"];
  }
  return [normalizePlatformKey(value)];
}

function busyDescription(key) {
  const task = platformBusyTask[key] ? `：${platformBusyTask[key]}` : "";
  return `${platformName(key)}当前已有任务正在执行${task}。请等待该平台任务完成后再启动新的${platformName(key)}任务。`;
}

function busySummary() {
  return ["xhs", "dy"]
    .filter((key) => platformBusy[key])
    .map((key) => `${platformName(key)}：${platformBusyTask[key] || "运行中"}`)
    .join("；");
}

function setPlatformSwitchStatus() {
  const info = platformInfo();
  if (platformBusy[selectedPlatform]) {
    setStatus(`${info.name}正在执行：${platformBusyTask[selectedPlatform] || "任务运行中"}。`, "running");
    return;
  }
  const running = busySummary();
  if (running) {
    setStatus(`已切换到${info.name}平台，当前平台空闲。\n后台仍在运行：${running}`, "running");
    return;
  }
  setStatus(`已切换到${info.name}平台。`, "ready");
}

function syncPassiveBusyStatus() {
  const running = busySummary();
  const pillText = els.runPill.textContent || "";
  if (running && pillText === "READY") {
    setStatus(`后台任务运行中：${running}`, "running");
    return;
  }
  if (!running && pillText === "RUNNING" && !localTaskActive.xhs && !localTaskActive.dy) {
    setStatus(`当前没有运行中的平台任务。`, "ready");
  }
}

function showAlert(message) {
  if (message) {
    window.alert(message);
  }
}

function makeError(message, alertShown = false) {
  const error = new Error(message);
  error.alertShown = alertShown;
  return error;
}

function alertErrorOnce(error) {
  if (!error || error.alertShown) {
    return;
  }
  const message = error.message || String(error);
  showAlert(message);
  error.alertShown = true;
}

function beginTask(platforms, label) {
  const busyPlatforms = platforms.filter((key) => platformBusy[key]);
  if (busyPlatforms.length) {
    const message = busyPlatforms.map(busyDescription).join("\n");
    setStatus(message, "error");
    appendLog(`ERROR: ${message}`);
    showAlert(message);
    return false;
  }
  platforms.forEach((key) => {
    localTaskActive[key] = true;
    platformBusy[key] = true;
    platformBusyTask[key] = label;
  });
  updateBusyUi();
  return true;
}

function endTask(platforms) {
  platforms.forEach((key) => {
    localTaskActive[key] = false;
    platformBusy[key] = false;
    platformBusyTask[key] = "";
  });
  updateBusyUi();
  refreshBackendBusy();
}

function anyPlatformBusy() {
  return platformBusy.xhs || platformBusy.dy;
}

function updateBusyUi() {
  const currentBusy = Boolean(platformBusy[selectedPlatform]);
  const currentPlatformButtons = [
    els.searchButton,
    els.aiFillButton,
    els.backfillOnlyButton,
    els.ampHypeButton,
    els.ampAiButton,
    els.openHypeButton,
    els.noteButton,
    els.pasteNoteButton,
    els.commentButton,
    els.pasteCommentButton,
    els.cleanCurrentButton,
  ];
  currentPlatformButtons.forEach((button) => {
    if (button) {
      button.disabled = currentBusy;
    }
  });

  const allBusy = anyPlatformBusy();
  [els.searchAllButton, els.aiFillAllButton, els.backfillAllButton, els.cleanAllButton].forEach((button) => {
    if (button) {
      button.disabled = allBusy;
    }
  });

  els.platformButtons.forEach((button) => {
    const key = normalizePlatformKey(button.dataset.platform || "xhs");
    button.classList.toggle("is-busy", Boolean(platformBusy[key]));
    button.title = platformBusy[key] ? busyDescription(key) : "";
    button.disabled = false;
  });
}

async function refreshBackendBusy() {
  try {
    const response = await fetch("/api/status", { cache: "no-store" });
    if (!response.ok) {
      return;
    }
    const data = await response.json();
    const busy = data.busy || {};
    ["xhs", "dy"].forEach((key) => {
      if (localTaskActive[key] && !busy[key]) {
        return;
      }
      platformBusy[key] = Boolean(busy[key]);
      platformBusyTask[key] = busy[key] && busy[key].task ? busy[key].task : "";
    });
    updateBusyUi();
    syncPassiveBusyStatus();
  } catch (_error) {
    // 状态轮询失败不影响当前页面操作，真正冲突仍由后端 409 兜底。
  }
}

function setDefaultAmpDates() {
  const now = new Date();
  const start = new Date(now.getFullYear(), now.getMonth(), 1);
  els.ampStartDate.value = formatDateInput(start);
  els.ampEndDate.value = formatDateInput(now);
}

function formatDateInput(date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function markActiveKeyword(keyword) {
  document.querySelectorAll(".keyword-chip").forEach((button) => {
    button.classList.toggle("is-active", button.textContent === keyword);
  });
}

async function runSearch() {
  const keyword = els.keywordInput.value.trim();
  if (!keyword) {
    setStatus("请输入关键词。", "error");
    return;
  }
  await runJob("search", "/api/search", {
    platform: selectedPlatform,
    keyword,
    maxNotes: Number(els.maxNotes.value || 0),
    scrollRounds: Number(els.scrollRounds.value || 10),
    ...filterState,
  });
}

async function runSearchAll() {
  const keyword = els.keywordInput.value.trim();
  if (!keyword) {
    setStatus("请输入关键词。", "error");
    return;
  }
  await runJob("search-all", "/api/search-all", {
    platform: "all",
    keyword,
    maxNotes: Number(els.maxNotes.value || 0),
    scrollRounds: Number(els.scrollRounds.value || 10),
    ...filterState,
  });
}

async function runAiFill(noAi = false) {
  await runJob(noAi ? "backfill-only" : "ai-fill", "/api/ai-fill", {
    platform: selectedPlatform,
    model: els.aiModelSelect.value,
    limit: Number(els.aiFillLimit.value || 0),
    concurrency: Number(els.aiFillConcurrency.value || 3),
    noAi,
  });
}

async function runAiFillAll(noAi = false) {
  await runJob(noAi ? "backfill-all" : "ai-fill-all", "/api/ai-fill-all", {
    platform: "all",
    model: els.aiModelSelect.value,
    limit: Number(els.aiFillLimit.value || 0),
    concurrency: Number(els.aiFillConcurrency.value || 3),
    noAi,
  });
}

async function runAmplification(method) {
  if (!els.ampStartDate.value || !els.ampEndDate.value) {
    setStatus("请选择口碑加热候选的开始日期和结束日期。", "error");
    return;
  }
  await runJob(method === "ai" ? "amplification-ai" : "amplification-hype", "/api/amplification-export", {
    platform: selectedPlatform,
    method,
    model: els.aiModelSelect.value,
    startDate: els.ampStartDate.value,
    endDate: els.ampEndDate.value,
    limit: Number(els.ampLimit.value || 0),
    minDecision: els.ampMinDecision.value,
    dryRun: els.ampDryRun.checked,
  });
}

async function openHype() {
  const info = platformInfo();
  setStatus(`正在打开 ${info.name} 的 Hype 软件界面...`, "running");
  appendLog(`> ${new Date().toLocaleString()} 打开 ${info.name} Hype 软件界面`);
  try {
    const response = await fetch("/api/open-hype", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ platform: selectedPlatform }),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.error || `HTTP ${response.status}`);
    }
    setStatus(`已尝试打开 Hype 软件界面。\n地址：${data.url}\n目标表：${data.workbook}`, "done");
    appendLog(`Hype目录：${data.hype}\n地址：${data.url}\n目标表：${data.workbook}`);
  } catch (error) {
    setStatus(`打开 Hype 失败：${error.message}`, "error");
    appendLog(`ERROR: ${error.message}`);
  }
}

async function pasteAndRunNote() {
  try {
    const text = await navigator.clipboard.readText();
    els.noteInput.value = text;
    await runNote("clipboard");
  } catch (error) {
    setStatus("读取剪贴板失败，请手动粘贴到链接框。", "error");
    appendLog(String(error && error.message ? error.message : error));
  }
}

async function pasteAndRunComments() {
  try {
    const text = await navigator.clipboard.readText();
    els.noteInput.value = text;
    await runComments("clipboard");
  } catch (error) {
    setStatus("读取剪贴板失败，请手动粘贴到链接框。", "error");
    appendLog(String(error && error.message ? error.message : error));
  }
}

async function runNote(mode = "manual") {
  const text = els.noteInput.value.trim();
  if (!text) {
    setStatus(`请在链接框里粘贴${platformInfo().name}分享文案或详情链接。`, "error");
    return;
  }
  await runJob(mode === "clipboard" ? "clipboard-note" : "note", "/api/note", { platform: selectedPlatform, text });
}

async function runComments(mode = "manual") {
  const text = els.noteInput.value.trim();
  if (!text) {
    setStatus(`请在链接框里粘贴${platformInfo().name}分享文案或详情链接。`, "error");
    return;
  }
  await runJob(mode === "clipboard" ? "clipboard-comments" : "comments", "/api/comments", { platform: selectedPlatform, text });
}

async function runCleanData(scope = "current") {
  const info = platformInfo();
  const target = scope === "all" ? "小红书和抖音两张监控总表" : `${info.name}监控总表`;
  const ok = window.confirm(`确认清洗${target}？\n\n将删除包含“实习 / 新橙海 / 工号 / 入职 / 面试 / 桔厂”的行，并按笔记ID去重，只保留最早出现的记录。\n清洗前会自动备份原表。`);
  if (!ok) {
    return;
  }
  await runJob(scope === "all" ? "clean-all" : "clean-current", "/api/clean-data", {
    platform: selectedPlatform,
    scope,
  });
}

async function runJob(kind, endpoint, payload) {
  if (isAiKind(kind)) {
    return runStreamingJob(kind, isParallelAiKind(kind) ? "/api/ai-fill-all-stream" : "/api/ai-fill-stream", payload);
  }
  const label = getKindLabel(kind);
  const info = platformInfo();
  const platformLabel = isParallelKind(kind) ? "双平台" : info.name;
  const platforms = jobPlatforms(payload);
  if (!beginTask(platforms, label)) {
    return;
  }
  setStatus(`正在执行：${platformLabel} · ${label}...`, "running");
  appendLog(`> ${new Date().toLocaleString()} 开始执行 ${platformLabel} · ${label}`);
  try {
    const response = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      const message = data.error || `HTTP ${response.status}`;
      if (data.alert || response.status === 409) {
        showAlert(message);
        throw makeError(message, true);
      }
      throw makeError(message);
    }
    if (Array.isArray(data.errors) && data.errors.length) {
      showAlert(data.errors.join("\n"));
    }
    const added = Number(data.aiUpdated ?? data.commentRows ?? data.dataRows ?? data.originRows ?? data.count ?? 0);
    if (isParallelKind(kind) && !isCleanKind(kind)) {
      setStatus(
        `${label}完成。\n追加全量 ${data.originRows ?? 0} 行，追加监控 ${data.dataRows ?? 0} 行，AI填写 ${data.aiUpdated ?? 0} 行，失败 ${data.failedAiRows ?? 0} 行。\n${(data.errors || []).length ? `部分错误：${data.errors.join(" | ")}` : "双平台均已完成。"}`,
        "done"
      );
    } else if (isAmplificationKind(kind)) {
      setStatus(
        `${label}完成。\n时间段：${data.startDate} 至 ${data.endDate}\n正向候选 ${data.positiveCandidates ?? 0} 条，跳过非正向 ${data.skippedNonPositive ?? 0} 条。\n筛选入选 ${data.selected ?? 0} 条，写入 ${data.appended ?? 0} 条，Hype兜底 ${data.aiFallbackToHype ?? 0} 条。\n目标表：${data.workbook}`,
        "done"
      );
    } else if (isAiKind(kind)) {
      setStatus(
        `${label}完成。\n扫描 ${data.scannedRows ?? 0} 行，并发 ${data.concurrency ?? 1}，尝试 ${data.attemptedAiRows ?? 0} 行，AI 填写 ${data.aiUpdated ?? 0} 行，本地兜底 ${data.localFallbackUpdated ?? 0} 行，失败 ${data.failedAiRows ?? 0} 行。\n回填后缺失 ${data.missingAiAfter ?? 0} 行。\n监控数据表：${data.table}`,
        "done"
      );
    } else if (isCommentKind(kind)) {
      setStatus(`${label}完成，追加 ${added} 条。\n评论总表：${data.comments}`, "done");
    } else if (isCleanKind(kind)) {
      setStatus(
        `${label}完成。\n清洗前 ${data.beforeRows ?? 0} 行，清洗后 ${data.afterRows ?? 0} 行。\n删除重复 ${data.removedDuplicateRows ?? 0} 行，删除脏数据 ${data.removedDirtyRows ?? 0} 行，补齐ID ${data.filledNoteIds ?? 0} 行。`,
        "done"
      );
    } else {
      const mediaLine = buildMediaStatusLine(data);
      setStatus(
        `${label}完成，追加 ${added} 条。${mediaLine ? `\n${mediaLine}` : ""}\n全量字段总表：${data.origin}\n监控数据表：${data.dataTable}`,
        "done"
      );
    }
    appendLog(buildSuccessLog(label, data));
  } catch (error) {
    alertErrorOnce(error);
    setStatus(`导出失败：${error.message}`, "error");
    appendLog(`ERROR: ${error.message}`);
  } finally {
    endTask(platforms);
  }
}

async function runStreamingJob(kind, endpoint, payload) {
  const label = getKindLabel(kind);
  const info = platformInfo();
  const platformLabel = isParallelAiKind(kind) ? "双平台" : info.name;
  const platforms = jobPlatforms(payload);
  if (!beginTask(platforms, label)) {
    return;
  }
  setStatus(`正在执行：${platformLabel} · ${label}...`, "running");
  appendLog(`> ${new Date().toLocaleString()} 开始执行 ${platformLabel} · ${label}`);
  let finalData = null;
  let streamError = null;
  try {
    const response = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok || !response.body) {
      const text = await response.text();
      let message = text || `HTTP ${response.status}`;
      try {
        const parsed = JSON.parse(text);
        message = parsed.error || message;
      } catch (_error) {
        // 非 JSON 错误直接展示原始文本。
      }
      if (response.status === 409) {
        showAlert(message);
        throw makeError(message, true);
      }
      throw makeError(message);
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) {
        break;
      }
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";
      for (const line of lines) {
        if (!line.trim()) {
          continue;
        }
        const event = JSON.parse(line);
        if (event.type === "progress") {
          handleAiProgress(event.payload, label);
        } else if (event.type === "result") {
          finalData = event.payload;
        } else if (event.type === "error") {
          streamError = makeError(event.error || "AI填写失败");
        } else if (event.type === "log") {
          appendLog(event.message || "");
        }
      }
      if (streamError) {
        throw streamError;
      }
    }
    if (buffer.trim()) {
      const event = JSON.parse(buffer);
      if (event.type === "result") {
        finalData = event.payload;
      } else if (event.type === "error") {
        throw makeError(event.error || "AI填写失败");
      }
    }
    if (!finalData) {
      throw makeError("AI填写进程没有返回最终结果");
    }
    if (Array.isArray(finalData.errors) && finalData.errors.length) {
      showAlert(finalData.errors.join("\n"));
    }
    const errorLine = Array.isArray(finalData.errors) && finalData.errors.length ? `\n错误：${finalData.errors.join(" | ")}` : "";
    setStatus(
      `${label}完成。\n扫描 ${finalData.scannedRows ?? 0} 行，并发 ${finalData.concurrency ?? 1}，尝试 ${finalData.attemptedAiRows ?? 0} 行，AI 填写 ${finalData.aiUpdated ?? 0} 行，本地兜底 ${finalData.localFallbackUpdated ?? 0} 行，失败 ${finalData.failedAiRows ?? 0} 行。\n回填后缺失 ${finalData.missingAiAfter ?? 0} 行。\n监控数据表：${finalData.table}${errorLine}`,
      finalData.errors && finalData.errors.length && !finalData.partialOk ? "error" : "done"
    );
    appendLog(buildSuccessLog(label, { ...finalData, stdout: "" }));
  } catch (error) {
    alertErrorOnce(error);
    setStatus(`导出失败：${error.message}`, "error");
    appendLog(`ERROR: ${error.message}`);
  } finally {
    endTask(platforms);
  }
}

function handleAiProgress(payload, label) {
  const event = payload.event;
  const prefix = payload.platformName ? `【${payload.platformName}】` : "";
  if (event === "start") {
    appendLog(`${prefix}AI准备：扫描 ${payload.rows ?? 0} 行，AI字段缺失 ${payload.missingAiBefore ?? 0} 行，确定性回填 ${payload.deterministicChanged ?? 0} 行。`);
    setStatus(`${label}运行中。\n${prefix}AI字段缺失 ${payload.missingAiBefore ?? 0} 行，正在准备模型填写。`, "running");
    return;
  }
  if (event === "ai_scan") {
    appendLog(`${prefix}AI待处理：${payload.attemptedAiRows ?? 0} 行；并发 ${payload.concurrency ?? 1}；重试轮数 ${payload.retryRounds ?? 1}；模型 ${payload.modelChoice || ""}。`);
    return;
  }
  if (event === "round_wait") {
    appendLog(`${prefix}等待后重试：第 ${payload.round} 轮，剩余 ${payload.remaining ?? 0} 行，等待 ${payload.seconds ?? 0} 秒。`);
    return;
  }
  if (event === "round_start") {
    appendLog(`${prefix}开始第 ${payload.round} 轮：剩余 ${payload.remaining ?? 0} 行，worker=${payload.workers ?? 1}，单行重试=${payload.retries ?? 1}。`);
    return;
  }
  if (event === "row_filled") {
    const fields = payload.fields || {};
    const lines = [
      `${prefix}已写回第 ${payload.row} 行（${payload.method}）：${payload.title || "无标题"}`,
      payload.noteId ? `笔记ID：${payload.noteId}` : "",
      `概括：${fields["概括"] || ""}`,
      `内容类型：${fields["内容类型"] || ""}；正负向：${fields["正负向"] || ""}；业务线：${fields["业务线"] || ""}`,
      `渠道类型：${fields["渠道类型"] || ""}；具体产品/场景：${fields["具体产品/场景"] || ""}`,
      `当前累计：AI ${payload.aiUpdated ?? 0} 行，本地兜底 ${payload.localFallbackUpdated ?? 0} 行，剩余缺失 ${payload.missingAiRows ?? 0} 行。`,
    ].filter(Boolean);
    appendLog(lines.join("\n"));
    setStatus(
      `${label}运行中。\n${prefix}已写回：AI ${payload.aiUpdated ?? 0} 行，本地兜底 ${payload.localFallbackUpdated ?? 0} 行。\n剩余缺失：${payload.missingAiRows ?? 0} 行。`,
      "running"
    );
    return;
  }
  if (event === "row_failed_round") {
    appendLog(`${prefix}本轮失败：第 ${payload.row} 行，第 ${payload.round} 轮。${payload.title || ""}\n原因：${payload.error || ""}`);
    return;
  }
  if (event === "final_errors") {
    appendLog(`${prefix}最终仍失败 ${payload.failedAiRows ?? 0} 行：${(payload.errors || []).join(" | ")}`);
    return;
  }
  if (event === "done") {
    appendLog(`${prefix}AI填写完成：AI ${payload.aiUpdated ?? 0} 行，本地兜底 ${payload.localFallbackUpdated ?? 0} 行，最终缺失 ${payload.missingAiAfter ?? 0} 行。`);
  }
}

function getKindLabel(kind) {
  if (kind === "search") {
    return "关键词批量数目查询";
  }
  if (kind === "search-all") {
    return "双平台并行关键词查询";
  }
  if (kind === "ai-fill") {
    return "AI填写总表";
  }
  if (kind === "ai-fill-all") {
    return "双平台并行AI填写";
  }
  if (kind === "backfill-only") {
    return "只回填ID/互动量";
  }
  if (kind === "backfill-all") {
    return "双平台并行只回填";
  }
  if (kind === "amplification-hype") {
    return "Hype模型写入Excel";
  }
  if (kind === "amplification-ai") {
    return "AI判断写入Excel";
  }
  if (kind === "clipboard-note") {
    return "粘贴板帖子查询";
  }
  if (kind === "comments") {
    return "文本框评论爬取";
  }
  if (kind === "clipboard-comments") {
    return "粘贴板评论爬取";
  }
  if (kind === "clean-current") {
    return "当前平台去重/脏数据清洗";
  }
  if (kind === "clean-all") {
    return "双平台去重/脏数据清洗";
  }
  return "单帖子单查询";
}

function isCommentKind(kind) {
  return kind === "comments" || kind === "clipboard-comments";
}

function isCleanKind(kind) {
  return kind === "clean-current" || kind === "clean-all";
}

function isAiKind(kind) {
  return kind === "ai-fill" || kind === "backfill-only" || kind === "ai-fill-all" || kind === "backfill-all";
}

function isParallelAiKind(kind) {
  return kind === "ai-fill-all" || kind === "backfill-all";
}

function isAmplificationKind(kind) {
  return kind === "amplification-hype" || kind === "amplification-ai";
}

function isParallelKind(kind) {
  return kind === "search-all" || kind === "ai-fill-all" || kind === "backfill-all" || kind === "clean-all";
}

function buildSuccessLog(label, data) {
  const lines = [
    data.stdout ? data.stdout.trim() : "",
    `完成：${label}`,
    data.originRows !== undefined ? `追加全量字段行数：${data.originRows}` : "",
    data.dataRows !== undefined ? `追加监控字段行数：${data.dataRows}` : "",
    data.commentRows !== undefined ? `追加评论行数：${data.commentRows}` : "",
    data.beforeRows !== undefined ? `清洗前行数：${data.beforeRows}` : "",
    data.afterRows !== undefined ? `清洗后行数：${data.afterRows}` : "",
    data.removedDuplicateRows !== undefined ? `删除重复行数：${data.removedDuplicateRows}` : "",
    data.removedDirtyRows !== undefined ? `删除脏数据行数：${data.removedDirtyRows}` : "",
    data.filledNoteIds !== undefined ? `补齐笔记ID行数：${data.filledNoteIds}` : "",
    Array.isArray(data.tables) && data.tables.length ? `清洗表格：${data.tables.join("，")}` : "",
    Array.isArray(data.backups) && data.backups.length ? `备份文件：${data.backups.join("，")}` : "",
    Array.isArray(data.results) && data.results.length ? `平台明细：${data.results.map((item) => `${item.platformName || item.platform}: 全量${item.originRows ?? 0}, 监控${item.dataRows ?? 0}, 评论${item.commentRows ?? 0}, AI${item.aiUpdated ?? 0}, 清洗${item.beforeRows ?? "-"}->${item.afterRows ?? "-"}`).join(" | ")}` : "",
    Array.isArray(data.results) && data.results.some((item) => item.writeDetails?.length)
      ? `双平台全量字段写入明细：\n${data.results.flatMap((item) => (item.writeDetails || []).map((line) => `【${item.platformName || item.platform}】${line}`)).join("\n")}`
      : "",
    Array.isArray(data.results) && data.results.some((item) => item.dataTableWriteDetails?.length)
      ? `双平台监控字段写入明细：\n${data.results.flatMap((item) => (item.dataTableWriteDetails || []).map((line) => `【${item.platformName || item.platform}】${line}`)).join("\n")}`
      : "",
    Array.isArray(data.results) && data.results.some((item) => item.commentWriteDetails?.length)
      ? `双平台评论字段写入明细：\n${data.results.flatMap((item) => (item.commentWriteDetails || []).map((line) => `【${item.platformName || item.platform}】${line}`)).join("\n")}`
      : "",
    Array.isArray(data.results) && data.results.some((item) => item.excelWriteDetails?.length)
      ? `双平台Excel字段写入明细：\n${data.results.flatMap((item) => (item.excelWriteDetails || []).map((line) => `【${item.platformName || item.platform}】${line}`)).join("\n")}`
      : "",
    Array.isArray(data.results) && data.results.some((item) => item.dirtySamples?.length) ? `脏数据样例：${data.results.flatMap((item) => item.dirtySamples || []).join(" | ")}` : "",
    Array.isArray(data.results) && data.results.some((item) => item.duplicateSamples?.length) ? `重复样例：${data.results.flatMap((item) => item.duplicateSamples || []).join(" | ")}` : "",
    data.origin ? `全量字段总表：${data.origin}` : "",
    data.sourceFieldCount !== undefined ? `本次源文件字段数：${data.sourceFieldCount}` : "",
    Array.isArray(data.newFields) && data.newFields.length ? `本次新增全量字段：${data.newFields.join("，")}` : "",
    Array.isArray(data.writeDetails) && data.writeDetails.length ? `全量字段写入明细：\n${data.writeDetails.join("\n")}` : "",
    data.writeDetailsOmitted ? `全量字段写入明细还有 ${data.writeDetailsOmitted} 行未展开。` : "",
    data.dataTable ? `监控数据表：${data.dataTable}` : "",
    Array.isArray(data.dataTableWriteDetails) && data.dataTableWriteDetails.length ? `监控字段写入明细：\n${data.dataTableWriteDetails.join("\n")}` : "",
    data.dataTableWriteDetailsOmitted ? `监控字段写入明细还有 ${data.dataTableWriteDetailsOmitted} 行未展开。` : "",
    data.comments ? `评论总表：${data.comments}` : "",
    Array.isArray(data.commentWriteDetails) && data.commentWriteDetails.length ? `评论字段写入明细：\n${data.commentWriteDetails.join("\n")}` : "",
    data.commentWriteDetailsOmitted ? `评论字段写入明细还有 ${data.commentWriteDetailsOmitted} 行未展开。` : "",
    data.table ? `AI填充表：${data.table}` : "",
    data.deterministicChanged !== undefined ? `确定性回填行数：${data.deterministicChanged}` : "",
    data.aiUpdated !== undefined ? `AI填写行数：${data.aiUpdated}` : "",
    data.localFallbackUpdated !== undefined ? `本地规则兜底行数：${data.localFallbackUpdated}` : "",
    data.attemptedAiRows !== undefined ? `AI尝试行数：${data.attemptedAiRows}` : "",
    data.failedAiRows !== undefined ? `AI最终失败行数：${data.failedAiRows}` : "",
    data.concurrency !== undefined ? `并发数：${data.concurrency}` : "",
    data.retryRounds !== undefined ? `失败重试轮数：${data.retryRounds}` : "",
    data.missingAiBefore !== undefined ? `AI字段回填前缺失行：${data.missingAiBefore}` : "",
    data.missingAiAfter !== undefined ? `AI字段回填后缺失行：${data.missingAiAfter}` : "",
    data.model ? `模型：${data.model}` : "",
    data.mediaDetectedRows !== undefined ? `媒体增强行数：${data.mediaDetectedRows}` : "",
    data.mediaImageCount !== undefined ? `识别图片数：${data.mediaImageCount}` : "",
    data.mediaTranscriptSourceCount !== undefined ? `识别音/视频数：${data.mediaTranscriptSourceCount}` : "",
    data.mediaOcrRows !== undefined ? `OCR写入行数：${data.mediaOcrRows}` : "",
    data.mediaTranscriptRows !== undefined ? `语音转文字写入行数：${data.mediaTranscriptRows}` : "",
    data.mediaErrorCount !== undefined ? `媒体增强错误数：${data.mediaErrorCount}` : "",
    Array.isArray(data.mediaErrors) && data.mediaErrors.length ? `媒体增强错误样例：${data.mediaErrors.join(" | ")}` : "",
    data.workbook ? `加热Excel：${data.workbook}` : "",
    data.totalInRange !== undefined ? `时间段内候选：${data.totalInRange}` : "",
    data.positiveCandidates !== undefined ? `正向候选：${data.positiveCandidates}` : "",
    data.skippedNonPositive !== undefined ? `跳过非正向：${data.skippedNonPositive}` : "",
    data.judged !== undefined ? `已判断：${data.judged}` : "",
    data.aiFallbackToHype !== undefined ? `AI失败后Hype兜底：${data.aiFallbackToHype}` : "",
    data.selected !== undefined ? `入选候选：${data.selected}` : "",
    data.wouldAppend !== undefined ? `预计写入：${data.wouldAppend}` : "",
    data.appended !== undefined ? `实际写入：${data.appended}` : "",
    data.skippedExisting !== undefined ? `跳过已存在：${data.skippedExisting}` : "",
    data.sheets ? `写入sheet：${Object.entries(data.sheets).map(([name, count]) => `${name}=${count}`).join("，")}` : "",
    Array.isArray(data.excelWriteDetails) && data.excelWriteDetails.length ? `Excel字段写入明细：\n${data.excelWriteDetails.join("\n")}` : "",
    data.excelWriteDetailsOmitted ? `Excel字段写入明细还有 ${data.excelWriteDetailsOmitted} 行未展开。` : "",
    Array.isArray(data.preview) && data.preview.length ? `预览：${data.preview.map((item) => `${item.发布时间} ${item.标题}【${item.判断}/${item.值得分}】`).join(" | ")}` : "",
    Array.isArray(data.errors) && data.errors.length ? `错误样例：${data.errors.join(" | ")}` : "",
    data.tempOrigin ? `临时全量文件：${data.tempOrigin}` : "",
    data.tempSummary ? `临时10字段文件：${data.tempSummary}` : "",
    data.tempComments ? `临时评论文件：${data.tempComments}` : "",
  ];
  return lines.filter(Boolean).join("\n");
}

function buildMediaStatusLine(data) {
  if (data.mediaDetectedRows === undefined && data.mediaImageCount === undefined && data.mediaTranscriptSourceCount === undefined) {
    return "";
  }
  return `媒体增强：图片 ${data.mediaImageCount ?? 0} 个，音/视频 ${data.mediaTranscriptSourceCount ?? 0} 个，OCR写入 ${data.mediaOcrRows ?? 0} 行，语音写入 ${data.mediaTranscriptRows ?? 0} 行，错误 ${data.mediaErrorCount ?? 0} 个。`;
}

function setStatus(message, state) {
  els.statusMessage.textContent = message;
  const pill = els.runPill;
  pill.className = "trained-pill";
  if (state === "running") {
    pill.textContent = "RUNNING";
  } else if (state === "error") {
    pill.textContent = "ERROR";
    pill.classList.add("error");
  } else {
    pill.textContent = state === "done" ? "DONE" : "READY";
    pill.classList.add("ready");
  }
}

function appendLog(message) {
  const current = els.logOutput.textContent === "等待操作。" ? "" : els.logOutput.textContent + "\n";
  els.logOutput.textContent = current + message.trim();
  els.logOutput.scrollTop = els.logOutput.scrollHeight;
}
