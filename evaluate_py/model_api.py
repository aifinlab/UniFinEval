"""
模型API调用模块
支持调用各种视觉语言模型的API
"""
import os
import sys
import base64
import time
import logging
import re
import json
import io
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from openai import OpenAI
from .config import API_CONFIG, EVAL_CONFIG

# 尝试导入PIL/Pillow用于图片压缩
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    logging.warning("PIL/Pillow未安装，图片压缩功能将不可用。建议安装: pip install Pillow")


def compress_image(image_path: str, max_longest_side: int = 1600, quality: int = 92, force_jpeg: bool = False) -> bytes:
    """
    智能图像压缩工具 - 专为多模态大模型多图输入设计
    
    重要规则：
    1. 分辨率定义为"最长边 (Max Edge)"，而非固定宽高
    2. 小图不要放大：如果原图最长边 <= max_longest_side，保持原尺寸，不放大
    3. 大图按比例缩小：如果原图最长边 > max_longest_side，保持宽高比缩放，使得 max(w, h) <= max_longest_side
    
    Args:
        image_path: 图片路径
        max_longest_side: 最长边的最大像素值，默认 1600（范围建议 1280-1600）
        quality: JPEG质量（1-100），默认92，当force_jpeg=True时使用此参数
        force_jpeg: 是否强制输出JPEG格式（多图场景推荐使用），默认False
        
    Returns:
        压缩后的图片字节数据
    """
    if not PIL_AVAILABLE:
        # 如果PIL不可用，直接读取原图
        with open(image_path, "rb") as f:
            return f.read()
    
    try:
        # 1. 读取图片
        if isinstance(image_path, str):
            if not os.path.exists(image_path):
                logging.warning(f"Warning: Image not found {image_path}")
                return b""
            img = Image.open(image_path)
        else:
            img = image_path
        
        original_width, original_height = img.size
        original_longest_side = max(original_width, original_height)
        
        # 2. 处理透明通道 (RGBA/P -> RGB)
        # 很多图表是透明底 PNG，直接转 JPG 会变全黑，必须填充白色背景
        if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1])
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        
        # 3. 智能缩放 (Lanczos 算法)
        longest_side = max(img.size)
        
        # 只有当原图 > 目标尺寸时才缩小，坚决不放大
        if longest_side > max_longest_side:
            ratio = max_longest_side / longest_side
            new_width = int(original_width * ratio)
            new_height = int(original_height * ratio)
            # 核心：使用 LANCZOS 滤镜，确保文字锐利
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            logging.info(f"🖼️ 图片压缩: {os.path.basename(image_path) if isinstance(image_path, str) else 'Image'} 原尺寸 {original_width}x{original_height} (最长边={original_longest_side}px) -> 压缩到 {new_width}x{new_height} (最长边={max_longest_side}px)")
        else:
            logging.info(f"🖼️ 图片压缩: {os.path.basename(image_path) if isinstance(image_path, str) else 'Image'} 原尺寸 {original_width}x{original_height} (最长边={original_longest_side}px) <= {max_longest_side}px，保持原尺寸（无需压缩）")
        
        # 4. 导出为高画质 JPEG（当force_jpeg=True时）或根据原格式
        output = io.BytesIO()
        if force_jpeg:
            # 强制使用JPEG格式（多图场景推荐）
            img.save(output, format="JPEG", quality=quality, optimize=True)
        else:
            # 根据原图格式选择保存格式（兼容旧逻辑）
            format_ext = Path(image_path).suffix.lower() if isinstance(image_path, str) else '.jpg'
            if format_ext in ['.jpg', '.jpeg']:
                img.save(output, format='JPEG', quality=quality, optimize=True)
            elif format_ext == '.png':
                # PNG格式使用optimize参数，保持原格式
                img.save(output, format='PNG', optimize=True)
            else:
                # 其他格式转换为JPEG
                img.save(output, format='JPEG', quality=quality, optimize=True)
        
        output.seek(0)
        return output.read()
        
    except Exception as e:
        logging.warning(f"图片压缩失败 {image_path}: {e}，使用原图")
        # 压缩失败时返回原图
        try:
            if isinstance(image_path, str):
                with open(image_path, "rb") as f:
                    return f.read()
            else:
                return b""
        except:
            return b""


