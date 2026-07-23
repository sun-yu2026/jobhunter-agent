"""
Gap Coach 的纯逻辑测试。

不调用 LLM API,只覆盖 Python 侧的规则:
- 优先级自动分配(硬=high / 软=medium / 加分=low)
- 排序(priority + 原始顺序)
- 截断到 top-N
- 越权项丢弃(LLM 编了 MatchResult 里不存在的技能)
- 去重
- estimated_days 兜底钳位
- quick_wins 透传 + 去重去空
- 输入校验

跑法:
  cd D:\\jobhunter-agent
  .\\venv\\Scripts\\python.exe -m tests.test_gap_coach_logic
"""
import sys

sys.stdout.reconfigure(encoding="utf-8")

from agents.gap_coach import (
    _MAX_GAPS,
    _build_gap_report,
    _build_missing_index,
    _clip_days,
    _select_and_sort_gaps,
    _validate_input,
)
from schemas.gap import GapCoachEvidence, GapItemEvidence
from schemas.jd import JDAnalysis
from schemas.match import MatchResult


def _assert_equal(actual, expected, name):
    if actual != expected:
        raise AssertionError(f"{name}: 期望 {expected!r},实际 {actual!r}")


def _assert_true(cond, name):
    if not cond:
        raise AssertionError(f"{name}: 期望为真,实际为假")


def _make_evidence(skill: str, days: int = 5) -> GapItemEvidence:
    """构造一条 LLM 侧的 evidence,内容都用占位符,只关心结构。"""
    return GapItemEvidence(
        skill=skill,
        why_it_matters=f"{skill} 对岗位重要。",
        learn_path=f"学习 {skill} 的路径。",
        estimated_days=days,
        interview_questions=[f"关于 {skill} 的问题 1", f"关于 {skill} 的问题 2"],
    )


def _make_match_result(
    hard_missing=None,
    soft_missing=None,
    bonus_missing=None,
) -> MatchResult:
    """构造一个只填缺失项的最小 MatchResult。"""
    return MatchResult(
        total_score=60.0,
        hard_skills_score=50.0,
        soft_skills_score=70.0,
        bonus_points_score=80.0,
        hit_hard_skills=[],
        missing_hard_skills=hard_missing or [],
        hit_soft_skills=[],
        missing_soft_skills=soft_missing or [],
        hit_bonus_points=[],
        missing_bonus_points=bonus_missing or [],
        assessment="占位总评。",
    )


# ---------- Test cases ----------


def test_priority_assignment_by_category():
    """硬技能 -> high, 软技能 -> medium, 加分项 -> low。"""
    match = _make_match_result(
        hard_missing=["LangGraph"],
        soft_missing=["跨团队协作"],
        bonus_missing=["Docker"],
    )
    priority_map, _ = _build_missing_index(match)
    _assert_equal(priority_map["LangGraph"], "high", "硬技能应为 high")
    _assert_equal(priority_map["跨团队协作"], "medium", "软技能应为 medium")
    _assert_equal(priority_map["Docker"], "low", "加分项应为 low")


def test_sorting_by_priority_then_original_order():
    """排序: high > medium > low, 同类内按 MatchResult 原始顺序稳定排序。"""
    match = _make_match_result(
        hard_missing=["A_硬1", "B_硬2"],
        soft_missing=["C_软1"],
        bonus_missing=["D_加1", "E_加2"],
    )
    priority_map, order_map = _build_missing_index(match)
    # 故意乱序输入,验证排序结果与输入顺序无关。
    evidence_list = [
        _make_evidence("D_加1"),
        _make_evidence("A_硬1"),
        _make_evidence("E_加2"),
        _make_evidence("C_软1"),
        _make_evidence("B_硬2"),
    ]
    items = _select_and_sort_gaps(evidence_list, priority_map, order_map)
    skills_in_order = [g.skill for g in items]
    _assert_equal(
        skills_in_order,
        ["A_硬1", "B_硬2", "C_软1", "D_加1", "E_加2"],
        "排序后应先硬(按原顺序) -> 软 -> 加分(按原顺序)",
    )


def test_top_n_truncation():
    """结果不能超过 _MAX_GAPS 条。"""
    # 构造 _MAX_GAPS + 3 条硬技能缺口
    n = _MAX_GAPS + 3
    hard = [f"skill_{i}" for i in range(n)]
    match = _make_match_result(hard_missing=hard)
    priority_map, order_map = _build_missing_index(match)
    evidence_list = [_make_evidence(s) for s in hard]

    items = _select_and_sort_gaps(evidence_list, priority_map, order_map)
    _assert_equal(len(items), _MAX_GAPS, f"应截断到 top-{_MAX_GAPS}")
    _assert_equal(
        [g.skill for g in items],
        hard[:_MAX_GAPS],
        "截断后应保留原顺序前 N 条",
    )


