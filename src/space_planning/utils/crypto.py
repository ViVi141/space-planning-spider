#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
安全配置管理器
提供敏感信息的加密存储和解密读取
"""

import os
import json
import base64
import hashlib
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    logger.warning("cryptography库未安装，敏感信息将使用base64编码（不安全）")


class SecureConfig:
    """安全配置管理器 - 加密存储敏感信息"""
    
    def __init__(self, config_file: str):
        """
        初始化安全配置管理器
        
        Args:
            config_file: 配置文件路径
        """
        self.config_file = config_file
        self.config_dir = os.path.dirname(config_file)
        
        # 确保配置目录存在
        if self.config_dir:
            os.makedirs(self.config_dir, exist_ok=True)
        
        # 获取或生成主密钥
        self.master_key = self._get_master_key()
        
        # 初始化加密器
        if CRYPTO_AVAILABLE:
            try:
                self.cipher = Fernet(self.master_key)
            except Exception as e:
                logger.error(f"初始化加密器失败: {e}")
                self.cipher = None
        else:
            self.cipher = None
            logger.warning("使用base64编码（不安全），建议安装cryptography库")
    
    def _get_master_key(self) -> bytes:
        """获取主密钥（基于机器特征生成）"""
        key_file = os.path.join(self.config_dir, '.config_key') if self.config_dir else '.config_key'
        
        # 如果密钥文件已存在，读取它
        if os.path.exists(key_file):
            try:
                with open(key_file, 'rb') as f:
                    key = f.read()
                    if len(key) == 44:  # Fernet密钥长度为44字节（base64编码后）
                        return key
                    else:
                        logger.warning("密钥文件格式不正确，重新生成")
            except Exception as e:
                logger.warning(f"读取密钥文件失败: {e}，重新生成")
        
        # 生成新密钥
        if CRYPTO_AVAILABLE:
            key = Fernet.generate_key()
        else:
            # 使用机器特征生成密钥（不够安全，但比明文好）
            machine_id = self._get_machine_id()
            key_hash = hashlib.sha256(machine_id.encode()).digest()
            key = base64.urlsafe_b64encode(key_hash[:32])
        
        # 保存密钥文件
        try:
            with open(key_file, 'wb') as f:
                f.write(key)
            # Windows下设置文件权限
            if os.name == 'nt':
                try:
                    import win32api
                    import win32security
                    user, domain, type = win32security.LookupAccountName("", win32api.GetUserName())
                    sd = win32security.GetFileSecurity(key_file, win32security.DACL_SECURITY_INFORMATION)
                    dacl = win32security.ACL()
                    dacl.AddAccessAllowedAce(win32security.ACL_REVISION, win32security.FILE_ALL_ACCESS, user)
                    sd.SetSecurityDescriptorDacl(1, dacl, 0)
                    win32security.SetFileSecurity(key_file, win32security.DACL_SECURITY_INFORMATION, sd)
                except ImportError:
                    pass  # pywin32未安装，跳过权限设置
            else:
                os.chmod(key_file, 0o600)  # 限制为只有所有者可读可写
            logger.info(f"已生成新的配置密钥: {key_file}")
        except Exception as e:
            logger.error(f"保存密钥文件失败: {e}")
        
        return key
    
    def _get_machine_id(self) -> str:
        """获取机器唯一标识"""
        import platform
        import socket
        
        try:
            hostname = socket.gethostname()
            system = platform.system()
            processor = platform.processor()
            machine = platform.machine()
            return f"{hostname}_{system}_{processor}_{machine}"
        except Exception:
            return "default_machine_id"
    
    def encrypt(self, plaintext: str) -> str:
        """
        加密字符串
        
        Args:
            plaintext: 明文字符串
            
        Returns:
            加密后的base64字符串
        """
        if not plaintext:
            return ""
        
        try:
            if CRYPTO_AVAILABLE and self.cipher:
                encrypted_bytes = self.cipher.encrypt(plaintext.encode('utf-8'))
                return base64.urlsafe_b64encode(encrypted_bytes).decode('utf-8')
            else:
                # 降级方案：base64编码（不安全，但比明文好）
                return base64.b64encode(plaintext.encode('utf-8')).decode('utf-8')
        except Exception as e:
            logger.error(f"加密失败: {e}")
            return plaintext  # 加密失败时返回原文（但记录错误）
    
    def decrypt(self, ciphertext: str) -> str:
        """
        解密字符串
        
        Args:
            ciphertext: 加密的base64字符串
            
        Returns:
            解密后的明文
        """
        if not ciphertext:
            return ""
        
        try:
            if CRYPTO_AVAILABLE and self.cipher:
                encrypted_bytes = base64.urlsafe_b64decode(ciphertext.encode('utf-8'))
                decrypted_bytes = self.cipher.decrypt(encrypted_bytes)
                return decrypted_bytes.decode('utf-8')
            else:
                # 降级方案：base64解码
                return base64.b64decode(ciphertext.encode('utf-8')).decode('utf-8')
        except Exception as e:
            logger.error(f"解密失败: {e}")
            return ""  # 解密失败时返回空字符串
    
    def get_sensitive(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        获取敏感信息（自动解密）
        
        Args:
            key: 配置键名
            default: 默认值
            
        Returns:
            解密后的值
        """
        try:
            config = self._load_config()
            
            # 检查是否是加密的值（以特定前缀标识）
            value = config.get(key)
            if value is None:
                return default
            
            # 如果是字符串且看起来像加密的值，尝试解密
            if isinstance(value, str) and len(value) > 20:  # 加密后的字符串通常较长
                try:
                    return self.decrypt(value)
                except:
                    # 解密失败，可能是未加密的旧值
                    return value
            
            return value if value else default
        except Exception as e:
            logger.error(f"获取敏感信息失败 [{key}]: {e}")
            return default
    
    def set_sensitive(self, key: str, value: Optional[str]):
        """
        设置敏感信息（自动加密）
        
        Args:
            key: 配置键名
            value: 要加密的值（None表示删除）
        """
        try:
            config = self._load_config()
            
            if value:
                # 加密并保存
                encrypted_value = self.encrypt(value)
                config[key] = encrypted_value
            else:
                # 删除配置项
                config.pop(key, None)
            
            self._save_config(config)
        except Exception as e:
            logger.error(f"设置敏感信息失败 [{key}]: {e}")
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"加载配置文件失败: {e}")
        
        return {}
    
    def _save_config(self, config: Dict[str, Any]):
        """保存配置文件"""
        try:
            # 确保目录存在
            if self.config_dir:
                os.makedirs(self.config_dir, exist_ok=True)
            
            # 保存配置
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            
            # 限制文件权限（Windows下可能需要pywin32）
            if os.name != 'nt':
                try:
                    os.chmod(self.config_file, 0o600)
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"保存配置文件失败: {e}")
            raise
    
    def get_all_config(self) -> Dict[str, Any]:
        """获取所有配置（敏感信息自动解密）"""
        config = self._load_config()
        
        # 敏感信息字段列表
        sensitive_keys = ['secret_id', 'secret_key', 'password', 'api_key', 'token']
        
        result = {}
        for key, value in config.items():
            if key in sensitive_keys and isinstance(value, str) and len(value) > 20:
                # 尝试解密敏感信息
                try:
                    result[key] = self.get_sensitive(key, value)
                except:
                    result[key] = value
            else:
                result[key] = value
        
        return result
    
    def migrate_plaintext_to_encrypted(self):
        """迁移明文配置到加密配置"""
        config = self._load_config()
        sensitive_keys = ['secret_id', 'secret_key', 'password']
        migrated = False
        
        for key in sensitive_keys:
            value = config.get(key)
            if value and isinstance(value, str) and len(value) < 50:
                # 可能是明文，尝试加密
                try:
                    # 如果是有效的base64编码，跳过（可能是旧加密）
                    base64.b64decode(value)
                    # 是base64编码，跳过
                    continue
                except:
                    # 是明文，加密它
                    encrypted = self.encrypt(value)
                    config[key] = encrypted
                    migrated = True
                    logger.info(f"已迁移配置项 {key} 到加密存储")
        
        if migrated:
            self._save_config(config)
            logger.info("配置迁移完成")
        
        return migrated

