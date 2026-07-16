# jobhunter-agent
一个多 Agent 协作的 AI 求职复盘工具 - JD解析、简历匹配、模拟面试全流程
 一个多 Agent 协作的 AI 求职复盘工具，帮你从 JD 到面试完整闭环。

  ## ✨  特性
  - 🤖 4 个专业 Agent 协作（LangGraph 编排）
  - 📊 简历匹配度量化打分
  - 🎓 基于 500+ 题库的个性化面试题推荐
  - 💬 支持多轮追问的模拟面试
  - ⚡  全流程流式响应

  ## 🏗️ 技术栈
  LangGraph · LangChain · FastAPI · Streamlit · Chroma · Pydantic · Docker

  ## 📐 系统架构

  用户上传简历 + JD
          ↓
  [JD Analyzer Agent] → 结构化 JD
          ↓
  [Resume Matcher Agent] → 匹配度打分
          ↓
  [Gap Coach Agent] → 缺口 + 面试题推荐（RAG）
          ↓
  [Mock Interviewer Agent] → 模拟面试 + 评分
          ↓
      评分报告

  ## 🚀 快速开始

  （施工中，Week 8 完成部署后补充）

  ## 📅 项目进度

  - [x] Week 1: 需求分析 + 环境搭建
  - [ ] Week 2: JD Analyzer Agent
  - [ ] Week 3: Resume Matcher Agent
  - [ ] Week 4: Gap Coach Agent + RAG
  - [ ] Week 5: Mock Interviewer Agent
  - [ ] Week 6: LangGraph 工作流编排
  - [ ] Week 7: FastAPI + Streamlit 前端
  - [ ] Week 8: 部署上线 + 演示视频
