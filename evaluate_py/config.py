"""
评测框架配置文件
支持API配置、模型配置、评测参数等
"""
import os
import logging
from typing import Dict, Any, Optional, List

# 自动加载 .env 文件（如果存在 python-dotenv）
try:
    from dotenv import load_dotenv
    # evaluate_py 目录的父目录是 evaluate 目录，.env 文件应该在 evaluate 目录下
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
except ImportError:
    pass


def _get_env(key: str, default: str = "") -> str:
    """从环境变量读取配置，提供默认值"""
    return os.getenv(key, default)



# ==================== API 服务商配置 ====================
BASE_URL_CONFIG = {
    "volces": {  # 火山引擎
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "api_key": _get_env("api2"),
    },
    "siliconflow": {  # SiliconFlow
        "base_url": "https://api.siliconflow.cn/v1",
        "api_key": _get_env("api4"),
    },
    "dashscope": {  # 阿里云 DashScope
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "api_key": _get_env("api1"),
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "api_key": _get_env("api3"),
    },
    # 本地推理服务配置（无API key）
    # 注意：本地服务IP地址和端口需要通过环境变量配置，避免硬编码
    # 环境变量格式：LOCAL_<PORT>_HOST 和 LOCAL_<PORT>_PORT
    # 例如：LOCAL_8000_HOST=localhost, LOCAL_8000_PORT=8000
    "local_8000": {
        "base_url": f"http://{_get_env('LOCAL_8000_HOST', 'localhost')}:8000/v1",
        "api_key": "",  # 无API key
    },
    "local_22003": {
        "base_url": f"http://{_get_env('LOCAL_22003_HOST', 'localhost')}:22003/v1",
        "api_key": "",
    },
    "local_22004": {
        "base_url": f"http://{_get_env('LOCAL_22004_HOST', 'localhost')}:22004/v1",
        "api_key": "",
    },
    "local_22005": {
        "base_url": f"http://{_get_env('LOCAL_22005_HOST', 'localhost')}:22005/v1",
        "api_key": "",
    },
    "local_22006": {
        "base_url": f"http://{_get_env('LOCAL_22006_HOST', 'localhost')}:22006/v1",
        "api_key": "",
    },
    "local_22007": {
        "base_url": f"http://{_get_env('LOCAL_22007_HOST', 'localhost')}:22007/v1",
        "api_key": "",
    },
    "local_2434": {
        "base_url": f"http://{_get_env('LOCAL_2434_HOST', 'localhost')}:2434/v1",
        "api_key": "",
    },
    "local_2435": {
        "base_url": f"http://{_get_env('LOCAL_2435_HOST', 'localhost')}:2435/v1",
        "api_key": "",
    }
}

