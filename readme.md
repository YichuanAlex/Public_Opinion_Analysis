# Public Opinion Analysis Pipeline / 舆情分析采集与加热 Pipeline

> 中文：本项目是一个本地运行的多平台舆情采集、字段归一、AI 标注和口碑加热候选导出工具。目前支持小红书和抖音。  
> English: This project is a local multi-platform public opinion pipeline for collection, field normalization, AI labeling, and amplification candidate export. It currently supports Rednote/Xiaohongshu and Douyin.

---

## 1. 项目能力 / What This Tool Does

中文：

本工具围绕“滴滴相关内容舆情监控”设计，主要完成以下流程：

1. 从小红书或抖音采集帖子、视频、图文和评论数据。
2. 将不同平台字段统一成监控总表字段，例如发布时间、标题、链接、内容、点赞量、收藏量、评论量、分享量、互动量、博主昵称、笔记ID。
3. 通过 AI 自动填写概括、内容类型、正负向、业务线、渠道类型、具体产品/场景等分析字段。
4. 按日期区间筛选候选内容，只允许 `正负向=正向` 的内容进入加热候选判断。
5. 将值得加热的内容写入 Hype_Something 下对应平台的 Excel 月份 sheet。

English:

This tool is designed for Didi-related public opinion monitoring. It supports the following workflow:

1. Collect posts, videos, image-text content, and comments from Rednote/Xiaohongshu or Douyin.
2. Normalize platform-specific fields into one monitoring schema, including publish time, title, link, content, likes, collects, comments, shares, interactions, author nickname, and note ID.
3. Use AI to fill analysis fields such as summary, content type, sentiment, business line, channel type, and product/scenario.
4. Filter amplification candidates by date range. Only rows with `正负向=正向` can enter amplification judgment.
5. Write selected amplification candidates into the platform-specific Excel workbook under Hype_Something.

---

## 2. 目录结构 / Directory Structure

中文：

核心目录如下：

```text
/Users/didi/Downloads/Public_Opinion_Analysis
├── run_public_opinion_suite.command
├── daily_work.py
├── check_and_repair_monitoring_tables.py
├── Visualization
│   ├── server.py
│   ├── index.html
│   ├── app.js
│   └── styles.css
├── Pipeline
│   ├── run_pipeline_gui.command
│   ├── pipeline_gui_server.py
│   ├── pipeline_gui.html
│   ├── pipeline_gui.js
│   ├── pipeline_gui.css
│   ├── pipeline_paths.py
│   ├── media_enrichment.py
│   ├── ocr_adapter.py
│   ├── download_asr_model.py
│   ├── xhs_note_to_csv.py
│   ├── xhs_search_to_csv.py
│   ├── xhs_comment_to_csv.py
│   ├── xhs_ai_fill_table.py
│   ├── xhs_amplification_export.py
│   ├── dy_note_to_csv.py
│   ├── dy_search_to_csv.py
│   ├── dy_comment_to_csv.py
│   ├── dy_ai_fill_table.py
│   ├── dy_amplification_export.py
│   ├── xhs_origin_data.csv
│   ├── xhs_Data_Table_on_Channel_Public_Opinion_Monitoring_2026.csv
│   ├── xhs_comments.csv
│   ├── dy_origin_data.csv
│   ├── dy_Data_Table_on_Channel_Public_Opinion_Monitoring_2026.csv
│   └── dy_comments.csv
├── Hype_Something
│   ├── start_tool.command
│   ├── server.js
│   ├── app.js
│   ├── run.js
│   ├── styles.css
│   ├── llm_config.json
│   ├── training_data_cleaned.csv
│   ├── 2026_Didi_Xiaohongshu_Daily_Word-of-Mouth_Amplification.xlsx
│   └── 2026_Didi_Douyin_Daily_Word-of-Mouth_Amplification.xlsx
├── cache
│   └── 单帖媒体增强临时目录，处理完成后自动清理
├── modelfile
│   └── faster-whisper-small
├── Social_Media_Copilot
└── requirements.txt
```

English:

The core folders are:

```text
/Users/didi/Downloads/Public_Opinion_Analysis
├── run_public_opinion_suite.command  # One-click launcher for Visualization + Pipeline
├── daily_work.py             # Unattended daily loop: search, clean, AI fill, amplification export
├── check_and_repair_monitoring_tables.py
├── Visualization             # Monthly dashboard homepage
├── Pipeline                 # Collection GUI, scripts, normalized CSV outputs
├── Hype_Something           # Local Hype judgment tool and Excel workbooks
├── cache                    # Temporary downloaded media; auto-cleaned per post
├── modelfile                # Local ASR model files
├── Social_Media_Copilot     # Reference open-source plugin logic
└── requirements.txt         # Python dependency file
```

---

## 3. 环境要求 / Environment Requirements

中文：

建议环境：

- macOS。
- Python 3.9 或更高版本。
- Google Chrome 或 Microsoft Edge。
- ffmpeg（推荐）。如果安装了 ffmpeg，脚本会先抽取 16k wav 再做转写；如果未安装，会直接把媒体文件交给本地 ASR 处理。
- 已在 Chrome 中登录需要采集的平台：
  - 小红书：https://www.xiaohongshu.com
  - 抖音：https://www.douyin.com
- Node.js 18 或更高版本。仅在需要打开 `Hype_Something` 独立软件界面时需要。
- 网络可以访问小红书、抖音和公司 LLM Proxy。

English:

Recommended environment:

- macOS.
- Python 3.9 or later.
- Google Chrome or Microsoft Edge.
- ffmpeg (recommended). If installed, the script extracts 16k wav audio before transcription; otherwise it passes the media file directly to local ASR.
- Logged-in browser sessions for the target platforms:
  - Rednote/Xiaohongshu: https://www.xiaohongshu.com
  - Douyin: https://www.douyin.com
- Node.js 18 or later. This is only required when opening the standalone Hype_Something interface.
- Network access to Rednote/Xiaohongshu, Douyin, and the internal LLM proxy.

---

## 4. 安装依赖 / Install Dependencies

中文：

进入项目根目录：

```bash
cd /Users/didi/Downloads/Public_Opinion_Analysis
```

建议使用 Python 虚拟环境：

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```

如果不想使用虚拟环境，也可以直接安装到当前 Python：

```bash
cd /Users/didi/Downloads/Public_Opinion_Analysis
python3 -m pip install -r requirements.txt
```

`requirements.txt` 包含 `.xlsx` 写入、macOS OCR、本地视频语音转写所需依赖。采集、CSV 处理、GUI 服务和 AI 请求仍主要使用 Python 标准库。

English:

Go to the project root:

```bash
cd /Users/didi/Downloads/Public_Opinion_Analysis
```

Using a Python virtual environment is recommended:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```

You can also install dependencies directly into your current Python environment:

```bash
cd /Users/didi/Downloads/Public_Opinion_Analysis
python3 -m pip install -r requirements.txt
```

`requirements.txt` includes dependencies for `.xlsx` writing, macOS OCR, and local video speech transcription. Collection, CSV processing, the GUI server, and AI requests still mostly use the Python standard library.

---

## 5. 首次运行前检查 / First-Time Checklist

中文：

1. 确认 Chrome 已安装。
2. 用 Chrome 登录小红书和抖音。
3. 确认 `Pipeline/run_pipeline_gui.command` 可以执行：

```bash
chmod +x /Users/didi/Downloads/Public_Opinion_Analysis/Pipeline/run_pipeline_gui.command
chmod +x /Users/didi/Downloads/Public_Opinion_Analysis/run_public_opinion_suite.command
chmod +x /Users/didi/Downloads/Public_Opinion_Analysis/daily_work.py
```

4. 如果 macOS 提示“无法打开来自未知开发者的文件”，右键点击 `run_pipeline_gui.command`，选择“打开”。
5. 安装 Python 依赖：

```bash
cd /Users/didi/Downloads/Public_Opinion_Analysis
python3 -m pip install -r requirements.txt
```

English:

1. Make sure Chrome is installed.
2. Log in to Rednote/Xiaohongshu and Douyin in Chrome.
3. Make sure the command launcher is executable:

```bash
chmod +x /Users/didi/Downloads/Public_Opinion_Analysis/Pipeline/run_pipeline_gui.command
chmod +x /Users/didi/Downloads/Public_Opinion_Analysis/run_public_opinion_suite.command
chmod +x /Users/didi/Downloads/Public_Opinion_Analysis/daily_work.py
```

4. If macOS blocks the file as coming from an unidentified developer, right-click `run_pipeline_gui.command` and choose Open.
5. Install Python dependencies:

```bash
cd /Users/didi/Downloads/Public_Opinion_Analysis
python3 -m pip install -r requirements.txt
```

---

