#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MCP微信公众号文章爬虫服务器 - FastMCP版本

基于MCP标准实现，使用FastMCP高级封装
提供以下功能：
1. 爬取微信公众号文章内容
2. 下载文章中的图片
3. 返回结构化的文章数据
4. 提供文章内容分析
"""

import json
import logging
import sys
import os
import threading
from typing import Dict, Optional, Any

# 导入配置管理
from .config import config

# 导入MCP FastMCP
try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    print("FastMCP不可用，请使用标准server.py")
    sys.exit(1)

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.append(project_root)

# 配置日志
logging.basicConfig(
    level=getattr(logging, config.log.level),
    format=config.log.format,
    filename=config.log.file
)
logger = logging.getLogger(__name__)

# 创建FastMCP应用实例
app = FastMCP(config.mcp.server_name)

# 导入爬虫模块
try:
    # 使用简化版爬虫
    from weixin_spider_simple import WeixinSpiderWithImages
    logger.info("使用简化版爬虫模块")
except ImportError as e:
    logger.error(f"导入简化版爬虫模块失败: {e}")
    sys.exit(1)


class SpiderSingleton:
    """爬虫单例管理类，线程安全"""
    
    _instance: Optional[WeixinSpiderWithImages] = None
    _lock = threading.Lock()
    
    @classmethod
    def get_instance(cls) -> WeixinSpiderWithImages:
        """获取爬虫实例，线程安全"""
        if cls._instance is None or cls._instance.driver is None:
            with cls._lock:
                if cls._instance is None or cls._instance.driver is None:
                    if cls._instance and cls._instance.driver is None:
                        logger.warning("检测到驱动已失效，重新初始化...")
                        try:
                            cls._instance.setup_driver(headless=config.spider.headless)
                            logger.info("驱动重新初始化成功")
                        except Exception as e:
                            logger.error(f"驱动重新初始化失败: {e}")
                            cls._instance = None
                    
                    if cls._instance is None:
                        try:
                            cls._instance = WeixinSpiderWithImages(
                                headless=config.spider.headless,
                                wait_time=config.spider.wait_time,
                                download_images=config.spider.download_images
                            )
                            logger.info("爬虫实例初始化成功")
                        except Exception as e:
                            logger.error(f"爬虫实例初始化失败: {e}")
                            raise RuntimeError(f"无法初始化爬虫实例: {e}")
        return cls._instance
    
    @classmethod
    def close_instance(cls):
        """关闭爬虫实例"""
        with cls._lock:
            if cls._instance:
                try:
                    cls._instance.close()
                    logger.info("爬虫实例已关闭")
                except Exception as e:
                    logger.error(f"关闭爬虫实例时出错: {e}")
                finally:
                    cls._instance = None


class ArticleCache:
    """文章缓存管理类"""
    
    def __init__(self, max_size: int = 100):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._max_size = max_size
        self._lock = threading.Lock()
    
    def get(self, url: str) -> Optional[Dict[str, Any]]:
        """获取缓存的文章"""
        with self._lock:
            return self._cache.get(url)
    
    def set(self, url: str, data: Dict[str, Any]):
        """设置缓存的文章"""
        with self._lock:
            if len(self._cache) >= self._max_size:
                # 移除最旧的缓存
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
            self._cache[url] = data
    
    def clear(self):
        """清空缓存"""
        with self._lock:
            self._cache.clear()


# 初始化文章缓存
article_cache = ArticleCache(max_size=100)


def create_json_response(data: Dict, ensure_ascii: bool = False, indent: int = 2) -> str:
    """创建JSON响应"""
    return json.dumps(data, ensure_ascii=ensure_ascii, indent=indent)


@app.tool()
def crawl_weixin_article(url: str, download_images: bool = True, custom_filename: str = None) -> str:
    """
    爬取微信公众号文章内容和图片
    
    Args:
        url: 微信公众号文章的URL链接
        download_images: 是否下载文章中的图片
        custom_filename: 自定义文件名（可选）
    
    Returns:
        爬取结果的JSON字符串
    """
    try:
        # 验证URL
        if not url or not isinstance(url, str) or not url.startswith("https://mp.weixin.qq.com/"):
            raise ValueError("无效的微信文章URL，必须以 https://mp.weixin.qq.com/ 开头")
        
        logger.info(f"开始爬取文章: {url}")
        
        # 检查缓存
        cached_data = article_cache.get(url)
        if cached_data and not download_images:  # 只有当不需要下载图片时才使用缓存
            logger.info(f"使用缓存的文章数据: {url}")
            return create_json_response({
                "status": "success",
                "message": "从缓存获取文章成功",
                "article": cached_data["article"],
                "files_saved": {
                    "json": True,
                    "txt": True,
                    "images": False
                }
            })
        
        # 获取爬虫实例并设置参数
        spider = SpiderSingleton.get_instance()
        spider.download_images = download_images
        
        # 爬取文章
        article_data = spider.crawl_article_by_url(url)
        if not article_data:
            raise RuntimeError("无法获取文章内容")
        
        # 保存文章到文件
        if not spider.save_article_to_file(article_data, custom_filename):
            raise RuntimeError("保存文件时出错")
        
        # 构建返回结果
        result = {
            "status": "success",
            "message": "文章爬取成功",
            "article": {
                "title": article_data.get("title", ""),
                "author": article_data.get("author", ""),
                "publish_time": article_data.get("publish_time", ""),
                "url": article_data.get("url", ""),
                "content_length": len(article_data.get("content", "")),
                "images_count": len(article_data.get("images", [])),
                "crawl_time": article_data.get("crawl_time", "")
            },
            "files_saved": {
                "json": True,
                "txt": True,
                "images": download_images
            }
        }
        
        if download_images:
            images = article_data.get("images", [])
            success_count = sum(1 for img in images if img.get("download_success", False))
            result["article"]["images_downloaded"] = f"{success_count}/{len(images)}"
        
        # 缓存文章数据（不包含图片信息）
        cache_data = {
            "article": result["article"],
            "crawl_time": article_data.get("crawl_time", "")
        }
        article_cache.set(url, cache_data)
        
        return create_json_response(result)
        
    except ValueError as e:
        logger.error(f"参数错误: {e}")
        return create_json_response({
            "status": "error",
            "message": f"参数错误: {str(e)}",
            "url": url
        })
    except RuntimeError as e:
        logger.error(f"爬取失败: {e}")
        return create_json_response({
            "status": "error",
            "message": f"爬取失败: {str(e)}",
            "url": url
        })
    except Exception as e:
        logger.error(f"爬取文章时发生意外错误: {e}", exc_info=True)
        return create_json_response({
            "status": "error",
            "message": f"爬取失败: {str(e)}",
            "url": url
        })


@app.tool()
def analyze_article_content(article_data: dict, analysis_type: str = "full") -> str:
    """
    分析已爬取的文章内容，提取关键信息
    
    Args:
        article_data: 文章数据对象
        analysis_type: 分析类型：summary(摘要), keywords(关键词), images(图片信息), full(完整分析)
    
    Returns:
        分析结果的JSON字符串
    """
    try:
        if not article_data or not isinstance(article_data, dict):
            raise ValueError("article_data 必须是字典格式的文章数据")
        
        # 检查文章数据的基本字段
        required_fields = ["title", "content"]
        missing_fields = [field for field in required_fields if field not in article_data]
        if missing_fields:
            logger.warning(f"文章数据缺少字段: {missing_fields}")
        
        logger.info(f"分析文章内容: analysis_type={analysis_type}, 文章标题={article_data.get('title', 'N/A')[:30]}...")
        
        result = {"analysis_type": analysis_type}
        content = article_data.get("content", "")
        
        # 生成摘要
        if analysis_type in ["summary", "full"]:
            result["summary"] = {
                "title": article_data.get("title", ""),
                "author": article_data.get("author", ""),
                "publish_time": article_data.get("publish_time", ""),
                "content_preview": content[:200] + "..." if len(content) > 200 else content,
                "word_count": len(content),
                "paragraph_count": len(content.split("\n\n")) if content else 0
            }
        
        # 提取关键词
        if analysis_type in ["keywords", "full"]:
            # 简单的关键词提取（基于词频）
            word_freq = {}
            for word in content.split():
                if len(word) > 1:  # 过滤单字符
                    word_freq[word] = word_freq.get(word, 0) + 1
            
            # 获取前10个高频词
            top_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:10]
            result["keywords"] = [word for word, freq in top_words]
        
        # 分析图片
        if analysis_type in ["images", "full"]:
            images = article_data.get("images", [])
            downloaded = sum(1 for img in images if img.get("download_success", False))
            result["images_analysis"] = {
                "total_count": len(images),
                "downloaded_count": downloaded,
                "failed_count": len(images) - downloaded,
                "image_details": [
                    {
                        "filename": img.get("filename", ""),
                        "alt_text": img.get("alt", ""),
                        "download_success": img.get("download_success", False)
                    }
                    for img in images[:5]  # 只显示前5张图片的详情
                ]
            }
        
        return create_json_response(result)
        
    except Exception as e:
        logger.error(f"分析文章内容失败: {e}", exc_info=True)
        return create_json_response({
            "status": "error",
            "message": f"分析失败: {str(e)}"
        })


@app.tool()
def get_article_statistics(article_data: dict) -> str:
    """
    获取文章统计信息（字数、图片数量等）
    
    Args:
        article_data: 文章数据对象
    
    Returns:
        统计信息的JSON字符串
    """
    try:
        if not article_data or not isinstance(article_data, dict):
            raise ValueError("article_data 必须是字典格式的文章数据")
        
        content = article_data.get("content", "")
        images = article_data.get("images", [])
        downloaded = sum(1 for img in images if img.get("download_success", False))
        
        stats = {
            "basic_info": {
                "title": article_data.get("title", ""),
                "author": article_data.get("author", ""),
                "publish_time": article_data.get("publish_time", ""),
                "crawl_time": article_data.get("crawl_time", "")
            },
            "content_statistics": {
                "total_characters": len(content),
                "total_words": len(content.split()),
                "paragraphs": len(content.split("\n\n")) if content else 0,
                "lines": len(content.split("\n")) if content else 0
            },
            "image_statistics": {
                "total_images": len(images),
                "downloaded_successfully": downloaded,
                "download_failed": len(images) - downloaded,
                "download_success_rate": f"{(downloaded / len(images) * 100):.1f}%" if images else "0%"
            }
        }
        
        return create_json_response(stats)
        
    except Exception as e:
        logger.error(f"获取统计信息失败: {e}", exc_info=True)
        return create_json_response({
            "status": "error",
            "message": f"统计失败: {str(e)}"
        })


@app.tool()
def clear_article_cache() -> str:
    """
    清空文章缓存
    
    Returns:
        操作结果的JSON字符串
    """
    try:
        article_cache.clear()
        logger.info("文章缓存已清空")
        return create_json_response({
            "status": "success",
            "message": "文章缓存已清空"
        })
    except Exception as e:
        logger.error(f"清空缓存失败: {e}", exc_info=True)
        return create_json_response({
            "status": "error",
            "message": f"清空缓存失败: {str(e)}"
        })


def cleanup():
    """清理资源"""
    logger.info("正在清理资源...")
    SpiderSingleton.close_instance()
    article_cache.clear()
    logger.info("资源清理完成")


def main():
    """启动MCP服务器"""
    try:
        logger.info("启动MCP微信爬虫服务器 (FastMCP版本)")
        logger.info(f"配置信息: 无头模式={config.spider.headless}, 等待时间={config.spider.wait_time}秒")
        
        # 预热爬虫实例
        try:
            SpiderSingleton.get_instance()
            logger.info("爬虫实例预热完成")
        except Exception as e:
            logger.error(f"爬虫实例预热失败: {e}")
            return
        
        logger.info("MCP微信爬虫服务器启动")
        app.run(transport=config.mcp.transport)
        
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在关闭服务器...")
    except Exception as e:
        logger.error(f"服务器运行出错: {e}", exc_info=True)
    finally:
        cleanup()
        logger.info("MCP微信爬虫服务器已关闭")


if __name__ == "__main__":
    main()