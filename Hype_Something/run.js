"use strict";
// 统一 CLI：支持本地模型训练和 LLM 判别两种方法
// 用法:
//   node run.js --method local --train training_data_cleaned.csv --test training_data_cleaned.csv [--out validation_results.csv]
//   node run.js --method llm  --train training_data_cleaned.csv --test training_data_cleaned.csv [--out llm_validation_results.csv]
//
// 本地模型超参数:
//   --strictness balanced|strict|growth
//   --cpe-mode auto|custom
//   --custom-cpe 0
//   --min-interactions 0
//   --auto-tune false          (自动搜索最佳 strictness × minInteractions)
//   --k-folds 0                (>1 时启用交叉验证)
//
// LLM 超参数:
//   --api-key <key>            (默认从环境变量 OPENAI_API_KEY 读取，否则用内置默认值)
//   --model <name>             (支持: All Named Models, All Internal Models, kimi-k2.5-external, minimax-m2.5-external, glm-5.1-external, glm-5-external, glm-5-internal, glm-5.1-internal)
//   --base-url <url>           (默认 https://llm-proxy.intra.xiaojukeji.com)
//   --threshold 1.4
//   --delay 1500
//   --temperature 0.2
//   --max-retries 2

const fs = require("fs");
const vm = require("vm");
const path = require("path");
const https = require("https");
const http = require("http");
const { URL } = require("url");

// ============ CLI 参数解析 ============
function arg(flag, def) {
  const i = process.argv.indexOf(flag);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : def;
}

const METHOD = arg("--method", "local");
const TRAIN = arg("--train", "training_data_cleaned.csv");
const TEST = arg("--test", "training_data_cleaned.csv");
const OUT = arg("--out", METHOD === "local" ? "validation_results.csv" : "llm_validation_results.csv");

// 本地模型超参数
const STRICTNESS = arg("--strictness", "balanced");
const CPE_MODE = arg("--cpe-mode", "auto");
const CUSTOM_CPE = Number(arg("--custom-cpe", "0"));
const MIN_INTERACTIONS = Number(arg("--min-interactions", "0"));
const AUTO_TUNE = arg("--auto-tune", "false") === "true";
const K_FOLDS = Number(arg("--k-folds", "0"));

// LLM 超参数
const API_KEY = arg("--api-key", process.env.OPENAI_API_KEY || "sk-e_n5TZagIOiaopqztzd1TQ");
const MODEL_ARG = arg("--model", "kimi-k2.5-external");
const BASE_URL = arg("--base-url", process.env.OPENAI_BASE_URL || "https://llm-proxy.intra.xiaojukeji.com");
const THRESHOLD = Number(arg("--threshold", "1.4"));
const DELAY = Number(arg("--delay", "1500"));
const TEMPERATURE = Number(arg("--temperature", "0.2"));
const MAX_RETRIES = Number(arg("--max-retries", "2"));
const SYSTEM_PROMPT = arg("--system-prompt", "");

// 模型分组
const MODEL_GROUPS = {
  "All Named Models": ["kimi-k2.5-external", "minimax-m2.5-external", "glm-5.1-external", "glm-5-external"],
  "All Internal Models": ["glm-5-internal", "glm-5.1-internal"],
};

const MODELS = MODEL_GROUPS[MODEL_ARG] || [MODEL_ARG];

// ============ 加载 app.js API ============
function loadAppApi() {
  const noop = function () {};
  const noopEl = {
    value: "",
    textContent: "",
    innerHTML: "",
    classList: { toggle: noop, add: noop, remove: noop, contains: () => false },
    addEventListener: noop,
    appendChild: noop,
    removeChild: noop,
    setAttribute: noop,
    remove: noop,
    click: noop,
    style: {},
  };
  const sandbox = {
    console,
    Math,
    Date,
    JSON,
    Number,
    String,
    Array,
    Object,
    Map,
    Set,
    isNaN,
    parseFloat,
    parseInt,
    isFinite,
    Proxy,
    document: {
      querySelector: () => noopEl,
      querySelectorAll: () => [],
      addEventListener: () => {},
      createElement: () => noopEl,
      body: { appendChild() {}, removeChild() {} },
    },
    window: {},
    localStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} },
    navigator: { clipboard: { writeText: () => {} } },
    fetch: () => Promise.reject(new Error("no fetch in batch mode")),
    URL: { createObjectURL: () => "", revokeObjectURL: () => {} },
    Blob: function () {},
    setTimeout: () => {},
  };
  sandbox.window = sandbox;
  sandbox.globalThis = sandbox;
  vm.createContext(sandbox);

  const appSrc = fs.readFileSync(path.join(__dirname, "app.js"), "utf8");
  const exportTail = `
;globalThis.__api = {
  parseHistoryTable,
  trainModel,
  predict,
  calculateCpe,
  parseNumber,
  getContentShape,
  tokenizeText,
  uniqueTokens,
};`;
  vm.runInContext(appSrc + exportTail, sandbox, { filename: "app.js" });
  return sandbox.__api;
}

