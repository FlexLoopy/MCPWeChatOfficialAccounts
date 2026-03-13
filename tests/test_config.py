#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置模块单元测试
"""

import os
import tempfile
import unittest
from pathlib import Path
from src.mcp_weixin_spider.config import (
    ConfigManager, Config, SpiderConfig, MCPConfig, LogConfig
)


class TestConfig(unittest.TestCase):
    """配置类单元测试"""
    
    def test_config_creation(self):
        """测试配置对象创建"""
        # 创建默认配置
        config = Config()
        self.assertIsInstance(config, Config)
        self.assertIsInstance(config.spider, SpiderConfig)
        self.assertIsInstance(config.mcp, MCPConfig)
        self.assertIsInstance(config.log, LogConfig)
        
        # 验证默认值
        self.assertEqual(config.spider.headless, True)
        self.assertEqual(config.spider.wait_time, 10)
        self.assertEqual(config.mcp.server_name, "mcp-weixin-spider")
        self.assertEqual(config.log.level, "INFO")
    
    def test_config_access(self):
        """测试配置访问"""
        config = Config()
        
        # 直接访问配置属性
        self.assertEqual(config.spider.headless, True)
        self.assertEqual(config.mcp.transport, "stdio")
        self.assertEqual(config.log.format, "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    
    def test_config_modification(self):
        """测试配置修改"""
        config = Config()
        
        # 修改配置
        config.spider.headless = False
        config.spider.wait_time = 5
        config.mcp.debug = True
        config.log.level = "DEBUG"
        
        # 验证修改结果
        self.assertEqual(config.spider.headless, False)
        self.assertEqual(config.spider.wait_time, 5)
        self.assertEqual(config.mcp.debug, True)
        self.assertEqual(config.log.level, "DEBUG")
    
    def test_config_validation(self):
        """测试配置验证"""
        # 有效配置
        config = Config()
        errors = config.validate()
        self.assertEqual(errors, {})
        
        # 无效配置 - 等待时间为0
        config.spider.wait_time = 0
        errors = config.validate()
        self.assertIn("wait_time", errors)
        
        # 无效配置 - 浏览器类型错误
        config.spider.wait_time = 10  # 恢复有效配置
        config.spider.browser = "invalid"
        errors = config.validate()
        self.assertIn("browser", errors)
        
        # 无效配置 - MCP传输方式错误
        config.spider.browser = "chrome"  # 恢复有效配置
        config.mcp.transport = "invalid"
        errors = config.validate()
        self.assertIn("transport", errors)
    
    def test_config_to_dict(self):
        """测试配置转换为字典"""
        config = Config()
        config_dict = config.to_dict()
        
        self.assertIsInstance(config_dict, dict)
        self.assertIn("spider", config_dict)
        self.assertIn("mcp", config_dict)
        self.assertIn("log", config_dict)
        
        # 验证字典值
        self.assertEqual(config_dict["spider"]["headless"], True)
        self.assertEqual(config_dict["mcp"]["server_name"], "mcp-weixin-spider")
        self.assertEqual(config_dict["log"]["level"], "INFO")


class TestConfigManager(unittest.TestCase):
    """配置管理器单元测试"""
    
    def setUp(self):
        """测试前设置"""
        # 保存原始环境变量
        self.original_env = os.environ.copy()
        # 创建临时目录用于测试配置文件
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
    
    def tearDown(self):
        """测试后清理"""
        # 恢复原始环境变量
        os.environ.clear()
        os.environ.update(self.original_env)
        # 删除临时目录
        self.temp_dir.cleanup()
    
    def test_config_manager_initialization(self):
        """测试配置管理器初始化"""
        manager = ConfigManager()
        self.assertIsInstance(manager, ConfigManager)
        self.assertIsInstance(manager.config, Config)
        self.assertIsNone(manager.config_path)
    
    def test_load_default_config(self):
        """测试加载默认配置"""
        manager = ConfigManager()
        config = manager.load_config()
        
        self.assertIsInstance(config, Config)
        # 验证默认值
        self.assertEqual(config.spider.headless, True)
        self.assertEqual(config.mcp.server_name, "mcp-weixin-spider")
        self.assertEqual(config.log.level, "INFO")
    
    def test_load_from_dict(self):
        """测试从字典加载配置"""
        manager = ConfigManager()
        
        # 创建测试配置字典
        config_dict = {
            "spider": {
                "headless": False,
                "wait_time": 5,
                "download_images": False,
                "browser": "edge"
            },
            "mcp": {
                "server_name": "test-server",
                "transport": "tcp",
                "debug": True
            },
            "log": {
                "level": "DEBUG",
                "format": "%(levelname)s - %(message)s"
            }
        }
        
        # 从字典加载配置
        manager._update_from_dict(config_dict)
        
        # 验证配置是否正确加载
        self.assertEqual(manager.config.spider.headless, False)
        self.assertEqual(manager.config.spider.wait_time, 5)
        self.assertEqual(manager.config.spider.download_images, False)
        self.assertEqual(manager.config.spider.browser, "edge")
        
        self.assertEqual(manager.config.mcp.server_name, "test-server")
        self.assertEqual(manager.config.mcp.transport, "tcp")
        self.assertEqual(manager.config.mcp.debug, True)
        
        self.assertEqual(manager.config.log.level, "DEBUG")
        self.assertEqual(manager.config.log.format, "%(levelname)s - %(message)s")
    
    def test_load_from_env(self):
        """测试从环境变量加载配置"""
        manager = ConfigManager()
        
        # 设置环境变量
        os.environ["HEADLESS"] = "false"
        os.environ["WAIT_TIME"] = "15"
        os.environ["BROWSER"] = "edge"
        os.environ["MCP_SERVER_NAME"] = "env-server"
        os.environ["MCP_DEBUG"] = "true"
        os.environ["LOG_LEVEL"] = "WARNING"
        
        # 从环境变量加载配置
        manager._load_from_env()
        
        # 验证配置是否正确加载
        self.assertEqual(manager.config.spider.headless, False)
        self.assertEqual(manager.config.spider.wait_time, 15)
        self.assertEqual(manager.config.spider.browser, "edge")
        self.assertEqual(manager.config.mcp.server_name, "env-server")
        self.assertEqual(manager.config.mcp.debug, True)
        self.assertEqual(manager.config.log.level, "WARNING")
    
    def test_save_and_load_config_file(self):
        """测试保存和加载配置文件"""
        manager = ConfigManager()
        
        # 修改配置
        manager.config.spider.headless = False
        manager.config.spider.wait_time = 5
        manager.config.mcp.server_name = "test-save"
        
        # 保存到临时文件
        config_file = self.temp_path / "test_config.toml"
        manager.save_config(str(config_file))
        
        # 验证文件存在
        self.assertTrue(config_file.exists())
        
        # 创建新的配置管理器并从文件加载
        new_manager = ConfigManager()
        loaded_config = new_manager.load_config(str(config_file))
        
        # 验证加载的配置
        self.assertEqual(loaded_config.spider.headless, False)
        self.assertEqual(loaded_config.spider.wait_time, 5)
        self.assertEqual(loaded_config.mcp.server_name, "test-save")
    
    def test_config_validation_failure(self):
        """测试配置验证失败"""
        manager = ConfigManager()
        
        # 设置无效配置
        manager.config.spider.wait_time = -1
        
        # 验证应该失败
        with self.assertRaises(ValueError) as context:
            manager._validate_config()
        
        self.assertIn("wait_time", str(context.exception))
    
    def test_determine_config_path(self):
        """测试确定配置文件路径"""
        manager = ConfigManager()
        
        # 测试指定路径
        test_path = self.temp_path / "config.toml"
        manager._determine_config_path(str(test_path))
        self.assertEqual(manager.config_path, test_path)
        
        # 创建一个子目录，确保其中没有配置文件
        empty_dir = self.temp_path / "empty_dir"
        empty_dir.mkdir()
        
        # 切换到空目录测试默认路径查找
        original_cwd = Path.cwd()
        os.chdir(empty_dir)
        try:
            manager.config_path = None
            manager._determine_config_path(None)
            self.assertIsNone(manager.config_path)  # 因为空目录中没有默认配置文件
        finally:
            os.chdir(original_cwd)
        
        # 创建临时默认配置文件并测试
        default_config = self.temp_path / "config.toml"
        default_config.write_text("[spider]\nheadless = false")
        
        # 切换到临时目录测试默认路径查找
        os.chdir(self.temp_path)
        try:
            manager.config_path = None
            manager._determine_config_path(None)
            self.assertEqual(manager.config_path, default_config)
        finally:
            os.chdir(original_cwd)


if __name__ == "__main__":
    unittest.main()
