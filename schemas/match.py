"""
Resume Matcher 的结构化输出 Schema。

设计原则:
- LLM 只判断哪些 JD 要求在简历中有明确证据。
- 命中归一化、缺失项补全和分数计算全部由 Python 完成。
- 保持扁平结构,方便后续 Gap Coach 直接消费。
"""
from typing import List

from pydantic import BaseModel, Field


class ResumeMatchEvidence(BaseModel):
    """LLM 返回的语义匹配证据,仅供 Resume Matcher 内部使用。"""

    hit_hard_skills: List[str] = Field(
        default_factory=list,
        description="简历中有明确证据的 JD 硬技能,必须原样返回 JD 中的措辞。",
    )
    hit_soft_skills: List[str] = Field(
        default_factory=list,
        description="简历中有明确证据的 JD 软技能,必须原样返回 JD 中的措辞。",
    )
    hit_bonus_points: List[str] = Field(
        default_factory=list,
        description="简历中有明确证据的 JD 加分项,必须原样返回 JD 中的措辞。",
    )
    assessment: str = Field(
        description="2-4 句话的事实性总评,说明主要优势、主要缺口和投递建议,不要编造经历。"
    )


class MatchResult(BaseModel):
    """简历文本与一份 JD 的可解释匹配结果。"""

    total_score: float = Field(
        ge=0,
        le=100,
        description="综合匹配度 0-100,按硬技能 70%、软技能 20%、加分项 10% 计算。",
    )
    hard_skills_score: float = Field(
        ge=0,
        le=100,
        description="硬技能命中率 0-100;JD 未列硬技能时为 100。",
    )
    soft_skills_score: float = Field(
        ge=0,
        le=100,
        description="软技能命中率 0-100;JD 未列软技能时为 100。",
    )
    bonus_points_score: float = Field(
        ge=0,
        le=100,
        description="加分项命中率 0-100;JD 未列加分项时为 100。",
    )
    hit_hard_skills: List[str] = Field(
        default_factory=list,
        description="简历中命中的硬技能,沿用 JD 原文措辞。",
    )
    missing_hard_skills: List[str] = Field(
        default_factory=list,
        description="JD 要求但简历中未体现的硬技能,沿用 JD 原文措辞。",
    )
    hit_soft_skills: List[str] = Field(
        default_factory=list,
        description="简历中命中的软技能,沿用 JD 原文措辞。",
    )
    missing_soft_skills: List[str] = Field(
        default_factory=list,
        description="JD 要求但简历中未体现的软技能,沿用 JD 原文措辞。",
    )
    hit_bonus_points: List[str] = Field(
        default_factory=list,
        description="简历中命中的加分项,沿用 JD 原文措辞。",
    )
    missing_bonus_points: List[str] = Field(
        default_factory=list,
        description="JD 加分项中简历未体现的内容,沿用 JD 原文措辞。",
    )
    assessment: str = Field(
        description="2-4 句话的事实性总评,说明主要优势、主要缺口和投递建议。"
    )
