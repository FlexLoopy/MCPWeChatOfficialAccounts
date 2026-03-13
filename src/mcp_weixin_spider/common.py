#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信公众号爬虫公共模块
包含共享的数据类、工具函数和浏览器管理功能
"""

import requests
import threading
from selenium import webdriver
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.edge.service import Service as EdgeService
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.microsoft import EdgeChromiumDriverManager
from bs4 import BeautifulSoup
import json
import os
import logging
from datetime import datetime
import re
from urllib.parse import urljoin
import shutil
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Optional, ClassVar, Dict

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
class WeixinSpiderBase:
    """微信公众号爬虫基类"""

    # 初始化参数
    headless: bool = True
    wait_time: int = 10
    download_images: bool = True
    max_workers: int = 4
    browser: str = "chrome"
    save_dir: Path = field(
        default_factory=lambda: Path(__file__).parent.parent.parent / "articles"
    )

    # 实例变量
    driver: Optional[WebDriver] = field(default=None, init=False)
    session: requests.Session = field(
        default_factory=requests.Session, init=False
    )

    def close(self):
        """关闭浏览器和会话"""
        logger.info("正在关闭浏览器和会话...")
        if self.driver:
            self.driver.quit()
            logger.info("浏览器已关闭")


@dataclass
class BrowserDriverManager:
    """浏览器驱动管理类"""

    browser: str = "chrome"
    headless: bool = True
    _chrome_driver_path: Optional[str] = None
    _chrome_driver_lock: ClassVar[threading.Lock] = threading.Lock()

    def __post_init__(self):
        self.browser = self.browser.lower()

    def find_chromedriver_path(self):
        """查找系统中的ChromeDriver路径"""
        with self._chrome_driver_lock:
            if self._chrome_driver_path:
                return self._chrome_driver_path

            # 常见的ChromeDriver路径
            possible_paths = [
                "/usr/local/bin/chromedriver",
                "/usr/bin/chromedriver",
                "/opt/homebrew/bin/chromedriver",
                shutil.which("chromedriver"),
            ]

            for path in possible_paths:
                if path and os.path.exists(path) and os.access(path, os.X_OK):
                    logger.info(f"找到ChromeDriver: {path}")
                    self._chrome_driver_path = path
                    return path

            self._chrome_driver_path = None
            return None

    def create_driver(self):
        """创建并返回浏览器驱动"""
        try:
            logger.info(f"正在设置{self.browser}浏览器驱动...")

            # 创建浏览器选项
            if self.browser == "chrome":
                options = ChromeOptions()
            elif self.browser == "edge":
                options = EdgeOptions()
            else:
                raise ValueError(f"不支持的浏览器类型: {self.browser}")

            if self.headless:
                if self.browser in ["chrome", "edge"]:
                    options.add_argument("--headless=new")
                logger.info("使用无头模式")

            # 基本设置
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--disable-extensions")
            options.add_argument("--disable-blink-features=AutomationControlled")

            # 排除自动化标识
            options.add_experimental_option(
                "excludeSwitches", ["enable-automation", "enable-logging"]
            )
            options.add_experimental_option("useAutomationExtension", False)

            # 优先尝试使用系统浏览器驱动
            try:
                logger.info(f"尝试使用系统{self.browser}Driver...")
                if self.browser == "chrome":
                    driver_path = self.find_chromedriver_path()
                    if driver_path:
                        service = ChromeService(driver_path)
                        return webdriver.Chrome(service=service, options=options)
                    else:
                        logger.info("未找到系统ChromeDriver，尝试使用webdriver-manager")
                elif self.browser == "edge":
                    # 查找EdgeDriver路径
                    edge_driver_path = shutil.which("msedgedriver") or shutil.which(
                        "edgedriver"
                    )
                    if edge_driver_path and os.path.exists(edge_driver_path):
                        service = EdgeService(edge_driver_path)
                        return webdriver.Edge(service=service, options=options)
                    else:
                        logger.info("未找到系统EdgeDriver，尝试使用webdriver-manager")
            except Exception as system_error:
                logger.warning(f"系统{self.browser}Driver失败: {system_error}")

            # 尝试使用webdriver-manager
            try:
                logger.info(
                    f"使用webdriver-manager自动下载兼容的{self.browser}Driver..."
                )
                if self.browser == "chrome":
                    service = ChromeService(ChromeDriverManager().install())
                    return webdriver.Chrome(service=service, options=options)
                elif self.browser == "edge":
                    service = EdgeService(EdgeChromiumDriverManager().install())
                    return webdriver.Edge(service=service, options=options)
            except Exception as wdm_error:
                logger.error(f"webdriver-manager失败: {wdm_error}")

            # 最后尝试不指定service
            try:
                logger.info(f"尝试使用默认{self.browser}Driver配置...")
                if self.browser == "chrome":
                    return webdriver.Chrome(options=options)
                elif self.browser == "edge":
                    return webdriver.Edge(options=options)
            except Exception as default_error:
                logger.error(f"默认配置也失败: {default_error}")
                raise RuntimeError(
                    f"无法初始化{self.browser}浏览器驱动: {default_error}"
                )

        except Exception as e:
            logger.error(f"设置浏览器驱动失败: {str(e)}")
            raise RuntimeError(f"无法初始化{self.browser}浏览器驱动: {e}")


@dataclass
class ArticleParser:
    """文章解析工具类
    
    Attributes:
        wait_time: 等待时间（秒）
    """
    
    wait_time: int = 10
    
    def extract_article_content(self, driver):
        """从浏览器页面提取文章内容
        
        Args:
            driver: 浏览器驱动对象
            
        Returns:
            ArticleData: 解析后的文章数据
        """
        try:
            # 获取页面源码
            page_source = driver.page_source
            soup = BeautifulSoup(page_source, "html.parser")

            # 获取文章标题
            title = "未知标题"
            if soup.find(id="activity-name"):
                title = soup.find(id="activity-name").get_text(strip=True)
            elif soup.find(class_="rich_media_title"):
                title = soup.find(class_="rich_media_title").get_text(strip=True)

            # 获取作者信息
            author = "未知作者"
            author_elements = soup.select(".rich_media_meta_text")
            if author_elements:
                author = author_elements[0].get_text(strip=True)

            # 获取发布时间
            publish_time = "未知时间"
            time_elements = soup.select(
                "#publish_time, .rich_media_meta_text:last-child"
            )
            if time_elements:
                publish_time = time_elements[0].get_text(strip=True)

            # 获取文章正文内容
            content_element = soup.find(id="js_content") or soup.find(
                class_="rich_media_content"
            )
            content_html = str(content_element) if content_element else ""
            content = (
                content_element.get_text(separator="\n", strip=True)
                if content_element
                else ""
            )

            # 提取图片信息
            images = []
            if content_element:
                img_elements = content_element.find_all("img")
                for i, img in enumerate(img_elements, 1):
                    img_url = img.get("data-src") or img.get("src")
                    if not img_url or img_url.startswith("data:"):
                        continue

                    # 处理相对URL
                    if img_url.startswith("//"):
                        img_url = "https:" + img_url
                    elif img_url.startswith("/"):
                        img_url = urljoin(driver.current_url, img_url)

                    alt_text = img.get("alt") or f"图片_{i}"
                    images.append(ImageInfo(index=i, url=img_url, alt=alt_text))

            return ArticleData(
                title=title,
                author=author,
                publish_time=publish_time,
                content_html=content_html,
                content=content,
                url=driver.current_url,
                crawl_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                images=images,
            )

        except Exception as e:
            logger.error(f"提取文章内容失败: {str(e)}", exc_info=True)
            return None


@dataclass
class ImageDownloader:
    """图片下载工具类"""

    session: requests.Session
    max_workers: int = 4

    def download_image(self, img_info, save_dir):
        """下载单张图片"""
        try:
            # 发送请求下载图片
            response = self.session.get(img_info.url, timeout=30, stream=True)
            response.raise_for_status()

            # 生成文件名
            filename = f"img_{img_info.index:03d}.png"
            filepath = os.path.join(save_dir, filename)

            # 保存图片
            with open(filepath, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            img_info.filename = filename
            img_info.local_path = filepath
            img_info.download_success = True
            logger.debug(f"图片下载成功: {filename}")

        except Exception as e:
            logger.error(f"下载图片失败 {img_info.url}: {str(e)}")
            img_info.download_success = False

    def download_all_images(self, article_data, save_dir):
        """下载所有图片"""
        if not article_data.images:
            return

        # 创建图片保存目录
        images_dir = os.path.join(save_dir, "images")
        os.makedirs(images_dir, exist_ok=True)

        logger.info(f"开始下载 {len(article_data.images)} 张图片...")

        # 使用线程池并行下载图片
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [
                executor.submit(self.download_image, img_info, images_dir)
                for img_info in article_data.images
            ]

            # 等待所有下载完成
            for future in futures:
                future.result()

        success_count = sum(1 for img in article_data.images if img.download_success)
        logger.info(f"图片下载完成: {success_count}/{len(article_data.images)} 张成功")


@dataclass
class ArticleSaver:
    """文章保存工具类
    
    Attributes:
        default_save_dir: 默认保存目录
        download_images: 是否下载图片
    """
    
    default_save_dir: Path = field(
        default_factory=lambda: Path(__file__).parent.parent.parent / "articles"
    )
    download_images: bool = True
    
    def save_article(
        self, 
        article_data: ArticleData, 
        save_dir: Optional[Path] = None, 
        custom_filename: Optional[str] = None
    ) -> bool:
        """保存文章到文件
        
        Args:
            article_data: 文章数据对象
            save_dir: 保存目录，默认为default_save_dir
            custom_filename: 自定义文件名，默认为None
            
        Returns:
            bool: 保存是否成功
        """
        if not article_data:
            logger.warning("没有文章数据可保存")
            return False

        try:
            # 创建保存目录
            current_save_dir = save_dir or self.default_save_dir
            current_save_dir = Path(current_save_dir)
            current_save_dir.mkdir(exist_ok=True)

            # 生成安全的文件名
            if custom_filename:
                safe_filename = custom_filename
            else:
                safe_title = re.sub(r'[<>:"/\\|?*]', "_", article_data.title)[:50]
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                safe_filename = f"{safe_title}_{timestamp}"

            # 创建文章专用目录
            article_dir = current_save_dir / safe_filename
            article_dir.mkdir(exist_ok=True)

            # 保存JSON格式
            json_file = article_dir / f"{safe_filename}.json"
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(asdict(article_data), f, ensure_ascii=False, indent=2)
            logger.info(f"JSON文件已保存: {json_file}")

            # 保存TXT格式
            txt_file = article_dir / f"{safe_filename}.txt"
            with open(txt_file, "w", encoding="utf-8") as f:
                f.write(f"标题: {article_data.title}\n")
                f.write(f"作者: {article_data.author}\n")
                f.write(f"发布时间: {article_data.publish_time}\n")
                f.write(f"抓取时间: {article_data.crawl_time}\n")
                f.write(f"链接: {article_data.url}\n")
                f.write("\n" + "=" * 80 + "\n\n")
                f.write(article_data.content)

                # 添加图片信息
                if article_data.images:
                    f.write("\n\n" + "=" * 80 + "\n")
                    f.write("图片信息:\n")
                    for img in article_data.images:
                        f.write(f"\n图片 {img.index}: {img.alt}\n")
                        f.write(f"原始URL: {img.url}\n")
                        f.write(
                            f"状态: {'下载成功' if img.download_success else '下载失败'}\n"
                        )
            logger.info(f"TXT文件已保存: {txt_file}")

            return True

        except Exception as e:
            logger.error(f"保存文件失败: {str(e)}", exc_info=True)
            return False


@dataclass
class SessionManager:
    """会话管理工具类
    
    Attributes:
        user_agent: User-Agent字符串
        accept: Accept头
        accept_language: Accept-Language头
        pool_connections: 连接池连接数
        pool_maxsize: 连接池最大大小
        max_retries: 最大重试次数
    """
    
    user_agent: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 "
        "Safari/537.36"
    )
    accept: str = (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/webp,*/*;q=0.8"
    )
    accept_language: str = "zh-CN,zh;q=0.9,en;q=0.8"
    pool_connections: int = 10
    pool_maxsize: int = 10
    max_retries: int = 3
    
    def create_session(self) -> requests.Session:
        """创建并配置requests会话
        
        Returns:
            requests.Session: 配置好的会话对象
        """
        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": self.user_agent,
                "Accept": self.accept,
                "Accept-Language": self.accept_language,
            }
        )
        # 优化连接池
        http_adapter = requests.adapters.HTTPAdapter(
            pool_connections=self.pool_connections, 
            pool_maxsize=self.pool_maxsize, 
            max_retries=self.max_retries
        )
        session.mount("http://", http_adapter)
        session.mount("https://", http_adapter)
        return session


@dataclass
class DependencyChecker:
    """依赖检查工具类"""
    
    @staticmethod
    def check_dependencies() -> bool:
        """检查依赖包是否安装
        
        Returns:
            bool: 所有依赖是否已安装
        """
        required_packages: Dict[str, str] = {
            "selenium": "selenium",
            "beautifulsoup4": "bs4",
            "requests": "requests",
            "webdriver_manager": "webdriver_manager",
        }

        missing: List[str] = []
        for pkg, import_name in required_packages.items():
            try:
                __import__(import_name)
                logger.info(f"✅ {pkg} 已安装")
            except ImportError:
                missing.append(pkg)
                logger.error(f"❌ {pkg} 未安装")

        if missing:
            logger.error(f"缺少依赖: {', '.join(missing)}")
            logger.error(
                "请运行: pip install selenium beautifulsoup4 requests webdriver-manager"
            )
            return False

        logger.info("✅ 所有依赖已安装")
        return True
