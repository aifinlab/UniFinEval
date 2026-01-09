"""
裁判模型模块
使用裁判模型判断模型答案与标准答案是否一致
"""
import os
import sys
import json
import time
import logging
import re
from typing import Optional, Dict, Any, Tuple

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from openai import OpenAI
from .config import API_CONFIG, JUDGE_MODEL_CONFIG, EVAL_CONFIG


def clean_json_text(text: str) -> str:
    """
    从模型输出中提取 JSON 字符串
    兼容模型输出 ```json ... ``` 包裹的情况
    """
    text = text.strip()
    # 尝试匹配 ```json {...} ``` 或 {...}
    pattern = r"```json\s*(\{.*?\})\s*```|(\{.*\})"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1) or match.group(2)
    
    # 如果没找到代码块，尝试直接寻找左右大括号包裹的内容
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1:
        return text[start:end+1]
    
    return text


def judge_answer(
    model_answer: str,
    gt_answer: str,
    question: str,
    options: Optional[dict] = None,
    max_retries: Optional[int] = None,
    retry_delay: Optional[float] = None
) -> Tuple[bool, str, float, Optional[dict], str]:
    """
    使用裁判模型判断模型答案与标准答案是否一致
    
    Args:
        model_answer: 模型输出的答案
        gt_answer: 标准答案（Ground Truth）
        question: 问题文本
        options: 选项字典（可选）
        max_retries: 最大重试次数
        retry_delay: 重试延迟
        
    Returns:
        (is_match, reasoning, response_time, raw_response, final_prompt)
        - is_match: 是否匹配
        - reasoning: 评判理由
        - response_time: 响应时间（秒）
        - raw_response: 原始API响应（字典格式）
        - final_prompt: 最终提交给裁判模型的完整提示词（用于日志记录）
    """
    if not JUDGE_MODEL_CONFIG.get("enabled", True):
        raise ValueError("裁判模型未启用")
    
    judge_model_name = JUDGE_MODEL_CONFIG.get("name")
    if not judge_model_name or judge_model_name not in API_CONFIG:
        raise ValueError(f"裁判模型配置错误: {judge_model_name}")
    
    api_config = API_CONFIG[judge_model_name]
    max_retries = max_retries or EVAL_CONFIG.get("judge_max_retries", 3)
    retry_delay = retry_delay or EVAL_CONFIG.get("judge_retry_delay", 1)
    
    # 检查 API key 是否为空
    api_key = api_config.get("api_key", "")
    if not api_key:
        error_msg = (
            f"裁判模型 API key 未配置！\n"
            f"裁判模型: {judge_model_name}\n"
            f"API 服务商: {api_config.get('base_url', 'unknown')}\n"
            f"请检查环境变量配置（.env 文件或系统环境变量）\n"
            f"对于 dashscope，需要设置 api1 环境变量"
        )
        logging.error(error_msg)
        raise ValueError(error_msg)
    
    client = OpenAI(
        base_url=api_config["base_url"],
        api_key=api_key
    )
    
    # 构建提示词
    system_prompt = """你是一个严格且智能的金融领域答案评判系统。你的任务是判断[模型答案]与[标准答案]在语义上是否一致。

**重要说明**：
模型答案可能有两种格式：
1. **Box格式**：如果模型成功提取了 \\boxed{{}} 中的内容，模型答案将是提取的内容（可能包含多个问题的答案，用逗号或分号分隔）
2. **完整内容格式**：如果模型未能提取 \\boxed{{}}，模型答案将是完整的响应内容，你需要从中提取关键答案信息进行判断

**评判标准**：

1. **多答案处理**：
   - 如果标准答案包含多个结果（多选题、多轮问题等），模型答案必须包含所有正确答案且一一对应正确
   - 模型答案中的多个答案可能用逗号（,）或分号（;）分隔，需要正确识别和匹配
   - 部分正确应判定为 False

2. **计算题评判**：
   - 数值结果必须意思相同（例如"10.5"与"10.50"、"10.5%"与"0.105"应判定为一致）
   - 允许合理的数值误差（如四舍五入导致的微小差异）
   - 单位必须一致或可等价转换（如"元"与"万元"需要换算后比较）
   - 计算公式和逻辑必须正确

3. **文字题/问答题评判**：
   - 在金融领域的语义下判断是否一致
   - 核心观点、结论、判断必须一致
   - 允许表达方式不同，但核心含义必须相同
   - 金融术语的使用必须准确（例如"收益率"与"回报率"在特定语境下可能不同）
   - 如果涉及金融概念、市场判断、风险评估等，需要从金融专业角度判断语义一致性

4. **格式处理**：
   - 忽略标点符号、Markdown格式、大小写的差异
   - 忽略无关的说明文字，只关注答案本身
   - 如果模型答案是完整内容（未提取box），需要从中提取关键答案信息

5. **完整内容提取**（当模型答案不是box格式时）：
   - 仔细阅读完整的模型响应内容
   - 识别其中的最终答案、结论或判断
   - 提取关键信息（数值、选项字母、结论性语句等）
   - 与标准答案进行语义比较

**评判流程**：
1. 首先判断模型答案的格式（box格式还是完整内容）
2. 如果是完整内容，提取其中的关键答案信息
3. 识别标准答案和模型答案中的多个答案（如果有）
4. 根据题目类型（计算题/文字题）采用相应的评判标准
5. 进行语义比较，给出最终判断

⚠️ **输出格式要求**：
请仅输出一个标准的 JSON 对象，不要包含任何其他解释性文字或Markdown标记。格式如下：
{
    "result": true,  // 如果一致为 true，不一致为 false
    "reasoning": "这里写简短的判定理由，说明判断依据和提取的信息（如果是完整内容格式）"
}"""

    user_content_text = f"""[问题]
{question}
"""
    
    # 如果存在选项，添加到提示词中
    if options is not None and isinstance(options, dict) and options:
        opt_str = "；".join([f"{k}: {v}" for k, v in options.items() if v])
        user_content_text += f"""
[选项]
{opt_str}
"""
    
    user_content_text += f"""
[标准答案 (GT)]
{gt_answer}

[模型答案]
{model_answer}

**评判要求**：
1. 如果模型答案是完整内容（未提取 \\boxed{{}}），请先从中提取关键答案信息，然后与标准答案比较
2. 如果模型答案包含多个答案（用逗号或分号分隔），请逐一与标准答案中的对应答案进行比较
3. 判断题目类型：
   - 如果是计算题，关注数值结果的语义一致性
   - 如果是文字题/问答题，关注在金融领域语义下的一致性
4. 忽略模型答案中的思考过程、推理步骤等，只关注最终答案部分
5. 如果标准答案也是多个答案，确保模型答案包含所有正确答案且一一对应正确

请根据上述内容生成 JSON 评判结果。"""

    # 构建最终提示词（用于日志记录）
    final_prompt = f"{system_prompt}\n\n{user_content_text}"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": [{"type": "text", "text": user_content_text}]}
    ]
    
    # 构建API调用参数
    # 超时时间：优先使用 EVAL_CONFIG 中的 timeout，其次使用模型配置中的 timeout
    timeout = EVAL_CONFIG.get("timeout") or api_config.get("timeout", 600)
    
    api_params = {
        "model": api_config["model"],
        "messages": messages,
        "max_tokens": api_config.get("max_tokens", 512),
        "timeout": timeout
    }
    # 仅当显式配置了温度时才传递，避免覆盖模型默认值
    if api_config.get("temperature") is not None:
        api_params["temperature"] = api_config["temperature"]
    
    # 重试机制
    last_error = None
    for attempt in range(max_retries):
        try:
            start_time = time.time()
            
            # 尝试使用 JSON 模式
            try:
                response = client.chat.completions.create(
                    **api_params,
                    response_format={"type": "json_object"}
                )
            except Exception as json_error:
                logging.warning(f"JSON模式不支持，使用普通模式: {json_error}")
                response = client.chat.completions.create(**api_params)
            
            response_time = time.time() - start_time
            
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
            
            raw_content = response.choices[0].message.content
            if not raw_content:
                raise ValueError("API响应内容为空")
            
            # 解析JSON结果
            cleaned_content = clean_json_text(raw_content)
            try:
                result_json = json.loads(cleaned_content)
                is_match = bool(result_json.get("result", False))
                reasoning = result_json.get("reasoning", "未提供理由") or "未提供理由"
            except json.JSONDecodeError as e:
                logging.warning(f"JSON解析失败: {e}")
                # 降级策略：简单的关键词匹配
                content_lower = raw_content.lower()
                if '"result": true' in content_lower or '"result":true' in content_lower:
                    is_match = True
                elif '"result": false' in content_lower or '"result":false' in content_lower:
                    is_match = False
                else:
                    is_match = "true" in content_lower and "false" not in content_lower
                reasoning = f"JSON解析错误，使用降级策略: {str(e)}"
            
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
                        "raw_content": raw_content,
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
                            choice_dict["message"] = message_dict
                        raw_response["choices"] = [choice_dict]
            except Exception as e:
                logging.warning(f"无法序列化完整响应对象: {e}")
                # 降级：只保存基本信息
                raw_response = {
                    "model": response.model if hasattr(response, 'model') else None,
                    "raw_content": raw_content
                }
            
            return is_match, reasoning, response_time, raw_response, final_prompt
            
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                wait_time = retry_delay * (2 ** attempt)
                logging.warning(f"裁判模型调用失败（尝试 {attempt + 1}/{max_retries}）: {e}，{wait_time:.1f}秒后重试...")
                time.sleep(wait_time)
            else:
                logging.error(f"裁判模型调用失败（已重试 {max_retries} 次）: {e}")
                raise
    
    # 如果所有重试都失败，也返回提示词
    raise Exception(f"裁判模型调用失败: {last_error}")
