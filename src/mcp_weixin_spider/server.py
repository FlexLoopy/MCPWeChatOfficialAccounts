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
    from .spider import WeixinSpiderWithImages
    logger.info("使用重构后的爬虫模块")
except ImportError as e:
    logger.error(f"导入爬虫模块失败: {e}")
    sys.exit(1)


class BrowserPool:
    """浏览器池管理类，线程安全"""
    
    def __init__(self, max_size: int = 5):
        self._pool: list[WeixinSpiderWithImages] = []
        self._max_size = max_size
        self._lock = threading.Lock()
        self._initialized = False
    
    def _initialize(self):
        """初始化浏览器池"""
        with self._lock:
            if self._initialized:
                return
            
            logger.info(f"初始化浏览器池，最大实例数: {self._max_size}")
            for i in range(self._max_size):
                try:
                    spider = WeixinSpiderWithImages(
                        headless=config.spider.headless,
                        wait_time=config.spider.wait_time,
                        download_images=config.spider.download_images,
                        browser=config.spider.browser
                    )
                    self._pool.append(spider)
                    logger.info(f"浏览器实例 {i+1}/{self._max_size} 初始化成功")
                except Exception as e:
                    logger.error(f"浏览器实例 {i+1}/{self._max_size} 初始化失败: {e}")
            
            self._initialized = True
    
    def get_browser(self) -> WeixinSpiderWithImages:
        """从池中获取浏览器实例"""
        with self._lock:
            # 初始化浏览器池（延迟初始化）
            if not self._initialized:
                self._initialize()
            
            if not self._pool:
                # 池为空，创建临时实例
                logger.warning("浏览器池为空，创建临时实例")
                return WeixinSpiderWithImages(
                    headless=config.spider.headless,
                    wait_time=config.spider.wait_time,
                    download_images=config.spider.download_images,
                    browser=config.spider.browser
                )
            
            # 从池中获取最后一个实例（栈式管理）
            return self._pool.pop()
    
    def return_browser(self, spider: WeixinSpiderWithImages):
        """将浏览器实例归还到池中"""
        with self._lock:
            if len(self._pool) < self._max_size:
                # 检查浏览器实例是否可用
                if spider and spider.driver:
                    try:
                        # 重置浏览器状态
                        spider.driver.delete_all_cookies()
                        spider.driver.execute_script("window.localStorage.clear();")
                        spider.driver.execute_script("window.sessionStorage.clear();")
                        spider.driver.get("about:blank")
                        
                        self._pool.append(spider)
                        logger.debug("浏览器实例已归还到池中")
                    except Exception as e:
                        logger.error(f"重置浏览器实例时出错: {e}")
                        # 关闭损坏的实例
                        try:
                            spider.close()
                        except Exception:
                            pass
                else:
                    # 实例已不可用，关闭并丢弃
                    try:
                        spider.close()
                    except Exception:
                        pass
            else:
                # 池已满，关闭实例
                try:
                    spider.close()
                    logger.debug("浏览器池已满，关闭多余实例")
                except Exception:
                    pass
    
    def close_all(self):
        """关闭所有浏览器实例"""
        with self._lock:
            for spider in self._pool:
                try:
                    spider.close()
                except Exception as e:
                    logger.error(f"关闭浏览器实例时出错: {e}")
            self._pool.clear()
            self._initialized = False
            logger.info("所有浏览器实例已关闭")


from collections import OrderedDict
from datetime import datetime, timedelta

