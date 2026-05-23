#!/usr/bin/env python3
"""Render the full Markdown report into a polished PDF.

This script intentionally uses ReportLab instead of browser printing so the
output is stable in restricted local environments. It keeps the PDF close to
the HTML/Markdown content while using larger print-friendly typography and
high-resolution local chart images.
"""

from __future__ import annotations

import html
import re
import sys
from pathlib import Path

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    Image,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
REPORT_MD = ROOT / "report.md"
REPORT_PDF = ROOT / "report.pdf"

NAVY = colors.HexColor("#152B45")
BLUE = colors.HexColor("#1F5D8C")
RED = colors.HexColor("#A23E48")
GREEN = colors.HexColor("#2F6B5F")
GOLD = colors.HexColor("#B3832D")
INK = colors.HexColor("#111827")
GRAY = colors.HexColor("#6B7280")
LIGHT = colors.HexColor("#F5F7FA")
LINE = colors.HexColor("#CBD5E1")
HEADER_BG = colors.HexColor("#E8EEF5")
ROW_ALT = colors.HexColor("#FAFBFC")


def register_fonts() -> tuple[str, str]:
    regular = "/System/Library/Fonts/STHeiti Light.ttc"
    bold = "/System/Library/Fonts/STHeiti Medium.ttc"
    if Path(regular).exists() and Path(bold).exists():
        pdfmetrics.registerFont(TTFont("ReportCJK", regular))
        pdfmetrics.registerFont(TTFont("ReportCJKBold", bold))
        pdfmetrics.registerFontFamily(
            "ReportCJK",
            normal="ReportCJK",
            bold="ReportCJKBold",
            italic="ReportCJK",
            boldItalic="ReportCJKBold",
        )
        return "ReportCJK", "ReportCJKBold"

    # Last-resort built-in CJK font. It is less elegant but keeps Chinese text readable.
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont

    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    return "STSong-Light", "STSong-Light"


FONT_REGULAR, FONT_BOLD = register_fonts()


def clean_text(text: str) -> str:
    return text.replace("<br>", "<br/>").replace("<br />", "<br/>").strip()


