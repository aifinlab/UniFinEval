#!/bin/bash
# ==============================================================================
# 评测脚本 - qwen3-vl-235b-a22b-thinking / Evaluation Script - qwen3-vl-235b-a22b-thinking
# ==============================================================================
# 用途：运行金融领域多用户画像评测（qwen3-vl-235b-a22b-thinking）
# Purpose: Run multi-user-profile evaluation in finance domain (model: qwen3-vl-235b-a22b-thinking)
# 说明：所有配置项都在下面，直接修改即可
# Note: All configuration options are below, edit directly as needed
# ==============================================================================
set -eu
# 如果bash版本支持pipefail，则启用它（bash 3.0+）
# Enable pipefail if bash version supports it (bash 3.0+)
if [[ "${BASH_VERSION%%.*}" -ge 3 ]] 2>/dev/null; then
    set -o pipefail
fi

# 加载通用工具函数 / Load common utility functions
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
if [ -f "$PROJECT_ROOT/utils_common.sh" ]; then
    source "$PROJECT_ROOT/utils_common.sh"
else
    # 如果没有工具函数，定义基本函数 / If utility functions not found, define basic functions
    print_error() { echo "❌ 错误：$1"; [ -n "${2:-}" ] && echo "   💡 建议：$2"; }
    print_warning() { echo "⚠️  警告：$1"; [ -n "${2:-}" ] && echo "   💡 建议：$2"; }
    print_success() { echo "✅ $1"; }
    print_info() { echo "ℹ️  $1"; }
    check_file_exists() {
        [ -f "$1" ] || { print_error "找不到文件" "路径: $1"; return 1; }
    }
    check_directory_exists() {
        [ -d "$1" ] || { print_error "目录不存在" "路径: $1"; return 1; }
    }
fi

# ==============================================================================
# 基础路径配置 / Basic Path Configuration
# ==============================================================================
# 输入文件路径（支持 .json, .jsonl 或 .csv）/ Input file path (supports .json, .jsonl or .csv)
# 请根据实际情况修改为您的数据文件路径 / Please modify to your actual data file path
INPUT_FILE="./data/data.xlsx"  # 示例：使用相对路径 / Example: using relative path
# INPUT_FILE="/path/to/your/dataset.json"  # 或使用绝对路径 / Or use absolute path
OUTPUT_FILE="evaluate.jsonl"                            # 只需要填写输出文件名，不要填写路径（支持 .json 或 .jsonl，根据扩展名自动判断格式）
                                                           # Only specify output filename, not path (supports .json or .jsonl, format auto-detected by extension)
                                                           # 文件将保存在：./outputs/{profile}/{model_name}/{OUTPUT_FILE}
                                                           # Files will be saved to: ./outputs/{profile}/{model_name}/{OUTPUT_FILE}
                                                           # 例如：eval_results.json -> ./outputs/expert/qwenvlmax/eval_results.json
                                                           # Example: eval_results.json -> ./outputs/expert/qwenvlmax/eval_results.json
                                                           # 如果为空字符串("")，则使用自动生成的带时间戳的文件名
                                                           # If empty string (""), use auto-generated filename with timestamp
                                                           # ⚠️ 重要：如果启用断点续传（RESUME=true），必须设置 OUTPUT_FILE，否则会报错
                                                           # ⚠️ Important: If resume is enabled (RESUME=true), OUTPUT_FILE must be set, otherwise error will occur
                                                           # 注意：输出目录固定为 ./outputs，按用户画像和模型分类组织
                                                           # Note: Output directory is fixed as ./outputs, organized by profile and model name
LOG_DIR="./evaluate_logs"                                  # 日志目录 / Log directory
LOG_LEVEL="INFO"                                           # 日志级别：DEBUG/INFO/WARNING/ERROR / Log level: DEBUG/INFO/WARNING/ERROR