def encode_image(image_path: str, compress: bool = False, max_longest_side: int = 1600, quality: int = 92) -> str:
    """
    将图片编码为 base64
    
    Args:
        image_path: 图片路径
        compress: 是否压缩图片，默认False
        max_longest_side: 压缩时的最长边最大像素值，默认 1600（范围建议 1280-1600）
        quality: JPEG质量（1-100），默认92，仅对JPEG格式有效
        
    Returns:
        base64 编码的图片字符串
    """
    if compress:
        # 压缩时强制使用JPEG格式
        force_jpeg = True
        image_data = compress_image(image_path, max_longest_side=max_longest_side, quality=quality, force_jpeg=force_jpeg)
        logging.debug(f"✅ 图片压缩完成: {os.path.basename(image_path)}, 压缩后大小={len(image_data)} bytes")
    else:
        with open(image_path, "rb") as image_file:
            image_data = image_file.read()
        logging.debug(f"⏭️ 跳过压缩: {os.path.basename(image_path)}, 使用原图 (大小={len(image_data)} bytes)")
    
    return base64.b64encode(image_data).decode('utf-8')


def get_image_format(image_path: str) -> str:
    """
    获取图片格式（用于 data URI）
    
    Args:
        image_path: 图片路径
        
    Returns:
        图片格式（如 jpeg, png）
    """
    suffix = Path(image_path).suffix.lower().replace('.', '')
    if suffix == 'jpg':
        return 'jpeg'
    return suffix if suffix in ['jpeg', 'png', 'webp', 'gif'] else 'jpeg'


def estimate_text_tokens(text: str) -> int:
    """
    估算文本的token数量
    使用简单估算：1 token ≈ 4 字符（对于中文和英文混合文本）
    
    Args:
        text: 文本内容
        
    Returns:
        估算的token数量
    """
    if not text:
        return 0
    # 简单估算：1 token ≈ 4 字符
    # 对于中文，可能更接近 1 token ≈ 1.5 字符，但为了保守估计，使用 4 字符
    return len(text) // 4 + 1


def estimate_image_tokens(image_path: str, width: Optional[int] = None, height: Optional[int] = None) -> int:
    """
    估算图片的token数量 (修正版：适配 Qwen/Llama Patch 机制)
    
    使用 Qwen/Llama Vision Patch 机制：
    - Patch size 通常是 14x14
    - Token数 = (H/14) * (W/14) + overhead
    - 这是 Qwen/Llama 等开源模型的真实消耗逻辑
    
    Args:
        image_path: 图片路径
        width: 图片宽度（可选，如果不提供则从文件读取）
        height: 图片高度（可选，如果不提供则从文件读取）
        
    Returns:
        估算的token数量
    """
    # 如果PIL不可用，给一个比较大的安全值
    if not PIL_AVAILABLE:
        return 2000
    
    try:
        if width is None or height is None:
            with Image.open(image_path) as img:
                width, height = img.size
        
        # Qwen/Llama Vision Patch size 通常是 14
        # 加上 ceil 向上取整，保证估算不会偏小
        patches_w = (width + 13) // 14
        patches_h = (height + 13) // 14
        
        # 基础 Token 数
        base_tokens = patches_w * patches_h
        
        # 加上特殊标记 Overhead (Vision Start, End 等)，给 128 安全余量
        return base_tokens + 128

    except Exception as e:
        logging.warning(f"估算图片token失败 {image_path}: {e}，使用保守估算")
        return 2000


def get_image_size(image_path: str) -> Tuple[int, int]:
    """
    获取图片尺寸
    
    Args:
        image_path: 图片路径
        
    Returns:
        (width, height)
    """
    if not PIL_AVAILABLE:
        return (1024, 1024)  # 默认值
    
    try:
        with Image.open(image_path) as img:
            return img.size
    except Exception as e:
        logging.warning(f"获取图片尺寸失败 {image_path}: {e}")
        return (1024, 1024)  # 默认值