## 6. API 配置 / API Configuration

中文：

AI 填写总表和 AI 判断加热候选会读取：

```text
/Users/didi/Downloads/Public_Opinion_Analysis/Hype_Something/llm_config.json
```

推荐配置格式如下：

```json
{
  "apiKey": "YOUR_API_KEY",
  "baseUrl": "https://llm-proxy.intra.xiaojukeji.com",
  "model": "kimi-k2.5-external"
}
```

GUI 中可选模型包括：

- `All Named Models`
- `All Internal Models`
- `kimi-k2.5-external`
- `minimax-m2.5-external`
- `glm-5.1-external`
- `glm-5-external`
- `glm-5-internal`
- `glm-5.1-internal`

注意：

- 不要把真实 API Key 写入 README。
- 不要把 `llm_config.json` 分享给外部人员。
- 如果 GUI 中选择了模型，会覆盖配置文件中的默认模型。
- 如果公司代理偶发 SSL/EOF 错误，脚本已内置重试、curl 兜底和并发控制。可以降低 GUI 里的并发数，例如从 3 改成 1 或 2。

English:

AI table filling and AI amplification judgment read this config file:

```text
/Users/didi/Downloads/Public_Opinion_Analysis/Hype_Something/llm_config.json
```

Recommended format:

```json
{
  "apiKey": "YOUR_API_KEY",
  "baseUrl": "https://llm-proxy.intra.xiaojukeji.com",
  "model": "kimi-k2.5-external"
}
```

Available GUI model options:

- `All Named Models`
- `All Internal Models`
- `kimi-k2.5-external`
- `minimax-m2.5-external`
- `glm-5.1-external`
- `glm-5-external`
- `glm-5-internal`
- `glm-5.1-internal`

Notes:

- Do not put the real API key in this README.
- Do not share `llm_config.json` externally.
- The model selected in the GUI overrides the default model in the config file.
- If the internal proxy occasionally returns SSL/EOF errors, the scripts already include retries, curl fallback, and concurrency control. You can reduce GUI concurrency from 3 to 1 or 2.

---

## 7. 启动 GUI / Start the GUI

中文：

推荐入口是项目根目录的总启动命令。它会同时启动可视化大屏和 Pipeline 采集工作台，并把“可视化大屏”作为首页打开：

```text
/Users/didi/Downloads/Public_Opinion_Analysis/run_public_opinion_suite.command
```

也可以在终端中运行：

```bash
cd /Users/didi/Downloads/Public_Opinion_Analysis
bash run_public_opinion_suite.command
```

默认端口：

| 页面 | 默认地址 |
|---|---|
| 可视化大屏首页 | `http://127.0.0.1:8765/` |
| Pipeline 采集工作台 | `http://127.0.0.1:8766/` |

可视化大屏右上角有“打开舆情采集工作台”按钮，会在新网页打开 Pipeline；Pipeline 左侧有“返回可视化首页”按钮。

可视化大屏已经做了响应式适配：顶部筛选按钮、表格、折线图、饼图和词云会随浏览器窗口、系统缩放或侧栏宽度变化自动重排；长文本默认用 `...` 截断，鼠标悬浮可查看完整内容；各模块标题按 A/B/C 从左到右、从上到下排序。

如果只想单独调试采集工作台，也可以双击：

```text
/Users/didi/Downloads/Public_Opinion_Analysis/Pipeline/run_pipeline_gui.command
```

也可以在终端中运行：

```bash
cd /Users/didi/Downloads/Public_Opinion_Analysis
bash Pipeline/run_pipeline_gui.command
```

启动后会自动打开本地网页，地址类似：

```text
http://127.0.0.1:8766/
```

如果端口被占用，Pipeline 单独启动时会自动换到附近可用端口。总启动命令可通过环境变量改端口：

```bash
VISUALIZATION_PORT=8865 PIPELINE_GUI_PORT=8866 bash run_public_opinion_suite.command
```

English:

The recommended entry point is the root launcher. It starts both the dashboard and the Pipeline workspace, then opens the Visualization dashboard as the homepage:

```text
/Users/didi/Downloads/Public_Opinion_Analysis/run_public_opinion_suite.command
```

Or run it in Terminal:

```bash
cd /Users/didi/Downloads/Public_Opinion_Analysis
bash run_public_opinion_suite.command
```

Default ports:

| Page | Default URL |
|---|---|
| Visualization dashboard homepage | `http://127.0.0.1:8765/` |
| Pipeline collection workspace | `http://127.0.0.1:8766/` |

The dashboard has an `打开舆情采集工作台` button in the top-right corner, which opens Pipeline in a new tab. Pipeline has a `返回可视化首页` link on the left side.

The Visualization dashboard is responsive: top filters, tables, line charts, pie charts, and word clouds resize when the browser window, system zoom, or side panel width changes. Long text is truncated with `...`, and hovering shows the full value. Module headings are ordered A/B/C from left to right and top to bottom.

If you only want to debug the collection workspace, double-click:

```text
/Users/didi/Downloads/Public_Opinion_Analysis/Pipeline/run_pipeline_gui.command
```

Or run it in Terminal:

```bash
cd /Users/didi/Downloads/Public_Opinion_Analysis
bash Pipeline/run_pipeline_gui.command
```

The local web GUI will open automatically at a URL like:

```text
http://127.0.0.1:8766/
```

When Pipeline is launched alone, it automatically chooses a nearby free port if the default one is occupied. The root launcher ports can be changed with environment variables:

```bash
VISUALIZATION_PORT=8865 PIPELINE_GUI_PORT=8866 bash run_public_opinion_suite.command
```

---

## 8. 平台切换 / Platform Switch

中文：

GUI 左上角 `Rednote Export / Public Opinion Pipeline` 区域下方有平台切换按钮：

- 小红书
- 抖音

切换后，同一套按钮会根据当前平台自动调用不同脚本：

| 平台 | 单帖 | 搜索 | 评论 | AI 回填 | 加热导出 |
|---|---|---|---|---|---|
| 小红书 | `xhs_note_to_csv.py` | `xhs_search_to_csv.py` | `xhs_comment_to_csv.py` | `xhs_ai_fill_table.py` | `xhs_amplification_export.py` |
| 抖音 | `dy_note_to_csv.py` | `dy_search_to_csv.py` | `dy_comment_to_csv.py` | `dy_ai_fill_table.py` | `dy_amplification_export.py` |

GUI 还提供显式双平台并行按钮：

- `双平台并行导出关键词`：同时运行小红书和抖音关键词搜索，各自写入自己的 `xhs_*` / `dy_*` 文件。
- `双平台并行AI填写`：同时回填两张监控总表中缺失的 AI 字段。
- `双平台并行只回填`：同时补齐两张表的 `笔记ID`、`互动量`、`渠道类型` 等确定性字段。
- `清洗双平台总表`：同时对两张监控总表去重和删除脏数据。

并行调度规则是“平台级互斥、跨平台并行”：

- 同一个平台一次只允许执行一个长任务。例如小红书正在 AI 填写时，不能再启动小红书关键词采集或小红书单帖采集。
- 不同平台可以同时执行不同任务。例如小红书正在 AI 填写时，可以切换到抖音并启动抖音单帖采集、关键词采集或评论采集。
- 如果同一平台已有任务在运行，GUI 会弹出 alert，提示当前平台正在执行的任务。
- 双平台并行按钮是快捷入口，只有小红书和抖音都空闲时才适合点击。

服务端使用平台级任务锁和写锁：同一平台内会互斥执行并顺序写同一张 CSV，两个平台之间不会互相阻塞。
双平台 AI 填写使用流式日志，执行结果区域会同时显示 `【小红书】` 和 `【抖音】` 前缀的逐行处理进度。

English:

Under the `Rednote Export / Public Opinion Pipeline` area in the top-left corner, there is a platform switch:

- Rednote/Xiaohongshu
- Douyin

After switching platforms, the same GUI buttons automatically call platform-specific scripts:

| Platform | Single post | Search | Comments | AI fill | Amplification export |
|---|---|---|---|---|---|
| Rednote/Xiaohongshu | `xhs_note_to_csv.py` | `xhs_search_to_csv.py` | `xhs_comment_to_csv.py` | `xhs_ai_fill_table.py` | `xhs_amplification_export.py` |
| Douyin | `dy_note_to_csv.py` | `dy_search_to_csv.py` | `dy_comment_to_csv.py` | `dy_ai_fill_table.py` | `dy_amplification_export.py` |

The GUI also provides explicit dual-platform parallel actions:

