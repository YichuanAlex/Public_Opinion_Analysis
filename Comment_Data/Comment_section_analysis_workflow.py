#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
评论区分析工作流 - 标准 Python 版

用途：
    将原 Dify/Coze 评论区分析工作流迁移为可本地或服务端运行的 Python 脚本。

核心能力：
    1. 读取社媒助手导出的 Excel/CSV/JSON 评论数据。
    2. 按列名识别“评论内容”列，不依赖固定 B 列。
    3. 支持多个关键词，统计各关键词命中条数、任一关键词命中条数和占比。
    4. 对全量评论做词典法情感分析，不只依赖大模型抽样推断。
    5. 高频词按“提及评论数/占比”统计，默认剔除表情类词，如“偷笑”“笑哭”等。
    6. 按点赞量、关键词命中、负面反馈进行加权抽样，再交给大模型归纳核心讨论焦点。
    7. 可生成词云图、报告 Markdown、统计 JSON、Top 词 CSV、抽样评论文本。
    8. 可选上传报告到内部云盘，上传参数通过环境变量配置。

依赖：
    必需：pandas, openpyxl, requests
    可选：jieba, wordcloud, matplotlib, pillow

安装：
    pip install pandas openpyxl requests jieba wordcloud matplotlib pillow

大模型配置：
    export LLM_API_KEY="你的 API Key"

示例：
    python comment_analysis_workflow_final.py \
      --input comments.xlsx \
      --target-keyword "滴滴,滑雪,教练" \
      --model glm-5.1-internal \
      --output-dir ./output

安全说明：
    不建议把 API Key 写入脚本或提交到代码仓库。本脚本默认从 LLM_API_KEY 或 OPENAI_API_KEY 读取。
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import os
import random
import re
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple
from urllib.parse import unquote, urlparse

import pandas as pd
import requests


# =========================
# 1. 大模型配置
# =========================

DEFAULT_BASE_URL = "https://llm-proxy.intra.xiaojukeji.com"
DEFAULT_MODEL = "glm-5.1-internal"

# 这里只做提示，不做强校验。实际平台如果新增模型，可以直接用 --model 指定。
KNOWN_MODEL_OPTIONS = [
    "kimi-k2.5-external",
    "minimax-m2.5-external",
    "glm-5.1-external",
    "glm-5-external",
    "glm-5-internal",
    "glm-5.1-internal",
]


# =========================
# 2. 情感词典
#    可用 --positive-words/--negative-words 追加自定义词表
# =========================

POSITIVE_WORDS: Set[str] = {
    # 基础正面
    "好", "棒", "赞", "优", "美", "香", "强", "牛", "妙", "佳", "爽", "赢", "稳", "准",
    # 常用正面词
    "好用", "方便", "快捷", "安全", "准时", "贴心", "舒适", "满意", "推荐", "感谢",
    "喜欢", "不错", "厉害", "专业", "靠谱", "实惠", "划算", "高效", "友好", "热情",
    "好评", "给力", "完美", "超棒", "很好", "非常好", "太好了", "开心", "愉快",
    "顺利", "省心", "放心", "暖心", "用心", "细心", "耐心", "称心", "超值", "点赞",
    "值得", "性价比", "蛮好", "挺好", "相当好", "真的好", "果然好", "确实好",
    "强推", "必推", "安利", "无敌", "绝了", "绝绝子", "太绝了", "爱了", "爱了爱了",
    "好棒", "好赞", "好香", "好爽", "好强", "好牛", "超好", "超赞", "超棒", "超爽",
    "yyds", "YYDS", "nice", "厉害了", "牛啊", "牛逼", "nb",
    "感动", "暖", "温暖", "走心", "舒心", "欢喜",
    "合适", "满足", "惊喜", "期待", "支持", "鼓励", "认可", "信任", "信赖",
    "好服务", "好态度", "好体验", "好司机", "好快", "好准", "好便宜", "好方便",
    "没问题", "完全没问题", "相当不错", "还挺好", "还不错", "算不错", "挺不错",
    "舒服", "顺畅", "流畅", "丝滑", "秒到", "飞快", "超快", "很快", "挺快", "蛮快",
    # 出行/服务场景
    "直达", "省力", "省钱", "省时间", "不用转车", "不用换乘", "准点", "准时到", "接送方便",
    "服务好", "态度好", "师傅好", "司机好", "车干净", "车况好", "体验好", "出行方便",
    "便利", "便捷", "实用", "贴合需求", "解决痛点", "值得体验", "值得推荐",
}

NEGATIVE_WORDS: Set[str] = {
    # 基础负面
    "差", "烂", "坏", "慢", "贵", "坑", "骗", "假", "臭", "糟", "垃圾", "烦", "气",
    # 常用负面词
    "难用", "麻烦", "不稳", "不准", "不满", "投诉", "退款", "骚扰", "欺骗", "虚假",
    "不靠谱", "太贵", "太慢", "太差", "很差", "非常差", "极差", "难受", "烦躁",
    "愤怒", "生气", "郁闷", "无语", "崩溃", "绝望", "恶心", "恶劣", "故障",
    "不好", "不行", "不合理", "不专业", "不负责", "没服务", "没态度",
    "太坑", "真坑", "被坑", "踩坑", "宰客", "黑心", "坑钱", "浪费", "后悔", "踩雷",
    "差评", "恶评", "投诉", "举报", "退钱", "赔偿", "维权", "拉黑", "卸载", "不用了",
    "失望", "大失所望", "非常失望", "超级失望", "很失望", "太失望",
    "离谱", "太离谱", "真离谱", "也太离谱", "不像话", "说不过去", "没法忍",
    "绕路", "乱收费", "多收", "乱扣", "扣费", "乱扣费", "自动扣", "强制扣",
    "等太久", "等好久", "等了很久", "迟到", "超时", "没来", "放鸽子", "爽约",
    "态度差", "态度恶劣", "服务差", "服务烂", "体验差", "体验烂", "体验极差",
    "不安全", "危险", "超速", "闯红灯", "违规", "事故", "出事", "吓到", "吓死",
    "脏", "臭", "异味", "破", "旧", "破旧", "破烂", "车况差",
    "骗人", "坑人", "黑店", "黑车", "无良", "恶意", "故意",
    # 出行/平台场景
    "抢不到", "抢票难", "找不到入口", "没有入口", "入口难找", "班次少", "班次不够",
    "取消订单", "随意取消", "提前倒计时", "未到起点", "司机未到", "司机抽烟", "抽烟",
    "资质问题", "审核不严", "安全隐患", "投诉无门", "处理慢", "客服差", "客服不处理",
    "软广", "硬广", "广告太硬", "植入", "反感植入", "反感广告",
}

