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
├── Pipeline
│   ├── run_xhs_note_gui.command
│   ├── xhs_gui_server.py
│   ├── xhs_gui.html
│   ├── xhs_gui.js
│   ├── xhs_gui.css
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
│   ├── origin_data.csv
│   ├── Data_Table_on_Channel_Public_Opinion_Monitoring_2026.csv
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
├── Social_Media_Copilot
└── requirements.txt
```

English:

The core folders are:

```text
/Users/didi/Downloads/Public_Opinion_Analysis
├── Pipeline                 # Collection GUI, scripts, normalized CSV outputs
├── Hype_Something           # Local Hype judgment tool and Excel workbooks
├── Social_Media_Copilot     # Reference open-source plugin logic
└── requirements.txt         # Python dependency file
```

---

## 3. 环境要求 / Environment Requirements

中文：

建议环境：

- macOS。
- Python 3.10 或更高版本。
- Google Chrome 或 Microsoft Edge。
- 已在 Chrome 中登录需要采集的平台：
  - 小红书：https://www.xiaohongshu.com
  - 抖音：https://www.douyin.com
- Node.js 18 或更高版本。仅在需要打开 `Hype_Something` 独立软件界面时需要。
- 网络可以访问小红书、抖音和公司 LLM Proxy。

English:

Recommended environment:

- macOS.
- Python 3.10 or later.
- Google Chrome or Microsoft Edge.
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

`requirements.txt` 当前只包含 `openpyxl`，用于读取和写入 `.xlsx` 加热表。采集、CSV 处理、GUI 服务和 AI 请求主要使用 Python 标准库。

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

The current Python dependency is `openpyxl`, which is used for reading and writing `.xlsx` amplification workbooks. Collection, CSV processing, the GUI server, and AI requests mainly use the Python standard library.

---

## 5. 首次运行前检查 / First-Time Checklist

中文：

1. 确认 Chrome 已安装。
2. 用 Chrome 登录小红书和抖音。
3. 确认 `Pipeline/run_xhs_note_gui.command` 可以执行：

```bash
chmod +x /Users/didi/Downloads/Public_Opinion_Analysis/Pipeline/run_xhs_note_gui.command
```

4. 如果 macOS 提示“无法打开来自未知开发者的文件”，右键点击 `run_xhs_note_gui.command`，选择“打开”。
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
chmod +x /Users/didi/Downloads/Public_Opinion_Analysis/Pipeline/run_xhs_note_gui.command
```

4. If macOS blocks the file as coming from an unidentified developer, right-click `run_xhs_note_gui.command` and choose Open.
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

最简单方式是双击：

```text
/Users/didi/Downloads/Public_Opinion_Analysis/Pipeline/run_xhs_note_gui.command
```

也可以在终端中运行：

```bash
cd /Users/didi/Downloads/Public_Opinion_Analysis
bash Pipeline/run_xhs_note_gui.command
```

启动后会自动打开本地网页，地址类似：

```text
http://127.0.0.1:8765/
```

如果 8765 被占用，程序会自动换到附近可用端口。

English:

The easiest way is to double-click:

```text
/Users/didi/Downloads/Public_Opinion_Analysis/Pipeline/run_xhs_note_gui.command
```

Or run it in Terminal:

```bash
cd /Users/didi/Downloads/Public_Opinion_Analysis
bash Pipeline/run_xhs_note_gui.command
```

The local web GUI will open automatically at a URL like:

```text
http://127.0.0.1:8765/
```

If port 8765 is already in use, the server will automatically choose a nearby available port.

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

English:

Under the `Rednote Export / Public Opinion Pipeline` area in the top-left corner, there is a platform switch:

- Rednote/Xiaohongshu
- Douyin

After switching platforms, the same GUI buttons automatically call platform-specific scripts:

| Platform | Single post | Search | Comments | AI fill | Amplification export |
|---|---|---|---|---|---|
| Rednote/Xiaohongshu | `xhs_note_to_csv.py` | `xhs_search_to_csv.py` | `xhs_comment_to_csv.py` | `xhs_ai_fill_table.py` | `xhs_amplification_export.py` |
| Douyin | `dy_note_to_csv.py` | `dy_search_to_csv.py` | `dy_comment_to_csv.py` | `dy_ai_fill_table.py` | `dy_amplification_export.py` |

