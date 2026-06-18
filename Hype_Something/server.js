"use strict";

const http = require("http");
const https = require("https");
const fs = require("fs");
const path = require("path");
const { URL } = require("url");

const PORT = Number(process.env.PORT) || 5173;
const ROOT = __dirname;

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".webp": "image/webp",
  ".ico": "image/x-icon",
  ".txt": "text/plain; charset=utf-8",
};

const DESKTOP_UA =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15";
const MOBILE_UA =
  "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1";

const COOKIE_FILE = path.join(ROOT, "cookies.txt");

function loadCookieFromDisk() {
  try {
    if (fs.existsSync(COOKIE_FILE)) {
      const raw = fs.readFileSync(COOKIE_FILE, "utf-8").trim();
      if (raw) return raw;
    }
  } catch (e) {}
  return "";
}

let XHS_COOKIE = process.env.XHS_COOKIE ? process.env.XHS_COOKIE.trim() : loadCookieFromDisk();
const COOKIE_LOCKED_BY_ENV = !!process.env.XHS_COOKIE;

// ── LLM 配置：优先环境变量，其次读 llm_config.json，最后用默认值 ──────────────
const LLM_CONFIG_FILE = path.join(ROOT, "llm_config.json");
const OPENAI_KEY_LOCKED_BY_ENV = !!process.env.OPENAI_API_KEY;

function loadLlmConfigFromDisk() {
  if (OPENAI_KEY_LOCKED_BY_ENV) return {};
  try {
    if (fs.existsSync(LLM_CONFIG_FILE)) {
      return JSON.parse(fs.readFileSync(LLM_CONFIG_FILE, "utf-8"));
    }
  } catch (e) {}
  return {};
}

function saveLlmConfigToDisk() {
  if (OPENAI_KEY_LOCKED_BY_ENV) return;
  try {
    fs.writeFileSync(LLM_CONFIG_FILE, JSON.stringify({
      apiKey: OPENAI_API_KEY,
      provider: LLM_PROVIDER,
      model: OPENAI_MODEL,
      baseUrl: OPENAI_BASE_URL,
      sendImage: LLM_SEND_IMAGE,
    }, null, 2), "utf-8");
  } catch (e) {
    console.error("写入 llm_config.json 失败：", e.message);
  }
}

const _savedLlm = loadLlmConfigFromDisk();
let OPENAI_API_KEY = process.env.OPENAI_API_KEY ? process.env.OPENAI_API_KEY.trim()
  : (_savedLlm.apiKey || "");
let LLM_PROVIDER = process.env.LLM_PROVIDER ? process.env.LLM_PROVIDER.trim().toLowerCase()
  : (_savedLlm.provider || process.env.OPENAI_PROVIDER || "openai").trim().toLowerCase();
let OPENAI_MODEL = process.env.OPENAI_MODEL ? process.env.OPENAI_MODEL.trim()
  : (_savedLlm.model || defaultModelForProvider(LLM_PROVIDER));
let OPENAI_BASE_URL = process.env.OPENAI_BASE_URL ? process.env.OPENAI_BASE_URL.replace(/\/+$/, "")
  : ((_savedLlm.baseUrl || defaultBaseUrlForProvider(LLM_PROVIDER)).replace(/\/+$/, ""));
let LLM_SEND_IMAGE = process.env.LLM_SEND_IMAGE
  ? (process.env.LLM_SEND_IMAGE !== "0" && process.env.LLM_SEND_IMAGE.toLowerCase() !== "false")
  : (typeof _savedLlm.sendImage === "boolean" ? _savedLlm.sendImage : defaultSendImageForProvider(LLM_PROVIDER));

if (XHS_COOKIE) {
  console.log("已加载 cookie（长度", XHS_COOKIE.length, "），抓取时会带上以提升成功率。");
} else {
  console.log("未配置 cookie。建议通过工具界面左侧「Cookie 设置」粘贴，无需重启。");
}

if (OPENAI_API_KEY) {
  console.log(`已加载 LLM 配置（${LLM_PROVIDER} / ${OPENAI_MODEL}），混合预测可用。`);
} else {
  console.log("未配置 LLM API Key。可在工具界面左侧「LLM 设置」粘贴，无需重启。");
}

function saveCookieToDisk(cookie) {
  if (COOKIE_LOCKED_BY_ENV) return;
  try {
    fs.writeFileSync(COOKIE_FILE, cookie, "utf-8");
  } catch (e) {
    console.error("写入 cookies.txt 失败：", e.message);
  }
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    req.on("data", (c) => chunks.push(c));
    req.on("end", () => resolve(Buffer.concat(chunks).toString("utf-8")));
    req.on("error", reject);
  });
}

function cookieStatus() {
  return {
    configured: !!XHS_COOKIE,
    length: XHS_COOKIE.length,
    preview: XHS_COOKIE ? XHS_COOKIE.slice(0, 40) + (XHS_COOKIE.length > 40 ? "…" : "") : "",
    lockedByEnv: COOKIE_LOCKED_BY_ENV,
  };
}