# 网络短表达。注意：表情包词不放这里，表情包词主要用于高频词剔除。
DIRECT_POSITIVE: Set[str] = {
    "哈哈", "哈哈哈", "哈哈哈哈", "hh", "hhh", "嘻嘻", "嘿嘿", "嘎嘎",
    "好哒", "好滴", "阔以", "可以的", "行的", "妥", "稳的", "没毛病",
    "冲", "冲冲", "冲啊", "来了", "安排", "已安排", "已到", "到了", "秒到",
    "感谢司机", "感谢师傅", "师傅辛苦", "辛苦了", "感恩", "比心", "爱心",
}

DIRECT_NEGATIVE: Set[str] = {
    "服了", "无了", "裂开", "蚌埠住了", "救命", "算了", "不想说了", "懒得说",
    "说多了都是泪", "心态崩了", "破防了", "自闭了", "黑名单", "永不再用",
    "再也不用", "最后一次", "第一次也是最后一次",
}

NEGATION_WORDS: Set[str] = {"不", "没", "无", "非", "别", "未", "莫", "勿", "毫不", "并不", "从不", "绝不"}
DEGREE_HIGH: Set[str] = {"非常", "超级", "极其", "特别", "十分", "相当", "真的", "确实", "太", "很", "超", "贼", "巨"}
DEGREE_LOW: Set[str] = {"有点", "有些", "稍微", "略微", "一点", "还算", "还好", "勉强", "将就"}


# =========================
# 3. 高频词/词云配置
# =========================

# 表情包/emoji 文本：高频词和词云中默认剔除。
EMOJI_WORDS: Set[str] = {
    "偷笑", "笑哭", "飞吻", "哭惹", "捂脸", "害羞", "大笑", "微笑", "萌萌哒", "笑", "哭",
    "点赞", "比心", "爱心", "玫瑰", "抱抱", "鼓掌", "呲牙", "调皮", "可怜", "委屈",
    "破涕为笑", "泪奔", "流泪", "发呆", "发怒", "尴尬", "惊讶", "疑问", "OK", "ok",
}

STOP_WORDS: Set[str] = {
    "我们", "你们", "他们", "她们", "它们", "感觉", "觉得", "时候", "应该", "然后",
    "因为", "所以", "但是", "如果", "还是", "已经", "现在", "就是", "好的", "好像",
    "看到", "这里", "那里", "其实", "知道", "可以", "大家", "自己", "真的", "这个",
    "那个", "什么", "怎么", "这么", "那么", "有点", "一下", "一直", "一次", "出来",
    "不会", "不能", "不要", "不是", "没有", "还有", "一个", "一种", "一条", "一点",
    "这么多", "为什么", "是不是", "的时候", "哈哈", "哈哈哈", "哈哈哈哈", "hhh", "hh",
    "啊啊", "啊啊啊", "呜呜", "呜呜呜", "哈哈哈哈哈", "评论", "评论区", "视频", "博主",
    "小红书", "抖音", "微博", "用户", "网友", "内容", "相关", "这种", "这种话", "不是吧",
}

BAD_CHARS_IN_TERM: Set[str] = set("的了是就有在你也我他她它与及和着这那啊太很没去哈呵嘻哎呀哇哦嗯呜唉呢呗吧吗喔啦呀嘛欸噢")

# 根据历史样例前置的领域词，避免 n-gram 拆成“言人”“人檀”等碎词。
DOMAIN_WORDS: Set[str] = {
    "滴滴", "司机", "师傅", "乘客", "客服", "订单", "打车", "网约车", "出行", "通勤出行",
    "出行成本", "车费", "车费返现", "特惠一口价", "抽烟", "山东司机", "接单效率",
    "停车难", "养车成本", "宠物", "下载APP", "下载 APP", "安全", "司机资质", "资质审核",
    "提前倒计时", "取消订单", "随意取消", "未到起点",
    "滑雪", "教练", "滑雪教练", "崇礼", "滑雪场", "雪场", "万龙滑雪场", "单板", "双板",
    "新手", "雪板", "雪具", "雪服", "滑雪服", "护具", "拍照", "冬天", "拼车", "拼房",
    "拼车拼房", "滑雪专线", "滴滴滑雪专线", "滑雪专线巴士", "站点巴士", "直通雪场",
    "北京", "上海", "周末滑雪", "雪场选择", "滑雪攻略", "装备", "穿搭", "购票", "门票",
    "檀健次", "健次", "代言人", "代言", "粉丝", "明星代言", "檀健次代言", "一起滑雪",
    "旅行", "辞职旅行", "生活方式", "松弛感", "自由", "好心态",
}

# 历史样例中的碎词归并。可用 --alias-file 追加。
DEFAULT_TERM_ALIASES: Dict[str, str] = {
    "檀健": "檀健次",
    "健次": "檀健次",
    "人檀": "檀健次",
    "言人": "代言人",
    "代言": "代言人",
    "滴滴滑雪专线": "滑雪专线",
    "滑雪专线巴士": "滑雪专线",
    "站点巴士": "滴滴站点巴士",
    "下载 APP": "下载APP",
}

EXPRESSION_PATTERN = re.compile(r"\[[^\[\]]{1,20}\]")
URL_PATTERN = re.compile(r"https?://\S+")
CHINESE_PATTERN = re.compile(r"[\u4e00-\u9fa5]")


# =========================
# 4. 大模型提示词
# =========================

SYSTEM_PROMPT = """你是一个专业的社媒舆情分析专家。前置 Python 程序已经完成全量数据统计、多关键词拆分、全量词典情感分析、高频词提取和加权抽样。你的任务是基于这些结果输出规范报告。

硬性要求：
1. 严格使用输入中的统计数值，禁止自己重新计算条数、占比、情感分布。
2. 高频词已经剔除表情类词，如“偷笑”“笑哭”“飞吻”“捂脸”等；不要再把表情、语气词、无意义碎词作为核心话题。
3. 核心讨论焦点必须来自评论抽样和高频词，写出具体讨论内容或具体诉求，不要写“用户表示”“评论区讨论”等空泛句。
4. 如果输入里有负面样本或负面关键词，结论要客观提及主要负面诉求，不要过度乐观。
5. 不要输出你自己的计算过程，不要解释方法。

输出模板必须如下，结构、emoji 和标题保持一致：
📊 **评论舆情分析报告**
---
1️⃣ **关键词搜索分析**
- 目标检索词：[填入目标检索词]
- 总评论基数：[填入总评论基数] 条
- 命中关键词的评论：[填入命中数]条（占比 [填入占比]）
- 关键词明细：[填入关键词明细]
---
2️⃣ **全量情感分析**（基于 [填入总评论基数] 条总评论）
- 整体分布：[填入整体情感分布]
- 💡 舆情结论：[根据数据填写一句话总结整体情绪倾向，必要时提及主要负面诉求]
---
3️⃣ **高频词 Top 10**
[填入高频词 Top 10]
---
4️⃣ **核心讨论焦点**
- 🎯 [焦点一：具体讨论内容或赞点/痛点]
- 🎯 [焦点二：具体讨论内容或赞点/痛点]
- 🎯 [焦点三：具体讨论内容或赞点/痛点]
"""


