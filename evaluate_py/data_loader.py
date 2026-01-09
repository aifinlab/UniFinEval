"""
数据加载模块
支持从 JSON、JSONL、CSV 或 Excel 文件加载数据，兼容 module1 的输出格式
支持可扩展字段，便于后续扩展
"""
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Union

from .data_converter import convert_to_standard_format, convert_batch, validate_standard_format


def load_json(file_path: Union[str, Path]) -> List[Dict[str, Any]]:
    """
    加载 JSON 文件
    
    Args:
        file_path: JSON 文件路径
        
    Returns:
        数据列表（如果是数组）或包含 items 字段的字典中的 items 列表
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 兼容两种格式：
    # 1. 直接是数组: [{...}, {...}]
    # 2. 包含 items 字段: {"items": [{...}, {...}], "metadata": {...}}
    if isinstance(data, list):
        return data
    elif isinstance(data, dict) and "items" in data:
        return data["items"]
    elif isinstance(data, dict):
        # 如果整个文件就是一个对象，转换为列表
        return [data]
    else:
        raise ValueError(f"不支持的JSON格式: {type(data)}")


def load_jsonl(file_path: Union[str, Path]) -> List[Dict[str, Any]]:
    """
    加载 JSONL 文件（每行一个 JSON 对象）
    
    Args:
        file_path: JSONL 文件路径
        
    Returns:
        数据列表
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")
    
    items = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
                items.append(item)
            except json.JSONDecodeError as e:
                logging.warning(f"第 {line_num} 行 JSON 解析失败: {e}")
                continue
    
    return items


def _process_csv_row(row: Dict[str, Any], row_num: int) -> Optional[Dict[str, Any]]:
    """
    处理 CSV/Excel 行数据（通用处理逻辑）
    
    Args:
        row: 原始行数据（字典）
        row_num: 行号（用于错误提示）
        
    Returns:
        处理后的行数据，如果处理失败返回 None
    """
    try:
        # 处理image_path字段（CSV格式使用分号分隔）
        if 'image_path' in row and row['image_path']:
            image_path_str = str(row['image_path']).strip()
            if image_path_str and ';' in image_path_str:
                row['image_path'] = [path.strip() for path in image_path_str.split(';') if path.strip()]
            elif image_path_str:
                row['image_path'] = image_path_str
            else:
                row['image_path'] = ""
        
        # 处理image_urls字段（可能是分号分隔的字符串）
        if 'image_urls' in row and row['image_urls']:
            image_urls_str = str(row['image_urls']).strip()
            if image_urls_str and ';' in image_urls_str:
                row['image_urls'] = [url.strip() for url in image_urls_str.split(';') if url.strip()]
            elif image_urls_str:
                row['image_urls'] = [image_urls_str]
            else:
                row['image_urls'] = []
        
        # 处理round字段（转换为整数）
        if 'round' in row and row['round']:
            try:
                row['round'] = int(row['round'])
            except (ValueError, TypeError):
                row['round'] = None
        
        # 处理空值（"null", "None", "none"等，以及 pandas 的 NaN）
        for key, value in row.items():
            if value is None:
                continue
            if isinstance(value, str):
                value_lower = value.lower().strip()
                if value_lower in ['null', 'none', 'nan', '']:
                    row[key] = None
            # 处理 pandas 的 NaN（float('nan')）
            elif isinstance(value, float):
                import math
                if math.isnan(value):
                    row[key] = None
        
        # 处理选择题选项列（CSV/Excel格式：option_A, option_B等）
        # 如果已经有options字段且是有效的字典或JSON字符串，优先使用它
        # 否则从选项列构建options字典
        has_valid_options = False
        if 'options' in row and row.get('options'):
            options_value = row.get('options')
            # 检查是否是有效的字典或JSON字符串
            if isinstance(options_value, dict) and options_value:
                has_valid_options = True
            elif isinstance(options_value, str) and options_value.strip():
                # 尝试解析JSON字符串
                try:
                    import json
                    parsed = json.loads(options_value.strip())
                    if isinstance(parsed, dict) and parsed:
                        has_valid_options = True
                except:
                    pass
        
        if not has_valid_options:
            # 收集所有以option_开头的列
            option_columns = {}
            option_keys_to_remove = []  # 记录需要从row中删除的列
            
            for key, value in row.items():
                if key.startswith('option_'):
                    # 提取选项键（去掉option_前缀）
                    option_key = key[7:]  # len('option_') = 7
                    if option_key:  # 确保提取到有效的键
                        # 只保留非空值
                        if value is not None:
                            if isinstance(value, str):
                                value_stripped = value.strip()
                                if value_stripped and value_stripped.lower() not in ['null', 'none', 'nan']:
                                    option_columns[option_key] = value_stripped
                            elif isinstance(value, (int, float)):
                                import math
                                if not (isinstance(value, float) and math.isnan(value)):
                                    option_columns[option_key] = str(value)
                        option_keys_to_remove.append(key)
            
            # 如果找到了选项列，构建options字典
            if option_columns:
                row['options'] = option_columns
                # 从row中删除已处理的选项列，避免重复
                for key in option_keys_to_remove:
                    row.pop(key, None)
            elif 'options' not in row:
                # 如果没有找到选项列，且没有options字段，设置为None
                row['options'] = None
        
        return row
    except Exception as e:
        logging.warning(f"第 {row_num} 行数据解析失败: {e}")
        return None


