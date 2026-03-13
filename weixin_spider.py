#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信公众号文章爬虫 - 简化优化版本
支持文章内容抓取、图片下载、多种格式保存
使用dataclass简化数据结构，优化代码逻辑
"""

import logging
from src.mcp_weixin_spider.spider import (
    WeixinSpider,   
    DependencyChecker
)
from src.mcp_weixin_spider.config import config

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_spider():
    """测试爬虫功能"""
    test_urls = [
        "https://mp.weixin.qq.com/s/KJl2oTMaKRra2l0PV7IIiA",  # 目标文章
    ]
    
    spider = None
    try:
        logger.info("开始测试微信公众号爬虫...")
        logger.info(f"使用配置文件: {config}")
        logger.info(f"配置内容: headless={config.spider.headless}, wait_time={config.spider.wait_time}, download_images={config.spider.download_images}")
        
        # 使用全局配置初始化爬虫
        spider = WeixinSpider(config=config.spider, skip_browser_check=True)
        
        for i, url in enumerate(test_urls, 1):
            logger.info(f"\n=== 测试第 {i} 个URL ===")
            logger.info(f"URL: {url}")
            
            article = spider.crawl_article_by_url(url)
            if article:
                logger.info(f"[SUCCESS] 抓取成功，标题: {article.title}")
                logger.info(f"图片数量: {len(article.images)} 张")
                
                if spider.save_article(article):
                    logger.info("[SUCCESS] 文章保存成功")
                else:
                    logger.error("[ERROR] 文章保存失败")
            else:
                logger.error("[ERROR] 抓取失败")
        
        logger.info("\n=== 测试完成 ===")
        
    except Exception as e:
        logger.error(f"测试过程中出现错误: {str(e)}", exc_info=True)
    finally:
        if spider:
            spider.close()


if __name__ == "__main__":
    logger.info("=== 微信公众号爬虫测试程序 ===")
    
    if DependencyChecker.check_dependencies():
        test_spider()