# ==================== 模型定义配置 ====================
MODEL_DEFINITIONS = {
    "doubao-seed-1-6-251015": {
        "base_url_key": "volces",
        "model": "doubao-seed-1-6-251015",
        "max_tokens": 25000,
        "timeout": 1200,
        "enable_thinking": True,
        "extra_body": {}
    },
    "GLM-4.6V": {
        "base_url_key": "openrouter",
        "model": "z-ai/GLM-4.6V",
        "max_tokens": 25000,
        "timeout": 1200,
        "enable_thinking": True,
        "extra_body": {}
    },
    "qwen-vl-max": {
        "base_url_key": "dashscope",
        "model": "qwen-vl-max",
        "max_tokens": 25000,
        "timeout": 1200,
        "stream": False,
        "enable_thinking": True,
        "extra_body": {}
    },
    "qwen3-vl-plus": {
        "base_url_key": "dashscope",
        "model": "qwen3-vl-plus",
        "max_tokens": 25000,
        "timeout": 1200,
        "stream": False,
        "enable_thinking": True,
        "extra_body": {}
    },
    "qwen-max": {  # 裁判模型
        "base_url_key": "dashscope",
        "model": "qwen-max",
        "max_tokens": 4096,  
        "temperature": 0.01,
        "timeout": 1200,
        "enable_thinking": False,
        "extra_body": {}
    },
    # 闭源模型（OpenRouter）
    "gpt-5.1-2025-11-13": {
        "base_url_key": "openrouter",
        "model": "openai/gpt-5.1",
        "max_tokens": 25000,
        "timeout": 1200,
        "enable_thinking": True,
        "extra_body": {}
    },
    "gemini-3-pro-preview": {
        "base_url_key": "openrouter",
        "model": "google/gemini-3-pro-preview",
        "max_tokens": 30000,
        "timeout": 1200,
        "enable_thinking": True,
        "extra_body": {}
    },
    "grok-4-1-fast-reasoning": {
        "base_url_key": "openrouter",
        "model": "x-ai/grok-4.1-fast",
        "max_tokens": 25000,
        "timeout": 1200,
        "enable_thinking": True,
        "extra_body": {}
    },
    "claude-sonnet-4-5-20250929": {
        "base_url_key": "openrouter",
        "model": "anthropic/claude-sonnet-4.5",
        "max_tokens": 25000,
        "timeout": 1200,
        "enable_thinking": True,
        "extra_body": {}
    },
    # 开源模型（本地推理）
    "qwen3-vl-235b-a22b-thinking": {
        "base_url_key": "local_8000",
        "model": "qwen-235b",
        "max_tokens": 25000,
        "timeout": 1200,
        #"enable_thinking": False,
        "extra_body": {}
    },
    "visfinr1": {
        "base_url_key": "local_8000",
        "model": "visfinr1",
        "max_tokens": 8196,
        "timeout": 1200,
        #"enable_thinking": False,
        "extra_body": {}
    },
    "qwen3-vl-32b-thinking": {
        "base_url_key": "local_22003",
        "model": "Qwen3-VL-32B-Thinking",
        "max_tokens": 25000,
        "timeout": 1200,
        #"enable_thinking": False,
        "extra_body": {}
    },
    "InternVL3_5-241B-A28B": {
        "base_url_key": "local_22004",
        "model": "InternVL3_5-241B-A28B",
        "max_tokens": 25000,
        "timeout": 1200,
        #"enable_thinking": True,
        "extra_body": {}
    },
    "InternVL3_5-30B-A3B": {
        "base_url_key": "local_22005",
        "model": "InternVL3_5-30B-A3B",
        "max_tokens": 25000,
        "timeout": 1200,
        #"enable_thinking": True,
        "extra_body": {}
    },
    "MiniCPM-V-4_5": {
        "base_url_key": "local_22006",
        "model": "MiniCPM-V-4_5",
        "max_tokens": 20000,
        "timeout": 1200,
        #"enable_thinking": False,
        "extra_body": {}
    },
    "Llama-3.2-11B-Vision": {
        "base_url_key": "local_22007",
        "model": "Llama-3.2-11B-Vision",
        "max_tokens": 25000,
        "timeout": 1200,
        #"enable_thinking": True,
        "extra_body": {}
    },
    "Qwen3-VL-8B-Thinking": {
        "base_url_key": "local_2434",
        "model": "Qwen3-VL-8B-Thinking",
        "max_tokens": 25000,
        "timeout": 1200,
        #"enable_thinking": False,
        "extra_body": {}
    },
    "Qwen3-VL-8B-Instruct": {
        "base_url_key": "local_2435",
        "model": "Qwen3-VL-8B-Instruct",
        "max_tokens": 25000,
        "timeout": 1200,
        #"enable_thinking": False,
        "extra_body": {}
    }
    #可以添加评测的模型
}

# ==================== 裁判模型配置 ====================
JUDGE_MODEL_CONFIG = {
    "name": "qwen-max",  # 指向 MODEL_DEFINITIONS 中的 key
    "enabled": True
}

# ==================== 用户画像配置 ====================
# 三种用户画像：beginner（小白）、retail（散户）、expert（专家）
USER_PROFILES = ["beginner", "retail", "expert", "expert_cot"]