def inline_markdown(text: str) -> str:
    text = clean_text(text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = html.escape(text, quote=False)
    text = text.replace("&lt;br/&gt;", "<br/>")
    text = re.sub(
        r"\*\*([^*]+)\*\*",
        lambda m: f'<font name="{FONT_BOLD}">{m.group(1)}</font>',
        text,
    )
    text = re.sub(
        r"`([^`]+)`",
        lambda m: f'<font name="Courier" color="#374151">{html.escape(m.group(1), quote=False)}</font>',
        text,
    )
    return text


def split_table_row(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.replace(r"\|", "|").strip() for cell in re.split(r"(?<!\\)\|", stripped)]


def is_separator_row(cells: list[str]) -> bool:
    return all(re.fullmatch(r":?-{3,}:?", cell.strip()) for cell in cells)


def extract_key_numbers(markdown: str) -> list[tuple[str, str, str, colors.Color]]:
    def find(pattern: str, default: str) -> str:
        match = re.search(pattern, markdown)
        return match.group(1) if match else default

    sample = find(r"保留 2025-05 至 2026-04 的 ([0-9]+) 条推荐", "818")
    alpha = find(r"平均相对行业指数超额收益为 ([+\-0-9.]+%)", "+1.53%")
    cyb = find(r"创业板指累计收益 \+?([0-9.]+%)", "88.76%")
    beat = find(r"只有 ([0-9]+) 家券商组合跑赢创业板指", "1")
    top10 = find(r"Top10 抱团股占全部推荐记录? ([0-9.]+%)", "18.7%")
    cr3 = find(r"三大行业合计占 ([0-9.]+%)", "62.5%")
    return [
        ("样本规模", f"{sample} 条", "严格 12 个月口径", BLUE),
        ("行业超额", alpha, "平均相对行业指数", GREEN),
        ("强基准", f"+{cyb}", "创业板指同期累计收益", RED),
        ("跑赢创业板", f"{beat}/6 家", "只有少数金股组合胜出", BLUE),
        ("抱团推荐", top10, "Top10 股票推荐占比", GOLD),
        ("行业集中", cr3, "信息技术、工业、材料", RED),
    ]


def build_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "cover_title": ParagraphStyle(
            "cover_title",
            parent=base["Title"],
            fontName=FONT_BOLD,
            fontSize=24,
            leading=31,
            textColor=NAVY,
            alignment=TA_LEFT,
            wordWrap="CJK",
            spaceAfter=8,
        ),
        "cover_subtitle": ParagraphStyle(
            "cover_subtitle",
            parent=base["Normal"],
            fontName=FONT_REGULAR,
            fontSize=12,
            leading=19,
            textColor=GRAY,
            alignment=TA_LEFT,
            wordWrap="CJK",
            spaceAfter=14,
        ),
        "h2": ParagraphStyle(
            "h2",
            parent=base["Heading2"],
            fontName=FONT_BOLD,
            fontSize=16.5,
            leading=24,
            textColor=NAVY,
            wordWrap="CJK",
            keepWithNext=True,
            spaceBefore=10,
            spaceAfter=8,
        ),
        "h3": ParagraphStyle(
            "h3",
            parent=base["Heading3"],
            fontName=FONT_BOLD,
            fontSize=13.2,
            leading=19,
            textColor=BLUE,
            wordWrap="CJK",
            keepWithNext=True,
            spaceBefore=8,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["BodyText"],
            fontName=FONT_REGULAR,
            fontSize=10.9,
            leading=17.4,
            firstLineIndent=0,
            alignment=TA_JUSTIFY,
            textColor=INK,
            wordWrap="CJK",
            spaceAfter=7,
        ),
        "bullet": ParagraphStyle(
            "bullet",
            parent=base["BodyText"],
            fontName=FONT_REGULAR,
            fontSize=10.8,
            leading=17.2,
            leftIndent=15,
            bulletIndent=2,
            textColor=INK,
            wordWrap="CJK",
            spaceAfter=5,
        ),
        "caption": ParagraphStyle(
            "caption",
            parent=base["BodyText"],
            fontName=FONT_REGULAR,
            fontSize=8.6,
            leading=12,
            textColor=GRAY,
            alignment=TA_CENTER,
            wordWrap="CJK",
            spaceAfter=9,
        ),
        "cell": ParagraphStyle(
            "cell",
            parent=base["BodyText"],
            fontName=FONT_REGULAR,
            fontSize=8.2,
            leading=11.5,
            textColor=INK,
            wordWrap="CJK",
        ),
        "cell_small": ParagraphStyle(
            "cell_small",
            parent=base["BodyText"],
            fontName=FONT_REGULAR,
            fontSize=7.5,
            leading=10.5,
            textColor=INK,
            wordWrap="CJK",
        ),
        "cell_header": ParagraphStyle(
            "cell_header",
            parent=base["BodyText"],
            fontName=FONT_BOLD,
            fontSize=8.2,
            leading=11.5,
            textColor=NAVY,
            alignment=TA_CENTER,
            wordWrap="CJK",
        ),
        "card": ParagraphStyle(
            "card",
            parent=base["BodyText"],
            fontName=FONT_REGULAR,
            fontSize=9,
            leading=19,
            textColor=INK,
            alignment=TA_LEFT,
            wordWrap="CJK",
        ),
    }


def make_table(rows: list[list[str]], styles: dict[str, ParagraphStyle], available_width: float) -> Table:
    if not rows:
        return Table([])
    col_count = max(len(row) for row in rows)
    normalized = [row + [""] * (col_count - len(row)) for row in rows]
    body_style = styles["cell_small"] if col_count >= 6 else styles["cell"]
    header_style = styles["cell_header"]

    data = []
    for r, row in enumerate(normalized):
        style = header_style if r == 0 else body_style
        data.append([Paragraph(inline_markdown(cell), style) for cell in row])

    weights = []
    for c in range(col_count):
        max_len = max(len(re.sub(r"<[^>]+>", "", normalized[r][c])) for r in range(len(normalized)))
        weights.append(max(1.0, min(3.5, max_len / 8)))
    total = sum(weights)
    col_widths = [available_width * w / total for w in weights]

    table = Table(data, colWidths=col_widths, repeatRows=1, hAlign="LEFT", splitByRow=True)
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), NAVY),
        ("GRID", (0, 0), (-1, -1), 0.45, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4.5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4.5),
        ("TOPPADDING", (0, 0), (-1, -1), 4.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5),
    ]
    for r in range(1, len(data)):
        if r % 2 == 0:
            commands.append(("BACKGROUND", (0, r), (-1, r), ROW_ALT))
    table.setStyle(TableStyle(commands))
    return table


