#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置文件集成测试脚本
验证配置文件是否能被正确加载和应用到实际功能中
"""

import logging
import os
from pathlib import Path
import unittest
from mcp_weixin_spider.config import ConfigManager, config

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TestConfigIntegration(unittest.TestCase):
    """配置文件集成测试"""
    
    def test_config_loading(self):
        """测试配置文件加载"""
        logger.info("=== 测试配置文件加载 ===")
        
        # 1. 检查全局配置是否已加载
        self.assertIsNotNone(config)
        
        # 2. 打印配置文件路径
        config_manager = ConfigManager()
        config_manager.load_config()
        self.assertIsNotNone(config_manager.config_path)
        
        # 3. 验证配置内容
        logger.info(f"\n=== 配置内容验证 ===")
        logger.info(f"Spider配置:")
        logger.info(f"  headless: {config.spider.headless}")
        logger.info(f"  wait_time: {config.spider.wait_time}")
        logger.info(f"  download_images: {config.spider.download_images}")
        logger.info(f"  browser: {config.spider.browser}")
        logger.info(f"  chrome_driver_path: {config.spider.chrome_driver_path}")
        logger.info(f"  edge_driver_path: {config.spider.edge_driver_path}")
        logger.info(f"  articles_dir: {config.spider.articles_dir}")
        logger.info(f"  images_dir: {config.spider.images_dir}")
        
        logger.info(f"\nMCP配置:")
        logger.info(f"  server_name: {config.mcp.server_name}")
        logger.info(f"  transport: {config.mcp.transport}")
        logger.info(f"  debug: {config.mcp.debug}")
        
        logger.info(f"\nLog配置:")
        logger.info(f"  level: {config.log.level}")
        logger.info(f"  format: {config.log.format}")
        logger.info(f"  file: {config.log.file}")
        
        # 4. 验证配置文件中的值是否被正确应用
        logger.info(f"\n=== 配置项验证 ===")
        
        # 检查配置文件中的特定值是否被正确加载
        expected_browser = "edge"  # 从config.toml中读取
        expected_articles_dir = ".temp"  # 从config.toml中读取
        expected_images_dir = "images"  # 从config.toml中读取
        
        actual_browser = config.spider.browser
        actual_articles_dir = Path(config.spider.articles_dir).name
        actual_images_dir = Path(config.spider.images_dir).name
        
        self.assertEqual(actual_browser, expected_browser, f"浏览器配置不匹配: 预期='{expected_browser}', 实际='{actual_browser}'")
        self.assertEqual(actual_articles_dir, expected_articles_dir, f"文章目录不匹配: 预期='{expected_articles_dir}', 实际='{actual_articles_dir}'")
        self.assertEqual(actual_images_dir, expected_images_dir, f"图片目录不匹配: 预期='{expected_images_dir}', 实际='{actual_images_dir}'")
        
        # 5. 验证配置文件路径
        logger.info(f"\n=== 配置文件路径验证 ===")
        config_file_path = Path("c:/Users/XMICUser/Desktop/tests/MCPWeChatOfficialAccounts/config.toml")
        self.assertTrue(config_file_path.exists(), f"配置文件不存在: {config_file_path}")
        
        # 6. 测试手动指定配置文件路径
        logger.info(f"\n=== 手动指定配置文件路径测试 ===")
        custom_config_manager = ConfigManager()
        custom_config = custom_config_manager.load_config(config_file_path)
        
        custom_browser = custom_config.spider.browser
        custom_articles_dir = Path(custom_config.spider.articles_dir).name
        custom_images_dir = Path(custom_config.spider.images_dir).name
        
        self.assertEqual(custom_browser, expected_browser, f"手动加载 - 浏览器配置错误: '{custom_browser}'")
        self.assertEqual(custom_articles_dir, expected_articles_dir, f"手动加载 - 文章目录错误: '{custom_articles_dir}'")
        self.assertEqual(custom_images_dir, expected_images_dir, f"手动加载 - 图片目录错误: '{custom_images_dir}'")
        
        # 7. 验证配置目录权限
        logger.info(f"\n=== 配置目录权限验证 ===")
        
        # 检查文章目录是否可写
        articles_dir_path = Path(config.spider.articles_dir)
        images_dir_path = Path(config.spider.images_dir)
        
        logger.info(f"文章目录: {articles_dir_path}")
        
        # 创建测试目录
        try:
            articles_dir_path.mkdir(parents=True, exist_ok=True)
            images_dir_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"✅ 文章目录创建成功")
            logger.info(f"✅ 图片目录创建成功")
            
            # 测试写入权限
            test_file = articles_dir_path / "test_permission.txt"
            test_file.write_text("test")
            test_file.unlink()
            logger.info(f"✅ 文章目录写入权限正常")
            
        except Exception as e:
            logger.error(f"❌ 目录权限测试失败: {str(e)}")
            self.fail(f"目录权限测试失败: {str(e)}")
        
        logger.info(f"\n=== 配置测试完成 ===")


if __name__ == "__main__":
    unittest.main()
