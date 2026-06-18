# xhs_note 数据字典解析
## 文件概况
- 文件：`xhs_note_6a1c5940000000003501f7d5.csv`
- 数据行数：1
- 字段数：201
- 空字段数：4；空字段：`cursor_score`, `items.0.note_card.image_list.0.file_id`, `items.0.note_card.image_list.0.url`, `items.0.note_card.image_list.0.trace_id`
- 结构判断：这是小红书笔记详情/分享结果的扁平化 JSON；`items.0` 表示 items 数组第 0 个笔记。
- 时间戳说明：CSV 中部分时间被写成科学计数法；`raw_json` 中保留更精确的毫秒时间戳。

## 字段组统计
- 视频转码流 media.stream：114 个字段
- 话题标签 tag_list：30 个字段
- 视频基础元数据 video：14 个字段
- 封面/图片信息 image_list：13 个字段
- 笔记核心字段 note_card：10 个字段
- 互动信息 interact_info：8 个字段
- 根级/采集控制字段：6 个字段
- 作者信息 user：4 个字段
- 列表项字段 item：2 个字段

## 样本笔记概要
- 标题：判断选题能不能爆｜我每天在用的选题skill
- 作者：鲤哥builder；user_id：621120b200000000100083d8
- 类型：video；note_id：6a1c5940000000003501f7d5
- 互动：点赞 575，收藏 707，评论 45，分享 238
- 发布时间：2026-05-31 23:52:33（北京时间，raw_json 精确值）
- 最后更新时间：2026-06-02 10:32:45（北京时间，raw_json 精确值）
- 采集时间：2026-06-16 16:07:03（北京时间，raw_json 精确值）
- 话题：Skill, REDSkill, ai, 人工智能, 一人公司, 自媒体创业, 自媒体运营, 选题, claude, 创作者运营

