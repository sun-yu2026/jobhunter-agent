# CLAUDE.md — jobhunter-agent 项目上下文

> 这个文件由 Claude Code 在会话启动时自动加载,用来记录跨会话的项目级偏好和约定。

---

## 教学笔记的位置

每次为本项目生成"当日教学文档/教学笔记/教学纪要"时:

- **只写到桌面**:`C:\Users\10940\Desktop\`
- 命名规范:`jobhunter-agent-Day{N}-教学笔记.md`(与已有 Day1-3、Day5-6、Day7 保持一致)
- **不要**放进项目 `docs/` 目录
- **不要**在 `README.md` 里加指向教学笔记的链接
- `docs/` 下只保留架构类、PRD 类的正式项目文档

原因:教学文档是个人学习材料,不进入项目版本管理。

---

## 项目基本信息

- 目标:多 Agent 协作的 AI 求职复盘工具(JD 解析 → 简历匹配 → 缺口教练 → 模拟面试)
- 技术栈:LangChain / LangGraph / FastAPI / Streamlit / Chroma / Pydantic
- LLM:火山方舟 doubao-seed-code(通过 `.env` 中的 `ARK_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL`)
- 虚拟环境:`D:\jobhunter-agent\venv\`,运行脚本时用 `.\venv\Scripts\python.exe`

---

## 分工原则(贯穿全项目)

- **LLM 只做语义理解**(判断命中、生成总评、抽取要点)
- **Python 只做确定性规则**(集合运算、公式计算、去重、归一化、异常拦截)
- 跨 Agent 传递的数据一律用 Pydantic 模型,禁止裸 dict