def make_image(path: Path, alt: str, styles: dict[str, ParagraphStyle], available_width: float):
    if not path.exists():
        return Paragraph(f"图表文件缺失：{html.escape(str(path))}", styles["caption"])
    with PILImage.open(path) as img:
        width, height = img.size
    draw_width = min(available_width, 176 * mm)
    draw_height = draw_width * height / width
    max_height = 118 * mm
    if draw_height > max_height:
        draw_height = max_height
        draw_width = draw_height * width / height
    flow = Image(str(path), width=draw_width, height=draw_height)
    return KeepTogether(
        [
            Spacer(1, 4),
            flow,
            Paragraph(f"图：{inline_markdown(alt)}", styles["caption"]),
        ]
    )


def make_cover(markdown: str, styles: dict[str, ParagraphStyle], available_width: float) -> list:
    cards = extract_key_numbers(markdown)
    card_cells = []
    for i in range(0, len(cards), 3):
        row = []
        for title, value, note, color in cards[i : i + 3]:
            text = (
                f'<font name="{FONT_BOLD}" size="9.5" color="#152B45">{title}</font><br/>'
                f'<font name="{FONT_BOLD}" size="19" color="{color.hexval()}">{value}</font><br/>'
                f'<font size="8.2" color="#6B7280">{note}</font>'
            )
            row.append(Paragraph(text, styles["card"]))
        card_cells.append(row)
    card_table = Table(
        card_cells,
        colWidths=[available_width / 3 - 5] * 3,
        rowHeights=[36 * mm, 36 * mm],
        hAlign="LEFT",
    )
    card_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.55, LINE),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F7FAFC")),
                ("LEFTPADDING", (0, 0), (-1, -1), 9),
                ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return [
        Spacer(1, 24 * mm),
        Paragraph("券商金股是“指路明灯”还是“韭菜指南”？", styles["cover_title"]),
        Paragraph("面向投资者的金股跟投研究报告<br/>研究区间：2025 年 5 月至 2026 年 4 月，严格 12 个月口径", styles["cover_subtitle"]),
        HRFlowable(width="100%", thickness=1.0, color=LINE, spaceBefore=4, spaceAfter=14),
        card_table,
        Spacer(1, 10 * mm),
        Paragraph(
            "本 PDF 采用完整正文排版，与 report.html 使用同一份 report.md 内容；图表以高清本地图片嵌入，字号和行距按研究报告阅读场景重新设置。",
            styles["body"],
        ),
        PageBreak(),
    ]


def parse_markdown(markdown: str, styles: dict[str, ParagraphStyle], available_width: float) -> list:
    story: list = []
    lines = markdown.splitlines()
    i = 0
    started = False
    h2_count = 0

    def flush_paragraph(buffer: list[str]) -> None:
        if not buffer:
            return
        text = " ".join(part.strip() for part in buffer if part.strip())
        if text:
            story.append(Paragraph(inline_markdown(text), styles["body"]))

    paragraph: list[str] = []
    while i < len(lines):
        raw = lines[i].rstrip()
        line = raw.strip()

        if not started:
            if line.startswith("## "):
                started = True
            else:
                i += 1
                continue

        if not line:
            flush_paragraph(paragraph)
            paragraph = []
            i += 1
            continue

        image_match = re.match(r"!\[([^\]]*)\]\(([^)]+)\)", line)
        if image_match:
            flush_paragraph(paragraph)
            paragraph = []
            alt = image_match.group(1) or "图表"
            image_path = ROOT / image_match.group(2)
            story.append(make_image(image_path, alt, styles, available_width))
            i += 1
            continue

        if line.startswith("|"):
            flush_paragraph(paragraph)
            paragraph = []
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i].strip())
                i += 1
            rows = [split_table_row(row) for row in table_lines]
            if len(rows) >= 2 and is_separator_row(rows[1]):
                rows = [rows[0]] + rows[2:]
            story.append(make_table(rows, styles, available_width))
            story.append(Spacer(1, 7))
            continue

        if line.startswith("## "):
            flush_paragraph(paragraph)
            paragraph = []
            h2_count += 1
            if h2_count > 1:
                story.append(PageBreak())
            title = line[3:].strip()
            story.append(Paragraph(inline_markdown(title), styles["h2"]))
            story.append(HRFlowable(width="100%", thickness=0.8, color=LINE, spaceBefore=2, spaceAfter=8))
            i += 1
            continue

        if line.startswith("### "):
            flush_paragraph(paragraph)
            paragraph = []
            story.append(Paragraph(inline_markdown(line[4:].strip()), styles["h3"]))
            i += 1
            continue

        bullet_match = re.match(r"^[-*]\s+(.+)$", line)
        ordered_match = re.match(r"^[0-9]+\.\s+(.+)$", line)
        if bullet_match or ordered_match:
            flush_paragraph(paragraph)
            paragraph = []
            text = bullet_match.group(1) if bullet_match else ordered_match.group(1)
            bullet = "•" if bullet_match else "•"
            story.append(Paragraph(inline_markdown(text), styles["bullet"], bulletText=bullet))
            i += 1
            continue

        paragraph.append(line)
        i += 1

    flush_paragraph(paragraph)
    return story