def _determine_image_compression_settings(
    image_paths: List[str],
    is_multi_round: bool = False
) -> Tuple[bool, int, int]:
    """
    确定图片压缩设置（提取的公共逻辑）
    
    Args:
        image_paths: 图片路径列表
        is_multi_round: 是否是多轮对话（多轮对话时强制压缩以节省token）
        
    Returns:
        (should_compress, max_longest_side, quality)
        - should_compress: 是否启用压缩
        - max_longest_side: 压缩后的最长边像素值
        - quality: JPEG压缩质量
    """
    if not image_paths:
        return False, 1600, 92
    
    num_images = len(image_paths)
    
    # 压缩策略：
    # 1. 单图单轮：根据配置决定是否压缩（默认不压缩，可通过 EVAL_COMPRESS_SINGLE_IMAGE_SINGLE_ROUND 环境变量或配置启用）
    # 2. 单图多轮：压缩到1024px，转换为JPEG
    # 3. 多图单轮：压缩到512px，转换为JPEG
    # 4. 多图多轮：压缩到512px，转换为JPEG
    if num_images > 1:
        # 多图场景：压缩到512px
        should_compress = True
        max_longest_side = 512
        quality = 85
        if is_multi_round:
            logging.info(f"📸 图片压缩策略: 检测到 {num_images} 张图片（多图多轮），使用配置（512px, quality=85, JPEG）")
        else:
            logging.info(f"📸 图片压缩策略: 检测到 {num_images} 张图片（多图单轮），使用配置（512px, quality=85, JPEG）")
        return should_compress, max_longest_side, quality
    elif is_multi_round:
        # 单图多轮：压缩到1024px
        should_compress = True
        max_longest_side = 1024
        quality = 92
        logging.info(f"📸 图片压缩策略: 检测到 1 张图片（单图多轮），使用配置（1024px, quality=92, JPEG）")
        return should_compress, max_longest_side, quality
    
    # 单图单轮：根据配置决定是否压缩
    should_compress = EVAL_CONFIG.get("compress_single_image_single_round", False)
    max_longest_side = EVAL_CONFIG.get("image_compress_max_longest_side", 1600)
    quality = EVAL_CONFIG.get("image_compress_quality", 92)
    
    if should_compress:
        logging.info(f"📸 图片压缩策略: 检测到 1 张图片（单图单轮），已启用压缩（{max_longest_side}px, quality={quality}, JPEG）")
    else:
        logging.info(f"📸 图片压缩策略: 检测到 1 张图片（单图单轮），未启用压缩，保持原图格式和尺寸")
    return should_compress, max_longest_side, quality


