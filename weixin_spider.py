#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信公众号文章爬虫 - 简化优化版本
支持文章内容抓取、图片下载、多种格式保存
使用dataclass简化数据结构，优化代码逻辑
"""

import time
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import json
import os
import logging
from datetime import datetime
import re
from urllib.parse import urljoin
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, asdict
from typing import List, Optional

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class ImageInfo:
    """图片信息数据类"""
    index: int
    url: str
    alt: str = ""
    title: str = ""
    filename: Optional[str] = None
    local_path: Optional[str] = None
    download_success: bool = False


@dataclass
class ArticleData:
    """文章数据类"""
    title: str
    author: str
    publish_time: str
    content_html: str
    content: str
    url: str
    crawl_time: str
    images: List[ImageInfo] = field(default_factory=list)


@dataclass
class WeixinSpider:
    """微信公众号文章爬虫类，支持多浏览器和图片下载"""
    headless: bool = True
    wait_time: int = 10
    download_images: bool = True
    max_workers: int = 4
    browser: str = 'chrome'
    
    driver: Optional[webdriver.Chrome] = field(default=None, init=False)
    session: requests.Session = field(default_factory=requests.Session, init=False)
    
    def __post_init__(self):
        """执行初始化逻辑"""
        self.browser = self.browser.lower()
        self.setup_session()
        self.setup_driver()
    
    def setup_session(self):
        """设置requests会话"""
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        })
    
    def setup_driver(self):
        """设置浏览器驱动"""
        logger.info(f"正在设置{self.browser}浏览器驱动...")
        
        options = ChromeOptions()
        if self.headless:
            options.add_argument('--headless=new')
        
        # 基本设置
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-blink-features=AutomationControlled')
        
        # 排除自动化标识
        options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
        options.add_experimental_option('useAutomationExtension', False)
        
        # 使用webdriver-manager自动下载兼容的驱动
        service = ChromeService(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
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
                return self._extract_article_content()
                
            except Exception as e:
                logger.error(f"第 {attempt + 1} 次尝试失败: {str(e)}")
                if attempt == retry_times - 1:
                    raise
                time.sleep(2 * (attempt + 1))
        
        raise Exception("所有重试都失败了")
    
    def _extract_article_content(self):
        """提取文章内容"""
        try:
            # 获取页面源码
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # 获取文章标题
            title = soup.find(id="activity-name").get_text(strip=True) if soup.find(id="activity-name") else \
                   soup.find(class_="rich_media_title").get_text(strip=True) if soup.find(class_="rich_media_title") else "未知标题"
            
            # 获取作者信息
            author = "未知作者"
            author_elements = soup.select(".rich_media_meta_text")
            if author_elements:
                author = author_elements[0].get_text(strip=True)
            
            # 获取发布时间
            publish_time = "未知时间"
            time_elements = soup.select("#publish_time, .rich_media_meta_text:last-child")
            if time_elements:
                publish_time = time_elements[0].get_text(strip=True)
            
            # 获取文章正文内容
            content_element = soup.find(id="js_content") or soup.find(class_="rich_media_content")
            content_html = str(content_element) if content_element else ""
            content = content_element.get_text(separator='\n', strip=True) if content_element else ""
            
            # 提取图片信息
            images = []
            if self.download_images and content_element:
                img_elements = content_element.find_all('img')
                for i, img in enumerate(img_elements, 1):
                    img_url = img.get('data-src') or img.get('src')
                    if not img_url or img_url.startswith('data:'):
                        continue
                    
                    # 处理相对URL
                    if img_url.startswith('//'):
                        img_url = 'https:' + img_url
                    elif img_url.startswith('/'):
                        img_url = urljoin(self.driver.current_url, img_url)
                    
                    alt_text = img.get('alt') or f"图片_{i}"
                    images.append(ImageInfo(index=i, url=img_url, alt=alt_text))
            
            return ArticleData(
                title=title,
                author=author,
                publish_time=publish_time,
                content_html=content_html,
                content=content,
                url=self.driver.current_url,
                crawl_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                images=images
            )
            
        except Exception as e:
            logger.error(f"提取文章内容失败: {str(e)}", exc_info=True)
            return None
    
    def _download_image(self, img_info, save_dir):
        """下载单张图片"""
        try:
            # 发送请求下载图片
            response = self.session.get(img_info.url, timeout=30, stream=True)
            response.raise_for_status()
            
            # 生成文件名
            filename = f"img_{img_info.index:03d}.png"
            filepath = os.path.join(save_dir, filename)
            
            # 保存图片
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            img_info.filename = filename
            img_info.local_path = filepath
            img_info.download_success = True
            logger.debug(f"图片下载成功: {filename}")
            
        except Exception as e:
            logger.error(f"下载图片失败 {img_info.url}: {str(e)}")
            img_info.download_success = False
    
    def _download_all_images(self, article_data, save_dir):
        """下载所有图片"""
        if not article_data.images:
            return
        
        # 创建图片保存目录
        images_dir = os.path.join(save_dir, "images")
        os.makedirs(images_dir, exist_ok=True)
        
        logger.info(f"开始下载 {len(article_data.images)} 张图片...")
        
        # 使用线程池并行下载图片
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [
                executor.submit(self._download_image, img_info, images_dir)
                for img_info in article_data.images
            ]
            
            # 等待所有下载完成
            for future in futures:
                future.result()
        
        success_count = sum(1 for img in article_data.images if img.download_success)
        logger.info(f"图片下载完成: {success_count}/{len(article_data.images)} 张成功")
    
    def save_article(self, article_data, custom_filename=None):
        """保存文章到文件"""
        if not article_data:
            logger.warning("没有文章数据可保存")
            return False
        
        try:
            # 创建保存目录
            save_dir = Path(__file__).parent / "articles"
            save_dir.mkdir(exist_ok=True)
            
            # 生成安全的文件名
            if custom_filename:
                safe_filename = custom_filename
            else:
                safe_title = re.sub(r'[<>:"/\\|?*]', '_', article_data.title)[:50]
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                safe_filename = f"{safe_title}_{timestamp}"
            
            # 创建文章专用目录
            article_dir = save_dir / safe_filename
            article_dir.mkdir(exist_ok=True)
            
            # 下载图片
            if self.download_images:
                self._download_all_images(article_data, article_dir)
            
            # 保存JSON格式
            json_file = article_dir / f"{safe_filename}.json"
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(asdict(article_data), f, ensure_ascii=False, indent=2)
            logger.info(f"JSON文件已保存: {json_file}")
            
            # 保存TXT格式
            txt_file = article_dir / f"{safe_filename}.txt"
            with open(txt_file, 'w', encoding='utf-8') as f:
                f.write(f"标题: {article_data.title}\n")
                f.write(f"作者: {article_data.author}\n")
                f.write(f"发布时间: {article_data.publish_time}\n")
                f.write(f"抓取时间: {article_data.crawl_time}\n")
                f.write(f"链接: {article_data.url}\n")
                f.write("\n" + "="*80 + "\n\n")
                f.write(article_data.content)
                
                # 添加图片信息
                if article_data.images:
                    f.write("\n\n" + "="*80 + "\n")
                    f.write("图片信息:\n")
                    for img in article_data.images:
                        f.write(f"\n图片 {img.index}: {img.alt}\n")
                        f.write(f"原始URL: {img.url}\n")
                        f.write(f"状态: {'下载成功' if img.download_success else '下载失败'}\n")
            logger.info(f"TXT文件已保存: {txt_file}")
            
            return True
            
        except Exception as e:
            logger.error(f"保存文件失败: {str(e)}", exc_info=True)
            return False
    
    def close(self):
        """关闭浏览器和会话"""
        logger.info("正在关闭浏览器和会话...")
        if self.driver:
            self.driver.quit()
            logger.info("浏览器已关闭")


def check_dependencies():
    """检查依赖包是否安装"""
    required_packages = {
        'selenium': 'selenium',
        'beautifulsoup4': 'bs4',
        'requests': 'requests',
        'webdriver_manager': 'webdriver_manager',
    }
    
    missing = []
    for pkg, import_name in required_packages.items():
        try:
            __import__(import_name)
            logger.info(f"✅ {pkg} 已安装")
        except ImportError:
            missing.append(pkg)
            logger.error(f"❌ {pkg} 未安装")
    
    if missing:
        logger.error(f"缺少依赖: {', '.join(missing)}")
        logger.error("请运行: pip install selenium beautifulsoup4 requests webdriver-manager")
        return False
    
    logger.info("✅ 所有依赖已安装")
    return True


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


def main():
    """主函数"""
    logger.info("=== 微信公众号爬虫测试程序 ===")
    
    if check_dependencies():
        test_spider()


if __name__ == "__main__":
    main()