class ArticleCache:
    """优化后的文章缓存管理类，支持LRU淘汰和过期时间"""
    
    def __init__(self, max_size: int = 100, expire_time: int = 3600):
        self._cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._cache_time: Dict[str, datetime] = {}  # 缓存创建时间
        self._max_size = max_size
        self._expire_time = expire_time  # 缓存过期时间（秒）
        self._lock = threading.Lock()
    
    def get(self, url: str) -> Optional[Dict[str, Any]]:
        """获取缓存的文章，检查过期时间"""
        with self._lock:
            if url not in self._cache:
                return None
            
            # 检查过期时间
            cache_time = self._cache_time[url]
            if datetime.now() - cache_time > timedelta(seconds=self._expire_time):
                del self._cache[url]
                del self._cache_time[url]
                return None
            
            # 移动到末尾表示最近使用
            self._cache.move_to_end(url)
            return self._cache[url]
    
    def set(self, url: str, data: Dict[str, Any]):
        """设置缓存的文章"""
        with self._lock:
            if url in self._cache:
                # 更新缓存
                self._cache[url] = data
                self._cache.move_to_end(url)
            else:
                # 检查缓存大小
                if len(self._cache) >= self._max_size:
                    # 移除最旧的缓存
                    oldest_key = next(iter(self._cache))
                    del self._cache[oldest_key]
                    del self._cache_time[oldest_key]
                
                # 添加新缓存
                self._cache[url] = data
                self._cache_time[url] = datetime.now()
    
    def clear(self):
        """清空缓存"""
        with self._lock:
            self._cache.clear()
            self._cache_time.clear()


# 初始化浏览器池
spider_pool = BrowserPool(max_size=5)  # 最大5个浏览器实例

# 初始化文章缓存
article_cache = ArticleCache(max_size=100, expire_time=3600)  # 缓存100条，过期时间1小时


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
    # 导入自定义异常类
    from .exceptions import InvalidURLError, CrawlFailedError
    
    # 验证URL
    if not url or not isinstance(url, str) or not url.startswith("https://mp.weixin.qq.com/"):
        raise InvalidURLError(url, "必须是有效的微信文章URL，以 https://mp.weixin.qq.com/ 开头")
    
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
    
    # 从浏览器池获取爬虫实例
    spider = None
    try:
        # 获取浏览器实例
        spider = spider_pool.get_browser()
        
        # 设置参数
        spider.download_images = download_images
        
        # 爬取文章
        article_data = spider.crawl_article_by_url(url)
        if not article_data:
            raise CrawlFailedError(url, "无法获取文章内容")
        
        # 保存文章到文件
        if not spider.save_article_to_file(article_data, custom_filename):
            raise CrawlFailedError(url, "保存文件时出错")
        
        # 构建返回结果
        result = {
            "status": "success",
            "message": "文章爬取成功",
            "article": {
                "title": article_data.title,
                "author": article_data.author,
                "publish_time": article_data.publish_time,
                "url": article_data.url,
                "content_length": len(article_data.content),
                "images_count": len(article_data.images),
                "crawl_time": article_data.crawl_time
            },
            "files_saved": {
                "json": True,
                "txt": True,
                "images": download_images
            }
        }
        
        if download_images:
            images = article_data.images
            success_count = sum(1 for img in images if img.download_success)
            result["article"]["images_downloaded"] = f"{success_count}/{len(images)}"
        
        # 缓存文章数据（不包含图片信息）
        cache_data = {
            "article": result["article"],
            "crawl_time": article_data.crawl_time
        }
        article_cache.set(url, cache_data)
        
        return create_json_response(result)
        
    except InvalidURLError as e:
        logger.error(f"URL验证失败: {e}")
        return create_json_response({
            "status": "error",
            "code": "INVALID_URL",
            "message": str(e),
            "url": url
        })
    except CrawlFailedError as e:
        logger.error(f"爬取失败: {e}")
        return create_json_response({
            "status": "error",
            "code": "CRAWL_FAILED",
            "message": str(e),
            "url": url,
            "attempt": getattr(e, "attempt", 1)
        })
    except Exception as e:
        logger.error(f"爬取文章时发生意外错误: {e}", exc_info=True)
        return create_json_response({
            "status": "error",
            "code": "INTERNAL_ERROR",
            "message": f"内部错误: {str(e)}",
            "url": url
        })
    finally:
        # 将浏览器实例归还到池中
        if spider:
            spider_pool.return_browser(spider)


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
    spider_pool.close_all()
    article_cache.clear()
    logger.info("资源清理完成")


def main():
    """启动MCP服务器"""
    try:
        logger.info("启动MCP微信爬虫服务器 (FastMCP版本)")
        logger.info(f"配置信息: 无头模式={config.spider.headless}, 等待时间={config.spider.wait_time}秒")
        
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