def call_model_api(
    model_name: str,
    prompt: str = None,
    image_paths: Optional[List[str]] = None,
    max_retries: Optional[int] = None,
    retry_delay: Optional[float] = None,
    messages: Optional[List[Dict[str, Any]]] = None
) -> Tuple[str, float, Dict[str, Any]]:
    """
    调用模型API
    
    Args:
        model_name: 模型名称（对应 API_CONFIG 中的 key）
        prompt: 提示词（如果提供了 messages，则忽略此参数）
        image_paths: 图片路径列表（可选，仅在未提供 messages 时使用）
        max_retries: 最大重试次数（默认使用配置）
        retry_delay: 重试延迟（默认使用配置）
        messages: 对话历史消息列表（可选，格式：[{"role": "user", "content": ...}, {"role": "assistant", "content": ...}, ...]）
                 如果提供了 messages，将使用它而不是 prompt 和 image_paths
        
    Returns:
        (answer, response_time, raw_response)
        - answer: 模型回答
        - response_time: 响应时间（秒）
        - raw_response: 原始API响应（字典格式）
    """
    if model_name not in API_CONFIG:
        raise ValueError(f"模型 '{model_name}' 不在 API_CONFIG 中")
    
    api_config = API_CONFIG[model_name]
    max_retries = max_retries or EVAL_CONFIG.get("max_retries", 3)
    retry_delay = retry_delay or EVAL_CONFIG.get("retry_delay", 1)
    
    # 超时时间：优先使用 EVAL_CONFIG 中的 timeout，其次使用模型配置中的 timeout
    timeout = EVAL_CONFIG.get("timeout") or api_config.get("timeout", 600)
    
    # 创建 OpenAI 客户端，timeout 应该在客户端初始化时设置
    client = OpenAI(
        base_url=api_config["base_url"],
        api_key=api_config["api_key"],
        timeout=timeout
    )
    
    # 如果提供了 messages，直接使用；否则构建单条消息
    if messages is not None:
        # 使用提供的对话历史
        # 如果第一条消息是 user 且需要添加图片，检查是否已经包含图片
        if messages and len(messages) > 0:
            first_msg = messages[0]
            if first_msg.get("role") == "user" and image_paths:
                user_content = first_msg.get("content", [])
                if isinstance(user_content, str):
                    user_content = [{"type": "text", "text": user_content}]
                elif not isinstance(user_content, list):
                    user_content = []
                
                # 检查第一条消息是否已经包含图片（避免重复添加）
                has_image_in_first_msg = any(
                    isinstance(item, dict) and item.get("type") == "image_url"
                    for item in user_content
                )
                
                if not has_image_in_first_msg:
                    # 第一条消息中没有图片，需要添加图片
                    # 估算文本token（从所有消息中提取文本）
                    text_content = ""
                    for msg in messages:
                        content = msg.get("content", "")
                        if isinstance(content, str):
                            text_content += content
                        elif isinstance(content, list):
                            for item in content:
                                if isinstance(item, dict) and item.get("type") == "text":
                                    text_content += item.get("text", "")
                    
                    # 确定图片压缩设置（使用公共函数）
                    # messages场景通常是多轮对话
                    is_multi_round = len(messages) > 1 or any(msg.get("role") == "assistant" for msg in messages)
                    should_compress, max_longest_side, quality = _determine_image_compression_settings(
                        image_paths=image_paths,
                        is_multi_round=is_multi_round
                    )
                    
                    # 添加图片到第一条消息
                    for image_path in image_paths:
                        if image_path.startswith(("http://", "https://")):
                            user_content.append({
                                "type": "image_url",
                                "image_url": {"url": image_path}
                            })
                        elif os.path.exists(image_path):
                            # 如果压缩，强制使用 JPEG 格式；如果不压缩，保持原格式
                            if should_compress:
                                image_format = 'jpeg'
                            else:
                                image_format = get_image_format(image_path)
                            base64_image = encode_image(image_path, compress=should_compress, max_longest_side=max_longest_side, quality=quality)
                            user_content.append({
                                "type": "image_url",
                                "image_url": {"url": f"data:image/{image_format};base64,{base64_image}"}
                            })
                        else:
                            logging.warning(f"图片文件不存在或URL无效: {image_path}")
                            continue
                    
                    messages[0]["content"] = user_content
                else:
                    # 第一条消息已经包含图片，不再重复添加
                    logging.debug("第一条消息已经包含图片，跳过重复添加")
    else:
        # 构建单条消息（原有逻辑）
        if prompt is None:
            raise ValueError("必须提供 prompt 或 messages 参数")
        
        user_content = []
        
        # 添加所有图片（支持多图输入，数组中的所有图片都会被添加到消息中）
        if image_paths:
            # 确定图片压缩设置（使用公共函数）
            # prompt场景通常是单轮对话
            should_compress, max_longest_side, quality = _determine_image_compression_settings(
                image_paths=image_paths,
                is_multi_round=False
            )
            
            logging.debug(f"准备添加 {len(image_paths)} 张图片到消息中")
            for image_path in image_paths:
                # 判断是URL还是本地路径
                if image_path.startswith(("http://", "https://")):
                    # URL格式，直接使用
                    user_content.append({
                        "type": "image_url",
                        "image_url": {"url": image_path}
                    })
                elif os.path.exists(image_path):
                    # 本地文件，编码为base64
                    # 如果压缩，强制使用 JPEG 格式；如果不压缩，保持原格式
                    if should_compress:
                        image_format = 'jpeg'
                    else:
                        image_format = get_image_format(image_path)
                    base64_image = encode_image(image_path, compress=should_compress, max_longest_side=max_longest_side, quality=quality)
                    user_content.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/{image_format};base64,{base64_image}"}
                    })
                else:
                    logging.warning(f"图片文件不存在或URL无效，已跳过: {image_path}")
                    continue
        
        # 添加文本提示词
        user_content.append({"type": "text", "text": prompt})
        
        messages = [{"role": "user", "content": user_content}]
    
    # 构建API调用参数
    # 注意：timeout 已经在客户端初始化时设置，不需要在 api_params 中传递

    api_params = {
        "model": api_config["model"],
        "messages": messages,
        "max_tokens": api_config.get("max_tokens", 8192),
    }

    # 可选参数：只在 config 中存在时才添加（与 module2 保持一致风格）
    if "temperature" in api_config:
        api_params["temperature"] = api_config["temperature"]
    if "top_p" in api_config:
        api_params["top_p"] = api_config["top_p"]
    if "frequency_penalty" in api_config:
        api_params["frequency_penalty"] = api_config["frequency_penalty"]
    if "presence_penalty" in api_config:
        api_params["presence_penalty"] = api_config["presence_penalty"]
    if "stream" in api_config:
        api_params["stream"] = api_config["stream"]

    # 处理 extra_body（某些API的特殊参数，比如思考模式 enable_thinking 等）
    # 在 config 中，我们已经把所有「非标准顶层参数」自动合并进了 extra_body，
    # 这里直接整体透传即可，兼容单轮 / 多轮。
    extra_body = api_config.get("extra_body", {})
    if extra_body:
        api_params["extra_body"] = extra_body
    
    # 重试机制
    last_error = None
    for attempt in range(max_retries):
        try:
            # 记录API调用信息（用于调试）
            if attempt == 0:
                logging.info(f"📡 开始调用模型API: {model_name} (base_url: {api_config['base_url']}, timeout: {timeout}s)")
            else:
                logging.info(f"📡 重试调用模型API: {model_name} (尝试 {attempt + 1}/{max_retries})")
            
            start_time = time.time()
            response = client.chat.completions.create(**api_params)
            response_time = time.time() - start_time
            
            logging.info(f"✅ API调用成功: {model_name} (耗时: {response_time:.2f}s)")
            
            if not response.choices or len(response.choices) == 0:
                # 在详细模式下，记录完整的API响应以便调试
                log_mode = os.getenv("EVAL_LOG_MODE", "detailed")
                if log_mode.lower() == "detailed":
                    try:
                        # 尝试将响应对象转换为字典
                        if hasattr(response, "model_dump"):
                            response_dict = response.model_dump()
                        elif hasattr(response, "dict"):
                            response_dict = response.dict()
                        elif isinstance(response, dict):
                            response_dict = response
                        else:
                            # 手动构建响应字典，获取常见属性
                            response_dict = {}
                            common_attrs = ['id', 'object', 'created', 'model', 'choices', 'usage', 'system_fingerprint', 'error']
                            for attr in common_attrs:
                                if hasattr(response, attr):
                                    try:
                                        value = getattr(response, attr)
                                        # 尝试序列化
                                        try:
                                            json.dumps(value, default=str)
                                            response_dict[attr] = value
                                        except (TypeError, ValueError):
                                            response_dict[attr] = str(value)
                                    except Exception:
                                        pass
                            
                            # 如果还是没有获取到内容，尝试获取所有公共属性
                            if not response_dict:
                                for attr in dir(response):
                                    if not attr.startswith('_') and not callable(getattr(response, attr, None)):
                                        try:
                                            value = getattr(response, attr, None)
                                            if value is not None:
                                                try:
                                                    json.dumps(value, default=str)
                                                    response_dict[attr] = value
                                                except (TypeError, ValueError):
                                                    response_dict[attr] = str(value)
                                        except Exception:
                                            pass
                        
                        # 记录完整的响应内容
                        response_json = json.dumps(response_dict, ensure_ascii=False, indent=2, default=str)
                        logging.error(f"⚠️ API响应中没有choices字段，完整响应内容：\n{response_json}")
                    except Exception as log_error:
                        logging.error(f"⚠️ API响应中没有choices字段，且无法序列化响应对象: {log_error}")
                        logging.error(f"响应对象类型: {type(response)}")
                        # 尝试至少记录一些基本信息
                        try:
                            if hasattr(response, 'id'):
                                logging.error(f"响应ID: {response.id}")
                            if hasattr(response, 'model'):
                                logging.error(f"响应模型: {response.model}")
                            if hasattr(response, 'error'):
                                logging.error(f"响应错误: {response.error}")
                        except Exception:
                            pass
                raise ValueError("API响应中没有choices字段")
            
            answer = response.choices[0].message.content
            if not answer:
                raise ValueError("API响应内容为空")
            
            # 提取token使用信息
            prompt_tokens = None
            completion_tokens = None
            total_tokens = None
            if hasattr(response, 'usage') and response.usage:
                prompt_tokens = getattr(response.usage, 'prompt_tokens', None)
                completion_tokens = getattr(response.usage, 'completion_tokens', None)
                total_tokens = getattr(response.usage, 'total_tokens', None)
            
            # 打印token使用信息到终端日志
            if prompt_tokens is not None or completion_tokens is not None or total_tokens is not None:
                token_info = []
                if prompt_tokens is not None:
                    token_info.append(f"输入token={prompt_tokens}")
                if completion_tokens is not None:
                    token_info.append(f"输出token={completion_tokens}")
                if total_tokens is not None:
                    token_info.append(f"总token={total_tokens}")
                logging.info(f"📊 Token使用: {', '.join(token_info)}")
            
            # 保存完整的原始响应（用于详细日志）
            try:
                if hasattr(response, "model_dump"):
                    raw_response = response.model_dump()
                elif isinstance(response, dict):
                    raw_response = response
                else:
                    # 手动构建完整响应字典
                    raw_response = {
                        "id": getattr(response, "id", None),
                        "object": getattr(response, "object", None),
                        "created": getattr(response, "created", None),
                        "model": getattr(response, "model", None),
                        "usage": {
                            "prompt_tokens": prompt_tokens,
                            "completion_tokens": completion_tokens,
                            "total_tokens": total_tokens,
                        } if (prompt_tokens is not None or completion_tokens is not None or total_tokens is not None) else None,
                    }
                    if hasattr(response, "choices") and len(response.choices) > 0:
                        choice = response.choices[0]
                        choice_dict = {
                            "index": getattr(choice, "index", None),
                            "finish_reason": getattr(choice, "finish_reason", None),
                        }
                        if hasattr(choice, "message"):
                            message = choice.message
                            message_dict = {
                                "role": getattr(message, "role", None),
                                "content": getattr(message, "content", None),
                            }
                            # 详细日志模式下：保留所有reasoning字段，不按优先级过滤
                            # 这样详细日志可以显示所有思考内容
                            if hasattr(message, "reasoning") and getattr(message, "reasoning", None):
                                message_dict["reasoning"] = getattr(message, "reasoning")
                            if hasattr(message, "reasoning_content") and getattr(message, "reasoning_content", None):
                                message_dict["reasoning_content"] = getattr(message, "reasoning_content")
                            if hasattr(message, "reasoning_details") and getattr(message, "reasoning_details", None):
                                message_dict["reasoning_details"] = getattr(message, "reasoning_details")
                            choice_dict["message"] = message_dict
                        raw_response["choices"] = [choice_dict]
            except Exception as e:
                logging.warning(f"无法序列化完整响应对象: {e}")
                # 降级：只保存基本信息
                raw_response = {
                    "model": response.model if hasattr(response, 'model') else None,
                    "usage": {
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "total_tokens": total_tokens,
                    } if (prompt_tokens is not None or completion_tokens is not None or total_tokens is not None) else None
                }
            
            return answer, response_time, raw_response
            
        except Exception as e:
            last_error = e
            # 记录详细的错误信息（用于调试）
            error_type = type(e).__name__
            error_msg = str(e)
            logging.error(f"❌ API调用异常: {error_type} - {error_msg}")
            
            # 如果是连接相关错误，记录更多信息
            if "timeout" in error_msg.lower() or "connection" in error_msg.lower():
                logging.error(f"   连接信息: base_url={api_config['base_url']}, timeout={timeout}s")
            elif "Invalid HTTP request" in error_msg or "400" in error_msg or "Bad Request" in error_msg:
                logging.error(f"   请求参数: model={api_config['model']}, messages数量={len(messages)}")
                logging.error(f"   可能是请求格式问题，请检查 extra_body 和其他参数")
            
            if attempt < max_retries - 1:
                wait_time = retry_delay * (2 ** attempt)  # 指数退避
                logging.warning(f"API调用失败（尝试 {attempt + 1}/{max_retries}）: {e}，{wait_time:.1f}秒后重试...")
                time.sleep(wait_time)
            else:
                logging.error(f"API调用失败（已重试 {max_retries} 次）: {e}")
                raise
    
    # 如果所有重试都失败
    raise Exception(f"API调用失败: {last_error}")