function llmStatus() {
  return {
    configured: !!OPENAI_API_KEY,
    provider: LLM_PROVIDER,
    model: OPENAI_MODEL,
    baseUrl: OPENAI_BASE_URL,
    sendImage: LLM_SEND_IMAGE,
    lockedByEnv: OPENAI_KEY_LOCKED_BY_ENV,
  };
}

function normalizeProvider(provider) {
  const value = String(provider || "").trim().toLowerCase();
  if (["openai", "deepseek", "gemini", "compatible"].includes(value)) return value;
  return "openai";
}

function inferProviderFromApiKey(apiKey) {
  const key = String(apiKey || "").trim();
  if (/^AIza[0-9A-Za-z_-]+/.test(key)) return "gemini";
  if (/^sk-[0-9A-Za-z_-]+/.test(key)) return null;
  return null;
}

function defaultModelForProvider(provider) {
  const p = normalizeProvider(provider);
  if (p === "deepseek") return "deepseek-chat";
  if (p === "gemini") return "gemini-2.5-flash";
  if (p === "compatible") return "";
  return "gpt-5.1";
}

function defaultBaseUrlForProvider(provider) {
  const p = normalizeProvider(provider);
  if (p === "deepseek") return "https://api.deepseek.com";
  if (p === "gemini") return "https://generativelanguage.googleapis.com";
  if (p === "compatible") return "";
  return "https://api.openai.com/v1";
}

function defaultSendImageForProvider(provider) {
  const p = normalizeProvider(provider);
  return p === "openai" || p === "gemini";
}

function providerLabel(provider) {
  return {
    openai: "OpenAI",
    deepseek: "DeepSeek",
    gemini: "Gemini",
    compatible: "OpenAI兼容",
  }[normalizeProvider(provider)] || "LLM";
}

function truncateText(value, max = 1200) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  if (text.length <= max) return text;
  return text.slice(0, max) + "…";
}

function compactNumber(value, digits = 2) {
  const n = Number(value);
  return Number.isFinite(n) ? Number(n.toFixed(digits)) : null;
}

function sanitizeLlmPayload(payload) {
  const post = payload && payload.post ? payload.post : {};
  const local = payload && payload.localPrediction ? payload.localPrediction : {};
  const similar = Array.isArray(payload && payload.similarHistory) ? payload.similarHistory : [];
  const modelSummary = payload && payload.modelSummary ? payload.modelSummary : {};
  const coverImage = typeof post.coverImage === "string" && post.coverImage.startsWith("data:image/")
    ? post.coverImage.slice(0, 5_500_000)
    : null;

  // 预先算好相似历史的关键统计，避免让 LLM 自己做算术（LLM 算术不可靠）
  const threshold = compactNumber(modelSummary.cpeThreshold, 2) || 1.4;
  const neighborCpes = similar
    .map((item) => Number(item.cpe))
    .filter((n) => Number.isFinite(n) && n > 0);
  const goodCount = neighborCpes.filter((c) => c <= threshold).length;
  const sortedCpes = [...neighborCpes].sort((a, b) => a - b);
  const medianCpe = sortedCpes.length
    ? (sortedCpes.length % 2
        ? sortedCpes[(sortedCpes.length - 1) / 2]
        : (sortedCpes[sortedCpes.length / 2 - 1] + sortedCpes[sortedCpes.length / 2]) / 2)
    : null;
  const historyStats = {
    successLine: threshold,
    neighborCount: neighborCpes.length,
    neighborsBelowLine: goodCount,
    neighborsAboveLine: neighborCpes.length - goodCount,
    fractionBelowLine: neighborCpes.length ? compactNumber(goodCount / neighborCpes.length, 2) : null,
    medianNeighborCpe: compactNumber(medianCpe, 2),
    minNeighborCpe: sortedCpes.length ? compactNumber(sortedCpes[0], 2) : null,
    maxNeighborCpe: sortedCpes.length ? compactNumber(sortedCpes[sortedCpes.length - 1], 2) : null,
  };

  return {
    historyStats,
    post: {
      title: truncateText(post.title, 180),
      body: truncateText(post.body, 1600),
      noteId: truncateText(post.noteId, 80),
      currentInteractions: compactNumber(post.currentInteractions, 0),
      likes: compactNumber(post.likes, 0),
      collects: compactNumber(post.collects, 0),
      comments: compactNumber(post.comments, 0),
      shares: compactNumber(post.shares, 0),
      cover: post.cover || null,
    },
    coverImage,
    localPrediction: {
      decision: truncateText(local.decision, 60),
      score: compactNumber(local.score, 0),
      predictedCpe: compactNumber(local.predictedCpe, 2),
      predictedInteractions: compactNumber(local.predictedInteractions, 0),
      neighborSuccessRate: compactNumber(local.neighborSuccessRate, 3),
      cpeThreshold: compactNumber(local.cpeThreshold, 2),
      confidence: compactNumber(local.confidence, 0),
      signals: Array.isArray(local.signals) ? local.signals.slice(0, 10) : [],
    },
    similarHistory: similar.slice(0, 8).map((item) => ({
      similarity: compactNumber(item.similarity, 0),
      title: truncateText(item.title, 160),
      body: truncateText(item.body, 260),
      preInteractions: compactNumber(item.preInteractions, 0),
      totalInteractions: compactNumber(item.totalInteractions, 0),
      spend: compactNumber(item.spend, 2),
      cpe: compactNumber(item.cpe, 2),
      result: truncateText(item.result, 20),
    })),
    modelSummary: {
      sampleCount: compactNumber(modelSummary.sampleCount, 0),
      cpeThreshold: compactNumber(modelSummary.cpeThreshold, 2),
      medianSpend: compactNumber(modelSummary.medianSpend, 2),
      baselineSuccessRate: compactNumber(modelSummary.baselineSuccessRate, 3),
      strictness: truncateText(modelSummary.strictness, 20),
    },
  };
}