# =========================
# 5. 通用工具函数
# =========================

def safe_text(value: Any) -> str:
    """把 Excel 单元格值安全转成文本，避免 int/float 没有 strip 的错误。"""
    if value is None:
        return ""
    try:
        if isinstance(value, float) and math.isnan(value):
            return ""
    except Exception:
        pass
    text = str(value).strip()
    if text.lower() in {"nan", "none", "null"}:
        return ""
    return text


def pct(numerator: int, denominator: int, digits: int = 1) -> str:
    if denominator <= 0:
        return f"{0:.{digits}f}%"
    return f"{numerator / denominator * 100:.{digits}f}%"


def split_keywords(raw_keyword: str) -> List[str]:
    raw_keyword = safe_text(raw_keyword)
    if not raw_keyword:
        return ["未指定关键词"]
    # 支持：中文逗号、英文逗号、顿号、分号、竖线、空白
    parts = re.split(r"[,，、;；|｜\s]+", raw_keyword)
    keywords = [p.strip(" '\"\t\r\n") for p in parts if p and p.strip(" '\"\t\r\n")]
    return keywords or [raw_keyword]


def load_word_list(path: Optional[Path]) -> Set[str]:
    if not path:
        return set()
    if not path.exists():
        raise FileNotFoundError(f"词表文件不存在：{path}")
    words: Set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # 支持一行多个词，用逗号分隔
        for part in re.split(r"[,，、;；|｜\s]+", line):
            part = part.strip()
            if part:
                words.add(part)
    return words


def load_alias_file(path: Optional[Path]) -> Dict[str, str]:
    """加载别名文件。格式：source,target；也支持 tab 分隔。"""
    if not path:
        return {}
    if not path.exists():
        raise FileNotFoundError(f"别名文件不存在：{path}")
    aliases: Dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "," in line:
            src, dst = line.split(",", 1)
        elif "\t" in line:
            src, dst = line.split("\t", 1)
        else:
            continue
        src = src.strip()
        dst = dst.strip()
        if src and dst:
            aliases[src] = dst
    return aliases


def normalize_base_url(base_url: str) -> str:
    base = safe_text(base_url).rstrip("/")
    if base.endswith("/v1"):
        return base
    return base + "/v1"


def is_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def download_input_file(url: str, output_dir: Path, timeout: int = 120) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    parsed = urlparse(url)
    guessed_name = Path(unquote(parsed.path)).name or "comments.xlsx"
    if not Path(guessed_name).suffix:
        guessed_name += ".xlsx"
    local_path = output_dir / guessed_name
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    local_path.write_bytes(response.content)
    return local_path


def resolve_input_path(input_value: str, cache_dir: Path) -> Path:
    if is_url(input_value):
        return download_input_file(input_value, cache_dir)
    return Path(input_value).expanduser().resolve()


# =========================
# 6. 读取 Excel/CSV/JSON
# =========================

COMMENT_COLUMN_CANDIDATES = [
    "评论内容", "一级评论内容", "评论", "内容", "正文", "笔记评论内容", "comment", "comments", "content", "text",
]

LIKE_COLUMN_CANDIDATES = [
    "点赞量", "点赞数", "点赞", "赞数", "赞", "like_count", "likes", "like", "digg_count",
]


def read_dataframe(input_path: Path, sheet_name: Optional[str] = None) -> pd.DataFrame:
    suffix = input_path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        sheet_arg: Any = 0 if sheet_name is None else sheet_name
        df = pd.read_excel(input_path, sheet_name=sheet_arg, dtype=object)
        return df
    if suffix == ".csv":
        last_error: Optional[Exception] = None
        for encoding in ("utf-8-sig", "utf-8", "gb18030", "gbk"):
            try:
                return pd.read_csv(input_path, dtype=object, encoding=encoding)
            except UnicodeDecodeError as exc:
                last_error = exc
        raise ValueError(f"CSV 编码无法识别，请转换为 UTF-8 或 GB18030 后重试：{last_error}")
    if suffix == ".json":
        raw = json.loads(input_path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            raw = raw.get("data", raw.get("items", raw.get("records", [])))
        if not isinstance(raw, list):
            raise ValueError("JSON 顶层需要是 list，或包含 data/items/records 字段。")
        return pd.DataFrame(raw)
    raise ValueError(f"不支持的文件类型：{suffix}。请使用 .xlsx/.xls/.csv/.json")


def normalize_column_name(name: Any) -> str:
    return re.sub(r"\s+", "", safe_text(name)).lower()


def detect_column(df: pd.DataFrame, candidates: Sequence[str], contains_keyword: Optional[str] = None) -> Optional[str]:
    if df.empty or len(df.columns) == 0:
        return None
    normalized_to_original: Dict[str, str] = {normalize_column_name(col): str(col) for col in df.columns}
    for cand in candidates:
        key = normalize_column_name(cand)
        if key in normalized_to_original:
            return normalized_to_original[key]

    if contains_keyword:
        for col in df.columns:
            col_text = str(col)
            if contains_keyword in col_text and "ID" not in col_text.upper() and "数" not in col_text:
                return col_text
    return None


def detect_comment_column(df: pd.DataFrame, user_column: Optional[str] = None) -> str:
    if user_column:
        if user_column not in df.columns:
            raise ValueError(f"指定的评论列不存在：{user_column}。实际列名：{list(df.columns)}")
        return user_column

    detected = detect_column(df, COMMENT_COLUMN_CANDIDATES, contains_keyword="评论")
    if detected:
        return detected

    # 兜底：选择平均文本长度较长且非空率较高的列。
    best_col: Optional[str] = None
    best_score = -1.0
    for col in df.columns:
        values = [safe_text(v) for v in df[col].head(500).tolist()]
        non_empty = [v for v in values if v]
        if not non_empty:
            continue
        avg_len = sum(len(v) for v in non_empty) / len(non_empty)
        non_empty_rate = len(non_empty) / max(len(values), 1)
        score = avg_len * non_empty_rate
        if score > best_score:
            best_score = score
            best_col = str(col)
    if best_col:
        return best_col
    raise ValueError("无法识别评论内容列。建议使用 --comment-column 指定，例如 --comment-column 评论内容")


def detect_like_column(df: pd.DataFrame, user_column: Optional[str] = None) -> Optional[str]:
    if user_column:
        if user_column not in df.columns:
            raise ValueError(f"指定的点赞列不存在：{user_column}。实际列名：{list(df.columns)}")
        return user_column
    return detect_column(df, LIKE_COLUMN_CANDIDATES, contains_keyword="赞")


def parse_like_count(value: Any) -> int:
    text = safe_text(value).replace(",", "")
    if not text:
        return 0
    try:
        # 1.2万、3w、4k
        lower = text.lower()
        multiplier = 1.0
        if lower.endswith("万"):
            multiplier = 10000.0
            lower = lower[:-1]
        elif lower.endswith("w"):
            multiplier = 10000.0
            lower = lower[:-1]
        elif lower.endswith("k"):
            multiplier = 1000.0
            lower = lower[:-1]
        number = float(re.sub(r"[^0-9.\-]", "", lower) or 0)
        return max(0, int(number * multiplier))
    except Exception:
        return 0


def normalize_comments(
    df: pd.DataFrame,
    comment_column: Optional[str] = None,
    like_column: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], str, Optional[str]]:
    if df.empty:
        raise ValueError("输入文件没有数据。")
    df = df.astype(object).where(pd.notna(df), "")
    real_comment_col = detect_comment_column(df, comment_column)
    real_like_col = detect_like_column(df, like_column)

    comments_data: List[Dict[str, Any]] = []
    for idx, row in df.iterrows():
        comment = safe_text(row.get(real_comment_col, ""))
        if not comment:
            continue
        likes = parse_like_count(row.get(real_like_col, 0)) if real_like_col else 0
        comments_data.append({"text": comment, "likes": likes, "row_index": int(idx) + 2})

    if not comments_data:
        raise ValueError(f"已识别评论列“{real_comment_col}”，但未读取到有效评论内容。")
    return comments_data, real_comment_col, real_like_col


