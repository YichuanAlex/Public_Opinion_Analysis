#!/bin/bash

# 切到脚本所在目录（确保无论在哪里双击都能找到 server.js）
cd "$(dirname "$0")"

# 检查是否安装了 Node.js
if ! command -v node &>/dev/null; then
  osascript -e 'display dialog "未检测到 Node.js。\n\n请先去 https://nodejs.org 下载安装 LTS 版本（大绿按钮），安装完毕后再双击本文件。" buttons {"好的"} with icon caution with title "需要先安装 Node.js"'
  exit 1
fi

# 检查 server.js 是否存在
if [ ! -f "server.js" ]; then
  osascript -e 'display dialog "找不到 server.js。\n\n请确认本文件和 server.js 在同一个文件夹里。" buttons {"好的"} with icon stop with title "文件缺失"'
  exit 1
fi

# 尝试释放 5173 端口（如果已经在跑了就直接开浏览器）
lsof -ti:5173 | xargs kill -9 2>/dev/null
sleep 0.4

# 启动 server（后台）
node server.js &
SERVER_PID=$!

# 等 server 启动，最多等 4 秒
for i in 1 2 3 4; do
  sleep 1
  if curl -s -o /dev/null http://localhost:5173; then
    break
  fi
done

# 打开浏览器
open http://localhost:5173

# 等 server 进程结束（关终端窗口 = 停止服务）
wait $SERVER_PID