function normalizeUrl(target, base) {
  const t = String(target || "").trim();
  if (/^https?:\/\//i.test(t)) return t;
  if (t.startsWith("//")) return "https:" + t;
  if (base) return new URL(t, base).toString();
  return t;
}

function fetchRaw(targetUrl, options = {}, maxRedirects = 5) {
  return new Promise((resolve, reject) => {
    if (maxRedirects < 0) {
      reject(new Error("重定向次数过多"));
      return;
    }
    let urlObj;
    try {
      urlObj = new URL(targetUrl);
    } catch (e) {
      reject(new Error("URL 不合法: " + targetUrl));
      return;
    }
    const lib = urlObj.protocol === "https:" ? https : http;
    const req = lib.request(
      {
        protocol: urlObj.protocol,
        hostname: urlObj.hostname,
        port: urlObj.port || (urlObj.protocol === "https:" ? 443 : 80),
        path: (urlObj.pathname || "/") + (urlObj.search || ""),
        method: "GET",
        headers: {
          "User-Agent": options.userAgent || DESKTOP_UA,
          Accept: options.accept || "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
          "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
          ...(options.withCookie && XHS_COOKIE ? { Cookie: XHS_COOKIE } : {}),
          ...(options.headers || {}),
        },
      },
      (res) => {
        if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
          const next = new URL(res.headers.location, targetUrl).toString();
          res.resume();
          fetchRaw(next, options, maxRedirects - 1).then(resolve, reject);
          return;
        }
        const chunks = [];
        res.on("data", (c) => chunks.push(c));
        res.on("end", () =>
          resolve({
            statusCode: res.statusCode,
            headers: res.headers,
            body: Buffer.concat(chunks),
            finalUrl: targetUrl,
          })
        );
      }
    );
    req.setTimeout(15000, () => {
      req.destroy(new Error("请求超时"));
    });
    req.on("error", reject);
    req.end();
  });
}

function decodeHtml(s) {
  return String(s)
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#x([0-9a-fA-F]+);/g, (_, h) => String.fromCodePoint(parseInt(h, 16)))
    .replace(/&#(\d+);/g, (_, d) => String.fromCodePoint(parseInt(d, 10)))
    .replace(/&apos;/g, "'")
    .replace(/&nbsp;/g, " ");
}

function pickMeta(html, prop) {
  const patterns = [
    new RegExp(`<meta[^>]+property\\s*=\\s*"${prop}"[^>]*>`, "i"),
    new RegExp(`<meta[^>]+name\\s*=\\s*"${prop}"[^>]*>`, "i"),
  ];
  for (const re of patterns) {
    const m = html.match(re);
    if (!m) continue;
    const content = m[0].match(/content\s*=\s*"([^"]*)"/i);
    if (content) return decodeHtml(content[1]);
  }
  return "";
}

function extractInitialState(html) {
  const marker = "window.__INITIAL_STATE__";
  const idx = html.indexOf(marker);
  if (idx < 0) return null;
  const eq = html.indexOf("=", idx + marker.length);
  if (eq < 0) return null;
  let i = eq + 1;
  while (i < html.length && /\s/.test(html[i])) i++;
  if (html[i] !== "{") return null;
  let depth = 0;
  let inStr = false;
  let strCh = "";
  let esc = false;
  const start = i;
  for (; i < html.length; i++) {
    const c = html[i];
    if (inStr) {
      if (esc) {
        esc = false;
        continue;
      }
      if (c === "\\") {
        esc = true;
        continue;
      }
      if (c === strCh) inStr = false;
      continue;
    }
    if (c === '"' || c === "'") {
      inStr = true;
      strCh = c;
      continue;
    }
    if (c === "{") depth++;
    else if (c === "}") {
      depth--;
      if (depth === 0) {
        const json = html.slice(start, i + 1);
        try {
          return JSON.parse(json.replace(/:\s*undefined/g, ":null"));
        } catch (e) {
          return null;
        }
      }
    }
  }
  return null;
}

