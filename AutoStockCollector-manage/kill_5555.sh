#!/bin/bash
# 停止5555端口进程

lsof -ti:5555 | xargs kill -9 2>/dev/null
echo "5555端口进程已停止"