# 从环境变量读取要评测的模型列表
# 环境变量 EVAL_MODELS：逗号分隔的模型名称列表，如 "doubao,GLM,qwenvlmax"
# 模型名称必须对应 MODEL_DEFINITIONS 中的 key
def get_eval_models() -> List[str]:
    """
    获取要评测的模型列表
    
    Returns:
        模型名称列表（对应 MODEL_DEFINITIONS 中的 key）
    """
    eval_models_str = _get_env("EVAL_MODELS", "")
    if not eval_models_str:
        # 如果没有设置环境变量，返回空列表（需要在脚本中设置）
        return []
    
    # 解析逗号分隔的模型列表
    models = [m.strip() for m in eval_models_str.split(",") if m.strip()]
    
    # 验证模型是否在 MODEL_DEFINITIONS 中
    valid_models = []
    for model in models:
        if model in MODEL_DEFINITIONS:
            valid_models.append(model)
        else:
            # 使用 print 而不是 logging，因为 logging 可能还未初始化
            print(f"警告：模型 '{model}' 不在 MODEL_DEFINITIONS 中，已跳过")
    
    return valid_models


################################
# 评测参数 & API_CONFIG 生成逻辑
################################

# ==================== 评测参数配置 ====================
# 支持从环境变量读取配置（优先级：环境变量 > 默认值）
def _get_int_env(key: str, default: int) -> int:
    """从环境变量读取整数配置"""
    value = _get_env(key, "")
    return int(value) if value and value.isdigit() else default


def _get_float_env(key: str, default: float) -> float:
    """从环境变量读取浮点数配置"""
    value = _get_env(key, "")
    try:
        return float(value) if value else default
    except ValueError:
        return default


def _get_bool_env(key: str, default: bool) -> bool:
    """从环境变量读取布尔配置"""
    value = _get_env(key, "")
    # 如果环境变量未设置（空字符串），返回默认值，避免把未设置的变量误判为 False
    if value == "":
        return default
    if value.lower() in ("true", "1", "yes", "on"):
        return True
    elif value.lower() in ("false", "0", "no", "off"):
        return False
    return default


# ==================== 评测全局配置 ====================

EVAL_CONFIG = {
    "max_retries": _get_int_env("EVAL_MAX_RETRIES", 3),  # API调用最大重试次数
    "retry_delay": _get_float_env("EVAL_RETRY_SLEEP", 1.0),  # 重试延迟（秒）
    "judge_max_retries": _get_int_env("EVAL_JUDGE_MAX_RETRIES", 3),  # 裁判模型最大重试次数
    "judge_retry_delay": _get_float_env("EVAL_JUDGE_RETRY_DELAY", 1.0),  # 裁判模型重试延迟（秒）
    "save_intermediate": True,  # 是否保存中间结果（断点续跑）
    "output_format": _get_env("EVAL_OUTPUT_FORMAT", "json"),  # 输出格式：json 或 jsonl
    "timeout": _get_int_env("EVAL_TIMEOUT", 600),  # API超时时间（秒）
    "batch_size": _get_int_env("EVAL_BATCH_SIZE", 10),  # JSON格式批量写入大小
    # 图片压缩配置
    "image_compress_threshold": _get_int_env("EVAL_IMAGE_COMPRESS_THRESHOLD", 5),  # 超过此数量的图片将自动压缩
    "image_compress_max_longest_side": _get_int_env("EVAL_IMAGE_COMPRESS_MAX_LONGEST_SIDE", 1600),  # 压缩后最长边的最大像素值（范围建议1280-1600）
    "image_compress_quality": _get_int_env("EVAL_IMAGE_COMPRESS_QUALITY", 92),  # JPEG压缩质量（1-100），默认92保证较高画质
    "compress_single_image_single_round": _get_bool_env("EVAL_COMPRESS_SINGLE_IMAGE_SINGLE_ROUND", False),  # 单图单轮是否压缩（默认False，不压缩）
    # 动态分辨率调整配置（用于控制输入token在25k以内）
    "enable_dynamic_resolution": _get_bool_env("EVAL_ENABLE_DYNAMIC_RESOLUTION", True),  # 是否启用动态分辨率调整
    "max_input_tokens": _get_int_env("EVAL_MAX_INPUT_TOKENS", 25000),  # 最大输入token数（默认25k，为32k上下文留出余量）
    "min_resolution": _get_int_env("EVAL_MIN_RESOLUTION", 512),  # 最小分辨率（最长边，防止图片过小）
    "max_resolution": _get_int_env("EVAL_MAX_RESOLUTION", 2048),  # 最大分辨率（最长边，初始值）
    "multi_round_count_by_rounds": _get_bool_env(
        "EVAL_MULTI_ROUND_COUNT_BY_ROUNDS", True
    ),  # 多轮题目是否按轮次计分（True=每轮算1题，False=整题算1题）
    "skip_missing_images": _get_bool_env(
        "EVAL_SKIP_MISSING_IMAGES", False
    ),  # 图片缺失时是否跳过题目（False=跳过题目，True=继续评测但不包含图片）
}