function findFirstNoteLike(obj, depth = 0) {
  if (!obj || typeof obj !== "object" || depth > 6) return null;
  if ((obj.title || obj.desc) && (obj.imageList || obj.images || obj.interactInfo || obj.interact_info)) {
    return obj;
  }
  for (const key of Object.keys(obj)) {
    const v = obj[key];
    if (v && typeof v === "object") {
      const found = findFirstNoteLike(v, depth + 1);
      if (found) return found;
    }
  }
  return null;
}

function pickNote(state) {
  if (!state || typeof state !== "object") return null;
  try {
    const detailMap = state.note?.noteDetailMap || state.noteDetailMap;
    if (detailMap && typeof detailMap === "object") {
      const keys = Object.keys(detailMap);
      for (const k of keys) {
        const entry = detailMap[k];
        const n = entry?.note || entry;
        if (n && (n.title || n.desc)) return n;
      }
    }
  } catch (e) {}
  return findFirstNoteLike(state);
}

function asNumber(...candidates) {
  for (const c of candidates) {
    if (c === undefined || c === null || c === "") continue;
    const n = Number(c);
    if (Number.isFinite(n)) return n;
  }
  return null;
}

function pickCoverUrl(note) {
  const images = note.imageList || note.images || note.imagesList;
  if (Array.isArray(images) && images.length) {
    const first = images[0];
    if (typeof first === "string") return first;
    const candidates = [
      first.urlDefault,
      first.url_default,
      first.url,
      first.urlPre,
      first.url_pre,
      Array.isArray(first.infoList) && first.infoList[0] && first.infoList[0].url,
      Array.isArray(first.info_list) && first.info_list[0] && first.info_list[0].url,
    ];
    for (const c of candidates) {
      if (typeof c === "string" && c) return c;
    }
  }
  return "";
}

function parseXhsHtml(html) {
  const ogTitle = pickMeta(html, "og:title") || pickMeta(html, "twitter:title");
  const ogDesc = pickMeta(html, "og:description") || pickMeta(html, "description");
  const ogImage = pickMeta(html, "og:image") || pickMeta(html, "twitter:image");

  let title = ogTitle || "";
  let body = ogDesc || "";
  let cover = ogImage || "";
  let likes = null;
  let collects = null;
  let comments = null;
  let shares = null;
  let noteId = "";

  const state = extractInitialState(html);
  const note = state ? pickNote(state) : null;
  if (note) {
    if (note.title) title = String(note.title);
    if (note.desc) body = String(note.desc);
    if (note.noteId) noteId = String(note.noteId);
    else if (note.id) noteId = String(note.id);
    const interact = note.interactInfo || note.interact_info || {};
    likes = asNumber(interact.likedCount, interact.liked_count, interact.likeCount, interact.like_count);
    collects = asNumber(interact.collectedCount, interact.collected_count, interact.collectCount, interact.collect_count);
    comments = asNumber(interact.commentCount, interact.comment_count);
    shares = asNumber(interact.shareCount, interact.share_count);
    const coverUrl = pickCoverUrl(note);
    if (coverUrl) cover = coverUrl;
  }

  title = (title || "").trim();
  body = (body || "").trim();
  cover = (cover || "").trim();

  return { title, body, cover, noteId, likes, collects, comments, shares };
}

function send(res, status, body, contentType) {
  res.writeHead(status, {
    "Content-Type": contentType,
    "Access-Control-Allow-Origin": "*",
  });
  res.end(body);
}

function postJson(targetUrl, payload, headers = {}) {
  return new Promise((resolve, reject) => {
    let urlObj;
    try {
      urlObj = new URL(targetUrl);
    } catch (e) {
      reject(new Error("URL 不合法: " + targetUrl));
      return;
    }
    const body = Buffer.from(JSON.stringify(payload), "utf-8");
    const lib = urlObj.protocol === "https:" ? https : http;
    const req = lib.request(
      {
        protocol: urlObj.protocol,
        hostname: urlObj.hostname,
        port: urlObj.port || (urlObj.protocol === "https:" ? 443 : 80),
        path: (urlObj.pathname || "/") + (urlObj.search || ""),
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Content-Length": body.length,
          ...headers,
        },
      },
      (res) => {
        const chunks = [];
        res.on("data", (c) => chunks.push(c));
        res.on("end", () => {
          const text = Buffer.concat(chunks).toString("utf-8");
          let json = null;
          try {
            json = JSON.parse(text);
          } catch (e) {}
          resolve({ statusCode: res.statusCode, headers: res.headers, text, json });
        });
      }
    );
    req.setTimeout(45000, () => {
      req.destroy(new Error("LLM 请求超时"));
    });
    req.on("error", reject);
    req.write(body);
    req.end();
  });
}

function extractResponseText(responseJson) {
  if (!responseJson) return "";
  if (typeof responseJson.output_text === "string") return responseJson.output_text;
  const chunks = [];
  const visit = (node) => {
    if (!node || typeof node !== "object") return;
    if (typeof node.text === "string") chunks.push(node.text);
    if (Array.isArray(node)) {
      node.forEach(visit);
      return;
    }
    Object.values(node).forEach(visit);
  };
  visit(responseJson.output);
  return chunks.join("\n").trim();
}