# =========================
# 7. 关键词统计
# =========================

def compute_keyword_stats(comments_list: Sequence[str], raw_keyword: str) -> Dict[str, Any]:
    keywords = split_keywords(raw_keyword)
    total_count = len(comments_list)
    keyword_counts: Dict[str, int] = {kw: 0 for kw in keywords}
    any_keyword_hit = 0
    keyword_hit_flags: List[bool] = []

    for text in comments_list:
        text_lower = text.lower()
        matched_any = False
        for kw in keywords:
            kw_norm = kw.lower()
            if kw_norm and kw_norm in text_lower:
                keyword_counts[kw] += 1
                matched_any = True
        keyword_hit_flags.append(matched_any)
        if matched_any:
            any_keyword_hit += 1

    details = " ｜ ".join(
        f"'{kw}' ({count}条，占比 {pct(count, total_count, digits=1)})"
        for kw, count in keyword_counts.items()
    )
    return {
        "keywords": keywords,
        "keyword_counts": keyword_counts,
        "keyword_count": any_keyword_hit,
        "keyword_ratio": pct(any_keyword_hit, total_count, digits=2),
        "keyword_details": details,
        "keyword_hit_flags": keyword_hit_flags,
    }


# =========================
# 8. 全量情感分析
# =========================

def clean_for_sentiment(text: str) -> str:
    text = URL_PATTERN.sub("", safe_text(text))
    text = EXPRESSION_PATTERN.sub("", text)
    return text.strip()


def _has_negation(context: str) -> bool:
    return any(word in context for word in NEGATION_WORDS)


def _degree_weight(context: str) -> float:
    if any(word in context for word in DEGREE_HIGH):
        return 1.5
    if any(word in context for word in DEGREE_LOW):
        return 0.6
    return 1.0


def _overlap(span: Tuple[int, int], spans: Sequence[Tuple[int, int]]) -> bool:
    start, end = span
    for s, e in spans:
        if start < e and s < end:
            return True
    return False


def analyze_sentiment(text: str, positive_words: Set[str], negative_words: Set[str]) -> str:
    """
    返回 positive / negative / neutral。

    设计取舍：
    - 不再采用“没有命中且短评论默认正面”的逻辑，避免把纯表情、纯语气词判得过乐观。
    - 单字词权重较低，长词优先，避免“好/差”等单字过度影响结果。
    - 仍然保留“哈哈、支持、感谢”等网络表达的正面倾向。
    """
    text_clean = clean_for_sentiment(text)
    if not text_clean:
        return "neutral"

    pos_score = 0.0
    neg_score = 0.0
    used_spans: List[Tuple[int, int]] = []

    terms: List[Tuple[str, str]] = []
    terms.extend((w, "positive") for w in positive_words | DIRECT_POSITIVE)
    terms.extend((w, "negative") for w in negative_words | DIRECT_NEGATIVE)
    terms = [(w, label) for w, label in terms if w]
    terms.sort(key=lambda item: len(item[0]), reverse=True)

    lower_text = text_clean.lower()
    for word, label in terms:
        word_lower = word.lower()
        start = 0
        while True:
            idx = lower_text.find(word_lower, start)
            if idx < 0:
                break
            span = (idx, idx + len(word_lower))
            start = idx + max(1, len(word_lower))
            if _overlap(span, used_spans):
                continue
            used_spans.append(span)

            context = text_clean[max(0, idx - 6):idx]
            weight = _degree_weight(context)
            if len(word) == 1:
                weight *= 0.45
            if label == "positive":
                if _has_negation(context):
                    neg_score += weight
                else:
                    pos_score += weight
            else:
                if _has_negation(context):
                    pos_score += weight * 0.6
                else:
                    neg_score += weight

    if pos_score == 0 and neg_score == 0:
        return "neutral"

    total = pos_score + neg_score
    ratio = pos_score / total if total else 0.5
    if pos_score - neg_score >= 0.6 and ratio >= 0.55:
        return "positive"
    if neg_score - pos_score >= 0.6 or ratio <= 0.4:
        return "negative"
    return "neutral"


def compute_sentiment_stats(
    comments_data: Sequence[Dict[str, Any]],
    positive_words: Set[str],
    negative_words: Set[str],
) -> Dict[str, Any]:
    pos_count = neg_count = neu_count = 0
    labels: List[str] = []
    negative_samples: List[Dict[str, Any]] = []

    for item in comments_data:
        label = analyze_sentiment(item["text"], positive_words, negative_words)
        labels.append(label)
        if label == "positive":
            pos_count += 1
        elif label == "negative":
            neg_count += 1
            negative_samples.append(item)
        else:
            neu_count += 1

    total_count = len(comments_data)
    sentiment_summary = (
        f"正面 {pos_count} 条（{pct(pos_count, total_count, digits=1)}）｜"
        f"负面 {neg_count} 条（{pct(neg_count, total_count, digits=1)}）｜"
        f"中性 {neu_count} 条（{pct(neu_count, total_count, digits=1)}）"
    )
    return {
        "sentiment_labels": labels,
        "pos_count": pos_count,
        "neg_count": neg_count,
        "neu_count": neu_count,
        "pos_ratio": pct(pos_count, total_count, digits=1),
        "neg_ratio": pct(neg_count, total_count, digits=1),
        "neu_ratio": pct(neu_count, total_count, digits=1),
        "sentiment_summary": sentiment_summary,
        "negative_samples": negative_samples,
    }


