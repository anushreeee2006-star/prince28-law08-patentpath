from pathlib import Path

import pymupdf
import pytest

from patentpath.ingest.parse import (
    ParseError,
    clean_text,
    drop_repeated_lines,
    headings_in,
    markup_to_markdown,
    parse_file,
    split_pages,
    with_heading_paths,
)


def test_clean_text_normalizes_and_repairs_text():
    result = clean_text("treat-\nment \x00 fi\u00ad")

    assert result == "treatment fi"


def test_headings_in_ignores_code_blocks():
    text = "# Introduction\n```python\n# Not a heading\n```\n## Details"

    found, in_code = headings_in(text)

    assert found == [(1, "Introduction"), (2, "Details")]
    assert in_code is False


def test_heading_paths_are_preserved_between_pages():
    texts = [
        "# Introduction\nFirst page",
        "Second page",
        "## Details\nThird page",
        "Fourth page",
    ]

    pages = with_heading_paths(texts)

    assert pages[0].headings == []
    assert pages[1].headings == ["Introduction"]
    assert pages[2].headings == ["Introduction"]
    assert pages[3].headings == ["Introduction", "Details"]


def test_split_pages_splits_at_paragraph_boundaries():
    result = split_pages("First paragraph\n\nSecond paragraph\n\nThird", size=25)

    assert len(result) == 2
    assert result[0] == "First paragraph"
    assert result[1] == "Second paragraph\n\nThird"


def test_markup_to_markdown_converts_asciidoc_headings():
    result = markup_to_markdown("= Main Title\n\n== Sub Title", ".adoc")

    assert result == "# Main Title\n\n## Sub Title"


def test_drop_repeated_lines_removes_headers_and_footers():
    pages = [
        "Document Header\nPage 1 line A\nPage 1 main content\nPage 1 line C\nDocument Footer",
        "Document Header\nPage 2 line A\nPage 2 main content\nPage 2 line C\nDocument Footer",
        "Document Header\nPage 3 line A\nPage 3 main content\nPage 3 line C\nDocument Footer",
        "Document Header\nPage 4 line A\nPage 4 main content\nPage 4 line C\nDocument Footer",
    ]

    result = drop_repeated_lines(pages)

    assert all("Document Header" not in page for page in result)
    assert all("Document Footer" not in page for page in result)
    assert "Page 1 main content" in result[0]


def test_parse_file_reads_markdown(tmp_path: Path):
    source = tmp_path / "sample.md"
    source.write_text(
        "# Patent Basics\n\nA patent protects an invention.",
        encoding="utf-8",
    )

    result = parse_file(source)

    assert result.kind == "text"
    assert result.title == "Patent Basics"
    assert len(result.pages) == 1
    assert "# Patent Basics" in result.pages[0].text


def test_parse_file_rejects_unsupported_extension(tmp_path: Path):
    source = tmp_path / "sample.docx"
    source.write_text("Sample content", encoding="utf-8")

    with pytest.raises(ParseError) as error:
        parse_file(source)

    assert error.value.reason == "unsupported_type"


def test_parse_error_limits_detail_length():
    error = ParseError("corrupt", "x" * 600)

    assert error.reason == "corrupt"
    assert len(error.detail) == 500


def test_pdf_parser_preserves_page_numbers_and_heading_paths(tmp_path: Path):
    source = tmp_path / "headings.pdf"
    doc = pymupdf.open()

    page1 = doc.new_page()
    page1.insert_text((72, 72), "Patent Guidelines", fontsize=24)
    page1.insert_text(
        (72, 120),
        "This document explains patent filing requirements and procedures "
        "for student inventors in India.",
        fontsize=11,
    )

    page2 = doc.new_page()
    page2.insert_text(
        (72, 72),
        "This page continues the patent guidelines with additional "
        "information about applications and documentation.",
        fontsize=11,
    )

    doc.save(source)
    doc.close()

    result = parse_file(source)

    assert len(result.pages) == 2
    assert result.pages[0].page_no == 1
    assert result.pages[1].page_no == 2
    assert result.pages[1].headings == ["Patent Guidelines"]