function parseJsonFromText(text) {
  const raw = String(text || "").trim();
  if (!raw) throw new Error("LLM 没有返回文本");
  try {
    return JSON.parse(raw);
  } catch (e) {
    const match = raw.match(/\{[\s\S]*\}/);
    if (match) return JSON.parse(match[0]);
    throw new Error("LLM 返回内容不是 JSON");
  }
}

function normalizeLlmPrediction(value) {
  const allowed = new Set(["值得加热", "建议小额测试", "暂不建议加热"]);
  const decision = allowed.has(value.decision) ? value.decision : "建议小额测试";
  const score = Math.max(0, Math.min(100, Number(value.score) || 50));
  const confidence = Math.max(0, Math.min(100, Number(value.confidence) || 55));
  const arrayOfText = (items) => (Array.isArray(items) ? items : [])
    .map((item) => String(item || "").trim())
    .filter(Boolean)
    .slice(0, 6);
  return {
    decision,
    score,
    confidence,
    predicted_cpe_range: String(value.predicted_cpe_range || value.predictedCpeRange || "").trim(),
    suggested_budget: String(value.suggested_budget || value.suggestedBudget || "").trim(),
    summary: String(value.summary || "").trim(),
    reasons: arrayOfText(value.reasons),
    risks: arrayOfText(value.risks),
    actions: arrayOfText(value.actions),
    calibration_notes: String(value.calibration_notes || value.calibrationNotes || "").trim(),
  };
}

function buildLlmPrompt(data) {
  const withoutImage = { ...data, coverImage: data.coverImage ? "[封面图片已作为视觉输入附加]" : null };
  const line = (data.historyStats && data.historyStats.successLine) || 1.4;
  const stats = data.historyStats || {};
  return `你是小红书投放 CPE 预测专家。任务：预测这条笔记加热后的综合 CPE，并据此判断是否值得加热。

# 最高优先级规则（必须遵守）
1. **CPE ≤ ${line} 才算加热成功；CPE > ${line} 就是失败。这是硬性业务红线。**
2. **历史相似样本的真实 CPE 是最强信号，远比内容写得好不好重要。**
   你的核心任务是预测 CPE，不是评价文案质量。一条文案优美、情绪饱满的帖子，
   如果相似历史样本的 CPE 普遍偏高，它加热后大概率也会失败。
3. **警惕"内容质量陷阱"**：旅行随拍、风景、小确幸、宠物日常、泛生活记录这类
   "看起来很美但主题宽泛"的内容，历史上 CPE 往往很差（受众不精准、转化弱）。
   不要因为文案打动你就给高分。
4. 本地模型的预测 CPE 只是参考之一，可以修正，但不要凭"内容感觉"反向覆盖历史数据。

# 决策映射（严格按预测 CPE 区间）
- 预测 CPE 中值明显 ≤ ${line}（且相似历史多数达标）→ "值得加热"
- 预测 CPE 中值在 ${line} 上下浮动、相似历史好坏参半 → "建议小额测试"
- 预测 CPE 中值明显 > ${line}，或相似历史多数不达标 → "暂不建议加热"
- 当信息不足或矛盾时，默认偏保守（历史成功率本来就低）。

# 本批相似历史已为你算好的统计（请以此为主锚点）
- 成功红线 CPE = ${line}
- 相似样本数 = ${stats.neighborCount ?? "未知"}
- 其中 CPE ≤ ${line}（达标）的 = ${stats.neighborsBelowLine ?? "未知"} 条
- CPE > ${line}（不达标）的 = ${stats.neighborsAboveLine ?? "未知"} 条
- 相似样本达标比例 = ${stats.fractionBelowLine ?? "未知"}
- 相似样本 CPE 中位数 = ${stats.medianNeighborCpe ?? "未知"}（范围 ${stats.minNeighborCpe ?? "?"} ~ ${stats.maxNeighborCpe ?? "?"}）
→ 如果达标比例低于 0.5 或 CPE 中位数 > ${line}，除非有强力反证，否则倾向 "暂不建议加热"。

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
${JSON.stringify(withoutImage, null, 2)}`;
}

async function callConfiguredLlm({ prompt, systemText, coverImage }) {
  const provider = normalizeProvider(LLM_PROVIDER);
  const inferred = inferProviderFromApiKey(OPENAI_API_KEY);
  if (inferred && inferred !== provider) {
    throw new Error(`当前 API Key 看起来是 ${providerLabel(inferred)} 的 Key，但服务商选的是 ${providerLabel(provider)}。请在 LLM 设置里切换服务商后保存。`);
  }
  if (provider === "gemini") {
    return callGemini({ prompt, systemText, coverImage });
  }
  if (provider === "openai") {
    return callOpenAIResponses({ prompt, systemText, coverImage });
  }
  return callOpenAICompatible({ prompt, systemText, coverImage });
}