def test_llm_hallucinated_skill_dropped():
    """LLM 返回了 MatchResult.missing_* 里没有的 skill,必须丢弃。"""
    match = _make_match_result(hard_missing=["LangGraph"])
    priority_map, order_map = _build_missing_index(match)
    evidence_list = [
        _make_evidence("LangGraph"),
        _make_evidence("量子计算"),  # 越权,不在 missing 里
    ]
    items = _select_and_sort_gaps(evidence_list, priority_map, order_map)
    _assert_equal(len(items), 1, "越权项应被丢弃")
    _assert_equal(items[0].skill, "LangGraph", "只保留合法项")


def test_duplicate_skills_deduped():
    """LLM 对同一个 skill 返回多次,只保留第一次。"""
    match = _make_match_result(hard_missing=["LangGraph"])
    priority_map, order_map = _build_missing_index(match)
    evidence_list = [
        _make_evidence("LangGraph", days=5),
        _make_evidence("LangGraph", days=10),
    ]
    items = _select_and_sort_gaps(evidence_list, priority_map, order_map)
    _assert_equal(len(items), 1, "重复 skill 只保留一条")
    _assert_equal(items[0].estimated_days, 5, "保留第一次出现的建议")


def test_clip_days_boundaries():
    """estimated_days 兜底钳位。schema 已限制 1-30,这里再验证一层。"""
    _assert_equal(_clip_days(5), 5, "范围内不变")
    _assert_equal(_clip_days(0), 1, "< 1 钳到 1")
    _assert_equal(_clip_days(-5), 1, "负数钳到 1")
    _assert_equal(_clip_days(30), 30, "边界值 30 不变")
    _assert_equal(_clip_days(100), 30, "> 30 钳到 30")


def test_build_gap_report_end_to_end():
    """完整装配路径: evidence + MatchResult -> GapReport。"""
    match = _make_match_result(
        hard_missing=["LangGraph"],
        soft_missing=["跨团队协作"],
    )
    evidence = GapCoachEvidence(
        gaps=[
            _make_evidence("跨团队协作", days=2),
            _make_evidence("LangGraph", days=6),
        ],
        quick_wins=["  改写 RAG 项目描述  ", "", "改写 RAG 项目描述"],
        overall_strategy="  建议先补 LangGraph。  ",
    )
    report = _build_gap_report(evidence, match)

    # 优先级排序生效: 硬技能应排在软技能之前
    _assert_equal(
        [g.skill for g in report.priority_gaps],
        ["LangGraph", "跨团队协作"],
        "GapReport 应按优先级排序",
    )
    _assert_equal(report.priority_gaps[0].priority, "high", "硬技能 priority 应为 high")
    _assert_equal(report.priority_gaps[1].priority, "medium", "软技能 priority 应为 medium")

    # quick_wins: 去空、去重、去两端空白
    _assert_equal(report.quick_wins, ["改写 RAG 项目描述"], "quick_wins 应去空+去重")

    # overall_strategy 应 strip
    _assert_equal(
        report.overall_strategy, "建议先补 LangGraph。", "overall_strategy 应 strip"
    )


def test_input_validation():
    """非法输入应尽早失败,不消耗 LLM 额度。"""
    match = _make_match_result(hard_missing=["A"])
    jd = JDAnalysis(
        job_title="AI 应用开发工程师",
        hard_skills=["A"],
        soft_skills=[],
        bonus_points=[],
        raw_jd="jd 原文",
    )

    # match_result 类型错
    try:
        _validate_input("not a match result", jd)
    except TypeError:
        pass
    else:
        raise AssertionError("非 MatchResult 应抛 TypeError")

    # jd_analysis 类型错
    try:
        _validate_input(match, "not a jd")
    except TypeError:
        pass
    else:
        raise AssertionError("非 JDAnalysis 应抛 TypeError")

    # job_title 为空
    empty_jd = JDAnalysis(
        job_title="  ", hard_skills=[], soft_skills=[], bonus_points=[], raw_jd="x"
    )
    try:
        _validate_input(match, empty_jd)
    except ValueError:
        pass
    else:
        raise AssertionError("空 job_title 应抛 ValueError")


def main():
    tests = [
        ("优先级:按类别自动分配", test_priority_assignment_by_category),
        ("排序:优先级 + 原始顺序", test_sorting_by_priority_then_original_order),
        ("截断:top-N", test_top_n_truncation),
        ("越权:LLM 幻觉 skill 丢弃", test_llm_hallucinated_skill_dropped),
        ("去重:同 skill 只保留一条", test_duplicate_skills_deduped),
        ("estimated_days 钳位", test_clip_days_boundaries),
        ("装配:evidence -> GapReport", test_build_gap_report_end_to_end),
        ("输入校验", test_input_validation),
    ]

    print(f"共 {len(tests)} 组 Gap Coach 纯逻辑测试")
    passed = 0
    for name, test in tests:
        try:
            test()
        except Exception as e:
            print(f"❌ {name}: {e}")
        else:
            print(f"✅ {name}")
            passed += 1

    print(f"总结: {passed}/{len(tests)} 通过")
    sys.exit(0 if passed == len(tests) else 1)


if __name__ == "__main__":
    main()
