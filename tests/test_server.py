#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试MCP微信爬虫服务器
"""

import json
import sys
import os

# 添加项目路径到sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from mcp.client import MCPClient
    from mcp.client.mcp import MCPError
    
    def test_server():
        """测试MCP服务器"""
        print("=== 测试MCP微信爬虫服务器 ===")
        
        # 创建MCP客户端
        client = MCPClient()
        
        try:
            # 连接到服务器
            client.connect()
            print("[SUCCESS] 成功连接到MCP服务器")
            
            # 获取可用工具
            tools = client.list_tools()
            print(f"\n[SUCCESS] 可用工具列表: {[tool['name'] for tool in tools]}")
            
            # 测试爬取文章工具
            test_url = "https://mp.weixin.qq.com/s/1qZ4a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a"
            print(f"\n=== 测试爬取文章工具 ===")
            print(f"测试URL: {test_url}")
            
            try:
                result = client.call_tool(
                    "crawl_weixin_article",
                    url=test_url,
                    download_images=False
                )
                print(f"[SUCCESS] 工具调用成功")
                print(f"结果类型: {type(result)}")
                
                if isinstance(result, str):
                    try:
                        result_json = json.loads(result)
                        print(f"[SUCCESS] 结果解析为JSON")
                        print(f"结果状态: {result_json.get('status')}")
                        print(f"结果消息: {result_json.get('message')}")
                    except json.JSONDecodeError:
                        print(f"[ERROR] 结果不是有效的JSON")
                        print(f"原始结果: {result}")
                else:
                    print(f"[SUCCESS] 结果: {result}")
            except MCPError as e:
                print(f"[WARNING] 工具调用失败: {e}")
                print("这可能是因为测试URL无效，实际使用时请提供有效的微信公众号文章URL")
            except Exception as e:
                print(f"[ERROR] 工具调用发生异常: {e}")
                import traceback
                traceback.print_exc()
            
        except Exception as e:
            print(f"[ERROR] 连接服务器失败: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # 关闭连接
            client.disconnect()
            print("\n[SUCCESS] 已关闭连接")
    
    if __name__ == "__main__":
        test_server()
        print("\n=== 测试完成 ===")
        
except ImportError as e:
    print(f"[ERROR] 导入MCP客户端失败: {e}")
    print("请确保已安装MCP客户端库")
    sys.exit(1)