# ==================== 动态生成 API_CONFIG ====================
# 规则：
# 1. 能被 OpenAI 兼容接口直接识别的超参数（model / max_tokens / temperature / top_p /
#    frequency_penalty / presence_penalty / stream / timeout 等），直接放到顶层。
# 2. 其它「不能直接读取」的参数（如 enable_thinking 之类的思考参数），自动合并进 extra_body，
#    同时在 API_CONFIG 顶层也保留一份，方便框架内部判断。
# 3. 如果用户在 MODEL_DEFINITIONS 里显式写了 extra_body，则自动在此基础上合并。

API_CONFIG: Dict[str, Dict[str, Any]] = {}

# 顶层直传给 chat.completions.create 的标准字段
_TOP_LEVEL_KEYS = {
    "model",
    "max_tokens",
    "temperature",
    "top_p",
    "frequency_penalty",
    "presence_penalty",
    "stream",
    "timeout",
}

for model_key, model_def in MODEL_DEFINITIONS.items():
    base_url_key = model_def.get("base_url_key")
    if base_url_key not in BASE_URL_CONFIG:
        raise ValueError(
            f"模型 '{model_key}' 的 base_url_key '{base_url_key}' 在 BASE_URL_CONFIG 中不存在。"
        )

    base_url_config = BASE_URL_CONFIG[base_url_key]

    # 基础必需字段
    api_conf: Dict[str, Any] = {
        "base_url": base_url_config["base_url"],
        "api_key": base_url_config["api_key"],
        "model": model_def["model"],
    }

    # 已有的 extra_body（用户显式配置）
    merged_extra_body: Dict[str, Any] = model_def.get("extra_body", {}).copy()

    # 遍历模型定义中的所有字段，自动拆分：
    # - 标准顶层参数：直接挂到 api_conf
    # - 其它参数：既保留在 api_conf 方便内部使用，也自动塞进 extra_body，保证请求体能拿到
    for k, v in model_def.items():
        if k in ("base_url_key", "extra_body", "model"):
            continue

        if k in _TOP_LEVEL_KEYS:
            api_conf[k] = v
        else:
            # 非标准字段（如 enable_thinking、未来扩展的 vendor 参数等）
            api_conf[k] = v
            # 放进 extra_body，保证请求体能拿到
            if k not in merged_extra_body:
                merged_extra_body[k] = v

    # 如果模型里根本没配 timeout，就给个默认的
    if "timeout" not in api_conf:
        api_conf["timeout"] = 600
    # 如果没配 max_tokens，也给个默认
    if "max_tokens" not in api_conf:
        api_conf["max_tokens"] = 8192

    api_conf["extra_body"] = merged_extra_body

    API_CONFIG[model_key] = api_conf

