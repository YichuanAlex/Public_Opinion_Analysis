# 评论区全量重跑命令

以下命令会删除旧的逐帖评论区导出文件，并重新按两张监控总表全量爬取评论区。

```bash
cd /Users/didi/Downloads/Public_Opinion_Analysis

# 1. 修复监控总表核心字段，只使用已有 origin_data 离线补全
python3 check_and_repair_monitoring_tables.py

# 2. 删除旧评论区导出文件并全量重爬
python3 Pipeline/export_comment_sections.py \
  --platform all \
  --reset-output \
  --overwrite \
  --headed

# 3. 评论区导出完成后，再跑一次监控表字段补全
python3 check_and_repair_monitoring_tables.py
```

如果只重跑一个平台：

```bash
python3 Pipeline/export_comment_sections.py --platform xhs --reset-output --overwrite --headed
python3 Pipeline/export_comment_sections.py --platform dy --reset-output --overwrite --headed
```

默认行为：

- `--limit-comments 0`：每条帖子导出全部评论。
- `--max-posts-per-platform 0`：每个平台处理全部候选帖子。
- 已存在的帖子评论文件默认跳过；使用 `--reset-output --overwrite` 才会先删旧文件再重跑。
