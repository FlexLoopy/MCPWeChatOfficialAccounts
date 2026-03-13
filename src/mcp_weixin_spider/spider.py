#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信公众号文章爬虫核心模块
支持文章内容抓取、图片下载、多种格式保存
"""

import requests
import threading
import time
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
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
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# 导入自定义异常类
from .exceptions import (
    InvalidParameterError,
    TimeoutError,
    SessionError,
    CacheError,
    AnalysisError,
    InvalidURLError,
    CrawlFailedError,
    DriverInitializationError,
    ImageDownloadError,
    FileSaveError,
    ContentExtractionError,
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
    """微信公众号爬虫类"""

    # 初始化参数
    headless: bool = True
    wait_time: int = 10
    download_images: bool = True
    max_workers: int = 4
    browser: str = "edge"
    skip_browser_check: bool = False
    save_dir: Path = field(
        default_factory=lambda: Path(__file__).parent.parent.parent / "articles"
    )
    config: Optional["SpiderConfig"] = None  # 添加配置参数

    # 实例变量
    driver: Optional[WebDriver] = field(default=None, init=False)
    session: Optional[requests.Session] = field(default=None, init=False)

    def __post_init__(self):
        """执行初始化逻辑"""
        # 如果提供了配置对象，则使用配置对象中的值
        if self.config:
            from .config import SpiderConfig

            self.headless = self.config.headless
            self.wait_time = self.config.wait_time
            self.download_images = self.config.download_images
            self.browser = self.config.browser
            # 更新save_dir，使用配置中的articles_dir
            self.save_dir = Path(self.config.articles_dir)
            # 检查配置对象是否有skip_browser_check属性
            if hasattr(self.config, 'skip_browser_check'):
                self.skip_browser_check = self.config.skip_browser_check

        self.browser = self.browser.lower()
        self.session = SessionManager.create_session()
        driver_manager = BrowserDriverManager(
            self.browser, 
            self.headless, 
            self.skip_browser_check
        )
        self.driver = driver_manager.create_driver()
        logger.info("浏览器驱动初始化成功")

    def crawl_article_by_url(
        self, url: str, retry_times: int = 2
    ) -> Optional[ArticleData]:
        """通过URL抓取文章内容

        Args:
            url: 微信公众号文章URL
            retry_times: 重试次数

        Returns:
            ArticleData: 解析后的文章数据

        Raises:
            ValueError: 无效的URL
            Exception: 所有重试都失败了
        """
        # 输入参数验证
        if not isinstance(url, str):
            raise InvalidParameterError("url", "必须是字符串类型")

        if not url.strip():
            raise InvalidParameterError("url", "不能为空")

        # URL验证
        url = url.strip()
        if not re.match(r"^https?://", url):
            url = "https://" + url
            logger.info(f"自动补全URL协议: {url}")

        # 验证是否为微信公众号文章URL
        if "mp.weixin.qq.com" not in url:
            logger.warning(f"URL {url} 可能不是微信公众号文章URL，将尝试抓取")

        for attempt in range(retry_times):
            try:
                logger.info(
                    f"[{self.browser}] 第 {attempt + 1}/{retry_times} 次尝试访问文章: {url}"
                )

                self.driver.get(url)
                wait = WebDriverWait(self.driver, self.wait_time)

                # 等待文章标题加载
                try:
                    logger.debug("等待文章标题元素加载...")
                    wait.until(EC.presence_of_element_located((By.ID, "activity-name")))
                    logger.debug("找到id为activity-name的标题元素")
                except Exception as e:
                    logger.debug(
                        f"未找到activity-name元素: {e}，尝试使用rich_media_title类选择器"
                    )
                    wait.until(
                        EC.presence_of_element_located(
                            (By.CSS_SELECTOR, ".rich_media_title")
                        )
                    )
                    logger.debug("找到rich_media_title类的标题元素")

                # 滚动页面确保内容完全加载
                logger.debug("滚动页面到底部以确保内容完全加载")
                self.driver.execute_script(
                    "window.scrollTo(0, document.body.scrollHeight);"
                )

                # 使用显式等待替代硬编码sleep，等待页面底部元素加载
                try:
                    logger.debug("等待文章正文内容加载完成...")
                    # 等待页面内容加载完成（等待正文区域可见）
                    wait.until(EC.presence_of_element_located((By.ID, "js_content")))
                    logger.debug("找到id为js_content的正文元素")
                except Exception as e:
                    logger.debug(
                        f"未找到js_content元素: {e}，尝试使用rich_media_content类选择器"
                    )
                    wait.until(
                        EC.presence_of_element_located(
                            (By.CSS_SELECTOR, ".rich_media_content")
                        )
                    )
                    logger.debug("找到rich_media_content类的正文元素")

                # 提取文章信息
                logger.info("开始提取文章内容...")
                article_data = ArticleParser.extract_article_content(self.driver)

                if article_data:
                    logger.info(f"成功提取文章: {article_data.title}")
                    logger.debug(f"文章包含 {len(article_data.images)} 张图片")

                    # 下载图片
                    if self.download_images:
                        logger.info(f"开始下载 {len(article_data.images)} 张图片...")
                        image_downloader = ImageDownloader(
                            self.session, self.max_workers
                        )
                        image_downloader.download_all_images(
                            article_data, self.save_dir
                        )
                else:
                    logger.warning("未提取到文章数据")

                return article_data

            except TimeoutException as e:
                logger.error(f"[{self.browser}] 第 {attempt + 1} 次尝试超时: {str(e)}")
                if attempt == retry_times - 1:
                    raise TimeoutError(f"爬取文章 {url}", self.wait_time) from e

            except WebDriverException as e:
                logger.error(
                    f"[{self.browser}] 第 {attempt + 1} 次尝试遇到浏览器错误: {str(e)}"
                )
                if attempt == retry_times - 1:
                    raise CrawlFailedError(
                        url, f"浏览器错误: {str(e)}", attempt + 1
                    ) from e

            except Exception as e:
                logger.error(f"[{self.browser}] 第 {attempt + 1} 次尝试失败: {str(e)}")
                logger.debug(f"详细错误信息: {traceback.format_exc()}")
                if attempt == retry_times - 1:
                    raise CrawlFailedError(url, str(e), attempt + 1) from e

            # 使用指数退避策略，避免固定等待
            backoff_time = 2 ** (attempt + 1)
            logger.info(
                f"[{self.browser}] 等待 {backoff_time} 秒后进行第 {attempt + 2} 次重试..."
            )
            time.sleep(backoff_time)

        raise Exception("所有重试都失败了")

    def save_article(
        self, article_data: Optional[ArticleData], custom_filename: Optional[str] = None
    ) -> bool:
        """保存文章到文件"""
        if not article_data:
            logger.warning("没有文章数据可保存")
            return False

        return ArticleSaver.save_article(
            article_data, self.save_dir, custom_filename, self.download_images
        )

    def close(self) -> None:
        """关闭浏览器和会话"""
        logger.info("正在关闭浏览器和会话...")
        if self.driver:
            self.driver.quit()
            logger.info("浏览器已关闭")

        # 关闭会话连接池
        if hasattr(self, "session"):
            self.session.close()
            logger.info("会话已关闭")


@dataclass
class BrowserDriverManager:
    """浏览器驱动管理类"""

    browser: str = "edge"
    headless: bool = True
    skip_browser_check: bool = False
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

    def _check_browser_installed(self):
        """检查浏览器是否已安装"""
        if self.browser == "chrome":
            # 检查Chrome是否安装
            chrome_paths = []
            
            # Windows路径 - 增加更多可能的安装位置
            if os.name == "nt":
                chrome_paths.extend([
                    "C:/Program Files/Google/Chrome/Application/chrome.exe",
                    "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
                    # 用户特定安装路径
                    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google/Chrome/Application/chrome.exe"),
                    os.path.join(os.environ.get("PROGRAMFILES", ""), "Google/Chrome/Application/chrome.exe"),
                    os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "Google/Chrome/Application/chrome.exe"),
                    # 其他可能的路径
                    "D:/Program Files/Google/Chrome/Application/chrome.exe",
                    "D:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
                ])
            # macOS路径
            elif sys.platform == "darwin":
                chrome_paths.append("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
            # Linux路径
            else:
                chrome_paths.extend([
                    "/usr/bin/google-chrome",
                    "/usr/bin/chromium",
                    "/usr/bin/chromium-browser",
                    "/usr/local/bin/google-chrome",
                    "/usr/local/bin/chromium",
                    "/opt/google/chrome/google-chrome",
                ])
            
            # 也使用which命令查找
            chrome_paths.append(shutil.which("chrome"))
            chrome_paths.append(shutil.which("google-chrome"))
            chrome_paths.append(shutil.which("chromium"))
            chrome_paths.append(shutil.which("chromium-browser"))
            chrome_paths.append(shutil.which("google-chrome-stable"))
            
            # 去重并过滤掉None值
            unique_paths = list(filter(None, set(chrome_paths)))
            
            for path in unique_paths:
                if os.path.exists(path):
                    logger.info(f"找到Chrome浏览器: {path}")
                    return True
            
            logger.error("未找到Chrome浏览器，请确保已安装Chrome")
            logger.error(f"搜索的路径: {unique_paths}")
            logger.error("下载链接: https://www.google.com/chrome/")
            return False
        
        elif self.browser == "edge":
            # 检查Edge是否安装
            edge_paths = [
                # Windows路径
                "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
                "C:/Program Files/Microsoft/Edge/Application/msedge.exe",
                # macOS路径
                "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
                # Linux路径
                "/usr/bin/msedge",
                "/usr/bin/microsoft-edge"
            ]
            
            # 也使用which命令查找
            edge_paths.append(shutil.which("msedge"))
            edge_paths.append(shutil.which("microsoft-edge"))
            
            for path in edge_paths:
                if path and os.path.exists(path):
                    logger.info(f"找到Edge浏览器: {path}")
                    return True
            
            logger.error("未找到Edge浏览器，请确保已安装Edge")
            logger.error("下载链接: https://www.microsoft.com/edge/")
            return False
        
        return True
    
    def create_driver(self):
        """创建并返回浏览器驱动"""
        try:
            logger.info(f"正在设置{self.browser}浏览器驱动...")
            
            # 检查浏览器是否已安装
            if not self.skip_browser_check and not self._check_browser_installed():
                raise DriverInitializationError(
                    self.browser, 
                    f"{self.browser}浏览器未安装，请先安装浏览器"
                )

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

            # 驱动创建策略列表，按优先级排序
            driver_creators = [
                self._create_driver_from_system,
                self._create_driver_from_webdriver_manager,
                self._create_driver_default,
            ]

            for creator in driver_creators:
                try:
                    driver = creator(options)
                    if driver:
                        return driver
                except Exception as e:
                    logger.warning(f"{creator.__name__} 失败: {e}")
                    # 如果是Chrome二进制文件未找到错误，提供更详细的错误信息
                    if "cannot find Chrome binary" in str(e):
                        logger.error("错误：无法找到Chrome二进制文件")
                        logger.error("请确保Chrome已正确安装，并添加到系统PATH中")
                        logger.error("或者尝试使用Edge浏览器，运行时添加参数：--browser edge")

            # 所有策略都失败
            raise DriverInitializationError(self.browser, "所有驱动创建策略都失败")

        except DriverInitializationError:
            # 已经是DriverInitializationError，直接重新抛出
            raise
        except Exception as e:
            logger.error(f"设置浏览器驱动失败: {str(e)}")
            raise DriverInitializationError(self.browser, str(e)) from e

    def _create_driver_from_system(self, options):
        """尝试使用系统浏览器驱动"""
        logger.info(f"尝试使用系统{self.browser}Driver...")

        if self.browser == "chrome":
            driver_path = self.find_chromedriver_path()
            if driver_path:
                service = ChromeService(driver_path)
                return webdriver.Chrome(service=service, options=options)
            logger.info("未找到系统ChromeDriver")
            return None
        elif self.browser == "edge":
            # 查找EdgeDriver路径
            edge_driver_path = shutil.which("msedgedriver") or shutil.which(
                "edgedriver"
            )
            if edge_driver_path and os.path.exists(edge_driver_path):
                service = EdgeService(edge_driver_path)
                return webdriver.Edge(service=service, options=options)
            logger.info("未找到系统EdgeDriver")
            return None
        return None

    def _create_driver_from_webdriver_manager(self, options):
        """尝试使用webdriver-manager创建驱动"""
        logger.info(f"使用webdriver-manager自动下载兼容的{self.browser}Driver...")

        if self.browser == "chrome":
            service = ChromeService(ChromeDriverManager().install())
            return webdriver.Chrome(service=service, options=options)
        elif self.browser == "edge":
            service = EdgeService(EdgeChromiumDriverManager().install())
            return webdriver.Edge(service=service, options=options)
        return None

    def _create_driver_default(self, options):
        """尝试使用默认配置创建驱动"""
        logger.info(f"尝试使用默认{self.browser}Driver配置...")

        if self.browser == "chrome":
            return webdriver.Chrome(options=options)
        elif self.browser == "edge":
            return webdriver.Edge(options=options)
        return None


@dataclass
class ArticleParser:
    """文章解析工具类

    Attributes:
        wait_time: 等待时间（秒）
    """

    wait_time: int = 10

    @staticmethod
    def extract_article_content(driver):
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
    _executor: Optional[ThreadPoolExecutor] = field(
        default=None, init=False, repr=False
    )

    def __post_init__(self):
        """初始化线程池"""
        self._executor = ThreadPoolExecutor(max_workers=self.max_workers)

    def __del__(self):
        """销毁时关闭线程池"""
        if self._executor:
            self._executor.shutdown(wait=False)

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

        # 使用复用的线程池并行下载图片
        futures = [
            self._executor.submit(self.download_image, img_info, images_dir)
            for img_info in article_data.images
        ]

        # 等待所有下载完成
        for future in as_completed(futures):
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

    @staticmethod
    def save_article(
        article_data, save_dir, custom_filename=None, download_images=True
    ):
        """保存文章到文件

        Args:
            article_data: 文章数据对象
            save_dir: 保存目录，默认为default_save_dir
            custom_filename: 自定义文件名，默认为None
            download_images: 是否下载图片

        Returns:
            bool: 保存是否成功
        """
        if not article_data:
            logger.warning("没有文章数据可保存")
            return False

        try:
            # 创建保存目录
            current_save_dir = Path(
                save_dir or Path(__file__).parent.parent.parent / "articles"
            )
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
        timeout: 请求超时时间（秒）
    """

    user_agent: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 "
        "Safari/537.36"
    )
    accept: str = (
        "text/html,application/xhtml+xml,application/xml;q=0.9," "image/webp,*/*;q=0.8"
    )
    accept_language: str = "zh-CN,zh;q=0.9,en;q=0.8"
    pool_connections: int = 10
    pool_maxsize: int = 10
    max_retries: int = 3
    timeout: float = 30.0  # 添加超时设置

    @classmethod
    def create_session(cls):
        """创建并配置requests会话

        Returns:
            requests.Session: 配置好的会话对象
        """
        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": cls.user_agent,
                "Accept": cls.accept,
                "Accept-Language": cls.accept_language,
            }
        )
        # 设置默认超时时间
        session.timeout = cls.timeout
        # 优化连接池
        http_adapter = requests.adapters.HTTPAdapter(
            pool_connections=cls.pool_connections,
            pool_maxsize=cls.pool_maxsize,
            max_retries=cls.max_retries,
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
