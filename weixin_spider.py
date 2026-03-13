#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信公众号文章爬虫 - 简化优化版本
支持文章内容抓取、图片下载、多种格式保存
使用dataclass简化数据结构，优化代码逻辑
"""

import time
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from dataclasses import dataclass
from pathlib import Path
from src.mcp_weixin_spider.common import (
    WeixinSpiderBase,
    BrowserDriverManager,
    ArticleParser,
    ImageDownloader,
    ArticleSaver,
    SessionManager,
    DependencyChecker
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class WeixinSpider(WeixinSpiderBase):
    """微信公众号文章爬虫类，支持多浏览器和图片下载"""
    
    def __post_init__(self):
        """执行初始化逻辑"""
        self.browser = self.browser.lower()
        self.session = SessionManager.create_session()
        driver_manager = BrowserDriverManager(self.browser, self.headless)
        self.driver = driver_manager.create_driver()
        logger.info("浏览器驱动初始化成功")
    
    def crawl_article_by_url(self, url, retry_times=2):
        """通过URL抓取文章内容"""
        for attempt in range(retry_times):
            try:
                logger.info(f"第 {attempt + 1} 次尝试访问文章: {url}")
                
                self.driver.get(url)
                wait = WebDriverWait(self.driver, self.wait_time)
                
                # 等待文章标题加载
                try:
                    wait.until(EC.presence_of_element_located((By.ID, "activity-name")))
                except:
                    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".rich_media_title")))
                
                # 滚动页面确保内容完全加载
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
                
                # 提取文章信息
                article_data = ArticleParser.extract_article_content(self.driver, self.wait_time)
                
                # 下载图片
                if self.download_images and article_data:
                    image_downloader = ImageDownloader(self.session, self.max_workers)
                    image_downloader.download_all_images(article_data, self.save_dir)
                
                return article_data
                
            except Exception as e:
                logger.error(f"第 {attempt + 1} 次尝试失败: {str(e)}")
                if attempt == retry_times - 1:
                    raise
                time.sleep(2 * (attempt + 1))
        
        raise Exception("所有重试都失败了")
    
    def save_article(self, article_data, custom_filename=None):
        """保存文章到文件"""
        if not article_data:
            logger.warning("没有文章数据可保存")
            return False
        
        return ArticleSaver.save_article(article_data, self.save_dir, custom_filename, self.download_images)


def test_spider():
    """测试爬虫功能"""
    test_urls = [
        "https://mp.weixin.qq.com/s/KJl2oTMaKRra2l0PV7IIiA",  # 目标文章
    ]
    
    spider = None
    try:
        logger.info("开始测试微信公众号爬虫...")
        spider = WeixinSpider(headless=True, download_images=True)
        
        for i, url in enumerate(test_urls, 1):
            logger.info(f"\n=== 测试第 {i} 个URL ===")
            logger.info(f"URL: {url}")
            
            article = spider.crawl_article_by_url(url)
            if article:
                logger.info(f"✅ 抓取成功，标题: {article.title}")
                logger.info(f"图片数量: {len(article.images)} 张")
                
                if spider.save_article(article):
                    logger.info("✅ 文章保存成功")
                else:
                    logger.error("❌ 文章保存失败")
            else:
                logger.error("❌ 抓取失败")
        
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