# =========================
# 9. 高频词/词云词频
# =========================

def clean_for_terms(text: str) -> str:
    text = safe_text(text)
    text = URL_PATTERN.sub("", text)
    text = EXPRESSION_PATTERN.sub("", text)
    # 常见分隔符保留为空格，方便分词
    text = re.sub(r"[#@/\\|,，。.!！?？:：;；（）()\[\]{}<>《》\"'“”‘’、\n\r\t]+", " ", text)
    return text.strip()


def is_valid_term(term: str, stop_words: Set[str], emoji_words: Set[str]) -> bool:
    term = safe_text(term)
    if not term:
        return False
    if term in stop_words or term in emoji_words:
        return False
    if len(term) < 2:
        return False
    if not CHINESE_PATTERN.search(term) and not re.search(r"[A-Za-z]", term):
        return False
    if len(term) <= 3 and any(ch in BAD_CHARS_IN_TERM for ch in term):
        return False
    if EXPRESSION_PATTERN.fullmatch(term):
        return False
    # 纯重复字符通常是语气词，例如 哈哈、啊啊。
    if len(set(term)) == 1 and len(term) <= 4:
        return False
    return True


def get_jieba_tokenizer(domain_words: Set[str]) -> Optional[Any]:
    try:
        import jieba  # type: ignore
    except Exception:
        return None
    for word in sorted(domain_words, key=len, reverse=True):
        if len(word) >= 2:
            try:
                jieba.add_word(word, freq=200000)
            except Exception:
                pass
    return jieba


def tokenize_with_jieba(text: str, jieba_module: Any) -> List[str]:
    return [safe_text(w) for w in jieba_module.lcut(clean_for_terms(text)) if safe_text(w)]


def extract_domain_phrases(text: str, domain_words: Set[str]) -> Set[str]:
    terms: Set[str] = set()
    for word in sorted(domain_words, key=len, reverse=True):
        if len(word) >= 2 and word in text:
            terms.add(word)
    return terms


def extract_ngram_terms(text: str, min_len: int = 2, max_len: int = 4) -> Set[str]:
    text = re.sub(r"[^\u4e00-\u9fa5A-Za-z0-9]", "", clean_for_terms(text))
    terms: Set[str] = set()
    # 中文 ngram
    chinese_text = "".join(re.findall(r"[\u4e00-\u9fa5]+", text))
    for n in range(min_len, max_len + 1):
        for i in range(0, max(0, len(chinese_text) - n + 1)):
            terms.add(chinese_text[i:i + n])
    # 英文/数字连续词
    for token in re.findall(r"[A-Za-z][A-Za-z0-9_\-]{1,}", text):
        terms.add(token)
    return terms


def apply_alias(term: str, aliases: Mapping[str, str]) -> str:
    return aliases.get(term, term)


def suppress_substrings(counter: Counter) -> Counter:
    """
    抑制明显碎词：如果短词是长词子串，且短词提及量没有显著高于长词，则删除短词。
    例：代言人 vs 言人；檀健次 vs 檀健。
    """
    result = Counter(counter)
    terms = sorted(result.keys(), key=lambda w: (len(w), result[w]), reverse=True)
    to_delete: Set[str] = set()
    for long_term in terms:
        if long_term in to_delete or len(long_term) < 3:
            continue
        long_count = result[long_term]
        for short_term in terms:
            if short_term == long_term or short_term in to_delete:
                continue
            if len(short_term) >= len(long_term):
                continue
            if len(short_term) < 2:
                continue
            if short_term in long_term and result[short_term] <= long_count * 1.35:
                to_delete.add(short_term)
    for term in to_delete:
        result.pop(term, None)
    return result


def compute_term_frequencies(
    comments_list: Sequence[str],
    keywords: Sequence[str],
    domain_words: Set[str],
    stop_words: Set[str],
    emoji_words: Set[str],
    aliases: Mapping[str, str],
    top_n: int = 10,
    exclude_targets: bool = False,
) -> Tuple[List[Dict[str, Any]], Counter]:
    effective_domain_words = set(domain_words) | {kw for kw in keywords if len(kw) >= 2}
    jieba_module = get_jieba_tokenizer(effective_domain_words)
    target_set = {kw.lower() for kw in keywords}

    mention_counter: Counter = Counter()
    for comment in comments_list:
        cleaned = clean_for_terms(comment)
        per_comment_terms: Set[str] = set()
        per_comment_terms |= extract_domain_phrases(cleaned, effective_domain_words)

        if jieba_module is not None:
            per_comment_terms |= set(tokenize_with_jieba(cleaned, jieba_module))
        else:
            per_comment_terms |= extract_ngram_terms(cleaned)

        normalized_terms: Set[str] = set()
        for term in per_comment_terms:
            term = apply_alias(term, aliases)
            if exclude_targets and term.lower() in target_set:
                continue
            if is_valid_term(term, stop_words, emoji_words):
                normalized_terms.add(term)

        for term in normalized_terms:
            mention_counter[term] += 1

    mention_counter = suppress_substrings(mention_counter)

    total_count = len(comments_list)
    rows: List[Dict[str, Any]] = []
    for term, count in mention_counter.most_common():
        if count <= 1:
            continue
        rows.append({
            "term": term,
            "mention_count": int(count),
            "ratio": round((count / total_count * 100) if total_count else 0, 4),
        })
    return rows[:top_n], mention_counter


def format_top_terms(top_terms: Sequence[Mapping[str, Any]], style: str = "both") -> str:
    if not top_terms:
        return "无有效高频词"
    lines: List[str] = []
    for idx, row in enumerate(top_terms, start=1):
        term = row["term"]
        count = int(row["mention_count"])
        ratio = float(row["ratio"])
        if style == "ratio":
            lines.append(f"{idx}. {term} (占比 {ratio:.1f}%)")
        elif style == "count":
            lines.append(f"{idx}. {term} ({count} 条)")
        else:
            lines.append(f"{idx}. {term} (提及 {count} 条，占比 {ratio:.1f}%)")
    return "\n".join(lines)


# =========================
# 10. 加权抽样
# =========================

