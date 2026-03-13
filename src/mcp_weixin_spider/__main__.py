#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MCP微信爬虫模块入口点

支持以下启动方式：
1. python3 -m mcp_weixin_spider.server  # 启动MCP服务器
2. python3 -m mcp_weixin_spider         # 默认启动MCP服务器
3. python3 -m mcp_weixin_spider client  # 启动交互式客户端
"""

import sys
from pathlib import Path

# 添加当前目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

# 导入并使用main.py中的main函数，统一入口点
from mcp_weixin_spider.main import main

if __name__ == "__main__":
    main()
