"""
结果处理辅助函数模块
包含答案检查、内容处理等工具函数
"""
import re
from typing import Dict, Any


def is_answer_empty(module2_item: Dict[str, Any], model_key: str = None, model_name: str = None) -> bool:
    """
    检查指定模型的answer字段是否为空
    支持检查所有可能的model_key格式（model, model1-model5），只要model_name匹配就检查
    
    Args:
        module2_item: module2格式的结果项
        model_key: 模型键（如 "model", "model1", "model2"），如果为None则自动查找
        model_name: 模型名称，用于匹配model_name字段
        
    Returns:
        True表示answer为空需要重新评测，False表示answer有效
    """
    # 如果提供了model_key，直接使用
    if model_key:
        model_data = module2_item.get(model_key, {})
        if isinstance(model_data, dict):
            # 如果提供了model_name，检查是否匹配
            if model_name and model_data.get("model_name") != model_name:
                # model_key存在但model_name不匹配，继续查找
                pass
            else:
                # 检查这个model_key的数据
                answer_value = model_data.get("answer", "")
                if not _check_answer_empty(answer_value):
                    return False  # 找到有效的answer
                elif not model_name:
                    # 如果没有提供model_name，且这个model_key的answer为空，继续查找
                    pass
    
    # 如果没有提供model_key或model_key不匹配，遍历所有可能的model_key
    # 优先检查"model"，然后检查model1-model5
    possible_keys = ["model"] + [f"model{i}" for i in range(1, 6)]
    
    for key in possible_keys:
        if model_key and key == model_key:
            continue  # 已经检查过了
        model_data = module2_item.get(key, {})
        if isinstance(model_data, dict):
            # 如果提供了model_name，检查是否匹配
            if model_name:
                if model_data.get("model_name") == model_name:
                    answer_value = model_data.get("answer", "")
                    return _check_answer_empty(answer_value)
            else:
                # 如果没有提供model_name，检查第一个非空的model_data
                answer_value = model_data.get("answer", "")
                if not _check_answer_empty(answer_value):
                    return False  # 找到有效的answer
    
    # 如果所有可能的model_key都没有找到有效数据，认为需要重新评测
    return True


def _check_answer_empty(answer_value: Any) -> bool:
    """
    检查answer值是否为空（辅助函数）
    
    Args:
        answer_value: answer的值（可能是字符串、字典等）
        
    Returns:
        True表示answer为空，False表示answer有效
    """
    if answer_value is None:
        return True
    
    # 多轮题目：answer是字典格式 {round1: "...", round2: "..."}
    if isinstance(answer_value, dict):
        # 如果字典为空，需要重新评测
        if not answer_value:
            return True
        # 检查每个round的answer是否为空
        for round_key, round_answer in answer_value.items():
            if not round_answer or (isinstance(round_answer, str) and not round_answer.strip()):
                # 只要有一个round的answer为空，就需要重新评测
                return True
        return False  # 所有round的answer都不为空
    
    # 单轮题目：answer是字符串
    if isinstance(answer_value, str):
        return not answer_value.strip()  # 空字符串或只包含空白字符视为空
    
    # 其他类型（如数字等）视为有效（非空）
    return False


def strip_boxed_content(text: str) -> str:
    """
    移除文本中的 \\boxed{...} 片段，只保留思考/分析部分。
    
    Args:
        text: 原始文本
        
    Returns:
        清理后的文本
    """
    if not text:
        return ""
    # 粗略移除所有 \boxed{...}，不追求完全语法正确，只用于日志/过程展示
    cleaned = re.sub(r"\\\\boxed\{.*?\}", "", text, flags=re.DOTALL)
    # 再尝试兼容单反斜杠写法（防御性处理）
    cleaned = re.sub(r"\\boxed\{.*?\}", "", cleaned, flags=re.DOTALL)
    return cleaned.strip()


def build_process_value(model_answer: str, model_data: Dict[str, Any]) -> str:
    """
    根据原始回答和 raw_response 构造 process：
    - 优先拼接模型的思考内容（reasoning_content / reasoning / reasoning_details）
    - 再拼接去掉 \\boxed{} 的正文内容
    
    Args:
        model_answer: 模型原始回答
        model_data: 模型数据字典（包含 raw_response）
        
    Returns:
        构造的 process 字符串
    """
    base_text = model_answer or ""
    non_box_text = strip_boxed_content(base_text)

    reasoning_text = ""
    raw_response = model_data.get("raw_response")
    try:
        if isinstance(raw_response, dict):
            choices = raw_response.get("choices") or []
            if choices:
                msg = choices[0].get("message") or {}
                # 按优先级提取思考内容：reasoning > reasoning_content > reasoning_details
                # 只保留优先级最高的一个，避免冗余
                r = msg.get("reasoning")
                if isinstance(r, str) and r.strip():
                    reasoning_text = r.strip()
                else:
                    rc = msg.get("reasoning_content")
                    if isinstance(rc, str) and rc.strip():
                        reasoning_text = rc.strip()
                    else:
                        rd = msg.get("reasoning_details")
                        # reasoning_details 可能是列表或字符串
                        if isinstance(rd, list):
                            texts = []
                            for d in rd:
                                if isinstance(d, dict):
                                    t = d.get("text")
                                    if isinstance(t, str) and t.strip():
                                        texts.append(t.strip())
                                elif isinstance(d, str) and d.strip():
                                    texts.append(d.strip())
                            if texts:
                                reasoning_text = "\n\n".join(texts)
                        elif isinstance(rd, str) and rd.strip():
                            reasoning_text = rd.strip()
    except Exception:
        # 防御性：解析失败时忽略思考内容，避免影响主流程
        reasoning_text = ""

    parts = []
    if reasoning_text:
        parts.append(f"【思考】\n{reasoning_text}")
    if non_box_text:
        parts.append(f"【回答】\n{non_box_text}")

    if parts:
        return "\n\n".join(parts)
    # 如果什么都提取不到，就退回完整回答
    return base_text

