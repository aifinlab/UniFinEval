"""
统计计算模块
负责计算评测结果的统计信息
"""
from typing import List, Dict, Any
from .config import EVAL_CONFIG
from .result_utils import is_answer_empty


def calculate_statistics(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    计算统计信息
    
    Args:
        results: 评测结果列表
        
    Returns:
        统计信息字典
    """
    # 获取配置：是否按轮次计分
    count_by_rounds = EVAL_CONFIG.get("multi_round_count_by_rounds", False)
    
    stats = {
        "total_items": len(results),
        "profiles": {},
        "models": {},
        "scoring_method": "按轮次计分" if count_by_rounds else "整题计分"  # 标注使用的计分方式
    }
    
    # 获取所有用户画像和模型
    all_profiles = set()
    all_models = set()
    
    for result in results:
        for profile in result.get("profiles", {}).keys():
            all_profiles.add(profile)
            for model_name in result["profiles"][profile].get("models", {}).keys():
                all_models.add(model_name)
    
    # 按用户画像统计
    for profile in all_profiles:
        profile_stats = {
            "total": 0,
            "correct": 0,
            "models": {}
        }
        
        for model_name in all_models:
            model_stats = {"total": 0, "correct": 0}
            
            for result in results:
                profile_data = result.get("profiles", {}).get(profile, {})
                model_data = profile_data.get("models", {}).get(model_name, {})
                
                # 检查是否为多轮题目且开启了按轮次计分
                is_multi_round = result.get("is_multi_round", False)
                rounds = model_data.get("rounds", [])
                
                if count_by_rounds and is_multi_round and isinstance(rounds, list) and len(rounds) > 0:
                    # 按轮次计分：每轮算一道题
                    for round_data in rounds:
                        round_correct = round_data.get("is_correct", False)
                        model_stats["total"] += 1
                        profile_stats["total"] += 1
                        if round_correct:
                            model_stats["correct"] += 1
                            profile_stats["correct"] += 1
                else:
                    # 按整题计分：整题算一道题
                    is_correct = None
                    if "is_correct" in model_data:
                        is_correct = model_data["is_correct"]
                    elif "all_rounds_correct" in model_data:
                        is_correct = model_data["all_rounds_correct"]
                    
                    if is_correct is not None:
                        model_stats["total"] += 1
                        profile_stats["total"] += 1
                        if is_correct:
                            model_stats["correct"] += 1
                            profile_stats["correct"] += 1
            
            model_stats["accuracy"] = model_stats["correct"] / model_stats["total"] if model_stats["total"] > 0 else 0
            profile_stats["models"][model_name] = model_stats
        
        profile_stats["accuracy"] = profile_stats["correct"] / profile_stats["total"] if profile_stats["total"] > 0 else 0
        stats["profiles"][profile] = profile_stats
    
    # 按模型统计（跨所有用户画像）
    for model_name in all_models:
        model_stats = {"total": 0, "correct": 0, "profiles": {}}
        
        for profile in all_profiles:
            profile_model_stats = {"total": 0, "correct": 0}
            
            for result in results:
                profile_data = result.get("profiles", {}).get(profile, {})
                model_data = profile_data.get("models", {}).get(model_name, {})
                
                # 检查是否为多轮题目且开启了按轮次计分
                is_multi_round = result.get("is_multi_round", False)
                rounds = model_data.get("rounds", [])
                
                if count_by_rounds and is_multi_round and isinstance(rounds, list) and len(rounds) > 0:
                    # 按轮次计分：每轮算一道题
                    for round_data in rounds:
                        round_correct = round_data.get("is_correct", False)
                        profile_model_stats["total"] += 1
                        model_stats["total"] += 1
                        if round_correct:
                            profile_model_stats["correct"] += 1
                            model_stats["correct"] += 1
                else:
                    # 按整题计分：整题算一道题
                    is_correct = None
                    if "is_correct" in model_data:
                        is_correct = model_data["is_correct"]
                    elif "all_rounds_correct" in model_data:
                        is_correct = model_data["all_rounds_correct"]
                    
                    if is_correct is not None:
                        profile_model_stats["total"] += 1
                        model_stats["total"] += 1
                        if is_correct:
                            profile_model_stats["correct"] += 1
                            model_stats["correct"] += 1
            
            profile_model_stats["accuracy"] = profile_model_stats["correct"] / profile_model_stats["total"] if profile_model_stats["total"] > 0 else 0
            model_stats["profiles"][profile] = profile_model_stats
        
        model_stats["accuracy"] = model_stats["correct"] / model_stats["total"] if model_stats["total"] > 0 else 0
        stats["models"][model_name] = model_stats
    
    # 按分类字段统计
    category_fields = ["question_type", "fintype", "image_type", "scenario", "capability", "difficulty", "source", "language"]
    stats["by_category"] = {}
    
    for category_field in category_fields:
        category_stats = {}
        
        # 收集所有该字段的值
        category_values = set()
        for result in results:
            category_value = result.get(category_field)
            if category_value:
                category_values.add(category_value)
        
        # 对每个分类值进行统计
        for category_value in category_values:
            category_value_stats = {
                "total": 0,
                "correct": 0,
                "models": {}
            }
            
            for model_name in all_models:
                model_category_stats = {"total": 0, "correct": 0}
                
                for result in results:
                    if result.get(category_field) != category_value:
                        continue
                    
                    # 统计所有用户画像的结果
                    for profile in all_profiles:
                        profile_data = result.get("profiles", {}).get(profile, {})
                        model_data = profile_data.get("models", {}).get(model_name, {})
                        
                        # 检查是否为多轮题目且开启了按轮次计分
                        is_multi_round = result.get("is_multi_round", False)
                        rounds = model_data.get("rounds", [])
                        
                        if count_by_rounds and is_multi_round and isinstance(rounds, list) and len(rounds) > 0:
                            # 按轮次计分：每轮算一道题
                            for round_data in rounds:
                                round_correct = round_data.get("is_correct", False)
                                model_category_stats["total"] += 1
                                category_value_stats["total"] += 1
                                if round_correct:
                                    model_category_stats["correct"] += 1
                                    category_value_stats["correct"] += 1
                        else:
                            # 按整题计分：整题算一道题
                            is_correct = None
                            if "is_correct" in model_data:
                                is_correct = model_data["is_correct"]
                            elif "all_rounds_correct" in model_data:
                                is_correct = model_data["all_rounds_correct"]
                            
                            if is_correct is not None:
                                model_category_stats["total"] += 1
                                category_value_stats["total"] += 1
                                if is_correct:
                                    model_category_stats["correct"] += 1
                                    category_value_stats["correct"] += 1
                
                model_category_stats["accuracy"] = model_category_stats["correct"] / model_category_stats["total"] if model_category_stats["total"] > 0 else 0
                category_value_stats["models"][model_name] = model_category_stats
            
            category_value_stats["accuracy"] = category_value_stats["correct"] / category_value_stats["total"] if category_value_stats["total"] > 0 else 0
            category_stats[category_value] = category_value_stats
        
        if category_stats:
            stats["by_category"][category_field] = category_stats
    
    return stats


def calculate_output_statistics(results: List[Dict[str, Any]], enabled_models: List[str]) -> Dict[str, Any]:
    """
    基于最终输出格式计算统计信息（用于在输出文件中展示）
    
    Args:
        results: module2格式的结果列表（每个结果项可能包含多个模型字段）
        enabled_models: 启用的模型列表
        
    Returns:
        统计信息字典，包含总得分和按分类字段的得分
    """
    # 获取配置：是否按轮次计分
    count_by_rounds = EVAL_CONFIG.get("multi_round_count_by_rounds", False)
    
    def _model_entry_is_valid(entry: Any) -> bool:
        """判定模型字段是否包含有效结果，过滤掉批量写入时生成的占位空结果。"""
        if not isinstance(entry, dict):
            return False
        if entry.get("response_time", 0) > 0:
            return True
        if entry.get("answer") not in ("", None, {}):
            return True
        if entry.get("process") not in ("", None, {}):
            return True
        return False
    
    def _count_item(item: Dict[str, Any], model_key: str, entry: Dict[str, Any], model_name: str = None) -> tuple:
        """
        统计单个题目的得分
        重要：分母只算有非空答案的题目，分子只算对的个数
        对于多轮题目按轮次计分：每一轮都算一个题，但只统计有非空答案的轮次
        
        Args:
            item: 结果项
            model_key: 模型键
            entry: 模型数据entry
            model_name: 模型名称（用于检查答案是否为空）
        
        Returns:
            (count, correct_count) - 题目数和正确数（只统计有非空答案的题目）
        """
        match_gt = entry.get("match_gt", False)
        
        # 检查 match_gt 是否为字典格式（多轮题目）
        if isinstance(match_gt, dict):
            # 多轮题目：match_gt 是字典格式 {round1: true/false, round2: true/false}
            answer_value = entry.get("answer", {})
            
            if count_by_rounds:
                # 按轮次计分：每一轮都算一个题，但只统计有非空答案的轮次
                if not isinstance(answer_value, dict):
                    # 如果answer不是字典，说明格式有问题，不统计
                    return (0, 0)
                
                # 只统计有非空答案的轮次
                count = 0
                correct = 0
                for round_key, round_correct in match_gt.items():
                    # 检查该轮次的答案是否为空
                    round_answer = answer_value.get(round_key, "")
                    # 判断该轮次答案是否为空
                    is_round_empty = False
                    if round_answer is None:
                        is_round_empty = True
                    elif isinstance(round_answer, str):
                        is_round_empty = not round_answer.strip()
                    elif isinstance(round_answer, dict):
                        is_round_empty = not round_answer
                    # 如果该轮次有非空答案，计入分母
                    if not is_round_empty:
                        count += 1
                        if round_correct:
                            correct += 1
                return (count, correct)
            else:
                # 按整题计分：所有轮次都正确才算正确
                # 但需要检查是否有至少一轮有非空答案
                if isinstance(answer_value, dict):
                    # 检查是否至少有一轮有非空答案
                    has_any_answer = False
                    for round_answer in answer_value.values():
                        if round_answer is not None:
                            if isinstance(round_answer, str) and round_answer.strip():
                                has_any_answer = True
                                break
                            elif not isinstance(round_answer, str):
                                has_any_answer = True
                                break
                    if not has_any_answer:
                        return (0, 0)  # 所有轮次答案都为空，不统计
                else:
                    # answer不是字典，检查是否为空
                    if model_name and is_answer_empty(item, model_key=model_key, model_name=model_name):
                        return (0, 0)
                
                all_correct = all(match_gt.values()) if match_gt else False
                return (1, 1 if all_correct else 0)
        else:
            # 单轮题目：match_gt 是布尔值
            # 检查答案是否为空，如果为空则不统计
            if model_name and is_answer_empty(item, model_key=model_key, model_name=model_name):
                return (0, 0)
            return (1, 1 if match_gt else 0)
    
    # 辅助函数：查找item中对应model_name的entry（支持model和model1-model5格式）
    def _find_model_entry(item: Dict[str, Any], model_name: str) -> tuple:
        """
        查找item中对应model_name的entry
        
        Returns:
            (model_key, entry) 或 (None, None)
        """
        # 优先检查"model"键（新格式）
        if "model" in item:
            entry = item.get("model")
            if _model_entry_is_valid(entry) and entry.get("model_name") == model_name:
                return ("model", entry)
        
        # 兼容旧格式：检查model1-model5
        for i in range(1, 6):
            model_key = f"model{i}"
            if model_key in item:
                entry = item.get(model_key)
                if _model_entry_is_valid(entry) and entry.get("model_name") == model_name:
                    return (model_key, entry)
        
        return (None, None)
    
    stats = {
        "total": {
            "total_count": 0,
            "correct_count": 0,
            "accuracy": 0.0
        },
        "by_model": {},
        "by_profile": {},
        "by_category": {},
        "scoring_method": "按轮次计分" if count_by_rounds else "整题计分"  # 标注使用的计分方式
    }
    
    # 辅助函数：对结果进行去重，每个question_id只保留第一个有非空答案的记录
    def _deduplicate_results(results_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        对结果列表进行去重：每个question_id只保留第一个有非空答案的记录
        
        Args:
            results_list: 结果列表
            
        Returns:
            去重后的结果列表
        """
        question_id_to_item = {}  # {question_id: item} 存储每个question_id的第一个有非空答案的记录
        question_id_has_valid_answer = {}  # {question_id: bool} 标记是否已找到非空答案
        
        for item in results_list:
            item_id = item.get("question_id", "")
            if not item_id:
                continue
            
            # 如果已经找到非空答案，跳过后续重复记录
            if item_id in question_id_has_valid_answer and question_id_has_valid_answer[item_id]:
                continue
            
            # 检查是否有非空答案（至少一个模型有非空答案）
            has_valid_answer = False
            for model_name in enabled_models:
                model_key, entry = _find_model_entry(item, model_name)
                if entry is None:
                    continue
                # 检查该模型的answer是否为空
                if not is_answer_empty(item, model_key=model_key, model_name=model_name):
                    has_valid_answer = True
                    break
            
            if item_id not in question_id_to_item:
                # 第一次遇到这个question_id
                question_id_to_item[item_id] = item
                question_id_has_valid_answer[item_id] = has_valid_answer
            else:
                # 重复的question_id，且之前还没找到非空答案
                if has_valid_answer:
                    # 找到第一个非空答案，替换之前的空答案记录
                    question_id_to_item[item_id] = item
                    question_id_has_valid_answer[item_id] = True
                # 如果当前记录是空的，忽略（继续使用之前找到的记录）
        
        # 构建去重后的结果列表
        deduplicated = []
        for item_id, item in question_id_to_item.items():
            deduplicated.append(item)
        
        return deduplicated
    
    # 对结果进行去重（所有统计都使用去重后的结果）
    deduplicated_results = _deduplicate_results(results)
    
    # 统计总得分：跳过空回答
    # 如果按轮次计分：每个有非空答案的轮次都算一个题
    # 如果按整题计分：每个有非空答案的question_id算一个题
    if count_by_rounds:
        # 按轮次计分：遍历去重后的结果，统计每个有非空答案的轮次
        total_correct = 0
        total_count = 0
        
        for item in deduplicated_results:
            item_id = item.get("question_id", "")
            if not item_id:
                continue
            
            for model_name in enabled_models:
                model_key, entry = _find_model_entry(item, model_name)
                if entry is None:
                    continue
                
                # 使用_count_item统计，它会自动处理空答案和按轮次计分
                count, correct = _count_item(item, model_key, entry, model_name=model_name)
                total_count += count
                total_correct += correct
    else:
        # 按整题计分：每个question_id只统计一次
        # 对于重复的question_id，优先使用有非空答案的记录
        total_correct = 0
        total_count = 0
        seen_question_ids = set()  # 用于去重，保证每个question_id只统计一次
        question_id_to_item = {}  # {question_id: item} 存储每个question_id的第一个有非空答案的记录
        
        # 第一遍：收集每个question_id的第一个有非空答案的记录
        for item in results:
            item_id = item.get("question_id", "")
            if not item_id:
                continue
            
            # 检查是否有非空答案（至少一个模型有非空答案）
            has_valid_answer = False
            for model_name in enabled_models:
                model_key, entry = _find_model_entry(item, model_name)
                if entry is None:
                    continue
                # 检查该模型的answer是否为空
                if not is_answer_empty(item, model_key=model_key, model_name=model_name):
                    has_valid_answer = True
                    break
            
            if item_id not in question_id_to_item:
                # 第一次遇到这个question_id，直接记录
                question_id_to_item[item_id] = item
            else:
                # 重复的question_id
                old_item = question_id_to_item[item_id]
                # 检查旧记录是否有非空答案
                old_has_valid_answer = False
                for model_name in enabled_models:
                    model_key, entry = _find_model_entry(old_item, model_name)
                    if entry is None:
                        continue
                    if not is_answer_empty(old_item, model_key=model_key, model_name=model_name):
                        old_has_valid_answer = True
                        break
                
                # 如果旧记录是空的，新记录是非空的，则替换
                if not old_has_valid_answer and has_valid_answer:
                    question_id_to_item[item_id] = item
                # 如果旧记录是非空的，新记录也是非空的，保持第一个（按出现顺序）
                # 如果旧记录是非空的，新记录是空的，保持旧的
                # 如果都是空的，保持第一个（按出现顺序）
        
        # 第二遍：统计每个question_id（只统计有非空答案的记录）
        for item_id, item in question_id_to_item.items():
            if item_id in seen_question_ids:
                continue
            
            # 检查是否有非空答案（至少一个模型有非空答案）
            # 如果一个question_id有多个模型，只要有一个模型有非空答案且正确，就算这个question_id正确
            has_valid_answer = False
            question_is_correct = False
            
            for model_name in enabled_models:
                model_key, entry = _find_model_entry(item, model_name)
                if entry is None:
                    continue
                # 检查该模型的answer是否为空
                if is_answer_empty(item, model_key=model_key, model_name=model_name):
                    continue
                
                # 找到非空答案
                has_valid_answer = True
                # 检查该模型是否正确
                match_gt = entry.get("match_gt", False)
                if isinstance(match_gt, dict):
                    # 多轮题目：所有轮次都正确才算正确
                    if all(match_gt.values()) if match_gt else False:
                        question_is_correct = True
                        break  # 找到一个正确的模型即可
                else:
                    # 单轮题目
                    if match_gt:
                        question_is_correct = True
                        break  # 找到一个正确的模型即可
            
            # 如果所有模型的答案都为空，跳过该题目
            if not has_valid_answer:
                continue
            
            # 标记该question_id已处理并统计
            seen_question_ids.add(item_id)
            total_count += 1
            if question_is_correct:
                total_correct += 1
    
    stats["total"]["total_count"] = total_count
    stats["total"]["correct_count"] = total_correct
    stats["total"]["accuracy"] = total_correct / total_count if total_count > 0 else 0.0
    
    # 按模型统计（使用去重后的结果）
    for model_name in enabled_models:
        model_total = 0
        model_correct = 0
        
        for item in deduplicated_results:
            model_key, entry = _find_model_entry(item, model_name)
            if entry is None:
                continue
            # 传递model_name用于检查答案是否为空
            count, correct = _count_item(item, model_key, entry, model_name=model_name)
            model_total += count
            model_correct += correct
        
        stats["by_model"][model_name] = {
            "total_count": model_total,
            "correct_count": model_correct,
            "accuracy": model_correct / model_total if model_total > 0 else 0.0
        }
    
    # 按用户画像统计（使用去重后的结果）
    profiles = {item["profile"] for item in deduplicated_results if "profile" in item}
    
    for profile in profiles:
        profile_total = 0
        profile_correct = 0
        
        for item in deduplicated_results:
            if item.get("profile") != profile:
                continue
            for model_name in enabled_models:
                model_key, entry = _find_model_entry(item, model_name)
                if entry is None:
                    continue
                # 传递model_name用于检查答案是否为空
                count, correct = _count_item(item, model_key, entry, model_name=model_name)
                profile_total += count
                profile_correct += correct
        
        stats["by_profile"][profile] = {
            "total_count": profile_total,
            "correct_count": profile_correct,
            "accuracy": profile_correct / profile_total if profile_total > 0 else 0.0
        }
    
    # 按分类字段统计（只统计实际存在的字段，使用去重后的结果）
    category_fields = ["question_type", "fintype", "image_type", "scenario", "capability", "difficulty", "source", "language"]
    
    # 先检查哪些字段实际存在
    existing_fields = set()
    for item in deduplicated_results:
        for field in category_fields:
            if field in item and item[field]:
                existing_fields.add(field)
    
    # 只统计存在的字段
    for category_field in existing_fields:
        category_stats = {}
        
        # 收集所有该字段的值（使用去重后的结果）
        category_values = set()
        for item in deduplicated_results:
            category_value = item.get(category_field)
            if category_value:
                category_values.add(category_value)
        
        # 对每个分类值进行统计（使用去重后的结果）
        for category_value in category_values:
            category_total = 0
            category_correct = 0
            
            for item in deduplicated_results:
                if item.get(category_field) != category_value:
                    continue
                
                for model_name in enabled_models:
                    model_key, entry = _find_model_entry(item, model_name)
                    if entry is None:
                        continue
                    # 传递model_name用于检查答案是否为空
                    count, correct = _count_item(item, model_key, entry, model_name=model_name)
                    category_total += count
                    category_correct += correct
            
            category_stats[category_value] = {
                "total_count": category_total,
                "correct_count": category_correct,
                "accuracy": category_correct / category_total if category_total > 0 else 0.0
            }
        
        if category_stats:
            stats["by_category"][category_field] = category_stats
    
    return stats

