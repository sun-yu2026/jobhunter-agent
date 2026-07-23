"""
Resume Matcher 的纯逻辑测试。

不调用 LLM API,用于验证命中归一化、缺失补全、输入校验和 70/20/10 评分。

跑法:
  cd D:\\jobhunter-agent
  python -m tests.test_resume_matcher_logic
"""
import sys

sys.stdout.reconfigure(encoding="utf-8")

from agents.resume_matcher import (
    _build_match_result,
    _compute_category_score,
    _compute_total_score,
    _normalize_hits,
    _validate_input,
)
from schemas.jd import JDAnalysis
from schemas.match import ResumeMatchEvidence


def _assert_equal(actual, expected, name):
    if actual != expected:
        raise AssertionError(f"{name}: 期望 {expected!r},实际 {actual!r}")


def test_score_formula():
    _assert_equal(_compute_total_score(80, 70, 50), 75.0, "70/20/10 公式")
    _assert_equal(_compute_total_score(100, 0, 0), 70.0, "权重边界")
    _assert_equal(_compute_total_score(0, 0, 0), 0.0, "全零边界")
    _assert_equal(_compute_total_score(100, 100, 100), 100.0, "满分边界")
    _assert_equal(_compute_category_score([], []), 100.0, "空类别不扣分")
    _assert_equal(_compute_category_score(["Python"], ["Python", "RAG"]), 50.0, "命中率")


def test_hit_normalization():
    requirements = ["Python", "RAG", "FastAPI", "python", "  "]
    hits = ["rag", "PYTHON", "不存在的技能", "RAG"]
    _assert_equal(
        _normalize_hits(hits, requirements),
        ["Python", "RAG"],
        "合法命中归一化、去重并保持 JD 顺序",
    )


def test_result_completion():
    jd = JDAnalysis(
        job_title="AI 应用开发工程师",
        hard_skills=["Python", "RAG", "FastAPI"],
        soft_skills=["沟通能力"],
        bonus_points=[],
        raw_jd="用于纯逻辑测试的 JD 原文。",
    )
    evidence = ResumeMatchEvidence(
        hit_hard_skills=["rag", "Python", "模型幻觉项"],
        hit_soft_skills=[],
        hit_bonus_points=["不存在的加分项"],
        assessment="具备部分核心技能,仍需补齐接口开发与沟通证据。",
    )

    result = _build_match_result(evidence, jd)

    _assert_equal(result.hit_hard_skills, ["Python", "RAG"], "硬技能命中")
    _assert_equal(result.missing_hard_skills, ["FastAPI"], "硬技能缺失补全")
    _assert_equal(result.hit_soft_skills, [], "软技能命中")
    _assert_equal(result.missing_soft_skills, ["沟通能力"], "软技能缺失补全")
    _assert_equal(result.hit_bonus_points, [], "非法加分命中剔除")
    _assert_equal(result.missing_bonus_points, [], "空加分类别")
    _assert_equal(result.hard_skills_score, 66.7, "硬技能分")
    _assert_equal(result.soft_skills_score, 0.0, "软技能分")
    _assert_equal(result.bonus_points_score, 100.0, "空加分项分")
    _assert_equal(result.total_score, 56.7, "综合分")


def test_input_validation():
    jd = JDAnalysis(
        job_title="测试岗位",
        hard_skills=[],
        soft_skills=[],
        bonus_points=[],
        raw_jd="测试 JD",
    )

    invalid_cases = [
        (lambda: _validate_input("", jd), ValueError),
        (lambda: _validate_input("   ", jd), ValueError),
        (lambda: _validate_input(None, jd), TypeError),
        (lambda: _validate_input("有效简历", None), TypeError),
    ]
    for call, expected_error in invalid_cases:
        try:
            call()
        except expected_error:
            continue
        raise AssertionError(f"输入校验应抛出 {expected_error.__name__}")


def main():
    tests = [
        ("评分公式", test_score_formula),
        ("命中归一化", test_hit_normalization),
        ("结果补全", test_result_completion),
        ("输入校验", test_input_validation),
    ]

    print(f"共 {len(tests)} 组纯逻辑测试")
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