async function callOpenAIResponses({ prompt, systemText, coverImage }) {
  const content = [{ type: "input_text", text: prompt }];
  if (LLM_SEND_IMAGE && coverImage) {
    content.push({ type: "input_image", image_url: coverImage });
  }
  const request = {
    model: OPENAI_MODEL,
    input: [
      { role: "system", content: [{ type: "input_text", text: systemText }] },
      { role: "user", content },
    ],
  };
  return postJson(`${OPENAI_BASE_URL}/responses`, request, {
    Authorization: `Bearer ${OPENAI_API_KEY}`,
  });
}

async function callOpenAICompatible({ prompt, systemText, coverImage }) {
  const content = [{ type: "text", text: prompt }];
  if (LLM_SEND_IMAGE && coverImage && LLM_PROVIDER === "compatible") {
    content.push({ type: "image_url", image_url: { url: coverImage } });
  }
  const request = {
    model: OPENAI_MODEL,
    messages: [
      { role: "system", content: systemText },
      { role: "user", content: content.length === 1 ? prompt : content },
    ],
    temperature: 0.2,
  };
  const base = OPENAI_BASE_URL || defaultBaseUrlForProvider(LLM_PROVIDER);
  if (!base) {
    throw new Error("OpenAI兼容 服务商需要填写 Base URL。");
  }
  return postJson(`${base.replace(/\/+$/, "")}/chat/completions`, request, {
    Authorization: `Bearer ${OPENAI_API_KEY}`,
  });
}

async function callGemini({ prompt, systemText, coverImage }) {
  const parts = [{ text: `${systemText}\n\n${prompt}` }];
  if (LLM_SEND_IMAGE && coverImage) {
    const parsed = parseDataUrl(coverImage);
    if (parsed) {
      parts.push({ inline_data: { mime_type: parsed.mimeType, data: parsed.base64 } });
    }
  }
  const request = {
    contents: [{ role: "user", parts }],
    generationConfig: {
      temperature: 0.2,
      responseMimeType: "application/json",
    },
  };
  const base = (OPENAI_BASE_URL || defaultBaseUrlForProvider("gemini")).replace(/\/+$/, "");
  const path = `${base}/v1beta/models/${encodeURIComponent(OPENAI_MODEL)}:generateContent?key=${encodeURIComponent(OPENAI_API_KEY)}`;
  return postJson(path, request);
}

function parseDataUrl(dataUrl) {
  const match = String(dataUrl || "").match(/^data:([^;]+);base64,(.+)$/);
  if (!match) return null;
  return { mimeType: match[1], base64: match[2] };
}

function extractLlmText(json) {
  if (normalizeProvider(LLM_PROVIDER) === "gemini") {
    return (
      json?.candidates?.[0]?.content?.parts
        ?.map((part) => part.text || "")
        .join("\n")
        .trim() || ""
    );
  }
  if (json?.choices?.[0]?.message?.content) {
    const content = json.choices[0].message.content;
    if (typeof content === "string") return content;
    if (Array.isArray(content)) return content.map((part) => part.text || "").join("\n").trim();
  }
  return extractResponseText(json);
}

async function handleLlmPredict(payload, res) {
  if (!OPENAI_API_KEY) {
    return send(res, 400, JSON.stringify({ error: "未配置 LLM API Key。请在左侧 LLM 设置中粘贴，或启动前设置 OPENAI_API_KEY。" }), "application/json; charset=utf-8");
  }
  const data = sanitizeLlmPayload(payload || {});
  const prompt = buildLlmPrompt(data);
  const systemText = "你是严谨的小红书投放 CPE 预测专家。核心原则：以历史相似样本的真实 CPE 为主要依据，而非文案质量；内容写得好但相似历史 CPE 差时，必须判定为失败。整体偏保守，宁可漏掉也不误推。只返回严格 JSON。";

  let upstream;
  try {
    upstream = await callConfiguredLlm({ prompt, systemText, coverImage: data.coverImage });
  } catch (err) {
    return send(res, 502, JSON.stringify({ error: "LLM 请求失败：" + err.message }), "application/json; charset=utf-8");
  }

  if (upstream.statusCode < 200 || upstream.statusCode >= 300) {
    const message = upstream.json?.error?.message || upstream.text || `${providerLabel(LLM_PROVIDER)} 返回 ${upstream.statusCode}`;
    return send(res, 502, JSON.stringify({ error: "LLM 服务错误：" + message.slice(0, 500) }), "application/json; charset=utf-8");
  }

  try {
    const text = extractLlmText(upstream.json);
    const parsed = parseJsonFromText(text);
    const prediction = normalizeLlmPrediction(parsed);
    return send(res, 200, JSON.stringify({ prediction, model: OPENAI_MODEL, provider: LLM_PROVIDER }), "application/json; charset=utf-8");
  } catch (err) {
    return send(res, 502, JSON.stringify({ error: "LLM 返回解析失败：" + err.message }), "application/json; charset=utf-8");
  }
}

