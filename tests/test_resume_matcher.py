"""
Resume Matcher 端到端测试。

实际调用 LLM,验证 JD 文本 -> JDAnalysis -> MatchResult 的完整链路。

跑法:
  cd D:\\jobhunter-agent
  .\\venv\\Scripts\\activate
  python -m tests.test_resume_matcher
"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from agents.jd_analyzer import analyze_jd
from agents.resume_matcher import match_resume


ROOT_DIR = Path(__file__).parent.parent


def _category_is_complete(requirements, hits, missing):
    return (
        len(hits) + len(missing) == len({item.casefold() for item in requirements})
        and not ({item.casefold() for item in hits} & {item.casefold() for item in missing})
    )


def run_one(resume_path: Path, jd_analysis) -> bool:
    print("\n" + "=" * 60)
    print(f"📄 测试简历: {resume_path.name}")
    print("=" * 60)

    resume_text = resume_path.read_text(encoding="utf-8")
    try:
        result = match_resume(resume_text, jd_analysis)
    except Exception as e:
        print(f"❌ 调用失败: {e}")
        return False

    expected_total = round(
        result.hard_skills_score * 0.7
        + result.soft_skills_score * 0.2
        + result.bonus_points_score * 0.1,
        1,
    )
    checks = {
        "总分在 0-100": 0 <= result.total_score <= 100,
        "三个分项分均在 0-100": all(
            0 <= score <= 100
            for score in (
                result.hard_skills_score,
                result.soft_skills_score,
                result.bonus_points_score,
            )
        ),
        "总分可按 70/20/10 复算": result.total_score == expected_total,
        "硬技能命中/缺失完整互斥": _category_is_complete(
            jd_analysis.hard_skills,
            result.hit_hard_skills,
            result.missing_hard_skills,
        ),
        "软技能命中/缺失完整互斥": _category_is_complete(
            jd_analysis.soft_skills,
            result.hit_soft_skills,
            result.missing_soft_skills,
        ),
        "加分项命中/缺失完整互斥": _category_is_complete(
            jd_analysis.bonus_points,
            result.hit_bonus_points,
            result.missing_bonus_points,
        ),
        "总评非空": bool(result.assessment.strip()),
    }

    print(f"总分: {result.total_score}")
    print(
        f"分项: 硬技能 {result.hard_skills_score} / "
        f"软技能 {result.soft_skills_score} / 加分项 {result.bonus_points_score}"
    )
    print(f"命中硬技能: {result.hit_hard_skills}")
    print(f"缺失硬技能: {result.missing_hard_skills}")
    print(f"总评: {result.assessment}")

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