- `双平台并行导出关键词`: run Rednote/Xiaohongshu and Douyin keyword search at the same time, writing to separate `xhs_*` / `dy_*` files.
- `双平台并行AI填写`: fill missing AI fields in both monitoring tables concurrently.
- `双平台并行只回填`: backfill deterministic fields such as `笔记ID`, interaction count, and channel type in both tables.
- `清洗双平台总表`: deduplicate and remove dirty rows from both monitoring tables concurrently.

The scheduling rule is platform-level exclusivity with cross-platform concurrency:

- One platform can run only one long task at a time. For example, if Rednote/Xiaohongshu AI fill is running, you cannot start another Rednote/Xiaohongshu search or single-post collection.
- Different platforms can run different tasks at the same time. For example, while Rednote/Xiaohongshu AI fill is running, you can switch to Douyin and start Douyin single-post collection, keyword search, or comment collection.
- If a task is already running on the same platform, the GUI shows an alert with the current task name.
- Dual-platform buttons are shortcuts and should be used only when both platforms are idle.

The server uses platform-level task locks and write locks: tasks within the same platform are mutually exclusive and CSV writes remain ordered, while Rednote/Xiaohongshu and Douyin do not block each other.
Dual-platform AI filling uses streaming logs, so the result panel shows interleaved per-row progress with `【小红书】` and `【抖音】` prefixes.

---

## 9. 输出文件 / Output Files

中文：

小红书输出：

| 文件 | 说明 |
|---|---|
| `Pipeline/xhs_origin_data.csv` | 小红书全量原始字段追加表 |
| `Pipeline/xhs_Data_Table_on_Channel_Public_Opinion_Monitoring_2026.csv` | 小红书监控总表 |
| `Pipeline/xhs_comments.csv` | 小红书评论总表 |
| `Hype_Something/2026_Didi_Xiaohongshu_Daily_Word-of-Mouth_Amplification.xlsx` | 小红书口碑加热 Excel |

抖音输出：

| 文件 | 说明 |
|---|---|
| `Pipeline/dy_origin_data.csv` | 抖音全量原始字段追加表 |
| `Pipeline/dy_Data_Table_on_Channel_Public_Opinion_Monitoring_2026.csv` | 抖音监控总表 |
| `Pipeline/dy_comments.csv` | 抖音评论总表 |
| `Hype_Something/2026_Didi_Douyin_Daily_Word-of-Mouth_Amplification.xlsx` | 抖音口碑加热 Excel |

English:

Rednote/Xiaohongshu outputs:

| File | Description |
|---|---|
| `Pipeline/xhs_origin_data.csv` | Full raw Rednote/Xiaohongshu field table |
| `Pipeline/xhs_Data_Table_on_Channel_Public_Opinion_Monitoring_2026.csv` | Rednote/Xiaohongshu monitoring table |
| `Pipeline/xhs_comments.csv` | Rednote/Xiaohongshu comment table |
| `Hype_Something/2026_Didi_Xiaohongshu_Daily_Word-of-Mouth_Amplification.xlsx` | Rednote/Xiaohongshu amplification workbook |

Douyin outputs:

| File | Description |
|---|---|
| `Pipeline/dy_origin_data.csv` | Full raw Douyin field table |
| `Pipeline/dy_Data_Table_on_Channel_Public_Opinion_Monitoring_2026.csv` | Douyin monitoring table |
| `Pipeline/dy_comments.csv` | Douyin comment table |
| `Hype_Something/2026_Didi_Douyin_Daily_Word-of-Mouth_Amplification.xlsx` | Douyin amplification workbook |

---

## 9.1 监控表核心字段回源修复 / Source Refresh for Missing Core Fields

中文：

如果 `xhs_origin_data.csv`、`dy_origin_data.csv` 和两张监控总表里同一条帖子的核心字段都为空，例如 `笔记内容`、`笔记标题`、`发布时间`、互动数据缺失，不能只靠本地互补解决。这时使用根目录脚本重新访问平台，按帖子 ID 逐条回源重爬：

```bash
cd /Users/didi/Downloads/Public_Opinion_Analysis
python3 check_and_repair_monitoring_tables.py --platform all --dry-run --refresh-missing --max-refresh 20
```

上面的命令只生成报告，不访问平台。确认候选合理后，再执行正式修复：

```bash
cd /Users/didi/Downloads/Public_Opinion_Analysis
python3 check_and_repair_monitoring_tables.py \
  --platform all \
  --refresh-missing \
  --max-refresh 20 \
  --headed \
  --request-interval 25 \
  --jitter 10 \
  --retry 2
```

参数说明：

| 参数 | 说明 |
|---|---|
| `--platform all/xhs/dy` | 选择修复双平台、小红书或抖音 |
| `--dry-run` | 只检查候选并输出报告，不写表、不访问平台 |
| `--refresh-missing` | 对本地仍缺核心字段的帖子回源重爬 |
| `--max-refresh 20` | 每个平台本次最多重爬 20 条；`0` 表示不限制 |
| `--headed` | 显示浏览器窗口，便于复用登录态和观察风控页面 |
| `--request-interval 25` | 每条之间至少等待 25 秒 |
| `--jitter 10` | 每条额外随机等待 0-10 秒 |
| `--retry 2` | 单条失败最多重试 2 轮 |

小红书裸链接处理：

- 如果链接只有 `https://www.xiaohongshu.com/discovery/item/{note_id}`，脚本会优先尝试 `https://www.xiaohongshu.com/explore/{note_id}?xsec_source=pc_search`。
- 同时会在本地 `xhs_origin_data.csv` 和 `xhs_Data_Table_on_Channel_Public_Opinion_Monitoring_2026.csv` 中查找同 ID 的历史 `xsec_token` 链接。
- 候选入口包括原始链接、`explore`、`discovery/item`、`search_result`、PC 分享参数和 App 分享参数组合。
- 如果候选入口仍停留在 `404`、`300031`、登录安全页或明显广告页，脚本会拒绝把错误页面内容写入 CSV，并继续尝试下一个候选入口或浏览器账号。
- 如果账号处于 `300013` 风控状态，应暂停采集，等网页端普通浏览恢复后再运行。
- 最稳妥的输入仍然是完整分享链接，例如含 `source=webshare&xsec_token=...&xsec_source=pc_share` 的链接。

English:

If the same post has blank core fields in both origin CSVs and monitoring tables, such as missing `笔记内容`, title, publish time, or interaction metrics, local table merging is not enough. Use the root script to revisit the platform and refresh missing rows by post ID:

```bash
cd /Users/didi/Downloads/Public_Opinion_Analysis
python3 check_and_repair_monitoring_tables.py --platform all --dry-run --refresh-missing --max-refresh 20
```

The command above only generates a report and does not visit the platform. After reviewing the candidates, run the real refresh:

```bash
cd /Users/didi/Downloads/Public_Opinion_Analysis
python3 check_and_repair_monitoring_tables.py \
  --platform all \
  --refresh-missing \
  --max-refresh 20 \
  --headed \
  --request-interval 25 \
  --jitter 10 \
  --retry 2
```

Argument summary:

| Argument | Description |
|---|---|
| `--platform all/xhs/dy` | Refresh both platforms, Rednote/Xiaohongshu only, or Douyin only |
| `--dry-run` | Inspect candidates and write a report only; no writeback and no platform visit |
| `--refresh-missing` | Re-crawl posts that still have missing core fields locally |
| `--max-refresh 20` | Refresh at most 20 rows per platform; `0` means no limit |
| `--headed` | Show the browser window to reuse login state and observe risk-control pages |
| `--request-interval 25` | Wait at least 25 seconds between rows |
| `--jitter 10` | Add 0-10 seconds random wait between rows |
| `--retry 2` | Retry each failed row up to 2 times |

Rednote/Xiaohongshu bare-link handling:

- If the input is only `https://www.xiaohongshu.com/discovery/item/{note_id}`, the script first tries `https://www.xiaohongshu.com/explore/{note_id}?xsec_source=pc_search`.
- It also searches local `xhs_origin_data.csv` and `xhs_Data_Table_on_Channel_Public_Opinion_Monitoring_2026.csv` for a historical URL with `xsec_token` for the same note ID.
- Candidate entrances include the original URL, `explore`, `discovery/item`, `search_result`, PC-share parameters, and App-share parameter combinations.
- If a candidate still lands on `404`, `300031`, a login/security page, or an obvious ad page, the script refuses to write that wrong page into CSV and continues with the next candidate or browser account.
- If the account is under `300013` rate limit, stop collection and retry after normal web browsing recovers.
- The safest input is still the full share URL containing `source=webshare&xsec_token=...&xsec_source=pc_share`.

---

## 10. 使用方式一：单帖子单查询 / Workflow 1: Single Post Query

中文：