# ==============================================================================
# 模型配置（固定为当前模型）/ Model Configuration (fixed to current model)
# ==============================================================================
EVAL_MODELS="qwen3-vl-235b-a22b-thinking"  
#InternVL3_5-241B-A28B,qwen3-vl-235b-a22b-thinking,Llama-3.2-11B-Vision等 / InternVL3_5-241B-A28B,qwen3-vl-235b-a22b-thinking,Llama-3.2-11B-Vision, etc.
# ==============================================================================
# 用户画像配置 / User Profile Configuration
# ==============================================================================
# 四种用户画像提示词：/ Four user profile prompts:
#   - beginner（金融小白）：扮演完全不懂金融的用户，用简单易懂的方式思考
#   - beginner (Financial Novice): Act as a user with no financial knowledge, think in simple and understandable ways
#   - retail（散户投资者）：扮演有一定金融基础的散户，用专业但易懂的方式思考
#   - retail (Retail Investor): Act as a retail investor with basic financial knowledge, think professionally but understandably
#   - expert（金融专家）：扮演资深的金融专家，用深度专业的方式思考
#   - expert (Financial Expert): Act as a senior financial expert, think with deep professional knowledge
#   - expert_cot（金融专家CoT）：扮演金融专家并使用思维链推理方法
#   - expert_cot (Financial Expert CoT): Act as a financial expert using chain-of-thought reasoning
# 使用逗号分隔的字符串指定用户画像，空字符串表示使用所有
# Use comma-separated string to specify user profiles, empty string means use all
# 单个画像：PROFILES="expert" / Single profile: PROFILES="expert"
# 多个画像：PROFILES="beginner,retail,expert,expert_cot" / Multiple profiles: PROFILES="beginner,retail,expert,expert_cot"

PROFILES="expert"                                             # 用户画像列表（逗号分隔），空字符串表示使用所有 / User profile list (comma-separated), empty string means use all

# ==============================================================================
# 运行配置 / Runtime Configuration
# ==============================================================================
RESUME=true                                                # 断点续跑： true(从输出文件中读取已处理的问题，跳过已完成的部分) 或 false(全新运行)
                                                           # Resume: true (read processed questions from output file, skip completed parts) or false (fresh run)
                                                           # 如果 OUTPUT_FILE 已指定，将从 ./outputs/{profile}/{model_name}/{OUTPUT_FILE} 中读取
                                                           # If OUTPUT_FILE is specified, will read from ./outputs/{profile}/{model_name}/{OUTPUT_FILE}
                                                           # 如果 OUTPUT_FILE 为空，将从输出目录中查找匹配的文件
                                                           # If OUTPUT_FILE is empty, will search for matching files in output directory
                                                           # 如果不续传且文件已存在，会自动生成 _v2、_v3 等版本号
                                                           # If not resuming and file exists, will auto-generate _v2, _v3, etc. version numbers
LIMIT=""                                                   # 限制处理数量：设置为数字（如"10"）只处理前N条数据，设置为空字符串("")处理全部数据
                                                           # Limit processing count: set to number (e.g. "10") to process first N items, set to empty string ("") to process all
USE_RANDOM=false                                            # 随机选择：true(随机选择/打乱顺序) 或 false(按顺序处理)
                                                           # Random selection: true (randomly select/shuffle) or false (process in order)
SEED="42"                                                   # 随机种子（仅当USE_RANDOM=true时有效）/ Random seed (only effective when USE_RANDOM=true)

# ==============================================================================
# 性能与并发配置 / Performance and Concurrency Configuration
# ==============================================================================
WORKERS=10                                               # 总并发线程数 / Total concurrent worker threads
BATCH=5                                                    # 批量处理大小，对应 EVAL_BATCH_SIZE / Batch processing size, corresponds to EVAL_BATCH_SIZE

# ==============================================================================
# 日志配置 / Logging Configuration
# ==============================================================================
LOG_MODE="detailed"                                           # 日志模式：simple(简化) 或 detailed(详细) / Log mode: simple (simplified) or detailed (comprehensive)

