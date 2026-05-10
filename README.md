# 🌊 Conflux

> 一本"会自我生长、自带纠错机制"的活体百科全书引擎

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

## 🎯 什么是 Conflux？

Conflux 将书籍/文档**双向编译**为：
- 🤖 **机器可调用的 Skill 索引** — 让 AI Agent 精准调用知识
- 🧠 **人类可探索的知识图谱** — Obsidian Vault 格式，支持非线性联想

同时，Conflux 会自动**感知跨源知识冲突**，将矛盾点显式标注，交由人类裁决。

## ✨ 核心特性

### 🔄 双向编译 (Dual Compilation)
将一本书同时编译为两套输出：
- **Skill YAML** — 结构化知识索引，可被 AI Agent / MCP 直接调用
- **Obsidian Vault** — 概念节点 + 双向链接，支持知识漫游

### 🕸️ 动态组网 (Dynamic Networking)
导入新书时，系统智能决策：
- **新知** → 开辟新的知识子网
- **旧识** → 自动建立跨书连接（如《生理学》的"心脏" ↔ 《解剖学》的"心肌"）

### ⚡ 冲突感知 (Conflict Awareness)
当不同来源的知识"打架"时：
- 自动识别矛盾论断
- 分类冲突类型（事实性/方法论/解读差异/时效性）
- 评估严重程度
- **不替你做主**，而是交由人类裁决

## 🚀 快速开始

### 安装

```bash
pip install conflux
```

### 初始化项目

```bash
conflux init --name "我的知识库"
```

### 导入一本书

```bash
conflux import ./books/生理学.md
```

### 构建输出

```bash
conflux build
```

### 查看冲突

```bash
conflux conflicts list
```

## 📖 输出示例

### Skill 文件 (给 AI 看)

```yaml
skill:
  id: "physiology.body_temperature"
  name: "人体体温知识"
  source:
    book: "《生理学》第9版"
    chapter: "第七章 能量代谢与体温"
  knowledge:
    facts:
      - "人体正常核心温度为36.5-37.5℃"
      - "体温调节中枢位于下丘脑"
    procedures:
      - trigger: "用户询问体温是否正常"
        steps:
          - "确认测量部位"
          - "对照正常范围判断"
```

### 概念节点 (给人看，Obsidian Markdown)

```markdown
# 心脏

## 来自不同书籍的视角
### 《生理学》视角
- 重点：电生理、心肌收缩机制
- [[心肌细胞动作电位]] | [[Frank-Starling机制]]

### 《解剖学》视角
- 重点：位置、形态、腔室结构
- [[心包]] | [[冠状动脉]]

## ⚠️ 冲突标注
- [[conflict_023]] — 关于"安静心率正常范围"的定义差异
```

## 🏗️ 架构

```
输入 (PDF/EPUB/MD) → 解析层 → 编译层 → 组网层 → 冲突检测 → 双向输出
                                                            ├── Skills (YAML)
                                                            └── Vault (Obsidian)
```

详细架构文档见 [docs/architecture.md](docs/architecture.md)

## 🛣️ Roadmap

- [x] **Phase 1**: 单书双向编译（Markdown → Skill + Vault）
- [ ] **Phase 2**: 多书动态组网
- [ ] **Phase 3**: 冲突检测与裁决 UI
- [ ] **Phase 4**: Web UI + 实时协作
- [ ] **Phase 5**: 插件系统 + 社区生态

## 🤝 贡献

欢迎参与贡献！查看 [CONTRIBUTING.md](CONTRIBUTING.md) 了解如何参与。

**特别欢迎的贡献方向**：
- 📄 新格式 Parser 插件
- 🎯 Skill 模板（适配不同 Agent 框架）
- ⚖️ 冲突裁决语料众包
- 🌐 多语言支持

## 📄 License

[MIT](LICENSE) © Conflux Contributors
