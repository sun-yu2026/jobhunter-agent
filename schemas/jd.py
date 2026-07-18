"""
JD Analyzer 的结构化输出 Schema。

设计原则(见 role-strategic-advisor 约定):
- 扁平 list,不过度设计。硬技能就是字符串,不拆 name/years/priority。
- 后面 Resume Matcher 需要什么再加字段,而不是提前预留。
- job_title 单独抽出来,方便后续按岗位聚类。
"""
from typing import List
from pydantic import BaseModel, Field


class JDAnalysis(BaseModel):
    """一份 JD 结构化解析结果。"""

    job_title: str = Field(
        description="岗位名称,如 'AI 应用开发工程师'。原文里怎么写就怎么抽,不要改写。"
    )

    hard_skills: List[str] = Field(
        default_factory=list,
        description=(
            "硬技能 / 必备技术栈。只放明确的技术名词,如 'Python'、'LangChain'、"
            "'RAG'、'向量数据库'、'FastAPI'。不要放 '熟练掌握' 这种修饰语。"
        ),
    )

    soft_skills: List[str] = Field(
        default_factory=list,
        description=(
            "软技能 / 通用能力,如 '沟通能力'、'团队协作'、'学习能力'、"
            "'问题拆解'。抽 JD 里明确提到的,不要脑补。"
        ),
    )

    bonus_points: List[str] = Field(
        default_factory=list,
        description=(
            "加分项 / 优先考虑条件。JD 里带 '优先'、'加分'、'有 xx 者优先' "
            "的内容都放这里,如 '有 Agent 项目经验'、'开源贡献'。"
        ),
    )

    raw_jd: str = Field(
        description="原始 JD 全文,方便后续 Resume Matcher 引用上下文。"
    )