// ============ 工具函数 ============
function readCsvText(file) {
  const buf = fs.readFileSync(file);
  return buf.toString("utf8").replace(/^\uFEFF/, "");
}

function csvCell(v) {
  if (v == null) return "";
  const s = String(v);
  return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
}

function corr(a, b) {
  const m = a.length;
  if (m < 2) return NaN;
  const ma = a.reduce((x, y) => x + y, 0) / m;
  const mb = b.reduce((x, y) => x + y, 0) / m;
  let num = 0,
    da = 0,
    db = 0;
  for (let i = 0; i < m; i++) {
    num += (a[i] - ma) * (b[i] - mb);
    da += (a[i] - ma) ** 2;
    db += (b[i] - mb) ** 2;
  }
  return da && db ? num / Math.sqrt(da * db) : NaN;
}

function rmse(pairs) {
  if (!pairs.length) return 0;
  return Math.sqrt(pairs.reduce((s, p) => s + (p.pred - p.real) ** 2, 0) / pairs.length);
}

function r2(pairs) {
  if (!pairs.length) return NaN;
  const real = pairs.map((p) => p.real);
  const meanReal = real.reduce((a, b) => a + b, 0) / real.length;
  const ssTot = real.reduce((s, v) => s + (v - meanReal) ** 2, 0);
  const ssRes = pairs.reduce((s, p) => s + (p.real - p.pred) ** 2, 0);
  return ssTot ? 1 - ssRes / ssTot : NaN;
}

