"""Word template renderer: replace {{placeholders}} in .docx templates with generated content,
preserving original formatting (font, size, alignment, east-asian fonts)."""

import re
import os
from typing import Optional
from copy import deepcopy
from docx import Document as DocxDocument
from docx.shared import Pt, Cm, Mm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn


PLACEHOLDER_PATTERN = re.compile(r"\{\{(\w+)\}\}")

# Public document format constants (from 集团公文标准与格式.docx)
FONT_TITLE = "方正小标宋_GBK"
FONT_BODY = "方正仿宋_GBK"
FONT_H1 = "方正黑体_GBK"
FONT_H2 = "方正楷体_GBK"

SIZE_TITLE = Pt(22)      # 2号 = 22pt
SIZE_BODY = Pt(16)       # 3号 = 16pt
LINE_SPACING = Pt(30)   # 固定值30磅


class TemplateRenderer:
    """Render generated content into a Word document by replacing placeholders in a template."""

    def __init__(self, template_path: str):
        self.template_path = template_path
        if template_path and os.path.exists(template_path):
            self.doc = DocxDocument(template_path)
        else:
            self.doc = None

    def _replace_in_runs(self, paragraph, replacements: dict) -> str:
        """Replace {{placeholder}} patterns in a paragraph's runs, preserving run formatting."""
        full_text = "".join(r.text for r in paragraph.runs)
        if "{{" not in full_text:
            return full_text

        def replacer(m):
            key = m.group(1)
            return replacements.get(key, m.group(0))

        new_text = PLACEHOLDER_PATTERN.sub(replacer, full_text)

        # Write back to first run, clear the rest
        if paragraph.runs:
            paragraph.runs[0].text = new_text
            for r in paragraph.runs[1:]:
                r.text = ""
        return new_text

    def _replace_multi_paragraph(self, paragraph, content: str, replacements: dict):
        """Handle multi-paragraph placeholders (e.g., {{事由段落}} that expands to multiple paragraphs)."""
        full_text = "".join(r.text for r in paragraph.runs)
        match = PLACEHOLDER_PATTERN.search(full_text)
        if not match:
            return

        key = match.group(1)
        if key not in replacements:
            return

        value = replacements[key]
        # If value contains multiple paragraphs (newlines), split and insert
        paragraphs = value.split("\n")
        paragraphs = [p for p in paragraphs if p.strip()]

        if len(paragraphs) <= 1:
            # Single paragraph: replace in-place
            new_text = full_text.replace(match.group(0), value)
            if paragraph.runs:
                paragraph.runs[0].text = new_text
                for r in paragraph.runs[1:]:
                    r.text = ""
        else:
            # First paragraph: replace placeholder, keep template style
            new_text = full_text.replace(match.group(0), paragraphs[0])
            if paragraph.runs:
                paragraph.runs[0].text = new_text
                for r in paragraph.runs[1:]:
                    r.text = ""

            # Insert additional paragraphs after current one, inheriting style
            current_element = paragraph._element
            for i, ptext in enumerate(paragraphs[1:], 1):
                new_para = deepcopy(current_element)
                current_element.addnext(new_para)
                current_element = new_para
                # Set text in the new paragraph
                from docx.text.paragraph import Paragraph
                new_paragraph = Paragraph(new_para, paragraph._parent)
                if new_paragraph.runs:
                    new_paragraph.runs[0].text = ptext
                    for r in new_paragraph.runs[1:]:
                        r.text = ""
                else:
                    new_paragraph.add_run(ptext)

    def render(self, replacements: dict, output_path: str) -> str:
        """Replace all {{placeholders}} in the template and save to output_path."""
        if not self.doc:
            # No template: generate default document
            return self._create_default_document(replacements, output_path)

        # Process all paragraphs (including those in tables)
        all_paragraphs = list(self.doc.paragraphs)
        for table in self.doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    all_paragraphs.extend(cell.paragraphs)

        for para in all_paragraphs:
            full_text = "".join(r.text for r in para.runs)
            if "{{" not in full_text:
                continue
            # Check if it's a multi-paragraph placeholder
            match = PLACEHOLDER_PATTERN.search(full_text)
            if match:
                key = match.group(1)
                if key in replacements and "\n" in str(replacements.get(key, "")):
                    self._replace_multi_paragraph(para, str(replacements[key]), replacements)
                else:
                    self._replace_in_runs(para, replacements)

        self.doc.save(output_path)
        return output_path

    def _create_default_document(self, replacements: dict, output_path: str) -> str:
        """Create a default public document from scratch with proper formatting."""
        from docx import Document
        from docx.shared import Mm as MmShared

        doc = Document()

        # Page setup: A4, margins top=37mm bottom=35mm left=28mm right=26mm
        section = doc.sections[0]
        section.page_width = MmShared(210)
        section.page_height = MmShared(297)
        section.top_margin = MmShared(37)
        section.bottom_margin = MmShared(35)
        section.left_margin = MmShared(28)
        section.right_margin = MmShared(26)
        section.header_distance = MmShared(20)
        section.footer_distance = MmShared(20)

        def _set_font(run, font_name, font_size, bold=False):
            run.font.name = font_name
            run.font.size = font_size
            run.font.bold = bold
            rpr = run._element.get_or_add_rPr()
            rfonts = rpr.find(qn("w:rFonts"))
            if rfonts is None:
                from docx.oxml import OxmlElement
                rfonts = OxmlElement("w:rFonts")
                rpr.insert(0, rfonts)
            rfonts.set(qn("w:eastAsia"), font_name)

        # Title (方正小标宋_GBK, 2号, centered)
        title_text = replacements.get("标题", replacements.get("title", ""))
        if title_text:
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            pf = p.paragraph_format
            pf.line_spacing = Pt(30)
            pf.line_spacing_rule = 4  # WD_LINE_SPACING.EXACTLY
            run = p.add_run(title_text)
            _set_font(run, FONT_TITLE, SIZE_TITLE, bold=False)

        # Empty line
        doc.add_paragraph()

        # Recipient line
        recipient = replacements.get("主送机关", "公司领导：")
        p = doc.add_paragraph()
        pf = p.paragraph_format
        pf.line_spacing = Pt(30)
        pf.line_spacing_rule = 4
        run = p.add_run(recipient)
        _set_font(run, FONT_BODY, SIZE_BODY)

        # Body paragraphs
        body_fields = [
            ("事由段落", "事由"),
            ("依据段落", "依据"),
            ("请示事项段落", "请示事项"),
        ]
        for placeholder_key, label in body_fields:
            content = replacements.get(placeholder_key, "")
            if not content:
                continue
            for line in content.split("\n"):
                if not line.strip():
                    continue
                p = doc.add_paragraph()
                pf = p.paragraph_format
                pf.line_spacing = Pt(30)
                pf.line_spacing_rule = 4
                pf.first_line_indent = MmShared(32)  # 2 chars indent
                run = p.add_run(line)
                _set_font(run, FONT_BODY, SIZE_BODY)

        # Closing
        p = doc.add_paragraph()
        pf = p.paragraph_format
        pf.line_spacing = Pt(30)
        pf.line_spacing_rule = 4
        pf.first_line_indent = MmShared(32)
        run = p.add_run("妥否，请批示。")
        _set_font(run, FONT_BODY, SIZE_BODY)

        # Department and date
        doc.add_paragraph()
        dept = replacements.get("起草部门", "")
        date = replacements.get("日期", "")
        if dept:
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            pf = p.paragraph_format
            pf.line_spacing = Pt(30)
            pf.line_spacing_rule = 4
            run = p.add_run(dept)
            _set_font(run, FONT_BODY, SIZE_BODY)
        if date:
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            pf = p.paragraph_format
            pf.line_spacing = Pt(30)
            pf.line_spacing_rule = 4
            run = p.add_run(date)
            _set_font(run, FONT_BODY, SIZE_BODY)

        # Sign-off section (签发人/联系人/电话)
        signer = replacements.get("签发人", "")
        contact = replacements.get("联系人", "")
        phone = replacements.get("联系电话", "")
        if signer or contact or phone:
            doc.add_paragraph()
            p = doc.add_paragraph()
            pf = p.paragraph_format
            pf.line_spacing = Pt(30)
            pf.line_spacing_rule = 4
            parts = []
            if signer:
                parts.append(f"签发人：{signer}")
            if contact:
                parts.append(f"联系人：{contact}")
            if phone:
                parts.append(f"联系电话：{phone}")
            run = p.add_run("  ".join(parts))
            _set_font(run, FONT_BODY, SIZE_BODY)

        doc.save(output_path)
        return output_path


def extract_placeholders(template_path: str) -> list[str]:
    """Extract all {{placeholder}} names from a .docx template."""
    if not os.path.exists(template_path):
        return []
    doc = DocxDocument(template_path)
    placeholders = set()
    all_text = []

    for para in doc.paragraphs:
        all_text.append(para.text)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    all_text.append(para.text)

    for text in all_text:
        for m in PLACEHOLDER_PATTERN.finditer(text):
            placeholders.add(m.group(1))

    return sorted(placeholders)
