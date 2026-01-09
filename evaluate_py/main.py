"""
评测主脚本
支持多种用户画像、多种模型的评测
"""
import os
import sys
import json
import argparse
import logging
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

# 添加当前目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)
sys.path.insert(0, current_dir)

# 从当前目录（evaluate_py）导入模块
from .data_loader import load_and_validate
from .prompts import get_all_profiles
from .config import MODEL_DEFINITIONS, get_eval_models, USER_PROFILES, EVAL_CONFIG

# 从新拆分的模块导入
from .logger import setup_logging, get_detailed_log_file, close_detailed_log_file
import threading
log_lock = threading.Lock()  # 日志文件写入锁
from .evaluator import evaluate_single_item
from .statistics import calculate_statistics, calculate_output_statistics
from .result_utils import is_answer_empty
from .result_converter import convert_to_module2_format, flush_json_buffer


# 函数已移至 logger.py 和其他模块

def main(args: argparse.Namespace):
    """主函数"""
    # 设置日志（从环境变量读取日志模式）
    log_mode = os.getenv("EVAL_LOG_MODE", "detailed")
    setup_logging(args.log_dir, args.log_level, log_mode)
    
    # 加载数据
    logging.info(f"加载数据: {args.input_file}")
    items = load_and_validate(args.input_file)
    logging.info(f"成功加载 {len(items)} 条数据")
    
    # 输入数据去重：对重复的 question_id 进行去重，只保留第一个出现的记录
    seen_question_ids = set()
    deduplicated_items = []
    duplicate_count = 0
    for item in items:
        item_id = item.get("question_id") or item.get("id", "")
        if item_id:
            if item_id in seen_question_ids:
                duplicate_count += 1
                logging.debug(f"跳过重复的 question_id: {item_id}")
                continue
            seen_question_ids.add(item_id)
        deduplicated_items.append(item)
    
    if duplicate_count > 0:
        logging.info(f"输入数据去重：发现 {duplicate_count} 条重复的 question_id，已过滤，剩余 {len(deduplicated_items)} 条数据")
    else:
        logging.info(f"输入数据去重：未发现重复的 question_id，保留全部 {len(deduplicated_items)} 条数据")
    
    items = deduplicated_items
    
    # 限制处理数量（如果设置了LIMIT环境变量）
    limit = os.getenv("EVAL_LIMIT", "")
    if limit and limit.isdigit():
        limit_num = int(limit)
        if limit_num > 0:
            # 是否随机选择
            use_random = os.getenv("EVAL_USE_RANDOM", "false").lower() in ("true", "1", "yes")
            if use_random:
                import random
                seed = os.getenv("EVAL_SEED", "")
                if seed and seed.isdigit():
                    random.seed(int(seed))
                random.shuffle(items)
            items = items[:limit_num]
            logging.info(f"限制处理数量: {limit_num} 条数据")
    
    # 确定要评测的模型和用户画像
    # 从环境变量读取要评测的模型列表（模型名称对应 MODEL_DEFINITIONS 中的 key）
    eval_model_names = get_eval_models()
    
    if not eval_model_names:
        raise ValueError(
            "没有指定要评测的模型。请在脚本中设置 EVAL_MODELS 环境变量，"
            "例如：export EVAL_MODELS='doubao,GLM,qwenvlmax'"
        )
    
    # 验证模型是否在 MODEL_DEFINITIONS 中
    enabled_models = []
    for model_name in eval_model_names:
        if model_name in MODEL_DEFINITIONS:
            enabled_models.append(model_name)
        else:
            logging.warning(f"模型 '{model_name}' 不在 MODEL_DEFINITIONS 中，已跳过")
    
    if not enabled_models:
        raise ValueError(f"没有有效的模型。请检查 EVAL_MODELS 环境变量和 MODEL_DEFINITIONS 配置")
    
    profiles = args.profiles if args.profiles else USER_PROFILES
    
    logging.info(f"启用的模型: {enabled_models}")
    logging.info(f"用户画像: {profiles}")
    
    # 检查：如果启用断点续传但没有指定输出文件名，报错
    use_custom_output_file = args.output_file is not None and args.output_file != ""
    if args.resume and not use_custom_output_file:
        error_msg = (
            "错误：启用断点续传时必须指定输出文件名（OUTPUT_FILE）。\n"
            "请在 run_eval.sh 中设置 OUTPUT_FILE，例如：OUTPUT_FILE=\"eval_results.json\""
        )
        logging.error(error_msg)
        raise ValueError(error_msg)
    
    # 输出目录固定为 ./outputs，按用户画像和模型分类组织
    base_output_dir = Path("./outputs")
    base_output_dir.mkdir(exist_ok=True)
    
    if use_custom_output_file:
        # 解析指定的输出文件名
        output_file_path = Path(args.output_file)
        # 只使用文件名部分，忽略路径（因为路径由 profile 和 model_name 决定）
        output_file_name = output_file_path.name
        base_name = output_file_path.stem
        file_ext = output_file_path.suffix.lstrip('.')
        
        # 如果文件有扩展名，使用扩展名；否则使用配置中的格式
        if file_ext:
            output_format = file_ext.lower()
        else:
            output_format = EVAL_CONFIG.get("output_format", "json").lower()
            file_ext = output_format
            output_file_name = f"{base_name}.{file_ext}"
        
        logging.info(f"使用指定的输出文件名: {output_file_name}")
        logging.info(f"输出格式: {output_format}")
        logging.info(f"文件将保存在: ./outputs/{{profile}}/{{model_name}}/{output_file_name}")
    else:
        # 使用自动生成的带时间戳的文件名（仅在不断点续传时）
        # 注意：如果启用断点续传，应该已经在上面的检查中报错了
        input_file_name = Path(args.input_file).stem  # 评测集命名（不含扩展名）
        limit_str = str(len(items)) if limit and limit.isdigit() and int(limit) > 0 else "all"
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_format = EVAL_CONFIG.get("output_format", "json").lower()
        output_file_name = f"eval_{input_file_name}_{limit_str}_{timestamp}.{output_format}"
        
        logging.info(f"使用自动生成的输出文件名: {output_file_name}")
        logging.info(f"输出格式: {output_format}")
        logging.info(f"文件将保存在: ./outputs/{{profile}}/{{model_name}}/{output_file_name}")
    
    # 辅助函数：获取下一个版本号的文件路径（类似 module1）
    def get_next_version_path(original_path: Path) -> Path:
        """如果文件已存在，生成_v2、_v3等版本号的文件路径"""
        if not original_path.exists():
            return original_path
        
        base_name = original_path.stem
        ext = original_path.suffix
        dir_path = original_path.parent
        
        counter = 2
        while True:
            new_name = f"{base_name}_v{counter}{ext}"
            new_path = dir_path / new_name
            if not new_path.exists():
                return new_path
            counter += 1
    
    # 为每个模型和用户画像组合创建输出文件
    output_files = {}  # {(model_name, profile): file_path}
    output_file_handles = {}  # {(model_name, profile): file_handle}  # 仅用于JSONL
    completed_items = {}  # {(model_name, profile): set(question_ids)}
    existing_results = {}  # {(model_name, profile): list(results)}
    
    for model_name in enabled_models:
        for profile in profiles:
            # 文件路径：./outputs/{profile}/{model_name}/{output_file_name}
            profile_model_dir = base_output_dir / profile / model_name
            profile_model_dir.mkdir(parents=True, exist_ok=True)
            
            # 断点续传：检查是否存在匹配的输出文件并读取已完成的问题
            existing_file = None
            if args.resume:
                # 断点续传模式下，必须指定了输出文件名（否则应该已经在上面的检查中报错）
                base_output_file = profile_model_dir / output_file_name
                if base_output_file.exists():
                    existing_file = base_output_file
                    output_file = base_output_file
                    logging.info(f"检测到输出文件: {base_output_file}")
                else:
                    # 检查是否有带版本号的文件（_v2, _v3等）
                    base_name_without_ext = Path(output_file_name).stem
                    pattern = f"{base_name_without_ext}_v*.{file_ext}"
                    versioned_files = list(profile_model_dir.glob(pattern))
                    if versioned_files:
                        # 使用最新的版本号文件
                        existing_file = max(versioned_files, key=lambda p: p.stat().st_mtime)
                        output_file = existing_file
                        logging.info(f"检测到带版本号的输出文件: {existing_file}")
                    else:
                        # 输出文件不存在，自动创建
                        output_file = base_output_file
                        logging.info(f"检测到输出文件不存在，将自动创建新文件: {output_file}")
            else:
                # 不续传
                if use_custom_output_file:
                    # 如果指定了输出文件名
                    base_output_file = profile_model_dir / output_file_name
                    if base_output_file.exists():
                        output_file = get_next_version_path(base_output_file)
                        logging.info(f"文件已存在，使用新版本: {output_file}")
                    else:
                        output_file = base_output_file
                else:
                    # 如果未指定输出文件名，生成新的带时间戳的文件名
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    output_file_name = f"eval_{input_file_name}_{limit_str}_{timestamp}.{output_format}"
                    output_file = profile_model_dir / output_file_name
            
            # 如果找到了已存在的文件，读取已完成的问题
            if existing_file and existing_file.exists():
                # 验证文件元数据（检查输入文件路径是否匹配）
                try:
                    if output_format == "jsonl":
                        # JSONL格式：读取第一行（统计信息）和已有结果
                        with open(existing_file, 'r', encoding='utf-8') as f:
                            first_line = f.readline().strip()
                            stats_data = {}
                            if first_line:
                                try:
                                    stats_data = json.loads(first_line)
                                except json.JSONDecodeError:
                                    pass
                            
                            # 读取已有结果
                            all_items = []
                            for line in f:
                                line = line.strip()
                                if not line:
                                    continue
                                try:
                                    item = json.loads(line)
                                    # 跳过统计信息行（如果被误读）
                                    if "statistics" in item and "question_id" not in item:
                                        continue
                                    all_items.append(item)
                                except json.JSONDecodeError:
                                    continue
                            
                            # 如果文件只有统计信息，没有数据行，记录日志
                            if len(all_items) == 0:
                                logging.info(f"  文件只有统计信息，没有数据行，将从头开始评测")
                            
                            # 去重逻辑：对于每个question_id，选取第一个非空答案的记录
                            # 如果所有记录都是空的，才需要重新评测
                            # 注意：保留所有记录在文件中，但在内存中只保留第一个非空答案的记录用于续连判断
                            cleaned_items = []
                            seen_ids = set()  # 已处理的question_id
                            question_id_to_item = {}  # {question_id: item} 存储每个question_id的第一个非空答案记录
                            question_id_has_valid_answer = {}  # {question_id: bool} 标记是否已找到非空答案
                            completed_ids = set()  # 只包含非空答案的question_id
                            removed_duplicate_count = 0
                            empty_answer_count = 0
                            
                            for item in all_items:
                                item_id = item.get("question_id", "")
                                if not item_id:
                                    continue
                                
                                # 如果已经找到非空答案，跳过后续重复记录
                                if item_id in question_id_has_valid_answer and question_id_has_valid_answer[item_id]:
                                    removed_duplicate_count += 1
                                    continue
                                
                                # 检查answer是否为空
                                is_empty = is_answer_empty(item, model_name=model_name)
                                
                                if item_id not in seen_ids:
                                    # 第一次遇到这个question_id
                                    seen_ids.add(item_id)
                                    if not is_empty:
                                        # 非空答案，直接使用，标记已找到非空答案
                                        question_id_to_item[item_id] = item
                                        question_id_has_valid_answer[item_id] = True
                                        completed_ids.add(item_id)
                                    else:
                                        # 空答案，先记录，继续查找是否有非空答案
                                        question_id_to_item[item_id] = item
                                        question_id_has_valid_answer[item_id] = False
                                        empty_answer_count += 1
                                        logging.debug(f"  发现answer为空的记录: question_id={item_id}，继续查找是否有非空答案")
                                else:
                                    # 重复的question_id，且之前还没找到非空答案
                                    removed_duplicate_count += 1
                                    if not is_empty:
                                        # 找到第一个非空答案，替换之前的空答案记录
                                        question_id_to_item[item_id] = item
                                        question_id_has_valid_answer[item_id] = True
                                        completed_ids.add(item_id)
                                        empty_answer_count -= 1  # 之前算作空答案，现在不算了
                                        logging.debug(f"  找到第一个非空答案记录，替换之前的空答案: question_id={item_id}")
                                    # 如果当前记录是空的，忽略（继续使用之前找到的记录）
                            
                            # 构建cleaned_items：只包含每个question_id的第一个非空答案记录（如果都是空的，则保留第一个空答案记录）
                            for item_id, item in question_id_to_item.items():
                                cleaned_items.append(item)
                            
                            # 统计：completed_ids中只包含有非空答案的question_id
                            # 如果question_id不在completed_ids中，说明所有记录都是空的，需要重新评测
                            
                            # JSONL格式在断点续传模式下：不去重文件，只在内存中去重，文件保持不变
                            # 这样可以避免重写文件导致的数据丢失风险
                            if removed_duplicate_count > 0:
                                logging.warning(f"  ⚠️ 发现 {removed_duplicate_count} 条重复记录，已在内存中去重，但文件保持不变（避免数据丢失）")
                                logging.warning(f"  ⚠️ 重复记录将在最终更新统计信息时统一处理")
                            elif empty_answer_count > 0:
                                logging.info(f"  发现 {empty_answer_count} 条空答案记录，这些题目将重新评测")
                            
                            results_list = cleaned_items
                            completed_items[(model_name, profile)] = completed_ids
                            existing_results[(model_name, profile)] = results_list
                            output_file = existing_file
                            logging.info(f"  已加载 {len(completed_ids)} 个已完成的问题（非空答案），{empty_answer_count} 个空答案问题将重新评测")
                    else:
                        # JSON格式：读取完整文件
                        with open(existing_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            if isinstance(data, dict) and "results" in data:
                                # 读取已有结果
                                all_items = data.get("results", [])
                                
                                # 去重逻辑：对于每个question_id，选取第一个非空答案的记录
                                # 如果所有记录都是空的，才需要重新评测
                                cleaned_items = []
                                seen_ids = set()  # 已处理的question_id
                                question_id_to_item = {}  # {question_id: item} 存储每个question_id的第一个非空答案记录
                                question_id_has_valid_answer = {}  # {question_id: bool} 标记是否已找到非空答案
                                completed_ids = set()  # 只包含非空答案的question_id
                                removed_duplicate_count = 0
                                empty_answer_count = 0
                                
                                for item in all_items:
                                    item_id = item.get("question_id", "")
                                    if not item_id:
                                        continue
                                    
                                    # 如果已经找到非空答案，跳过后续重复记录
                                    if item_id in question_id_has_valid_answer and question_id_has_valid_answer[item_id]:
                                        removed_duplicate_count += 1
                                        continue
                                    
                                    # 检查answer是否为空
                                    is_empty = is_answer_empty(item, model_name=model_name)
                                    
                                    if item_id not in seen_ids:
                                        # 第一次遇到这个question_id
                                        seen_ids.add(item_id)
                                        if not is_empty:
                                            # 非空答案，直接使用，标记已找到非空答案
                                            question_id_to_item[item_id] = item
                                            question_id_has_valid_answer[item_id] = True
                                            completed_ids.add(item_id)
                                        else:
                                            # 空答案，先记录，继续查找是否有非空答案
                                            question_id_to_item[item_id] = item
                                            question_id_has_valid_answer[item_id] = False
                                            empty_answer_count += 1
                                            logging.debug(f"  发现answer为空的记录: question_id={item_id}，继续查找是否有非空答案")
                                    else:
                                        # 重复的question_id，且之前还没找到非空答案
                                        removed_duplicate_count += 1
                                        if not is_empty:
                                            # 找到第一个非空答案，替换之前的空答案记录
                                            question_id_to_item[item_id] = item
                                            question_id_has_valid_answer[item_id] = True
                                            completed_ids.add(item_id)
                                            empty_answer_count -= 1  # 之前算作空答案，现在不算了
                                            logging.debug(f"  找到第一个非空答案记录，替换之前的空答案: question_id={item_id}")
                                        # 如果当前记录是空的，忽略（继续使用之前找到的记录）
                                
                                # 构建cleaned_items：只包含每个question_id的第一个非空答案记录（如果都是空的，则保留第一个空答案记录）
                                for item_id, item in question_id_to_item.items():
                                    cleaned_items.append(item)
                                
                                # 统计：completed_ids中只包含有非空答案的question_id
                                # 如果question_id不在completed_ids中，说明所有记录都是空的，需要重新评测
                                
                                # JSON格式在断点续传模式下：使用原子写入机制，避免数据丢失
                                if removed_duplicate_count > 0:
                                    # 安全检查：如果去重后没有数据，但原始数据也不为空，说明可能有问题，不重写文件
                                    if len(cleaned_items) == 0 and len(all_items) > 0:
                                        logging.error(f"  ❌ 严重错误：去重后数据为空，但原始数据有 {len(all_items)} 条！跳过重写文件，避免数据丢失！")
                                        logging.error(f"  ❌ 请检查文件: {existing_file}")
                                        cleaned_items = all_items  # 使用原始数据，避免数据丢失
                                    else:
                                        logging.info(f"  去重处理: 删除了 {removed_duplicate_count} 条重复记录，保留了 {empty_answer_count} 条空答案记录（将重新评测）")
                                    
                                    # 使用原子写入：先写入临时文件，成功后再替换原文件
                                    data["results"] = cleaned_items
                                    # 重新计算统计信息
                                    stats = calculate_output_statistics(cleaned_items, enabled_models)
                                    data["statistics"] = stats
                                    
                                    # 原子写入：先写临时文件
                                    temp_file = existing_file.with_suffix(existing_file.suffix + '.tmp')
                                    try:
                                        with open(temp_file, 'w', encoding='utf-8') as f:
                                            json.dump(data, f, ensure_ascii=False, indent=2)
                                        # 写入成功后再替换原文件（原子操作）
                                        temp_file.replace(existing_file)
                                        logging.info(f"  已安全重写文件，保留 {len(cleaned_items)} 条记录（包括空答案）")
                                    except Exception as e:
                                        logging.error(f"  ❌ 写入临时文件失败: {e}，保留原文件不变")
                                        if temp_file.exists():
                                            temp_file.unlink()  # 清理临时文件
                                        raise
                                elif empty_answer_count > 0:
                                    logging.info(f"  发现 {empty_answer_count} 条空答案记录，这些题目将重新评测")
                                
                                results_list = cleaned_items
                                completed_items[(model_name, profile)] = completed_ids
                                existing_results[(model_name, profile)] = results_list
                                output_file = existing_file
                                logging.info(f"  已加载 {len(completed_ids)} 个已完成的问题（非空答案），{empty_answer_count} 个空答案问题将重新评测")
                except Exception as e:
                    logging.warning(f"加载已有文件失败: {e}，将创建新文件")
                    # 如果加载失败，使用新文件路径（不覆盖 existing_file）
                    pass
            
            output_files[(model_name, profile)] = output_file
            
            # JSONL格式：打开文件句柄（追加模式）
            if output_format == "jsonl":
                file_handle = open(output_file, 'a', encoding='utf-8')
                output_file_handles[(model_name, profile)] = file_handle
                
                # 如果是新文件，写入统计信息占位符（第一行）
                if output_file.stat().st_size == 0:
                    stats_placeholder = {
                        "statistics": {
                            "total": {"total_count": 0, "correct_count": 0, "accuracy": 0.0},
                            "by_model": {},
                            "by_profile": {},
                            "by_category": {}
                        }
                    }
                    file_handle.write(json.dumps(stats_placeholder, ensure_ascii=False) + '\n')
                    file_handle.flush()
    
    # 初始化批量写入buffer（仅用于JSON格式）
    batch_size = EVAL_CONFIG.get("batch_size", 10)  # 默认每10条保存一次
    result_buffers = {}  # {(model_name, profile): list(results)}
    for model_name in enabled_models:
        for profile in profiles:
            # buffer应该初始化为空列表，只用于存储新添加的结果（待保存的）
            # existing_results已经在文件中，flush_json_buffer会从文件中读取，不应该放入buffer以避免重复
            result_buffers[(model_name, profile)] = []
    
    # 辅助函数已移至 result_utils.py 和 result_converter.py
    from .result_utils import build_process_value

    # 辅助函数：将结果转换为module2格式并写入
    # 并发配置（均分逻辑：确保每个模型-画像组合得到相同的并发数）
    workers = os.getenv("EVAL_WORKERS", "")
    try:
        workers = int(workers) if str(workers).strip() else 1
    except ValueError:
        workers = 1
    if workers <= 0:
        workers = 1
    separator = "=" * 40
    combos = [(m, p) for m in enabled_models for p in profiles]
    num_combos = len(combos)
    
    # 均分逻辑：确保每个组合得到相同的并发数
    # 1. 计算每个组合应该得到的并发数（向下取整，确保均分）
    per_combo_workers = max(1, workers // num_combos)
    
    # 2. 计算实际同时运行的组合数
    #    如果每个组合的并发数 * 组合数 <= workers，所有组合同时运行
    #    否则，限制同时运行的组合数，确保总并发不超过workers
    if per_combo_workers * num_combos <= workers:
        # 所有组合同时运行，每个组合使用 per_combo_workers 个并发
        combo_workers = num_combos
        actual_per_combo = per_combo_workers
    else:
        # 限制同时运行的组合数（这种情况很少见，通常发生在 workers < num_combos 时）
        combo_workers = max(1, workers // per_combo_workers)
        actual_per_combo = max(1, workers // combo_workers)
    
    # 3. 验证总并发
    actual_total_workers = combo_workers * actual_per_combo
    
    logging.info(
        f"并发配置（均分）: "
        f"总并发={workers}, "
        f"模型数={len(enabled_models)} ({', '.join(enabled_models)}), "
        f"画像数={len(profiles)} ({', '.join(profiles)}), "
        f"组合数={num_combos}, "
        f"同时运行组合数={combo_workers}, "
        f"每个组合并发数={actual_per_combo}, "
        f"实际总并发={actual_total_workers}"
    )
    
    if actual_total_workers < workers:
        unused = workers - actual_total_workers
        logging.warning(
            f"⚠️ 并发数未完全利用: 配置={workers}, 实际={actual_total_workers}, "
            f"浪费={unused}个并发（建议将WORKERS调整为{num_combos}的倍数，如{num_combos * actual_per_combo}）"
        )
    elif actual_total_workers == workers:
        logging.info(f"✅ 并发数完全利用: 所有{workers}个并发均分给{num_combos}个组合，每个组合{actual_per_combo}个并发")
    
    # 使用实际计算的值
    per_combo_workers = actual_per_combo

    # 评测每个模型/用户画像组合，并行调度组合，在组合内部再并发题目（多轮视为单任务）
    failures = []  # 收集失败问题

    def process_combo(model_name: str, profile: str):
        key = (model_name, profile)
        logging.info(f"\n{separator}\n开始模型: {model_name} | 画像: {profile}\n{separator}")
        futures = {}
        try:
            with ThreadPoolExecutor(max_workers=per_combo_workers) as executor:
                for item in items:
                    item_id = item.get("question_id") or item.get("id", "")
                    if item_id and item_id in completed_items.get(key, set()):
                        continue
                    future = executor.submit(
                        evaluate_single_item,
                        item,
                        [model_name],  # 单模型，避免内部再次并行
                        [profile],
                        1             # 内部不开线程池
                    )
                    futures[future] = item_id
                
                # 为每个模型/画像组合单独显示一个进度条，前缀包含模型名和画像，便于区分
                for future in tqdm(
                    as_completed(futures),
                    total=len(futures),
                    desc=f"{model_name}-{profile}",
                ):
                    item_id = futures[future]
                    try:
                        result = future.result()
                    except Exception as e:
                        failures.append({"question_id": item_id, "reason": f"future exception: {e}"})
                        continue
                    
                    if not result:
                        failures.append({"question_id": item_id, "reason": "evaluate_single_item returned None"})
                        continue
                    if isinstance(result, dict) and "error" in result:
                        failures.append({"question_id": result.get("question_id", item_id), "reason": result.get("error", "unknown error")})
                        continue
                    
                    module2_item = convert_to_module2_format(result, model_name, profile)
                    if not module2_item:
                        continue
                    
                    item_id = module2_item.get("question_id", "") or item_id
                    if not item_id:
                        continue
                    
                    # 检查是否已存在（避免重复写入）
                    if item_id in completed_items.get(key, set()):
                        logging.debug(f"  跳过已存在的question_id: {item_id}")
                        continue
                    
                    # 添加到已完成列表
                    if key not in completed_items:
                        completed_items[key] = set()
                    completed_items[key].add(item_id)
                    
                    if output_format == "jsonl":
                        file_handle = output_file_handles.get(key)
                        if file_handle:
                            try:
                                file_handle.write(json.dumps(module2_item, ensure_ascii=False) + '\n')
                                file_handle.flush()
                            except Exception as e:
                                logging.error(f"实时写入失败 ({model_name}, {profile}): {e}")
                    else:
                        if key not in result_buffers:
                            result_buffers[key] = []
                        result_buffers[key].append(module2_item)
                        
                        if len(result_buffers[key]) >= batch_size:
                            flush_json_buffer(model_name, profile, result_buffers, output_files, enabled_models)
        finally:
            # 确保当前模型画像的缓冲被刷新（即使异常/中断）
            if output_format == "json":
                flush_json_buffer(model_name, profile, result_buffers, output_files, enabled_models)

    interrupted = False
    try:
        with ThreadPoolExecutor(max_workers=combo_workers) as combo_executor:
            combo_future_map = {combo_executor.submit(process_combo, m, p): (m, p) for m, p in combos}
            for future in as_completed(combo_future_map):
                m, p = combo_future_map[future]
                try:
                    future.result()
                except Exception as e:
                    failures.append({"question_id": "", "reason": f"combo {m}-{p} exception: {e}"})
    except KeyboardInterrupt:
        interrupted = True
        logging.warning("检测到中断信号，正在尝试优雅停止并刷盘...")
        try:
            combo_executor.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass

    # 关闭所有文件句柄（JSONL格式，在更新统计信息前关闭）
    if output_format == "jsonl":
        for key, file_handle in output_file_handles.items():
            try:
                file_handle.close()
            except Exception as e:
                logging.warning(f"关闭文件句柄失败 {key}: {e}")
    
    # 刷新所有buffer（JSON格式）
    if output_format == "json":
        logging.info("\n刷新所有buffer...")
        for model_name in enabled_models:
            for profile in profiles:
                flush_json_buffer(model_name, profile, result_buffers, output_files, enabled_models)
    
    # 更新统计信息并保存最终结果
    logging.info("\n更新统计信息...")
    for model_name in enabled_models:
        for profile in profiles:
            key = (model_name, profile)
            output_file = output_files[key]
            
            try:
                if output_format == "jsonl":
                    # JSONL格式：读取所有结果，重新计算统计信息，更新第一行
                    all_results = []
                    with open(output_file, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        if lines:
                            # 跳过第一行（统计信息）
                            for line in lines[1:]:
                                line = line.strip()
                                if line:
                                    try:
                                        all_results.append(json.loads(line))
                                    except json.JSONDecodeError:
                                        continue
                    
                    # 保留所有记录，不去重（用户要求不准删除数据）
                    # 只统计重复记录数量用于日志，但不删除
                    duplicate_count = 0
                    seen_ids = set()
                    for item in all_results:
                        item_id = item.get("question_id", "")
                        if item_id and item_id in seen_ids:
                            duplicate_count += 1
                        if item_id:
                            seen_ids.add(item_id)
                    
                    # 保留所有记录，不去重
                    final_list = all_results
                    
                    if duplicate_count > 0:
                        # 只记录日志，不删除数据
                        duplicate_ratio = duplicate_count / len(all_results) if all_results else 0
                        logging.info(f"  发现 {duplicate_count} 条重复的 question_id（重复率 {duplicate_ratio*100:.1f}%），但保留所有记录，不删除数据")
                    
                    # 安全检查1：如果数据为空，但文件大小较大（说明文件之前可能有数据），不重写文件
                    file_size = output_file.stat().st_size
                    # 统计信息占位符大约200-300字节，如果文件大于1KB但读取不到数据，可能是读取问题
                    if len(final_list) == 0 and file_size > 1024:
                        logging.warning(f"  ⚠️ 警告：文件大小 {file_size} 字节，但读取不到数据！可能是文件格式问题，跳过重写文件，避免数据丢失！")
                        logging.warning(f"  ⚠️ 请检查文件: {output_file}")
                        continue
                    
                    # 重新计算统计信息（使用所有记录，不去重）
                    stats = calculate_output_statistics(final_list, enabled_models)
                    
                    # 原子写入：先写入临时文件，成功后再替换原文件（避免数据丢失）
                    temp_file = output_file.with_suffix(output_file.suffix + '.tmp')
                    try:
                        with open(temp_file, 'w', encoding='utf-8') as f:
                            f.write(json.dumps({"statistics": stats}, ensure_ascii=False) + '\n')
                            for item in final_list:
                                f.write(json.dumps(item, ensure_ascii=False) + '\n')
                        # 写入成功后再替换原文件（原子操作）
                        temp_file.replace(output_file)
                        logging.info(f"已安全更新统计信息: {output_file.name} (共 {len(final_list)} 条结果，保留所有记录)")
                    except Exception as e:
                        logging.error(f"  ❌ 写入临时文件失败: {e}，保留原文件不变")
                        if temp_file.exists():
                            temp_file.unlink()  # 清理临时文件
                        raise
                else:
                    # JSON格式：重新计算统计信息
                    with open(output_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    all_results = data.get("results", [])
                    stats = calculate_output_statistics(all_results, enabled_models)
                    data["statistics"] = stats
                    
                    # 原子写入：先写入临时文件，成功后再替换原文件（避免数据丢失）
                    temp_file = output_file.with_suffix(output_file.suffix + '.tmp')
                    try:
                        with open(temp_file, 'w', encoding='utf-8') as f:
                            json.dump(data, f, ensure_ascii=False, indent=2)
                        # 写入成功后再替换原文件（原子操作）
                        temp_file.replace(output_file)
                        logging.info(f"已安全更新统计信息: {output_file.name} (共 {len(all_results)} 条结果)")
                    except Exception as e:
                        logging.error(f"  ❌ 写入临时文件失败: {e}，保留原文件不变")
                        if temp_file.exists():
                            temp_file.unlink()  # 清理临时文件
                        raise
            except Exception as e:
                logging.error(f"更新统计信息失败 ({model_name}, {profile}): {e}")
    
    # 如果是中断退出，保存完就立刻静默退出（不再打印后续摘要日志）
    if interrupted:
        logging.info(f"\n评测中断，但已保存当前结果并更新统计，共生成 {len(output_files)} 个输出文件，准备静默退出。")
        # 直接退出进程，避免线程池清理阶段产生多余日志
        os._exit(0)
    
    logging.info(f"\n评测完成！共生成 {len(output_files)} 个输出文件")
    
    # 失败摘要
    logging.info("\n" + "="*60)
    logging.info("失败摘要")
    logging.info("="*60)
    if not failures:
        logging.info("所有问题均处理成功，未记录失败。")
    else:
        logging.info(f"失败总数: {len(failures)}")
        for fail in failures:
            logging.info(f"- question_id: {fail.get('question_id','')} | reason: {fail.get('reason','')}")
    # 详细日志文件也写入失败摘要
    detailed_log_file = get_detailed_log_file()
    if detailed_log_file:
        with log_lock:
            try:
                detailed_log_file.write("=" * 80 + "\n")
                detailed_log_file.write("失败摘要\n")
                detailed_log_file.write("=" * 80 + "\n")
                if not failures:
                    detailed_log_file.write("所有问题均处理成功，未记录失败。\n")
                else:
                    detailed_log_file.write(f"失败总数: {len(failures)}\n")
                    for fail in failures:
                        detailed_log_file.write(f"- question_id: {fail.get('question_id','')} | reason: {fail.get('reason','')}\n")
                detailed_log_file.write("\n")
                detailed_log_file.flush()
            except Exception as e:
                logging.warning(f"写入失败摘要到详细日志失败: {e}")
    
    # 打印统计摘要（从输出文件中读取）
    logging.info("\n" + "="*60)
    logging.info("统计摘要")
    logging.info("="*60)
    
    for model_name in enabled_models:
        for profile in profiles:
            key = (model_name, profile)
            output_file = output_files[key]
            
            try:
                if output_file.exists():
                    if output_format == "jsonl":
                        with open(output_file, 'r', encoding='utf-8') as f:
                            first_line = f.readline().strip()
                            if first_line:
                                stats_data = json.loads(first_line)
                                stats = stats_data.get("statistics", {})
                    else:
                        with open(output_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            stats = data.get("statistics", {})
                    
                    total_stats = stats.get("total", {})
                    logging.info(f"\n{model_name} - {profile}:")
                    logging.info(f"  总准确率: {total_stats.get('accuracy', 0):.2%} ({total_stats.get('correct_count', 0)}/{total_stats.get('total_count', 0)})")
            except Exception as e:
                logging.warning(f"读取统计信息失败 ({model_name}, {profile}): {e}")
    
    
    # 关闭详细日志文件
    close_detailed_log_file()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='金融领域多用户画像评测脚本')
    parser.add_argument('--input_file', type=str, required=True, help='输入文件路径（支持 JSON、JSONL、CSV、Excel (.xlsx/.xls)）')
    parser.add_argument('--output_file', type=str, default=None, 
                       help='输出文件名（可选，支持 .json 或 .jsonl）。文件将保存在 ./outputs/{profile}/{model_name}/ 目录下')
    parser.add_argument('--log_dir', type=str, default='logs', help='日志目录')
    parser.add_argument('--log_level', type=str, default='INFO', help='日志级别')
    parser.add_argument('--profiles', type=str, nargs='+', default=None, 
                       help='用户画像列表（beginner/retail/expert/expert_cot），默认全部')
    parser.add_argument('--resume', action='store_true', help='是否启用断点续跑（从输出文件中读取已处理的问题）')
    
    args = parser.parse_args()
    main(args)
