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

    def __init__(self, url: str, message: str = "无效的微信文章URL") -> None:
        self.url: str = url
        self.message: str = message
        super().__init__(f"{message}: {url}")


class CrawlFailedError(WeixinSpiderError):
    """爬取失败异常"""

    def __init__(self, url: str, reason: str, attempt: int = 1) -> None:
        self.url: str = url
        self.reason: str = reason
        self.attempt: int = attempt
        super().__init__(f"第{attempt}次爬取{url}失败: {reason}")


class DriverInitializationError(WeixinSpiderError):
    """浏览器驱动初始化失败异常"""

    def __init__(self, browser: str, reason: str) -> None:
        self.browser: str = browser
        self.reason: str = reason
        super().__init__(f"初始化{browser}浏览器驱动失败: {reason}")


class ImageDownloadError(WeixinSpiderError):
    """图片下载失败异常"""

    def __init__(self, url: str, reason: str) -> None:
        self.url: str = url
        self.reason: str = reason
        super().__init__(f"下载图片{url}失败: {reason}")


class FileSaveError(WeixinSpiderError):
    """文件保存失败异常"""

    def __init__(self, filename: str, reason: str) -> None:
        self.filename: str = filename
        self.reason: str = reason
        super().__init__(f"保存文件{filename}失败: {reason}")


class ContentExtractionError(WeixinSpiderError):
    """内容提取失败异常"""

    def __init__(self, url: str, reason: str) -> None:
        self.url: str = url
        self.reason: str = reason
        super().__init__(f"从{url}提取内容失败: {reason}")


class InvalidParameterError(WeixinSpiderError):
    """无效参数异常"""

    def __init__(self, parameter_name: str, reason: str) -> None:
        self.parameter_name: str = parameter_name
        self.reason: str = reason
        super().__init__(f"无效参数 {parameter_name}: {reason}")


class TimeoutError(WeixinSpiderError):
    """超时异常"""

    def __init__(self, operation: str, wait_time: int) -> None:
        self.operation: str = operation
        self.wait_time: int = wait_time
        super().__init__(f"{operation} 超时，已等待 {wait_time} 秒")


class SessionError(WeixinSpiderError):
    """会话错误异常"""

    def __init__(self, reason: str) -> None:
        self.reason: str = reason
        super().__init__(f"会话错误: {reason}")


class CacheError(WeixinSpiderError):
    """缓存错误异常"""

    def __init__(self, operation: str, reason: str) -> None:
        self.operation: str = operation
        self.reason: str = reason
        super().__init__(f"缓存 {operation} 失败: {reason}")


class AnalysisError(WeixinSpiderError):
    """分析错误异常"""

    def __init__(self, analysis_type: str, reason: str) -> None:
        self.analysis_type: str = analysis_type
        self.reason: str = reason
        super().__init__(f"{analysis_type} 分析失败: {reason}")
