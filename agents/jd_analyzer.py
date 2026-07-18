"""
JD Analyzer Agent

输入:JD 文本(str)
输出:JDAnalysis(pydantic 对象)

实现说明:
- 不用 with_structured_output(火山方舟 CodingPlan 的 function calling 兼容不稳)
- 改用 PydanticOutputParser:把 schema 描述塞进 prompt,让模型返回纯 JSON,
  再由 parser 校验并转成 pydantic 对象。兼容性最好,不依赖厂商特性。
"""
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser

from schemas.jd import JDAnalysis
from prompts.jd_analyzer import (
    JD_ANALYZER_SYSTEM_PROMPT,
    JD_ANALYZER_USER_TEMPLATE,
)

load_dotenv()


def build_jd_analyzer():
    """构造 JD Analyzer chain。

    返回一个 chain,输入 {"jd_text": "..."},输出 JDAnalysis 对象。
    """
    llm = ChatOpenAI(
        api_key=os.getenv("ARK_API_KEY"),
        base_url=os.getenv("LLM_BASE_URL"),
        model=os.getenv("LLM_MODEL"),
        temperature=0,  # 抽取任务,不需要创造性
        # 注:doubao-seed-2.0-code 不支持 response_format={"type": "json_object"},
        # 只能靠 prompt 引导 + parser 兜底。
    )

    parser = PydanticOutputParser(pydantic_object=JDAnalysis)

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", JD_ANALYZER_SYSTEM_PROMPT + "\n\n{format_instructions}"),
            ("user", JD_ANALYZER_USER_TEMPLATE),
        ]
    ).partial(format_instructions=parser.get_format_instructions())

    return prompt | llm | parser


def analyze_jd(jd_text: str) -> JDAnalysis:
    """便捷入口:传 JD 文本,返回结构化结果。"""
    chain = build_jd_analyzer()
    return chain.invoke({"jd_text": jd_text})


if __name__ == "__main__":
    # 命令行直接跑:python -m agents.jd_analyzer
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    demo_jd = """岗位:AI 应用开发工程师
职责:
1. 基于 LangChain / LangGraph 搭建多 Agent 系统
2. 负责 RAG 系统的落地与调优
要求:
- 熟练掌握 Python,有 FastAPI 开发经验
- 熟悉大模型 API 调用、Prompt 工程
- 良好的沟通能力和团队协作精神
加分项:
- 有 Agent 项目落地经验者优先
- 熟悉向量数据库(Chroma / Milvus)更佳
"""
    result = analyze_jd(demo_jd)
    print("=" * 50)
    print(f"岗位: {result.job_title}")
    print(f"硬技能: {result.hard_skills}")
    print(f"软技能: {result.soft_skills}")
    print(f"加分项: {result.bonus_points}")
    print("=" * 50)
