from openai import OpenAI
from nonebot import logger
from .manager import chat_manager
import asyncio
import json

async def recognize_image(image_url: str, prompt: str = "请简洁描述这张图片的内容") -> str:
    """
    使用多模态模型识别图片内容
    :param image_url: 图片URL
    :param prompt: 识别提示词
    :return: 识别结果文本
    """
    # 获取图片识别专用的AI配置
    ai_config = chat_manager.get_current_image_recognition_config()
    
    if not ai_config:
        raise Exception("未配置图片识别服务，请使用 'px image ai add' 命令添加配置")
    
    try:
        # 动态创建客户端
        client = OpenAI(
            api_key=ai_config.get("api_key", ""),
            base_url=ai_config.get("api_url", ""),
        )
        
        def sync_call():
            completion = client.chat.completions.create(
                model=ai_config.get("model", ""),
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": image_url,
                                    "detail": "high"
                                }
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }
                ],
                max_tokens=1000
            )
            return completion.choices[0].message.content

        result = await asyncio.to_thread(sync_call)

        if not result:
            raise Exception("图片识别返回了空结果")
            
        return result
    except Exception as e:
        logger.error(f"图片识别服务出现异常: {e}")
        raise Exception(f"图片识别出现异常: {e}")