function isErrorPage(finalUrl, html) {
  if (finalUrl && /\/404(\?|$)/.test(finalUrl)) return true;
  if (finalUrl && /errorCode=-?\d+/.test(finalUrl)) return true;
  if (html && /errorCode=-510001/.test(html.slice(0, 5000))) return true;
  return false;
}

async function handleFetchPost(target, res) {
  const fetchOnce = (ua, withCookie) =>
    fetchRaw(target, {
      userAgent: ua,
      withCookie,
      headers: { Referer: "https://www.xiaohongshu.com/" },
    });

  let result;
  let html = "";
  try {
    result = await fetchOnce(DESKTOP_UA, true);
    html = result.body.toString("utf-8");
    if (result.statusCode !== 200 || isErrorPage(result.finalUrl, html) || !looksLikeNotePage(html)) {
      try {
        const mobile = await fetchOnce(MOBILE_UA, true);
        const mobileHtml = mobile.body.toString("utf-8");
        if (mobile.statusCode === 200 && !isErrorPage(mobile.finalUrl, mobileHtml)) {
          result = mobile;
          html = mobileHtml;
        }
      } catch (e) {}
    }
  } catch (err) {
    return send(res, 502, JSON.stringify({ error: "抓取失败：" + err.message }), "application/json; charset=utf-8");
  }

  if (result.statusCode !== 200) {
    return send(
      res,
      502,
      JSON.stringify({ error: `上游返回 ${result.statusCode}，可能是风控页或链接已失效` }),
      "application/json; charset=utf-8"
    );
  }

  if (isErrorPage(result.finalUrl, html)) {
    const hint = XHS_COOKIE
      ? "小红书把这条链接重定向到了 404 错误页（errorCode=-510001）。可能是 xsec_token 已过期、笔记被删，或当前 cookie 没有访问权限。建议重新从 App 复制最新分享链接。"
      : "小红书把这条链接重定向到了 404 错误页（errorCode=-510001）。这条链接的 xsec_token 通常已过期。解决方法：① 重新从小红书 App 复制最新分享链接；② 或在项目目录放一个 cookies.txt（复制你登录态浏览器里 xiaohongshu.com 的 Cookie 头）后重启 server.js。";
    return send(res, 422, JSON.stringify({ error: hint, finalUrl: result.finalUrl }), "application/json; charset=utf-8");
  }

  const parsed = parseXhsHtml(html);

  if (!parsed.title && !parsed.body) {
    return send(
      res,
      422,
      JSON.stringify({
        error: "页面解析失败：拿不到标题和正文。可能是风控页、需要登录、或不是笔记页。建议在 App 内重新复制完整笔记链接再试。",
        finalUrl: result.finalUrl,
      }),
      "application/json; charset=utf-8"
    );
  }

  if (parsed.cover) parsed.cover = normalizeUrl(parsed.cover);
  parsed.sourceUrl = result.finalUrl || target;
  return send(res, 200, JSON.stringify(parsed), "application/json; charset=utf-8");
}

function looksLikeNotePage(html) {
  return html.includes("__INITIAL_STATE__") || /og:title/i.test(html);
}

async function handleImageProxy(target, res) {
  try {
    const normalized = normalizeUrl(target);
    const r = await fetchRaw(normalized, {
      accept: "image/*,*/*;q=0.8",
      headers: { Referer: "https://www.xiaohongshu.com/" },
    });
    const ct = r.headers["content-type"] || "image/jpeg";
    res.writeHead(r.statusCode, {
      "Content-Type": ct,
      "Access-Control-Allow-Origin": "*",
      "Cache-Control": "public, max-age=3600",
    });
    res.end(r.body);
  } catch (err) {
    send(res, 502, "image proxy failed: " + err.message, "text/plain; charset=utf-8");
  }
}

function serveStatic(req, res, pathname) {
  if (pathname === "/") pathname = "/index.html";
  const safe = path.normalize(pathname).replace(/^(\.\.[\\/])+/, "");
  const filePath = path.join(ROOT, safe);
  if (!filePath.startsWith(ROOT)) {
    return send(res, 403, "forbidden", "text/plain; charset=utf-8");
  }
  fs.readFile(filePath, (err, data) => {
    if (err) {
      return send(res, 404, "not found", "text/plain; charset=utf-8");
    }
    const mime = MIME[path.extname(filePath).toLowerCase()] || "application/octet-stream";
    res.writeHead(200, { "Content-Type": mime });
    res.end(data);
  });
}

