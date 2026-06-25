# 舆情可视化大屏 / Public Opinion Dashboard

## 启动方式 / Run

```bash
cd /Users/didi/Downloads/Public_Opinion_Analysis
python3 Visualization/server.py --port 8765
```

然后打开：

```text
http://127.0.0.1:8765/
```

也可以双击：

```text
Visualization/run_visualization.command
```

## 数据来源 / Data Sources

- `Pipeline/xhs_Data_Table_on_Channel_Public_Opinion_Monitoring_2026.csv`
- `Pipeline/dy_Data_Table_on_Channel_Public_Opinion_Monitoring_2026.csv`
- `Comment_Data/xhs/*.xlsx`
- `Comment_Data/dy/*.xlsx`
- `Hype_Something/2026_Didi_Xiaohongshu_Daily_Word-of-Mouth_Amplification.xlsx`
- `Hype_Something/2026_Didi_Douyin_Daily_Word-of-Mouth_Amplification.xlsx`

## 本地检查 / Local Check

```bash
python3 Visualization/server.py --check
```

该命令只读取本地文件并输出数据摘要，不会访问小红书或抖音平台。

## 外部 PDF / External PDF

搜索趋势页会遍历：

```text
External_Data/**/*.pdf
```

并按 PDF 文本中的各级子标题自动生成展示模块。PDF 解析依赖以下任意一种即可：

```bash
python3 -m pip install pypdf
# 或
python3 -m pip install pdfplumber
```

如果当前 Python 没有 PDF 解析依赖，大屏不会崩溃，会在“外部统计”模块展示依赖提示。

## 评论区全量重跑 / Full Comment Refresh

全量重跑命令已写入：

```text
Pipeline/comment_export_full_run_commands.md
```
