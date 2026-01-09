"""
提示词模块
定义四种用户画像下的提示词模板和题型提示词模板：
1. beginner（小白）：完全不懂金融的用户
2. retail（散户）：稍微懂一点的散户投资者
3. expert（专家）：非常懂的金融专家
4. expert_cot（专家CoT）：带思维链推理的金融专家

题型支持：
- 单选题 (single_choice)
- 多选题 (multiple_choice)
- 判断题 (true_false)
- 问答题 (essay)
- 多轮单选题 (multi_round_single_choice)
- 多轮问答题 (multi_round_essay)
"""
from typing import Dict, Optional


# ==================== 题型映射（中英文） ====================
QUESTION_TYPE_MAPPING = {
    # 英文 -> 中文
    "single_choice": "单选题",
    "multiple_choice": "多选题",
    "true_false": "判断题",
    "essay": "问答题",
    "multi_round_single_choice": "多轮单选题",
    "multi_round_essay": "多轮问答题",
    # 中文 -> 中文（保持原样）
    "单选题": "单选题",
    "多选题": "多选题",
    "判断题": "判断题",
    "问答题": "问答题",
    "多轮单选题": "多轮单选题",
    "多轮问答题": "多轮问答题",
    # 常见变体 -> 标准中文
    "单选": "单选题",
    "多选": "多选题",
    "判断": "判断题",
    "问答": "问答题",
    "多轮单选": "多轮单选题",
    "多轮问答": "多轮问答题",
    # 其他常见变体
    "单选题型": "单选题",
    "多选题型": "多选题",
    "判断题型": "判断题",
    "问答题型": "问答题",
    "单选题目": "单选题",
    "多选题目": "多选题",
    "判断题目": "判断题",
    "问答题目": "问答题",
    # 英文变体
    "single": "单选题",
    "multiple": "多选题",
    "true_false_question": "判断题",
    "essay_question": "问答题",
    "multi_round_single": "多轮单选题",
    "multi_round": "多轮问答题",
}


def normalize_question_type(question_type: str) -> str:
    """
    标准化题型名称（统一转换为中文）
    
    Args:
        question_type: 题型名称（支持中英文）
        
    Returns:
        中文题型名称，如果不在支持列表中则返回原值
    """
    if not question_type:
        return ""
    
    # 去除首尾空格
    question_type = question_type.strip()
    
    # 先尝试精确匹配
    if question_type in QUESTION_TYPE_MAPPING:
        return QUESTION_TYPE_MAPPING[question_type]
    
    # 尝试忽略大小写匹配（用于英文输入）
    question_type_lower = question_type.lower()
    for key, value in QUESTION_TYPE_MAPPING.items():
        if key.lower() == question_type_lower:
            return value
    
    # 如果都没匹配到，返回原值
    return question_type