function median(arr) {
  const s = [...arr].filter(Number.isFinite).sort((a, b) => a - b);
  if (!s.length) return null;
  const m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

// ============ 本地模型核心 ============
function evaluateModel(api, trainText, testText, settings) {
  const trainParsed = api.parseHistoryTable(trainText);
  const model = api.trainModel(trainParsed, settings);
  const testParsed = api.parseHistoryTable(testText);
  const thr = model.cpeThreshold;
  const pairs = [];
  const rows = [];

  testParsed.records.forEach((rec) => {
    const input = {
      title: rec.title,
      body: rec.body,
      preInteractions: rec.preInteractions,
      interactionParts: rec.interactionParts || {},
      cover: rec.cover || null,
      channel: rec.channel,
      category1: rec.category1,
      category2: rec.category2,
      tags: rec.tags,
    };
    const p = api.predict(input, model);
    const predCpe = p.predictedCpe;
    const realCpe = rec.cpe;
    const valid = Number.isFinite(realCpe) && realCpe > 0 && Number.isFinite(predCpe) && predCpe > 0;
    let err = null,
      absErr = null,
      errRate = null;
    if (valid) {
      err = predCpe - realCpe;
      absErr = Math.abs(err);
      errRate = absErr / realCpe;
      pairs.push({ pred: predCpe, real: realCpe });
    }
    rows.push({
      noteId: rec.noteId,
      title: rec.title,
      link: rec.link,
      pre: rec.preInteractions,
      predCpe: valid ? predCpe.toFixed(2) : "",
      realCpe: Number.isFinite(realCpe) && realCpe > 0 ? realCpe.toFixed(2) : "无效",
      err: valid ? err.toFixed(2) : "",
      absErr: valid ? absErr.toFixed(2) : "",
      errRate: valid ? (errRate * 100).toFixed(1) + "%" : "—",
      decision: p.decision.title,
      probability: (p.probability * 100).toFixed(0),
      confidence: p.confidence,
    });
  });

  const n = pairs.length;
  const mae = n ? pairs.reduce((s, p) => s + Math.abs(p.pred - p.real), 0) / n : 0;
  const mape = n ? pairs.reduce((s, p) => s + Math.abs(p.pred - p.real) / p.real, 0) / n : 0;
  const rmseVal = rmse(pairs);
  const rVal = corr(
    pairs.map((p) => p.pred),
    pairs.map((p) => p.real)
  );
  const r2Val = r2(pairs);
  const sortedAbs = pairs.map((p) => Math.abs(p.pred - p.real)).sort((a, b) => a - b);
  const medAE = n ? (n % 2 ? sortedAbs[(n - 1) / 2] : (sortedAbs[n / 2 - 1] + sortedAbs[n / 2]) / 2) : 0;
  let dirHit = 0;
  pairs.forEach((p) => {
    if ((p.pred <= thr) === (p.real <= thr)) dirHit++;
  });
  const dirRate = n ? dirHit / n : 0;

  return {
    model,
    rows,
    pairs,
    n,
    mae,
    mape,
    rmse: rmseVal,
    r: rVal,
    r2: r2Val,
    medAE,
    dirRate,
    thr,
    testCount: testParsed.records.length,
  };
}

function writeValidationCsv(outPath, result, extraLines = []) {
  const header = ["笔记ID", "标题", "链接", "投前互动量", "模型预测CPE", "真实综合CPE", "误差(预测−真实)", "绝对误差", "误差率", "决策", "值得分", "置信度"];
  const lines = [header.map(csvCell).join(",")];
  result.rows.forEach((r) => {
    lines.push(
      [r.noteId, r.title, r.link, r.pre, r.predCpe, r.realCpe, r.err, r.absErr, r.errRate, r.decision, r.probability, r.confidence]
        .map(csvCell)
        .join(",")
    );
  });
  lines.push("");
  lines.push("==== 汇总 (预测CPE vs 真实CPE) ====");
  lines.push(`验证集总条数,${result.testCount}`);
  lines.push(`有效条数(真实CPE>0),${result.n}`);
  lines.push(`剔除条数,${result.testCount - result.n}`);
  lines.push(`CPE口径阈值(优秀线),${Number.isFinite(result.thr) ? result.thr.toFixed(2) : "--"}`);
  lines.push(`MAE 平均绝对误差,${result.mae.toFixed(2)}`);
  lines.push(`RMSE 均方根误差,${result.rmse.toFixed(2)}`);
  lines.push(`MAPE 平均绝对百分比误差,${(result.mape * 100).toFixed(1)}%`);
  lines.push(`中位绝对误差,${result.medAE.toFixed(2)}`);
  lines.push(`相关系数 r,${Number.isFinite(result.r) ? result.r.toFixed(3) : "--"}`);
  lines.push(`决定系数 R²,${Number.isFinite(result.r2) ? result.r2.toFixed(3) : "--"}`);
  lines.push(`方向命中率(在优秀线同侧),${(result.dirRate * 100).toFixed(1)}%`);
  extraLines.forEach((l) => lines.push(l));
  fs.writeFileSync(outPath, "\uFEFF" + lines.join("\n"), "utf8");
}

function printSummary(result, label = "") {
  console.error(`\n==== ${label}汇总 (预测CPE vs 真实CPE) ====`);
  console.error(`有效 ${result.n}/${result.testCount} 条`);
  console.error(`MAE=${result.mae.toFixed(2)} RMSE=${result.rmse.toFixed(2)} MAPE=${(result.mape * 100).toFixed(1)}% 中位AE=${result.medAE.toFixed(2)}`);
  console.error(`r=${Number.isFinite(result.r) ? result.r.toFixed(3) : "--"} R²=${Number.isFinite(result.r2) ? result.r2.toFixed(3) : "--"} 方向命中=${(result.dirRate * 100).toFixed(1)}%`);
}

// ============ 交叉验证 ============
function kFoldSplit(records, k) {
  const shuffled = records.slice().sort(() => Math.random() - 0.5);
  const folds = [];
  const size = Math.floor(shuffled.length / k);
  for (let i = 0; i < k; i++) {
    folds.push(shuffled.slice(i * size, i === k - 1 ? shuffled.length : (i + 1) * size));
  }
  return folds;
}

function runCrossValidation(api, trainText, settings, k) {
  const trainParsed = api.parseHistoryTable(trainText);
  const records = trainParsed.records;
  if (records.length < k * 4) {
    console.error(`样本数 ${records.length} 太少，无法做 ${k}-fold 交叉验证`);
    return null;
  }
  const folds = kFoldSplit(records, k);
  const allPairs = [];
  let totalMae = 0,
    totalRmse = 0,
    totalDirRate = 0;

  for (let i = 0; i < k; i++) {
    const testRecs = folds[i];
    const trainRecs = folds.flatMap((f, idx) => (idx === i ? [] : f));
    const fakeTrainParsed = { ...trainParsed, records: trainRecs };
    const model = api.trainModel(fakeTrainParsed, settings);
    const thr = model.cpeThreshold;
    const pairs = [];
    testRecs.forEach((rec) => {
      const input = {
        title: rec.title,
        body: rec.body,
        preInteractions: rec.preInteractions,
        interactionParts: rec.interactionParts || {},
        cover: rec.cover || null,
        channel: rec.channel,
      };
      const p = api.predict(input, model);
      const predCpe = p.predictedCpe;
      const realCpe = rec.cpe;
      if (Number.isFinite(realCpe) && realCpe > 0 && Number.isFinite(predCpe) && predCpe > 0) {
        pairs.push({ pred: predCpe, real: realCpe });
      }
    });
    const n = pairs.length;
    const mae = n ? pairs.reduce((s, p) => s + Math.abs(p.pred - p.real), 0) / n : 0;
    const rmseVal = rmse(pairs);
    let dirHit = 0;
    pairs.forEach((p) => {
      if ((p.pred <= thr) === (p.real <= thr)) dirHit++;
    });
    const dirRate = n ? dirHit / n : 0;
    console.error(`Fold ${i + 1}/${k}: n=${n} MAE=${mae.toFixed(2)} RMSE=${rmseVal.toFixed(2)} Dir=${(dirRate * 100).toFixed(1)}%`);
    totalMae += mae;
    totalRmse += rmseVal;
    totalDirRate += dirRate;
    allPairs.push(...pairs);
  }

  const avgMae = totalMae / k;
  const avgRmse = totalRmse / k;
  const avgDirRate = totalDirRate / k;
  const rVal = corr(
    allPairs.map((p) => p.pred),
    allPairs.map((p) => p.real)
  );
  console.error(`\nCV 平均: MAE=${avgMae.toFixed(2)} RMSE=${avgRmse.toFixed(2)} Dir=${(avgDirRate * 100).toFixed(1)}% r=${Number.isFinite(rVal) ? rVal.toFixed(3) : "--"}`);
  return { avgMae, avgRmse, avgDirRate, allPairs };
}

// ============ 超参数自动搜索 ============
function autoTune(api, trainText, testText) {
  const strictnessOptions = ["strict", "balanced", "growth"];
  const minIntOptions = [0, 10, 50, 100];
  let best = null;
  let bestScore = Infinity;

  console.error("开始超参数自动搜索 (strictness × minInteractions)...");
  for (const s of strictnessOptions) {
    for (const m of minIntOptions) {
      const settings = { strictness: s, cpeMode: "auto", customCpe: 0, minInteractions: m };
      const result = evaluateModel(api, trainText, testText, settings);
      const score = result.mae * 0.6 + (1 - result.dirRate) * 2.0;
      console.error(`  strictness=${s} minInteractions=${m} => MAE=${result.mae.toFixed(2)} Dir=${(result.dirRate * 100).toFixed(1)}% score=${score.toFixed(3)}`);
      if (score < bestScore) {
        bestScore = score;
        best = { settings, result };
      }
    }
  }
  console.error(`\n最佳参数: strictness=${best.settings.strictness} minInteractions=${best.settings.minInteractions}`);
  return best;
}

// ============ LLM 调用 ============
function postJson(targetUrl, payload, headers = {}) {
  return new Promise((resolve, reject) => {
    let urlObj;
    try {
      urlObj = new URL(targetUrl);
    } catch (e) {
      reject(new Error("URL 不合法: " + targetUrl));
      return;
    }
    const lib = urlObj.protocol === "https:" ? https : http;
    const body = JSON.stringify(payload);
    const req = lib.request(
      {
        protocol: urlObj.protocol,
        hostname: urlObj.hostname,
        port: urlObj.port || (urlObj.protocol === "https:" ? 443 : 80),
        path: (urlObj.pathname || "/") + (urlObj.search || ""),
        method: "POST",
        headers: { "Content-Type": "application/json", "Content-Length": Buffer.byteLength(body), ...headers },
        timeout: 120000,
      },
      (res) => {
        const chunks = [];
        res.on("data", (c) => chunks.push(c));
        res.on("end", () => {
          const text = Buffer.concat(chunks).toString("utf8");
          let json = null;
          try {
            json = JSON.parse(text);
          } catch (e) {}
          resolve({ statusCode: res.statusCode, text, json });
        });
      }
    );
    req.on("error", reject);
    req.on("timeout", () => {
      req.destroy();
      reject(new Error("timeout"));
    });
    req.write(body);
    req.end();
  });
}

function buildLlmPrompt(data) {
  const line = data.cpeThreshold || 1.4;
  const stats = data.historyStats || {};
  return `你是小红书投放 CPE 预测专家。任务：预测这条笔记加热后的综合 CPE，并据此判断是否值得加热。

# 最高优先级规则（必须遵守）
1. **CPE ≤ ${line} 才算加热成功；CPE > ${line} 就是失败。这是硬性业务红线。**
2. **历史相似样本的真实 CPE 是最强信号，远比内容写得好不好重要。**
3. **警惕"内容质量陷阱"**：旅行随拍、风景、小确幸、宠物日常、泛生活记录这类内容，历史上 CPE 往往很差。
4. 本地模型的预测 CPE 只是参考之一，可以修正，但不要凭"内容感觉"反向覆盖历史数据。

# 决策映射（严格按预测 CPE 区间）
- 预测 CPE 中值明显 ≤ ${line}（且相似历史多数达标）→ "值得加热"
- 预测 CPE 中值在 ${line} 上下浮动、相似历史好坏参半 → "建议小额测试"
- 预测 CPE 中值明显 > ${line}，或相似历史多数不达标 → "暂不建议加热"

# 相似历史统计
- 成功红线 CPE = ${line}
- 相似样本数 = ${stats.neighborCount ?? "未知"}
- 其中 CPE ≤ ${line} 的 = ${stats.neighborsBelowLine ?? "未知"} 条
- 相似样本达标比例 = ${stats.fractionBelowLine ?? "未知"}
- 相似样本 CPE 中位数 = ${stats.medianNeighborCpe ?? "未知"}

# 输出要求
- 严格 JSON，不要 Markdown，不要 JSON 之外的任何文字。
- decision 只能是 "值得加热"、"建议小额测试"、"暂不建议加热" 三选一。
- predicted_cpe_range 必须是你预测的 CPE 区间，如 "0.8-1.3"、"1.5-2.2"、"3.0+"。
- score 0-100，是"值得加热"的把握度（越高越值得，与预测 CPE 反向）。
- suggested_budget 人民币区间，如 "50-100元"；暂不建议时填 "0元" 或 "不建议"。
- calibration_notes 里简述：你的预测 CPE 主要依据哪几条相似历史，是否纠正了本地模型。

JSON 字段：
{
  "decision": "值得加热 | 建议小额测试 | 暂不建议加热",
  "score": 0,
  "confidence": 0,
  "predicted_cpe_range": "",
  "suggested_budget": "",
  "summary": "",
  "reasons": [],
  "risks": [],
  "actions": [],
  "calibration_notes": ""
}

输入数据：
${JSON.stringify(data.input, null, 2)}`;
}

async function callLlm(api, model, rec, localPrediction, modelSummary, baseUrl, apiKey) {
  const input = {
    title: rec.title,
    body: rec.body,
    currentInteractions: rec.preInteractions,
    likes: rec.interactionParts?.likes,
    collects: rec.interactionParts?.collects,
    comments: rec.interactionParts?.comments,
    shares: rec.interactionParts?.shares,
    cover: null,
  };
  const similarHistory = localPrediction.neighbors.map((n) => ({
    similarity: Math.round(n.score * 100),
    title: n.record.title,
    body: n.record.body,
    preInteractions: n.record.preInteractions,
    totalInteractions: n.record.totalInteractions,
    spend: n.record.spend,
    cpe: n.record.cpe,
    result: n.record.label ? "成功" : "失败",
  }));
  const historyStats = {
    successLine: modelSummary.cpeThreshold,
    neighborCount: similarHistory.length,
    neighborsBelowLine: similarHistory.filter((h) => h.cpe <= modelSummary.cpeThreshold).length,
    neighborsAboveLine: similarHistory.filter((h) => h.cpe > modelSummary.cpeThreshold).length,
    fractionBelowLine: similarHistory.length
      ? similarHistory.filter((h) => h.cpe <= modelSummary.cpeThreshold).length / similarHistory.length
      : null,
    medianNeighborCpe: similarHistory.length ? median(similarHistory.map((h) => h.cpe)) : null,
    minNeighborCpe: similarHistory.length ? Math.min(...similarHistory.map((h) => h.cpe)) : null,
    maxNeighborCpe: similarHistory.length ? Math.max(...similarHistory.map((h) => h.cpe)) : null,
  };
  const data = {
    input,
    historyStats,
    similarHistory,
    modelSummary,
    cpeThreshold: modelSummary.cpeThreshold,
    localPrediction: {
      decision: localPrediction.decision.title,
      score: Math.round(localPrediction.probability * 100),
      predictedCpe: localPrediction.predictedCpe,
      predictedInteractions: localPrediction.predictedInteractions,
      neighborSuccessRate: localPrediction.neighborSuccessRate,
      cpeThreshold: modelSummary.cpeThreshold,
      confidence: localPrediction.confidence,
    },
  };
  const prompt = buildLlmPrompt(data);
  const systemText =
    SYSTEM_PROMPT ||
    "你是严谨的小红书投放 CPE 预测专家。核心原则：以历史相似样本的真实 CPE 为主要依据，而非文案质量；整体偏保守，宁可漏掉也不误推。只返回严格 JSON。";

  const request = {
    model,
    messages: [
      { role: "system", content: systemText },
      { role: "user", content: prompt },
    ],
    temperature: TEMPERATURE,
  };

  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    try {
      const res = await postJson(`${baseUrl.replace(/\/+$/, "")}/chat/completions`, request, {
        Authorization: `Bearer ${apiKey}`,
      });
      if (res.statusCode < 200 || res.statusCode >= 300) {
        throw new Error(`HTTP ${res.statusCode}: ${res.text?.slice(0, 200)}`);
      }
      const content = res.json?.choices?.[0]?.message?.content || "";
      const parsed = parseJsonFromText(content);
      return normalizeLlmPrediction(parsed);
    } catch (err) {
      if (attempt === MAX_RETRIES) throw err;
      console.error(`  LLM 调用失败(${attempt + 1}/${MAX_RETRIES + 1}): ${err.message}，${DELAY}ms 后重试...`);
      await new Promise((r) => setTimeout(r, DELAY));
    }
  }
}

