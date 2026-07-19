# JobHunter Agent
> 一个多 Agent 协作的 AI 求职复盘工具,帮求职者完成从 JD 解析到模拟面试的完整闭环。
 ## 💡 项目动机

  作为一名正在准备 AI 应用开发岗位面试的求职者,我发现自己面试准备时存在三个痛点:

  1. **JD 关键词提取全靠肉眼**,20 份 JD 读完记不住重点
  2. **不知道简历和 JD 匹配度到底几分**,投出去像开盲盒
  3. **面试前不知道会被问什么**,没法针对性准备

  于是我做了这个工具——**让 AI 帮我准备 AI 岗位的面试**。
 ## ✨  特性
  - 🤖 4 个专业 Agent 协作（LangGraph 编排）
  - 📊 简历匹配度量化打分
  - 🎓 基于 500+ 题库的个性化面试题推荐
  - 💬 支持多轮追问的模拟面试
  - ⚡  全流程流式响应
 ## ✨  核心功能

  | 模块 | 输入 | 输出 |
  |------|------|------|
  | **JD Analyzer** | 岗位 JD 文本 | 结构化 JD(硬技能/软技能/加分项) |
  | **Resume Matcher** | 简历 PDF + JD | 匹配度打分(0-100) + 命中分析 |
  | **Gap Coach** | 匹配结果 | 缺口清单 + 高频面试题推荐 |
  | **Mock Interviewer** | 用户答题 | 多轮追问 + 4 维度评分报告 |

  ---

  ## 📐 系统架构

  用户上传简历 + JD
          ↓
  [JD Analyzer Agent] → 结构化 JD
          ↓
  [Resume Matcher Agent] → 匹配度打分
          ↓
  [Gap Coach Agent] → 缺口 + 面试题推荐(RAG)
          ↓
  [Mock Interviewer Agent] → 模拟面试 + 评分
          ↓
      评分报告

  > 详细架构图见 [docs/architecture.md](docs/architecture.md)(含 Mermaid 数据流图 + 系统分层图)

  ---

  ## 🏗️ 技术栈
  LangGraph · LangChain · FastAPI · Streamlit · Chroma · Pydantic · Docker

    ## 📅 项目进度

  - [x] Day 1: 项目立项 + Repo 初始化
  - [x] Day 2-3: JD Analyzer MVP(Schema + Prompt + 3 份样本 JD 集成测试)
  - [x] Day 4: 系统架构图([docs/architecture.md](docs/architecture.md))
  - [ ] Week 1: 需求调研(20 份 JD 分析) + 环境搭建
  - [ ] Week 2: JD Analyzer Agent
  - [ ] Week 3: Resume Matcher Agent + PDF 解析
  - [ ] Week 4: Gap Coach Agent + RAG 面试题库
  - [ ] Week 5: Mock Interviewer Agent
  - [ ] Week 6: LangGraph 工作流编排
  - [ ] Week 7: FastAPI + Streamlit 前端
  - [ ] Week 8: Docker 部署 + 演示视频

  ---

  ## 🚀 快速开始

  *(施工中,预计 Week 7 提供完整启动流程)*

  ---

  ## 📖 项目文档

  - [产品需求文档 PRD](docs/PRD.md) *(Day 3 完成)*
  - [系统架构图](docs/architecture.md) *(Day 4 完成)*

  ---

  ## 📝 License

 