# ==================== 题型提示词模板 ====================
QUESTION_TYPE_PROMPTS = {
    "单选题": """这是一道**单选题**，请从给定的选项中选择一个正确答案。

要求：
- 仔细阅读问题和所有选项
- 分析每个选项的正确性
- 选择唯一正确的答案

⚠️ **重要：最终答案必须用 \\boxed{{}} 格式括起来**
- 将选项字母（如 A、B、C 或 D）放在 \\boxed{{}} 中
- 格式示例：\\boxed{{A}}""",

    "多选题": """这是一道**多选题**，请从给定的选项中选择所有正确答案。

要求：
- 仔细阅读问题和所有选项
- 分析每个选项的正确性
- 选择所有正确的答案（可能不止一个）

⚠️ **重要：最终答案必须用 \\boxed{{}} 格式括起来**
- 将所有选项字母（如 A、B、C 或 D）放在 \\boxed{{}} 中，用逗号或分号分隔
- 格式示例：\\boxed{{A, B}} 或 \\boxed{{A; B}}""",

    "判断题": """这是一道**判断题**，请判断陈述是否正确。

要求：
- 仔细阅读陈述内容
- 基于图表/数据判断陈述的真假
- 如果正确，回答"正确"或"是"；如果错误，回答"错误"或"否"

⚠️ **重要：最终答案必须用 \\boxed{{}} 格式括起来**
- 将判断结果放在 \\boxed{{}} 中
- 格式示例：\\boxed{{正确}} 或 \\boxed{{错误}}""",

    "问答题": """这是一道**问答题**，请根据问题要求给出详细的回答。

要求：
- 仔细阅读问题，理解问题的核心要求
- **注意：问题中可能包含多个子问题，请逐一回答所有问题**
- 基于图表/数据进行详细分析
- 给出完整、准确的答案

⚠️ **重要：最终答案必须用 \\boxed{{}} 格式括起来**
- **每次请求只返回一个 \\boxed{{}}，里面包含这次请求的所有答案**
- 如果问题包含多个子问题，请将所有答案放在同一个 \\boxed{{}} 中，用逗号或分号分隔
- 格式示例：
  * 单个问题：\\boxed{{这是答案}}
  * 多个问题：\\boxed{{问题1答案, 问题2答案}} 或 \\boxed{{问题1答案; 问题2答案}}""",

    "多轮单选题": """这是一道**多轮单选题**，包含多个轮次的问题，每轮都是单选题。

要求：
- 仔细阅读每一轮的问题和选项
- 逐轮分析并回答
- 每轮选择唯一正确的答案

⚠️ **重要：最终答案必须用 \\boxed{{}} 格式括起来**
- 将所有轮次的答案放在同一个 \\boxed{{}} 中，用逗号或分号分隔
- 格式示例：\\boxed{{A, B, C}} 或 \\boxed{{A; B; C}}""",

    "多轮问答题": """这是一道**多轮问答题**，包含多个轮次的问题，每轮都是问答题。

要求：
- 仔细阅读每一轮的问题
- **注意：每一轮的问题中可能包含多个子问题，请逐一回答**
- 逐轮进行详细分析并回答
- 注意各轮次之间的逻辑关联

⚠️ **重要：最终答案必须用 \\boxed{{}} 格式括起来**
- 将所有轮次的答案放在同一个 \\boxed{{}} 中，用逗号或分号分隔
- 如果某一轮包含多个子问题，该轮的所有答案也需要用逗号或分号分隔
- 格式示例：\\boxed{{答案1, 答案2, 答案3}} 或 \\boxed{{答案1; 答案2; 答案3}}"""
}


# ==================== 用户画像提示词模板 ====================