def load_csv(file_path: Union[str, Path]) -> List[Dict[str, Any]]:
    """
    加载 CSV 文件
    
    Args:
        file_path: CSV 文件路径
        
    Returns:
        数据列表
    """
    import csv
    
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")
    
    items = []
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row_num, row in enumerate(reader, 2):  # 从第2行开始（第1行是表头）
            processed_row = _process_csv_row(row, row_num)
            if processed_row:
                items.append(processed_row)
    
    return items


def load_excel(file_path: Union[str, Path], sheet_name: Optional[Union[str, int]] = 0) -> List[Dict[str, Any]]:
    """
    加载 Excel 文件（.xlsx 或 .xls）
    支持与 CSV 相同的字段格式
    
    Args:
        file_path: Excel 文件路径
        sheet_name: 工作表名称或索引（默认第一个工作表）
        
    Returns:
        数据列表
    """
    try:
        import pandas as pd
    except ImportError:
        raise ImportError(
            "加载 Excel 文件需要 pandas 和 openpyxl 库。"
            "请安装: pip install pandas openpyxl"
        )
    
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")
    
    try:
        # 读取 Excel 文件
        df = pd.read_excel(file_path, sheet_name=sheet_name, engine='openpyxl')
    except ImportError:
        raise ImportError(
            "读取 Excel 文件需要 openpyxl 库。"
            "请安装: pip install openpyxl"
        )
    except Exception as e:
        raise ValueError(f"读取 Excel 文件失败: {e}")
    
    # 将 DataFrame 转换为字典列表
    # 使用 orient='records' 将每行转换为字典
    items = []
    for row_num, (_, row) in enumerate(df.iterrows(), start=2):  # 从第2行开始（第1行是表头）
        # 将 pandas Series 转换为字典
        row_dict = row.to_dict()
        # 处理行数据
        processed_row = _process_csv_row(row_dict, row_num)
        if processed_row:
            items.append(processed_row)
    
    return items


def load_data(file_path: Union[str, Path]) -> List[Dict[str, Any]]:
    """
    自动识别文件格式并加载数据
    
    Args:
        file_path: 文件路径（支持 .json, .jsonl, .csv, .xlsx, .xls）
        
    Returns:
        数据列表
    """
    file_path = Path(file_path)
    suffix = file_path.suffix.lower()
    
    if suffix == '.json':
        return load_json(file_path)
    elif suffix == '.jsonl':
        return load_jsonl(file_path)
    elif suffix == '.csv':
        return load_csv(file_path)
    elif suffix in ['.xlsx', '.xls']:
        return load_excel(file_path)
    else:
        # 尝试根据内容自动判断
        try:
            return load_json(file_path)
        except:
            try:
                return load_jsonl(file_path)
            except:
                try:
                    return load_csv(file_path)
                except:
                    try:
                        return load_excel(file_path)
                    except:
                        raise ValueError(f"无法识别文件格式: {file_path}，支持格式: .json, .jsonl, .csv, .xlsx, .xls")


