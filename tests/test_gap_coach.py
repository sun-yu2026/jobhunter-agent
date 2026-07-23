"""
Gap Coach 端到端测试。

实际调用 LLM,验证 JD -> JDAnalysis -> MatchResult -> GapReport 的完整链路。
门槛: 需要 .env 中配置好 ARK_API_KEY / LLM_BASE_URL / LLM_MODEL。

跑法:
  cd D:\\jobhunter-agent
  .\\venv\\Scripts\\activate
  python -m tests.test_gap_coach
"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from agents.gap_coach import _MAX_GAPS, coach_gaps
from agents.jd_analyzer import analyze_jd
from agents.resume_matcher import match_resume


ROOT_DIR = Path(__file__).parent.parent


def _all_gaps_from_missing(report, match) -> bool:
    """Coach 生成的每个 gap.skill 都必须来自 MatchResult.missing_*。"""
    missing_pool = set(
        match.missing_hard_skills
        + match.missing_soft_skills
        + match.missing_bonus_points
    )
    return all(gap.skill in missing_pool for gap in report.priority_gaps)


def _priority_matches_category(report, match) -> bool:
    """每个 gap 的 priority 必须与其归属的类别一致。"""
    hard = set(match.missing_hard_skills)
    soft = set(match.missing_soft_skills)
    bonus = set(match.missing_bonus_points)
    for gap in report.priority_gaps:
        if gap.skill in hard and gap.priority != "high":
            return False
        if gap.skill in soft and gap.priority != "medium":
            return False
        if gap.skill in bonus and gap.priority != "low":
            return False
    return True


def _sorted_by_priority(report) -> bool:
    """priority_gaps 应先 high 后 medium 后 low。"""
    rank = {"high": 0, "medium": 1, "low": 2}
    ranks = [rank[g.priority] for g in report.priority_gaps]
    return ranks == sorted(ranks)


def _no_duplicate_skills(report) -> bool:
    """priority_gaps 内不能有同名 skill。"""
    skills = [g.skill for g in report.priority_gaps]
    return len(skills) == len(set(skills))


def run_one(resume_path: Path, jd_analysis) -> bool:
    print("\n" + "=" * 60)
    print(f"📄 测试简历: {resume_path.name}")
    print("=" * 60)

    resume_text = resume_path.read_text(encoding="utf-8")

    try:
        match = match_resume(resume_text, jd_analysis)
        report = coach_gaps(match, jd_analysis)
    except Exception as e:
        print(f"❌ 调用失败: {e}")
        return False

    # 若 match 完全没有 missing,这份简历不需要 Coach —— 直接算通过。
    total_missing = (
        len(match.missing_hard_skills)
        + len(match.missing_soft_skills)
        + len(match.missing_bonus_points)
    )
    if total_missing == 0:
        print("(该简历无任何缺口,跳过 Coach 校验,直接通过)")
        return True

    checks = {
        f"gap 数量 <= {_MAX_GAPS}": len(report.priority_gaps) <= _MAX_GAPS,
        "所有 gap.skill 来自 missing_*": _all_gaps_from_missing(report, match),
        "priority 与类别一致": _priority_matches_category(report, match),
        "按 priority 排序": _sorted_by_priority(report),
        "priority_gaps 无重复 skill": _no_duplicate_skills(report),
        "每个 gap.estimated_days 在 1-30": all(
            1 <= g.estimated_days <= 30 for g in report.priority_gaps
        ),
        "overall_strategy 非空": bool(report.overall_strategy.strip()),
    }

    print(f"共 {len(report.priority_gaps)} 条 priority_gaps:")
    for i, gap in enumerate(report.priority_gaps, 1):
        qs = " / ".join(gap.interview_questions[:2])
        print(f"  [{i}] [{gap.priority}] {gap.skill} (~{gap.estimated_days}d)  Q: {qs}")
    print(f"quick_wins ({len(report.quick_wins)} 条):")
    for w in report.quick_wins:
        print(f"  - {w}")
    print(f"overall_strategy: {report.overall_strategy}")

    all_ok = True
    for name, ok in checks.items():
        print(f"  {'✅' if ok else '❌'} {name}")
        all_ok = all_ok and ok
    return all_ok


def main():
    jd_path = ROOT_DIR / "data" / "jd_samples" / "sample_01_placeholder.txt"
    resume_dir = ROOT_DIR / "data" / "resume_samples"
    samples = sorted(resume_dir.glob("*.txt"))

    if not jd_path.exists():
        print(f"❌ 没找到 JD 样本: {jd_path}")
        sys.exit(1)
    if not samples:
        print(f"❌ 没找到简历样本: {resume_dir}")
        sys.exit(1)

    print(f"正在解析上游 JD: {jd_path.name}")
    try:
        jd_analysis = analyze_jd(jd_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"❌ JD Analyzer 调用失败: {e}")
        sys.exit(1)

    print(f"岗位: {jd_analysis.job_title};共 {len(samples)} 份简历待测")
    results = [run_one(path, jd_analysis) for path in samples]

    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"总结: {passed}/{total} 通过")
    print("=" * 60)
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