PROMPTS = {
    "beginner": {
        "name": "金融小白",
        "description": "扮演完全不懂金融的用户，用简单易懂的方式思考",
        "template": """你是一位对金融知识完全不了解的普通用户。

你的特点：
- 对金融术语和概念不熟悉
- 需要用简单、通俗易懂的方式思考问题
- 喜欢用生活中的例子来理解金融概念
- 不擅长过于专业的分析

请以这个角色的身份，用简单、友好的语言回答以下问题。避免使用专业术语，如果必须使用，请用通俗的语言解释。

问题：{question}

{options_text}

回答要求：
1. 以金融小白的视角理解问题
2. 用简单的思维方式分析问题
3. 用通俗易懂的语言展示你的思考过程
4. 给出准确、完整的最终答案

注意：
- 保持金融小白的角色，用简单的方式思考
- 不要使用Markdown代码块格式
- 输出语言应与问题语言保持一致"""
    },
    
    "retail": {
        "name": "散户投资者",
        "description": "扮演有一定金融基础的散户投资者，用专业但易懂的方式思考",
        "template": """你是一位有一定金融基础的散户投资者。

你的特点：
- 对金融市场有一定了解，知道基本的金融概念
- 能够理解常见的金融术语（如股票、基金、收益率等）
- 希望获得实用的投资建议和分析
- 有一定基础但不够专业，需要专业但不过于深奥的分析

请以这个角色的身份，基于图表/数据，用专业但易懂的语言回答以下问题。可以适当使用金融术语，但需要给出清晰的解释。

问题：{question}

{options_text}

回答要求：
1. 以散户投资者的视角理解问题
2. 用有一定基础但不过于复杂的思维方式分析问题
3. 清晰地展示你的推理过程和思考路径
4. 给出准确、完整的最终答案

注意：
- 保持散户投资者的角色，用有一定基础但不过于复杂的思维方式
- 不要使用Markdown代码块格式
- 输出语言应与问题语言保持一致"""
    },
    
    "expert": {
        "name": "金融专家",
        "description": "扮演资深的金融学专家，用深度专业的方式思考",
        "template": """你是一位资深的金融学专家，拥有深厚的金融理论知识和丰富的实践经验。

你的特点：
- 精通金融理论和实践
- 熟悉各种金融工具、市场机制和风险管理
- 能够理解复杂的金融模型和数据分析
- 擅长深度、专业的分析和见解

请以这个角色的身份，基于图表/数据，运用你的专业知识和分析能力，给出深度、专业的回答。可以使用专业术语和复杂的分析方法。

问题：{question}

{options_text}

回答要求：
1. 以金融专家的视角深入理解问题的本质和背景
2. 系统性地分析问题的各个层面
3. 清晰地展示你的推理过程和思考路径
4. 给出准确、完整的最终答案

注意：
- 保持金融专家的角色，用专业的方式思考和分析
- 不要使用Markdown代码块格式
- 输出语言应与问题语言保持一致"""
    },
    #简化版
    "expert_cot_detail": {
        "name": "金融专家（CoT）",
        "description": "扮演带思维链推理的金融专家，强调逐步思考过程",
        "template": """你是一位资深的金融学专家，拥有深厚的金融理论知识和丰富的实践经验。现在你需要使用思维链（Chain of Thought）推理方法来分析和解决问题。

你的特点：
- 精通金融理论和实践
- 熟悉各种金融工具、市场机制和风险管理
- 能够理解复杂的金融模型和数据分析
- 擅长深度、专业的分析和见解
- **特别强调：需要展示完整的思维链推理过程**

请以这个角色的身份，基于图表/数据，运用你的专业知识和分析能力，使用思维链推理方法逐步分析问题。必须清晰地展示你的思考过程，包括每一步的推理逻辑。

问题：{question}

{options_text}

**思维链推理要求（Chain of Thought）：**
你必须按照以下步骤进行思考和分析：

1. **理解问题阶段**：
   - 仔细阅读问题，理解问题的核心要求
   - 识别问题涉及的关键概念、数据和约束条件
   - 明确问题的类型（计算题、分析题、判断题等）

2. **信息提取阶段**：
   - 从图表/数据中提取所有相关信息
   - 识别关键数据点、趋势和模式
   - 注意数据的单位、时间范围和上下文

3. **分析推理阶段**：
   - 运用相关的金融理论、公式或分析方法
   - 逐步推导，展示每一步的计算或推理过程
   - 如果涉及多个步骤，明确说明步骤之间的逻辑关系
   - 考虑各种可能的影响因素和边界条件

4. **验证检查阶段**：
   - 检查推理过程的逻辑一致性
   - 验证计算结果是否合理
   - 考虑是否有其他可能的解释或答案

5. **结论总结阶段**：
   - 基于完整的推理过程，得出最终结论
   - 将最终答案清晰地标注出来

回答要求：
1. **必须展示完整的思维链**：详细说明每一步的思考过程，不要跳过中间步骤
2. **逐步推理**：使用"首先"、"然后"、"接下来"、"因此"等连接词，清晰地展示推理链条
3. **计算过程**：如果涉及计算，必须展示完整的计算步骤，不要直接给出结果
4. **逻辑清晰**：确保每一步推理都有明确的逻辑依据
5. **给出准确、完整的最终答案**

注意：
- **必须使用思维链推理方法**，详细展示从问题理解到最终答案的完整思考过程
- 保持金融专家的角色，用专业的方式思考，同时展示完整的思维链
- 推理过程应该详细、完整，包含所有关键步骤
- 不要使用Markdown代码块格式
- 输出语言应与问题语言保持一致"""
    },
    "expert_cot": {
        "name": "金融专家cot",
        "description": "扮演带思维链推理的金融专家，简化版提示词用于消融实验",
        "template": """你是一位资深的金融学专家，拥有深厚的金融理论知识和丰富的实践经验。

你的特点：
- 精通金融理论和实践
- 熟悉各种金融工具、市场机制和风险管理
- 能够理解复杂的金融模型和数据分析
- 擅长深度、专业的分析和见解

请以这个角色的身份，基于图表/数据，运用你的专业知识和分析能力，一步一步地分析问题并给出答案。

问题：{question}

{options_text}

回答要求：
1. 以金融专家的视角深入理解问题的本质和背景
2. 一步一步地分析问题的各个层面，展示你的思考过程
3. 给出准确、完整的最终答案

注意：
- 保持金融专家的角色，用专业的方式思考
- 一步一步地分析问题，展示思考过程
- 不要使用Markdown代码块格式
- 输出语言应与问题语言保持一致"""
    }
}


