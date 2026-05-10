# 🌊 Conflux 使用指南

## 一、整体流程

```
准备文档 → init → import → build → serve（查看结果）
   ↓          ↓        ↓        ↓          ↓
Markdown   创建项目  导入文档  AI编译     Web UI
/EPUB/PDF   结构               组网+冲突   知识图谱
```

整个流程只需要 **4 条命令**。

---

## 二、快速开始（5 分钟上手）

### Step 1: 安装

```bash
cd conflux
pip install -e .
# 如果要用本地 embedding（推荐，免费离线）:
pip install sentence-transformers
```

### Step 2: 初始化知识库

```bash
conflux init --name "我的医学知识库"
```

会生成以下结构：
```
.
├── conflux.config.yaml    ← 配置文件
├── sources/               ← 放入你的书籍/文档
├── output/
│   ├── skills/            ← 生成的 Skill 文件
│   └── vault/             ← 生成的 Obsidian 笔记
├── data/                  ← 数据存储
└── logs/
```

### Step 3: 编辑配置文件

打开 `conflux.config.yaml`，根据你的需要调整：

```yaml
engine:
  llm:
    provider: "deepseek"              # 使用 DeepSeek
    model: "deepseek/deepseek-chat"   # DeepSeek-V3
    api_key_env: "DEEPSEEK_API_KEY"   # 从这个环境变量读 key
  embedding:
    provider: "local"                          # ← 本地 embedding，免费离线
    model: "BAAI/bge-small-zh-v1.5"            # 中文优秀模型
  networking:
    similarity_threshold: 0.85        # 概念合并阈值
```

### Step 4: 设置 API Key

```bash
# 对话/推理用 DeepSeek（便宜，中文强）
export DEEPSEEK_API_KEY="sk-你的key"

# Embedding 用本地模型 → 不需要额外 Key！
```

> **还没有 DeepSeek Key？** 去 https://platform.deepseek.com 注册，有免费额度。

### Step 5: 放入书籍

把你的 `.md`、`.epub` 或 `.pdf` 文件放入 `sources/` 目录。

### Step 6: 导入 & 构建

```bash
# 导入单个文件
conflux import sources/内科学.md

# 或批量导入整个目录
conflux import batch ./sources

# 构建：概念提取 → 组网 → 冲突检测 → 输出
conflux build
```

### Step 7: 查看结果

```bash
# 启动 Web UI
conflux serve --port 8080
# 浏览器打开 http://localhost:8080
```

---

## 三、所有 CLI 命令速查

| 命令 | 作用 |
|------|------|
| `conflux init --name "xxx"` | 初始化知识库项目 |
| `conflux import <文件>` | 导入单个文档 |
| `conflux import batch [目录]` | 批量导入目录下所有文档 |
| `conflux import list` | 查看已导入的文档 |
| `conflux import remove <id>` | 删除已导入的文档 |
| `conflux build` | 编译 + 组网 + 冲突检测 + 生成输出 |
| `conflux build --skip-conflicts` | 跳过冲突检测 |
| `conflux build --skip-networking` | 跳过组网 |
| `conflux build --full` | 全量重建（忽略缓存） |
| `conflux serve --port 8080` | 启动 Web UI |
| `conflux status` | 查看知识库状态 |
| `conflux doctor` | 诊断环境 |
| `conflux clean` | 清理输出文件 |
| `conflux version` | 显示版本 |

---

## 四、配置详解

### `conflux.config.yaml` 完整结构

```yaml
project:
  name: "我的知识库"
  language: "zh-CN"

input:
  sources_dir: "./sources"
  supported_formats: ["md", "epub", "pdf"]

output:
  skills_dir: "./output/skills"
  vault_dir: "./output/vault"

engine:
  llm:
    provider: "deepseek"                # openai | deepseek | anthropic
    model: "deepseek/deepseek-chat"     # LiteLLM 模型名
    api_key_env: "DEEPSEEK_API_KEY"     # 读取 API Key 的环境变量名
    api_base: ""                        # 自定义 API 端点（可选）

  embedding:
    provider: "local"                   # "local" 或 "api"
    model: "BAAI/bge-small-zh-v1.5"     # 本地模型名 或 API 模型名

  conflict_detection:
    sensitivity: "medium"               # low | medium | high

  networking:
    similarity_threshold: 0.85          # 0.0-1.0，越高越严格

storage:
  vector_db: "chromadb"
  graph_db: "networkx"
  persistence_dir: "./data/"
```

### LLM Provider 配置对照

| Provider | model 值 | api_key_env | 备注 |
|----------|---------|-------------|------|
| DeepSeek | `deepseek/deepseek-chat` | `DEEPSEEK_API_KEY` | 推荐，中文强 |
| OpenAI | `gpt-4o-mini` 或 `gpt-4o` | `OPENAI_API_KEY` | 需翻墙 |
| 智谱 AI | `zhipu/glm-4` | `ZHIPUAI_API_KEY` | 国内可访问 |
| 本地 Ollama | `ollama/qwen2.5:7b` | 不需要 | 完全离线 |

