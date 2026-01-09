"""
评测核心逻辑模块
负责单个数据项的评测
"""
import os
import json
import logging
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from .prompts import get_prompt, normalize_question_type, QUESTION_TYPE_MAPPING
from .model_api import (
    call_model_api, extract_answer_from_response,
    get_image_format, encode_image, estimate_text_tokens,
    _determine_image_compression_settings
)
from .judge import judge_answer
from .config import EVAL_CONFIG
from .logger import (
    sanitize_messages_for_log,
    log_model_response_detailed,
    log_judge_response_detailed,
    get_log_mode,
    get_detailed_log_file
)

def evaluate_single_item(
    item: Dict[str, Any],
    enabled_models: List[str],
    profiles: List[str],
    workers: int = 1
) -> Optional[Dict[str, Any]]:
    """
    评测单个数据项
    
    Args:
        item: 数据项
        enabled_models: 启用的模型列表
        profiles: 用户画像列表
        
    Returns:
        评测结果字典，如果失败返回 None
    """
    # 获取问题ID
    item_id = item.get("question_id") or item.get("id", "")
    
    logging.info(f"\n{'='*60}")
    logging.info(f"评测数据项: {item_id}")
    logging.info(f"{'='*60}")
    
    try:
        # 获取数据项信息
        question = item.get("question", "")
        answer = item.get("answer", "")
        options = item.get("options")
        
        # 处理image_path：支持多张图片（可能是字符串、列表、逗号分隔或分号分隔的字符串）
        image_path_raw = item.get("image_path", "")
        image_paths = []
        
        if image_path_raw:
            if isinstance(image_path_raw, list):
                # 已经是列表格式（Excel/CSV 导入时已处理）
                image_paths = image_path_raw
            elif isinstance(image_path_raw, str):
                # 字符串格式：可能是单个路径、逗号分隔或分号分隔的多个路径
                # 优先检查分号（CSV/Excel 格式），然后检查逗号（JSON 格式）
                if ';' in image_path_raw:
                    # 分号分隔的多个路径（CSV/Excel 格式）
                    image_paths = [path.strip() for path in image_path_raw.split(';') if path.strip()]
                elif ',' in image_path_raw:
                    # 逗号分隔的多个路径（JSON 格式）
                    image_paths = [path.strip() for path in image_path_raw.split(',') if path.strip()]
                else:
                    # 单个路径
                    image_paths = [image_path_raw.strip()] if image_path_raw.strip() else []
            else:
                # 其他类型，转换为字符串
                image_paths = [str(image_path_raw)] if image_path_raw else []
        
        # 支持image_urls字段（第二种格式）
        image_urls = item.get("image_urls", [])
        if image_urls:
            # 如果是URL，也添加到路径列表（API调用时会处理）
            if isinstance(image_urls, list):
                image_paths.extend(image_urls)
            else:
                image_paths.append(image_urls)
        
        # 去重并过滤空值
        image_paths = [path for path in image_paths if path and str(path).strip()]
        
        # 如果存在本地图片路径但文件缺失，则跳过整个题目的评测，在失败摘要中报错
        missing_local_images = [
            path for path in image_paths
            if isinstance(path, str)
            and not path.startswith(("http://", "https://"))
            and not os.path.exists(path)
        ]
        
        if missing_local_images:
            # 构造简要错误信息（只展示前几项，避免日志过长）
            sample = ", ".join(missing_local_images[:3])
            more = "" if len(missing_local_images) <= 3 else f" 等共 {len(missing_local_images)} 张"
            
            # 根据配置决定行为
            skip_missing_images = EVAL_CONFIG.get("skip_missing_images", False)
            if skip_missing_images:
                # 如果启用跳过缺失图片选项，则只记录警告并移除缺失的图片路径，继续评测
                logging.warning(f"题目 {item_id} 存在缺失图片，已移除缺失的图片路径，继续评测（不包含图片）。缺失文件示例: {sample}{more}")
                # 从 image_paths 中移除缺失的图片路径
                image_paths = [path for path in image_paths if path not in missing_local_images]
            else:
                # 默认行为：跳过整个题目的评测，在失败摘要中报错
                msg = f"题目 {item_id} 存在缺失图片，已跳过本题评测。缺失文件示例: {sample}{more}"
                # 抛出异常，由上层捕获并记录到失败摘要
                raise FileNotFoundError(msg)
        
        # 判断是否为多轮问答格式
        is_multi_round = item.get("is_multi_round", False)
        if not is_multi_round:
            # 检查是否为多轮格式（question和answer都是字典，且都有round开头的key）
            if isinstance(question, dict) and isinstance(answer, dict):
                # 确保字典不为空
                if question and answer:
                    # 获取question中所有以round开头的key
                    round_keys_in_question = [k for k in question.keys() if k.startswith("round")]
                    # 获取answer中所有以round开头的key
                    round_keys_in_answer = [k for k in answer.keys() if k.startswith("round")]
                    
                    # 判断条件：
                    # 1. question中至少有一个round开头的key
                    # 2. answer中至少有一个round开头的key
                    # 3. question和answer中至少有一个共同的round key（确保数据完整性）
                    if round_keys_in_question and round_keys_in_answer:
                        # 检查是否有共同的round key
                        common_round_keys = set(round_keys_in_question) & set(round_keys_in_answer)
                        if common_round_keys:
                            is_multi_round = True
                            logging.debug(f"🔍 题目 {item_id}: 自动识别为多轮题目，round_keys={sorted(common_round_keys)}")
                        else:
                            logging.warning(f"⚠️ 题目 {item_id}: question和answer都有round key，但没有共同的key，question_rounds={round_keys_in_question}, answer_rounds={round_keys_in_answer}")
                    elif round_keys_in_question:
                        # 如果question有round key但answer没有，可能是数据不完整，但依然认为是多轮题目
                        is_multi_round = True
                        logging.warning(f"⚠️ 题目 {item_id}: question有round key但answer没有，question_rounds={round_keys_in_question}, answer_rounds={round_keys_in_answer}")
        
        # 调试：记录多轮题目判断结果
        if isinstance(question, dict) and isinstance(answer, dict):
            round_keys_in_question = [k for k in question.keys() if k.startswith("round")]
            round_keys_in_answer = [k for k in answer.keys() if k.startswith("round")]
            logging.debug(f"🔍 题目 {item_id}: question类型={type(question)}, answer类型={type(answer)}, question_round_keys={round_keys_in_question}, answer_round_keys={round_keys_in_answer}, is_multi_round={is_multi_round}")
        
        has_options = options is not None and isinstance(options, dict) and any(options.values()) if options else False
        
        # 获取并标准化题型（统一转换为中文）
        raw_question_type = item.get("question_type", "")
        normalized_question_type = ""
        if raw_question_type:
            normalized_question_type = normalize_question_type(raw_question_type)
        
        # 定义选择题类型（中文）
        # 注意：判断题不是选择题，不需要输入选项
        CHOICE_QUESTION_TYPES = {"单选题", "多选题", "多轮单选题"}
        
        # 检查选择题是否有选项（在开始评测前）
        def is_choice_question(q_type: str) -> bool:
            """判断是否是选择题类型"""
            if not q_type:
                return False
            return q_type in CHOICE_QUESTION_TYPES
        
        def has_valid_options(opts) -> bool:
            """检查选项是否有效（非空字典且有值）"""
            if opts is None:
                return False
            if not isinstance(opts, dict):
                return False
            # 检查是否有非空值
            return any(v for v in opts.values() if v)
        
        # 对于多轮题目，检查每一轮
        if is_multi_round:
            # 获取所有轮次
            round_keys = sorted(
                [k for k in question.keys() if k.startswith("round")],
                key=lambda x: int(x.replace("round", "")) if x.replace("round", "").isdigit() else 999
            )
            
            # 判断该轮是否是选择题
            # 多轮单选题整个题目都是选择题，每一轮都需要选项
            if normalized_question_type == "多轮单选题":
                # 检查是否有选项
                if not isinstance(options, dict) or not options:
                    error_msg = f"题目 {item_id} 是多轮单选题，但缺少选项（options为空或无效），已跳过本题评测"
                    logging.error(error_msg)
                    raise ValueError(error_msg)
                
                # 检查选项格式：可能是每轮独立或所有轮次共用
                # 1. 每轮独立：options = {"round1": {"A": "..."}, "round2": {"A": "..."}}
                # 2. 所有轮次共用：options = {"A": "...", "B": "..."}
                has_round_keys = any(k.startswith("round") for k in options.keys())
                
                if has_round_keys:
                    # 每轮独立选项格式：检查每一轮都有选项
                    for round_key in round_keys:
                        round_options = options.get(round_key)
                        if not has_valid_options(round_options):
                            error_msg = f"题目 {item_id} 是多轮单选题，但轮次 {round_key} 缺少选项（options为空或无效），已跳过本题评测"
                            logging.error(error_msg)
                            raise ValueError(error_msg)
                else:
                    # 所有轮次共用选项格式：检查选项是否有效
                    if not has_valid_options(options):
                        error_msg = f"题目 {item_id} 是多轮单选题，但共用选项无效（options为空或无效），已跳过本题评测"
                        logging.error(error_msg)
                        raise ValueError(error_msg)
                # 其他多轮题目（如多轮问答题）不需要选项，跳过检查
        else:
            # 单轮题目：如果是选择题但没有选项，报错
            if is_choice_question(normalized_question_type):
                if not has_valid_options(options):
                    error_msg = f"题目 {item_id} 是{normalized_question_type}，但缺少选项（options为空或无效），已跳过本题评测"
                    logging.error(error_msg)
                    raise ValueError(error_msg)
        
        # 存储所有评测结果（使用标准格式字段名，题型使用中文）
        results = {
            "question_id": item_id,
            "image_id": item.get("image_id", ""),
            "image_path": image_paths[0] if image_paths else "",  # 保存第一个路径用于显示
            "image_paths": image_paths,  # 保存所有图片路径
            "image_type": item.get("image_type", ""),
            "question_type": normalized_question_type or raw_question_type,  # 使用中文题型
            "question": question,
            "answer": answer,
            "options": options,
            "is_multi_round": is_multi_round,
            "profiles": {}
        }
        
        # 保留分类字段（用于统计）
        for field in ["scenario", "capability", "difficulty", "source", "language"]:
            if field in item:
                results[field] = item[field]
        
        # 保留 original_image_path 字段（不参与评测，但输出时需要记录）
        if "original_image_path" in item:
            results["original_image_path"] = item["original_image_path"]
        
        # 对每个用户画像进行评测
        for profile in profiles:
            logging.info(f"\n--- 用户画像: {profile} ---")
            
            profile_results = {
                "profile": profile,
                "models": {}
            }
            
            # 处理多轮问答
            if is_multi_round:
                logging.info(f"✅ 识别为多轮题目，开始逐轮评测")
                # 多轮问答：使用对话历史逐轮评测
                rounds_data = {}
                all_rounds_correct = True
                total_response_time = 0
                total_judge_time = 0
                
                # 获取所有轮次（按round1, round2...排序）
                round_keys = sorted(
                    [k for k in question.keys() if k.startswith("round")],
                    key=lambda x: int(x.replace("round", "")) if x.replace("round", "").isdigit() else 999
                )
                
                # 为每个模型维护对话历史（messages列表）
                # 格式：{model_name: [{"role": "user", "content": ...}, {"role": "assistant", "content": ...}, ...]}
                conversation_history = {model_name: [] for model_name in enabled_models}
                
                for round_key in round_keys:
                    round_num = round_key.replace("round", "")
                    round_question = question.get(round_key, "")
                    round_answer = answer.get(round_key, "")
                    # 获取该轮次对应的选项
                    round_options = options.get(round_key) if isinstance(options, dict) else None
                    
                    logging.info(f"  轮次 {round_num}: {round_question[:100]}...")
                    
                    # 对每个启用的模型进行评测
                    for model_name in enabled_models:
                        # model_name 直接对应 MODEL_DEFINITIONS 中的 key
                        if round_key not in rounds_data:
                            rounds_data[round_key] = {}
                        
                        try:
                            # 获取该用户画像的提示词（单轮问题，包含题型提示词）
                            prompt = get_prompt(profile, round_question, round_options, normalized_question_type)
                            
                            # 构建对话历史：从conversation_history复制之前所有轮的对话（user和assistant消息）
                            # 第一轮时conversation_history为空，后续轮次会包含之前所有轮的完整对话
                            messages = conversation_history[model_name].copy()
                            logging.debug(f"    轮次 {round_num} 开始前，对话历史包含 {len(messages)} 条消息（{len([m for m in messages if m.get('role') == 'user'])} 条user，{len([m for m in messages if m.get('role') == 'assistant'])} 条assistant）")
                            
                            # 添加当前轮次的问题
                            # 每轮都可以输入图片（如果需要），但通常第一轮输入即可
                            # 检查对话历史中是否已经包含图片
                            has_image_in_history = False
                            if messages:
                                for msg in messages:
                                    if msg.get("role") == "user":
                                        content = msg.get("content", [])
                                        if isinstance(content, list):
                                            for item in content:
                                                if isinstance(item, dict) and item.get("type") == "image_url":
                                                    has_image_in_history = True
                                                    break
                                        if has_image_in_history:
                                            break
                            
                            # 构建当前轮次的user消息
                            from .model_api import get_image_format, encode_image
                            user_content = []
                            
                            # 如果对话历史中没有图片，且当前有图片路径，则添加所有图片（支持多图输入）
                            # 注意：在第一轮对话时，所有图片都会被添加到第一条消息中
                            if not has_image_in_history and image_paths:
                                # 使用统一的压缩设置函数（与call_model_api保持一致）
                                from .model_api import _determine_image_compression_settings
                                
                                # 确定图片压缩设置（使用与call_model_api相同的逻辑）
                                # 多轮对话时强制压缩以节省token
                                should_compress, max_longest_side, quality = _determine_image_compression_settings(
                                    image_paths=image_paths,
                                    is_multi_round=True  # 多轮对话场景
                                )
                                
                                logging.debug(f"  添加 {len(image_paths)} 张图片到当前轮次消息中")
                                for image_path in image_paths:
                                    if image_path.startswith(("http://", "https://")):
                                        user_content.append({
                                            "type": "image_url",
                                            "image_url": {"url": image_path}
                                        })
                                    elif os.path.exists(image_path):
                                        # 使用新算法（黄金配置）时，强制使用 JPEG 格式
                                        if should_compress and max_longest_side == 1280 and quality == 85:
                                            image_format = 'jpeg'
                                        else:
                                            image_format = get_image_format(image_path)
                                        base64_image = encode_image(image_path, compress=should_compress, max_longest_side=max_longest_side, quality=quality)
                                        user_content.append({
                                            "type": "image_url",
                                            "image_url": {"url": f"data:image/{image_format};base64,{base64_image}"}
                                        })
                                    else:
                                        logging.warning(f"  图片文件不存在或URL无效，已跳过: {image_path}")
                            
                            # 添加文本问题
                            user_content.append({"type": "text", "text": prompt})
                            current_user_msg = {"role": "user", "content": user_content}
                            
                            messages.append(current_user_msg)
                            
                            # 调用模型API（使用对话历史）
                            # 传递image_paths以便进行动态分辨率调整
                            model_answer, response_time, raw_response = call_model_api(
                                model_name=model_name,
                                messages=messages,
                                image_paths=image_paths if image_paths else None
                            )
                            
                            # 提取答案（用于添加到对话历史）
                            # 判断该轮次是否有选项
                            has_round_options = round_options is not None and isinstance(round_options, dict) and any(round_options.values())
                            extracted_answer, is_from_box, original_response = extract_answer_from_response(model_answer, has_round_options)
                            
                            # 将本轮问答添加到对话历史中，供下一轮使用
                            # 优化：为了减少token消耗，只保存问题和答案的核心内容，不保存完整的提示词模板
                            
                            # 1. 构建精简的user消息（只包含问题本身和选项，不包含提示词模板）
                            # 检查对话历史中是否已经有图片（第一轮会添加图片，后续轮次不需要）
                            has_image_in_conversation_history = any(
                                msg.get("role") == "user" and isinstance(msg.get("content"), list) and
                                any(item.get("type") == "image_url" for item in msg.get("content", []))
                                for msg in conversation_history[model_name]
                            )
                            
                            simplified_user_content = []
                            # 只在第一轮添加图片（如果对话历史中还没有图片，且当前轮次有图片）
                            # 注意：使用current_user_msg中已经构建好的图片内容，避免重复编码
                            if not has_image_in_conversation_history and image_paths:
                                # 从current_user_msg中提取图片内容（已经编码好了）
                                if isinstance(current_user_msg.get("content"), list):
                                    for item in current_user_msg["content"]:
                                        if isinstance(item, dict) and item.get("type") == "image_url":
                                            simplified_user_content.append(item)
                            
                            # 只保存问题本身，不包含提示词模板
                            question_text = round_question
                            if round_options and isinstance(round_options, dict) and any(round_options.values()):
                                # 如果有选项，格式化选项文本
                                options_list = []
                                for key in sorted(round_options.keys()):
                                    value = round_options.get(key, "")
                                    if value:
                                        options_list.append(f"{key}. {value}")
                                if options_list:
                                    question_text = f"{round_question}\n\n选项：\n" + "\n".join(options_list)
                            
                            simplified_user_content.append({"type": "text", "text": question_text})
                            simplified_user_msg = {"role": "user", "content": simplified_user_content}
                            
                            # 2. 构建精简的assistant消息（只保存简要答案）
                            # 优先使用提取的答案（不包含思考过程），如果没有提取到则只截取最后300字符
                            brief_answer_for_history = extracted_answer if extracted_answer and extracted_answer.strip() else (
                                original_response[-300:] if len(original_response) > 300 else original_response
                            )
                            
                            # 将精简后的消息添加到conversation_history，确保下一轮能看到完整的对话历史
                            conversation_history[model_name].append(simplified_user_msg)
                            conversation_history[model_name].append({"role": "assistant", "content": brief_answer_for_history})
                            logging.debug(f"    轮次 {round_num} 结束后，conversation_history包含 {len(conversation_history[model_name])} 条消息（{len([m for m in conversation_history[model_name] if m.get('role') == 'user'])} 条user，{len([m for m in conversation_history[model_name] if m.get('role') == 'assistant'])} 条assistant）")
                            
                            # 详细日志：记录模型响应
                            # 将对话历史转换为字符串格式（用于日志）
                            # 清理base64图片数据，避免日志过大
                            if messages:
                                sanitized_messages = sanitize_messages_for_log(messages, image_paths)
                                prompt_for_log = json.dumps(sanitized_messages, ensure_ascii=False, indent=2)
                            else:
                                prompt_for_log = prompt
                            # 详细日志：记录模型响应
                            if get_log_mode() == "detailed":
                                if get_detailed_log_file():
                                    log_model_response_detailed(
                                        question_id=item_id,
                                        round_key=round_key,
                                        model_name=model_name,
                                        profile=profile,
                                        prompt=prompt_for_log,
                                        raw_response=raw_response,
                                        image_paths=image_paths
                                    )
                                else:
                                    logging.warning(f"详细日志模式已启用，但DETAILED_LOG_FILE为None，无法写入详细日志")
                            
                            # 如果 box 没提取到东西，使用完整 content 进行裁判模型评测
                            answer_for_judge = original_response if not is_from_box else extracted_answer
                            
                            total_response_time += response_time
                            
                            # 使用裁判模型评判
                            is_correct, reasoning, judge_time, judge_response, judge_prompt = judge_answer(
                                model_answer=answer_for_judge,
                                gt_answer=round_answer,
                                question=round_question,
                                options=round_options
                            )
                            
                            # 详细日志：记录裁判模型响应
                            if get_log_mode() == "detailed":
                                if get_detailed_log_file():
                                    log_judge_response_detailed(
                                    question_id=item_id,
                                    round_key=round_key,
                                    model_name=model_name,
                                    profile=profile,
                                    model_answer=answer_for_judge,  # 使用实际用于评判的答案
                                    gt_answer=round_answer,
                                    is_match=is_correct,
                                    reasoning=reasoning,
                                    judge_time=judge_time,
                                    raw_response=judge_response,
                                    prompt=judge_prompt,
                                    image_paths=image_paths
                                    )
                                else:
                                    logging.warning(f"详细日志模式已启用，但DETAILED_LOG_FILE为None，无法写入详细日志")
                            
                            total_judge_time += judge_time
                            
                            if not is_correct:
                                all_rounds_correct = False
                            
                            logging.info(f"    轮次{round_num} 模型{model_name}: {'✓' if is_correct else '✗'}")
                            
                            # 保存该轮次的结果
                            # 注意：为了兼容 module2 格式，我们保存 model_answer 作为 process，extracted_answer 作为 answer
                            result_data = {
                                "model_name": model_name,
                                "prompt": prompt_for_log,  # 保存完整的对话历史（JSON格式）
                                "conversation_history": messages,  # 保存对话历史（列表格式）
                                "model_answer": model_answer,  # 完整回答（作为 process）
                                "extracted_answer": extracted_answer,  # 提取的答案（作为 answer）
                                "is_from_box": is_from_box,  # 是否从 box 中提取
                                "answer_for_judge": answer_for_judge,  # 实际用于评判的答案
                                "is_correct": is_correct,
                                "reasoning": reasoning,
                                "response_time": response_time,
                                "judge_time": judge_time,
                            }
                            # 保存该轮次的选项（如果有）
                            if round_options is not None:
                                result_data["options"] = round_options
                            # 始终保存 raw_response（multi_answer_filter 等模块需要用它提取思考内容）
                            result_data["raw_response"] = raw_response
                            result_data["judge_response"] = judge_response
                            
                            rounds_data[round_key][model_name] = result_data
                            
                        except Exception as e:
                            logging.error(f"    轮次{round_num} 模型{model_name} 评测失败: {e}")
                            all_rounds_correct = False
                            if round_key not in rounds_data:
                                rounds_data[round_key] = {}
                            rounds_data[round_key][model_name] = {
                                "model_name": model_name,
                                "error": str(e),
                                "is_correct": False,
                                "model_answer": "",  # 确保answer字段为空，不传入错误信息
                                "extracted_answer": "",  # 确保extracted_answer字段为空
                                "answer_for_judge": "",  # 确保answer_for_judge字段为空
                                "response_time": 0.0,
                                "judge_time": 0.0
                            }
                
                # 汇总每个模型的所有轮次结果
                for model_name in enabled_models:
                    model_rounds = []
                    model_all_correct = True
                    for round_key in round_keys:
                        if round_key in rounds_data and model_name in rounds_data[round_key]:
                            round_result = rounds_data[round_key][model_name]
                            # 获取该轮次对应的选项
                            round_options = options.get(round_key) if isinstance(options, dict) else None
                            round_item = {
                                "round": round_key,
                                "question": question.get(round_key, ""),
                                "answer": answer.get(round_key, ""),
                                **round_result
                            }
                            # 确保选项被包含（如果result_data中没有，则显式添加）
                            if round_options is not None and "options" not in round_item:
                                round_item["options"] = round_options
                            model_rounds.append(round_item)
                            logging.debug(f"  汇总轮次 {round_key} 到 model_rounds: round={round_key}, has_model_answer={bool(round_result.get('model_answer'))}, has_extracted_answer={bool(round_result.get('extracted_answer'))}")
                            if not round_result.get("is_correct", False):
                                model_all_correct = False
                        else:
                            logging.warning(f"  警告: 轮次 {round_key} 模型 {model_name} 的数据不存在于 rounds_data 中")
                    
                    logging.info(f"  模型 {model_name} 汇总完成: 共 {len(model_rounds)} 轮，model_rounds结构: {[r.get('round', 'NO_ROUND') for r in model_rounds]}")
                    
                    profile_results["models"][model_name] = {
                        "model_name": model_name,
                        "is_multi_round": True,
                        "rounds": model_rounds,
                        "all_rounds_correct": model_all_correct,
                        "total_response_time": total_response_time,
                        "total_judge_time": total_judge_time,
                        "is_correct": model_all_correct  # 所有轮次都正确才算正确
                    }
                    
                    # 调试：确认 rounds 数据已保存
                    logging.info(f"✅ 多轮题目 {item_id} 模型 {model_name}: profile_results['models'][{model_name}].keys()={list(profile_results['models'][model_name].keys())}, has_rounds={'rounds' in profile_results['models'][model_name]}, rounds长度={len(profile_results['models'][model_name].get('rounds', []))}")
            
            else:
                # 单轮问答：原有逻辑
                logging.info(f"✅ 识别为单轮题目")
                # 获取该用户画像的提示词（包含题型提示词）
                prompt = get_prompt(profile, question, options, normalized_question_type)
                logging.debug(f"提示词: {prompt[:200]}...")
                
                # 对每个启用的模型进行评测（并行）
                def eval_single_model(model_name: str):
                    logging.info(f"  模型: {model_name}")
                    try:
                        model_answer, response_time, raw_response = call_model_api(
                            model_name=model_name,
                            prompt=prompt,
                            image_paths=image_paths if image_paths else None
                        )
                        
                        # 详细日志：记录模型响应
                        if get_log_mode() == "detailed":
                            if get_detailed_log_file():
                                log_model_response_detailed(
                                question_id=item_id,
                                model_name=model_name,
                                profile=profile,
                                prompt=prompt,
                                raw_response=raw_response,
                                image_paths=image_paths
                                )
                            else:
                                logging.warning(f"详细日志模式已启用，但DETAILED_LOG_FILE为None，无法写入详细日志")
                        
                        extracted_answer, is_from_box, original_response = extract_answer_from_response(model_answer, has_options)
                        answer_for_judge = original_response if not is_from_box else extracted_answer
                        
                        logging.info(f"    模型回答: {extracted_answer[:100]}...")
                        if not is_from_box:
                            logging.info(f"    注意: 未从 \\boxed{{}} 中提取到答案，使用完整响应进行评测")
                        logging.info(f"    响应时间: {response_time:.2f}s")
                        
                        is_correct, reasoning, judge_time, judge_response, judge_prompt = judge_answer(
                            model_answer=answer_for_judge,
                            gt_answer=answer,
                            question=question,
                            options=options
                        )
                        
                        # 详细日志：记录裁判模型响应
                        if get_log_mode() == "detailed":
                            if get_detailed_log_file():
                                log_judge_response_detailed(
                                question_id=item_id,
                                model_name=model_name,
                                profile=profile,
                                model_answer=answer_for_judge,
                                gt_answer=answer,
                                is_match=is_correct,
                                reasoning=reasoning,
                                judge_time=judge_time,
                                raw_response=judge_response,
                                prompt=judge_prompt,
                                image_paths=image_paths
                                )
                            else:
                                logging.warning(f"详细日志模式已启用，但DETAILED_LOG_FILE为None，无法写入详细日志")
                        
                        logging.info(f"    评判结果: {'✓' if is_correct else '✗'} ({reasoning[:50]}...)")
                        logging.info(f"    评判时间: {judge_time:.2f}s")
                        
                        result_data = {
                            "model_name": model_name,
                            "prompt": prompt,
                            "model_answer": model_answer,
                            "extracted_answer": extracted_answer,
                            "is_from_box": is_from_box,
                            "answer_for_judge": answer_for_judge,
                            "is_correct": is_correct,
                            "reasoning": reasoning,
                            "response_time": response_time,
                            "judge_time": judge_time,
                        }
                        if get_log_mode() == "detailed":
                            result_data["raw_response"] = raw_response
                            result_data["judge_response"] = judge_response
                        return model_name, result_data
                    except Exception as e:
                        logging.error(f"    模型 {model_name} 评测失败: {e}")
                        return model_name, {
                            "model_name": model_name,
                            "error": str(e),
                            "is_correct": False,
                            "model_answer": "",  # 确保answer字段为空，不传入错误信息
                            "extracted_answer": "",  # 确保extracted_answer字段为空
                            "answer_for_judge": "",  # 确保answer_for_judge字段为空
                            "response_time": 0.0,
                            "judge_time": 0.0
                        }

                with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
                    futures = [executor.submit(eval_single_model, m) for m in enabled_models]
                    for future in as_completed(futures):
                        model_name, model_result = future.result()
                        profile_results["models"][model_name] = model_result
                        # 调试：确认单轮题目数据已保存
                        logging.debug(f"✅ 单轮题目 {item_id} 模型 {model_name}: profile_results['models'][{model_name}].keys()={list(profile_results['models'][model_name].keys())}")
            
            # 调试：在保存到 results 之前，检查数据
            if is_multi_round:
                for model_name in enabled_models:
                    if model_name in profile_results["models"]:
                        model_data_check = profile_results["models"][model_name]
                        logging.info(f"🔍 保存前检查 {item_id} {model_name}: has_rounds={'rounds' in model_data_check}, keys={list(model_data_check.keys())}")
            
            results["profiles"][profile] = profile_results
        
        return results
        
    except Exception as e:
        logging.error(f"数据项 {item_id} 评测失败: {e}")
        return {"question_id": item_id, "error": str(e)}