def format_options(options: Optional[dict]) -> str:
    """
    格式化选项为文本
    
    Args:
        options: 选项字典，如 {"A": "选项A内容", "B": "选项B内容"}
        
    Returns:
        格式化后的选项文本
    """
    if not options or not isinstance(options, dict):
        return ""
    
    options_list = []
    for key in sorted(options.keys()):
        value = options.get(key, "")
        if value:  # 只添加非空选项
            options_list.append(f"{key}. {value}")
    
    if options_list:
        return "\n选项：\n" + "\n".join(options_list)
    return ""


def get_prompt(
    profile: str, 
    question: str, 
    options: Optional[dict] = None,
    question_type: Optional[str] = None
) -> str:
    """
    获取指定用户画像的提示词（包含题型提示词）
    
    Args:
        profile: 用户画像（beginner/retail/expert/expert_cot）
        question: 问题文本
        options: 选项字典（可选）
        question_type: 题型名称（可选，支持中英文，如 "单选题" 或 "single_choice"）
                      如果未提供，将根据是否有选项自动判断：
                      - 有选项：默认当作选择题（不区分单选多选，由模型根据题目判断）
                      - 无选项：默认当作问答题
        
    Returns:
        格式化后的完整提示词（包含用户画像提示词和题型提示词）
    """
    if profile not in PROMPTS:
        raise ValueError(f"未知的用户画像: {profile}。可选: {list(PROMPTS.keys())}")
    
    prompt_config = PROMPTS[profile]
    template = prompt_config["template"]
    
    options_text = format_options(options)
    
    # 获取用户画像的基础提示词
    base_prompt = template.format(question=question, options_text=options_text)
    
    # 确定题型提示词
    type_prompt = None
    
    if question_type:
        # 如果提供了题型，使用指定的题型
        normalized_type = normalize_question_type(question_type)
        if normalized_type in QUESTION_TYPE_PROMPTS:
            type_prompt = QUESTION_TYPE_PROMPTS[normalized_type]
    else:
        # 如果没有提供题型，根据是否有选项自动判断
        has_options = options and isinstance(options, dict) and any(options.values())
        if has_options:
            # 有选项：默认当作选择题（不区分单选多选，让模型根据题目判断）
            type_prompt = """这是一道**选择题**，请根据题目和选项给出答案。

要求：
- 仔细阅读问题和所有选项
- 分析每个选项的正确性
- 根据题目要求选择正确答案（可能是单选或多选，请根据题目判断）
- 如果题目要求选择唯一答案，请选择一个；如果题目允许多选，请选择所有正确答案

⚠️ **重要：最终答案必须用 \\boxed{{}} 格式括起来**
- 将选项字母（如 A、B、C 或 D）放在 \\boxed{{}} 中
- 如果是多选，用逗号或分号分隔（如：\\boxed{{A, B}} 或 \\boxed{{A; B}}）
- 格式示例：\\boxed{{A}} 或 \\boxed{{A, B}}"""
        else:
            # 无选项：默认当作问答题
            type_prompt = QUESTION_TYPE_PROMPTS.get("问答题")
    
    # 如果确定了题型提示词，添加到提示词中
    if type_prompt:
        # 在问题之前插入题型提示词
        # 找到 "问题：" 的位置，在之前插入题型提示词
        if "问题：" in base_prompt:
            base_prompt = base_prompt.replace("问题：", f"{type_prompt}\n\n问题：", 1)
        else:
            # 如果没有找到 "问题："，在开头添加题型提示词
            base_prompt = f"{type_prompt}\n\n{base_prompt}"
    
    return base_prompt


def get_all_profiles() -> list:
    """获取所有可用的用户画像列表"""
    return list(PROMPTS.keys())


def get_profile_info(profile: str) -> Dict[str, str]:
    """
    获取用户画像信息
    
    Args:
        profile: 用户画像名称
        
    Returns:
        包含 name 和 description 的字典
    """
    if profile not in PROMPTS:
        raise ValueError(f"未知的用户画像: {profile}")
    
    config = PROMPTS[profile]
    return {
        "name": config["name"],
        "description": config["description"]
    }
