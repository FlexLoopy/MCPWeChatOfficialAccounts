#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信爬虫自定义异常类
"""


class WeixinSpiderError(Exception):
    """微信爬虫自定义异常基类"""
    pass


class InvalidURLError(WeixinSpiderError):
    """无效URL异常"""
    def __init__(self, url, message="无效的微信文章URL"):
        self.url = url
        self.message = message
        super().__init__(f"{message}: {url}")


class CrawlFailedError(WeixinSpiderError):
    """爬取失败异常"""
    def __init__(self, url, reason, attempt=1):
        self.url = url
        self.reason = reason
        self.attempt = attempt
        super().__init__(f"第{attempt}次爬取{url}失败: {reason}")


class DriverInitializationError(WeixinSpiderError):
    """浏览器驱动初始化失败异常"""
    def __init__(self, browser, reason):
        self.browser = browser
        self.reason = reason
        super().__init__(f"初始化{browser}浏览器驱动失败: {reason}")


class ImageDownloadError(WeixinSpiderError):
    """图片下载失败异常"""
    def __init__(self, url, reason):
        self.url = url
        self.reason = reason
        super().__init__(f"下载图片{url}失败: {reason}")


class FileSaveError(WeixinSpiderError):
    """文件保存失败异常"""
    def __init__(self, filename, reason):
        self.filename = filename
        self.reason = reason
        super().__init__(f"保存文件{filename}失败: {reason}")


class ContentExtractionError(WeixinSpiderError):
    """内容提取失败异常"""
    def __init__(self, url, reason):
        self.url = url
        self.reason = reason
        super().__init__(f"从{url}提取内容失败: {reason}")