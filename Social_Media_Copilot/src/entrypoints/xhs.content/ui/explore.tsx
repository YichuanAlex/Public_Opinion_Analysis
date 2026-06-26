import { CopyButton, CopyOption } from "@/components/copy/copy-button";
import { Logo } from "@/components/logo";
import { Button } from "@/components/ui/button";
import { defineSocialMediaCopilotUi } from "@/utils/ui";
import { throttle } from "lodash";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { webV1Feed } from "../api/note";
import { getPostMedias } from "../utils/media";

const Component = (props: {
  noteId: string;
  xsecToken: string;
}) => {
  const { noteId, xsecToken } = props;
  const [noteCard, setNoteCard] = useState<any>();
  const reportedKeyRef = useRef('');

  const clean = (value: any) => String(value || '').replace(/\s+/g, ' ').trim();

  const getDomNoteCard = () => {
    const text = clean(document.body?.innerText || '');
    const firstText = (selectors: string[], minLen = 1, maxLen = 5000) => {
      for (const selector of selectors) {
        for (const node of Array.from(document.querySelectorAll(selector))) {
          const value = clean((node as HTMLElement).innerText || node.textContent || node.getAttribute('title') || '');
          if (value.length >= minLen && value.length <= maxLen) return value;
        }
      }
      return '';
    };
    const parseCount = (labels: string[]) => {
      for (const label of labels) {
        const patterns = [
          new RegExp(`([0-9]+(?:\\.[0-9]+)?\\s*(?:万|千|w|W|k|K)?)\\s*${label}`),
          new RegExp(`${label}\\s*([0-9]+(?:\\.[0-9]+)?\\s*(?:万|千|w|W|k|K)?)`)
        ];
        for (const pattern of patterns) {
          const match = text.replace(/,/g, '').match(pattern);
          if (match) return match[1].replace(/\s+/g, '');
        }
      }
      return '';
    };
    const title = firstText(['#detail-title', 'h1', '.title', '[class*="title"]'], 2, 180)
      || clean(document.title || '').replace(/\s*[-|_]\s*小红书.*$/, '').replace(/\s*小红书.*$/, '');
    const desc = firstText(['#detail-desc', '.note-content', '.desc', '[class*="desc"]', '[class*="content"]'], 3, 8000)
      || title;
    let nickname = firstText([
      '#noteContainer [class*="author"] [class*="name"]',
      '#noteContainer [class*="user"] [class*="name"]',
      '#noteContainer [class*="nickname"]',
      '[class*="author"] [class*="name"]',
      '[class*="user"] [class*="name"]',
      '[class*="nickname"]'
    ], 1, 80);
    if ((!nickname || nickname === '我') && title) {
      const titleIndex = text.indexOf(title);
      const beforeTitle = titleIndex > 0 ? text.slice(Math.max(0, titleIndex - 120), titleIndex) : '';
      const match = beforeTitle.match(/(?:^|\s)(?:\d+\s*\/\s*\d+\s+)?(.{1,36}?)\s+关注\s*$/);
      if (match) nickname = clean(match[1]);
    }
    return {
      note_id: noteId,
      source_url: location.href,
      title,
      desc,
      type: text.includes('说点什么') ? 'normal' : '',
      time: '',
      ip_location: '',
      user: { nickname: nickname || '' },
      interact_info: {
        liked_count: parseCount(['点赞', '赞']),
        collected_count: parseCount(['收藏']),
        comment_count: parseCount(['评论']),
        share_count: parseCount(['分享'])
      }
    };
  };

  const reportToPipeline = async (card: any) => {
    const reportNoteId = clean(card?.note_id || noteId);
    if (!reportNoteId) return;
    const reportKey = `${reportNoteId}:${clean(card?.title)}:${clean(card?.desc).slice(0, 80)}`;
    if (reportedKeyRef.current === reportKey) return;
    const payload = {
      ...card,
      note_id: reportNoteId,
      source_url: card?.source_url || location.href,
      platform: 'xhs',
      reported_at: new Date().toISOString()
    };
    for (const port of [8766, 8765, 8767, 8768, 8769]) {
      try {
        const response = await fetch(`http://127.0.0.1:${port}/api/copilot/xhs-note`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
          mode: 'cors',
        });
        if (response.ok) {
          reportedKeyRef.current = reportKey;
          console.info('Social_Media_Copilot cached xhs note for Pipeline', reportNoteId, port);
          return;
        }
      } catch (error) {
        // Pipeline GUI may not be running on this port. Try the next common port silently.
      }
    }
  };

  const getNoteCard = async () => {
    if (noteCard) return noteCard;
    try {
      if (xsecToken) {
        const res = await webV1Feed(noteId, 'pc_feed', xsecToken);
        const card = res.items?.[0]?.note_card;
        const withContext = {
          ...card,
          source_url: location.href,
        };
        setNoteCard(withContext);
        await reportToPipeline(withContext);
        return withContext;
      }
    } catch (error) {
      console.warn('Social_Media_Copilot xhs feed api failed, fallback to DOM', error);
    }
    const card = getDomNoteCard();
    setNoteCard(card);
    await reportToPipeline(card);
    return card;
  };

  useEffect(() => {
    getNoteCard().catch((error) => {
      console.warn('Social_Media_Copilot xhs note cache report failed', error);
    });
  }, [noteId, xsecToken]);

  const downloadMedia = async () => {
    const noteCard = await getNoteCard();
    const files = getPostMedias(noteCard, ['video']);
    for (const file of files) {
      await sendMessage("download", {
        filename: file.filename,
        url: file.url,
      });
    }
    toast.success("下载成功");
  };

  const handleOpenDialog = async () => {
    const noteCard = await getNoteCard();
    sendMessage('openTaskDialog', {
      name: 'post-comment',
      post: {
        postId: noteCard.note_id,
        commentCount: parseInt(noteCard.interact_info?.comment_count),
        title: noteCard.title,
        url: location.href
      }
    })
  }

  const copyOptions: CopyOption[] = [{
    label: "笔记ID",
    value: "note_id"
  }, {
    label: "笔记链接",
    value: "source_url"
  }, {
    label: "博主昵称",
    value: "user.nickname"
  }, {
    label: "笔记类型",
    value: "type",
    hidden: true
  }, {
    label: "点赞数",
    value: "interact_info.liked_count",
    hidden: true
  }, {
    label: "收藏数",
    value: "interact_info.collected_count",
    hidden: true
  }, {
    label: "评论数",
    value: "interact_info.comment_count",
    hidden: true
  }, {
    label: "分享数",
    value: "interact_info.share_count",
    hidden: true
  }, {
    label: "笔记标题",
    value: "title"
  }, {
    label: "笔记内容",
    value: "desc"
  }, {
    label: "发布时间",
    value: "time",
    hidden: true
  }, {
    label: "IP地址",
    value: "ip_location",
    hidden: true
  }];

  return (<>
    <Logo />
    <Button size="sm" onClick={throttle(downloadMedia, 3000)}>下载笔记视频/图片</Button>
    <CopyButton size="sm" options={copyOptions} getData={getNoteCard}>复制笔记信息</CopyButton>
    <Button size="sm" onClick={throttle(handleOpenDialog, 2000)}>导出评论</Button>
  </>);
};

export default defineSocialMediaCopilotUi({
  name: 'social-media-copilot-xhs-explore',
  position: "inline",
  append: "after",
  className: "flex px-6 pb-[24px] gap-4",
  matches: ["*://www.xiaohongshu.com/explore/*"],
  anchor: "#noteContainer > div.interaction-container > div.author-container",
  render: ({ root, remove }) => {
    const noteId = location.pathname.split("/").reverse()[0];
    const xsecToken = new URL(location.href).searchParams.get("xsec_token") as string || '';
    if (!noteId) {
      remove();
      return;
    }
    root.render(<Component noteId={noteId} xsecToken={xsecToken} />);
  }
});