# ==============================================================================
# 超时与重试配置（具体的在config.py中定义）/ Timeout and Retry Configuration (detailed definitions in config.py)
# ==============================================================================
TIMEOUT=1200                                                 # 单次API请求超时时间（秒），默认600秒 / Single API request timeout (seconds), default 600s
MAX_RETRIES=1                                               # 请求失败时的最大重试次数，默认3次 / Maximum retry attempts on failure, default 3
RETRY_SLEEP=1.0                                             # 请求失败后的基础重试间隔（秒），后续按指数退避，默认1秒
                                                           # Base retry delay after failure (seconds), exponential backoff afterwards, default 1s

# ==============================================================================
# 图片缺失处理配置 / Missing Image Handling Configuration
# ==============================================================================
SKIP_MISSING_IMAGES=false                                    # 图片缺失时的处理方式：false(跳过题目，默认) 或 true(继续评测但不包含图片)
                                                             # Missing image handling: false (skip question, default) or true (continue evaluation without images)
                                                             # 设置为 true 时，缺失图片的题目会继续评测，但不会包含图片（适用于图片非必需的情况）
                                                             # When set to true, questions with missing images will continue evaluation but without images (suitable when images are not required)

# ==============================================================================
# 统计计分配置 / Scoring Configuration
# ==============================================================================
# 多轮题目计分方式：/ Multi-round question scoring method:
#   false（默认）：多轮题目整题算1题，所有轮次都正确才算正确
#   false (default): Multi-round question counts as 1 question, all rounds must be correct
#   true：多轮题目按轮次计分，每轮算1题（例如3轮题目=3题，每轮独立计分）
#   true: Multi-round question scored by rounds, each round counts as 1 question (e.g. 3 rounds = 3 questions, each scored independently)
# 注意：此配置只影响统计计算，不影响输出JSON格式（多轮题目仍保持多轮格式）
# Note: This configuration only affects statistics calculation, not output JSON format (multi-round questions still maintain multi-round format)
MULTI_ROUND_COUNT_BY_ROUNDS=true                         # 多轮题目是否按轮次计分，false为多轮整题算1题，true为按轮次计分
                                                           # Whether to score multi-round questions by rounds, false = whole question counts as 1, true = score by rounds



# ==============================================================================
# 预检查 / Pre-checks
# ==============================================================================
if ! check_file_exists "$INPUT_FILE" "输入文件"; then
    exit 1
fi

# 创建必要的目录 / Create necessary directories
# 输出目录固定为 ./outputs，按用户画像和模型分类组织
# Output directory is fixed as ./outputs, organized by profile and model name
mkdir -p "./outputs"
mkdir -p "$LOG_DIR"

# ==============================================================================
# 构建环境变量（传递给Python脚本）/ Build environment variables (passed to Python script)
# ==============================================================================
# 设置要评测的模型列表（已经是逗号分隔的字符串）/ Set model list to evaluate (already comma-separated string)
export EVAL_MODELS="$EVAL_MODELS"

# 设置其他配置 / Set other configurations
export EVAL_TIMEOUT="$TIMEOUT"
export EVAL_MAX_RETRIES="$MAX_RETRIES"
export EVAL_RETRY_SLEEP="$RETRY_SLEEP"
export EVAL_JUDGE_MAX_RETRIES="$MAX_RETRIES"              # 裁判模型重试次数（使用相同值）/ Judge model retry count (use same value)
export EVAL_JUDGE_RETRY_DELAY="$RETRY_SLEEP"              # 裁判模型重试延迟（使用相同值）/ Judge model retry delay (use same value)
export EVAL_LIMIT="$LIMIT"
export EVAL_USE_RANDOM="$USE_RANDOM"
export EVAL_SEED="$SEED"
export EVAL_LOG_MODE="$LOG_MODE"
export EVAL_WORKERS="$WORKERS"
export EVAL_BATCH_SIZE="$BATCH"                            # 传递批量写入大小，作用于 JSON buffer 刷新 / Pass batch write size, affects JSON buffer flushing
export EVAL_MULTI_ROUND_COUNT_BY_ROUNDS="$MULTI_ROUND_COUNT_BY_ROUNDS"  # 多轮题目是否按轮次计分 / Whether to score multi-round questions by rounds
export EVAL_SKIP_MISSING_IMAGES="$SKIP_MISSING_IMAGES"      # 图片缺失时是否继续评测（不包含图片）/ Whether to continue evaluation when images are missing (without images)

