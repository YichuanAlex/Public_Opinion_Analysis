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
    origin: "Pipeline/origin_data.csv",
    table: "Pipeline/Data_Table_on_Channel_Public_Opinion_Monitoring_2026.csv",
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
  aiModelSelect: document.querySelector("#aiModelSelect"),
  aiFillLimit: document.querySelector("#aiFillLimit"),
  aiFillConcurrency: document.querySelector("#aiFillConcurrency"),
  aiFillButton: document.querySelector("#aiFillButton"),
  backfillOnlyButton: document.querySelector("#backfillOnlyButton"),
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
      setStatus(`已选择关键词：${keyword}\n点击「导出当前关键词」开始追加。`, "ready");
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
      setStatus(`已切换到${platformInfo().name}平台。`, "ready");
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
  els.aiFillButton.addEventListener("click", () => runAiFill(false));
  els.backfillOnlyButton.addEventListener("click", () => runAiFill(true));
  els.ampHypeButton.addEventListener("click", () => runAmplification("hype"));
  els.ampAiButton.addEventListener("click", () => runAmplification("ai"));
  els.openHypeButton.addEventListener("click", openHype);
  els.noteButton.addEventListener("click", runNote);
  els.pasteNoteButton.addEventListener("click", pasteAndRunNote);
  els.commentButton.addEventListener("click", runComments);
  els.pasteCommentButton.addEventListener("click", pasteAndRunComments);
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

