from nonebot import on_message, logger, get_driver, require, get_plugin_config
require("nonebot_plugin_localstore")
from nonebot.plugin import PluginMetadata
from nonebot.adapters.onebot.v11 import MessageEvent, Bot, Message, MessageSegment
from .chat import should_reply_in_group, get_chat_reply_with_tools
from .context import get_context, add_message, clear_context, load_contexts
from .manager import chat_manager
from .commands import *
from .send2root import *
from .image2txt import *
from .config import *
import asyncio
import random
import json
from .mcp_manager import *
from typing import Dict, Set

__plugin_meta__ = PluginMetadata(
    name="pxchat",
    description="基于AI的聊天插件，支持大模型任意切换、上下文记忆、群聊智能参与、图片识别、MCP等功能",
    usage="使用px about命令获取插件信息，支持指令配置",
    type="application",
    homepage="https://github.com/whopxxx/nonebot-plugin-pxchat",
    config=PluginConfig,
    supported_adapters={"~onebot.v11"},
)

# 初始化管理器和上下文
load_contexts()
# 读取配置文件
get_plugin_config(PluginConfig)
# 创建消息处理器，不限制规则，在handle中自行判断
chat = on_message(priority=50, block=False)

async def send_split_messages(chat_handler, message: str, event: MessageEvent = None, delay_range: tuple = (2, 3)):
    """
    分段发送消息，支持@回复
    :param chat_handler: 聊天处理器
    :param message: 要发送的消息
    :param event: 消息事件，用于@回复
    :param delay_range: 每段消息之间的延迟时间范围（秒）
    """
    if not message:
        return

    segments = []
    
    # 尝试解析JSON格式
    try:
        data = json.loads(message)
        if isinstance(data, dict) and "reply" in data and isinstance(data["reply"], list):
            segments = [segment for segment in data["reply"] if segment and segment.strip()]
    except (json.JSONDecodeError, TypeError) as e:
        # 如果不是JSON，直接使用原消息
        error_msg = f"处理聊天请求时发生异常:\n {str(e)}"
        await send_error_to_super_users(error_msg, event)
        return

    if not segments:
        return

    # 如果被@且是群聊，第一段需要@触发用户
    if event and hasattr(event, 'group_id') and event.group_id and event.is_tome():
        first_segment = segments[0]
        # 构建@消息
        at_message = Message(f"[CQ:at,qq={event.user_id}] {first_segment}")
        await chat_handler.send(at_message)
        
        # 发送剩余段落
        for segment in segments[1:]:
            await chat_handler.send(segment)
            if segment != segments[-1]:  # 不是最后一段就延迟
                await asyncio.sleep(random.uniform(*delay_range))
    else:
        # 普通分段发送
        for i, segment in enumerate(segments):
            await chat_handler.send(segment)
            if i < len(segments) - 1:
                await asyncio.sleep(random.uniform(*delay_range))