## 全量字段明细
| 序号 | 字段名 | 字段组 | 推断类型 | 是否为空 | 字段说明 | 样例值 |
|---:|---|---|---|---|---|---|
| 1 | `source_url` | 根级/采集控制字段 | url | 否 | 采集来源 URL，包含小红书笔记链接、分享来源和 xsec_token 参数。 | `https://www.xiaohongshu.com/discovery/item/6a1c5940000000003501f7d5?source=webshare&xhsshare=pc_web&xsec_token=ABWi04RRGvlaXI32GR3kwreWf8...` |
| 2 | `note_id` | 根级/采集控制字段 | string | 否 | 根级笔记 ID。 | `6a1c5940000000003501f7d5` |
| 3 | `xsec_source` | 根级/采集控制字段 | string | 否 | 来源场景，示例 pc_share 表示 PC 分享入口。 | `pc_share` |
| 4 | `cursor_score` | 根级/采集控制字段 | empty | 是 | 分页/游标分数字段；本文件为空。 | `` |
| 5 | `items.0.note_card.interact_info.liked_count` | 互动信息 interact_info | integer | 否 | 点赞数。 | `575` |
| 6 | `items.0.note_card.interact_info.collected` | 互动信息 interact_info | boolean | 否 | 当前采集账号是否已收藏。 | `FALSE` |
| 7 | `items.0.note_card.interact_info.collected_count` | 互动信息 interact_info | integer | 否 | 收藏数。 | `707` |
| 8 | `items.0.note_card.interact_info.comment_count` | 互动信息 interact_info | integer | 否 | 评论数。 | `45` |
| 9 | `items.0.note_card.interact_info.share_count` | 互动信息 interact_info | integer | 否 | 分享数。 | `238` |
| 10 | `items.0.note_card.interact_info.followed` | 互动信息 interact_info | boolean | 否 | 当前采集账号是否已关注作者。 | `FALSE` |
| 11 | `items.0.note_card.interact_info.relation` | 互动信息 interact_info | string | 否 | 当前采集账号与作者的关系状态。 | `none` |
| 12 | `items.0.note_card.interact_info.liked` | 互动信息 interact_info | boolean | 否 | 当前采集账号是否已点赞。 | `FALSE` |
| 13 | `items.0.note_card.time` | 笔记核心字段 note_card | number | 否 | 笔记发布时间戳，单位毫秒。 | `1.78024E+12` |
| 14 | `items.0.note_card.video.media.video.md5` | 视频基础元数据 video | string | 否 | 视频文件 MD5。 | `63fa7092c3eba348156128a68938df01` |
| 15 | `items.0.note_card.video.media.video.hdr_type` | 视频基础元数据 video | integer | 否 | HDR 类型标识。 | `0` |
| 16 | `items.0.note_card.video.media.video.drm_type` | 视频基础元数据 video | integer | 否 | DRM 类型标识。 | `0` |
| 17 | `items.0.note_card.video.media.video.stream_types.0` | 视频基础元数据 video | integer | 否 | 可用视频流类型编号数组中的一个元素。 | `309` |
| 18 | `items.0.note_card.video.media.video.stream_types.1` | 视频基础元数据 video | integer | 否 | 可用视频流类型编号数组中的一个元素。 | `259` |
| 19 | `items.0.note_card.video.media.video.stream_types.2` | 视频基础元数据 video | integer | 否 | 可用视频流类型编号数组中的一个元素。 | `108` |
| 20 | `items.0.note_card.video.media.video.stream_types.3` | 视频基础元数据 video | integer | 否 | 可用视频流类型编号数组中的一个元素。 | `115` |
| 21 | `items.0.note_card.video.media.video.biz_name` | 视频基础元数据 video | integer | 否 | 业务线/业务名称编号。 | `110` |
| 22 | `items.0.note_card.video.media.video.biz_id` | 视频基础元数据 video | integer | 否 | 业务 ID。 | `282069096329508821` |
| 23 | `items.0.note_card.video.media.video.duration` | 视频基础元数据 video | integer | 否 | 视频时长，通常单位秒。 | `147` |
| 24 | `items.0.note_card.video.media.stream.h266` | 视频转码流 media.stream | json-string | 否 | H.266/VVC 视频流数组；本样本为空数组。 | `[]` |
| 25 | `items.0.note_card.video.media.stream.av1` | 视频转码流 media.stream | json-string | 否 | AV1 视频流数组；本样本为空数组。 | `[]` |
| 26 | `items.0.note_card.video.media.stream.h264.0.default_stream` | 视频转码流 media.stream | integer | 否 | h264 第 0 路视频流的是否默认播放流，0/1。 | `0` |
| 27 | `items.0.note_card.video.media.stream.h264.0.width` | 视频转码流 media.stream | integer | 否 | h264 第 0 路视频流的视频宽度，像素。 | `720` |
| 28 | `items.0.note_card.video.media.stream.h264.0.volume` | 视频转码流 media.stream | integer | 否 | h264 第 0 路视频流的音量标识/归一化字段。 | `0` |
| 29 | `items.0.note_card.video.media.stream.h264.0.ssim` | 视频转码流 media.stream | integer | 否 | h264 第 0 路视频流的SSIM 质量指标。 | `0` |
| 30 | `items.0.note_card.video.media.stream.h264.0.quality_type` | 视频转码流 media.stream | string | 否 | h264 第 0 路视频流的清晰度等级，如 HD。 | `HD` |
| 31 | `items.0.note_card.video.media.stream.h264.0.size` | 视频转码流 media.stream | integer | 否 | h264 第 0 路视频流的文件大小，字节。 | `13661708` |
| 32 | `items.0.note_card.video.media.stream.h264.0.audio_duration` | 视频转码流 media.stream | integer | 否 | h264 第 0 路视频流的音频时长，毫秒。 | `146866` |
| 33 | `items.0.note_card.video.media.stream.h264.0.master_url` | 视频转码流 media.stream | url | 否 | h264 第 0 路视频流的主播放地址，通常带临时签名参数。 | `http://sns-video-v2.xhscdn.com/stream/1/110/259/01ea1c59407132a0010370039e7ebd8f2a_259.mp4?sign=1af2d4b6c58131a978a899b1011f1673&t=6a35a167` |
| 34 | `items.0.note_card.video.media.stream.h264.0.psnr` | 视频转码流 media.stream | integer | 否 | h264 第 0 路视频流的PSNR 质量指标。 | `0` |
| 35 | `items.0.note_card.video.media.stream.h264.0.weight` | 视频转码流 media.stream | integer | 否 | h264 第 0 路视频流的流权重或选择优先级。 | `62` |
| 36 | `items.0.note_card.video.media.stream.h264.0.fps` | 视频转码流 media.stream | integer | 否 | h264 第 0 路视频流的帧率。 | `30` |
| 37 | `items.0.note_card.video.media.stream.h264.0.video_codec` | 视频转码流 media.stream | string | 否 | h264 第 0 路视频流的视频编码格式。 | `h264` |
| 38 | `items.0.note_card.video.media.stream.h264.0.audio_channels` | 视频转码流 media.stream | integer | 否 | h264 第 0 路视频流的音频声道数。 | `2` |
| 39 | `items.0.note_card.video.media.stream.h264.0.height` | 视频转码流 media.stream | integer | 否 | h264 第 0 路视频流的视频高度，像素。 | `1280` |
| 40 | `items.0.note_card.video.media.stream.h264.0.duration` | 视频转码流 media.stream | integer | 否 | h264 第 0 路视频流的媒体流总时长，毫秒。 | `146867` |
| 41 | `items.0.note_card.video.media.stream.h264.0.avg_bitrate` | 视频转码流 media.stream | integer | 否 | h264 第 0 路视频流的平均码率，bps。 | `744167` |
| 42 | `items.0.note_card.video.media.stream.h264.0.audio_codec` | 视频转码流 media.stream | string | 否 | h264 第 0 路视频流的音频编码格式。 | `aac` |
| 43 | `items.0.note_card.video.media.stream.h264.0.hdr_type` | 视频转码流 media.stream | integer | 否 | h264 第 0 路视频流的HDR 类型标识。 | `0` |
| 44 | `items.0.note_card.video.media.stream.h264.0.vmaf` | 视频转码流 media.stream | integer | 否 | h264 第 0 路视频流的VMAF 质量指标；-1 常见于未计算。 | `-1` |
| 45 | `items.0.note_card.video.media.stream.h264.0.stream_desc` | 视频转码流 media.stream | string | 否 | h264 第 0 路视频流的流描述/转码模板名称。 | `WM_X264_MP4_web` |
| 46 | `items.0.note_card.video.media.stream.h264.0.format` | 视频转码流 media.stream | string | 否 | h264 第 0 路视频流的封装格式。 | `mp4` |
| 47 | `items.0.note_card.video.media.stream.h264.0.video_duration` | 视频转码流 media.stream | integer | 否 | h264 第 0 路视频流的视频轨时长，毫秒。 | `146800` |
| 48 | `items.0.note_card.video.media.stream.h264.0.rotate` | 视频转码流 media.stream | integer | 否 | h264 第 0 路视频流的旋转角度。 | `0` |
| 49 | `items.0.note_card.video.media.stream.h264.0.stream_type` | 视频转码流 media.stream | integer | 否 | h264 第 0 路视频流的流类型编号。 | `259` |
| 50 | `items.0.note_card.video.media.stream.h264.0.video_bitrate` | 视频转码流 media.stream | integer | 否 | h264 第 0 路视频流的视频码率，bps。 | `673851` |
| 51 | `items.0.note_card.video.media.stream.h264.0.backup_urls.0` | 视频转码流 media.stream | url | 否 | h264 第 0 路视频流的备用播放地址。 | `http://sns-bak-v1.xhscdn.com/stream/1/110/259/01ea1c59407132a0010370039e7ebd8f2a_259.mp4` |
| 52 | `items.0.note_card.video.media.stream.h264.0.backup_urls.1` | 视频转码流 media.stream | url | 否 | h264 第 0 路视频流的备用播放地址。 | `http://sns-bak-v6.xhscdn.com/stream/1/110/259/01ea1c59407132a0010370039e7ebd8f2a_259.mp4` |
| 53 | `items.0.note_card.video.media.stream.h264.0.audio_bitrate` | 视频转码流 media.stream | integer | 否 | h264 第 0 路视频流的音频码率，bps。 | `64056` |
| 54 | `items.0.note_card.video.media.stream.h265.0.volume` | 视频转码流 media.stream | integer | 否 | h265 第 0 路视频流的音量标识/归一化字段。 | `0` |
| 55 | `items.0.note_card.video.media.stream.h265.0.audio_codec` | 视频转码流 media.stream | string | 否 | h265 第 0 路视频流的音频编码格式。 | `aac` |
| 56 | `items.0.note_card.video.media.stream.h265.0.audio_duration` | 视频转码流 media.stream | integer | 否 | h265 第 0 路视频流的音频时长，毫秒。 | `146866` |
| 57 | `items.0.note_card.video.media.stream.h265.0.weight` | 视频转码流 media.stream | integer | 否 | h265 第 0 路视频流的流权重或选择优先级。 | `62` |
| 58 | `items.0.note_card.video.media.stream.h265.0.duration` | 视频转码流 media.stream | integer | 否 | h265 第 0 路视频流的媒体流总时长，毫秒。 | `146867` |
| 59 | `items.0.note_card.video.media.stream.h265.0.rotate` | 视频转码流 media.stream | integer | 否 | h265 第 0 路视频流的旋转角度。 | `0` |
| 60 | `items.0.note_card.video.media.stream.h265.0.backup_urls.0` | 视频转码流 media.stream | url | 否 | h265 第 0 路视频流的备用播放地址。 | `http://sns-bak-v1.xhscdn.com/stream/1/110/309/01ea1c59407132a0010370019e7ebf8e2c_309.mp4` |
| 61 | `items.0.note_card.video.media.stream.h265.0.backup_urls.1` | 视频转码流 media.stream | url | 否 | h265 第 0 路视频流的备用播放地址。 | `http://sns-bak-v6.xhscdn.com/stream/1/110/309/01ea1c59407132a0010370019e7ebf8e2c_309.mp4` |
| 62 | `items.0.note_card.video.media.stream.h265.0.height` | 视频转码流 media.stream | integer | 否 | h265 第 0 路视频流的视频高度，像素。 | `1280` |
| 63 | `items.0.note_card.video.media.stream.h265.0.width` | 视频转码流 media.stream | integer | 否 | h265 第 0 路视频流的视频宽度，像素。 | `720` |
| 64 | `items.0.note_card.video.media.stream.h265.0.avg_bitrate` | 视频转码流 media.stream | integer | 否 | h265 第 0 路视频流的平均码率，bps。 | `885475` |
| 65 | `items.0.note_card.video.media.stream.h265.0.fps` | 视频转码流 media.stream | integer | 否 | h265 第 0 路视频流的帧率。 | `30` |
| 66 | `items.0.note_card.video.media.stream.h265.0.video_codec` | 视频转码流 media.stream | string | 否 | h265 第 0 路视频流的视频编码格式。 | `hevc` |
| 67 | `items.0.note_card.video.media.stream.h265.0.video_duration` | 视频转码流 media.stream | integer | 否 | h265 第 0 路视频流的视频轨时长，毫秒。 | `146800` |
| 68 | `items.0.note_card.video.media.stream.h265.0.format` | 视频转码流 media.stream | string | 否 | h265 第 0 路视频流的封装格式。 | `mp4` |
| 69 | `items.0.note_card.video.media.stream.h265.0.video_bitrate` | 视频转码流 media.stream | integer | 否 | h265 第 0 路视频流的视频码率，bps。 | `783167` |
| 70 | `items.0.note_card.video.media.stream.h265.0.audio_bitrate` | 视频转码流 media.stream | integer | 否 | h265 第 0 路视频流的音频码率，bps。 | `96015` |
| 71 | `items.0.note_card.video.media.stream.h265.0.master_url` | 视频转码流 media.stream | url | 否 | h265 第 0 路视频流的主播放地址，通常带临时签名参数。 | `http://sns-video-v2.xhscdn.com/stream/1/110/309/01ea1c59407132a0010370019e7ebf8e2c_309.mp4?sign=c4cf24b1916cb5b45c7ef50d92b275de&t=6a35a167` |
| 72 | `items.0.note_card.video.media.stream.h265.0.ssim` | 视频转码流 media.stream | integer | 否 | h265 第 0 路视频流的SSIM 质量指标。 | `0` |
| 73 | `items.0.note_card.video.media.stream.h265.0.quality_type` | 视频转码流 media.stream | string | 否 | h265 第 0 路视频流的清晰度等级，如 HD。 | `HD` |
| 74 | `items.0.note_card.video.media.stream.h265.0.psnr` | 视频转码流 media.stream | number | 否 | h265 第 0 路视频流的PSNR 质量指标。 | `43.012001037597656` |
| 75 | `items.0.note_card.video.media.stream.h265.0.stream_type` | 视频转码流 media.stream | integer | 否 | h265 第 0 路视频流的流类型编号。 | `309` |
| 76 | `items.0.note_card.video.media.stream.h265.0.audio_channels` | 视频转码流 media.stream | integer | 否 | h265 第 0 路视频流的音频声道数。 | `2` |
| 77 | `items.0.note_card.video.media.stream.h265.0.hdr_type` | 视频转码流 media.stream | integer | 否 | h265 第 0 路视频流的HDR 类型标识。 | `0` |
| 78 | `items.0.note_card.video.media.stream.h265.0.stream_desc` | 视频转码流 media.stream | string | 否 | h265 第 0 路视频流的流描述/转码模板名称。 | `X265_MP4_WEB_309` |
| 79 | `items.0.note_card.video.media.stream.h265.0.default_stream` | 视频转码流 media.stream | integer | 否 | h265 第 0 路视频流的是否默认播放流，0/1。 | `0` |
| 80 | `items.0.note_card.video.media.stream.h265.0.size` | 视频转码流 media.stream | integer | 否 | h265 第 0 路视频流的文件大小，字节。 | `16255899` |
| 81 | `items.0.note_card.video.media.stream.h265.0.vmaf` | 视频转码流 media.stream | integer | 否 | h265 第 0 路视频流的VMAF 质量指标；-1 常见于未计算。 | `-1` |
| 82 | `items.0.note_card.video.media.stream.h265.1.video_codec` | 视频转码流 media.stream | string | 否 | h265 第 1 路视频流的视频编码格式。 | `hevc` |
| 83 | `items.0.note_card.video.media.stream.h265.1.audio_channels` | 视频转码流 media.stream | integer | 否 | h265 第 1 路视频流的音频声道数。 | `2` |
| 84 | `items.0.note_card.video.media.stream.h265.1.ssim` | 视频转码流 media.stream | integer | 否 | h265 第 1 路视频流的SSIM 质量指标。 | `0` |
| 85 | `items.0.note_card.video.media.stream.h265.1.avg_bitrate` | 视频转码流 media.stream | integer | 否 | h265 第 1 路视频流的平均码率，bps。 | `2189734` |
| 86 | `items.0.note_card.video.media.stream.h265.1.fps` | 视频转码流 media.stream | integer | 否 | h265 第 1 路视频流的帧率。 | `30` |
| 87 | `items.0.note_card.video.media.stream.h265.1.height` | 视频转码流 media.stream | integer | 否 | h265 第 1 路视频流的视频高度，像素。 | `2560` |
| 88 | `items.0.note_card.video.media.stream.h265.1.stream_desc` | 视频转码流 media.stream | string | 否 | h265 第 1 路视频流的流描述/转码模板名称。 | `X265_MP4_WEB_108` |
| 89 | `items.0.note_card.video.media.stream.h265.1.video_bitrate` | 视频转码流 media.stream | integer | 否 | h265 第 1 路视频流的视频码率，bps。 | `2056344` |
| 90 | `items.0.note_card.video.media.stream.h265.1.backup_urls.0` | 视频转码流 media.stream | url | 否 | h265 第 1 路视频流的备用播放地址。 | `http://sns-bak-v1.xhscdn.com/stream/1/110/108/01ea1c59407132a0010370019e828e54c7_108.mp4` |
| 91 | `items.0.note_card.video.media.stream.h265.1.backup_urls.1` | 视频转码流 media.stream | url | 否 | h265 第 1 路视频流的备用播放地址。 | `http://sns-bak-v6.xhscdn.com/stream/1/110/108/01ea1c59407132a0010370019e828e54c7_108.mp4` |
| 92 | `items.0.note_card.video.media.stream.h265.1.master_url` | 视频转码流 media.stream | url | 否 | h265 第 1 路视频流的主播放地址，通常带临时签名参数。 | `http://sns-video-v2.xhscdn.com/stream/1/110/108/01ea1c59407132a0010370019e828e54c7_108.mp4?sign=c4e2ce74bf154dbc537430a7ab8c00bf&t=6a35a167` |
| 93 | `items.0.note_card.video.media.stream.h265.1.weight` | 视频转码流 media.stream | integer | 否 | h265 第 1 路视频流的流权重或选择优先级。 | `70` |
| 94 | `items.0.note_card.video.media.stream.h265.1.stream_type` | 视频转码流 media.stream | integer | 否 | h265 第 1 路视频流的流类型编号。 | `108` |
| 95 | `items.0.note_card.video.media.stream.h265.1.default_stream` | 视频转码流 media.stream | integer | 否 | h265 第 1 路视频流的是否默认播放流，0/1。 | `0` |
| 96 | `items.0.note_card.video.media.stream.h265.1.video_duration` | 视频转码流 media.stream | integer | 否 | h265 第 1 路视频流的视频轨时长，毫秒。 | `146800` |
| 97 | `items.0.note_card.video.media.stream.h265.1.audio_bitrate` | 视频转码流 media.stream | integer | 否 | h265 第 1 路视频流的音频码率，bps。 | `128000` |
| 98 | `items.0.note_card.video.media.stream.h265.1.rotate` | 视频转码流 media.stream | integer | 否 | h265 第 1 路视频流的旋转角度。 | `0` |
| 99 | `items.0.note_card.video.media.stream.h265.1.hdr_type` | 视频转码流 media.stream | integer | 否 | h265 第 1 路视频流的HDR 类型标识。 | `0` |
| 100 | `items.0.note_card.video.media.stream.h265.1.psnr` | 视频转码流 media.stream | number | 否 | h265 第 1 路视频流的PSNR 质量指标。 | `45.57899856567383` |
| 101 | `items.0.note_card.video.media.stream.h265.1.format` | 视频转码流 media.stream | string | 否 | h265 第 1 路视频流的封装格式。 | `mp4` |
| 102 | `items.0.note_card.video.media.stream.h265.1.duration` | 视频转码流 media.stream | integer | 否 | h265 第 1 路视频流的媒体流总时长，毫秒。 | `146890` |
| 103 | `items.0.note_card.video.media.stream.h265.1.width` | 视频转码流 media.stream | integer | 否 | h265 第 1 路视频流的视频宽度，像素。 | `1440` |
| 104 | `items.0.note_card.video.media.stream.h265.1.quality_type` | 视频转码流 media.stream | string | 否 | h265 第 1 路视频流的清晰度等级，如 HD。 | `HD` |
| 105 | `items.0.note_card.video.media.stream.h265.1.audio_codec` | 视频转码流 media.stream | string | 否 | h265 第 1 路视频流的音频编码格式。 | `aac` |
| 106 | `items.0.note_card.video.media.stream.h265.1.audio_duration` | 视频转码流 media.stream | integer | 否 | h265 第 1 路视频流的音频时长，毫秒。 | `146889` |
| 107 | `items.0.note_card.video.media.stream.h265.1.vmaf` | 视频转码流 media.stream | integer | 否 | h265 第 1 路视频流的VMAF 质量指标；-1 常见于未计算。 | `-1` |
| 108 | `items.0.note_card.video.media.stream.h265.1.size` | 视频转码流 media.stream | integer | 否 | h265 第 1 路视频流的文件大小，字节。 | `40206257` |
| 109 | `items.0.note_card.video.media.stream.h265.1.volume` | 视频转码流 media.stream | integer | 否 | h265 第 1 路视频流的音量标识/归一化字段。 | `0` |
| 110 | `items.0.note_card.video.media.stream.h265.2.video_codec` | 视频转码流 media.stream | string | 否 | h265 第 2 路视频流的视频编码格式。 | `hevc` |
| 111 | `items.0.note_card.video.media.stream.h265.2.master_url` | 视频转码流 media.stream | url | 否 | h265 第 2 路视频流的主播放地址，通常带临时签名参数。 | `http://sns-video-v2.xhscdn.com/stream/1/110/115/01ea1c59407132a0010370019e7ec17b40_115.mp4?sign=bda396735b4dc5606ee7fcbfbda0eb5d&t=6a35a167` |
| 112 | `items.0.note_card.video.media.stream.h265.2.backup_urls.0` | 视频转码流 media.stream | url | 否 | h265 第 2 路视频流的备用播放地址。 | `http://sns-bak-v1.xhscdn.com/stream/1/110/115/01ea1c59407132a0010370019e7ec17b40_115.mp4` |
| 113 | `items.0.note_card.video.media.stream.h265.2.backup_urls.1` | 视频转码流 media.stream | url | 否 | h265 第 2 路视频流的备用播放地址。 | `http://sns-bak-v6.xhscdn.com/stream/1/110/115/01ea1c59407132a0010370019e7ec17b40_115.mp4` |
| 114 | `items.0.note_card.video.media.stream.h265.2.width` | 视频转码流 media.stream | integer | 否 | h265 第 2 路视频流的视频宽度，像素。 | `1080` |
| 115 | `items.0.note_card.video.media.stream.h265.2.fps` | 视频转码流 media.stream | integer | 否 | h265 第 2 路视频流的帧率。 | `30` |
| 116 | `items.0.note_card.video.media.stream.h265.2.rotate` | 视频转码流 media.stream | integer | 否 | h265 第 2 路视频流的旋转角度。 | `0` |
| 117 | `items.0.note_card.video.media.stream.h265.2.format` | 视频转码流 media.stream | string | 否 | h265 第 2 路视频流的封装格式。 | `mp4` |
| 118 | `items.0.note_card.video.media.stream.h265.2.audio_bitrate` | 视频转码流 media.stream | integer | 否 | h265 第 2 路视频流的音频码率，bps。 | `96015` |
| 119 | `items.0.note_card.video.media.stream.h265.2.stream_desc` | 视频转码流 media.stream | string | 否 | h265 第 2 路视频流的流描述/转码模板名称。 | `X265_MP4_WEB_115` |
| 120 | `items.0.note_card.video.media.stream.h265.2.psnr` | 视频转码流 media.stream | number | 否 | h265 第 2 路视频流的PSNR 质量指标。 | `42.98899841308594` |
| 121 | `items.0.note_card.video.media.stream.h265.2.weight` | 视频转码流 media.stream | integer | 否 | h265 第 2 路视频流的流权重或选择优先级。 | `70` |
| 122 | `items.0.note_card.video.media.stream.h265.2.default_stream` | 视频转码流 media.stream | integer | 否 | h265 第 2 路视频流的是否默认播放流，0/1。 | `0` |
| 123 | `items.0.note_card.video.media.stream.h265.2.hdr_type` | 视频转码流 media.stream | integer | 否 | h265 第 2 路视频流的HDR 类型标识。 | `0` |
| 124 | `items.0.note_card.video.media.stream.h265.2.ssim` | 视频转码流 media.stream | integer | 否 | h265 第 2 路视频流的SSIM 质量指标。 | `0` |
| 125 | `items.0.note_card.video.media.stream.h265.2.height` | 视频转码流 media.stream | integer | 否 | h265 第 2 路视频流的视频高度，像素。 | `1920` |
| 126 | `items.0.note_card.video.media.stream.h265.2.size` | 视频转码流 media.stream | integer | 否 | h265 第 2 路视频流的文件大小，字节。 | `21318913` |
| 127 | `items.0.note_card.video.media.stream.h265.2.audio_duration` | 视频转码流 media.stream | integer | 否 | h265 第 2 路视频流的音频时长，毫秒。 | `146866` |
| 128 | `items.0.note_card.video.media.stream.h265.2.audio_channels` | 视频转码流 media.stream | integer | 否 | h265 第 2 路视频流的音频声道数。 | `2` |
| 129 | `items.0.note_card.video.media.stream.h265.2.avg_bitrate` | 视频转码流 media.stream | integer | 否 | h265 第 2 路视频流的平均码率，bps。 | `1161263` |
| 130 | `items.0.note_card.video.media.stream.h265.2.audio_codec` | 视频转码流 media.stream | string | 否 | h265 第 2 路视频流的音频编码格式。 | `aac` |
| 131 | `items.0.note_card.video.media.stream.h265.2.duration` | 视频转码流 media.stream | integer | 否 | h265 第 2 路视频流的媒体流总时长，毫秒。 | `146867` |
| 132 | `items.0.note_card.video.media.stream.h265.2.video_bitrate` | 视频转码流 media.stream | integer | 否 | h265 第 2 路视频流的视频码率，bps。 | `1059080` |
| 133 | `items.0.note_card.video.media.stream.h265.2.video_duration` | 视频转码流 media.stream | integer | 否 | h265 第 2 路视频流的视频轨时长，毫秒。 | `146800` |
| 134 | `items.0.note_card.video.media.stream.h265.2.quality_type` | 视频转码流 media.stream | string | 否 | h265 第 2 路视频流的清晰度等级，如 HD。 | `HD` |
| 135 | `items.0.note_card.video.media.stream.h265.2.stream_type` | 视频转码流 media.stream | integer | 否 | h265 第 2 路视频流的流类型编号。 | `115` |
| 136 | `items.0.note_card.video.media.stream.h265.2.volume` | 视频转码流 media.stream | integer | 否 | h265 第 2 路视频流的音量标识/归一化字段。 | `0` |
| 137 | `items.0.note_card.video.media.stream.h265.2.vmaf` | 视频转码流 media.stream | integer | 否 | h265 第 2 路视频流的VMAF 质量指标；-1 常见于未计算。 | `-1` |
| 138 | `items.0.note_card.video.media.video_id` | 笔记核心字段 note_card | integer | 否 | 视频 ID。 | `137953908247048864` |
| 139 | `items.0.note_card.video.image.first_frame_fileid` | 视频基础元数据 video | string | 否 | 视频第一帧图片文件 ID。 | `110/0/01ea1c59407132a00010000000019e7ebcad47_0.jpg` |
| 140 | `items.0.note_card.video.image.thumbnail_fileid` | 视频基础元数据 video | string | 否 | 视频缩略图文件 ID。 | `frame/110/0/01ea1c59407132a00010000000019e7ebd1974_0.webp` |
| 141 | `items.0.note_card.video.capa.duration` | 视频基础元数据 video | integer | 否 | 视频能力/播放层记录的时长，通常单位秒。 | `146` |
| 142 | `items.0.note_card.video.media_v2` | 视频基础元数据 video | json-string | 否 | 新版本视频媒体 JSON 字符串，内容与 video/media/stream 高度重叠。 | `{"video_id":"137953908247048864","video":{"biz_name":110,"biz_id":"282069096329508821","duration":147,"md5":"63fa7092c3eba348156128a68938...` |
| 143 | `items.0.note_card.at_user_list` | 笔记核心字段 note_card | json-string | 否 | 正文 @ 用户列表，JSON 数组字符串。 | `[]` |
| 144 | `items.0.note_card.last_update_time` | 笔记核心字段 note_card | number | 否 | 笔记最后更新时间戳，单位毫秒。 | `1.78037E+12` |
| 145 | `items.0.note_card.ip_location` | 笔记核心字段 note_card | string | 否 | 发布/显示 IP 属地。 | `广东` |
| 146 | `items.0.note_card.share_info.un_share` | 笔记核心字段 note_card | boolean | 否 | 是否不可分享；FALSE 表示未禁分享。 | `FALSE` |
| 147 | `items.0.note_card.note_id` | 笔记核心字段 note_card | string | 否 | note_card 内部笔记 ID。 | `6a1c5940000000003501f7d5` |
| 148 | `items.0.note_card.type` | 笔记核心字段 note_card | string | 否 | 笔记类型；本样本为 video。 | `video` |
| 149 | `items.0.note_card.desc` | 笔记核心字段 note_card | string | 否 | 笔记正文/描述。 | `#Skill[话题]# #REDSkill[话题]# #ai[话题]# #人工智能[话题]# #一人公司[话题]# #自媒体创业[话题]# #自媒体运营[话题]# #选题[话题]# #claude[话题]#  #创作者运营[话题]#` |
| 150 | `items.0.note_card.title` | 笔记核心字段 note_card | string | 否 | 笔记标题。 | `判断选题能不能爆｜我每天在用的选题skill` |
| 151 | `items.0.note_card.user.nickname` | 作者信息 user | string | 否 | 作者昵称。 | `鲤哥builder` |
| 152 | `items.0.note_card.user.avatar` | 作者信息 user | url | 否 | 作者头像 URL。 | `https://sns-avatar-qc.xhscdn.com/avatar/1040g2jo31elfmqfa500g5ogh42p410uof62mec0` |
| 153 | `items.0.note_card.user.xsec_token` | 作者信息 user | string | 否 | 作者安全访问 token。 | `ABucIZd2...uT1NM=` |
| 154 | `items.0.note_card.user.user_id` | 作者信息 user | string | 否 | 作者用户 ID。 | `621120b200000000100083d8` |
| 155 | `items.0.note_card.image_list.0.file_id` | 封面/图片信息 image_list | empty | 是 | 图片文件 ID；本样本为空。 | `` |
| 156 | `items.0.note_card.image_list.0.width` | 封面/图片信息 image_list | integer | 否 | 图片宽度，像素。 | `1242` |
| 157 | `items.0.note_card.image_list.0.live_photo` | 封面/图片信息 image_list | boolean | 否 | 是否 Live Photo。 | `FALSE` |
| 158 | `items.0.note_card.image_list.0.url_default` | 封面/图片信息 image_list | url | 否 | 默认封面图 URL。 | `http://sns-webpic-qc.xhscdn.com/202606161607/6a6222c34b29a6ed15963ae3e16b037b/1040g2sg320t7i0acn0705ogh42p410uol2tqq48!nd_dft_wlteh_webp_3` |
| 159 | `items.0.note_card.image_list.0.stream` | 封面/图片信息 image_list | json-string | 否 | 图片流信息 JSON 对象字符串。 | `{}` |
| 160 | `items.0.note_card.image_list.0.height` | 封面/图片信息 image_list | integer | 否 | 图片高度，像素。 | `1656` |
| 161 | `items.0.note_card.image_list.0.url` | 封面/图片信息 image_list | empty | 是 | 图片 URL；本样本为空。 | `` |
| 162 | `items.0.note_card.image_list.0.trace_id` | 封面/图片信息 image_list | empty | 是 | 图片追踪 ID；本样本为空。 | `` |
| 163 | `items.0.note_card.image_list.0.info_list.0.image_scene` | 封面/图片信息 image_list | string | 否 | 封面图片不同场景版本的场景名称。 | `WB_PRV` |
| 164 | `items.0.note_card.image_list.0.info_list.0.url` | 封面/图片信息 image_list | url | 否 | 封面图片某个场景版本的 URL。 | `http://sns-webpic-qc.xhscdn.com/202606161607/85ee8bf142c59e26bcb58ac45c72e8c1/1040g2sg320t7i0acn0705ogh42p410uol2tqq48!nd_prv_wlteh_webp_3` |
| 165 | `items.0.note_card.image_list.0.info_list.1.image_scene` | 封面/图片信息 image_list | string | 否 | 封面图片不同场景版本的场景名称。 | `WB_DFT` |
| 166 | `items.0.note_card.image_list.0.info_list.1.url` | 封面/图片信息 image_list | url | 否 | 封面图片某个场景版本的 URL。 | `http://sns-webpic-qc.xhscdn.com/202606161607/6a6222c34b29a6ed15963ae3e16b037b/1040g2sg320t7i0acn0705ogh42p410uol2tqq48!nd_dft_wlteh_webp_3` |
| 167 | `items.0.note_card.image_list.0.url_pre` | 封面/图片信息 image_list | url | 否 | 预览图 URL。 | `http://sns-webpic-qc.xhscdn.com/202606161607/85ee8bf142c59e26bcb58ac45c72e8c1/1040g2sg320t7i0acn0705ogh42p410uol2tqq48!nd_prv_wlteh_webp_3` |
| 168 | `items.0.note_card.tag_list.0.id` | 话题标签 tag_list | string | 否 | 第 0 个话题标签 ID。 | `5e16c4e70000000001004308` |
| 169 | `items.0.note_card.tag_list.0.name` | 话题标签 tag_list | string | 否 | 第 0 个话题标签名称。 | `Skill` |
| 170 | `items.0.note_card.tag_list.0.type` | 话题标签 tag_list | string | 否 | 第 0 个标签类型；本样本均为 topic。 | `topic` |
| 171 | `items.0.note_card.tag_list.1.id` | 话题标签 tag_list | string | 否 | 第 1 个话题标签 ID。 | `6a109c7200000000060117e3` |
| 172 | `items.0.note_card.tag_list.1.name` | 话题标签 tag_list | string | 否 | 第 1 个话题标签名称。 | `REDSkill` |
| 173 | `items.0.note_card.tag_list.1.type` | 话题标签 tag_list | string | 否 | 第 1 个标签类型；本样本均为 topic。 | `topic` |
| 174 | `items.0.note_card.tag_list.2.id` | 话题标签 tag_list | string | 否 | 第 2 个话题标签 ID。 | `5c1c3c9a000000000a030af3` |
| 175 | `items.0.note_card.tag_list.2.name` | 话题标签 tag_list | string | 否 | 第 2 个话题标签名称。 | `ai` |
| 176 | `items.0.note_card.tag_list.2.type` | 话题标签 tag_list | string | 否 | 第 2 个标签类型；本样本均为 topic。 | `topic` |
| 177 | `items.0.note_card.tag_list.3.id` | 话题标签 tag_list | string | 否 | 第 3 个话题标签 ID。 | `620cd421000000000100130c` |
| 178 | `items.0.note_card.tag_list.3.name` | 话题标签 tag_list | string | 否 | 第 3 个话题标签名称。 | `人工智能` |
| 179 | `items.0.note_card.tag_list.3.type` | 话题标签 tag_list | string | 否 | 第 3 个标签类型；本样本均为 topic。 | `topic` |
| 180 | `items.0.note_card.tag_list.4.id` | 话题标签 tag_list | string | 否 | 第 4 个话题标签 ID。 | `602cb0d0000000000100585b` |
| 181 | `items.0.note_card.tag_list.4.name` | 话题标签 tag_list | string | 否 | 第 4 个话题标签名称。 | `一人公司` |
| 182 | `items.0.note_card.tag_list.4.type` | 话题标签 tag_list | string | 否 | 第 4 个标签类型；本样本均为 topic。 | `topic` |
| 183 | `items.0.note_card.tag_list.5.id` | 话题标签 tag_list | string | 否 | 第 5 个话题标签 ID。 | `5c349f2800000000080005e2` |
| 184 | `items.0.note_card.tag_list.5.name` | 话题标签 tag_list | string | 否 | 第 5 个话题标签名称。 | `自媒体创业` |
| 185 | `items.0.note_card.tag_list.5.type` | 话题标签 tag_list | string | 否 | 第 5 个标签类型；本样本均为 topic。 | `topic` |
| 186 | `items.0.note_card.tag_list.6.name` | 话题标签 tag_list | string | 否 | 第 6 个话题标签名称。 | `自媒体运营` |
| 187 | `items.0.note_card.tag_list.6.type` | 话题标签 tag_list | string | 否 | 第 6 个标签类型；本样本均为 topic。 | `topic` |
| 188 | `items.0.note_card.tag_list.6.id` | 话题标签 tag_list | string | 否 | 第 6 个话题标签 ID。 | `5c7125aa000000000e00b660` |
| 189 | `items.0.note_card.tag_list.7.id` | 话题标签 tag_list | string | 否 | 第 7 个话题标签 ID。 | `5ed2f138000000000101d666` |
| 190 | `items.0.note_card.tag_list.7.name` | 话题标签 tag_list | string | 否 | 第 7 个话题标签名称。 | `选题` |
| 191 | `items.0.note_card.tag_list.7.type` | 话题标签 tag_list | string | 否 | 第 7 个标签类型；本样本均为 topic。 | `topic` |
| 192 | `items.0.note_card.tag_list.8.id` | 话题标签 tag_list | string | 否 | 第 8 个话题标签 ID。 | `6198f6380000000001002175` |
| 193 | `items.0.note_card.tag_list.8.name` | 话题标签 tag_list | string | 否 | 第 8 个话题标签名称。 | `claude` |
| 194 | `items.0.note_card.tag_list.8.type` | 话题标签 tag_list | string | 否 | 第 8 个标签类型；本样本均为 topic。 | `topic` |
| 195 | `items.0.note_card.tag_list.9.id` | 话题标签 tag_list | string | 否 | 第 9 个话题标签 ID。 | `60effc850000000001001b08` |
| 196 | `items.0.note_card.tag_list.9.name` | 话题标签 tag_list | string | 否 | 第 9 个话题标签名称。 | `创作者运营` |
| 197 | `items.0.note_card.tag_list.9.type` | 话题标签 tag_list | string | 否 | 第 9 个标签类型；本样本均为 topic。 | `topic` |
| 198 | `items.0.id` | 列表项字段 item | string | 否 | items 数组第 0 个对象的 ID，通常等于 note_id。 | `6a1c5940000000003501f7d5` |
| 199 | `items.0.model_type` | 列表项字段 item | string | 否 | 对象模型类型，示例 note。 | `note` |
| 200 | `current_time` | 根级/采集控制字段 | number | 否 | 采集当前时间戳，CSV 中为科学计数法，raw_json 内含更精确毫秒值。 | `1.7816E+12` |
| 201 | `raw_json` | 根级/采集控制字段 | json-string | 否 | 原始 JSON 响应字符串，包含本行扁平化前的完整结构。 | `{"cursor_score":"","items":[{"note_card":{"interact_info":{"liked_count":"575","collected":false,"collected_count":"707"...` |
