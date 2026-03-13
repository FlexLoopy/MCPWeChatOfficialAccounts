#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理模块
使用dataclass和toml进行配置管理
"""

import os
import toml
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, Dict, Any


@dataclass
class SpiderConfig:
    """爬虫相关配置"""
    headless: bool = True
    wait_time: int = 10
    download_images: bool = True
    browser: str = "chrome"  # 浏览器类型，支持'chrome'和'edge'
    chrome_driver_path: Optional[str] = None
    edge_driver_path: Optional[str] = None
    articles_dir: str = "articles"
    images_dir: str = "images"
    
    def validate(self) -> Dict[str, str]:
        """验证配置有效性"""
        errors = {}
        if self.wait_time <= 0:
            errors["wait_time"] = "等待时间必须大于0"
        if not self.articles_dir:
            errors["articles_dir"] = "文章保存目录不能为空"
        if not self.images_dir:
            errors["images_dir"] = "图片保存目录不能为空"
        if self.browser not in ["chrome", "edge"]:
            errors["browser"] = "浏览器类型必须是'chrome'或'edge'"
        return errors


@dataclass
class MCPConfig:
    """MCP相关配置"""
    server_name: str = "mcp-weixin-spider"
    transport: str = "stdio"
    debug: bool = False
    
    def validate(self) -> Dict[str, str]:
        """验证配置有效性"""
        errors = {}
        if not self.server_name:
            errors["server_name"] = "服务器名称不能为空"
        if self.transport not in ["stdio", "tcp"]:
            errors["transport"] = "传输方式必须是stdio或tcp"
        return errors


@dataclass
class LogConfig:
    """日志相关配置"""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file: Optional[str] = None
    
    def validate(self) -> Dict[str, str]:
        """验证配置有效性"""
        errors = {}
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.level.upper() not in valid_levels:
            errors["level"] = f"日志级别必须是{', '.join(valid_levels)}之一"
        return errors


@dataclass
class Config:
    """主配置类"""
    spider: SpiderConfig = field(default_factory=SpiderConfig)
    mcp: MCPConfig = field(default_factory=MCPConfig)
    log: LogConfig = field(default_factory=LogConfig)
    
    def validate(self) -> Dict[str, str]:
        """验证所有配置有效性"""
        errors = {}
        errors.update(self.spider.validate())
        errors.update(self.mcp.validate())
        errors.update(self.log.validate())
        return errors
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return asdict(self)


class ConfigManager:
    """配置管理类"""
    
    # 环境变量映射关系
    ENV_MAPPINGS = {
        # Spider配置
        "HEADLESS": ("spider", "headless", bool),
        "DOWNLOAD_IMAGES": ("spider", "download_images", bool),
        "WAIT_TIME": ("spider", "wait_time", int),
        "BROWSER": ("spider", "browser", str),
        "CHROME_DRIVER_PATH": ("spider", "chrome_driver_path", str),
        "EDGE_DRIVER_PATH": ("spider", "edge_driver_path", str),
        "ARTICLES_DIR": ("spider", "articles_dir", str),
        "IMAGES_DIR": ("spider", "images_dir", str),
        # MCP配置
        "MCP_SERVER_NAME": ("mcp", "server_name", str),
        "MCP_TRANSPORT": ("mcp", "transport", str),
        "MCP_DEBUG": ("mcp", "debug", bool),
        # 日志配置
        "LOG_LEVEL": ("log", "level", str),
        "LOG_FILE": ("log", "file", str),
    }
    
    def __init__(self):
        self.config: Config = Config()
        self.config_path: Optional[Path] = None
    
    def load_config(self, config_path: Optional[str] = None) -> Config:
        """
        加载配置文件
        
        Args:
            config_path: 配置文件路径，如果为None则使用默认路径
            
        Returns:
            配置对象
        """
        # 确定配置文件路径
        if config_path:
            self.config_path = Path(config_path)
        else:
            # 尝试从多个位置查找配置文件
            possible_paths = [
                Path("./config.toml"),
                Path("./src/config.toml"),
                Path(os.path.expanduser("~/.mcp-weixin/config.toml")),
            ]
            
            for path in possible_paths:
                if path.exists():
                    self.config_path = path
                    break
        
        # 加载配置文件
        if self.config_path and self.config_path.exists():
            with open(self.config_path, "r", encoding="utf-8") as f:
                toml_data = toml.load(f)
            
            # 更新配置
            self._update_from_dict(toml_data)
        
        # 从环境变量加载配置，环境变量优先级高于配置文件
        self._load_from_env()
        
        # 验证配置
        errors = self.config.validate()
        if errors:
            raise ValueError(f"配置验证失败: {', '.join(f'{k}: {v}' for k, v in errors.items())}")
        
        return self.config
    
    def _update_from_dict(self, data: Dict[str, Any]):
        """从字典更新配置"""
        for section_name, section_data in data.items():
            if hasattr(self.config, section_name):
                section = getattr(self.config, section_name)
                for key, value in section_data.items():
                    if hasattr(section, key):
                        setattr(section, key, value)
    
    def _load_from_env(self):
        """从环境变量加载配置"""
        for env_key, (section, config_key, data_type) in self.ENV_MAPPINGS.items():
            env_value = os.getenv(env_key)
            if env_value is not None:
                try:
                    section_obj = getattr(self.config, section)
                    if data_type == bool:
                        value = env_value.lower() == "true"
                    else:
                        value = data_type(env_value)
                    setattr(section_obj, config_key, value)
                except (ValueError, TypeError) as e:
                    raise ValueError(f"环境变量 {env_key} 格式无效: {e}")
    
    def save_config(self, config_path: Optional[str] = None):
        """
        保存配置到文件
        
        Args:
            config_path: 配置文件路径，如果为None则使用当前配置文件路径
        """
        if config_path:
            self.config_path = Path(config_path)
        elif not self.config_path:
            self.config_path = Path("./config.toml")
        
        # 创建配置目录（如果不存在）
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 保存配置文件
        with open(self.config_path, "w", encoding="utf-8") as f:
            toml.dump(self.config.to_dict(), f)


# 创建全局配置实例
config_manager = ConfigManager()
# 加载配置
config = config_manager.load_config()