@chat.handle()
async def _(bot: Bot, event: MessageEvent):
    # 检查全局开关
    if not chat_manager.is_chat_enabled():
        return
    
    if not chat_manager.get_super_users():
        await chat.finish("请在配置文件中添加管理员账号")

    # 获取群聊ID
    group_id = getattr(event, "group_id", None)
    user_id = str(event.user_id)

    # 构建上下文key
    if group_id:
        group_id_str = str(group_id)
        # 群聊检查
        if not chat_manager.is_group_enabled(group_id_str):
            return
        key = f"group_{group_id}"
        is_group = True
    else:
        key = user_id
        is_group = False
    
    user_msg2 = str(event.get_plaintext())
    # 过滤掉命令消息
    if user_msg2.startswith("px "):
        return

    # 支持命令清理上下文
    if user_msg2 in ["清除对话", "重置对话"]:
        clear_context(key)
        await chat.finish("已清除对话历史")

    user_msg = await event_proc(event)
    # 获取当前上下文
    context = get_context(key)

    # 群聊特殊处理
    if is_group:
        # 记录用户信息到上下文（即使不触发AI回复）
        user_info = f"用户{user_id}({event.sender.nickname if event.sender else '未知用户'})说："
        user_message_with_info = f"{user_info}: {user_msg}"
        
        # 添加到上下文
        add_message(key, "user", user_message_with_info)

        # 判断是否需要回复
        should_reply = False
        
        # 情况1: 被@了必须回复
        if event.is_tome():
            should_reply = True
            logger.info(f"群聊中被@，准备回复")
            # 续租群聊活跃度
            group_manager.renew_probability(group_id_str)
        # 情况2: 没有被@，根据活跃度和AI判断
        else:
            # 获取当前活跃度
            dynamic_probability = group_manager.get_probability(group_id_str)
            if random.random() < dynamic_probability:
                # AI判断是否应该回复
                try:
                    should_reply = await should_reply_in_group(get_context(key))
                except Exception as e:
                    error_msg = f"群聊对话判断异常:\n {str(e)}" 
                    await send_error_to_super_users(error_msg, event)
                    should_reply = False  # 出错则不回复
                if should_reply:
                    logger.info(f"AI判断需要参与群聊讨论")
                    # 续租群聊活跃度
                    group_manager.renew_probability(group_id_str)
                else:
                    logger.info(f"AI判断不需要参与群聊讨论")

        if not should_reply:
            return
    else:
        # 私聊直接记录
        add_message(key, "user", user_msg)

    # 调用聊天接口（群聊和私聊使用不同的系统提示词）
    try:
        # 获取回复，没有开启MCP的话会切换到普通对话
        reply = await get_chat_reply_with_tools(get_context(key), is_group)
        
        # 添加机器人回复 - 记录原始回复内容
        add_message(key, "assistant", reply)

        # 分段发送主回复，传入event用于@回复
        await send_split_messages(chat, reply, event if is_group else None)

    except Exception as e:
        error_msg = f"处理聊天请求时发生异常:\n {str(e)}"
        # 清除上下文
        clear_context(key)
        # 发送异常信息给超级用户
        await send_error_to_super_users(error_msg, event)
        # 给用户返回统一回复
        await chat.send("抱歉，处理消息时出现了问题，已通知管理员")


# 检查
async def event_proc(event: MessageEvent):
    # 检查图片识别功能是否开启
    user_text = event.get_plaintext().strip()
    recognition_msg = f"{user_text}\n"
    if chat_manager.is_image_recognition_enabled():
        # 检查消息中是否包含图片
        image_urls = []
        for seg in event.message:
            if seg.type == "image":
                image_urls.append(seg.data.get("url"))
        # 如果包含图片，进行识别
        if image_urls:
            try:
                recognition_list = []
                # 处理所有图片
                for i, image_url in enumerate(image_urls):
                    result = await recognize_image(image_url)
                    recognition_list.append(f"[图片{i + 1}的识别结果]{result}")
                # 识别图片内容
                recognition_msg += "\n".join(recognition_list)
                logger.info(f"识别结果: {recognition_msg}")
            except Exception as e:
                error_msg = f"图片识别失败: {str(e)}"
                logger.info(error_msg)
                await send_error_to_super_users(error_msg, event)
                recognition_msg += f"\n[图片识别失败](你现在还没有图片识别的能力)"
    return recognition_msg


group_timers: Dict[str, asyncio.Task] = {}
group_probability_states: Dict[str, float] = {}

