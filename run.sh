#!/bin/bash
# AI信息助手 - Linux/Mac 启动脚本

cd "$(dirname "$0")"

# 激活虚拟环境
if [ -f .venv/bin/activate ]; then
    source .venv/bin/activate
else
    echo "⚠️ 虚拟环境不存在，请先运行: python -m venv .venv && .venv/bin/pip install -r requirements.txt"
    exit 1
fi

# 运行
if [ $# -eq 0 ]; then
    python src/main.py
else
    python src/main.py "$@"
fi