def extract_boxed_content(text: str) -> Optional[str]:
    """
    从文本中提取 \\boxed{} 中的内容，支持嵌套大括号
    
    Args:
        text: 输入文本
        
    Returns:
        提取的内容，如果未找到则返回 None
    """
    # 手动查找所有 \\boxed{ ... } 配对，支持嵌套大括号
    all_matches = []
    pos = 0
    
    while True:
        # 查找下一个 \\boxed{
        start_idx = text.find('\\boxed{', pos)
        if start_idx == -1:
            break
        
        # 从 \\boxed{ 后面开始匹配大括号
        brace_start = start_idx + len('\\boxed{')
        depth = 0
        end_idx = -1
        
        for i in range(brace_start, len(text)):
            if text[i] == '{':
                depth += 1
            elif text[i] == '}':
                if depth == 0:
                    # 找到匹配的右大括号
                    end_idx = i
                    break
                else:
                    depth -= 1
        
        if end_idx != -1:
            # 提取内容
            content = text[brace_start:end_idx].strip()
            if content:
                all_matches.append(content)
            pos = end_idx + 1
        else:
            # 未找到匹配的右大括号，跳过这个 \\boxed{
            pos = brace_start
    
    # 返回最后一个匹配（通常是最终答案）
    return all_matches[-1] if all_matches else None