class GroupProbabilityManager:
    """群聊智能参与管理器"""
    
    def __init__(self):
        self._shutting_down = False
        logger.info(f"活跃度管理器初始化完成，基础活跃度: {chat_manager.get_group_chat_probability()}")
    
    async def _decay_task(self, group_id: str):
        """活跃度衰减任务"""
        try:
            while not self._shutting_down:
                # 等待60秒
                await asyncio.sleep(60)
                
                if self._shutting_down:
                    break
                
                # 获取当前活跃度，使用round避免浮点数精度问题
                current_prob = group_probability_states.get(group_id, 0.0)
                new_prob = max(0, round(current_prob - 0.1, 2))  # 保留2位小数
                
                # 更新活跃度
                group_probability_states[group_id] = new_prob
                logger.info(f"群组 {group_id} 活跃度衰减: {current_prob:.2f} → {new_prob:.2f}")
                
                # 如果活跃度为0，停止任务并清理状态
                if new_prob <= 0:
                    logger.info(f"群组 {group_id} 活跃度衰减结束")
                    if group_id in group_timers:
                        del group_timers[group_id]
                    # 同时清理状态
                    if group_id in group_probability_states:
                        del group_probability_states[group_id]
                    break
                    
        except asyncio.CancelledError:
            logger.info(f"群组 {group_id} 衰减任务被取消")
        except Exception as e:
            logger.error(f"群组 {group_id} 衰减任务异常: {e}")
            if group_id in group_timers:
                del group_timers[group_id]
            # 异常时也清理状态
            if group_id in group_probability_states:
                del group_probability_states[group_id]
    
    def renew_probability(self, group_id: str):
        """续租活跃度"""
        if self._shutting_down:
            return False
        try:
            # 设置活跃度为基础值，使用round避免精度问题
            base_prob = chat_manager.get_group_chat_probability()
            group_probability_states[group_id] = round(base_prob, 2)
            
            # 取消现有任务
            if group_id in group_timers:
                task = group_timers[group_id]
                if not task.done():
                    task.cancel()
                del group_timers[group_id]
            
            # 创建新任务
            task = asyncio.create_task(self._decay_task(group_id))
            group_timers[group_id] = task
            
            logger.info(f"群组 {group_id} 活跃度续租: {base_prob:.2f}")
            return True
            
        except Exception as e:
            logger.error(f"群组 {group_id} 续租失败: {e}")
            return False
    
    def get_probability(self, group_id: str) -> float:
        """获取活跃度"""
        return group_probability_states.get(group_id, 0.0)
    
    def has_active_timer(self, group_id: str) -> bool:
        """检查是否有活跃定时器"""
        return group_id in group_timers and not group_timers[group_id].done()
    
    async def shutdown(self):
        """关闭管理器"""
        self._shutting_down = True
        logger.info("开始关闭活跃度管理器...")
        
        # 取消所有任务
        for group_id, task in list(group_timers.items()):
            if not task.done():
                task.cancel()
        
        # 清空状态
        group_timers.clear()
        group_probability_states.clear()
        
        logger.info("活跃度管理器关闭完成")

group_manager: GroupProbabilityManager = GroupProbabilityManager()  # 类型注解确保类型安全


debug_cmd = on_command("px activity", priority=5, block=True)

@debug_cmd.handle()
async def handle_debug_cmd(event: MessageEvent):
    if not await check_super_user(event):
        await mcp_cmd.finish("你没有权限")
    """检查asyncio任务状态"""
    # 获取所有任务
    tasks = asyncio.all_tasks()
    current_task = asyncio.current_task()
    
    # 统计任务信息
    task_info = []
    for task in tasks:
        if task is current_task:
            continue
            
        task_dict = {
            "name": task.get_name(),
            "done": task.done(),
            "cancelled": task.cancelled(),
            "state": "运行中"
        }
        
        if task.done():
            task_dict["state"] = "已完成"
        elif task.cancelled():
            task_dict["state"] = "已取消"
            
        task_info.append(task_dict)
    
    # 构建状态消息
    status_lines = [
        "🤖 任务调试信息:",
        f"📊 总任务数: {len(tasks)}",
        f"🎯 活跃度管理器任务数: {len(group_timers)}",
        f"📈 活跃度状态数: {len(group_probability_states)}",
        "",
        "📋 活跃度管理器状态:",
        f"  活跃群组: {list(group_timers.keys())}",
        f"  活跃度状态: {group_probability_states}",
    ]
    
    
    await debug_cmd.finish("\n".join(status_lines))

driver = get_driver()

@driver.on_shutdown
async def shutdown_hook():
    """Driver 关闭时清理定时任务"""
    if group_manager:
        await group_manager.shutdown()