### Embedding 配置对照

| 方案 | provider | model | 是否需要网络 | 是否免费 |
|------|----------|-------|-------------|---------|
| **本地模型（推荐）** | `local` | `BAAI/bge-small-zh-v1.5` | 仅首次下载 | ✅ |
| 本地大模型 | `local` | `BAAI/bge-large-zh-v1.5` | 仅首次下载 | ✅ |
| OpenAI API | `api` | `text-embedding-3-small` | 是 | ❌ |

---

## 五、Python API 使用

除了 CLI，你也可以用 Python 代码直接调用各模块：

### 5.1 基本调用

```python
import asyncio
from conflux.llm.client import LLMClient, LLMConfig

# 配置：DeepSeek 对话 + 本地 Embedding
config = LLMConfig(
    provider="deepseek",
    model="deepseek/deepseek-chat",
    embed_provider="local",               # 本地 embedding
    embed_model_name="BAAI/bge-small-zh-v1.5",
)
client = LLMClient(config)

async def main():
    # 对话
    reply = await client.chat(
        system_prompt="你是医学专家",
        user_prompt="什么是心律失常？"
    )
    print(reply)

    # Embedding（走本地模型，不需要 API Key）
    vector = await client.embed("心律失常")
    print(f"向量维度: {len(vector)}")

asyncio.run(main())
```

### 5.2 概念组网

```python
from conflux.models.concept import Concept
from conflux.networker import SimilarityEngine

engine = SimilarityEngine(llm_client=client, threshold=0.7)

concept_a = Concept(name="心率", definition="每分钟心脏搏动的次数")
concept_b = Concept(name="心跳频率", definition="心脏每分钟跳动次数")

# 先计算 embedding
await engine.ensure_embedding(concept_a)
await engine.ensure_embedding(concept_b)

# 判断是否同一概念
is_same = engine.is_same_concept(concept_a, concept_b)
print(f"是否同一概念: {is_same}")  # True (相似度 ≈ 0.85)
```

### 5.3 冲突检测

```python
from conflux.models.conflict import Claim
from conflux.conflict import StanceDetector, SeverityScorer

claim_a = Claim(
    statement="正常成人静息心率为 60-100 次/分",
    subject="正常心率范围",
    source_book="内科学",
)
claim_b = Claim(
    statement="普通人正常心率为 50-90 次/分",
    subject="正常心率范围",
    source_book="运动医学",
)

detector = StanceDetector()
same_topic = detector._same_topic(claim_a, claim_b)
print(f"同一主题: {same_topic}")  # True
```

---

## 六、干跑测试（不需要任何 Key）

如果你只想先看看整个流程，可以用 dry-run 模式：

```bash
# 运行内置 demo（自动 dry-run）
cd conflux
.venv/bin/python demo.py

# 运行本地 Embedding 真实语义计算 demo
.venv/bin/python demo_local_embed.py
```

在代码中使用 dry-run：

```python
config = LLMConfig(
    dry_run=True,            # 对话 API 返回 mock 数据
    embed_provider="local",  # embedding 仍用真实本地模型
)
```

---

## 七、常见问题

### Q: 为什么要分 LLM 和 Embedding 两个配置？

因为它们做的事情完全不同：
- **LLM（对话）**：从文本中提取概念、生成结构化数据、检测冲突（需要推理能力）
- **Embedding**：把文本变成向量，用于计算语义相似度（不需要推理，只需要好的向量表示）

所以可以混搭：用 DeepSeek 做对话推理（便宜），用本地模型做 Embedding（免费）。

### Q: 本地 Embedding 模型第一次下载很慢？

模型约 90MB，首次自动从 HuggingFace 下载。如果网络慢，可以：

```bash
# 方案 1: 使用镜像
export HF_ENDPOINT=https://hf-mirror.com
.venv/bin/python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-zh-v1.5')"

# 方案 2: 手动下载后指定路径
# 下载到 ~/.cache/huggingface/ 即可，程序会自动找到
```

### Q: 没有任何 API Key 能用吗？

能！两种方式：

1. **dry-run 模式**：`dry_run=True`，所有 LLM 调用返回 mock 数据，适合了解流程
2. **本地 Ollama**：装 Ollama + 中文模型，对话和 Embedding 都走本地

```bash
# 安装 Ollama 后
ollama pull qwen2.5:7b

# 配置
engine:
  llm:
    provider: "ollama"
    model: "ollama/qwen2.5:7b"
  embedding:
    provider: "local"
    model: "BAAI/bge-small-zh-v1.5"
```

### Q: 支持哪些文档格式？

- **Markdown** (.md) — 最佳支持
- **EPUB** (.epub) — 电子书
- **PDF** (.pdf) — 需要 PDF 解析库支持
