import asyncio
from contextlib import AsyncExitStack
from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client
from nonebot import logger
from .manager import chat_manager

class TransientMCPClient:
    """一次性MCP客户端，每次调用都重新连接"""
    
    def __init__(self):
        self.tools_cache = {}  # 缓存工具列表，避免重复发现

    async def _create_session(self, config, exit_stack):
        """根据配置创建MCP会话并正确管理上下文"""
        server_type = config.get("type", "sse")
        
        try:
            if server_type == "sse":
                # SSE传输方式 - 正确使用异步上下文管理器
                sse_transport_cm = sse_client(
                    url=config["url"], 
                    headers=config.get("headers", {})
                )
                sse_transport = await exit_stack.enter_async_context(sse_transport_cm)
                read, write = sse_transport
            elif server_type == "stdio":
                # stdio传输方式 - 正确使用异步上下文管理器
                stdio_transport_cm = stdio_client(
                    command=config["command"],
                    args=config.get("args", []),
                    env=config.get("env", {})
                )
                stdio_transport = await exit_stack.enter_async_context(stdio_transport_cm)
                read, write = stdio_transport
            else:
                raise ValueError(f"不支持的MCP传输类型: {server_type}")
            
            # 创建ClientSession并进入其上下文
            session_cm = ClientSession(read, write)
            session = await exit_stack.enter_async_context(session_cm)
            
            # 初始化会话
            await session.initialize()
            
            return session
            
        except Exception as e:
            logger.error(f"创建MCP会话失败: {e}")
            raise

    async def get_tools(self):
        """获取所有可用工具"""
        if self.tools_cache:
            return self.tools_cache
            
        tools = []
        async with AsyncExitStack() as exit_stack:
            try:
                # 从管理器获取启用的MCP服务器配置
                server_config = chat_manager.get_enabled_mcp_servers()
                if not server_config:
                    logger.info("没有启用的MCP服务器配置")
                    return []
                    
                for server_name, config in server_config.items():
                    try:
                        logger.info(f"连接服务器 [{server_name}] 获取工具列表")
                        
                        # 创建会话
                        session = await self._create_session(config, exit_stack)
                        
                        # 获取工具列表
                        response = await session.list_tools()
                        for tool in response.tools:
                            tool_info = {
                                "name": f"{server_name}___{tool.name}",
                                "description": tool.description or f"Tool {tool.name} from {server_name}",
                                "parameters": tool.inputSchema or {"type": "object", "properties": {}},
                                "server_name": server_name,
                                "tool_name": tool.name
                            }
                            tools.append(tool_info)
                            logger.info(f"发现工具: {tool.name}")
                            
                    except Exception as e:
                        logger.error(f"获取服务器 [{server_name}] 工具失败: {e}")
                        continue
                        
                # 缓存工具列表
                self.tools_cache = tools
                return tools
                
            except Exception as e:
                logger.error(f"获取工具列表过程中发生错误: {e}")
                return []

    async def call_tool(self, tool_name: str, arguments: dict, timeout: float = 30.0):
        """调用工具 - 每次调用都创建新连接"""
        if "___" not in tool_name:
            raise ValueError(f"无效的工具名格式: {tool_name}")
            
        server_name, real_tool_name = tool_name.split("___", 1)
        logger.info(f"调用工具: {server_name}.{real_tool_name}, 参数: {arguments}")
        
        # 从管理器获取MCP服务器配置
        server_config = chat_manager.get_mcp_servers()
        config = server_config.get(server_name)
        if not config:
            raise ValueError(f"未知服务器: {server_name}")
        
        async with AsyncExitStack() as exit_stack:
            try:
                # 创建会话
                session = await self._create_session(config, exit_stack)
                
                # 调用工具
                response = await asyncio.wait_for(
                    session.call_tool(real_tool_name, arguments),
                    timeout=timeout
                )
                
                result = response.content[0].text if response.content else "工具调用成功"
                logger.info(f"工具调用完成: {result[:100]}...")
                return result
                
            except asyncio.TimeoutError:
                logger.warning(f"工具调用超时: {tool_name}")
                return f"工具调用超时，请稍后重试"
            except Exception as e:
                logger.error(f"工具调用失败 {tool_name}: {e}")
                return f"工具调用失败: {str(e)}"

    def get_openai_tools_format(self):
        """获取OpenAI格式的工具列表"""
        openai_tools = []
        for tool in self.tools_cache:
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["parameters"]
                }
            })
        return openai_tools

    def clear_cache(self):
        """清除工具缓存"""
        self.tools_cache = {}

# 全局客户端实例
mcp_client = TransientMCPClient()