def extract_json_from_text(text: str) -> Dict[str, Any]:
    """
    从文本中提取JSON对象（参考 model1.py）
    
    Args:
        text: 输入文本
        
    Returns:
        提取的JSON字典，如果未找到则返回空字典
    """
    text = text.strip()
    # 尝试匹配 ```json {...} ``` 或 {...}
    pattern = r"```json\s*(\{.*?\})\s*```|(\{.*\})"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        json_str = match.group(1) or match.group(2)
        try:
            return json.loads(json_str)
        except:
            pass
    
    # 如果没找到代码块，尝试直接寻找JSON
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1:
        try:
            return json.loads(text[start:end+1])
        except:
            pass
    
    return {}


def extract_answer_by_keywords(text: str) -> Optional[str]:
    """
    通过关键词模式提取答案（参考 model1.py）
    
    Args:
        text: 输入文本
        
    Returns:
        提取的答案，如果未找到则返回 None
    """
    # 查找 "答案是"、"答案："、"Answer:" 等关键词后的内容
    answer_patterns = [
        r'答案是[：:]\s*(.+?)(?:\n|$)',
        r'答案[：:]\s*(.+?)(?:\n|$)',
        r'Answer[：:]\s*(.+?)(?:\n|$)',
        r'最终答案[：:]\s*(.+?)(?:\n|$)',
        r'答案为[：:]\s*(.+?)(?:\n|$)',
        r'答案是\s*(.+?)(?:\n|$)',
    ]
    for pattern in answer_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            answer_content = match.group(1).strip()
            # 清理可能的标点符号
            answer_content = answer_content.rstrip('。，,')
            if answer_content:
                return answer_content
    return None