---

## 9. 输出文件 / Output Files

中文：

小红书输出：

| 文件 | 说明 |
|---|---|
| `Pipeline/origin_data.csv` | 小红书全量原始字段追加表 |
| `Pipeline/Data_Table_on_Channel_Public_Opinion_Monitoring_2026.csv` | 小红书监控总表 |
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
| `Pipeline/origin_data.csv` | Full raw Rednote/Xiaohongshu field table |
| `Pipeline/Data_Table_on_Channel_Public_Opinion_Monitoring_2026.csv` | Rednote/Xiaohongshu monitoring table |
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

抖音：

```text
https://www.douyin.com/video/...
```

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

Douyin:

```text
https://www.douyin.com/video/...
```

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

English:

Comment collection only works for one specific post/video link from the single-post or clipboard workflow. It does not collect comments for keyword batch results automatically.

Buttons:

- `爬取文本框评论`: collect comments from the current text box link.
- `粘贴板评论爬取`: collect comments from the clipboard link.

Outputs:

- Rednote/Xiaohongshu comments are appended to `Pipeline/xhs_comments.csv`.
- Douyin comments are appended to `Pipeline/dy_comments.csv`.

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

---

## 14. 监控总表字段 / Monitoring Table Fields

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

## 15. AI 填写总表 / AI Table Filling

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

## 16. 口碑加热候选 / Amplification Candidate Export

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

## 17. 命令行用法 / Command-Line Usage

中文：

GUI 是推荐方式。如果需要单独调试脚本，可以用命令行。

小红书单帖：

```bash
python3 Pipeline/xhs_note_to_csv.py --use-default-profile \
  --output Pipeline/origin_data.csv \
  --summary-output Pipeline/xhs_note_10_fields.csv \
  "https://www.xiaohongshu.com/discovery/item/..."
```

小红书关键词：

```bash
python3 Pipeline/xhs_search_to_csv.py "滴滴打车" \
  --output Pipeline/origin_data.csv \
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
  --output Pipeline/origin_data.csv \
  --summary-output Pipeline/xhs_note_10_fields.csv \
  "https://www.xiaohongshu.com/discovery/item/..."
```

Rednote/Xiaohongshu keyword search:

```bash
python3 Pipeline/xhs_search_to_csv.py "滴滴打车" \
  --output Pipeline/origin_data.csv \
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

---

## 18. 登录态与反爬注意事项 / Login Session and Anti-Bot Notes

中文：

脚本会克隆本机 Chrome 默认 Profile 到临时目录，尽量复用你已经登录的平台 Cookie。这样不会直接改动你的 Chrome 原 Profile。

建议：

- 先在 Chrome 中正常登录小红书和抖音。
- 采集时保留可见 Chrome 页面，不要快速关闭。
- 关键词采集不要设置过大数量。
- 不要连续高频重复点击。
- 如果出现验证码、安全验证、登录墙，请在打开的浏览器中手动处理后再重试。
- 如果小红书链接缺少或失效 `xsec_token`，请重新复制分享链接。
- 如果抖音链接是短链，脚本会尝试打开页面解析真实 `aweme_id`。

English:

The scripts clone the local Chrome default profile into a temporary directory and try to reuse your existing login cookies. They do not directly modify your original Chrome profile.

Recommendations:

- Log in to Rednote/Xiaohongshu and Douyin in Chrome first.
- Keep the visible Chrome page open during collection.
- Do not use an overly large keyword collection count.
- Avoid repeated high-frequency clicks.
- If CAPTCHA, security verification, or login walls appear, complete them manually in the opened browser and retry.
- If a Rednote/Xiaohongshu link has a missing or expired `xsec_token`, copy a fresh share link.
- If a Douyin link is a short link, the script attempts to open the page and resolve the real `aweme_id`.

---

## 19. 常见问题 / Troubleshooting

中文：

### 19.1 GUI 打不开

检查：

```bash
cd /Users/didi/Downloads/Public_Opinion_Analysis
python3 Pipeline/xhs_gui_server.py
```

如果提示端口占用，脚本会自动换端口。看终端输出的本地 URL。

### 19.2 提示缺少 openpyxl

运行：

```bash
python3 -m pip install -r requirements.txt
```

### 19.3 AI 填写报 SSL EOF 或 curl SSL 错误

可以尝试：

- 把并发数改成 `1` 或 `2`。
- 再点击一次，脚本会继续填仍为空的行。
- 换模型，例如 `glm-5.1-internal` 或 `minimax-m2.5-external`。

### 19.4 小红书关键词报没有识别到 xsec_token

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

### 19.5 抖音搜索没有识别到视频卡片

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

### 19.6 Excel 无法保存

可能原因：

- 目标 Excel 正在被 WPS、Excel 或 Numbers 打开。

处理：

- 关闭目标 Excel。
- 重新点击写入按钮。
- 先勾选 dry-run 确认候选，再正式写入。

English:

### 19.1 GUI does not open

Check manually:

```bash
cd /Users/didi/Downloads/Public_Opinion_Analysis
python3 Pipeline/xhs_gui_server.py
```

If a port is occupied, the script automatically chooses another one. Check the local URL printed in Terminal.

### 19.2 Missing openpyxl

Run:

```bash
python3 -m pip install -r requirements.txt
```

### 19.3 AI filling reports SSL EOF or curl SSL errors

Try:

- Reduce concurrency to `1` or `2`.
- Click again. The script will continue filling rows that are still blank.
- Switch models, for example `glm-5.1-internal` or `minimax-m2.5-external`.

### 19.4 Rednote/Xiaohongshu keyword search cannot find xsec_token

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

### 19.5 Douyin search cannot identify video cards

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

### 19.6 Excel cannot be saved

Possible reason:

- The target Excel workbook is open in WPS, Excel, or Numbers.

Fix:

- Close the workbook.
- Click the write button again.
- Use dry-run first, then write officially.

---

## 20. 安全注意事项 / Security Notes

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

## 21. 推荐日常流程 / Recommended Daily Workflow

中文：

1. 打开 Chrome，确认小红书和抖音登录状态正常。
2. 双击 `Pipeline/run_xhs_note_gui.command`。
3. 选择平台。
4. 先跑小数量关键词搜索，例如 10 条。
5. 检查当前平台监控总表是否追加正常。
6. 点击“AI填写总表”补齐分析字段。
7. 在“口碑加热候选”选择日期范围。
8. 先勾选 dry-run 预览。
9. 确认候选合理后取消 dry-run，写入对应平台 Excel。
10. 如需进一步人工判断，打开 `Hype_Something/start_tool.command` 或点击 GUI 中“打开Hype软件界面”。

English:

1. Open Chrome and confirm login status for Rednote/Xiaohongshu and Douyin.
2. Double-click `Pipeline/run_xhs_note_gui.command`.
3. Select a platform.
4. Start with a small keyword search, for example 10 rows.
5. Check that the current platform monitoring table is appended correctly.
6. Click `AI填写总表` to fill analysis fields.
7. Select a date range in the amplification section.
8. Enable dry-run for preview.
9. If the candidates look reasonable, disable dry-run and write to the platform workbook.
10. For further manual judgment, open `Hype_Something/start_tool.command` or click `打开Hype软件界面` in the GUI.

---

## 22. 维护说明 / Maintenance Notes

中文：

- 小红书和抖音网页结构可能变化。如果搜索页突然抓不到内容，优先检查页面是否需要登录或验证。
- 平台接口字段可能变化。如果监控总表出现空字段，检查对应的 `xhs_*` 或 `dy_*` 归一化脚本。
- 加热 Excel 表头如果被人工改动，导出脚本可能需要同步更新表头别名。
- 抖音和小红书链路是独立的。修改新平台逻辑时，不要直接改旧平台脚本，优先改对应 `dy_*` 或 `xhs_*` 文件。

English:

- Rednote/Xiaohongshu and Douyin web structures may change. If search suddenly fails, first check whether login or verification is required.
- Platform API fields may change. If normalized monitoring fields become blank, inspect the corresponding `xhs_*` or `dy_*` normalization script.
- If workbook headers are manually changed, the export script may need updated header aliases.
- Douyin and Rednote/Xiaohongshu flows are independent. When changing one platform, avoid modifying the other platform scripts unless necessary.