1. 启动 GUI。
2. 在左上角选择平台：小红书或抖音。
3. 在“单帖子单查询”文本框中粘贴平台分享文案或网页链接。
4. 点击“单帖子单查询”。
5. 程序会追加：
   - 全量字段到当前平台的 origin CSV。
   - 10 个监控字段到当前平台的监控总表。

适用示例：

小红书：

```text
https://www.xiaohongshu.com/discovery/item/...
```

小红书建议优先粘贴完整分享文案或带 `xsec_token` 的 webshare 链接。只有裸 `discovery/item/{id}` 链接时，脚本会优先尝试 `/explore/{id}?xsec_source=pc_search`，再尝试历史 token、PC 分享入口和 App 分享入口。如果所有入口都停留在安全页或广告页，脚本会拒绝写入错误内容并提示重试。

抖音：

```text
https://www.douyin.com/video/...
```

抖音支持 `douyin.com/video/...`、`iesdouyin.com/share/video/...`、`v.douyin.com/...` 短链和完整分享文案。

English:

1. Start the GUI.
2. Select the platform in the top-left area: Rednote/Xiaohongshu or Douyin.
3. Paste the platform share text or web URL into the single-post text box.
4. Click `单帖子单查询`.
5. The script appends:
   - Full raw fields to the current platform origin CSV.
   - 10 monitoring fields to the current platform monitoring table.

Examples:

Rednote/Xiaohongshu:

```text
https://www.xiaohongshu.com/discovery/item/...
```

For Rednote/Xiaohongshu, full share text or a webshare URL with `xsec_token` is preferred. If only a bare `discovery/item/{id}` URL is provided, the script first tries `/explore/{id}?xsec_source=pc_search`, then local historical tokens, PC-share entrances, and App-share entrances. If all entrances remain on security or ad pages, the script refuses to write the wrong content and asks for a retry.

Douyin:

```text
https://www.douyin.com/video/...
```

Douyin supports `douyin.com/video/...`, `iesdouyin.com/share/video/...`, `v.douyin.com/...` short URLs, and full share text.

---

## 11. 使用方式二：关键词批量数目查询 / Workflow 2: Keyword Batch Search

中文：

1. 选择平台。
2. 在左侧关键词按钮中选择预设关键词，或在关键词输入框手动输入。
3. 设置“最多笔记”：
   - `0` 表示不限制，只抓当前保守滚动能加载到的内容。
   - 建议先用 `10` 或 `20` 小规模测试。
4. 设置“滚动轮次”：
   - 默认 `10`。
   - 如果抓取较少，可以增加到 `15` 或 `20`。
5. 设置筛选项：
   - 排序依据：综合、最新、最多点赞、最多评论、最多收藏。
   - 笔记类型：不限、视频、图文。
   - 发布时间：不限、一天内、一周内、半年内。
   - 搜索范围：不限、已看过、未看过、已关注。
   - 位置距离：不限、同城、附近。
6. 点击“导出当前关键词”。

说明：

- 小红书侧会打开真实搜索页面，慢速加载并提取带 `xsec_token` 的笔记卡片，再逐条请求详情。
- 抖音侧会打开真实搜索页面，慢速滚动识别 `aweme_id`，再逐条请求视频/图文详情。
- 为了降低风控风险，不建议同时开多个 GUI 或连续高频点击。
- 如果页面出现登录、验证码或安全验证，需要在打开的浏览器页面中手动完成。

English:

1. Select a platform.
2. Choose a preset keyword on the left, or manually type a keyword.
3. Set `最多笔记`:
   - `0` means no hard limit. The script exports what conservative scrolling can load.
   - Start with `10` or `20` for testing.
4. Set `滚动轮次`:
   - Default is `10`.
   - Increase to `15` or `20` if too few results are loaded.
5. Configure filters:
   - Sort: comprehensive, latest, most likes, most comments, most collects.
   - Content type: all, video, image-text.
   - Publish time: all, within 1 day, within 1 week, within 6 months.
   - Search scope: all, viewed, not viewed, followed.
   - Location: all, same city, nearby.
6. Click `导出当前关键词`.

Notes:

- Rednote/Xiaohongshu opens the real search page, slowly loads cards, extracts note links with `xsec_token`, then fetches details one by one.
- Douyin opens the real search page, slowly scrolls to identify `aweme_id`, then fetches video/image-text details one by one.
- To reduce anti-bot risk, avoid running multiple GUI instances or clicking repeatedly at high frequency.
- If login, CAPTCHA, or security verification appears, complete it manually in the opened browser page.

---

## 12. 使用方式三：粘贴板帖子查询 / Workflow 3: Clipboard Post Query

中文：

1. 复制一条平台分享文案或链接。
2. 在 GUI 中选择对应平台。
3. 点击“粘贴板帖子查询”。
4. 程序会读取剪贴板、填入文本框，并执行单帖查询。

English:

1. Copy one platform share text or URL.
2. Select the matching platform in the GUI.
3. Click `粘贴板帖子查询`.
4. The tool reads the clipboard, fills the text box, and runs a single-post query.

---

## 13. 评论区爬取 / Comment Collection

中文：

评论爬取只针对“单帖子单查询”和“粘贴板帖子查询”里的单条链接，不针对关键词批量结果。

按钮：

- `爬取文本框评论`：读取当前文本框中的链接并爬取评论。
- `粘贴板评论爬取`：读取剪贴板中的链接并爬取评论。

输出：

- 小红书评论追加到 `Pipeline/xhs_comments.csv`。
- 抖音评论追加到 `Pipeline/dy_comments.csv`。
- 批量评论导出脚本会按帖子 ID 保存独立 Excel 到 `Comment_Data/xhs/` 和 `Comment_Data/dy/`。

评论字段包括：

- 评论ID
- 笔记ID
- 笔记链接
- 评论层级
- 用户ID
- 用户链接
- 用户名称
- 评论内容
- 评论时间
- 点赞数
- 子评论数
- IP地址
- 一级评论ID
- 回复目标评论ID
- 回复目标用户ID
- 回复目标用户名称

如果要从两张监控总表批量导出所有帖子的评论区 Excel，使用：

```bash
cd /Users/didi/Downloads/Public_Opinion_Analysis
python3 Pipeline/export_comment_sections.py --platform all --max-posts-per-platform 0 --limit-comments 0 --headed
```

常用参数：

| 参数 | 说明 |
|---|---|
| `--platform all/xhs/dy` | 导出双平台、小红书或抖音 |
| `--max-posts-per-platform 0` | 每个平台处理全部帖子；调试时可改成小数字 |
| `--limit-comments 0` | 每条帖子导出全部评论；调试时可改成 `50` |
| `--note-id id1,id2` | 只导出指定帖子 ID |
| `--overwrite` | 覆盖已有同名 XLSX |
| `--reset-output` | 删除所选平台旧评论 Excel 后重新导出 |
| `--dry-run` | 只预览，不访问平台 |

English:

Comment collection only works for one specific post/video link from the single-post or clipboard workflow. It does not collect comments for keyword batch results automatically.

Buttons:

- `爬取文本框评论`: collect comments from the current text box link.
- `粘贴板评论爬取`: collect comments from the clipboard link.

Outputs:

- Rednote/Xiaohongshu comments are appended to `Pipeline/xhs_comments.csv`.
- Douyin comments are appended to `Pipeline/dy_comments.csv`.
- The batch comment export script saves one Excel workbook per post ID into `Comment_Data/xhs/` and `Comment_Data/dy/`.

Comment fields include:

- Comment ID
- Note ID
- Note link
- Comment level
- User ID
- User link
- Username
- Comment text
- Comment time
- Like count
- Sub-comment count
- IP location
- Root comment ID
- Reply target comment ID
- Reply target user ID
- Reply target username

To batch export comment-section Excel files for all posts in both monitoring tables, run:

```bash
cd /Users/didi/Downloads/Public_Opinion_Analysis
python3 Pipeline/export_comment_sections.py --platform all --max-posts-per-platform 0 --limit-comments 0 --headed
```

Common arguments:

| Argument | Description |
|---|---|
| `--platform all/xhs/dy` | Export both platforms, Rednote/Xiaohongshu only, or Douyin only |
| `--max-posts-per-platform 0` | Process all posts per platform; use a small number for debugging |
| `--limit-comments 0` | Export all comments per post; use `50` for debugging |
| `--note-id id1,id2` | Export only specific post IDs |
| `--overwrite` | Overwrite existing XLSX files |
| `--reset-output` | Delete old comment workbooks for the selected platform before exporting |
| `--dry-run` | Preview only, without visiting the platforms |

---

## 14. 监控总表去重与脏数据清洗 / Monitoring Table Deduplication and Cleaning

中文：

GUI 在“单帖子单查询 / 粘贴板帖子查询 / 爬取文本框评论 / 粘贴板评论爬取”按钮下方提供两个清洗按钮：