def weighted_sample_comments(
    comments_data: Sequence[Dict[str, Any]],
    keyword_hit_flags: Sequence[bool],
    sentiment_labels: Sequence[str],
    total_limit: int = 250,
    high_like_threshold: int = 100,
    high_like_limit: int = 100,
    keyword_limit: int = 60,
    negative_limit: int = 60,
    seed: int = 42,
) -> List[str]:
    """
    抽样策略：
    1. 高赞评论优先，避免丢失主要讨论方向。
    2. 关键词命中评论补充，确保和目标词相关。
    3. 负面评论补充，避免结论过度乐观。
    4. 剩余名额按点赞量加权随机抽样。
    """
    rng = random.Random(seed)
    selected: List[Dict[str, Any]] = []
    seen: Set[str] = set()

    def add_items(items: Iterable[Dict[str, Any]], limit: int) -> None:
        nonlocal selected, seen
        for item in items:
            if len(selected) >= total_limit or limit <= 0:
                break
            text = item["text"]
            if text in seen:
                continue
            selected.append(item)
            seen.add(text)
            limit -= 1

    high_like_items = sorted(
        [item for item in comments_data if int(item.get("likes", 0)) >= high_like_threshold],
        key=lambda item: int(item.get("likes", 0)),
        reverse=True,
    )
    add_items(high_like_items, high_like_limit)

    keyword_items = [item for item, hit in zip(comments_data, keyword_hit_flags) if hit]
    keyword_items = sorted(keyword_items, key=lambda item: int(item.get("likes", 0)), reverse=True)
    add_items(keyword_items, keyword_limit)

    negative_items = [item for item, label in zip(comments_data, sentiment_labels) if label == "negative"]
    negative_items = sorted(negative_items, key=lambda item: int(item.get("likes", 0)), reverse=True)
    add_items(negative_items, negative_limit)

    if len(selected) < total_limit:
        remaining = [item for item in comments_data if item["text"] not in seen]
        # 点赞量加权，但避免超高赞完全垄断。
        weights = [math.log1p(max(0, int(item.get("likes", 0)))) + 1.0 for item in remaining]
        while remaining and len(selected) < total_limit:
            chosen = rng.choices(remaining, weights=weights, k=1)[0]
            idx = remaining.index(chosen)
            selected.append(chosen)
            seen.add(chosen["text"])
            remaining.pop(idx)
            weights.pop(idx)

    return [item["text"] for item in selected[:total_limit]]


def format_sample_comments(sampled_comments: Sequence[str], max_chars: int = 18000) -> str:
    text = "\n".join(sampled_comments)
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n……（抽样评论因长度限制已截断）"


# =========================
# 11. 词云和文件输出
# =========================

def find_chinese_font() -> Optional[str]:
    env_font = os.getenv("WORDCLOUD_FONT_PATH")
    if env_font and Path(env_font).exists():
        return env_font
    candidates = [
        # macOS
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        # Linux common
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.otf",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/truetype/arphic/uming.ttc",
        # Windows
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/simsun.ttc",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate
    return None


def generate_wordcloud(
    frequencies: Counter,
    output_dir: Path,
    file_prefix: str = "评论词云图",
    width: int = 1200,
    height: int = 800,
) -> Tuple[Optional[Path], Optional[str]]:
    if not frequencies:
        return None, "无有效词频，未生成词云图。"
    try:
        from wordcloud import WordCloud  # type: ignore
    except Exception:
        return None, "未安装 wordcloud，跳过词云图生成。可执行：pip install wordcloud matplotlib pillow"

    output_dir.mkdir(parents=True, exist_ok=True)
    now = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"{file_prefix}_{now}.png"
    font_path = find_chinese_font()
    if font_path is None:
        warning = "未找到中文字体，词云可能无法正确显示中文。可设置 WORDCLOUD_FONT_PATH。"
    else:
        warning = None

    # 词云不需要太多低频词，取前 200 个。
    freqs = dict(frequencies.most_common(200))
    wc = WordCloud(
        width=width,
        height=height,
        background_color="white",
        font_path=font_path,
        max_words=200,
        collocations=False,
    )
    wc.generate_from_frequencies(freqs)
    wc.to_file(str(output_path))
    return output_path, warning


def save_text(text: str, output_dir: Path, prefix: str, suffix: str = ".md") -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    now = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = output_dir / f"{prefix}_{now}{suffix}"
    path.write_text(text, encoding="utf-8")
    return path


def save_json(data: Mapping[str, Any], output_dir: Path, prefix: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    now = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = output_dir / f"{prefix}_{now}.json"
    def default(obj: Any) -> Any:
        if isinstance(obj, Path):
            return str(obj)
        if isinstance(obj, Counter):
            return dict(obj)
        return str(obj)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=default), encoding="utf-8")
    return path


def save_top_terms_csv(top_terms: Sequence[Mapping[str, Any]], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    now = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = output_dir / f"高频词_{now}.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["rank", "term", "mention_count", "ratio"])
        writer.writeheader()
        for idx, row in enumerate(top_terms, start=1):
            writer.writerow({
                "rank": idx,
                "term": row["term"],
                "mention_count": row["mention_count"],
                "ratio": f"{float(row['ratio']):.4f}%",
            })
    return path


# =========================
# 12. 组装给大模型的数据
# =========================

def build_compiled_data(stats: Mapping[str, Any]) -> str:
    negative_preview = "\n".join(item["text"] for item in stats.get("negative_samples", [])[:30]) or "无明显负面样本"
    return f"""
- 目标检索词：{stats['target_keyword']}
- 总评论基数：{stats['total_count']} 条
- 命中关键词的评论：{stats['keyword_count']} 条（占比 {stats['keyword_ratio']}）
- 关键词明细：{stats['keyword_details']}
- 整体情感分布：{stats['sentiment_summary']}

【高频词 Top 10】
{stats['top_keywords_str']}

【负面样本预览】
{negative_preview}

【加权评论抽样】
{stats['sampled_comments']}
""".strip()


def call_llm_report(
    compiled_data: str,
    api_key: str,
    base_url: str = DEFAULT_BASE_URL,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.2,
    timeout: int = 180,
) -> str:
    url = normalize_base_url(base_url) + "/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "请基于以下统计结果和抽样评论生成报告：\n\n" + compiled_data},
        ],
        "temperature": temperature,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=timeout)
        response.raise_for_status()
        data = response.json()
    except requests.Timeout as exc:
        raise RuntimeError(f"大模型请求超时：{exc}") from exc
    except requests.RequestException as exc:
        body = getattr(exc.response, "text", "")[:1000] if getattr(exc, "response", None) is not None else ""
        raise RuntimeError(f"大模型请求失败：{exc}; response={body}") from exc
    except ValueError as exc:
        raise RuntimeError(f"大模型接口返回内容不是合法 JSON：{response.text[:1000]}") from exc

    try:
        return safe_text(data["choices"][0]["message"]["content"])
    except Exception as exc:
        raise RuntimeError(f"无法从大模型响应中读取文本：{json.dumps(data, ensure_ascii=False)[:1000]}") from exc


