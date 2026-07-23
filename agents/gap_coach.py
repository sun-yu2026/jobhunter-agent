"""
Gap Coach Agent

输入: MatchResult(pydantic 对象) + JDAnalysis(用于岗位上下文)
输出: GapReport(pydantic 对象)

实现说明(延续 Day 5-6 Matcher 的分工):
- LLM 负责语义生成: why / learn_path / estimated_days / questions / quick_wins。
- Python 负责规则性工作:
  1. 校验 skill 是否在 MatchResult.missing_* 里 —— 越权项直接丢弃。
  2. 按类别自动打上优先级(硬=high / 软=medium / 加分=low)。
  3. 排序: high > medium > low, 同优先级内按 MatchResult 原始顺序稳定排序。
  4. 截断: 保留 top-N,防止 LLM 生成一大堆低价值建议。
  5. estimated_days 兜底: LLM 越界(<1 或 >30)时钳到边界。
- 兼容火山方舟接口: PydanticOutputParser + prompt 引导,不依赖 function calling。
"""
import json
import os
from typing import Dict, List, Tuple

from dotenv import load_dotenv
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from prompts.gap_coach import (
    GAP_COACH_SYSTEM_PROMPT,
    GAP_COACH_USER_TEMPLATE,
)
from schemas.gap import (
    GapCoachEvidence,
    GapItem,
    GapItemEvidence,
    GapReport,
    Priority,
)
from schemas.jd import JDAnalysis
from schemas.match import MatchResult

load_dotenv()


# top-N 常量: 硬软加合计缺口再多也只保留前 N 条。
# 取 6 是经验值: 3 硬 + 2 软 + 1 加分基本足够指导一次投递,超过反而让人执行不动。
_MAX_GAPS = 6

# 单个 gap 的天数硬边界。schema 已经限制 1-30,这里再兜一层,防止 LLM 输出
# schema 之外的值时构造对象失败。
_MIN_DAYS = 1
_MAX_DAYS = 30

# 优先级到排序权重的映射: 数字小的排前面。
_PRIORITY_RANK: Dict[Priority, int] = {"high": 0, "medium": 1, "low": 2}


def build_gap_coach():
    """构造 Gap Coach chain。

    返回一个 chain,输入 {"match_result": "...", "job_title": "..."},
    输出 GapCoachEvidence 对象。
    """
    llm = ChatOpenAI(
        api_key=os.getenv("ARK_API_KEY"),
        base_url=os.getenv("LLM_BASE_URL"),
        model=os.getenv("LLM_MODEL"),
        temperature=0,
    )

    parser = PydanticOutputParser(pydantic_object=GapCoachEvidence)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", GAP_COACH_SYSTEM_PROMPT + "\n\n{format_instructions}"),
            ("user", GAP_COACH_USER_TEMPLATE),
        ]
    ).partial(format_instructions=parser.get_format_instructions())

    return prompt | llm | parser


def _validate_input(match_result: MatchResult, jd_analysis: JDAnalysis) -> None:
    """在调用 LLM 前校验输入,避免无效请求消耗额度。"""
    if not isinstance(match_result, MatchResult):
        raise TypeError("match_result 必须是 MatchResult 对象")
    if not isinstance(jd_analysis, JDAnalysis):
        raise TypeError("jd_analysis 必须是 JDAnalysis 对象")
    if not jd_analysis.job_title.strip():
        raise ValueError("JD 解析结果缺少岗位名称")


def _build_missing_index(
    match_result: MatchResult,
) -> Tuple[Dict[str, Priority], Dict[str, int]]:
    """把 missing_* 展平成 {skill: priority} 和 {skill: 原始顺序} 两个索引。

    - priority 用于给 LLM 生成的 gap 打上优先级标签。
    - order 用于同优先级内保持 JD/Matcher 输出的稳定顺序。
    """
    priority_map: Dict[str, Priority] = {}
    order_map: Dict[str, int] = {}
    counter = 0

    def register(items: List[str], priority: Priority) -> None:
        nonlocal counter
        for item in items:
            # 只在没登记过时写入,避免重复项覆盖优先级。
            if item and item not in priority_map:
                priority_map[item] = priority
                order_map[item] = counter
                counter += 1

    register(match_result.missing_hard_skills, "high")
    register(match_result.missing_soft_skills, "medium")
    register(match_result.missing_bonus_points, "low")

    return priority_map, order_map


def _clip_days(days: int) -> int:
    """把 estimated_days 钳到 [_MIN_DAYS, _MAX_DAYS] 之间,防御性兜底。"""
    return max(_MIN_DAYS, min(_MAX_DAYS, days))