def test_pdf_parser_detects_tables(tmp_path: Path):
    source = tmp_path / "table.pdf"
    doc = pymupdf.open()
    page = doc.new_page()

    page.insert_text(
        (72, 60),
        "Patent information and filing details are provided here "
        + "for student inventors and applicants.",
    )

    for y in (100, 140, 180):
        page.draw_line((72, y), (320, y))

    for x in (72, 196, 320):
        page.draw_line((x, 100), (x, 180))

    page.insert_text((85, 125), "Form")
    page.insert_text((210, 125), "Purpose")
    page.insert_text((85, 165), "Form 1")
    page.insert_text((210, 165), "Application")

    doc.save(source)
    doc.close()

    result = parse_file(source)

    assert result.pages[0].tables >= 1
    assert "Form" in result.pages[0].text


def test_pdf_parser_detects_one_blank_page_among_text_pages(tmp_path: Path):
    source = tmp_path / "mixed-pages.pdf"
    doc = pymupdf.open()

    for number in range(2):
        page = doc.new_page()
        page.insert_text(
            (72, 72),
            f"Page {number + 1}: " + "This page contains enough readable text for extraction. " * 4,
        )

    doc.new_page()
    doc.save(source)
    doc.close()

    for parser in ("pymupdf", "pypdf"):
        result = parse_file(source, pdf_parser=parser)
        assert len(result.pages) == 3
        assert result.scanned_pages == [3]


def test_scanned_pdf_reports_no_text_layer(tmp_path: Path):
    source = tmp_path / "scanned.pdf"
    doc = pymupdf.open()
    doc.new_page()
    doc.save(source)
    doc.close()

    with pytest.raises(ParseError) as error:
        parse_file(source)

    assert error.value.reason == "no_text_layer"


def test_broken_pdf_reports_corrupt(tmp_path: Path):
    source = tmp_path / "broken.pdf"
    source.write_bytes(b"This is not a valid PDF file.")

    for parser in ("pymupdf", "pypdf"):
        with pytest.raises(ParseError) as error:
            parse_file(source, pdf_parser=parser)

        assert error.value.reason in {"corrupt", "crash"}


def test_password_protected_pdf_reports_encrypted(tmp_path: Path):
    source = tmp_path / "encrypted.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Protected patent document.")

    doc.save(
        source,
        encryption=pymupdf.PDF_ENCRYPT_AES_256,
        owner_pw="owner-password",
        user_pw="user-password",
    )
    doc.close()

    for parser in ("pymupdf", "pypdf"):
        with pytest.raises(ParseError) as error:
            parse_file(source, pdf_parser=parser)

        assert error.value.reason == "encrypted"


def test_both_pdf_parsers_agree_on_page_count(tmp_path: Path):
    source = tmp_path / "comparison.pdf"
    doc = pymupdf.open()

    for number in range(2):
        page = doc.new_page()
        page.insert_text(
            (72, 72),
            f"Page {number + 1}: "
            + (
                "This is a sufficiently long paragraph containing "
                "information about patent applications and filing rules. "
            )
            * 3,
        )

    doc.save(source)
    doc.close()

    pymupdf_result = parse_file(source, pdf_parser="pymupdf")
    pypdf_result = parse_file(source, pdf_parser="pypdf")

    assert len(pymupdf_result.pages) == 2
    assert len(pypdf_result.pages) == 2


def test_html_parser_extracts_article_content(tmp_path: Path):
    source = tmp_path / "article.html"

    source.write_text(
        """
        <html>
        <head><title>Patent Guide</title></head>
        <body>
            <nav>Home Menu Contact Navigation</nav>
            <article>
                <h1>Patent Application Guide</h1>
                <p>
                    A patent protects a new invention. Applicants must
                    prepare the required documents and submit an application.
                    The patent office examines the application before granting
                    patent protection under the applicable rules.
                </p>
            </article>
            <footer>Copyright Footer Information</footer>
        </body>
        </html>
        """,
        encoding="utf-8",
    )

    result = parse_file(source)
    combined_text = "\n".join(page.text for page in result.pages)

    assert result.kind == "html"
    assert "Patent Application Guide" in combined_text
    assert "patent" in combined_text.lower()