function parseJsonFromText(text) {
  text = String(text || "").trim();
  if (text.startsWith("```json")) text = text.slice(7);
  else if (text.startsWith("```")) text = text.slice(3);
  if (text.endsWith("```")) text = text.slice(0, -3);
  text = text.trim();
  try {
    return JSON.parse(text);
  } catch (e) {}
  const m = text.match(/\{[\s\S]*\}/);
  if (m)
    try {
      return JSON.parse(m[0]);
    } catch (e) {}
  throw new Error("无法从文本解析 JSON");
}

function normalizeLlmPrediction(value) {
  const mapDecision = (d) => {
    const s = String(d || "").trim();
    if (s.includes("值得加热")) return "worth";
    if (s.includes("小额测试")) return "test";
    if (s.includes("不建议")) return "hold";
    return "hold";
  };
  const mapTitle = (k) =>
    ({ worth: "值得加热", test: "建议小额测试", hold: "暂不建议加热" }[k] || k);
  const key = mapDecision(value.decision);
  return {
    decision: key,
    title: mapTitle(key),
    score: Math.max(0, Math.min(100, Math.round(Number(value.score) || 0))),
    confidence: Math.max(0, Math.min(100, Math.round(Number(value.confidence) || 0))),
    predicted_cpe_range: String(value.predicted_cpe_range || value.predictedCpeRange || "").trim(),
    suggested_budget: String(value.suggested_budget || value.suggestedBudget || "").trim(),
    summary: String(value.summary || "").trim(),
    reasons: Array.isArray(value.reasons) ? value.reasons.map(String) : [],
    risks: Array.isArray(value.risks) ? value.risks.map(String) : [],
    actions: Array.isArray(value.actions) ? value.actions.map(String) : [],
    calibration_notes: String(value.calibration_notes || value.calibrationNotes || "").trim(),
  };
}

