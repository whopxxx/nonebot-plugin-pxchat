import json
import os
from typing import List, Dict

CONTEXT_FILE = "px_chat_context.json"
MAX_CONTEXT_LENGTH = 20  # 每个对话最大消息数

# { "user_id_or_group_id": [{"role": "user|assistant|system", "content": "..."}] }
_contexts: Dict[str, List[Dict[str, str]]] = {}

def load_contexts():
    global _contexts
    if os.path.exists(CONTEXT_FILE):
        try:
            with open(CONTEXT_FILE, "r", encoding="utf-8") as f:
                _contexts = json.load(f)
        except Exception:
            _contexts = {}

def save_contexts():
    with open(CONTEXT_FILE, "w", encoding="utf-8") as f:
        json.dump(_contexts, f, ensure_ascii=False, indent=2)

def get_context(key: str) -> List[Dict[str, str]]:
    return _contexts.get(key, [])

def add_message(key: str, role: str, content: str):
    context = _contexts.get(key, [])
    context.append({"role": role, "content": content})
    if len(context) > MAX_CONTEXT_LENGTH:
        context = context[-MAX_CONTEXT_LENGTH:]
    _contexts[key] = context
    save_contexts()

def clear_context(key: str):
    if key in _contexts:
        del _contexts[key]
        save_contexts()

def add_user_message_to_group(group_id: str, user_id: str, nickname: str, content: str):
    """
    专门用于群聊环境添加用户消息
    """
    key = f"group_{group_id}"
    user_info = f"用户{user_id}({nickname})"
    user_message = f"{user_info}: {content}"
    add_message(key, "user", user_message)