async function runAiFill(noAi = false) {
  await runJob(noAi ? "backfill-only" : "ai-fill", "/api/ai-fill", {
    platform: selectedPlatform,
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
  setBusy(true);
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
  } finally {
    setBusy(false);
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

async function runJob(kind, endpoint, payload) {
  const label = getKindLabel(kind);
  const info = platformInfo();
  setBusy(true);
  setStatus(`正在执行：${info.name} · ${label}...`, "running");
  appendLog(`> ${new Date().toLocaleString()} 开始执行 ${info.name} · ${label}`);
  try {
    const response = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.error || `HTTP ${response.status}`);
    }
    const added = Number(data.aiUpdated ?? data.commentRows ?? data.dataRows ?? data.originRows ?? data.count ?? 0);
    if (isAmplificationKind(kind)) {
      setStatus(
        `${label}完成。\n时间段：${data.startDate} 至 ${data.endDate}\n正向候选 ${data.positiveCandidates ?? 0} 条，跳过非正向 ${data.skippedNonPositive ?? 0} 条。\n筛选入选 ${data.selected ?? 0} 条，写入 ${data.appended ?? 0} 条。\n目标表：${data.workbook}`,
        "done"
      );
    } else if (isAiKind(kind)) {
      setStatus(
        `${label}完成。\n扫描 ${data.scannedRows ?? 0} 行，并发 ${data.concurrency ?? 1}，尝试 ${data.attemptedAiRows ?? 0} 行，AI 填写 ${data.aiUpdated ?? 0} 行，失败 ${data.failedAiRows ?? 0} 行。\n回填后缺失 ${data.missingAiAfter ?? 0} 行。\n监控数据表：${data.table}`,
        "done"
      );
    } else if (isCommentKind(kind)) {
      setStatus(`${label}完成，追加 ${added} 条。\n评论总表：${data.comments}`, "done");
    } else {
      setStatus(
        `${label}完成，追加 ${added} 条。\n全量字段总表：${data.origin}\n监控数据表：${data.dataTable}`,
        "done"
      );
    }
    appendLog(buildSuccessLog(label, data));
  } catch (error) {
    setStatus(`导出失败：${error.message}`, "error");
    appendLog(`ERROR: ${error.message}`);
  } finally {
    setBusy(false);
  }
}

function getKindLabel(kind) {
  if (kind === "search") {
    return "关键词批量数目查询";
  }
  if (kind === "ai-fill") {
    return "AI填写总表";
  }
  if (kind === "backfill-only") {
    return "只回填ID/互动量";
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
  return "单帖子单查询";
}

function isCommentKind(kind) {
  return kind === "comments" || kind === "clipboard-comments";
}

function isAiKind(kind) {
  return kind === "ai-fill" || kind === "backfill-only";
}

function isAmplificationKind(kind) {
  return kind === "amplification-hype" || kind === "amplification-ai";
}

function buildSuccessLog(label, data) {
  const lines = [
    data.stdout ? data.stdout.trim() : "",
    `完成：${label}`,
    data.originRows !== undefined ? `追加全量字段行数：${data.originRows}` : "",
    data.dataRows !== undefined ? `追加监控字段行数：${data.dataRows}` : "",
    data.commentRows !== undefined ? `追加评论行数：${data.commentRows}` : "",
    data.origin ? `全量字段总表：${data.origin}` : "",
    data.dataTable ? `监控数据表：${data.dataTable}` : "",
    data.comments ? `评论总表：${data.comments}` : "",
    data.table ? `AI填充表：${data.table}` : "",
    data.deterministicChanged !== undefined ? `确定性回填行数：${data.deterministicChanged}` : "",
    data.aiUpdated !== undefined ? `AI填写行数：${data.aiUpdated}` : "",
    data.attemptedAiRows !== undefined ? `AI尝试行数：${data.attemptedAiRows}` : "",
    data.failedAiRows !== undefined ? `AI最终失败行数：${data.failedAiRows}` : "",
    data.concurrency !== undefined ? `并发数：${data.concurrency}` : "",
    data.retryRounds !== undefined ? `失败重试轮数：${data.retryRounds}` : "",
    data.missingAiBefore !== undefined ? `AI字段回填前缺失行：${data.missingAiBefore}` : "",
    data.missingAiAfter !== undefined ? `AI字段回填后缺失行：${data.missingAiAfter}` : "",
    data.model ? `模型：${data.model}` : "",
    data.workbook ? `加热Excel：${data.workbook}` : "",
    data.totalInRange !== undefined ? `时间段内候选：${data.totalInRange}` : "",
    data.positiveCandidates !== undefined ? `正向候选：${data.positiveCandidates}` : "",
    data.skippedNonPositive !== undefined ? `跳过非正向：${data.skippedNonPositive}` : "",
    data.judged !== undefined ? `已判断：${data.judged}` : "",
    data.selected !== undefined ? `入选候选：${data.selected}` : "",
    data.wouldAppend !== undefined ? `预计写入：${data.wouldAppend}` : "",
    data.appended !== undefined ? `实际写入：${data.appended}` : "",
    data.skippedExisting !== undefined ? `跳过已存在：${data.skippedExisting}` : "",
    data.sheets ? `写入sheet：${Object.entries(data.sheets).map(([name, count]) => `${name}=${count}`).join("，")}` : "",
    Array.isArray(data.preview) && data.preview.length ? `预览：${data.preview.map((item) => `${item.发布时间} ${item.标题}【${item.判断}/${item.值得分}】`).join(" | ")}` : "",
    Array.isArray(data.errors) && data.errors.length ? `错误样例：${data.errors.join(" | ")}` : "",
    data.tempOrigin ? `临时全量文件：${data.tempOrigin}` : "",
    data.tempSummary ? `临时10字段文件：${data.tempSummary}` : "",
    data.tempComments ? `临时评论文件：${data.tempComments}` : "",
  ];
  return lines.filter(Boolean).join("\n");
}

function setBusy(busy) {
  [els.searchButton, els.aiFillButton, els.backfillOnlyButton, els.ampHypeButton, els.ampAiButton, els.openHypeButton, els.noteButton, els.pasteNoteButton, els.commentButton, els.pasteCommentButton].forEach((button) => {
    button.disabled = busy;
  });
  els.platformButtons.forEach((button) => {
    button.disabled = busy;
  });
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