def truncate_last_n_tokens(text: str, n_tokens: int = 100) -> str:
    """
    截取文本的最后 N 个 token
    
    Args:
        text: 输入文本
        n_tokens: 要截取的 token 数量，默认 100
        
    Returns:
        截取后的文本（最后 N 个 token）
    """
    if not text:
        return ""
    
    # 估算总 token 数
    total_tokens = estimate_text_tokens(text)
    
    # 如果文本的 token 数小于等于目标 token 数，直接返回
    if total_tokens <= n_tokens:
        return text
    
    # 计算需要截取的字符数（保守估计：1 token ≈ 4 字符）
    # 为了确保能截取到足够的 token，我们使用更保守的估算
    target_chars = n_tokens * 4
    
    # 从末尾截取
    truncated = text[-target_chars:]
    
    # 如果截取后的 token 数仍然超过目标，继续调整
    while estimate_text_tokens(truncated) > n_tokens and len(truncated) > 0:
        # 每次减少 10% 的字符
        truncated = truncated[int(len(truncated) * 0.9):]
    
    return truncated


def extract_answer_from_response(response: str, has_options: bool = False) -> tuple:
    """
    从模型响应中提取答案（参考 model1.py 的多层 fallback 机制）
    
    提取策略（按优先级）：
    1. 从 \\boxed{} 中提取（支持嵌套大括号）
    2. 从 JSON 格式中提取（兼容旧格式）
    3. 如果 box 为空，使用 content 的最后一百个 token 截断
    4. 如果都没有，返回完整响应（保底机制）
    
    Args:
        response: 模型原始响应
        has_options: 是否是选择题（保留参数以兼容现有调用，但不再使用）
        
    Returns:
        (extracted_answer, is_from_box, original_response)
        - extracted_answer: 提取的答案
        - is_from_box: 是否从 \\boxed{} 中提取（True表示从box中提取，False表示使用完整响应）
        - original_response: 原始完整响应（用于fallback）
    """
    original_response = response.strip()
    response = original_response
    
    # ==================== 策略1: 从 \\boxed{} 中提取（支持嵌套大括号） ====================
    boxed_content = extract_boxed_content(response)
    if boxed_content:
        # 从 box 中成功提取到内容
        logging.debug(f"从 \\boxed{{}} 中提取到答案: {boxed_content[:100]}")
        return boxed_content, True, original_response
    
    # ==================== 策略2: 从 JSON 格式中提取（兼容旧格式） ====================
    result_json = extract_json_from_text(response)
    if result_json:
        answer_wrapped = result_json.get("answer", "")
        if answer_wrapped:
            # 尝试从 JSON 的 answer 字段中提取 boxed 格式
            answer_from_json_box = extract_boxed_content(answer_wrapped)
            if answer_from_json_box:
                logging.debug(f"从 JSON 格式的 \\boxed{{}} 中提取到答案: {answer_from_json_box[:100]}")
                return answer_from_json_box, True, original_response
            else:
                # 如果没有 boxed 格式，直接使用 answer 内容
                answer_cleaned = answer_wrapped.strip()
                if answer_cleaned:
                    logging.debug(f"从 JSON 格式中提取到答案: {answer_cleaned[:100]}")
                    return answer_cleaned, False, original_response
    
    # ==================== 策略3: 如果 box 为空，使用 content 的最后一百个 token 截断 ====================
    # 如果执行到这里，说明前面的策略都没有从 box 中提取到内容（box 为空）
    # 使用最后100个token截断作为输入给裁判模型
    truncated_content = truncate_last_n_tokens(original_response, n_tokens=100)
    if truncated_content and truncated_content.strip():
        logging.debug(f"Box为空，使用最后100个token截断: {truncated_content[:100]}...")
        return truncated_content, False, original_response
    
    # ==================== 策略4: 如果都没有提取到，返回完整响应（保底机制） ====================
    logging.debug("未能从任何策略中提取到答案，使用完整响应作为保底")
    return original_response, False, original_response
