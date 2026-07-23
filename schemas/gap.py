"""
Gap Coach 的结构化输出 Schema。

设计原则(延续 Day 5-6 Matcher 的 LLM-vs-Python 分工):
- LLM 只负责语义生成: 为每个缺口写 why / learn_path / interview_questions,
  以及识别可以靠改写简历补上的 quick_wins。
- Python 负责规则性工作: 分配 priority、按硬技能 > 软技能 > 加分项排序、
  截断 top-N、estimated_days 范围校验、去重。
- 因此对外 GapItem 里的 priority 字段由 Python 填充,LLM 输出的 GapItemEvidence
  不包含 priority,避免 LLM 越权。
"""
from typing import List, Literal

from pydantic import BaseModel, Field


# 硬技能 = high,软技能 = medium,加分项 = low。
# 用 Literal 而不是自由字符串,防止下游拿到 "非常重要" 这种口语值。
Priority = Literal["high", "medium", "low"]


class GapItemEvidence(BaseModel):
    """LLM 为单个缺口生成的语义信息。

    只放"需要语义理解才能写出来"的字段,不放 priority(那是规则决定的),
    也不放技能名(技能名从 MatchResult 里原样传入,避免 LLM 改写措辞)。
    """

    skill: str = Field(
        description="缺口的技能/能力名称,必须与 MatchResult 中 missing_* 里的原文完全一致。"
    )
    why_it_matters: str = Field(
        description="1 句话解释这个缺口对目标岗位为什么重要,基于 JD 上下文,不要空话。"
    )
    learn_path: str = Field(
        description=(
            "一条可执行的学习路径,尽量给出具体动作和产出,例如 "
            "'读官方 QuickStart(1 天) → 跑通 2 个示例(2 天) → 用 Chroma 做一个 mini RAG(3 天)'。"
        )
    )
    estimated_days: int = Field(
        ge=1,
        le=30,
        description="补上这个缺口的合理学习天数估计,取值 1-30。超过范围由 Python 侧兜底。",
    )
    interview_questions: List[str] = Field(
        default_factory=list,
        description="围绕这个技能的 2-3 道面试常见问题,不要给答案,只列问题。",
    )


class GapCoachEvidence(BaseModel):
    """LLM 返回的原始建议,仅供 Gap Coach 内部使用。

    Python 侧会:
    - 校验每个 gap 的 skill 是否在 MatchResult 的 missing_* 里
    - 给每个 gap 打上 priority(硬=high / 软=medium / 加分=low)
    - 排序 + 截断 top-N
    - 校准 estimated_days 到 [1, 30]
    - 装配成 GapReport
    """

    gaps: List[GapItemEvidence] = Field(
        default_factory=list,
        description="针对 MatchResult 中所有 missing_* 项目生成的建议,每项一个 GapItemEvidence。",
    )
    quick_wins: List[str] = Field(
        default_factory=list,
        description=(
            "可以通过改写简历措辞就能补上的项,例如 '简历里的企业知识库项目实际就是 RAG,"
            "建议在描述里明确写出检索增强生成'。每项 1 句话,不要建议造假经历。"
        ),
    )
    overall_strategy: str = Field(
        description=(
            "2-4 句话的总体投递策略,说明先补哪些、可以先靠改写简历补哪些、"
            "是否建议投递。不要给出具体分数,不要编造经历。"
        )
    )


class GapItem(BaseModel):
    """带优先级的单个缺口条目,是最终交付给下游的形状。"""

    skill: str = Field(description="缺口技能/能力,沿用 JD/MatchResult 中的原始措辞。")
    priority: Priority = Field(
        description="优先级: high=硬技能缺口, medium=软技能缺口, low=加分项缺口。"
    )
    why_it_matters: str = Field(description="1 句话解释为什么这个缺口重要。")
    learn_path: str = Field(description="可执行的学习路径,含具体动作和大致周期。")
    estimated_days: int = Field(
        ge=1, le=30, description="补上该缺口的估计天数,取值 1-30。"
    )
    interview_questions: List[str] = Field(
        default_factory=list, description="围绕该技能的 2-3 道常见面试题。"
    )


class GapReport(BaseModel):
    """Gap Coach 的最终输出: 一份可执行的缺口补强报告。"""

    priority_gaps: List[GapItem] = Field(
        default_factory=list,
        description=(
            "按优先级(high > medium > low)排序后的缺口列表,最多保留 top-N 条。"
            "N 的具体值由 Agent 侧的常量决定,不写死在 schema 里。"
        ),
    )
    quick_wins: List[str] = Field(
        default_factory=list,
        description="靠改写简历就能补上的项,每项 1 句可执行建议。",
    )
    overall_strategy: str = Field(
        description="2-4 句话的整体投递策略,不含具体分数,不编造经历。"
    )
