"""
Resume Matcher Agent

输入:简历文本(str) + JDAnalysis
输出:MatchResult(pydantic 对象)

实现说明:
- LLM 只负责需要语义理解的命中判断和总评。
- Python 负责命中归一化、缺失项补全和 70/20/10 确定性评分。
- 结构化输出沿用 PydanticOutputParser,兼容火山方舟当前接口。
"""
import json
import os
from typing import List

from dotenv import load_dotenv
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from prompts.resume_matcher import (
    RESUME_MATCHER_SYSTEM_PROMPT,
    RESUME_MATCHER_USER_TEMPLATE,
)
from schemas.jd import JDAnalysis
from schemas.match import MatchResult, ResumeMatchEvidence

load_dotenv()


def build_resume_matcher():
    """构造 Resume Matcher chain。

    返回一个 chain,输入 {"resume_text": "...", "jd_analysis": "..."},
    输出 ResumeMatchEvidence 对象。
    """
    llm = ChatOpenAI(
        api_key=os.getenv("ARK_API_KEY"),
        base_url=os.getenv("LLM_BASE_URL"),
        model=os.getenv("LLM_MODEL"),
        temperature=0,
    )

    parser = PydanticOutputParser(pydantic_object=ResumeMatchEvidence)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", RESUME_MATCHER_SYSTEM_PROMPT + "\n\n{format_instructions}"),
            ("user", RESUME_MATCHER_USER_TEMPLATE),
        ]
    ).partial(format_instructions=parser.get_format_instructions())

    return prompt | llm | parser


def _validate_input(resume_text: str, jd_analysis: JDAnalysis) -> None:
    """在调用 LLM 前校验输入,避免无效请求消耗额度。"""
    if not isinstance(resume_text, str):
        raise TypeError("resume_text 必须是字符串")
    if not resume_text.strip():
        raise ValueError("简历文本为空")
    if not isinstance(jd_analysis, JDAnalysis):
        raise TypeError("jd_analysis 必须是 JDAnalysis 对象")
    if not jd_analysis.job_title.strip():
        raise ValueError("JD 解析结果缺少岗位名称")


def _item_key(item: str) -> str:
    """生成用于匹配的规范键,保留输出时仍使用 JD 原文。"""
    return " ".join(item.split()).casefold()


def _unique_requirements(requirements: List[str]) -> List[str]:
    """按 JD 顺序去重,忽略大小写与多余空白。"""
    unique = []
    seen = set()
    for requirement in requirements:
        key = _item_key(requirement)
        if key and key not in seen:
            unique.append(requirement)
            seen.add(key)
    return unique


def _normalize_hits(hits: List[str], requirements: List[str]) -> List[str]:
    """只保留合法 JD 项,去重并按 JD 原始顺序返回。"""
    hit_keys = {_item_key(hit) for hit in hits if _item_key(hit)}
    return [
        requirement
        for requirement in _unique_requirements(requirements)
        if _item_key(requirement) in hit_keys
    ]


def _find_missing(requirements: List[str], hits: List[str]) -> List[str]:
    """由 JD 全量和归一化命中项确定性计算缺失项。"""
    hit_keys = {_item_key(hit) for hit in hits}
    return [
        requirement
        for requirement in _unique_requirements(requirements)
        if _item_key(requirement) not in hit_keys
    ]


def _compute_category_score(hits: List[str], requirements: List[str]) -> float:
    """按命中率计算分项分;JD 未提出该类要求时不扣分。"""
    unique_requirements = _unique_requirements(requirements)
    if not unique_requirements:
        return 100.0
    return round(len(hits) / len(unique_requirements) * 100, 1)


def _compute_total_score(hard_score: float, soft_score: float, bonus_score: float) -> float:
    """按固定的 70/20/10 权重计算总分。"""
    return round(hard_score * 0.7 + soft_score * 0.2 + bonus_score * 0.1, 1)


def _build_match_result(evidence: ResumeMatchEvidence, jd_analysis: JDAnalysis) -> MatchResult:
    """将 LLM 证据转换成完整、可复算的 MatchResult。"""
    hit_hard = _normalize_hits(evidence.hit_hard_skills, jd_analysis.hard_skills)
    hit_soft = _normalize_hits(evidence.hit_soft_skills, jd_analysis.soft_skills)
    hit_bonus = _normalize_hits(evidence.hit_bonus_points, jd_analysis.bonus_points)

    missing_hard = _find_missing(jd_analysis.hard_skills, hit_hard)
    missing_soft = _find_missing(jd_analysis.soft_skills, hit_soft)
    missing_bonus = _find_missing(jd_analysis.bonus_points, hit_bonus)

    hard_score = _compute_category_score(hit_hard, jd_analysis.hard_skills)
    soft_score = _compute_category_score(hit_soft, jd_analysis.soft_skills)
    bonus_score = _compute_category_score(hit_bonus, jd_analysis.bonus_points)

    return MatchResult(
        total_score=_compute_total_score(hard_score, soft_score, bonus_score),
        hard_skills_score=hard_score,
        soft_skills_score=soft_score,
        bonus_points_score=bonus_score,
        hit_hard_skills=hit_hard,
        missing_hard_skills=missing_hard,
        hit_soft_skills=hit_soft,
        missing_soft_skills=missing_soft,
        hit_bonus_points=hit_bonus,
        missing_bonus_points=missing_bonus,
        assessment=evidence.assessment.strip(),
    )


def match_resume(resume_text: str, jd_analysis: JDAnalysis) -> MatchResult:
    """便捷入口:传简历文本和 JDAnalysis,返回确定性评分结果。"""
    _validate_input(resume_text, jd_analysis)
    chain = build_resume_matcher()

    jd_context = jd_analysis.model_dump(exclude={"raw_jd"})
    evidence = chain.invoke(
        {
            "resume_text": resume_text,
            "jd_analysis": json.dumps(jd_context, ensure_ascii=False, indent=2),
        }
    )
    return _build_match_result(evidence, jd_analysis)


if __name__ == "__main__":
    # 命令行直接跑:python -m agents.resume_matcher
    import sys

    from agents.jd_analyzer import analyze_jd

    sys.stdout.reconfigure(encoding="utf-8")

    demo_jd = """岗位:AI 应用开发工程师
要求:
- 熟练掌握 Python,有 FastAPI 开发经验
- 熟悉 LangChain、RAG 和向量数据库
- 良好的沟通能力
加分项:
- 有 Agent 项目落地经验者优先
"""
    demo_resume = """求职方向:AI 应用开发工程师
技能:Python、FastAPI、LangChain、Chroma 向量数据库。
项目:实现过基于 RAG 的企业知识库问答系统,负责需求沟通与接口开发。
"""

    result = match_resume(demo_resume, analyze_jd(demo_jd))
    print("=" * 50)
    print(f"总分: {result.total_score}")
    print(
        f"分项: 硬技能 {result.hard_skills_score} / "
        f"软技能 {result.soft_skills_score} / 加分项 {result.bonus_points_score}"
    )
    print(f"命中硬技能: {result.hit_hard_skills}")
    print(f"缺失硬技能: {result.missing_hard_skills}")
    print(f"总评: {result.assessment}")
    print("=" * 50)
