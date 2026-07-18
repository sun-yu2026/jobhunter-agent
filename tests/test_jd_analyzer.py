"""
JD Analyzer 端到端测试。

不是单元测试,是"跑一遍看输出"的集成测试。
目的:确认 3 份 JD 都能返回合法的 JDAnalysis,且字段非空。

跑法:
  cd D:\\jobhunter-agent
  .\\venv\\Scripts\\activate
  python -m tests.test_jd_analyzer
"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from agents.jd_analyzer import analyze_jd


def run_one(jd_path: Path) -> bool:
    print("\n" + "=" * 60)
    print(f"📄 测试文件: {jd_path.name}")
    print("=" * 60)

    jd_text = jd_path.read_text(encoding="utf-8")
    try:
        result = analyze_jd(jd_text)
    except Exception as e:
        print(f"❌ 调用失败: {e}")
        return False

    print(f"岗位标题     : {result.job_title}")
    print(f"硬技能 ({len(result.hard_skills):2d}): {result.hard_skills}")
    print(f"软技能 ({len(result.soft_skills):2d}): {result.soft_skills}")
    print(f"加分项 ({len(result.bonus_points):2d}): {result.bonus_points}")

    # 最基本的合理性校验
    checks = {
        "岗位标题非空": bool(result.job_title.strip()),
        "至少抽出 1 条硬技能": len(result.hard_skills) >= 1,
        "raw_jd 已保留": len(result.raw_jd) > 50,
    }
    all_ok = True
    for name, ok in checks.items():
        icon = "✅" if ok else "❌"
        print(f"  {icon} {name}")
        all_ok = all_ok and ok
    return all_ok


def main():
    sample_dir = Path(__file__).parent.parent / "data" / "jd_samples"
    samples = sorted(sample_dir.glob("*.txt"))
    if not samples:
        print(f"❌ 没找到 JD 样本,目录: {sample_dir}")
        sys.exit(1)

    print(f"共 {len(samples)} 份 JD 待测")
    results = [run_one(p) for p in samples]

    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"总结: {passed}/{total} 通过")
    print("=" * 60)
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