// ============ 主流程 ============
async function main() {
  const api = loadAppApi();

  if (METHOD === "local") {
    console.error(`[本地模型] 训练集: ${TRAIN} | 测试集: ${TEST} | 输出: ${OUT}`);
    console.error(`超参数: strictness=${STRICTNESS} cpeMode=${CPE_MODE} minInteractions=${MIN_INTERACTIONS}`);

    const trainText = readCsvText(TRAIN);
    const testText = readCsvText(TEST);

    if (AUTO_TUNE) {
      const best = autoTune(api, trainText, testText);
      writeValidationCsv(OUT, best.result, [
        "",
        `最佳参数: strictness=${best.settings.strictness} minInteractions=${best.settings.minInteractions}`,
      ]);
      printSummary(best.result, "最佳参数 ");
      console.error(`\n结果已写入: ${OUT}`);
      return;
    }

    if (K_FOLDS > 1) {
      const cvResult = runCrossValidation(
        api,
        trainText,
        {
          strictness: STRICTNESS,
          cpeMode: CPE_MODE,
          customCpe: CUSTOM_CPE,
          minInteractions: MIN_INTERACTIONS,
        },
        K_FOLDS
      );
      if (!cvResult) return;
      const lines = [
        "",
        "==== 交叉验证汇总 ====",
        `K-Folds,${K_FOLDS}`,
        `平均 MAE,${cvResult.avgMae.toFixed(2)}`,
        `平均 RMSE,${cvResult.avgRmse.toFixed(2)}`,
        `平均方向命中率,${(cvResult.avgDirRate * 100).toFixed(1)}%`,
        `总有效样本,${cvResult.allPairs.length}`,
      ];
      fs.writeFileSync(OUT, "\uFEFF" + lines.join("\n"), "utf8");
      console.error(`\n交叉验证结果已写入: ${OUT}`);
      return;
    }

    const result = evaluateModel(api, trainText, testText, {
      strictness: STRICTNESS,
      cpeMode: CPE_MODE,
      customCpe: CUSTOM_CPE,
      minInteractions: MIN_INTERACTIONS,
    });
    writeValidationCsv(OUT, result);
    printSummary(result);
    console.error(`\n结果已写入: ${OUT}`);
    return;
  }

  if (METHOD === "llm") {
    console.error(`[LLM模型] 训练集: ${TRAIN} | 测试集: ${TEST} | 输出: ${OUT}`);
    console.error(`API: ${BASE_URL} | 模型: ${MODEL_ARG} | 温度: ${TEMPERATURE}`);

    const trainText = readCsvText(TRAIN);
    const testText = readCsvText(TEST);
    const trainParsed = api.parseHistoryTable(trainText);
    const settings = { strictness: "balanced", cpeMode: "auto", customCpe: 0, minInteractions: 0 };
    const model = api.trainModel(trainParsed, settings);
    const testParsed = api.parseHistoryTable(testText);
    const modelSummary = {
      sampleCount: model.records.length,
      cpeThreshold: model.cpeThreshold,
      medianSpend: model.medianSpend,
      baselineSuccessRate: model.baseline,
      strictness: model.settings.strictness,
    };

    for (const currentModel of MODELS) {
      console.error(`\n>>> 正在测试模型: ${currentModel}`);
      const rows = [];
      const pairs = [];
      let idx = 0;
      for (const rec of testParsed.records) {
        idx++;
        const input = {
          title: rec.title,
          body: rec.body,
          preInteractions: rec.preInteractions,
          interactionParts: rec.interactionParts || {},
          cover: rec.cover || null,
          channel: rec.channel,
        };
        const localP = api.predict(input, model);
        const realCpe = rec.cpe;
        const valid = Number.isFinite(realCpe) && realCpe > 0;

        let llmPred = null;
        let llmError = "";
        try {
          llmPred = await callLlm(api, currentModel, rec, localP, modelSummary, BASE_URL, API_KEY);
        } catch (err) {
          llmError = err.message;
          console.error(`  [${idx}/${testParsed.records.length}] 失败: ${err.message}`);
        }

        if (llmPred && valid) {
          const decisionToCpe = {
            worth: model.cpeThreshold * 0.6,
            test: model.cpeThreshold,
            hold: model.cpeThreshold * 1.6,
          };
          const llmCpe = decisionToCpe[llmPred.decision] || model.cpeThreshold;
          pairs.push({ pred: llmCpe, real: realCpe });
        }

        rows.push({
          noteId: rec.noteId,
          title: rec.title,
          realCpe: valid ? realCpe.toFixed(2) : "无效",
          localDecision: localP.decision.title,
          localScore: Math.round(localP.probability * 100),
          llmDecision: llmPred ? llmPred.title : llmError,
          llmScore: llmPred ? llmPred.score : "",
          llmCpeRange: llmPred ? llmPred.predicted_cpe_range : "",
          llmBudget: llmPred ? llmPred.suggested_budget : "",
          llmSummary: llmPred ? llmPred.summary : "",
          llmCalibration: llmPred ? llmPred.calibration_notes : "",
        });

        console.error(
          `  [${idx}/${testParsed.records.length}] ${rec.title.slice(0, 24)}... 本地=${localP.decision.title} LLM=${llmPred ? llmPred.title : "失败"}`
        );

        if (idx < testParsed.records.length) {
          await new Promise((r) => setTimeout(r, DELAY));
        }
      }

      const n = pairs.length;
      const mae = n ? pairs.reduce((s, p) => s + Math.abs(p.pred - p.real), 0) / n : 0;
      const mape = n ? pairs.reduce((s, p) => s + Math.abs(p.pred - p.real) / p.real, 0) / n : 0;
      const rmseVal = rmse(pairs);
      let dirHit = 0;
      pairs.forEach((p) => {
        if ((p.pred <= model.cpeThreshold) === (p.real <= model.cpeThreshold)) dirHit++;
      });
      const dirRate = n ? dirHit / n : 0;

      const header = [
        "笔记ID",
        "标题",
        "真实CPE",
        "本地决策",
        "本地值得分",
        "LLM决策",
        "LLM值得分",
        "LLM预测CPE区间",
        "LLM建议预算",
        "LLM摘要",
        "LLM校准说明",
      ];
      const lines = [header.map(csvCell).join(",")];
      rows.forEach((r) => {
        lines.push(
          [
            r.noteId,
            r.title,
            r.realCpe,
            r.localDecision,
            r.localScore,
            r.llmDecision,
            r.llmScore,
            r.llmCpeRange,
            r.llmBudget,
            r.llmSummary,
            r.llmCalibration,
          ]
            .map(csvCell)
            .join(",")
        );
      });
      lines.push("");
      lines.push("==== 汇总 ====");
      lines.push(`模型,${currentModel}`);
      lines.push(`有效条数,${n}`);
      lines.push(`MAE,${mae.toFixed(2)}`);
      lines.push(`RMSE,${rmseVal.toFixed(2)}`);
      lines.push(`MAPE,${(mape * 100).toFixed(1)}%`);
      lines.push(`方向命中率,${(dirRate * 100).toFixed(1)}%`);

      const outPath = MODELS.length > 1 ? OUT.replace(".csv", `_${currentModel}.csv`) : OUT;
      fs.writeFileSync(outPath, "\uFEFF" + lines.join("\n"), "utf8");
      console.error(`\n模型 ${currentModel} 结果已写入: ${outPath}`);
      console.error(`MAE=${mae.toFixed(2)} RMSE=${rmseVal.toFixed(2)} MAPE=${(mape * 100).toFixed(1)}% Dir=${(dirRate * 100).toFixed(1)}%`);
    }
    return;
  }

  console.error("未知方法: " + METHOD);
  console.error("用法: node run.js --method local|llm [options...]");
  process.exit(1);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});