- `清洗当前平台总表`：只清洗当前左上角选中的平台监控总表。
- `清洗双平台总表`：同时清洗小红书和抖音监控总表。

清洗范围只包括：

- `Pipeline/xhs_Data_Table_on_Channel_Public_Opinion_Monitoring_2026.csv`
- `Pipeline/dy_Data_Table_on_Channel_Public_Opinion_Monitoring_2026.csv`

清洗规则：

- 按 `笔记ID` 去重。
- 如果 `笔记ID` 为空，会先尝试从 `笔记链接` 中解析平台唯一 ID。
- 同一个 `笔记ID` 出现多次时，只保留行号最靠前、最早出现的那一条。
- 删除包含以下脏词的行：`实习`、`新橙海`、`工号`、`入职`、`面试`、`桔厂`。
- 脏词会在标题、正文、概括、博主昵称、业务线、具体产品/场景等文本字段中检查。
- 清洗前会自动备份原表到 `Pipeline/gui_exports/clean_backups/`。

English:

The GUI provides two cleaning buttons below the single-post and comment buttons:

- `清洗当前平台总表`: clean only the currently selected platform monitoring table.
- `清洗双平台总表`: clean both Rednote/Xiaohongshu and Douyin monitoring tables.

Cleaning only applies to:

- `Pipeline/xhs_Data_Table_on_Channel_Public_Opinion_Monitoring_2026.csv`
- `Pipeline/dy_Data_Table_on_Channel_Public_Opinion_Monitoring_2026.csv`

Rules:

- Deduplicate by `笔记ID`.
- If `笔记ID` is blank, the tool tries to parse the platform-specific unique ID from `笔记链接`.
- When the same `笔记ID` appears multiple times, only the earliest row is kept.
- Rows containing these dirty keywords are removed: `实习`, `新橙海`, `工号`, `入职`, `面试`, `桔厂`.
- Dirty keywords are checked in text fields such as title, content, summary, author, business line, and scenario.
- Before writing changes, the original CSV is backed up to `Pipeline/gui_exports/clean_backups/`.

---

## 15. 监控总表字段 / Monitoring Table Fields

中文：

两个平台的监控总表都使用同一套字段：

```text
发布时间
笔记标题
笔记链接
笔记内容
点赞量
收藏量
评论量
分享量
互动量
博主昵称
概括
内容类型
正负向
业务线
渠道类型
具体产品/场景
笔记ID
是否剔除
是否剔除.输出结果
```

其中采集自动填写：

```text
发布时间, 笔记标题, 笔记链接, 笔记内容, 点赞量, 收藏量, 评论量, 分享量, 互动量, 博主昵称, 渠道类型, 笔记ID
```

AI 自动填写：

```text
概括, 内容类型, 正负向, 业务线, 具体产品/场景
```

English:

Both platform monitoring tables use the same schema:

```text
发布时间
笔记标题
笔记链接
笔记内容
点赞量
收藏量
评论量
分享量
互动量
博主昵称
概括
内容类型
正负向
业务线
渠道类型
具体产品/场景
笔记ID
是否剔除
是否剔除.输出结果
```

Automatically collected fields:

```text
发布时间, 笔记标题, 笔记链接, 笔记内容, 点赞量, 收藏量, 评论量, 分享量, 互动量, 博主昵称, 渠道类型, 笔记ID
```

AI-filled fields:

```text
概括, 内容类型, 正负向, 业务线, 具体产品/场景
```

---

## 16. AI 填写总表 / AI Table Filling

中文：

使用步骤：

1. 先选择平台。
2. 在左侧“AI 填写”区域选择模型。
3. 设置“最多行”：
   - `0` 表示填写所有仍有 AI 字段缺失的行。
   - 如果只是测试，可以填 `3` 或 `5`。
4. 设置“并发数”：
   - 默认 `3`。
   - 如果出现网络或 SSL 错误，建议改成 `1` 或 `2`。
5. 点击“AI填写总表”。

“只回填ID/互动量”按钮不会调用 AI，只会补：

- 笔记ID
- 互动量
- 渠道类型

AI 填写逻辑：

- 不是只填刚刚追加的数据。
- 每次点击时，会扫描当前平台整张监控表。
- 只要 AI 字段存在空值，就会尝试回填。
- 已经有值的 AI 字段默认不会覆盖。

English:

Steps:

1. Select a platform.
2. Choose a model in the AI filling section.
3. Set `最多行`:
   - `0` means fill all rows with missing AI fields.
   - Use `3` or `5` for testing.
4. Set concurrency:
   - Default is `3`.
   - If network or SSL errors appear, reduce it to `1` or `2`.
5. Click `AI填写总表`.

The `只回填ID/互动量` button does not call AI. It only fills:

- Note ID
- Interaction count
- Channel type

AI filling behavior:

- It is not limited to newly appended rows.
- Each click scans the full monitoring table for the current platform.
- Any row with missing AI fields is eligible.
- Existing AI field values are not overwritten by default.

---

## 17. 口碑加热候选 / Amplification Candidate Export

中文：

使用步骤：

1. 选择平台。
2. 确认该平台监控总表中已经有 AI 字段，尤其是 `正负向`。
3. 在“口碑加热候选”区域选择开始日期和结束日期。
4. 设置“最多判断”：
   - 默认 `30`。
   - `0` 表示判断日期区间内全部候选。
5. 设置“入选门槛”：
   - `只写入“值得加热”`
   - `含“建议小额测试”`
6. 可以先勾选“只预览，不写入 Excel”。
7. 点击：
   - `Hype模型写入Excel`
   - 或 `AI判断写入Excel`

重要规则：

- 加热候选只允许 `正负向=正向` 的内容进入判断。
- 负向、中性、无匹配类别都会被跳过。
- 小红书写入：

```text
Hype_Something/2026_Didi_Xiaohongshu_Daily_Word-of-Mouth_Amplification.xlsx
```

- 抖音写入：

```text
Hype_Something/2026_Didi_Douyin_Daily_Word-of-Mouth_Amplification.xlsx
```

English:

Steps:

1. Select a platform.
2. Make sure the platform monitoring table has AI-filled fields, especially `正负向`.
3. Select a start date and end date in the amplification section.
4. Set `最多判断`:
   - Default is `30`.
   - `0` means judge all candidates in the date range.
5. Set the entry threshold:
   - Only write `值得加热`.
   - Or include `建议小额测试`.
6. You can first enable `只预览，不写入 Excel`.
7. Click:
   - `Hype模型写入Excel`
   - or `AI判断写入Excel`

Important rule:

- Only rows with `正负向=正向` can enter amplification judgment.
- Negative, neutral, or unmatched rows are skipped.
- Rednote/Xiaohongshu writes to:

```text
Hype_Something/2026_Didi_Xiaohongshu_Daily_Word-of-Mouth_Amplification.xlsx
```

- Douyin writes to:

```text
Hype_Something/2026_Didi_Douyin_Daily_Word-of-Mouth_Amplification.xlsx
```

---

## 18. 命令行用法 / Command-Line Usage

中文：

GUI 是推荐方式。如果需要单独调试脚本，可以用命令行。

小红书单帖：

```bash
python3 Pipeline/xhs_note_to_csv.py --use-default-profile \
  --output Pipeline/xhs_origin_data.csv \
  --summary-output Pipeline/xhs_note_10_fields.csv \
  "https://www.xiaohongshu.com/discovery/item/..."
```

小红书关键词：

```bash
python3 Pipeline/xhs_search_to_csv.py "滴滴打车" \
  --output Pipeline/xhs_origin_data.csv \
  --summary-output Pipeline/xhs_note_10_fields.csv \
  --max-notes 10 \
  --headed
```

小红书评论：

```bash
python3 Pipeline/xhs_comment_to_csv.py --use-default-profile \
  --output Pipeline/xhs_comments.csv \
  --limit 100 \
  "https://www.xiaohongshu.com/discovery/item/..."
```

抖音单帖：

```bash
python3 Pipeline/dy_note_to_csv.py --use-default-profile \
  --output Pipeline/dy_origin_data.csv \
  --summary-output Pipeline/dy_note_10_fields.csv \
  "https://www.douyin.com/video/..."
```

抖音关键词：

```bash
python3 Pipeline/dy_search_to_csv.py "滴滴打车" \
  --output Pipeline/dy_origin_data.csv \
  --summary-output Pipeline/dy_note_10_fields.csv \
  --max-notes 10 \
  --headed
```

抖音评论：

```bash
python3 Pipeline/dy_comment_to_csv.py --use-default-profile \
  --output Pipeline/dy_comments.csv \
  --limit 100 \
  "https://www.douyin.com/video/..."
```

AI 回填：

