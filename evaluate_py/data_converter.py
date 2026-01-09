"""
数据格式转换模块
将不同的输入格式统一转换为标准格式，便于后续评测处理
"""
import logging
from typing import Dict, Any, List, Optional


def convert_to_standard_format(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    将任意格式的数据项转换为标准格式
    
    标准格式字段：
    - image_id: 图片ID
    - image_path: 图片路径
    - image_type: 图片类型
    - question_id: 问题ID
    - question_type: 问题类型
    - question: 问题（字符串或字典，如 {"round1": "...", "round2": "..."}）
    - options: 选项（null 或字典）
    - answer: 答案（字符串或字典，如 {"round1": "...", "round2": "..."}）
    - qa_make_process: 问题生成过程（字符串或字典）
    
    Args:
        item: 原始数据项（任意格式）
        
    Returns:
        标准格式的数据项
    """
    standard = {}
    
    # ==================== ID字段转换 ====================
    # 重要说明：
    # 1. 问题ID：id 和 question_id 都是问题ID，标识一个问题（单轮或多轮）
    #    - 格式1：多轮问题共享同一个 id 和 question_id
    #    - 格式2：多轮问题分散在多行，但每行都有相同的 id（问题ID），只是 round 不同
    # 2. 图片ID：image_id 是图片ID，只和图片路径绑定，独立于问题ID
    #    - 一个图片可能被多个问题使用
    #    - 一个问题也可能有多张图片
    
    # 问题ID转换：优先使用 question_id，其次使用 id
    # 这两个字段都表示问题ID，只是命名不同
    standard["question_id"] = item.get("question_id") or item.get("id", "")
    
    # 图片ID：只从 image_id 字段获取，不与其他ID混用
    # image_id 独立于问题ID，只和图片路径绑定
    standard["image_id"] = item.get("image_id", "")
    
    # ==================== 路径和类型字段 ====================
    # 处理image_path：支持逗号分隔的多张图片（JSON/JSONL格式）
    image_path_raw = item.get("image_path", "")
    if isinstance(image_path_raw, str) and image_path_raw and ',' in image_path_raw:
        # 逗号分隔的字符串，转换为列表
        standard["image_path"] = [path.strip() for path in image_path_raw.split(',') if path.strip()]
    elif isinstance(image_path_raw, list):
        # 已经是列表，直接使用
        standard["image_path"] = image_path_raw
    else:
        # 单个路径或空字符串
        standard["image_path"] = image_path_raw if image_path_raw else ""
    
    standard["image_type"] = item.get("image_type") or item.get("type", "")
    standard["question_type"] = item.get("question_type") or item.get("gen_type", "")
    
    # 处理original_image_path：支持数组格式（格式与image_path相同）
    original_image_path_raw = item.get("original_image_path", "")
    if isinstance(original_image_path_raw, str) and original_image_path_raw and ',' in original_image_path_raw:
        # 逗号分隔的字符串，转换为列表
        standard["original_image_path"] = [path.strip() for path in original_image_path_raw.split(',') if path.strip()]
    elif isinstance(original_image_path_raw, list):
        # 已经是列表，直接使用
        standard["original_image_path"] = original_image_path_raw
    elif original_image_path_raw:
        # 单个路径，转换为列表以保持格式一致
        standard["original_image_path"] = [original_image_path_raw]
    else:
        # 空值，不设置字段（或设置为空列表）
        standard["original_image_path"] = []
    
    # ==================== 图片URL字段（第二种格式） ====================
    # 处理image_urls字段（可能是列表或字符串）
    image_urls = item.get("image_urls")
    if image_urls:
        if isinstance(image_urls, list):
            standard["image_urls"] = image_urls
        elif isinstance(image_urls, str):
            # CSV格式可能是分号分隔的字符串
            if ";" in image_urls:
                standard["image_urls"] = [url.strip() for url in image_urls.split(";") if url.strip()]
            else:
                standard["image_urls"] = [image_urls] if image_urls.strip() else []
        else:
            standard["image_urls"] = []
    else:
        standard["image_urls"] = []
    
    # 如果image_urls存在但image_path为空，使用第一个image_url作为image_path
    if standard["image_urls"] and not standard["image_path"]:
        standard["image_path"] = standard["image_urls"][0]
    
    # ==================== 分类字段（第二种格式） ====================
    # 保留所有分类字段，用于后续统计
    for field in ["scenario", "capability", "difficulty", "source"]:
        if field in item:
            standard[field] = item[field]
    
    # ==================== 问题字段转换 ====================
    question = item.get("question", "")
    
    # 如果question已经是字典格式（多轮），直接使用
    if isinstance(question, dict):
        standard["question"] = question
    # 如果是字符串，保持为字符串（单轮）
    elif isinstance(question, str):
        standard["question"] = question
    else:
        # 其他类型，转换为字符串
        standard["question"] = str(question) if question else ""
    
    # ==================== 答案字段转换 ====================
    answer = item.get("answer", "")
    
    # 如果answer已经是字典格式（多轮），直接使用
    if isinstance(answer, dict):
        standard["answer"] = answer
    # 如果是字符串，保持为字符串（单轮）
    elif isinstance(answer, str):
        standard["answer"] = answer
    else:
        # 其他类型，转换为字符串
        standard["answer"] = str(answer) if answer else ""
    
    # ==================== 选项字段转换 ====================
    options = item.get("options")
    if options is None:
        standard["options"] = None
    elif isinstance(options, dict):
        standard["options"] = options
    elif isinstance(options, str):
        # 尝试解析JSON字符串
        try:
            import json
            standard["options"] = json.loads(options)
        except:
            standard["options"] = None
    else:
        standard["options"] = None
    
    # ==================== 过程字段转换 ====================
    # 优先使用新格式的qa_make_process，如果没有则使用旧格式的process
    qa_make_process = item.get("qa_make_process") or item.get("process", "")
    
    # 如果qa_make_process已经是字典格式（多轮），直接使用
    if isinstance(qa_make_process, dict):
        standard["qa_make_process"] = qa_make_process
    # 如果是字符串，保持为字符串（单轮）
    elif isinstance(qa_make_process, str):
        standard["qa_make_process"] = qa_make_process
    else:
        standard["qa_make_process"] = ""
    
    # ==================== 保留其他字段 ====================
    # 保留所有其他字段，以便后续扩展使用
    excluded_fields = {
        "id", "type", "gen_type", "process",  # 旧格式字段
        "image_id", "question_id", "image_type", "question_type",  # 已转换字段
        "image_path", "question", "answer", "options", "qa_make_process"  # 已转换字段
    }
    
    for key, value in item.items():
        if key not in excluded_fields:
            standard[key] = value
    
    # ==================== 添加元数据 ====================
    # 判断是否为多轮问答
    is_multi_round = (
        isinstance(standard["question"], dict) and 
        isinstance(standard["answer"], dict) and
        any(key.startswith("round") for key in standard["question"].keys())
    )
    standard["is_multi_round"] = is_multi_round
    
    return standard


def merge_multi_round_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    合并多轮对话数据（第二种格式：多行数据合并为单行）
    
    将相同id的多行数据（通过round字段区分）合并为一个数据项，
    将question/answer等字段转换为字典格式（round1, round2等）
    
    注意：
    - id 和 question_id 都是问题ID，标识一个问题（多轮问题共享同一个问题ID）
    - image_id 是图片ID，只和图片路径绑定，独立于问题ID
    - 格式2中，相同id的多行数据合并后，question_id 就是那个 id
    
    Args:
        items: 原始数据项列表（可能包含多行相同id的数据）
        
    Returns:
        合并后的数据项列表
    """
    # 按问题ID（id或question_id）分组
    grouped = {}
    for item in items:
        # 问题ID：优先使用 question_id，其次使用 id
        question_id = item.get("question_id") or item.get("id") or ""
        if not question_id:
            # 如果没有问题ID，直接保留原样（不参与合并）
            continue
        
        if question_id not in grouped:
            grouped[question_id] = []
        grouped[question_id].append(item)
    
    merged_items = []
    
    for question_id, group_items in grouped.items():
        # 如果只有一条数据，直接转换
        if len(group_items) == 1:
            merged_items.append(group_items[0])
            continue
        
        # 检查是否有round字段（多轮对话）
        has_round = any("round" in item and item.get("round") is not None for item in group_items)
        
        if not has_round:
            # 没有round字段，可能是重复的问题ID，取第一条
            merged_items.append(group_items[0])
            continue
        
        # 按round排序
        group_items.sort(key=lambda x: x.get("round", 0) if x.get("round") is not None else 999)
        
        # 合并为单条数据
        merged_item = {}
        
        # 保留第一条数据的基础字段
        first_item = group_items[0]
        
        # 问题ID：合并后的多轮问题共享同一个问题ID
        merged_item["id"] = question_id
        merged_item["question_id"] = question_id
        
        # 图片ID：从第一条数据获取（如果有），图片ID独立于问题ID
        # 注意：如果多行数据中有不同的 image_id，可能需要特殊处理
        # 目前策略：使用第一条数据的 image_id
        if "image_id" in first_item and first_item["image_id"]:
            merged_item["image_id"] = first_item["image_id"]
        else:
            # 检查所有行是否有 image_id
            for item in group_items:
                if "image_id" in item and item["image_id"]:
                    merged_item["image_id"] = item["image_id"]
                    break
        
        # 保留分类字段（从第一条数据获取，假设同一对话的分类字段相同）
        for field in ["question_type", "scenario", "capability", "difficulty", "source"]:
            if field in first_item:
                merged_item[field] = first_item[field]
        
        # 处理image_urls（合并所有轮次的图片）
        all_image_urls = []
        for item in group_items:
            if "image_urls" in item and item["image_urls"]:
                if isinstance(item["image_urls"], list):
                    all_image_urls.extend(item["image_urls"])
                elif isinstance(item["image_urls"], str):
                    # CSV格式可能是分号分隔的字符串
                    if ";" in item["image_urls"]:
                        all_image_urls.extend([url.strip() for url in item["image_urls"].split(";") if url.strip()])
                    else:
                        all_image_urls.append(item["image_urls"])
        if all_image_urls:
            merged_item["image_urls"] = list(set(all_image_urls))  # 去重
        
        # 合并question和answer为字典格式
        question_dict = {}
        answer_dict = {}
        
        for idx, item in enumerate(group_items, 1):
            round_num = item.get("round", idx)
            round_key = f"round{round_num}"
            
            if "question" in item and item["question"]:
                question_dict[round_key] = item["question"]
            
            if "answer" in item and item["answer"]:
                answer_dict[round_key] = item["answer"]
        
        merged_item["question"] = question_dict if question_dict else group_items[0].get("question", "")
        merged_item["answer"] = answer_dict if answer_dict else group_items[0].get("answer", "")
        
        # 保留其他字段（从第一条数据）
        for key, value in first_item.items():
            if key not in merged_item and key not in ["round", "question", "answer", "image_urls"]:
                merged_item[key] = value
        
        merged_items.append(merged_item)
    
    # 处理没有id的数据项（直接保留）
    for item in items:
        item_id = item.get("id") or item.get("question_id") or ""
        if not item_id:
            merged_items.append(item)
    
    return merged_items


def convert_batch(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    批量转换数据项
    支持两种格式：
    1. 第一种格式：多轮问题已经在同一个数据项中（字典格式）
    2. 第二种格式：多轮问题分开在多行中（需要合并）
    
    Args:
        items: 原始数据项列表
        
    Returns:
        标准格式的数据项列表
    """
    # 检测是否为第二种格式（需要合并的格式）
    # 判断标准：存在round字段，且相同id有多条数据
    need_merge = False
    id_counts = {}
    for item in items:
        item_id = item.get("id") or item.get("question_id") or ""
        if item_id:
            id_counts[item_id] = id_counts.get(item_id, 0) + 1
        if "round" in item and item.get("round") is not None:
            need_merge = True
    
    # 如果有id出现多次，且存在round字段，则需要合并
    if need_merge and any(count > 1 for count in id_counts.values()):
        logging.info("检测到第二种格式（多行数据），开始合并...")
        items = merge_multi_round_items(items)
    
    # 转换为标准格式
    converted = []
    for item in items:
        try:
            standard_item = convert_to_standard_format(item)
            converted.append(standard_item)
        except Exception as e:
            item_id = item.get("id") or item.get("question_id") or item.get("image_id") or "unknown"
            logging.warning(f"转换数据项失败 {item_id}: {e}")
            continue
    
    return converted


def validate_standard_format(item: Dict[str, Any]) -> bool:
    """
    验证数据项是否符合标准格式
    
    Args:
        item: 数据项
        
    Returns:
        是否符合标准格式
    """
    # 必需字段
    required_fields = ["question_id", "question", "answer"]
    for field in required_fields:
        if field not in item:
            item_id = item.get("question_id") or item.get("image_id") or "unknown"
            logging.warning(f"标准格式数据项缺少必需字段 '{field}': {item_id}")
            return False
    
    # 验证question字段
    question = item.get("question")
    if not question:
        item_id = item.get("question_id") or "unknown"
        logging.warning(f"标准格式数据项question字段为空: {item_id}")
        return False
    
    # 验证answer字段
    answer = item.get("answer")
    if not answer:
        item_id = item.get("question_id") or "unknown"
        logging.warning(f"标准格式数据项answer字段为空: {item_id}")
        return False
    
    # 如果是多轮格式，验证question和answer的轮次是否匹配
    if item.get("is_multi_round", False):
        if not isinstance(question, dict) or not isinstance(answer, dict):
            item_id = item.get("question_id") or "unknown"
            logging.warning(f"多轮格式数据项question或answer不是字典: {item_id}")
            return False
        
        # 检查question和answer的轮次是否匹配
        question_rounds = set(k for k in question.keys() if k.startswith("round"))
        answer_rounds = set(k for k in answer.keys() if k.startswith("round"))
        
        if question_rounds != answer_rounds:
            item_id = item.get("question_id") or "unknown"
            logging.warning(
                f"多轮格式数据项question和answer轮次不匹配: {item_id} "
                f"(question: {question_rounds}, answer: {answer_rounds})"
            )
            return False
    
    return True


def detect_format(item: Dict[str, Any]) -> str:
    """
    检测数据项的格式类型
    
    Args:
        item: 数据项
        
    Returns:
        格式类型：'new_format', 'old_format', 'unknown'
    """
    # 新格式特征：有image_id或question_id，且question/answer可能是字典
    has_new_format_fields = "image_id" in item or "question_id" in item
    has_multi_round = (
        isinstance(item.get("question"), dict) or 
        isinstance(item.get("answer"), dict)
    )
    
    # 旧格式特征：有id字段，且question/answer是字符串
    has_old_format_fields = "id" in item
    has_single_round = (
        isinstance(item.get("question"), str) and 
        isinstance(item.get("answer"), str)
    )
    
    if has_new_format_fields or has_multi_round:
        return "new_format"
    elif has_old_format_fields and has_single_round:
        return "old_format"
    else:
        return "unknown"


def get_format_info(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    获取数据格式信息
    
    Args:
        items: 数据项列表
        
    Returns:
        格式信息字典
    """
    format_counts = {"new_format": 0, "old_format": 0, "unknown": 0}
    multi_round_count = 0
    single_round_count = 0
    
    for item in items:
        format_type = detect_format(item)
        format_counts[format_type] = format_counts.get(format_type, 0) + 1
        
        if isinstance(item.get("question"), dict) or isinstance(item.get("answer"), dict):
            multi_round_count += 1
        else:
            single_round_count += 1
    
    return {
        "format_distribution": format_counts,
        "multi_round_count": multi_round_count,
        "single_round_count": single_round_count,
        "total_count": len(items)
    }
