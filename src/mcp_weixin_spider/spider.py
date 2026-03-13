#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信公众号文章爬虫核心模块
支持文章内容抓取、图片下载、多种格式保存
"""

import time
import requests
import threading
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.edge.service import Service as EdgeService
from webdriver_manager.microsoft import EdgeChromiumDriverManager
from bs4 import BeautifulSoup
import json
import os
import logging
from datetime import datetime
import re
from urllib.parse import urljoin, urlparse
import hashlib
from pathlib import Path
import sys
import shutil
import subprocess
import base64
from urllib.parse import unquote
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, asdict
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ImageInfo:
    """图片信息数据类"""
    index: int
    url: str
    alt: str
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
class WeixinSpiderWithImages:
    """微信公众号文章爬虫类，支持多浏览器和图片下载"""
    # 类级别锁，避免在初始化完成前被调用
    _chrome_driver_lock = threading.Lock()
    
    # 初始化参数
    headless: bool = True
    wait_time: int = 10
    download_images: bool = True
    max_workers: int = 4
    browser: str = 'chrome'
    
    # 实例变量
    driver: Optional[webdriver.Chrome] = field(default=None, init=False)
    session: requests.Session = field(default_factory=requests.Session, init=False)
    _chrome_driver_path: Optional[str] = field(default=None, init=False)
    
    def __post_init__(self):
        """执行复杂的初始化逻辑"""
        self.browser = self.browser.lower()
        self.setup_session()
        self.setup_driver(self.headless)
        
    def setup_session(self):
        """设置requests会话，优化请求头和连接池"""
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        # 优化连接池
        self.session.mount('http://', requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=3))
        self.session.mount('https://', requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=3))
        
    def find_chromedriver_path(self):
        """查找系统中的ChromeDriver路径，使用缓存避免重复查找"""
        with self._chrome_driver_lock:
            if self._chrome_driver_path:
                return self._chrome_driver_path
            
            # 常见的ChromeDriver路径
            possible_paths = [
                '/usr/local/bin/chromedriver',
                '/usr/bin/chromedriver',
                '/opt/homebrew/bin/chromedriver',
                shutil.which('chromedriver'),
            ]
            
            for path in possible_paths:
                if path and os.path.exists(path) and os.access(path, os.X_OK):
                    logger.info(f"找到ChromeDriver: {path}")
                    self._chrome_driver_path = path
                    return path
            
            self._chrome_driver_path = None
            return None
        
    def setup_driver(self, headless=True):
        """设置浏览器驱动，优化启动参数"""
        try:
            logger.info(f"正在设置{self.browser}浏览器驱动...")
            
            # 创建浏览器选项
            if self.browser == 'chrome':
                options = ChromeOptions()
            elif self.browser == 'edge':
                options = EdgeOptions()
            else:
                raise ValueError(f"不支持的浏览器类型: {self.browser}")
            
            if headless:
                if self.browser == 'chrome':
                    options.add_argument('--headless=new')  # Chrome新的无头模式
                elif self.browser == 'edge':
                    options.add_argument('--headless=new')  # Edge新的无头模式
                logger.info("使用无头模式")
            
            # 基本设置 - 针对版本兼容性和渲染器连接问题优化
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--disable-extensions')
            options.add_argument('--disable-logging')
            options.add_argument('--disable-web-security')
            options.add_argument('--allow-running-insecure-content')
            options.add_argument('--disable-features=VizDisplayCompositor')
            options.add_argument('--disable-features=TranslateUI')
            options.add_argument('--disable-background-timer-throttling')
            options.add_argument('--disable-backgrounding-occluded-windows')
            options.add_argument('--disable-renderer-backgrounding')
            options.add_argument('--disable-ipc-flooding-protection')
            options.add_argument('--disable-hang-monitor')
            options.add_argument('--disable-client-side-phishing-detection')
            options.add_argument('--disable-popup-blocking')
            options.add_argument('--disable-prompt-on-repost')
            options.add_argument('--disable-sync')
            options.add_argument('--no-first-run')
            options.add_argument('--disable-default-apps')
            options.add_argument('--disable-component-update')
            options.add_argument('--disable-background-networking')
            options.add_argument('--disable-component-extensions-with-background-pages')
            options.add_argument('--disable-blink-features=AutomationControlled')
            
            # 解决渲染器连接问题的关键参数
            options.add_argument('--single-process')  # 使用单进程模式
            options.add_argument('--disable-gpu-sandbox')
            options.add_argument('--disable-software-rasterizer')
            options.add_argument('--remote-debugging-port=0')  # 禁用远程调试端口
            options.add_argument('--disable-dev-tools')
            
            # 内存和性能优化
            options.add_argument('--memory-pressure-off')
            options.add_argument('--max_old_space_size=4096')
            options.add_argument('--disable-features=site-per-process')
            options.add_argument('--enable-features=OverlayScrollbar')
            
            # 设置用户代理 - 更新到最新版本
            options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36')
            
            # 排除自动化标识
            options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
            options.add_experimental_option('useAutomationExtension', False)
            
            # 设置prefs以避免各种弹窗
            prefs = {
                "profile.default_content_setting_values": {
                    "notifications": 2,
                    "geolocation": 2,
                    "media_stream": 2,
                },
                "profile.default_content_settings.popups": 0,
                "profile.managed_default_content_settings.images": 2 if not self.download_images else 1,
                "profile.managed_default_content_settings.stylesheets": 1,
                "profile.managed_default_content_settings.javascript": 1,
                "profile.managed_default_content_settings.plugins": 1,
                "profile.managed_default_content_settings.activex_objects": 1,
            }
            options.add_experimental_option("prefs", prefs)
            
            # 优先尝试使用系统浏览器驱动
            try:
                logger.info(f"尝试使用系统{self.browser}Driver...")
                if self.browser == 'chrome':
                    driver_path = self.find_chromedriver_path()
                    if driver_path:
                        service = ChromeService(driver_path)
                        self.driver = webdriver.Chrome(service=service, options=options)
                        logger.info("使用系统ChromeDriver成功初始化")
                        return
                    else:
                        logger.info("未找到系统ChromeDriver，尝试使用webdriver-manager")
                elif self.browser == 'edge':
                    # 查找EdgeDriver路径
                    edge_driver_path = shutil.which('msedgedriver') or shutil.which('edgedriver')
                    if edge_driver_path and os.path.exists(edge_driver_path):
                        service = EdgeService(edge_driver_path)
                        self.driver = webdriver.Edge(service=service, options=options)
                        logger.info("使用系统EdgeDriver成功初始化")
                        return
                    else:
                        logger.info("未找到系统EdgeDriver，尝试使用webdriver-manager")
            except Exception as system_error:
                logger.warning(f"系统{self.browser}Driver失败: {system_error}")
                
            # 尝试使用webdriver-manager
            try:
                logger.info(f"使用webdriver-manager自动下载兼容的{self.browser}Driver...")
                if self.browser == 'chrome':
                    service = ChromeService(ChromeDriverManager().install())
                    self.driver = webdriver.Chrome(service=service, options=options)
                    logger.info("使用webdriver-manager成功初始化ChromeDriver")
                    return
                elif self.browser == 'edge':
                    service = EdgeService(EdgeChromiumDriverManager().install())
                    self.driver = webdriver.Edge(service=service, options=options)
                    logger.info("使用webdriver-manager成功初始化EdgeDriver")
                    return
            except Exception as wdm_error:
                logger.error(f"webdriver-manager失败: {wdm_error}")
                
            # 最后尝试不指定service
            try:
                logger.info(f"尝试使用默认{self.browser}Driver配置...")
                if self.browser == 'chrome':
                    self.driver = webdriver.Chrome(options=options)
                    logger.info("使用默认配置成功初始化ChromeDriver")
                    return
                elif self.browser == 'edge':
                    self.driver = webdriver.Edge(options=options)
                    logger.info("使用默认配置成功初始化EdgeDriver")
                    return
            except Exception as default_error:
                logger.error(f"默认配置也失败: {default_error}")
                raise RuntimeError(f"无法初始化{self.browser}浏览器驱动: {default_error}")
            
        except Exception as e:
            logger.error(f"设置浏览器驱动失败: {str(e)}")
            # 提供备用方案
            self.driver = None
            raise RuntimeError(f"无法初始化{self.browser}浏览器驱动: {e}")