#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""仓库 Markdown → Word（课程交付 / 评审用）。三份实训课文档共用这一条导出链。

为什么不用 pandoc / LibreOffice：本机 WSL 没装；且它们对中文字体与表格的控制不如
python-docx 直接可控（宋体/黑体 eastAsia 双设、表格字号、题注居中、分页）。

用法：
    # SRS（md 里自带图片引用）
    python3 build_docx.py ../../需求规格说明书.md -o /tmp/srs.docx

    # UML 建模（md 里是 mermaid，用已生成的 PNG 顶替，按出现顺序一一对应）
    python3 build_docx.py ../../UML建模.md -o /tmp/uml.docx \
        --mermaid-figures fig-4-1-context.png,fig-5-1-usecase-main.png,fig-5-2-usecase-settings.png

约定：**Markdown 是正文真源**，Word/PDF 只是导出件；改了 docx 不会回流到 md。
"""
from __future__ import annotations

import argparse
import os
import re
import sys

SKILL_SCRIPTS = "/home/abird/.agents/skills/word-skill/scripts"
sys.path.insert(0, SKILL_SCRIPTS)

from docx import Document  # noqa: E402
from docx.enum.table import WD_TABLE_ALIGNMENT  # noqa: E402
from docx.enum.text import WD_ALIGN_PARAGRAPH  # noqa: E402
from docx.shared import Pt, RGBColor  # noqa: E402
from docx.shared import Cm  # noqa: E402
from docx_utils import (  # noqa: E402
    PageSpec,
    clean_heading_style,
    save_document,
    set_cell_shading,
    set_cjk_font,
    setup_document_styles,
)

HERE = os.path.dirname(os.path.abspath(__file__))
IMAGE_WIDTH_CM = 15.9          # 正文宽 16.6cm（左右边距 2.2cm），留一点余量
CAPTION_RE = re.compile(r"^图 \d+-\d+")
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def strip_inline(text: str) -> str:
    """去掉行内 Markdown 标记（Word 里不支持 ** 语法，留着会显示成星号）。"""
    text = LINK_RE.sub(r"\1", text)
    text = text.replace("**", "").replace("``", "").replace("`", "")
    text = re.sub(r"(?<=\S)\*(?=\S)", "", text)
    return text.strip()


def is_table_sep(line: str) -> bool:
    return bool(re.match(r"^\|[\s:\-|]+\|$", line.strip()))


def parse_table(lines, i):
    raw = []
    while i < len(lines) and lines[i].strip().startswith("|"):
        raw.append(lines[i].strip())
        i += 1
    rows = [[c.strip() for c in ln.strip("|").split("|")] for ln in raw if not is_table_sep(ln)]
    if not rows:
        return None, i
    header, body = rows[0], rows[1:]
    ncol = len(header)
    body = [r + [""] * (ncol - len(r)) if len(r) < ncol else r[:ncol] for r in body]
    return {"type": "table", "header": [strip_inline(c) for c in header],
            "rows": [[strip_inline(c) for c in r] for r in body],
            "shade_header": "DCE6F5"}, i


def md_to_blocks(md_text, md_dir, mermaid_figs=()):
    lines = md_text.split("\n")
    blocks, i = [], 0
    fence_lang, fence_buf, in_fence = None, [], False
    pending_list = None
    fig_iter = iter(mermaid_figs)

    def flush():
        nonlocal pending_list
        if pending_list:
            kind, items = pending_list
            blocks.append({"type": "bullet_list" if kind == "bullet" else "number_list",
                           "items": items})
            pending_list = None

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("```"):
            if not in_fence:
                in_fence, fence_lang, fence_buf = True, stripped[3:].strip().lower(), []
            else:
                in_fence = False
                if fence_lang == "mermaid":
                    # mermaid 在 Word 里没法渲染：用同一目录下已生成的 PNG 顶替
                    name = next(fig_iter, None)
                    path = os.path.join(HERE, name) if name else None
                    if path and os.path.exists(path):
                        blocks.append({"type": "image", "path": path,
                                       "width_cm": IMAGE_WIDTH_CM, "align": "center"})
                    elif mermaid_figs:
                        print(f"[警告] mermaid 缺少对应 PNG：{name}", file=sys.stderr)
                else:
                    # ASCII 流程图之类的代码块：保留等宽文本（字号已在后处理里调小）
                    for ln in fence_buf:
                        if ln.strip():
                            blocks.append({"type": "paragraph", "text": ln.rstrip(),
                                           "indent": False, "code": True})
            i += 1
            continue
        if in_fence:
            fence_buf.append(line)
            i += 1
            continue

        if not stripped:
            flush()
            i += 1
            continue

        m = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)$", stripped)
        if m:
            flush()
            path = os.path.join(md_dir, m.group(2))
            if os.path.exists(path):
                blocks.append({"type": "image", "path": path,
                               "width_cm": IMAGE_WIDTH_CM, "align": "center"})
            else:
                print(f"[警告] 图片不存在，已跳过：{path}", file=sys.stderr)
            i += 1
            continue

        if stripped.startswith("|"):
            flush()
            block, i = parse_table(lines, i)
            if block:
                blocks.append(block)
            continue

        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            flush()
            level = len(m.group(1)) - 1          # # → 标题(0)，## → Heading 1
            blocks.append({"type": "heading", "level": level,
                           "text": strip_inline(m.group(2)),
                           "page_break": level == 1})   # 每章另起一页
            i += 1
            continue

        if re.match(r"^-{3,}$", stripped):
            flush()
            i += 1
            continue

        if stripped.startswith(">"):
            flush()
            text = strip_inline(stripped.lstrip(">").strip())
            if text:
                blocks.append({"type": "paragraph", "text": text, "indent": False})
            i += 1
            continue

        m = re.match(r"^[-*]\s+(.*)$", stripped)
        if m:
            if not pending_list or pending_list[0] != "bullet":
                flush()
                pending_list = ("bullet", [])
            pending_list[1].append(strip_inline(m.group(1)))
            i += 1
            continue

        m = re.match(r"^(\d+)\.\s+(.*)$", stripped)
        if m:
            # 有序列表保留原编号写成普通段落：Word 的 List Number 会在多个列表之间连续编号，
            # 导致每个用例的流程步骤编号错乱（1,2,3 → 7,8,9）。
            flush()
            blocks.append({"type": "paragraph", "indent": False,
                           "text": f"{m.group(1)}. {strip_inline(m.group(2))}"})
            i += 1
            continue

        flush()
        blocks.append({"type": "paragraph", "text": strip_inline(stripped), "indent": True})
        i += 1

    flush()
    return blocks


def render(doc: Document, blocks) -> None:
    """按 block 列表渲染（自渲染版：page_break 走 page_break_before，不插空段落）。"""
    for b in blocks:
        t = b["type"]
        if t == "heading":
            h = doc.add_heading(b["text"], level=b["level"])
            if b["level"] == 0:
                h.alignment = WD_ALIGN_PARAGRAPH.CENTER
            if b.get("page_break"):
                h.paragraph_format.page_break_before = True
        elif t == "paragraph":
            p = doc.add_paragraph(b["text"])
            if b.get("indent", False):
                p.paragraph_format.first_line_indent = Pt(24)
        elif t == "bullet_list":
            for item in b["items"]:
                doc.add_paragraph(item, style="List Bullet")
        elif t == "table":
            header, rows = b["header"], b["rows"]
            table = doc.add_table(rows=len(rows) + 1, cols=len(header), style="Table Grid")
            for j, text in enumerate(header):
                table.rows[0].cells[j].text = str(text)
                set_cell_shading(table.rows[0].cells[j], b.get("shade_header", "DCE6F5"))
            for i, row in enumerate(rows, start=1):
                for j, text in enumerate(row):
                    table.rows[i].cells[j].text = str(text)
        elif t == "image":
            doc.add_picture(b["path"], width=Cm(b.get("width_cm", IMAGE_WIDTH_CM)))
            doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        else:
            raise ValueError(f"未知 block：{t}")


def post_process(doc: Document) -> None:
    """题注居中、表格字体、标题 4 中文字体、插图与题注同页。"""
    style = doc.styles["Heading 4"]
    set_cjk_font(style, "黑体", "Arial")
    clean_heading_style(style)

    for para in doc.paragraphs:
        text = para.text.strip()
        if para._p.findall(".//{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}inline"):
            para.paragraph_format.keep_with_next = True     # 图与题注不分页
            para.paragraph_format.space_after = Pt(4)
        if CAPTION_RE.match(text):
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            para.paragraph_format.space_after = Pt(10)
            for run in para.runs:
                run.font.size = Pt(10)
                run.font.bold = False
                run.font.color.rgb = RGBColor(0x44, 0x44, 0x44)
        if re.match(r"^[─│┌┐└┘├┤┬┴┼▼▲←→─]{2,}", text) or "│" in text:
            # ASCII 流程图：缩小字号让它别折行
            para.paragraph_format.line_spacing = 1.0
            for run in para.runs:
                run.font.size = Pt(7)

    for table in doc.tables:
        table.style = "Table Grid"
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.autofit = True
        for r_i, row in enumerate(table.rows):
            for cell in row.cells:
                for para in cell.paragraphs:
                    para.paragraph_format.line_spacing = 1.15
                    para.paragraph_format.space_after = Pt(0)
                    for run in para.runs:
                        run.font.size = Pt(9)
                        if r_i == 0:
                            run.font.bold = True


def main() -> int:
    ap = argparse.ArgumentParser(description="仓库 Markdown → Word")
    ap.add_argument("md", help="输入 Markdown 路径")
    ap.add_argument("-o", "--output", required=True, help="输出 .docx 路径")
    ap.add_argument("--mermaid-figures", default="",
                    help="逗号分隔的 PNG 文件名（相对 assets/srs/），按 mermaid 出现顺序替换")
    args = ap.parse_args()

    md_path = os.path.abspath(args.md)
    figs = [f.strip() for f in args.mermaid_figures.split(",") if f.strip()]
    blocks = md_to_blocks(open(md_path, encoding="utf-8").read(),
                          os.path.dirname(md_path), figs)

    doc = Document()
    # 左右边距 2.2cm → 正文宽 16.6cm，恰好容纳 15.9cm 宽的插图（1:1，不缩放字号）
    setup_document_styles(doc, PageSpec(top_cm=2.4, bottom_cm=2.4, left_cm=2.2, right_cm=2.2))
    render(doc, blocks)
    post_process(doc)

    if os.path.exists(args.output):
        os.remove(args.output)
    out = save_document(doc, args.output)
    print(f"[完成] {out}（段落 {len(doc.paragraphs)}，表格 {len(doc.tables)}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