# ==============================================================================
# 构建命令参数 / Build command arguments
# ==============================================================================
CMD_ARGS=(
    "--input_file" "$INPUT_FILE"
    "--log_dir" "$LOG_DIR"
    "--log_level" "$LOG_LEVEL"
)

# 添加输出文件参数（如果指定了）/ Add output file argument (if specified)
if [ -n "$OUTPUT_FILE" ]; then
    CMD_ARGS+=("--output_file" "$OUTPUT_FILE")
fi

# 添加断点续跑参数 / Add resume argument
if [ "$RESUME" = "true" ]; then
    CMD_ARGS+=("--resume")
fi

# 添加用户画像参数 / Add user profile arguments
if [ -n "$PROFILES" ]; then
    CMD_ARGS+=("--profiles")
    # 将逗号分隔的字符串拆分为数组 / Split comma-separated string into array
    IFS=',' read -ra PROFILE_ARRAY <<< "$PROFILES"
    for profile in "${PROFILE_ARRAY[@]}"; do
        # 去除前后空格 / Trim leading and trailing spaces
        profile=$(echo "$profile" | xargs)
        if [ -n "$profile" ]; then
            CMD_ARGS+=("$profile")
        fi
    done
fi

# ==============================================================================
# 打印配置信息 / Print configuration information
# ==============================================================================
echo "=============================================================================="
echo "评测配置 - qwen3-vl-235b-a22b-thinking"
echo "=============================================================================="
echo "输入文件: $INPUT_FILE"
if [ -n "$OUTPUT_FILE" ]; then
    echo "输出文件: $OUTPUT_FILE (保存在 ./outputs/{profile}/{model_name}/ 目录下)"
else
    echo "输出文件: 自动生成（保存在 ./outputs/ 目录下，带时间戳）"
fi
echo "日志目录: $LOG_DIR"
echo "日志级别: $LOG_LEVEL"
echo ""
echo "模型配置:"
echo "  要评测的模型: $EVAL_MODELS"
echo ""
echo "用户画像: ${PROFILES:-全部 (beginner, retail, expert, expert_cot)}"
if [ "$RESUME" = "true" ]; then
    echo "断点续跑: ✅ 已启用（将从输出文件中读取已处理的问题）"
else
    echo "断点续跑: ❌ 全新运行"
fi
if [ -n "$LIMIT" ]; then
    echo "限制数量: $LIMIT"
    echo "随机选择: $USE_RANDOM"
    if [ "$USE_RANDOM" = "true" ]; then
        echo "随机种子: $SEED"
    fi
fi
echo ""
echo "超时与重试配置:"
echo "  超时时间: ${TIMEOUT}s"
echo "  最大重试: $MAX_RETRIES 次"
echo "  重试延迟: ${RETRY_SLEEP}s"
echo ""
echo "其他配置:"
echo "  日志模式: $LOG_MODE"
echo "  多轮题目计分: $MULTI_ROUND_COUNT_BY_ROUNDS ($([ "$MULTI_ROUND_COUNT_BY_ROUNDS" = "true" ] && echo "按轮次计分" || echo "整题计分"))"
echo "  图片缺失处理: $SKIP_MISSING_IMAGES ($([ "$SKIP_MISSING_IMAGES" = "true" ] && echo "继续评测（不包含图片）" || echo "跳过题目"))"
if [ -n "$OUTPUT_FILE" ]; then
    echo "  输出格式: 由输出文件后缀决定 (${OUTPUT_FILE##*.})"
else
    echo "  输出格式: 默认 json（未指定输出文件名时自动生成）"
fi
echo "=============================================================================="
echo ""

# ==============================================================================
# 运行评测 / Run evaluation
# ==============================================================================
echo "开始评测..."
python -m evaluate_py.main "${CMD_ARGS[@]}"

echo ""
echo "=============================================================================="
echo "评测完成！"
echo "=============================================================================="