def draw_page(canvas, doc) -> None:
    canvas.saveState()
    width, height = A4
    canvas.setFillColor(colors.white)
    canvas.rect(0, 0, width, height, stroke=0, fill=1)
    canvas.setFillColor(NAVY)
    canvas.rect(0, height - 7 * mm, width, 2.8 * mm, stroke=0, fill=1)
    if doc.page == 1:
        canvas.setFillColor(RED)
        canvas.rect(doc.leftMargin, height - 43 * mm, 3.5 * mm, 22 * mm, stroke=0, fill=1)
        canvas.setFont(FONT_BOLD, 9.5)
        canvas.setFillColor(GRAY)
        canvas.drawString(doc.leftMargin, 14 * mm, "资料来源：六大券商金股数据、AkShare、申万行业指数；作者整理")
    else:
        canvas.setFont(FONT_BOLD, 9.2)
        canvas.setFillColor(NAVY)
        canvas.drawString(doc.leftMargin, height - 13 * mm, "券商金股研究报告")
        canvas.setFont(FONT_REGULAR, 8.0)
        canvas.setFillColor(GRAY)
        canvas.drawRightString(width - doc.rightMargin, height - 13 * mm, "2025-05 至 2026-04")
        canvas.setStrokeColor(colors.HexColor("#E5E7EB"))
        canvas.setLineWidth(0.5)
        canvas.line(doc.leftMargin, 16 * mm, width - doc.rightMargin, 16 * mm)
        canvas.setFont(FONT_REGULAR, 7.6)
        canvas.setFillColor(GRAY)
        canvas.drawString(doc.leftMargin, 10 * mm, "资料来源：六大券商金股数据、AkShare、申万行业指数；作者整理")
        canvas.drawRightString(width - doc.rightMargin, 10 * mm, str(doc.page))
    canvas.restoreState()


def render(markdown_path: Path = REPORT_MD, output_path: Path = REPORT_PDF) -> None:
    markdown = markdown_path.read_text(encoding="utf-8")
    page_width, page_height = A4
    margin_left = 16 * mm
    margin_right = 16 * mm
    margin_top = 22 * mm
    margin_bottom = 20 * mm
    frame = Frame(
        margin_left,
        margin_bottom,
        page_width - margin_left - margin_right,
        page_height - margin_top - margin_bottom,
        id="normal",
    )
    doc = BaseDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=margin_left,
        rightMargin=margin_right,
        topMargin=margin_top,
        bottomMargin=margin_bottom,
        title="券商金股分析报告",
        author="数据分析第二次小组作业",
    )
    doc.addPageTemplates([PageTemplate(id="report", frames=[frame], onPage=draw_page)])
    styles = build_styles()
    story = make_cover(markdown, styles, frame.width)
    story.extend(parse_markdown(markdown, styles, frame.width))
    doc.build(story)


if __name__ == "__main__":
    md = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else REPORT_MD
    out = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else REPORT_PDF
    render(md, out)