```bash
python3 Pipeline/xhs_ai_fill_table.py --limit 0 --concurrency 3
python3 Pipeline/dy_ai_fill_table.py --limit 0 --concurrency 3
```

加热导出 dry-run：

```bash
python3 Pipeline/xhs_amplification_export.py \
  --start-date 2026-06-01 \
  --end-date 2026-06-17 \
  --dry-run

python3 Pipeline/dy_amplification_export.py \
  --start-date 2026-06-01 \
  --end-date 2026-06-17 \
  --dry-run
```

English:

The GUI is the recommended way. For debugging, you can run scripts directly.

Rednote/Xiaohongshu single post:

```bash
python3 Pipeline/xhs_note_to_csv.py --use-default-profile \
  --output Pipeline/xhs_origin_data.csv \
  --summary-output Pipeline/xhs_note_10_fields.csv \
  "https://www.xiaohongshu.com/discovery/item/..."
```

Rednote/Xiaohongshu keyword search:

```bash
python3 Pipeline/xhs_search_to_csv.py "滴滴打车" \
  --output Pipeline/xhs_origin_data.csv \
  --summary-output Pipeline/xhs_note_10_fields.csv \
  --max-notes 10 \
  --headed
```

Rednote/Xiaohongshu comments:

```bash
python3 Pipeline/xhs_comment_to_csv.py --use-default-profile \
  --output Pipeline/xhs_comments.csv \
  --limit 100 \
  "https://www.xiaohongshu.com/discovery/item/..."
```

Douyin single post:

```bash
python3 Pipeline/dy_note_to_csv.py --use-default-profile \
  --output Pipeline/dy_origin_data.csv \
  --summary-output Pipeline/dy_note_10_fields.csv \
  "https://www.douyin.com/video/..."
```

Douyin keyword search:

```bash
python3 Pipeline/dy_search_to_csv.py "滴滴打车" \
  --output Pipeline/dy_origin_data.csv \
  --summary-output Pipeline/dy_note_10_fields.csv \
  --max-notes 10 \
  --headed
```

Douyin comments:

```bash
python3 Pipeline/dy_comment_to_csv.py --use-default-profile \
  --output Pipeline/dy_comments.csv \
  --limit 100 \
  "https://www.douyin.com/video/..."
```

AI fill:

```bash
python3 Pipeline/xhs_ai_fill_table.py --limit 0 --concurrency 3
python3 Pipeline/dy_ai_fill_table.py --limit 0 --concurrency 3
```

Amplification dry-run:

```bash
python3 Pipeline/xhs_amplification_export.py \
  --start-date 2026-06-01 \
  --end-date 2026-06-17 \
  --dry-run

python3 Pipeline/dy_amplification_export.py \
  --start-date 2026-06-01 \
  --end-date 2026-06-17 \
  --dry-run
```

### 18.1 无人值守日循环 / Unattended Daily Loop

中文：

根目录 `daily_work.py` 用于循环执行完整日常流程，适合放在本机长期运行。默认流程是：

1. 小红书和抖音双平台关键词搜索。
2. 清洗双平台总表。
3. 双平台并行 AI 填写。
4. 再次清洗双平台总表。
5. Hype 模型写入加热 Excel。
6. AI 判断写入加热 Excel。
7. 休眠后继续下一轮。

默认关键词为：

```text
滴滴打车、滴滴快车、滴滴司机、滴滴宠物、滴滴安全、滴滴女司机、滴滴专车、滴滴特惠、滴滴巴士、滴滴香卡、滴滴豪华车、滴滴拼车、滴滴车站、滴滴海外打车、滴滴轻享、滴滴出租车、滴滴特快、滴滴 AI打车、滴滴 AI 叫车、滴滴IP彩蛋车
```

默认发布时间筛选是 `一周内`，默认 `--max-notes 0` 表示每个关键词不设硬上限。

先测试一轮：

```bash
cd /Users/didi/Downloads/Public_Opinion_Analysis
python3 daily_work.py --once --verbose-stdout
```

长期循环运行：

```bash
cd /Users/didi/Downloads/Public_Opinion_Analysis
python3 daily_work.py
```

常用参数：

| 参数 | 默认值 | 说明 |
|---|---:|---|
| `--once` | 关闭 | 只执行一轮后退出 |
| `--publish-time` | `一周内` | 关键词搜索发布时间筛选 |
| `--max-notes` | `0` | 每个平台每个关键词最大导出数；`0` 表示不设上限 |
| `--scroll-rounds` | `10` | 每个关键词搜索滚动轮数 |
| `--keyword-sleep` | `20` | 关键词之间休眠秒数 |
| `--cycle-sleep` | `1800` | 每轮结束后的休眠秒数 |
| `--ai-concurrency` | `3` | 单平台 AI 填写并发数 |
| `--hype-limit` | `0` | 加热候选最多判断行数；`0` 表示不设上限 |
| `--dry-run` | 关闭 | 只预览加热写入，不写 Excel |

账号被限流或出现安全页时，不建议继续无人值守循环。应先停止脚本，等网页端普通浏览恢复后再启动，并适当调大 `--keyword-sleep` 和 `--cycle-sleep`。

English:

The root `daily_work.py` runs the full daily workflow in a loop and is suitable for unattended local operation. The default workflow is:

1. Run dual-platform keyword search for Rednote/Xiaohongshu and Douyin.
2. Clean both platform monitoring tables.
3. Run parallel AI filling for both platforms.
4. Clean both tables again.
5. Write amplification candidates with the Hype model.
6. Write amplification candidates with AI judgment.
7. Sleep and start the next cycle.

Default keywords:

```text
滴滴打车、滴滴快车、滴滴司机、滴滴宠物、滴滴安全、滴滴女司机、滴滴专车、滴滴特惠、滴滴巴士、滴滴香卡、滴滴豪华车、滴滴拼车、滴滴车站、滴滴海外打车、滴滴轻享、滴滴出租车、滴滴特快、滴滴 AI打车、滴滴 AI 叫车、滴滴IP彩蛋车
```

The default publish-time filter is `一周内`, and `--max-notes 0` means no hard limit per keyword.

Run one test cycle:

```bash
cd /Users/didi/Downloads/Public_Opinion_Analysis
python3 daily_work.py --once --verbose-stdout
```

Run continuously:

```bash
cd /Users/didi/Downloads/Public_Opinion_Analysis
python3 daily_work.py
```

Common arguments:

| Argument | Default | Description |
|---|---:|---|
| `--once` | off | Run one cycle and exit |
| `--publish-time` | `一周内` | Keyword search publish-time filter |
| `--max-notes` | `0` | Max rows per platform per keyword; `0` means unlimited |
| `--scroll-rounds` | `10` | Scroll rounds per keyword search |
| `--keyword-sleep` | `20` | Sleep seconds between keywords |
| `--cycle-sleep` | `1800` | Sleep seconds after each full cycle |
| `--ai-concurrency` | `3` | Per-platform AI filling concurrency |
| `--hype-limit` | `0` | Max amplification candidates to judge; `0` means unlimited |
| `--dry-run` | off | Preview amplification output without writing Excel |

If the account is rate-limited or security pages appear, stop the unattended loop first. Restart only after normal web browsing recovers, and consider increasing `--keyword-sleep` and `--cycle-sleep`.

---

## 19. 登录态与反爬注意事项 / Login Session and Anti-Bot Notes

中文：

脚本会克隆本机 Chrome 默认 Profile 到临时目录，尽量复用你已经登录的平台 Cookie。这样不会直接改动你的 Chrome 原 Profile。

建议：

- 先在 Chrome 中正常登录小红书和抖音。
- 如果 Edge 也登录了备用账号，单帖修复和小红书兜底会优先按可用浏览器账号轮换尝试，避免同一账号连续撞安全页。
- 采集时保留可见 Chrome 页面，不要快速关闭。
- 关键词采集不要设置过大数量。
- 不要连续高频重复点击。
- 如果出现验证码、安全验证、登录墙，请在打开的浏览器中手动处理后再重试。
- 如果小红书链接缺少 `xsec_token`，脚本会优先尝试 `/explore/{note_id}?xsec_source=pc_search`、本地历史 token 和多种分享入口；如果仍失败，请重新复制完整分享链接。
- 小红书脚本会拒绝把 `404`、`300031`、安全限制页或明显广告页内容写进 CSV。
- 如果抖音链接是短链，脚本会尝试打开页面解析真实 `aweme_id`。

如果需要使用真实浏览器 DOM 兜底读取当前已打开的小红书页面，macOS 需要允许浏览器执行 AppleScript JavaScript。可以在浏览器菜单中开启“查看 > 开发者 > 允许 Apple 事件中的 JavaScript”，也可以运行：

