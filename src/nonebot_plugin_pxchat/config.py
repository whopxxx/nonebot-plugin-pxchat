from pydantic import BaseModel
from nonebot import get_plugin_config
from typing import Set, Dict, List, Any

class PluginConfig(BaseModel):
    """插件配置"""
    # 超级用户列表
    pxchat_super_users: Set[str] = set()

    # MCP配置
    pxchat_mcp: Dict[str, Dict[str, Any]] = {}

config = get_plugin_config(PluginConfig)