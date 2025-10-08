import json
import os
from typing import List, Dict, Any, Optional
from nonebot import logger
from nonebot.adapters.onebot.v11 import MessageEvent

# 管理配置文件路径
MANAGER_FILE = "px_chat_manager.json"

class ChatManager:
    def __init__(self):
        self._data: Dict[str, Any] = {}
        self._load_manager_config()
    
    def _load_manager_config(self):
        """加载管理配置"""
        if os.path.exists(MANAGER_FILE):
            try:
                with open(MANAGER_FILE, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
                logger.info("聊天管理器配置加载成功")
            except Exception as e:
                logger.error(f"加载聊天管理器配置失败: {e}")
                self._data = self._get_default_config()
        else:
            self._data = self._get_default_config()
            self._save_manager_config()
            logger.info("创建新的聊天管理器配置")
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            "super_users": [],
            "enabled_groups": [],
            "chat_enabled": True,
            "group_chat_probability": 1,  # 群活跃度基础值
            "personality": "你叫px，是被困在服务器中的ai程序。在聊天中回答问题要保持简洁直接。情绪随心情波动，回答长短看情况。任何问题都只给关键信息，不啰嗦",
            "ai_configs": [],  # 改为数组形式，支持多个模型配置
            "current_ai_config": 0,  # 当前使用的配置索引
            "image_recognition_enabled": False,  # 图片识别功能开关
            "current_image_recognition_config": 0,  # 当前图片识别配置索引
            "enable_search": False,   # 是否启用搜索功能
            "mcp_enabled": False,     # MCP功能总开关
            "mcp_servers": {          # MCP服务器配置
                # "web_search": {
                #     "url": "https://dashscope.aliyuncs.com/api/v1/mcps/WebSearch/sse",
                #     "headers": {
                #         "Authorization": "Bearer you-key-here"
                #     },
                #     "enabled": True
                # }
                # 可以添加stdio类型的配置示例:
                # "local_tool": {
                #     "type": "stdio",
                #     "command": "python",
                #     "args": ["/path/to/mcp/server.py"],
                #     "env": {"KEY": "value"},
                #     "enabled": True
                # }
            }
        }
    
    def _save_manager_config(self):
        """保存管理配置"""
        try:
            with open(MANAGER_FILE, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存聊天管理器配置失败: {e}")
    
    # MCP功能管理
    def is_mcp_enabled(self) -> bool:
        """检查MCP功能是否启用"""
        return self._data.get("mcp_enabled", False)
    
    def set_mcp_enabled(self, enabled: bool) -> bool:
        """设置MCP功能开关"""
        if self._data.get("mcp_enabled", False) != enabled:
            self._data["mcp_enabled"] = enabled
            self._save_manager_config()
            return True
        return False
    
    def get_mcp_servers(self) -> Dict[str, Any]:
        """获取所有MCP服务器配置"""
        return self._data.get("mcp_servers", {})
    
    def get_enabled_mcp_servers(self) -> Dict[str, Any]:
        """获取启用的MCP服务器配置"""
        all_servers = self.get_mcp_servers()
        return {name: config for name, config in all_servers.items() 
                if config.get("enabled", True)}
    
    def set_mcp_server_enabled(self, server_name: str, enabled: bool) -> bool:
        """设置单个MCP服务器的启用状态"""
        servers = self.get_mcp_servers()
        if server_name in servers:
            if servers[server_name].get("enabled", True) != enabled:
                servers[server_name]["enabled"] = enabled
                self._data["mcp_servers"] = servers
                self._save_manager_config()
                return True
        return False
    
    def add_mcp_server(self, server_name: str, server_type: str, **kwargs) -> bool:
        """添加MCP服务器配置
        
        Args:
            server_name: 服务器名称
            server_type: 服务器类型 "sse" 或 "stdio"
            **kwargs: 配置参数
                - 对于sse类型: url, headers
                - 对于stdio类型: command, args, env
        """
        servers = self.get_mcp_servers()
        if server_name in servers:
            return False
        
        base_config = {
            "type": server_type,
            "enabled": True
        }
        
        if server_type == "sse":
            base_config.update({
                "url": kwargs.get("url"),
                "headers": kwargs.get("headers", {})
            })
        elif server_type == "stdio":
            base_config.update({
                "command": kwargs.get("command"),
                "args": kwargs.get("args", []),
                "env": kwargs.get("env", {})
            })
        else:
            return False
        
        servers[server_name] = base_config
        self._data["mcp_servers"] = servers
        self._save_manager_config()
        return True
    
    def remove_mcp_server(self, server_name: str) -> bool:
        """移除MCP服务器配置"""
        servers = self.get_mcp_servers()
        if server_name in servers:
            del servers[server_name]
            self._data["mcp_servers"] = servers
            self._save_manager_config()
            return True
        return False
    
    # 群聊触发概率管理
    def get_group_chat_probability(self) -> float:
        """获取群聊触发概率"""
        return self._data.get("group_chat_probability", 0.2)
    
    def set_group_chat_probability(self, probability: float) -> bool:
        """设置群聊触发概率"""
        if not 0 <= probability <= 1:
            return False
        
        if self._data.get("group_chat_probability", 0.2) != probability:
            self._data["group_chat_probability"] = probability
            self._save_manager_config()
            return True
        return False
    
    # 管理员管理
    def is_super_user(self, user_id: str) -> bool:
        """检查用户是否为管理员"""
        return user_id in self._data.get("super_users", [])
    
    def add_super_user(self, user_id: str) -> bool:
        """添加管理员"""
        if user_id not in self._data.get("super_users", []):
            if "super_users" not in self._data:
                self._data["super_users"] = []
            self._data["super_users"].append(user_id)
            self._save_manager_config()
            return True
        return False
    
    def remove_super_user(self, user_id: str) -> bool:
        """移除管理员"""
        if user_id in self._data.get("super_users", []):
            self._data["super_users"].remove(user_id)
            self._save_manager_config()
            return True
        return False
    
    def get_super_users(self) -> List[str]:
        """获取所有管理员"""
        return self._data.get("super_users", [])
    
    # 群聊管理
    def is_group_enabled(self, group_id: str) -> bool:
        """检查群聊是否启用"""
        return group_id in self._data.get("enabled_groups", [])
    
    def enable_group(self, group_id: str) -> bool:
        """启用群聊"""
        if group_id not in self._data.get("enabled_groups", []):
            if "enabled_groups" not in self._data:
                self._data["enabled_groups"] = []
            self._data["enabled_groups"].append(group_id)
            self._save_manager_config()
            return True
        return False
    
    def disable_group(self, group_id: str) -> bool:
        """禁用群聊"""
        if group_id in self._data.get("enabled_groups", []):
            self._data["enabled_groups"].remove(group_id)
            self._save_manager_config()
            return True
        return False
    
    def get_enabled_groups(self) -> List[str]:
        """获取所有启用的群聊"""
        return self._data.get("enabled_groups", [])
    
    # AI配置管理
    def get_ai_configs(self) -> List[Dict[str, str]]:
        """获取所有AI配置"""
        return self._data.get("ai_configs", [])
    
    def get_current_ai_config(self) -> Dict[str, str]:
        """获取当前使用的AI配置"""
        configs = self.get_ai_configs()
        current_index = self._data.get("current_ai_config", 0)
        if configs and 0 <= current_index < len(configs):
            return configs[current_index]
        return {}
    
    def add_ai_config(self, name: str, api_key: str, api_url: str, model: str) -> bool:
        """添加新的AI配置"""
        if "ai_configs" not in self._data:
            self._data["ai_configs"] = []
        
        for config in self._data["ai_configs"]:
            if config.get("name") == name:
                return False
        
        new_config = {
            "name": name,
            "api_key": api_key,
            "api_url": api_url,
            "model": model
        }
        
        self._data["ai_configs"].append(new_config)
        self._save_manager_config()
        return True
    
    def remove_ai_config(self, name: str) -> bool:
        """移除AI配置"""
        configs = self.get_ai_configs()
        for i, config in enumerate(configs):
            if config.get("name") == name:
                is_current_chat_config = (self._data.get("current_ai_config", 0) == i)
                is_current_image_config = (self._data.get("current_image_recognition_config", 0) == i)
                
                self._data["ai_configs"].pop(i)
                
                current_chat_index = self._data.get("current_ai_config", 0)
                if current_chat_index >= i:
                    self._data["current_ai_config"] = max(0, current_chat_index - 1)
                
                current_image_index = self._data.get("current_image_recognition_config", 0)
                if current_image_index >= i:
                    self._data["current_image_recognition_config"] = max(0, current_image_index - 1)
                
                self._save_manager_config()
                return True, is_current_chat_config, is_current_image_config
        return False, False, False
    
    def switch_ai_config(self, name: str) -> bool:
        """切换到指定的AI配置"""
        configs = self.get_ai_configs()
        for i, config in enumerate(configs):
            if config.get("name") == name:
                self._data["current_ai_config"] = i
                self._save_manager_config()
                return True
        return False
    
    def get_current_config_index(self) -> int:
        """获取当前配置索引"""
        return self._data.get("current_ai_config", 0)
    
    # 全局开关管理
    def is_chat_enabled(self) -> bool:
        """检查AI聊天是否启用"""
        return self._data.get("chat_enabled", True)
    
    def set_chat_enabled(self, enabled: bool) -> bool:
        """设置AI聊天开关"""
        if self._data.get("chat_enabled", True) != enabled:
            self._data["chat_enabled"] = enabled
            self._save_manager_config()
            return True
        return False
    
    # 搜索功能开关
    def is_search_enabled(self) -> bool:
        """检查搜索功能是否启用"""
        return self._data.get("enable_search", False)
    
    def set_search_enabled(self, enabled: bool) -> bool:
        """设置搜索功能开关"""
        if self._data.get("enable_search", False) != enabled:
            self._data["enable_search"] = enabled
            self._save_manager_config()
            return True
        return False
    
    # 人设管理
    def get_personality(self) -> str:
        """获取人设配置"""
        return self._data.get("personality", "")
    
    def set_personality(self, personality: str) -> bool:
        """设置人设配置"""
        if self._data.get("personality", "") != personality:
            self._data["personality"] = personality
            self._save_manager_config()
            return True
        return False
    
    # 权限检查
    def check_permission(self, event: MessageEvent) -> bool:
        """检查用户是否有权限操作"""
        user_id = str(event.user_id)
        return self.is_super_user(user_id)

    # 图片识别相关方法
    def is_image_recognition_enabled(self) -> bool:
        """检查图片识别功能是否启用"""
        return self._data.get("image_recognition_enabled", False)

    def set_image_recognition_enabled(self, enabled: bool) -> bool:
        """设置图片识别功能开关"""
        if self._data.get("image_recognition_enabled", False) != enabled:
            self._data["image_recognition_enabled"] = enabled
            self._save_manager_config()
            return True
        return False

    def get_current_image_recognition_config(self) -> Dict[str, str]:
        """获取当前图片识别使用的AI配置"""
        configs = self.get_ai_configs()
        current_index = self._data.get("current_image_recognition_config", 0)
        if configs and 0 <= current_index < len(configs):
            return configs[current_index]
        return {}

    def switch_image_recognition_config(self, name: str) -> bool:
        """切换到指定的图片识别配置"""
        configs = self.get_ai_configs()
        for i, config in enumerate(configs):
            if config.get("name") == name:
                self._data["current_image_recognition_config"] = i
                self._save_manager_config()
                return True
        return False

    def get_current_image_config_index(self) -> int:
        """获取当前图片识别配置索引"""
        return self._data.get("current_image_recognition_config", 0)

# 全局管理器实例
chat_manager = ChatManager()