def build_fallback_report(stats: Mapping[str, Any]) -> str:
    """未调用大模型时的基础报告。"""
    if stats["pos_count"] >= stats["neg_count"] and stats["pos_count"] >= stats["neu_count"]:
        conclusion = "整体舆情偏正向。"
    elif stats["neg_count"] >= stats["pos_count"] and stats["neg_count"] >= stats["neu_count"]:
        conclusion = "整体舆情偏负向，需要重点关注负面反馈。"
    else:
        conclusion = "整体舆情以中性表达为主，需要结合具体样本判断讨论焦点。"

    return f"""📊 **评论舆情分析报告**
---
1️⃣ **关键词搜索分析**
- 目标检索词：{stats['target_keyword']}
- 总评论基数：{stats['total_count']} 条
- 命中关键词的评论：{stats['keyword_count']}条（占比 {stats['keyword_ratio']}）
- 关键词明细：{stats['keyword_details']}
---
2️⃣ **全量情感分析**（基于 {stats['total_count']} 条总评论）
- 整体分布：{stats['sentiment_summary']}
- 💡 舆情结论：{conclusion}
---
3️⃣ **高频词 Top 10**
{stats['top_keywords_str']}
---
4️⃣ **核心讨论焦点**
- 🎯 未调用大模型，建议结合高频词和抽样评论人工归纳焦点一。
- 🎯 未调用大模型，建议结合高频词和抽样评论人工归纳焦点二。
- 🎯 未调用大模型，建议结合高频词和抽样评论人工归纳焦点三。
"""


# =========================
# 13. 可选：上传内部云盘
# =========================

def upload_to_cloud_disk(report_text: str, file_name: str) -> Dict[str, str]:
    """
    对应原 YAML 中“代码执行 2”的上传逻辑。

    需要配置环境变量：
        CLOUD_DISK_APIKEY
        CLOUD_DISK_USERNAME
        CLOUD_DISK_GROUP_ID
        CLOUD_DISK_PARENT_ID

    可选：
        CLOUD_DISK_UPLOAD_URL
    """
    api_key = os.getenv("CLOUD_DISK_APIKEY")
    username = os.getenv("CLOUD_DISK_USERNAME")
    group_id = os.getenv("CLOUD_DISK_GROUP_ID")
    parent_id = os.getenv("CLOUD_DISK_PARENT_ID")
    upload_url = os.getenv(
        "CLOUD_DISK_UPLOAD_URL",
        "http://api-kylin.intra.xiaojukeji.com/EP_CLOUD_DISK_oe_openapi_cooper_server_prod/openapi/v1/files",
    )
    missing = [
        name for name, value in {
            "CLOUD_DISK_APIKEY": api_key,
            "CLOUD_DISK_USERNAME": username,
            "CLOUD_DISK_GROUP_ID": group_id,
            "CLOUD_DISK_PARENT_ID": parent_id,
        }.items() if not value
    ]
    if missing:
        raise RuntimeError("缺少云盘上传环境变量：" + ", ".join(missing))

    headers = {"Apikey": api_key, "username": username}
    files = {"file": (file_name, report_text.encode("utf-8"), "text/markdown")}
    try:
        response = requests.post(
            upload_url,
            headers=headers,
            files=files,
            data={"parentid": parent_id},
            params={"group_id": group_id},
            timeout=60,
        )
        response.raise_for_status()
        result = response.json()
    except Exception as exc:
        raise RuntimeError(f"云盘上传请求失败：{exc}") from exc

    if result.get("code") == 200:
        file_id = str(result.get("data", [{}])[0].get("id", ""))
        return {"success": "上传成功", "file_name": file_name, "file_id": file_id}
    return {
        "success": "上传失败",
        "file_name": file_name,
        "file_id": "",
        "error": json.dumps(result, ensure_ascii=False),
    }


# =========================
# 14. 主分析流程
# =========================

def analyze_comments(
    input_path: Path,
    target_keyword: str,
    sheet_name: Optional[str] = None,
    comment_column: Optional[str] = None,
    like_column: Optional[str] = None,
    positive_words_file: Optional[Path] = None,
    negative_words_file: Optional[Path] = None,
    stop_words_file: Optional[Path] = None,
    domain_words_file: Optional[Path] = None,
    alias_file: Optional[Path] = None,
    sample_seed: int = 42,
    sample_limit: int = 250,
    top_n: int = 10,
    top_format: str = "both",
    exclude_targets_in_top: bool = False,
) -> Dict[str, Any]:
    df = read_dataframe(input_path, sheet_name=sheet_name)
    comments_data, real_comment_col, real_like_col = normalize_comments(df, comment_column, like_column)
    comments_list = [item["text"] for item in comments_data]
    total_count = len(comments_data)

    positive_words = set(POSITIVE_WORDS) | load_word_list(positive_words_file)
    negative_words = set(NEGATIVE_WORDS) | load_word_list(negative_words_file)
    stop_words = set(STOP_WORDS) | load_word_list(stop_words_file)
    domain_words = set(DOMAIN_WORDS) | load_word_list(domain_words_file)
    aliases = dict(DEFAULT_TERM_ALIASES)
    aliases.update(load_alias_file(alias_file))

    keyword_stats = compute_keyword_stats(comments_list, target_keyword)
    sentiment_stats = compute_sentiment_stats(comments_data, positive_words, negative_words)

    top_terms, term_counter = compute_term_frequencies(
        comments_list=comments_list,
        keywords=keyword_stats["keywords"],
        domain_words=domain_words,
        stop_words=stop_words,
        emoji_words=EMOJI_WORDS,
        aliases=aliases,
        top_n=top_n,
        exclude_targets=exclude_targets_in_top,
    )
    top_keywords_str = format_top_terms(top_terms, style=top_format)

    sampled = weighted_sample_comments(
        comments_data=comments_data,
        keyword_hit_flags=keyword_stats["keyword_hit_flags"],
        sentiment_labels=sentiment_stats["sentiment_labels"],
        total_limit=sample_limit,
        seed=sample_seed,
    )

    stats: Dict[str, Any] = {
        "input_path": str(input_path),
        "comment_column": real_comment_col,
        "like_column": real_like_col,
        "target_keyword": safe_text(target_keyword) or "未指定关键词",
        "total_count": total_count,
        "sample_count": len(sampled),
        "top_terms": top_terms,
        "top_keywords_str": top_keywords_str,
        "sampled_comments": format_sample_comments(sampled),
        "term_counter": term_counter,
        **{k: v for k, v in keyword_stats.items() if k != "keyword_hit_flags"},
        **{k: v for k, v in sentiment_stats.items() if k != "sentiment_labels"},
    }
    stats["compiled_data"] = build_compiled_data(stats)
    return stats


