"""
Resume Parser: PDF 简历 -> 干净的简历文本。

设计原则:
- 只做 PDF 文本提取和轻量清洗,不做任何语义理解。
- 语义匹配继续交给 Resume Matcher(LLM + Python 规则)。
- 对各种"劣质 PDF"给出明确、可捕获的异常,方便上层 UI 展示。

对外只暴露两个函数:
- extract_resume_text(pdf_path): 底层文本提取
- match_resume_from_pdf(pdf_path, jd_analysis): 端到端便捷入口
"""
import re
from pathlib import Path
from typing import Union

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from agents.resume_matcher import match_resume
from schemas.jd import JDAnalysis
from schemas.match import MatchResult


# 加密 / 扫描 / 空文件都是"技术上能打开但拿不到有效文本"的常见情况,
# 单独抛出让 UI 能给出更精确的提示,而不是一律报"解析失败"。
class ResumeParseError(Exception):
    """PDF 简历解析失败的基类异常。"""


class EncryptedPDFError(ResumeParseError):
    """PDF 已加密且无法自动解密。"""


class EmptyResumeError(ResumeParseError):
    """PDF 中提取不到任何可用文本(扫描版 / 空文件 / 全图片版)。"""


# 简历最小长度阈值,低于该长度基本可以判定为扫描版或异常 PDF。
# 取 30 是经验值:典型简历首行"姓名 + 求职方向"就已超过。
_MIN_MEANINGFUL_TEXT_LENGTH = 30


def _clean_text(text: str) -> str:
    """轻量清洗 PDF 提取出的原始文本。

    规则:
    - 归一化换行符;
    - 合并 3 个及以上连续换行为 2 个,保留段落分隔;
    - 每行两端去空白,过滤纯空白行;
    - 全局去除行首尾多余空格。

    不做:
    - 语义清洗(错别字、简历段落识别都留给下游);
    - 去除中文之间的空格(有些 PDF 排版会插入,但这里保留原样,
      让 LLM 自行判断即可,避免误删)。
    """
    if not text:
        return ""

    # 统一换行符,避免 Windows/Mac 差异
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")

    # 逐行清理:去掉纯空白行的多余空白
    lines = [line.strip() for line in normalized.split("\n")]

    # 合并 3+ 连续空行为 1 个空行(保留段落感)
    cleaned_lines = []
    blank_streak = 0
    for line in lines:
        if line == "":
            blank_streak += 1
            if blank_streak <= 1:
                cleaned_lines.append("")
        else:
            blank_streak = 0
            # 把行内多个连续空白压成 1 个空格,避免 PDF 排版残留
            cleaned_lines.append(re.sub(r"[ \t]+", " ", line))

    return "\n".join(cleaned_lines).strip()


def _validate_pdf_path(pdf_path: Union[str, Path]) -> Path:
    """归一化并校验 PDF 路径,尽早失败。"""
    if pdf_path is None:
        raise TypeError("pdf_path 不能为 None")
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF 文件不存在: {path}")
    if not path.is_file():
        raise ValueError(f"路径不是文件: {path}")
    if path.suffix.lower() != ".pdf":
        # 不强行拒绝,只警告式提示;pypdf 会在读取时报错
        # 保留为 ValueError 以便调用方可捕获
        raise ValueError(f"文件扩展名不是 .pdf: {path.name}")
    return path


def extract_resume_text(pdf_path: Union[str, Path]) -> str:
    """从 PDF 简历中提取干净的纯文本。

    参数:
        pdf_path: PDF 文件路径(str 或 Path)

    返回:
        清洗后的简历文本

    异常:
        FileNotFoundError: 文件不存在
        ValueError: 路径不是文件 / 不是 .pdf
        EncryptedPDFError: PDF 已加密且无法解密
        EmptyResumeError: 提取不到有效文本(扫描版 / 图片版 / 空 PDF)
        ResumeParseError: 其他 PDF 结构损坏的情况
    """
    path = _validate_pdf_path(pdf_path)

    try:
        reader = PdfReader(str(path))
    except PdfReadError as e:
        raise ResumeParseError(f"PDF 结构损坏,无法解析: {e}") from e

    # 加密 PDF:尝试用空口令解密(很多"仅设置权限"的 PDF 用空口令即可),
    # 失败就抛专用异常,让 UI 提示用户去除密码保护。
    if reader.is_encrypted:
        try:
            unlocked = reader.decrypt("")
        except Exception as e:
            raise EncryptedPDFError(f"PDF 已加密且无法自动解密: {e}") from e
        if not unlocked:
            raise EncryptedPDFError("PDF 已加密,请先在原软件中去掉密码保护再上传")

    # 逐页提取,单页失败不影响整体
    page_texts = []
    for index, page in enumerate(reader.pages):
        try:
            page_text = page.extract_text() or ""
        except Exception:
            # 单页解析失败不致命,继续尝试后续页
            page_text = ""
        if page_text.strip():
            page_texts.append(page_text)

    cleaned = _clean_text("\n\n".join(page_texts))

    # 扫描版 PDF / 图片版 PDF / 全空 PDF 都会走到这里
    if len(cleaned) < _MIN_MEANINGFUL_TEXT_LENGTH:
        raise EmptyResumeError(
            "PDF 中未提取到足够的文本,可能是扫描版或图片版简历,"
            "请改用文字版 PDF 或先在 Word 中另存为 PDF"
        )

    return cleaned


def match_resume_from_pdf(
    pdf_path: Union[str, Path], jd_analysis: JDAnalysis
) -> MatchResult:
    """端到端便捷入口: PDF 路径 + JDAnalysis -> MatchResult。

    只是把 extract_resume_text 和 match_resume 串起来。
    单元测试仍应针对两个环节分别测试,避免耦合。
    """
    resume_text = extract_resume_text(pdf_path)
    return match_resume(resume_text, jd_analysis)


if __name__ == "__main__":
    # 命令行直接跑:python -m agents.resume_parser <pdf_path>
    import sys

    sys.stdout.reconfigure(encoding="utf-8")

    if len(sys.argv) < 2:
        print("用法: python -m agents.resume_parser <resume.pdf>")
        sys.exit(1)

    try:
        text = extract_resume_text(sys.argv[1])
    except ResumeParseError as e:
        print(f"❌ 解析失败: {e}")
        sys.exit(1)

    print("=" * 50)
    print(f"提取到 {len(text)} 字符")
    print("-" * 50)
    print(text)
    print("=" * 50)
