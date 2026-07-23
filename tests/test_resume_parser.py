"""
Resume Parser 的纯逻辑测试。

不调用 LLM API,只验证 PDF -> 文本 的提取和清洗环节。
测试用的 PDF 在 tests 目录下由 reportlab 现场生成,不写入仓库。

跑法:
  cd D:\\jobhunter-agent
  .\\venv\\Scripts\\python.exe -m tests.test_resume_parser
"""
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

from agents.resume_parser import (
    EmptyResumeError,
    EncryptedPDFError,
    ResumeParseError,
    _clean_text,
    extract_resume_text,
)


def _make_text_pdf(pdf_path: Path, lines):
    """生成一份有可提取文本的 PDF。用英文避免字体缺失。"""
    c = canvas.Canvas(str(pdf_path), pagesize=A4)
    y = 800
    for line in lines:
        c.drawString(50, y, line)
        y -= 20
    c.save()


def _make_empty_pdf(pdf_path: Path):
    """生成一份完全没有文字对象的 PDF,模拟扫描版/图片版。"""
    c = canvas.Canvas(str(pdf_path), pagesize=A4)
    # 什么都不画,直接 showPage + save,得到一份"空白 PDF"
    c.showPage()
    c.save()


def _make_encrypted_pdf(pdf_path: Path, owner_password: str, user_password: str):
    """生成一份加密 PDF。"""
    from reportlab.lib import pdfencrypt

    enc = pdfencrypt.StandardEncryption(
        userPassword=user_password,
        ownerPassword=owner_password,
        canPrint=0,
        canModify=0,
    )
    c = canvas.Canvas(str(pdf_path), pagesize=A4, encrypt=enc)
    c.drawString(50, 800, "This resume should not be readable without password.")
    c.save()


def _assert_equal(actual, expected, name):
    if actual != expected:
        raise AssertionError(f"{name}: 期望 {expected!r},实际 {actual!r}")


def _assert_true(cond, name):
    if not cond:
        raise AssertionError(f"{name}: 期望为真,实际为假")


def test_clean_text_collapses_blank_lines():
    raw = "line1\n\n\n\nline2\n   \n   \nline3"
    cleaned = _clean_text(raw)
    _assert_equal(
        cleaned,
        "line1\n\nline2\n\nline3",
        "3+ 空行被压成 1 个空行",
    )


def test_clean_text_normalizes_windows_newlines():
    raw = "line1\r\nline2\r\n\r\nline3"
    cleaned = _clean_text(raw)
    _assert_equal(
        cleaned,
        "line1\nline2\n\nline3",
        "\\r\\n 被归一化为 \\n",
    )


def test_clean_text_collapses_inline_whitespace():
    raw = "A   B\t\tC     D"
    cleaned = _clean_text(raw)
    _assert_equal(cleaned, "A B C D", "行内多空白被压成单空格")


def test_extract_text_from_normal_pdf():
    with tempfile.TemporaryDirectory() as td:
        pdf_path = Path(td) / "resume.pdf"
        _make_text_pdf(
            pdf_path,
            [
                "Name: Test Candidate",
                "Objective: AI Application Developer",
                "Skills: Python, FastAPI, LangChain, RAG, Vector Database",
                "Projects: Enterprise RAG QA system using Chroma and LangGraph.",
            ],
        )
        text = extract_resume_text(pdf_path)
        _assert_true("Python" in text, "关键字 Python 应被提取")
        _assert_true("LangChain" in text, "关键字 LangChain 应被提取")
        _assert_true(len(text) >= 30, "提取长度足够大")


def test_empty_pdf_raises_empty_resume_error():
    with tempfile.TemporaryDirectory() as td:
        pdf_path = Path(td) / "blank.pdf"
        _make_empty_pdf(pdf_path)
        try:
            extract_resume_text(pdf_path)
        except EmptyResumeError:
            return
        raise AssertionError("空 PDF 应抛出 EmptyResumeError")


def test_missing_file_raises_file_not_found():
    try:
        extract_resume_text(Path("D:/definitely/does/not/exist.pdf"))
    except FileNotFoundError:
        return
    raise AssertionError("不存在的文件应抛出 FileNotFoundError")


def test_wrong_extension_raises_value_error():
    with tempfile.TemporaryDirectory() as td:
        txt_path = Path(td) / "resume.txt"
        txt_path.write_text("not a pdf", encoding="utf-8")
        try:
            extract_resume_text(txt_path)
        except ValueError:
            return
        raise AssertionError(".txt 后缀应抛出 ValueError")


def test_encrypted_pdf_raises_encrypted_error():
    with tempfile.TemporaryDirectory() as td:
        pdf_path = Path(td) / "encrypted.pdf"
        _make_encrypted_pdf(pdf_path, owner_password="owner", user_password="user")
        try:
            extract_resume_text(pdf_path)
        except EncryptedPDFError:
            return
        except ResumeParseError as e:
            # 某些 reportlab/pypdf 版本组合下会退化成通用 ResumeParseError,
            # 只要不是静默返回错文本即可
            print(f"  (加密测试触发了 ResumeParseError: {e})")
            return
        raise AssertionError("加密 PDF 应抛出 EncryptedPDFError 或 ResumeParseError")


def test_directory_path_raises_value_error():
    with tempfile.TemporaryDirectory() as td:
        try:
            extract_resume_text(td)
        except ValueError:
            return
        raise AssertionError("传入目录应抛出 ValueError")


def main():
    tests = [
        ("清洗:压缩多空行", test_clean_text_collapses_blank_lines),
        ("清洗:归一化 CRLF", test_clean_text_normalizes_windows_newlines),
        ("清洗:压缩行内空白", test_clean_text_collapses_inline_whitespace),
        ("提取:正常 PDF", test_extract_text_from_normal_pdf),
        ("异常:空/扫描 PDF", test_empty_pdf_raises_empty_resume_error),
        ("异常:文件不存在", test_missing_file_raises_file_not_found),
        ("异常:非 PDF 扩展名", test_wrong_extension_raises_value_error),
        ("异常:加密 PDF", test_encrypted_pdf_raises_encrypted_error),
        ("异常:传入目录", test_directory_path_raises_value_error),
    ]

    print(f"共 {len(tests)} 组 PDF 解析测试")
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
