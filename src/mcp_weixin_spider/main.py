#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MCP微信爬虫主启动脚本

提供多种启动方式：
1. MCP服务器模式
2. 交互式客户端模式
"""

import argparse
import asyncio
import logging
import sys
import traceback
from pathlib import Path

# 添加当前目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from mcp_weixin_spider.server import main as server_main


def create_parser():
    """创建命令行参数解析器"""
    parser = argparse.ArgumentParser(
        description="MCP微信公众号文章爬虫",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 启动MCP服务器
  python main.py server
  
  # 启动交互式客户端
  python main.py client
  
  # 显示版本信息
  python main.py --version
        """,
    )

    parser.add_argument(
        "mode",
        choices=["server", "client"],
        help="运行模式：server(服务器), client(交互式客户端)",
    )

    parser.add_argument("--version", action="version", version="MCP微信爬虫 v0.1.0")

    parser.add_argument("--debug", action="store_true", help="启用调试模式")

    return parser


def run_server(debug: bool = False):
    """运行MCP服务器"""
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)
        print("🐛 调试模式已启用")

    print("🚀 启动MCP微信爬虫服务器...")
    server_main()


async def run_client(debug: bool = False):
    """运行交互式客户端"""
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)
        print("🐛 调试模式已启用")

    print("🎯 运行MCP交互式客户端...")
    # 动态导入client模块，避免循环导入
    from mcp_weixin_spider.client import run_client as client_runner

    server_path = Path(__file__).parent / "server.py"
    await client_runner(str(server_path))


def main():
    """主函数"""
    parser = create_parser()
    args = parser.parse_args()

    # 配置基本日志
    from mcp_weixin_spider.config import setup_logging

    setup_logging()

    try:
        if args.mode == "server":
            run_server(args.debug)
        elif args.mode == "client":
            asyncio.run(run_client(args.debug))
    except KeyboardInterrupt:
        print("\n👋 程序已退出")
    except Exception as e:
        print(f"❌ 运行时错误: {e}")
        if args.debug:
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