def validate_data_item(item: Dict[str, Any]) -> bool:
    """
    验证数据项是否符合基本要求
    
    Args:
        item: 数据项字典
        
    Returns:
        是否有效
    """
    # 支持两种格式：
    # 1. 旧格式：id, question, answer
    # 2. 新格式：image_id/question_id, question (可能是字典), answer (可能是字典)
    
    # 提取ID字段（兼容新旧格式），用于错误日志
    item_id = item.get("id") or item.get("question_id") or item.get("image_id") or "unknown"
    
    # 检查ID字段（兼容新旧格式）
    has_id = "id" in item or "question_id" in item or "image_id" in item
    if not has_id:
        logging.warning(f"数据项缺少ID字段: {item_id}")
        return False
    
    # 检查问题字段（可能是字符串或字典）
    has_question = "question" in item
    if not has_question:
        logging.warning(f"数据项缺少question字段: {item_id}")
        return False
    
    # 检查答案字段（可能是字符串或字典）
    has_answer = "answer" in item
    if not has_answer:
        logging.warning(f"数据项缺少answer字段: {item_id}")
        return False
    
    return True


def normalize_data_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    标准化数据项，确保字段一致性
    支持新旧两种格式：
    1. 旧格式：id, type, question (字符串), answer (字符串)
    2. 新格式：image_id/question_id, image_type/question_type, question (字典), answer (字典)
    
    Args:
        item: 原始数据项
        
    Returns:
        标准化后的数据项
    """
    # 兼容新旧格式的ID字段
    item_id = item.get("id") or item.get("question_id") or item.get("image_id") or ""
    
    # 兼容新旧格式的type字段
    item_type = item.get("type") or item.get("image_type") or item.get("question_type") or ""
    
    # 处理image_path：支持逗号分隔的多张图片（JSON/JSONL格式）
    image_path_raw = item.get("image_path", "")
    if isinstance(image_path_raw, str) and image_path_raw and ',' in image_path_raw:
        # 逗号分隔的字符串，转换为列表
        image_path = [path.strip() for path in image_path_raw.split(',') if path.strip()]
    elif isinstance(image_path_raw, list):
        # 已经是列表，直接使用
        image_path = image_path_raw
    else:
        # 单个路径或空字符串
        image_path = image_path_raw if image_path_raw else ""
    
    normalized = {
        "id": item_id,
        "image_id": item.get("image_id", ""),
        "question_id": item.get("question_id", ""),
        "image_path": image_path,  # 可能是字符串或列表
        "type": item_type,
        "image_type": item.get("image_type", ""),
        "question_type": item.get("question_type", ""),
        "question": item.get("question", ""),  # 可能是字符串或字典
        "options": item.get("options", None),  # 可能是 null 或 dict
        "answer": item.get("answer", ""),  # 可能是字符串或字典
        "process": item.get("process", ""),
        "qa_make_process": item.get("qa_make_process", ""),  # 新格式的process字段
        "gen_type": item.get("gen_type", ""),
    }
    
    # 保留所有其他字段（可扩展性）
    for key, value in item.items():
        if key not in normalized:
            normalized[key] = value
    
    # 处理 options：如果是 null，转换为 None；如果是字符串，尝试解析
    if normalized["options"] is None:
        pass  # 保持 None
    elif isinstance(normalized["options"], str):
        try:
            normalized["options"] = json.loads(normalized["options"])
        except:
            normalized["options"] = None
    elif not isinstance(normalized["options"], dict):
        normalized["options"] = None
    
    # 判断是否为多轮问答格式
    is_multi_round = (
        isinstance(normalized["question"], dict) and 
        isinstance(normalized["answer"], dict) and
        any(key.startswith("round") for key in normalized["question"].keys())
    )
    normalized["is_multi_round"] = is_multi_round
    
    return normalized


def load_and_validate(file_path: Union[str, Path], convert_to_standard: bool = True) -> List[Dict[str, Any]]:
    """
    加载数据并验证，可选择转换为标准格式
    
    Args:
        file_path: 文件路径
        convert_to_standard: 是否转换为标准格式（默认 True）
        
    Returns:
        验证通过的数据列表（标准格式）
    """
    items = load_data(file_path)
    
    if convert_to_standard:
        # 转换为标准格式
        converted_items = convert_batch(items)
        # 验证标准格式
        validated_items = []
        for item in converted_items:
            if validate_standard_format(item):
                validated_items.append(item)
            else:
                logging.warning(f"跳过无效数据项: {item.get('question_id', 'unknown')}")
    else:
        # 使用旧逻辑（向后兼容）
        validated_items = []
        for item in items:
            if validate_data_item(item):
                normalized = normalize_data_item(item)
                validated_items.append(normalized)
            else:
                logging.warning(f"跳过无效数据项: {item.get('id', 'unknown')}")
    
    logging.info(f"成功加载 {len(validated_items)}/{len(items)} 条数据")
    return validated_items
