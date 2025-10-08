from nonebot import logger, get_bot
from nonebot.adapters.onebot.v11 import MessageEvent
from .manager import chat_manager


async def send_forward_message(user_id: int = None, group_id: int = None, messages: list = None):
    """
    发送合并转发消息
    :param user_id: QQ号（私聊时使用）
    :param group_id: 群号（群聊时使用）
    :param messages: 消息节点列表
    """
    if not messages:
        logger.warning("合并转发消息内容为空")
        return None
    
    try:
        bot = get_bot()
        params = {"messages": messages}
        
        if not user_id and not group_id:
            logger.error(f"参数错误: 至少指定 user_id 或 group_id 其中一个")
            return None

        params["user_id"] = user_id
        params["group_id"] = group_id
        
        result = await bot.call_api("send_forward_msg", **params)
        logger.info(f"合并转发消息发送成功")
        return result
        
    except Exception as e:
        logger.error(f"发送合并转发消息失败: {e}")
        return None


async def create_text_node(nickname: str, user_id: int, content: str):
    """创建文本消息节点"""
    return {
        "type": "node",
        "data": {
            "name": nickname,
            "uin": str(user_id),
            "content": content
        }
    }


async def send_long_message(title: str, content: str, user_id: int = None, group_id: int = None):
    """
    智能发送长消息，根据长度选择普通消息或合并转发
    """
    messages = [
        await create_text_node("系统消息", get_bot().self_id, title),
        await create_text_node("系统消息", get_bot().self_id, content)
    ]
    return await send_forward_message(user_id=user_id, group_id=group_id, messages=messages)


def extract_error_summary(error_msg: str, max_length: int = 500) -> str:
    """提取错误信息的关键摘要"""
    if len(error_msg) <= max_length:
        return error_msg
    
    lines = error_msg.split('\n')
    summary_parts = []
    
    if lines:
        summary_parts.append(lines[0])
    
    keywords = ['error', 'Error', 'Exception', 'failed', 'Failed', 'timeout', 'Timeout']
    for line in lines[1:]:
        if any(keyword in line for keyword in keywords):
            if line not in summary_parts:
                summary_parts.append(line)
            if len('\n'.join(summary_parts)) > max_length:
                break
    
    if len('\n'.join(summary_parts)) < max_length // 2:
        for line in lines[1:6]:
            if line not in summary_parts and line.strip():
                summary_parts.append(line)
    
    summary = '\n'.join(summary_parts)
    
    if len(summary) > max_length:
        summary = summary[:max_length] + "..."
    
    return summary


async def send_error_to_super_users(error_msg: str, event: MessageEvent = None):
    """发送错误信息给所有管理员，使用合并转发"""
    super_users = chat_manager.get_super_users()
    if not super_users:
        logger.warning("没有配置管理员，无法发送错误信息")
        return
    
    bot = get_bot()
    error_summary = extract_error_summary(error_msg)
    
    messages = []
    
    # 错误概述
    overview_content = "聊天插件错误报告"
    if event:
        overview_content += f"\n触发用户: {event.user_id}"
        if hasattr(event, 'group_id') and event.group_id:
            overview_content += f"\n触发群组: {event.group_id}"
        
        trigger_msg = event.get_plaintext()
        if len(trigger_msg) > 100:
            trigger_msg = trigger_msg[:100] + "..."
        overview_content += f"\n触发消息: {trigger_msg}"
    
    messages.append(await create_text_node("系统监控", bot.self_id, overview_content))
    messages.append(await create_text_node("错误信息", bot.self_id, f"错误详情:\n{error_summary}"))
    
    # 发送给所有管理员
    for user_id in super_users:
        try:
            await send_forward_message(user_id=int(user_id), messages=messages)
            logger.info(f"已发送错误信息给管理员 {user_id}")
        except Exception as e:
            logger.error(f"发送错误信息给管理员 {user_id} 失败: {e}")
            try:
                fallback_msg = f"聊天插件错误:\n{error_summary[:100]}..."
                await bot.send_private_msg(user_id=int(user_id), message=fallback_msg)
            except Exception as fallback_e:
                logger.error(f"备用消息发送失败: {fallback_e}")