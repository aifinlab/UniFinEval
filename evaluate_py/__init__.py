"""
评测框架核心模块
包含所有评测相关的核心功能
"""

from .main import main
from .data_loader import load_and_validate
from .prompts import get_prompt, get_all_profiles
from .model_api import call_model_api, extract_answer_from_response
from .judge import judge_answer
from .config import MODEL_DEFINITIONS, get_eval_models, USER_PROFILES, EVAL_CONFIG

# 导出新拆分的模块
from .logger import setup_logging, get_detailed_log_file, close_detailed_log_file
from .evaluator import evaluate_single_item
from .statistics import calculate_statistics, calculate_output_statistics
from .result_utils import is_answer_empty, build_process_value
from .result_converter import convert_to_module2_format, flush_json_buffer

__all__ = [
    'main',
    'load_and_validate',
    'get_prompt',
    'get_all_profiles',
    'call_model_api',
    'extract_answer_from_response',
    'judge_answer',
    'MODEL_DEFINITIONS',
    'get_eval_models',
    'USER_PROFILES',
    'EVAL_CONFIG',
    # 新拆分的模块
    'setup_logging',
    'get_detailed_log_file',
    'close_detailed_log_file',
    'evaluate_single_item',
    'calculate_statistics',
    'calculate_output_statistics',
    'is_answer_empty',
    'build_process_value',
    'convert_to_module2_format',
    'flush_json_buffer',
]