```bash
defaults write com.google.Chrome AppleScriptEnabled -bool true
defaults write com.microsoft.Edge AppleScriptEnabled -bool true
```

设置后需要重启 Chrome 或 Edge。

English:

The scripts clone the local Chrome default profile into a temporary directory and try to reuse your existing login cookies. They do not directly modify your original Chrome profile.

Recommendations:

- Log in to Rednote/Xiaohongshu and Douyin in Chrome first.
- If Edge is also logged in with a backup account, single-post repair and Rednote/Xiaohongshu fallback can rotate across available browser accounts, reducing repeated failures on the same account.
- Keep the visible Chrome page open during collection.
- Do not use an overly large keyword collection count.
- Avoid repeated high-frequency clicks.
- If CAPTCHA, security verification, or login walls appear, complete them manually in the opened browser and retry.
- If a Rednote/Xiaohongshu link is missing `xsec_token`, the script first tries `/explore/{note_id}?xsec_source=pc_search`, local historical tokens, and multiple share entrances. If that still fails, copy a fresh full share URL.
- The Rednote/Xiaohongshu script refuses to write `404`, `300031`, security-limit pages, or obvious ad pages into CSV.
- If a Douyin link is a short link, the script attempts to open the page and resolve the real `aweme_id`.

If the real-browser DOM fallback is needed for a currently opened Rednote/Xiaohongshu page, macOS must allow the browser to execute JavaScript through AppleScript. Enable `View > Developer > Allow JavaScript from Apple Events` in the browser menu, or run:

```bash
defaults write com.google.Chrome AppleScriptEnabled -bool true
defaults write com.microsoft.Edge AppleScriptEnabled -bool true
```

Restart Chrome or Edge after changing this setting.

---

## 20. 媒体增强、OCR 与 ASR / Media Enrichment, OCR, and ASR

中文：

单帖子查询和粘贴板帖子查询会默认启用媒体增强：

- 从接口字段中识别当前帖子的图片、视频或视频音轨 URL。
- 下载媒体到项目相对路径 `cache/`。
- 图片通过本地 OCR 提取文字，并追加到监控表 `笔记内容` 字段，格式为 `【第1张图片中的文字内容】`。
- 视频或音轨通过本地 ASR 提取语音文本，并追加到监控表 `笔记内容` 字段，格式为 `【第1个视频中的语音内容】`。
- 单条帖子处理完成后自动删除本次 `cache/` 临时目录。

关键词批量搜索默认不启用媒体增强，避免在账号限流或大批量采集时额外放大请求量。如需命令行开启，可以加：

```bash
python3 Pipeline/xhs_search_to_csv.py "滴滴打车" --media-enrich --max-notes 3 --headed
python3 Pipeline/dy_search_to_csv.py "滴滴打车" --media-enrich --max-notes 3 --headed
```

图片文字识别统一通过 `Pipeline/ocr_adapter.py` 调用。

- Windows：强制使用项目内置 `Wechat_OCR/OCR` 或 `wechat_ocr/OCR` 中的 WeChatOCR。初始化失败或执行失败时直接报错，不允许自动切换到其他 OCR。
- macOS：使用 macOS 原生 Vision OCR，通过 PyObjC 调用，支持中文识别。首次使用前请运行 `python3 -m pip install -r requirements.txt`。
- 其他平台：当前不自动兜底，脚本会明确报错。

视频语音转文字使用本地 `faster-whisper-small` 模型，模型放在项目相对路径 `modelfile/faster-whisper-small`。如果模型缺失，运行：

```bash
python3 Pipeline/download_asr_model.py --model small
```

命令行测试：

```bash
python3 Pipeline/ocr_adapter.py /path/to/image.png
python3 Pipeline/ocr_adapter.py /path/to/image.png --json
```

English:

Single-post queries and clipboard-post queries enable media enrichment by default:

- Media URLs are extracted from the already collected API fields.
- Media files are downloaded into the project-relative `cache/` directory.
- Image text is extracted by local OCR and appended to the monitoring table `笔记内容` field as `【第1张图片中的文字内容】`.
- Video or audio speech is transcribed by local ASR and appended as `【第1个视频中的语音内容】`.
- The temporary `cache/` folder for that post is deleted after processing.

Keyword search does not enable media enrichment by default, so large batch jobs do not add extra media requests while an account is rate-limited. To enable it from the command line:

```bash
python3 Pipeline/xhs_search_to_csv.py "滴滴打车" --media-enrich --max-notes 3 --headed
python3 Pipeline/dy_search_to_csv.py "滴滴打车" --media-enrich --max-notes 3 --headed
```

Image OCR is centralized in `Pipeline/ocr_adapter.py`.

- Windows: always use the bundled WeChatOCR from `Wechat_OCR/OCR` or `wechat_ocr/OCR`. If initialization or OCR execution fails, the script raises an error. It must not fall back to any other OCR engine.
- macOS: use Apple's native Vision OCR through PyObjC, with Chinese recognition support. Install dependencies first with `python3 -m pip install -r requirements.txt`.
- Other platforms: no automatic fallback; the script fails explicitly.

Video speech transcription uses the local `faster-whisper-small` model under the project-relative `modelfile/faster-whisper-small` path. If the model is missing, run:

```bash
python3 Pipeline/download_asr_model.py --model small
```

CLI test:

```bash
python3 Pipeline/ocr_adapter.py /path/to/image.png
python3 Pipeline/ocr_adapter.py /path/to/image.png --json
```

---

## 21. 常见问题 / Troubleshooting

中文：

### 21.1 GUI 打不开

检查：

```bash
cd /Users/didi/Downloads/Public_Opinion_Analysis
python3 Pipeline/pipeline_gui_server.py
```

如果提示端口占用，脚本会自动换端口。看终端输出的本地 URL。

### 21.2 提示缺少 openpyxl

运行：

```bash
python3 -m pip install -r requirements.txt
```

### 21.3 AI 填写报 SSL EOF 或 curl SSL 错误

可以尝试：

- 把并发数改成 `1` 或 `2`。
- 再点击一次，脚本会继续填仍为空的行。
- 换模型，例如 `glm-5.1-internal` 或 `minimax-m2.5-external`。

### 21.4 小红书关键词报没有识别到 xsec_token

可能原因：

- 未登录。
- 页面出现安全验证。
- 页面结构变化。
- 搜索页没有加载出真实笔记卡片。

处理：

- 确认 Chrome 已登录小红书。
- 打开的页面中手动完成验证。
- 降低抓取频率。
- 换关键词或减少“最多笔记”。

### 21.5 抖音搜索没有识别到视频卡片

可能原因：

- 未登录。
- 页面要求验证。
- 抖音搜索页面结构变更。
- 当前关键词结果较少。

处理：

- 确认 Chrome 已登录抖音。
- 手动完成验证。
- 用 `--headed` 打开可见页面观察。
- 先用小数量测试，例如 `--max-notes 5`。

### 21.6 Excel 无法保存

可能原因：

- 目标 Excel 正在被 WPS、Excel 或 Numbers 打开。

处理：

- 关闭目标 Excel。
- 重新点击写入按钮。
- 先勾选 dry-run 确认候选，再正式写入。

English:

### 21.1 GUI does not open

Check manually:

```bash
cd /Users/didi/Downloads/Public_Opinion_Analysis
python3 Pipeline/pipeline_gui_server.py
```

If a port is occupied, the script automatically chooses another one. Check the local URL printed in Terminal.

### 21.2 Missing openpyxl

Run:

```bash
python3 -m pip install -r requirements.txt
```

### 21.3 AI filling reports SSL EOF or curl SSL errors

Try:

- Reduce concurrency to `1` or `2`.
- Click again. The script will continue filling rows that are still blank.
- Switch models, for example `glm-5.1-internal` or `minimax-m2.5-external`.

### 21.4 Rednote/Xiaohongshu keyword search cannot find xsec_token

Possible reasons:

- Not logged in.
- Security verification is shown.
- Page structure changed.
- The search page did not load real note cards.

Fixes:

- Make sure Chrome is logged in to Rednote/Xiaohongshu.
- Complete verification in the opened browser page.
- Reduce collection frequency.
- Try another keyword or reduce max notes.

### 21.5 Douyin search cannot identify video cards

Possible reasons:

- Not logged in.
- Verification is required.
- Douyin search page structure changed.
- The keyword has too few results.

Fixes:

- Make sure Chrome is logged in to Douyin.
- Complete verification manually.
- Use `--headed` to observe the visible page.
- Start with a small amount, for example `--max-notes 5`.

### 21.6 Excel cannot be saved

Possible reason:

- The target Excel workbook is open in WPS, Excel, or Numbers.

Fix:

- Close the workbook.
- Click the write button again.
- Use dry-run first, then write officially.

