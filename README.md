<div align="center">

# UniFinEval

**A Comprehensive Evaluation Framework for Financial Vision-Language Models**

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![arXiv](https://img.shields.io/badge/arXiv-XXXX.XXXXX-b31b1b.svg)](https://arxiv.org/abs/XXXX.XXXXX)

*A unified evaluation framework for assessing financial vision-language models across multiple user profiles and diverse question types*

**[English](#english)** | **[中文 (中文版 README)](README_CN.md)**

</div>

---

<a id="english"></a>
## 📖 Overview

**UniFinEval** is a comprehensive evaluation framework designed specifically for financial vision-language models. It supports multi-user profile evaluation, multi-round dialogue assessment, and provides detailed analysis capabilities for various financial question types.

### Key Features

- 🎯 **Multi-User Profile Evaluation**: Supports evaluation across different user profiles (beginner, retail investor, expert, expert with CoT)
- 🔄 **Multi-Round Dialogue Support**: Handles complex multi-turn financial conversations
- 📊 **Comprehensive Statistics**: Detailed accuracy analysis by model, profile, category, and difficulty
- 🖼️ **Multi-Modal Support**: Seamlessly handles both text and image inputs
- ⚡ **High Performance**: Parallel evaluation with configurable concurrency
- 💾 **Resume Capability**: Supports checkpoint resumption for long-running evaluations
- 📝 **Detailed Logging**: Comprehensive logging system for debugging and analysis

---

## 🔗 Links

- **📄 Paper**: [arXiv:XXXX.XXXXX](https://arxiv.org/abs/XXXX.XXXXX) | [PDF](UniFinEval____arXiv.pdf)
- **📦 Dataset**: [Dataset Link](https://github.com/your-repo/dataset) | [HuggingFace](https://huggingface.co/datasets/your-dataset)
- **💻 Code**: [GitHub Repository](https://github.com/your-repo/unifineval)

---

## 🚀 Quick Start

### Prerequisites

- Python 3.8 or higher
- pip package manager

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-repo/unifineval.git
   cd unifineval
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables**
   ```bash
   cp env.example .env
   # Edit .env file with your API keys and configuration
   ```

### Basic Usage

1. **Prepare your dataset**
   - Format your data according to the [Input Format Requirements](evaluate_py/输入格式要求.md)
   - Supported formats: JSON, JSONL, CSV, Excel (.xlsx/.xls)

2. **Run evaluation**
   ```bash
   python -m evaluate_py.main \
       --input_file ./data/your_dataset.json \
       --output_file eval_results.json \
       --log_dir ./logs \
       --log_level INFO
   ```

3. **Using shell script (recommended)**
   ```bash
   # Edit evaluate.sh to configure your settings
   bash evaluate.sh
   ```

---

## 📋 Configuration

### Environment Variables

Create a `.env` file in the project root with the following variables:

```bash
# API Keys for different providers
api1=your_dashscope_api_key      # Alibaba Cloud DashScope
api2=your_volces_api_key          # ByteDance Volces
api3=your_openrouter_api_key      # OpenRouter
api4=your_siliconflow_api_key     # SiliconFlow

# Models to evaluate (comma-separated)
EVAL_MODELS=model1,model2,model3

# Local inference service configuration (if using local models)
LOCAL_8000_HOST=localhost
LOCAL_8000_PORT=8000
```

See [env.example](env.example) for a complete template.

### Model Configuration

Models are configured in `evaluate_py/config.py`. You can add new models by modifying the `MODEL_DEFINITIONS` dictionary:

```python
MODEL_DEFINITIONS = {
    "your-model-name": {
        "base_url_key": "dashscope",  # or "volces", "openrouter", etc.
        "model": "your-model-id",
        "max_tokens": 25000,
        "timeout": 1200,
        "enable_thinking": True,
        "extra_body": {}
    }
}
```

---

## 📊 User Profiles

The framework supports four user profiles for evaluation:

- **beginner**: Financial novice with basic understanding
- **retail**: Retail investor with moderate financial knowledge
- **expert**: Financial expert with deep domain knowledge
- **expert_cot**: Expert using chain-of-thought reasoning

You can specify profiles using the `--profiles` argument:

```bash
python -m evaluate_py.main \
    --input_file ./data/dataset.json \
    --profiles beginner retail expert
```

---

## 📁 Project Structure

```
unifineval/
├── evaluate_py/              # Core evaluation framework
│   ├── __init__.py
│   ├── main.py              # Main entry point
│   ├── config.py            # Configuration management
│   ├── data_loader.py       # Data loading utilities
│   ├── evaluator.py         # Core evaluation logic
│   ├── model_api.py         # Model API integration
│   ├── judge.py             # Answer judging logic
│   ├── prompts.py           # Prompt templates
│   ├── statistics.py        # Statistical analysis
│   └── ...
├── outputs/                 # Evaluation results (auto-generated)
│   └── {profile}/
│       └── {model_name}/
│           └── *.json
├── logs/                    # Log files (auto-generated)
├── env.example             # Environment variable template
├── requirements.txt        # Python dependencies
├── README.md               # This file (English)
├── README_CN.md            # Chinese documentation
└── evaluate.sh             # Example evaluation script
```

---

## 🔧 Advanced Usage

### Multi-Round Dialogue Evaluation

The framework automatically detects and handles multi-round dialogues. Ensure your data follows the format:

```json
{
  "question_id": "q001",
  "question": {
    "round1": "First question...",
    "round2": "Follow-up question..."
  },
  "answer": {
    "round1": "First answer...",
    "round2": "Follow-up answer..."
  }
}
```

### Resume Evaluation

To resume a previous evaluation:

```bash
python -m evaluate_py.main \
    --input_file ./data/dataset.json \
    --output_file eval_results.json \
    --resume
```

### Custom Output Format

Results are saved in JSON or JSONL format:

- **JSON**: Single file with all results and statistics
- **JSONL**: Line-delimited format, one result per line

Specify format via output file extension:

```bash
--output_file results.json    # JSON format
--output_file results.jsonl   # JSONL format
```

### Image Handling

The framework supports:
- Local image paths
- Image URLs (http/https)
- Multiple images per question
- Automatic image compression for token optimization

---

## 📈 Output Format

Evaluation results include:

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

## 🧪 Testing

Run tests to verify installation:

```bash
python -m pytest tests/
```

---

## 📝 Citation

If you use UniFinEval in your research, please cite:

```bibtex
@article{unifineval2024,
  title={UniFinEval: A Unified Evaluation Framework for Financial Vision-Language Models},
  author={Your Name and Collaborators},
  journal={arXiv preprint arXiv:XXXX.XXXXX},
  year={2024}
}
```

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- Thanks to all contributors and users of this framework
- Special thanks to the open-source community for inspiration and tools

---

## 📧 Contact

For questions, issues, or suggestions:
- Open an issue on [GitHub](https://github.com/your-repo/unifineval/issues)
- Email: your-email@example.com

---

<div align="center">

**Made with ❤️ for the Financial AI Research Community**

[⬆ Back to Top](#unifineval)

</div>
