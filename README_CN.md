<div align="center">

# UniFinEval

**金融视觉语言模型综合评估框架**

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![arXiv](https://img.shields.io/badge/arXiv-XXXX.XXXXX-b31b1b.svg)](https://arxiv.org/abs/XXXX.XXXXX)

*一个统一的评估框架，用于评估金融视觉语言模型在不同用户画像和多样化问题类型下的表现*

**[English (English README)](README.md)** | **[中文](#中文)**

</div>

---

<a id="中文"></a>
## 📖 概述

**UniFinEval** 是一个专为金融视觉语言模型设计的综合评估框架。它支持多用户画像评估、多轮对话评估，并为各种金融问题类型提供详细的分析功能。

### 核心特性

- 🎯 **多用户画像评估**：支持不同用户画像的评估（金融小白、散户投资者、专家、专家CoT）
- 🔄 **多轮对话支持**：处理复杂的多轮金融对话
- 📊 **全面统计**：按模型、画像、类别和难度进行详细的准确率分析
- 🖼️ **多模态支持**：无缝处理文本和图像输入
- ⚡ **高性能**：可配置并发的并行评估
- 💾 **断点续传**：支持长时间运行的评估的检查点恢复
- 📝 **详细日志**：用于调试和分析的综合日志系统

---

## 🔗 相关链接

- **📄 论文**：[arXiv:XXXX.XXXXX](https://arxiv.org/abs/XXXX.XXXXX) | [PDF](UniFinEval____arXiv.pdf)
- **📦 数据集**：[数据集链接](https://github.com/your-repo/dataset) | [HuggingFace](https://huggingface.co/datasets/your-dataset)
- **💻 代码**：[GitHub 仓库](https://github.com/your-repo/unifineval)

---

## 🚀 快速开始

### 前置要求

- Python 3.8 或更高版本
- pip 包管理器

### 安装

1. **克隆仓库**
   ```bash
   git clone https://github.com/your-repo/unifineval.git
   cd unifineval
   ```

2. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

3. **配置环境变量**
   ```bash
   cp env.example .env
   # 编辑 .env 文件，填入您的 API keys 和配置
   ```

### 基本使用

1. **准备数据集**
   - 根据[输入格式要求](evaluate_py/输入格式要求.md)格式化您的数据
   - 支持的格式：JSON、JSONL、CSV、Excel (.xlsx/.xls)

2. **运行评估**
   ```bash
   python -m evaluate_py.main \
       --input_file ./data/your_dataset.json \
       --output_file eval_results.json \
       --log_dir ./logs \
       --log_level INFO
   ```

3. **使用 Shell 脚本（推荐）**
   ```bash
   # 编辑 evaluate.sh 配置您的设置
   bash evaluate.sh
   ```

---

## 📋 配置

### 环境变量

在项目根目录创建 `.env` 文件，包含以下变量：

```bash
# 不同服务商的 API Keys
api1=your_dashscope_api_key      # 阿里云 DashScope
api2=your_volces_api_key          # 字节跳动火山引擎
api3=your_openrouter_api_key      # OpenRouter
api4=your_siliconflow_api_key     # SiliconFlow

# 要评估的模型（逗号分隔）
EVAL_MODELS=model1,model2,model3

# 本地推理服务配置（如果使用本地模型）
LOCAL_8000_HOST=localhost
LOCAL_8000_PORT=8000
```

完整模板请参考 [env.example](env.example)。

### 模型配置

模型在 `evaluate_py/config.py` 中配置。您可以通过修改 `MODEL_DEFINITIONS` 字典来添加新模型：

```python
MODEL_DEFINITIONS = {
    "your-model-name": {
        "base_url_key": "dashscope",  # 或 "volces", "openrouter" 等
        "model": "your-model-id",
        "max_tokens": 25000,
        "timeout": 1200,
        "enable_thinking": True,
        "extra_body": {}
    }
}
```

---

## 📊 用户画像

框架支持四种用户画像进行评估：

- **beginner**：金融小白，具有基本理解能力
- **retail**：散户投资者，具有中等金融知识
- **expert**：金融专家，具有深厚的领域知识
- **expert_cot**：使用思维链推理的专家

您可以使用 `--profiles` 参数指定画像：

```bash
python -m evaluate_py.main \
    --input_file ./data/dataset.json \
    --profiles beginner retail expert
```

---

## 📁 项目结构

```
unifineval/
├── evaluate_py/              # 核心评估框架
│   ├── __init__.py
│   ├── main.py              # 主入口点
│   ├── config.py            # 配置管理
│   ├── data_loader.py       # 数据加载工具
│   ├── evaluator.py         # 核心评估逻辑
│   ├── model_api.py         # 模型 API 集成
│   ├── judge.py             # 答案评判逻辑
│   ├── prompts.py           # 提示词模板
│   ├── statistics.py        # 统计分析
│   └── ...
├── outputs/                 # 评估结果（自动生成）
│   └── {profile}/
│       └── {model_name}/
│           └── *.json
├── logs/                    # 日志文件（自动生成）
├── env.example             # 环境变量模板
├── requirements.txt        # Python 依赖
├── README.md               # 英文文档
├── README_CN.md            # 中文文档（本文件）
└── evaluate.sh             # 示例评估脚本
```

---

## 🔧 高级用法

### 多轮对话评估

框架自动检测并处理多轮对话。确保您的数据遵循以下格式：

```json
{
  "question_id": "q001",
  "question": {
    "round1": "第一个问题...",
    "round2": "后续问题..."
  },
  "answer": {
    "round1": "第一个答案...",
    "round2": "后续答案..."
  }
}
```

### 断点续传

要恢复之前的评估：

```bash
python -m evaluate_py.main \
    --input_file ./data/dataset.json \
    --output_file eval_results.json \
    --resume
```

### 自定义输出格式

结果以 JSON 或 JSONL 格式保存：

- **JSON**：包含所有结果和统计信息的单个文件
- **JSONL**：行分隔格式，每行一个结果

通过输出文件扩展名指定格式：

```bash
--output_file results.json    # JSON 格式
--output_file results.jsonl   # JSONL 格式
```

### 图像处理

框架支持：
- 本地图像路径
- 图像 URL (http/https)
- 每个问题多张图像
- 自动图像压缩以优化 token 使用

---

## 📈 输出格式

评估结果包括：

```json
{
  "statistics": {
    "total": {
      "total_count": 100,
      "correct_count": 85,
      "accuracy": 0.85
    },
    "by_model": {...},
    "by_profile": {...},
    "by_category": {...}
  },
  "results": [
    {
      "question_id": "q001",
      "question_type": "单选题",
      "profiles": {
        "expert": {
          "models": {
            "model-name": {
              "is_correct": true,
              "extracted_answer": "...",
              "response_time": 2.5,
              ...
            }
          }
        }
      }
    }
  ]
}
```

---

## 🧪 测试

运行测试以验证安装：

```bash
python -m pytest tests/
```

---

## 📝 引用

如果您在研究中使用 UniFinEval，请引用：

```bibtex
@article{unifineval2024,
  title={UniFinEval: A Unified Evaluation Framework for Financial Vision-Language Models},
  author={Your Name and Collaborators},
  journal={arXiv preprint arXiv:XXXX.XXXXX},
  year={2024}
}
```

---

## 🤝 贡献

欢迎贡献！请随时提交 Pull Request。

1. Fork 仓库
2. 创建您的功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交您的更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开 Pull Request

---

## 📄 许可证

本项目采用 MIT 许可证 - 详情请参阅 [LICENSE](LICENSE) 文件。

---

## 🙏 致谢

- 感谢所有贡献者和框架用户
- 特别感谢开源社区的启发和工具

---

## 📧 联系方式

如有问题、建议或反馈：
- 在 [GitHub](https://github.com/your-repo/unifineval/issues) 上提交 issue
- 邮箱：your-email@example.com

---

<div align="center">

**为金融 AI 研究社区而制作 ❤️**

[⬆ 返回顶部](#中文)

</div>