### 21.7 小红书出现 `安全限制 / Too many requests / 300013`

中文：

这表示当前账号或浏览器会话已经被平台限流。不要继续高频刷新、批量搜索或反复重启脚本，否则限制时间可能变长。推荐处理方式：

1. 立即暂停自动采集，至少等待数小时；如果网页端普通浏览也报错，建议等到第二天再恢复。
2. 在 Chrome 中手动打开小红书，确认普通浏览、搜索、打开帖子都恢复正常后，再运行工具。
3. 恢复后先用小批量参数测试，例如关键词最多 3-5 条，滚动轮数 2-3 轮。
4. 拉长两次任务之间的间隔，不要连续跑大量关键词。
5. 避免同一账号同时在多个脚本、多个浏览器窗口或多台设备上高频访问。
6. 如果需要稳定、大规模数据，应优先使用平台授权接口、企业数据服务或经过许可的数据源。

本项目不会提供绕过安全限制、伪装身份、规避风控的能力；代码侧只做保守降频、减少请求和失败提示。

English:

This means the current account or browser session is rate-limited by the platform. Do not keep refreshing, searching, or restarting the scripts aggressively, because that may extend the restriction window. Recommended recovery:

1. Stop automated collection immediately and wait for several hours; if normal web browsing also fails, wait until the next day.
2. Open Rednote/Xiaohongshu manually in Chrome and confirm normal browsing, search, and note opening work again.
3. Resume with a very small batch, for example 3-5 notes and 2-3 scroll rounds.
4. Increase the interval between jobs and avoid running many keywords back-to-back.
5. Avoid using the same account from multiple scripts, browser windows, or devices at high frequency.
6. For stable large-scale data collection, prefer official/authorized APIs, enterprise data services, or licensed data sources.

This project does not provide bypasses for platform safety controls, identity spoofing, or risk-control circumvention. The code only supports conservative throttling, fewer requests, and clearer failure messages.

### 21.8 小红书单帖停在 404/300031 或真实浏览器 DOM 兜底失败

中文：

如果日志出现“所有小红书候选入口都未进入目标详情页”或“页面仍停留在 404/300031 安全页”，说明当前账号或入口无法稳定打开目标笔记。处理顺序：

1. 在 Chrome 或 Edge 中手动打开目标链接，确认能看到真实帖子内容，而不是安全页、广告页或首页。
2. 优先尝试 `https://www.xiaohongshu.com/explore/{note_id}?xsec_source=pc_search` 形式。
3. 如果你手上有完整分享链接，优先粘贴带 `xsec_token` 的完整链接。
4. 如果日志提示 `Executing JavaScript through AppleScript is turned off`，开启浏览器菜单“查看 > 开发者 > 允许 Apple 事件中的 JavaScript”，或运行第 19 节中的 `defaults write` 命令并重启浏览器。
5. 如果 Social_Media_Copilot 插件能在真实页面中复制笔记信息，可以先在浏览器里打开帖子并使用插件复制，再回到 Pipeline 重新执行。
6. 如果普通网页浏览也提示 `300013` 或 Too many requests，停止脚本并等待账号恢复。

English:

If the log says all Rednote/Xiaohongshu candidate entrances failed, or the page remains on `404` / `300031`, the current account or entrance cannot reliably open the target note. Recommended order:

1. Open the target URL manually in Chrome or Edge and confirm that the real post is visible, not a security page, ad page, or homepage.
2. Prefer `https://www.xiaohongshu.com/explore/{note_id}?xsec_source=pc_search`.
3. If you have a full share URL, use the complete URL with `xsec_token` first.
4. If the log says `Executing JavaScript through AppleScript is turned off`, enable `View > Developer > Allow JavaScript from Apple Events`, or run the `defaults write` commands in section 19 and restart the browser.
5. If Social_Media_Copilot can copy note information from the real page, open the post in the browser, copy through the plugin, then rerun Pipeline.
6. If normal web browsing also shows `300013` or Too many requests, stop the script and wait for the account to recover.

---

## 22. 安全注意事项 / Security Notes

中文：

- 不要把 `llm_config.json` 分享给外部人员，因为里面可能包含 API Key。
- 不要分享浏览器 Cookie、登录态、验证码或个人账号信息。
- 不要把采集到的评论、用户信息和链接发到不可信环境。
- 如果需要把项目打包给同事，建议删除：

```text
Hype_Something/llm_config.json
Hype_Something/cookies.txt
Pipeline/*.log
Pipeline/gui_exports/
```

English:

- Do not share `llm_config.json` externally because it may contain an API key.
- Do not share browser cookies, login sessions, verification codes, or personal account information.
- Do not send collected comments, user information, or links to untrusted environments.
- If packaging this project for colleagues, consider deleting:

```text
Hype_Something/llm_config.json
Hype_Something/cookies.txt
Pipeline/*.log
Pipeline/gui_exports/
```

---

## 23. 推荐日常流程 / Recommended Daily Workflow

中文：

1. 打开 Chrome，确认小红书和抖音登录状态正常。
2. 双击 `run_public_opinion_suite.command`，先进入可视化大屏首页。
3. 需要采集或回填时，点击右上角“打开舆情采集工作台”。
4. 在 Pipeline 中选择平台。
5. 先跑小数量关键词搜索，例如 10 条。
6. 检查当前平台监控总表是否追加正常。
7. 点击“清洗当前平台总表”去重并删除招聘/实习类脏数据。
8. 点击“AI填写总表”补齐分析字段。
9. 在“口碑加热候选”选择日期范围。
10. 先勾选 dry-run 预览。
11. 确认候选合理后取消 dry-run，写入对应平台 Excel。
12. 如需进一步人工判断，打开 `Hype_Something/start_tool.command` 或点击 GUI 中“打开Hype软件界面”。

无人值守方式：

```bash
cd /Users/didi/Downloads/Public_Opinion_Analysis
python3 daily_work.py --once --verbose-stdout
python3 daily_work.py
```

第一行用于测试一轮，第二行用于持续循环。账号出现风控时请先停止循环。

English:

1. Open Chrome and confirm login status for Rednote/Xiaohongshu and Douyin.
2. Double-click `run_public_opinion_suite.command` and enter the Visualization dashboard first.
3. When collection or backfill is needed, click `打开舆情采集工作台` in the top-right corner.
4. Select a platform in Pipeline.
5. Start with a small keyword search, for example 10 rows.
6. Check that the current platform monitoring table is appended correctly.
7. Click `清洗当前平台总表` to deduplicate and remove recruitment/internship dirty rows.
8. Click `AI填写总表` to fill analysis fields.
9. Select a date range in the amplification section.
10. Enable dry-run for preview.
11. If the candidates look reasonable, disable dry-run and write to the platform workbook.
12. For further manual judgment, open `Hype_Something/start_tool.command` or click `打开Hype软件界面` in the GUI.

Unattended mode:

```bash
cd /Users/didi/Downloads/Public_Opinion_Analysis
python3 daily_work.py --once --verbose-stdout
python3 daily_work.py
```

The first command runs one test cycle. The second command runs continuously. Stop the loop first if the account hits platform rate limits.

---

## 24. 维护说明 / Maintenance Notes

中文：

- 小红书和抖音网页结构可能变化。如果搜索页突然抓不到内容，优先检查页面是否需要登录或验证。
- 平台接口字段可能变化。如果监控总表出现空字段，检查对应的 `xhs_*` 或 `dy_*` 归一化脚本。
- 加热 Excel 表头如果被人工改动，导出脚本可能需要同步更新表头别名。
- 抖音和小红书链路是独立的。修改新平台逻辑时，不要直接改旧平台脚本，优先改对应 `dy_*` 或 `xhs_*` 文件。
- 可视化大屏表格长文本依赖统一的截断和悬浮预览逻辑。新增表格时优先复用现有渲染函数，避免长文本把列撑窄。
- 小红书单帖采集应继续复用候选入口生成和安全页识别逻辑，不要把 404、安全限制页或广告页作为正常内容写入总表。

English:

- Rednote/Xiaohongshu and Douyin web structures may change. If search suddenly fails, first check whether login or verification is required.
- Platform API fields may change. If normalized monitoring fields become blank, inspect the corresponding `xhs_*` or `dy_*` normalization script.
- If workbook headers are manually changed, the export script may need updated header aliases.
- Douyin and Rednote/Xiaohongshu flows are independent. When changing one platform, avoid modifying the other platform scripts unless necessary.
- Visualization tables rely on shared truncation and hover-preview behavior. Reuse the existing table rendering helpers when adding new tables, so long text does not squeeze columns.
- Rednote/Xiaohongshu single-post collection should keep using candidate entrance generation and security-page detection. Do not write 404, security-limit, or ad pages as normal content.