def _to_gap_item(evidence: GapItemEvidence, priority: Priority) -> GapItem:
    """把 LLM 侧的 evidence + Python 侧决定的 priority 装配成 GapItem。"""
    return GapItem(
        skill=evidence.skill,
        priority=priority,
        why_it_matters=evidence.why_it_matters.strip(),
        learn_path=evidence.learn_path.strip(),
        estimated_days=_clip_days(evidence.estimated_days),
        interview_questions=list(evidence.interview_questions),
    )


def _select_and_sort_gaps(
    evidence_list: List[GapItemEvidence],
    priority_map: Dict[str, Priority],
    order_map: Dict[str, int],
) -> List[GapItem]:
    """过滤越权项、去重、打上优先级、稳定排序、截断 top-N。"""
    seen: set = set()
    items: List[GapItem] = []

    for evidence in evidence_list:
        skill = evidence.skill
        # 校验: LLM 只能针对 missing_* 里存在的项生成建议;越权项直接丢弃。
        if skill not in priority_map:
            continue
        # 去重: 同一个 skill 只保留第一次出现的建议。
        if skill in seen:
            continue
        seen.add(skill)
        items.append(_to_gap_item(evidence, priority_map[skill]))

    # 排序: (priority_rank, 原始顺序);两个都是数字,越小越靠前。
    items.sort(
        key=lambda item: (_PRIORITY_RANK[item.priority], order_map[item.skill])
    )

    return items[:_MAX_GAPS]


def _build_gap_report(
    evidence: GapCoachEvidence, match_result: MatchResult
) -> GapReport:
    """把 LLM 证据 + Python 规则拼装成最终的 GapReport。"""
    priority_map, order_map = _build_missing_index(match_result)
    priority_gaps = _select_and_sort_gaps(evidence.gaps, priority_map, order_map)

    # quick_wins 直接透传;LLM 返回的就是可执行建议,不需要 Python 决策。
    # 但做一个简单的去空和去重,防御 LLM 输出重复项。
    quick_wins: List[str] = []
    seen_wins: set = set()
    for win in evidence.quick_wins:
        stripped = win.strip()
        if stripped and stripped not in seen_wins:
            quick_wins.append(stripped)
            seen_wins.add(stripped)

    return GapReport(
        priority_gaps=priority_gaps,
        quick_wins=quick_wins,
        overall_strategy=evidence.overall_strategy.strip(),
    )


def coach_gaps(match_result: MatchResult, jd_analysis: JDAnalysis) -> GapReport:
    """便捷入口: 传 MatchResult 和 JDAnalysis,返回 GapReport。"""
    _validate_input(match_result, jd_analysis)
    chain = build_gap_coach()

    # 只把 MatchResult 里 Coach 用得到的字段发给 LLM,减小 prompt 体积。
    match_context = match_result.model_dump()
    evidence = chain.invoke(
        {
            "match_result": json.dumps(match_context, ensure_ascii=False, indent=2),
            "job_title": jd_analysis.job_title,
        }
    )
    return _build_gap_report(evidence, match_result)


if __name__ == "__main__":
    # 命令行直接跑: python -m agents.gap_coach
    import sys

    from agents.jd_analyzer import analyze_jd
    from agents.resume_matcher import match_resume

    sys.stdout.reconfigure(encoding="utf-8")

    demo_jd = """岗位:AI 应用开发工程师
要求:
- 熟练掌握 Python,有 FastAPI 开发经验
- 熟悉 LangChain / LangGraph
- 熟悉向量数据库(Chroma / Milvus)
- 良好的沟通能力
加分项:
- 有 Agent 项目落地经验者优先
- 熟悉 Docker 部署更佳
"""
    demo_resume = """求职方向:AI 应用开发工程师
技能:Python、FastAPI、LangChain。
项目:实现过基于 RAG 的企业知识库问答系统,负责需求沟通与接口开发。
"""

    jd = analyze_jd(demo_jd)
    match = match_resume(demo_resume, jd)
    report = coach_gaps(match, jd)

    print("=" * 60)
    print(f"目标岗位: {jd.job_title}")
    print("-" * 60)
    for i, gap in enumerate(report.priority_gaps, 1):
        print(f"[{i}] [{gap.priority.upper()}] {gap.skill}  (~{gap.estimated_days} 天)")
        print(f"    为什么重要: {gap.why_it_matters}")
        print(f"    学习路径:  {gap.learn_path}")
        print(f"    面试题:    {gap.interview_questions}")
        print()
    print("Quick wins:")
    for w in report.quick_wins:
        print(f"  - {w}")
    print("-" * 60)
    print(f"整体策略: {report.overall_strategy}")
    print("=" * 60)