const server = http.createServer(async (req, res) => {
  try {
    const u = new URL(req.url, `http://${req.headers.host || "localhost"}`);

    // CORS preflight
    if (req.method === "OPTIONS") {
      res.writeHead(204, { "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "GET,POST", "Access-Control-Allow-Headers": "Content-Type" });
      return res.end();
    }

    if (u.pathname === "/api/cookie") {
      if (req.method === "GET") {
        return send(res, 200, JSON.stringify(cookieStatus()), "application/json; charset=utf-8");
      }
      if (req.method === "POST") {
        if (COOKIE_LOCKED_BY_ENV) {
          return send(res, 403, JSON.stringify({ error: "Cookie 由环境变量 XHS_COOKIE 锁定，无法通过界面修改。" }), "application/json; charset=utf-8");
        }
        let body;
        try { body = JSON.parse(await readBody(req)); } catch (e) { body = {}; }
        const cookie = typeof body.cookie === "string" ? body.cookie.trim() : "";
        XHS_COOKIE = cookie;
        saveCookieToDisk(cookie);
        console.log(cookie ? `Cookie 已更新（长度 ${cookie.length}）` : "Cookie 已清空");
        return send(res, 200, JSON.stringify(cookieStatus()), "application/json; charset=utf-8");
      }
    }

    if (u.pathname === "/api/llm-status") {
      return send(res, 200, JSON.stringify(llmStatus()), "application/json; charset=utf-8");
    }

    if (u.pathname === "/api/llm-config") {
      if (req.method !== "POST") {
        return send(res, 405, JSON.stringify({ error: "method not allowed" }), "application/json; charset=utf-8");
      }
      let body;
      try { body = JSON.parse(await readBody(req)); } catch (e) { body = {}; }
      if (OPENAI_KEY_LOCKED_BY_ENV && (body.clearKey || body.apiKey)) {
        return send(res, 403, JSON.stringify({ error: "API Key 由环境变量 OPENAI_API_KEY 锁定，无法通过界面修改。" }), "application/json; charset=utf-8");
      }
      const previousProvider = LLM_PROVIDER;
      const previousDefaultModel = defaultModelForProvider(previousProvider);
      if (typeof body.provider === "string" && body.provider.trim()) {
        LLM_PROVIDER = normalizeProvider(body.provider);
      }
      if (body.clearKey) {
        OPENAI_API_KEY = "";
      } else if (typeof body.apiKey === "string" && body.apiKey.trim()) {
        OPENAI_API_KEY = body.apiKey.trim();
        const inferred = inferProviderFromApiKey(OPENAI_API_KEY);
        if (inferred && inferred !== LLM_PROVIDER) {
          LLM_PROVIDER = inferred;
        }
      }
      const bodyModel = typeof body.model === "string" ? body.model.trim() : "";
      if (bodyModel && !(LLM_PROVIDER !== previousProvider && bodyModel === previousDefaultModel)) {
        OPENAI_MODEL = body.model.trim();
      } else if (!OPENAI_MODEL || LLM_PROVIDER !== previousProvider) {
        OPENAI_MODEL = defaultModelForProvider(LLM_PROVIDER);
      }
      const bodyBaseUrl = typeof body.baseUrl === "string" ? body.baseUrl.trim() : "";
      if (bodyBaseUrl && !(LLM_PROVIDER !== previousProvider && bodyBaseUrl.replace(/\/+$/, "") === defaultBaseUrlForProvider(previousProvider).replace(/\/+$/, ""))) {
        OPENAI_BASE_URL = bodyBaseUrl.replace(/\/+$/, "");
      } else {
        OPENAI_BASE_URL = defaultBaseUrlForProvider(LLM_PROVIDER).replace(/\/+$/, "");
      }
      if (typeof body.sendImage === "boolean") {
        LLM_SEND_IMAGE = body.sendImage;
      } else if (LLM_PROVIDER !== previousProvider) {
        LLM_SEND_IMAGE = defaultSendImageForProvider(LLM_PROVIDER);
      }
      saveLlmConfigToDisk();
      console.log(OPENAI_API_KEY ? `LLM 配置已更新（${LLM_PROVIDER} / ${OPENAI_MODEL}）` : "LLM API Key 已清空");
      return send(res, 200, JSON.stringify(llmStatus()), "application/json; charset=utf-8");
    }

    if (u.pathname === "/api/llm-predict") {
      if (req.method !== "POST") {
        return send(res, 405, JSON.stringify({ error: "method not allowed" }), "application/json; charset=utf-8");
      }
      let body;
      try { body = JSON.parse(await readBody(req)); } catch (e) { body = {}; }
      return handleLlmPredict(body, res);
    }

    if (u.pathname === "/api/fetch-post") {
      const target = u.searchParams.get("url");
      if (!target) {
        return send(res, 400, JSON.stringify({ error: "缺少 url 参数" }), "application/json; charset=utf-8");
      }
      return handleFetchPost(target, res);
    }
    if (u.pathname === "/api/image-proxy") {
      const target = u.searchParams.get("url");
      if (!target) return send(res, 400, "missing url", "text/plain; charset=utf-8");
      return handleImageProxy(target, res);
    }
    return serveStatic(req, res, u.pathname);
  } catch (err) {
    return send(res, 500, JSON.stringify({ error: err.message }), "application/json; charset=utf-8");
  }
});

server.listen(PORT, () => {
  console.log(`小红书加热判断工具运行中：http://localhost:${PORT}`);
  console.log("在浏览器里打开上面的地址即可。Ctrl+C 退出。");
});
