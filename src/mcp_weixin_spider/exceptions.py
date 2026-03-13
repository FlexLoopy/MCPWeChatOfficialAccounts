#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信爬虫自定义异常类
"""

from dataclasses import dataclass


class WeixinSpiderError(Exception):
    """微信爬虫自定义异常基类"""
    pass


@dataclass
class InvalidURLError(WeixinSpiderError):
    """无效URL异常"""
    url: str
    message: str = "无效的微信文章URL"
    
    def __post_init__(self):
        super().__init__(f"{self.message}: {self.url}")


@dataclass
class CrawlFailedError(WeixinSpiderError):
    """爬取失败异常"""
    url: str
    reason: str
    attempt: int = 1
    
    def __post_init__(self):
        super().__init__(f"第{self.attempt}次爬取{self.url}失败: {self.reason}")


@dataclass
class DriverInitializationError(WeixinSpiderError):
    """浏览器驱动初始化失败异常"""
    browser: str
    reason: str
    
    def __post_init__(self):
        super().__init__(f"初始化{self.browser}浏览器驱动失败: {self.reason}")


@dataclass
class ImageDownloadError(WeixinSpiderError):
    """图片下载失败异常"""
    url: str
    reason: str
    
    def __post_init__(self):
        super().__init__(f"下载图片{self.url}失败: {self.reason}")


@dataclass
class FileSaveError(WeixinSpiderError):
    """文件保存失败异常"""
    filename: str
    reason: str
    
    def __post_init__(self):
        super().__init__(f"保存文件{self.filename}失败: {self.reason}")


@dataclass
class ContentExtractionError(WeixinSpiderError):
    """内容提取失败异常"""
    url: str
    reason: str
    
    def __post_init__(self):
        super().__init__(f"从{self.url}提取内容失败: {self.reason}")


@dataclass
class InvalidParameterError(WeixinSpiderError):
    """无效参数异常"""
    parameter_name: str
    reason: str
    
    def __post_init__(self):
        super().__init__(f"无效参数 {self.parameter_name}: {self.reason}")


@dataclass
class TimeoutError(WeixinSpiderError):
    """超时异常"""
    operation: str
    wait_time: int
    
    def __post_init__(self):
        super().__init__(f"{self.operation} 超时，已等待 {self.wait_time} 秒")


@dataclass
class SessionError(WeixinSpiderError):
    """会话错误异常"""
    reason: str
    
    def __post_init__(self):
        super().__init__(f"会话错误: {self.reason}")


@dataclass
class CacheError(WeixinSpiderError):
    """缓存错误异常"""
    operation: str
    reason: str
    
    def __post_init__(self):
        super().__init__(f"缓存 {self.operation} 失败: {self.reason}")


@dataclass
class AnalysisError(WeixinSpiderError):
    """分析错误异常"""
    analysis_type: str
    reason: str
    
    def __post_init__(self):
        super().__init__(f"{self.analysis_type} 分析失败: {self.reason}")