def append_artifact_links(report_text: str, wordcloud_path: Optional[Path], wordcloud_warning: Optional[str]) -> str:
    lines = [report_text.rstrip()]
    if wordcloud_path:
        lines.append("---")
        lines.append(f"☁️ **评论词云图**：{wordcloud_path}")
    elif wordcloud_warning:
        lines.append("---")
        lines.append(f"☁️ **评论词云图**：{wordcloud_warning}")
    return "\n".join(lines).strip() + "\n"


# =========================
# 15. CLI
# =========================

def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="评论区分析工作流的标准 Python 脚本版")
    parser.add_argument("--input", "-i", required=True, help="输入评论文件路径或下载 URL，支持 .xlsx/.xls/.csv/.json")
    parser.add_argument("--target-keyword", "-k", required=True, help="目标检索词；支持逗号、中文逗号、顿号、空格分隔多个关键词")
    parser.add_argument("--output-dir", "-o", type=Path, default=Path("./output"), help="输出目录")
    parser.add_argument("--sheet-name", default=None, help="Excel sheet 名称；默认读取第一个 sheet")
    parser.add_argument("--comment-column", default=None, help="评论内容列名；不填则自动按列名识别")
    parser.add_argument("--like-column", default=None, help="点赞量列名；不填则自动识别，识别不到按 0 处理")

    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"模型名称；常用候选：{', '.join(KNOWN_MODEL_OPTIONS)}")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="OpenAI-compatible Base URL")
    parser.add_argument("--api-key", default=None, help="大模型 API Key；更推荐用 LLM_API_KEY 环境变量")
    parser.add_argument("--temperature", type=float, default=0.2, help="大模型 temperature；建议 0-0.2 保持格式稳定")
    parser.add_argument("--llm-timeout", type=int, default=180, help="大模型请求超时时间，秒")
    parser.add_argument("--no-llm", action="store_true", help="不调用大模型，只输出统计模板")

    parser.add_argument("--sample-seed", type=int, default=42, help="抽样随机种子；固定值可复现")
    parser.add_argument("--sample-limit", type=int, default=250, help="送入大模型的评论抽样数量上限")
    parser.add_argument("--top-n", type=int, default=10, help="高频词数量")
    parser.add_argument("--top-format", choices=["ratio", "count", "both"], default="both", help="高频词展示格式")
    parser.add_argument("--exclude-targets-in-top", action="store_true", help="高频词中排除目标关键词本身")

    parser.add_argument("--positive-words", type=Path, default=None, help="追加正面词表 txt，一行一个或用逗号分隔")
    parser.add_argument("--negative-words", type=Path, default=None, help="追加负面词表 txt，一行一个或用逗号分隔")
    parser.add_argument("--stop-words", type=Path, default=None, help="追加停用词表 txt")
    parser.add_argument("--domain-words", type=Path, default=None, help="追加领域词表 txt，用于高频词和分词")
    parser.add_argument("--alias-file", type=Path, default=None, help="高频词归并别名文件，格式 source,target")

    parser.add_argument("--no-wordcloud", action="store_true", help="不生成词云图")
    parser.add_argument("--save-compiled-data", action="store_true", help="保存传给大模型的 compiled_data 调试文本")
    parser.add_argument("--upload", action="store_true", help="分析完成后上传报告到内部云盘；需要 CLOUD_DISK_* 环境变量")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    try:
        input_path = resolve_input_path(args.input, args.output_dir / "download_cache")
        if not input_path.exists():
            raise FileNotFoundError(f"输入文件不存在：{input_path}")

        if args.model not in KNOWN_MODEL_OPTIONS:
            print(f"提示：模型 {args.model!r} 不在脚本内置候选列表中，将仍然尝试调用。", file=sys.stderr)

        stats = analyze_comments(
            input_path=input_path,
            target_keyword=args.target_keyword,
            sheet_name=args.sheet_name,
            comment_column=args.comment_column,
            like_column=args.like_column,
            positive_words_file=args.positive_words,
            negative_words_file=args.negative_words,
            stop_words_file=args.stop_words,
            domain_words_file=args.domain_words,
            alias_file=args.alias_file,
            sample_seed=args.sample_seed,
            sample_limit=args.sample_limit,
            top_n=args.top_n,
            top_format=args.top_format,
            exclude_targets_in_top=args.exclude_targets_in_top,
        )

        wordcloud_path: Optional[Path] = None
        wordcloud_warning: Optional[str] = None
        if not args.no_wordcloud:
            wordcloud_path, wordcloud_warning = generate_wordcloud(stats["term_counter"], args.output_dir)
            if wordcloud_warning:
                print("词云提示：" + wordcloud_warning, file=sys.stderr)

        if args.save_compiled_data:
            compiled_path = save_text(stats["compiled_data"], args.output_dir, prefix="compiled_data", suffix=".txt")
            print(f"compiled_data 已保存：{compiled_path}")

        if args.no_llm:
            report_text = build_fallback_report(stats)
        else:
            api_key = args.api_key or os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise RuntimeError("未配置大模型 API Key。请设置 LLM_API_KEY 环境变量，或使用 --api-key 传入。")
            report_text = call_llm_report(
                compiled_data=stats["compiled_data"],
                api_key=api_key,
                base_url=args.base_url,
                model=args.model,
                temperature=args.temperature,
                timeout=args.llm_timeout,
            )

        report_text = append_artifact_links(report_text, wordcloud_path, wordcloud_warning)

        report_path = save_text(report_text, args.output_dir, prefix="舆情分析报告", suffix=".md")
        stats_for_json = dict(stats)
        stats_for_json.pop("term_counter", None)
        stats_for_json.pop("sampled_comments", None)
        stats_for_json.pop("compiled_data", None)
        stats_path = save_json(stats_for_json, args.output_dir, prefix="统计结果")
        top_terms_path = save_top_terms_csv(stats["top_terms"], args.output_dir)
        sample_path = save_text(stats["sampled_comments"], args.output_dir, prefix="抽样评论", suffix=".txt")

        print(f"报告已保存：{report_path}")
        print(f"统计 JSON 已保存：{stats_path}")
        print(f"高频词 CSV 已保存：{top_terms_path}")
        print(f"抽样评论已保存：{sample_path}")
        if wordcloud_path:
            print(f"词云图已保存：{wordcloud_path}")
        print("\n" + report_text)

        if args.upload:
            upload_result = upload_to_cloud_disk(report_text, report_path.name)
            print("\n云盘上传结果：" + json.dumps(upload_result, ensure_ascii=False))

        return 0
    except Exception as exc:
        print(f"执行失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
