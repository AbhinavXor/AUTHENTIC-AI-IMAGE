from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.sax.saxutils import escape

from matplotlib.font_manager import FontProperties, findfont
from PIL import Image as PILImage
from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    CondPageBreak,
    Frame,
    HRFlowable,
    Image,
    KeepTogether,
    ListFlowable,
    ListItem,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Preformatted,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

from artifacts.charting import render_chart_image
from artifacts.equations import (
    EquationRenderingError,
    normalize_math_expression,
    render_equation_image,
)
from artifacts.models import (
    ArtifactDocument,
    ArtifactLayoutBrief,
    BulletListBlock,
    CalloutBlock,
    ChartBlock,
    CodeBlock,
    DiagramBlock,
    EquationBlock,
    PageBreakBlock,
    ParagraphBlock,
    QuoteBlock,
    TableBlock,
)


_ACCENT = colors.HexColor("#147D6D")
_ACCENT_DARK = colors.HexColor("#0C554A")
_ACCENT_LIGHT = colors.HexColor("#EAF5F2")
_INK = colors.HexColor("#162033")
_BODY = colors.HexColor("#344054")
_MUTED = colors.HexColor("#667085")
_LINE = colors.HexColor("#D8E0E8")
_SOFT = colors.HexColor("#F7F9FC")
_WHITE = colors.white


@dataclass(frozen=True, slots=True)
class _VisualTheme:
    accent: colors.Color
    accent_dark: colors.Color
    accent_light: colors.Color
    ink: colors.Color
    body: colors.Color
    muted: colors.Color
    line: colors.Color
    soft: colors.Color


def _hex(value: str) -> colors.Color:
    return colors.HexColor(value)


_VISUAL_THEMES: dict[str, _VisualTheme] = {
    "minimal_academic": _VisualTheme(_hex("#315A85"), _hex("#1F3B5C"), _hex("#EEF4FA"), _hex("#182230"), _hex("#344054"), _hex("#667085"), _hex("#D7E0EA"), _hex("#F8FAFC")),
    "classic_university": _VisualTheme(_hex("#B18A3D"), _hex("#243B64"), _hex("#F7F1E4"), _hex("#18243B"), _hex("#39465E"), _hex("#6F7785"), _hex("#D9D3C5"), _hex("#FBF9F4")),
    "modern_engineering": _VisualTheme(_hex("#0F9A8A"), _hex("#123B52"), _hex("#E7F7F4"), _hex("#122033"), _hex("#33485B"), _hex("#667786"), _hex("#CFDDE4"), _hex("#F5F9FA")),
    "technical_grid": _VisualTheme(_hex("#1DA1B8"), _hex("#172554"), _hex("#E8F7FA"), _hex("#111B35"), _hex("#35415C"), _hex("#69748B"), _hex("#CBD8E8"), _hex("#F4F8FC")),
    "formal_research": _VisualTheme(_hex("#8E3B46"), _hex("#562832"), _hex("#F8ECEE"), _hex("#251D20"), _hex("#493E42"), _hex("#766A6E"), _hex("#DED2D5"), _hex("#FBF8F8")),
    "data_rich_analytical": _VisualTheme(_hex("#2878C8"), _hex("#164A7B"), _hex("#EAF3FC"), _hex("#14263B"), _hex("#334C65"), _hex("#667D91"), _hex("#CDDDEA"), _hex("#F4F8FC")),
    "visual_learning": _VisualTheme(_hex("#7559C7"), _hex("#49358C"), _hex("#F0ECFC"), _hex("#211A36"), _hex("#443B59"), _hex("#756C88"), _hex("#DDD5F0"), _hex("#F9F7FD")),
    "code_first_technical": _VisualTheme(_hex("#16A7A0"), _hex("#202938"), _hex("#E7F7F6"), _hex("#101828"), _hex("#344054"), _hex("#667085"), _hex("#CBD5E1"), _hex("#F1F5F9")),
    "print_optimized_monochrome": _VisualTheme(_hex("#555555"), _hex("#111111"), _hex("#EEEEEE"), _hex("#111111"), _hex("#333333"), _hex("#666666"), _hex("#C8C8C8"), _hex("#F5F5F5")),
    "accessible_reading": _VisualTheme(_hex("#167A5A"), _hex("#153B67"), _hex("#E9F5EF"), _hex("#101C2C"), _hex("#2E4057"), _hex("#5D6E82"), _hex("#CCD8E4"), _hex("#F5F8FB")),
}


def _theme(brief: ArtifactLayoutBrief | None) -> _VisualTheme:
    visual_system = (
        brief.visual_system
        if brief is not None
        else "accessible_reading"
    )
    return _VISUAL_THEMES.get(
        visual_system,
        _VISUAL_THEMES["accessible_reading"],
    )


def _safe(value: str) -> str:
    return escape(value.strip()).replace("\n", "<br/>")


def _register_fonts() -> dict[str, str]:
    names = {
        "regular": "Helvetica",
        "bold": "Helvetica-Bold",
        "italic": "Helvetica-Oblique",
        "mono": "Courier",
        "serif": "Times-Roman",
        "serif_bold": "Times-Bold",
    }
    try:
        paths = {
            "regular": findfont(
                FontProperties(family="DejaVu Sans", weight="normal"),
                fallback_to_default=False,
            ),
            "bold": findfont(
                FontProperties(family="DejaVu Sans", weight="bold"),
                fallback_to_default=False,
            ),
            "italic": findfont(
                FontProperties(family="DejaVu Sans", style="italic"),
                fallback_to_default=False,
            ),
            "mono": findfont(
                FontProperties(family="DejaVu Sans Mono", weight="normal"),
                fallback_to_default=False,
            ),
            "serif": findfont(
                FontProperties(family="DejaVu Serif", weight="normal"),
                fallback_to_default=False,
            ),
            "serif_bold": findfont(
                FontProperties(family="DejaVu Serif", weight="bold"),
                fallback_to_default=False,
            ),
        }
        registered = {
            "regular": "AuthenticSans",
            "bold": "AuthenticSans-Bold",
            "italic": "AuthenticSans-Italic",
            "mono": "AuthenticMono",
            "serif": "AuthenticSerif",
            "serif_bold": "AuthenticSerif-Bold",
        }
        for key, font_name in registered.items():
            if font_name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(font_name, paths[key]))
        names = registered
    except Exception:
        pass
    return names


def _styles(
    fonts: dict[str, str],
    brief: ArtifactLayoutBrief | None = None,
) -> dict[str, ParagraphStyle]:
    sample = getSampleStyleSheet()
    theme = _theme(brief)
    family = brief.family if brief is not None else "modern_summary"
    density = brief.visual_density if brief is not None else "balanced"
    editorial_family = family in {
        "academic_textbook",
        "research_paper",
        "case_study",
    } or (brief is not None and brief.visual_system in {
        "classic_university",
        "formal_research",
        "minimal_academic",
    })
    body_font = fonts["serif"] if editorial_family else fonts["regular"]
    title_font = fonts["serif_bold"] if editorial_family else fonts["bold"]
    body_size = {
        "compact": 9.35,
        "balanced": 10.0,
        "spacious": 10.45,
    }[density]
    body_leading = {
        "compact": 13.7,
        "balanced": 15.0,
        "spacious": 16.1,
    }[density]
    title_size = {
        "academic_textbook": 28.5,
        "research_paper": 27.0,
        "executive_report": 27.5,
        "technical_spec": 25.5,
        "proposal_document": 28.0,
        "data_report": 27.0,
        "case_study": 29.0,
        "modern_summary": 29.0,
    }[family]
    return {
        "eyebrow": ParagraphStyle(
            "ArtifactEyebrow",
            parent=sample["Normal"],
            fontName=fonts["bold"],
            fontSize=8.4,
            leading=11,
            alignment=TA_LEFT,
            textColor=theme.accent_dark,
            tracking=1.35,
            spaceAfter=10,
            keepWithNext=1,
        ),
        "title": ParagraphStyle(
            "ArtifactTitle",
            parent=sample["Title"],
            fontName=title_font,
            fontSize=title_size,
            leading=35,
            alignment=TA_LEFT,
            textColor=theme.ink,
            spaceAfter=13,
        ),
        "subtitle": ParagraphStyle(
            "ArtifactSubtitle",
            parent=sample["Normal"],
            fontName=fonts["regular"],
            fontSize=11.2,
            leading=16.5,
            alignment=TA_LEFT,
            textColor=theme.muted,
            spaceAfter=14,
        ),
        "metadata": ParagraphStyle(
            "ArtifactMetadata",
            parent=sample["Normal"],
            fontName=fonts["regular"],
            fontSize=8.6,
            leading=12.5,
            alignment=TA_LEFT,
            textColor=theme.muted,
        ),
        "part": ParagraphStyle(
            "ArtifactPart",
            parent=sample["Heading1"],
            fontName=fonts["bold"],
            fontSize=17.5,
            leading=22,
            textColor=_WHITE,
            backColor=theme.accent_dark,
            borderColor=theme.accent_dark,
            borderWidth=0,
            borderPadding=(10, 12, 10, 12),
            spaceBefore=14,
            spaceAfter=9,
            keepWithNext=1,
        ),
        "h1": ParagraphStyle(
            "ArtifactHeading1",
            parent=sample["Heading1"],
            fontName=fonts["serif_bold"],
            fontSize=18.5,
            leading=23,
            textColor=theme.ink,
            spaceBefore=17,
            spaceAfter=8,
            keepWithNext=1,
        ),
        "h2": ParagraphStyle(
            "ArtifactHeading2",
            parent=sample["Heading2"],
            fontName=fonts["bold"],
            fontSize=13.6,
            leading=17.5,
            textColor=theme.accent_dark,
            spaceBefore=13,
            spaceAfter=6,
            keepWithNext=1,
        ),
        "h3": ParagraphStyle(
            "ArtifactHeading3",
            parent=sample["Heading3"],
            fontName=fonts["bold"],
            fontSize=10.6,
            leading=14,
            textColor=colors.HexColor("#475467"),
            spaceBefore=8,
            spaceAfter=4,
            keepWithNext=1,
        ),
        "body": ParagraphStyle(
            "ArtifactBody",
            parent=sample["BodyText"],
            fontName=body_font,
            fontSize=body_size,
            leading=body_leading,
            alignment=TA_LEFT,
            textColor=theme.body,
            splitLongWords=0,
            spaceAfter=7.5,
            allowWidows=0,
            allowOrphans=0,
        ),
        "list_body": ParagraphStyle(
            "ArtifactListBody",
            parent=sample["BodyText"],
            fontName=body_font,
            fontSize=max(8.9, body_size - 0.1),
            leading=max(13.2, body_leading - 0.3),
            textColor=theme.body,
            splitLongWords=0,
            spaceAfter=2,
        ),
        "table_body": ParagraphStyle(
            "ArtifactTableBody",
            parent=sample["BodyText"],
            fontName=fonts["regular"],
            fontSize=8.25,
            leading=11.2,
            alignment=TA_LEFT,
            textColor=theme.body,
            splitLongWords=0,
            wordWrap="LTR",
        ),
        "table_header": ParagraphStyle(
            "ArtifactTableHeader",
            parent=sample["BodyText"],
            fontName=fonts["bold"],
            fontSize=8.25,
            leading=11.2,
            alignment=TA_LEFT,
            textColor=_WHITE,
            splitLongWords=0,
            wordWrap="LTR",
        ),
        "caption": ParagraphStyle(
            "ArtifactCaption",
            parent=sample["Normal"],
            fontName=fonts["italic"],
            fontSize=8.15,
            leading=11.6,
            alignment=TA_LEFT,
            textColor=theme.muted,
            spaceBefore=4,
            spaceAfter=10,
        ),
        "figure_label": ParagraphStyle(
            "ArtifactFigureLabel",
            parent=sample["Normal"],
            fontName=fonts["bold"],
            fontSize=7.9,
            leading=10.5,
            alignment=TA_LEFT,
            textColor=theme.accent_dark,
            tracking=0.45,
            spaceBefore=2,
            spaceAfter=2,
        ),
        "quote": ParagraphStyle(
            "ArtifactQuote",
            parent=sample["BodyText"],
            fontName=body_font,
            fontSize=body_size,
            leading=body_leading,
            leftIndent=12,
            rightIndent=8,
            borderColor=theme.accent,
            borderWidth=1.7,
            borderPadding=9,
            textColor=colors.HexColor("#34423D"),
            backColor=colors.HexColor("#F2F8F6"),
            spaceBefore=5,
            spaceAfter=9,
        ),
        "callout_title": ParagraphStyle(
            "ArtifactCalloutTitle",
            parent=sample["Normal"],
            fontName=fonts["bold"],
            fontSize=8.7,
            leading=11.5,
            textColor=theme.ink,
        ),
        "callout_body": ParagraphStyle(
            "ArtifactCalloutBody",
            parent=sample["BodyText"],
            fontName=body_font,
            fontSize=max(8.9, body_size - 0.35),
            leading=max(13.0, body_leading - 0.5),
            textColor=theme.body,
        ),
        "equation_fallback": ParagraphStyle(
            "ArtifactEquationFallback",
            parent=sample["BodyText"],
            fontName=fonts["mono"],
            fontSize=9.2,
            leading=13.5,
            alignment=TA_CENTER,
            textColor=theme.ink,
            backColor=theme.soft,
            borderColor=theme.line,
            borderWidth=0.5,
            borderPadding=7,
            spaceBefore=5,
            spaceAfter=8,
        ),
        "equation_label": ParagraphStyle(
            "ArtifactEquationLabel",
            parent=sample["Normal"],
            fontName=fonts["regular"],
            fontSize=7.8,
            leading=10,
            alignment=TA_RIGHT,
            textColor=theme.muted,
        ),
        "code": ParagraphStyle(
            "ArtifactCode",
            parent=sample["Code"],
            fontName=fonts["mono"],
            fontSize=7.9,
            leading=10.8,
            leftIndent=7,
            rightIndent=7,
            borderWidth=0.5,
            borderColor=theme.line,
            borderPadding=7,
            backColor=theme.soft,
            spaceBefore=5,
            spaceAfter=9,
        ),
    }


class _Template(BaseDocTemplate):
    def __init__(
        self,
        filename: str,
        *,
        document_title: str,
        author: str | None,
        fonts: dict[str, str],
        layout_brief: ArtifactLayoutBrief,
    ) -> None:
        self.document_title = document_title
        self.document_author = author
        self.fonts = fonts
        self.layout_brief = layout_brief
        self.visual_theme = _theme(layout_brief)
        self.current_section = document_title
        self._outline_has_level_zero = False
        super().__init__(
            filename,
            pagesize=A4,
            leftMargin=18 * mm,
            rightMargin=18 * mm,
            topMargin=21 * mm,
            bottomMargin=18 * mm,
            title=document_title,
            author=author or "",
            subject="Structured professional document",
            keywords=(
                f"{layout_brief.family}, structured document, professional PDF"
            ),
        )
        portrait_frame = Frame(
            self.leftMargin,
            self.bottomMargin,
            self.width,
            self.height,
            id="portrait-content",
        )
        landscape_size = landscape(A4)
        landscape_frame = Frame(
            self.leftMargin,
            self.bottomMargin,
            landscape_size[0] - self.leftMargin - self.rightMargin,
            landscape_size[1] - self.topMargin - self.bottomMargin,
            id="landscape-content",
        )
        self.addPageTemplates(
            [
                PageTemplate(
                    id="portrait",
                    frames=[portrait_frame],
                    onPage=self._draw_page,
                    pagesize=A4,
                ),
                PageTemplate(
                    id="landscape",
                    frames=[landscape_frame],
                    onPage=self._draw_page,
                    pagesize=landscape_size,
                ),
            ]
        )

    @property
    def landscape_width(self) -> float:
        page_width, _ = landscape(A4)
        return page_width - self.leftMargin - self.rightMargin

    def beforeDocument(self) -> None:
        self._outline_has_level_zero = False
        self.current_section = self.document_title

    def _draw_cover_decoration(self, canvas, width: float, height: float) -> None:
        family = self.layout_brief.family
        visual = self.layout_brief.visual_system
        theme = self.visual_theme
        canvas.setStrokeColor(theme.accent)
        canvas.setFillColor(theme.accent)

        if visual == "modern_engineering":
            canvas.setFillColor(theme.accent_dark)
            canvas.rect(0, height - 13 * mm, width, 13 * mm, fill=1, stroke=0)
            canvas.setFillColor(theme.accent)
            canvas.rect(0, 0, 7 * mm, height - 13 * mm, fill=1, stroke=0)
            canvas.setFillColor(theme.accent_light)
            canvas.rect(width - 38 * mm, 0, 38 * mm, 14 * mm, fill=1, stroke=0)
            return
        if visual == "technical_grid":
            canvas.setFillColor(theme.accent_dark)
            canvas.rect(0, height - 18 * mm, width, 18 * mm, fill=1, stroke=0)
            canvas.setStrokeColor(theme.accent_light)
            canvas.setLineWidth(0.35)
            for offset in range(0, 42, 7):
                canvas.line(width - (offset + 7) * mm, 0, width - (offset + 7) * mm, height)
            canvas.setFillColor(theme.accent)
            canvas.rect(width - 42 * mm, 0, 42 * mm, 18 * mm, fill=1, stroke=0)
            return
        if visual == "classic_university":
            canvas.setStrokeColor(theme.accent_dark)
            canvas.setLineWidth(1.1)
            canvas.rect(10 * mm, 10 * mm, width - 20 * mm, height - 20 * mm, fill=0, stroke=1)
            canvas.setStrokeColor(theme.accent)
            canvas.setLineWidth(0.5)
            canvas.rect(13 * mm, 13 * mm, width - 26 * mm, height - 26 * mm, fill=0, stroke=1)
            canvas.setFillColor(theme.accent)
            canvas.rect(10 * mm, height - 15 * mm, width - 20 * mm, 5 * mm, fill=1, stroke=0)
            return
        if visual == "minimal_academic":
            canvas.setFillColor(theme.accent_dark)
            canvas.rect(13 * mm, 0, 2.2 * mm, height, fill=1, stroke=0)
            canvas.setStrokeColor(theme.accent)
            canvas.setLineWidth(0.7)
            canvas.line(22 * mm, height - 20 * mm, width - 18 * mm, height - 20 * mm)
            return
        if visual == "formal_research":
            canvas.setFillColor(theme.accent_dark)
            canvas.rect(0, height - 7 * mm, width, 7 * mm, fill=1, stroke=0)
            canvas.setFillColor(theme.accent)
            canvas.rect(0, 0, width, 2.5 * mm, fill=1, stroke=0)
            return
        if visual == "data_rich_analytical":
            canvas.setFillColor(theme.accent_dark)
            canvas.rect(0, height - 12 * mm, width, 12 * mm, fill=1, stroke=0)
            canvas.setFillColor(theme.accent)
            for index, bar_height in enumerate((12, 22, 34, 49)):
                canvas.rect(width - (46 - index * 9) * mm, 0, 6 * mm, bar_height * mm, fill=1, stroke=0)
            return
        if visual == "visual_learning":
            canvas.setFillColor(theme.accent_light)
            for radius, x, y in ((34, width - 18 * mm, height - 18 * mm), (20, width - 12 * mm, 16 * mm), (12, 18 * mm, 13 * mm)):
                canvas.circle(x, y, radius * mm / 4, fill=1, stroke=0)
            canvas.setFillColor(theme.accent)
            canvas.rect(0, height - 4 * mm, width, 4 * mm, fill=1, stroke=0)
            return
        if visual == "code_first_technical":
            canvas.setFillColor(theme.accent_dark)
            canvas.rect(0, 0, 14 * mm, height, fill=1, stroke=0)
            canvas.setFillColor(theme.accent)
            canvas.rect(14 * mm, height - 8 * mm, width - 14 * mm, 8 * mm, fill=1, stroke=0)
            canvas.setStrokeColor(theme.accent_light)
            canvas.setLineWidth(1.4)
            canvas.line(width - 31 * mm, 18 * mm, width - 20 * mm, 18 * mm)
            canvas.line(width - 31 * mm, 18 * mm, width - 31 * mm, 31 * mm)
            canvas.line(width - 20 * mm, 18 * mm, width - 20 * mm, 31 * mm)
            return
        if visual == "print_optimized_monochrome":
            canvas.setStrokeColor(theme.accent_dark)
            canvas.setLineWidth(1.4)
            canvas.line(14 * mm, height - 14 * mm, width - 14 * mm, height - 14 * mm)
            canvas.line(14 * mm, 14 * mm, width - 14 * mm, 14 * mm)
            return
        if visual == "accessible_reading":
            canvas.setFillColor(theme.accent_dark)
            canvas.rect(0, height - 9 * mm, width, 9 * mm, fill=1, stroke=0)
            canvas.setFillColor(theme.accent)
            canvas.rect(0, 0, 9 * mm, height, fill=1, stroke=0)
            return

        if family == "executive_report":
            canvas.rect(0, height - 5 * mm, width, 5 * mm, fill=1, stroke=0)
            canvas.setFillColor(theme.accent_light)
            canvas.rect(width - 34 * mm, 0, 34 * mm, 10 * mm, fill=1, stroke=0)
        elif family == "research_paper":
            canvas.setLineWidth(1.2)
            canvas.line(18 * mm, height - 18 * mm, width - 18 * mm, height - 18 * mm)
        elif family == "academic_textbook":
            canvas.setLineWidth(2.2)
            canvas.line(14 * mm, 0, 14 * mm, height)
            canvas.setStrokeColor(theme.accent_light)
            canvas.setLineWidth(0.9)
            canvas.line(19 * mm, 0, 19 * mm, height)
        elif family == "technical_spec":
            canvas.setFillColor(theme.accent_dark)
            canvas.rect(0, height - 10 * mm, width, 10 * mm, fill=1, stroke=0)
            canvas.setFillColor(theme.accent_light)
            canvas.rect(width - 22 * mm, height - 22 * mm, 22 * mm, 12 * mm, fill=1, stroke=0)
        elif family == "proposal_document":
            canvas.setFillColor(theme.accent_dark)
            canvas.rect(0, 0, 8 * mm, height, fill=1, stroke=0)
            canvas.setFillColor(theme.accent_light)
            canvas.rect(8 * mm, height - 7 * mm, width - 8 * mm, 7 * mm, fill=1, stroke=0)
        elif family == "data_report":
            canvas.setFillColor(theme.accent_dark)
            canvas.rect(0, height - 7 * mm, width, 7 * mm, fill=1, stroke=0)
            canvas.setFillColor(theme.accent_light)
            for index in range(4):
                canvas.rect(
                    width - (index + 1) * 9 * mm,
                    0,
                    7 * mm,
                    (index + 1) * 3 * mm,
                    fill=1,
                    stroke=0,
                )
        elif family == "case_study":
            canvas.setFillColor(theme.accent_dark)
            canvas.rect(0, 0, 6 * mm, height, fill=1, stroke=0)
            canvas.setStrokeColor(theme.accent_light)
            canvas.setLineWidth(1.1)
            canvas.line(width - 18 * mm, 14 * mm, width - 18 * mm, height - 14 * mm)
        else:
            canvas.setLineWidth(1.6)
            canvas.line(18 * mm, height - 16 * mm, 65 * mm, height - 16 * mm)

    def _draw_body_decoration(self, canvas, width: float, height: float) -> None:
        visual = self.layout_brief.visual_system
        theme = self.visual_theme
        if visual == "technical_grid":
            canvas.setFillColor(theme.accent_light)
            canvas.rect(width - 7 * mm, 0, 7 * mm, height, fill=1, stroke=0)
            canvas.setFillColor(theme.accent)
            canvas.rect(width - 7 * mm, height - 48 * mm, 7 * mm, 24 * mm, fill=1, stroke=0)
            canvas.setStrokeColor(theme.line)
            canvas.setLineWidth(0.45)
            canvas.line(self.leftMargin, height - 17 * mm, width - self.rightMargin, height - 17 * mm)
        elif visual == "classic_university":
            canvas.setStrokeColor(theme.accent)
            canvas.setLineWidth(0.55)
            canvas.line(12 * mm, 0, 12 * mm, height)
        elif visual == "minimal_academic":
            canvas.setFillColor(theme.accent)
            canvas.rect(0, 0, 2 * mm, height, fill=1, stroke=0)
        elif visual == "formal_research":
            canvas.setFillColor(theme.accent_dark)
            canvas.rect(0, height - 2 * mm, width, 2 * mm, fill=1, stroke=0)
        elif visual == "data_rich_analytical":
            canvas.setFillColor(theme.accent_light)
            canvas.rect(0, 0, 5 * mm, height, fill=1, stroke=0)
        elif visual == "visual_learning":
            canvas.setFillColor(theme.accent_light)
            canvas.circle(width - 7 * mm, height - 18 * mm, 8 * mm, fill=1, stroke=0)
        elif visual == "code_first_technical":
            canvas.setFillColor(theme.accent_dark)
            canvas.rect(0, 0, 4 * mm, height, fill=1, stroke=0)
        elif visual == "print_optimized_monochrome":
            canvas.setStrokeColor(theme.line)
            canvas.setLineWidth(0.45)
            canvas.line(self.leftMargin, height - 16 * mm, width - self.rightMargin, height - 16 * mm)
        elif visual == "accessible_reading":
            canvas.setFillColor(theme.accent)
            canvas.rect(0, height - 3 * mm, width, 3 * mm, fill=1, stroke=0)
        elif visual == "modern_engineering":
            canvas.setFillColor(theme.accent)
            canvas.rect(0, 0, 3 * mm, height, fill=1, stroke=0)

    def _draw_page(self, canvas, document) -> None:
        canvas.saveState()
        width, height = canvas._pagesize
        theme = self.visual_theme
        if document.page == 1:
            self._draw_cover_decoration(canvas, width, height)
        else:
            self._draw_body_decoration(canvas, width, height)
            header_mode = self.layout_brief.header_mode
            if header_mode != "none":
                canvas.setStrokeColor(theme.line)
                canvas.setLineWidth(0.4)
                canvas.line(
                    self.leftMargin,
                    height - 13.8 * mm,
                    width - self.rightMargin,
                    height - 13.8 * mm,
                )
                canvas.setFillColor(theme.muted)
                canvas.setFont(self.fonts["regular"], 7.2)
                header = (
                    self.current_section
                    if header_mode == "running_section"
                    else self.document_title
                )
                if len(header) > 92:
                    header = header[:89].rstrip() + "..."
                canvas.drawString(self.leftMargin, height - 11.2 * mm, header)
                if self.layout_brief.branding_mode == "full":
                    canvas.drawRightString(
                        width - self.rightMargin,
                        height - 11.2 * mm,
                        "Authentic AI",
                    )

        footer_mode = self.layout_brief.footer_mode
        if footer_mode != "none":
            canvas.setFillColor(theme.muted)
            canvas.setFont(self.fonts["regular"], 7.2)
            if footer_mode == "page_number_and_title":
                title = self.document_title
                if len(title) > 54:
                    title = title[:51].rstrip() + "..."
                canvas.drawString(self.leftMargin, 8.5 * mm, title)
            elif self.layout_brief.branding_mode in {"subtle", "full"}:
                canvas.drawString(self.leftMargin, 8.5 * mm, "Authentic AI")
            canvas.drawRightString(
                width - self.rightMargin,
                8.5 * mm,
                f"{document.page}",
            )
        canvas.restoreState()

    def afterFlowable(self, flowable) -> None:
        if not isinstance(flowable, Paragraph):
            return
        style_name = flowable.style.name
        if style_name not in {
            "ArtifactPart",
            "ArtifactHeading1",
            "ArtifactHeading2",
        }:
            return
        text = flowable.getPlainText().strip()
        if text.casefold() in {
            "contents",
            "executive overview",
            "executive summary",
            "learning roadmap",
        }:
            return
        self.current_section = text or self.current_section

        if style_name in {"ArtifactPart", "ArtifactHeading1"}:
            level = 0
        else:
            level = 1 if self._outline_has_level_zero else 0

        if level == 0:
            self._outline_has_level_zero = True
        bookmark = f"heading-{level}-{self.seq.nextf('heading')}"
        self.canv.bookmarkPage(bookmark)
        self.canv.addOutlineEntry(
            text,
            bookmark,
            level=level,
            closed=False,
        )
        self.notify("TOCEntry", (level, text, self.page, bookmark))

def _column_widths(block: TableBlock, width: float) -> list[float]:
    columns = max(len(block.columns), 1)
    scores: list[float] = []
    for index, heading in enumerate(block.columns):
        samples = [heading]
        samples.extend(
            row[index]
            for row in block.rows[:60]
            if index < len(row)
        )
        longest_word = max(
            (
                len(word)
                for value in samples
                for word in value.replace("/", " ").split()
            ),
            default=4,
        )
        average_length = sum(len(value) for value in samples) / max(len(samples), 1)
        scores.append(max(9.0, longest_word * 1.65, min(average_length, 72)))

    total = sum(scores) or columns
    raw = [width * score / total for score in scores]
    minimum = min(32 * mm, width / columns * 0.76)
    adjusted = [max(minimum, value) for value in raw]
    scale = width / sum(adjusted)
    return [value * scale for value in adjusted]


def _is_wide_table(block: TableBlock) -> bool:
    if len(block.columns) >= 6:
        return True
    longest_words = [
        max((len(word) for word in value.replace("/", " ").split()), default=0)
        for value in block.columns
    ]
    for row in block.rows[:30]:
        for index, value in enumerate(row):
            if index >= len(longest_words):
                continue
            longest_words[index] = max(
                longest_words[index],
                max((len(word) for word in value.replace("/", " ").split()), default=0),
            )
    return len(block.columns) >= 5 and sum(longest_words) >= 72


def _table(
    block: TableBlock,
    *,
    styles: dict[str, ParagraphStyle],
    width: float,
    compact: bool = False,
) -> Table:
    body_style = styles["table_body"].clone(
        "ArtifactTableBodyCompact" if compact else "ArtifactTableBodyLocal"
    )
    header_style = styles["table_header"].clone(
        "ArtifactTableHeaderCompact" if compact else "ArtifactTableHeaderLocal"
    )
    if compact:
        body_style.fontSize = min(body_style.fontSize, 7.65)
        body_style.leading = min(body_style.leading, 9.7)
        header_style.fontSize = min(header_style.fontSize, 7.55)
        header_style.leading = min(header_style.leading, 9.5)
    body_style.splitLongWords = 0
    header_style.splitLongWords = 0

    rows = [
        [Paragraph(_safe(value), header_style) for value in block.columns]
    ]
    rows.extend(
        [
            [Paragraph(_safe(value), body_style) for value in row]
            for row in block.rows
        ]
    )
    table = Table(
        rows,
        repeatRows=1,
        colWidths=_column_widths(block, width),
        hAlign="LEFT",
        splitByRow=1,
    )
    commands: list[tuple] = [
        ("BACKGROUND", (0, 0), (-1, 0), _ACCENT_DARK),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5 if compact else 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5 if compact else 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4.5 if compact else 5.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5 if compact else 5.5),
    ]
    for row_index in range(1, len(rows)):
        if row_index % 2 == 0:
            commands.append(
                ("BACKGROUND", (0, row_index), (-1, row_index), _SOFT)
            )
    table.setStyle(TableStyle(commands))
    return table

def _equation_image(
    block: EquationBlock,
    *,
    asset_directory: Path,
    maximum_width: float,
    cache: dict[str, Path],
) -> Image | Paragraph:
    try:
        normalized = normalize_math_expression(block.expression)
    except EquationRenderingError:
        normalized = block.expression.strip()
    key = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:20]
    image_path = cache.get(key)
    if image_path is None:
        image_path = asset_directory / f"equation-{key}.png"
        try:
            render_equation_image(block.expression, image_path)
        except EquationRenderingError:
            fonts = _register_fonts()
            return Paragraph(
                _safe(block.expression),
                _styles(fonts)["equation_fallback"],
            )
        cache[key] = image_path

    with PILImage.open(image_path) as rendered:
        pixel_width, pixel_height = rendered.size
    natural_width = pixel_width / 260 * 72
    natural_height = pixel_height / 260 * 72
    max_height = 16.5 * mm
    scale = min(
        1.03,
        maximum_width / max(natural_width, 1),
        max_height / max(natural_height, 1),
    )
    return Image(
        str(image_path),
        width=max(18 * mm, natural_width * scale),
        height=max(4.2 * mm, natural_height * scale),
    )


def _equation_group(
    blocks: list[EquationBlock],
    *,
    styles: dict[str, ParagraphStyle],
    width: float,
    asset_directory: Path,
    cache: dict[str, Path],
) -> list[object]:
    rows: list[list[object]] = []
    for block in blocks:
        equation = _equation_image(
            block,
            asset_directory=asset_directory,
            maximum_width=width * 0.80,
            cache=cache,
        )
        label = Paragraph(
            _safe(block.label or ""),
            styles["equation_label"],
        )
        rows.append([equation, label])
    container = Table(
        rows,
        colWidths=[width - 22 * mm, 22 * mm],
        hAlign="CENTER",
    )
    container.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                ("LINEBEFORE", (0, 0), (0, -1), 2.0, _ACCENT),
                ("ALIGN", (0, 0), (0, -1), "CENTER"),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return [KeepTogether([Spacer(1, 2), container, Spacer(1, 7)])]


def _callout_table(
    block: CalloutBlock,
    *,
    styles: dict[str, ParagraphStyle],
    width: float,
) -> Table:
    palette = {
        "warning": ("#FFF7E8", "#D17A22", "Warning"),
        "success": ("#EEF8F2", "#2F855A", "Verified"),
        "assumption": ("#F4F1FB", "#7A4EAB", "Assumption"),
        "info": ("#EFF6FA", "#315C8C", "Note"),
    }
    background_hex, accent_hex, fallback = palette.get(
        block.kind,
        palette["info"],
    )
    title = block.title.strip() or fallback
    rows = [
        [
            Paragraph(_safe(title), styles["callout_title"]),
            Paragraph(_safe(block.text), styles["callout_body"]),
        ]
    ]
    table = Table(rows, colWidths=[31 * mm, width - 31 * mm], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(background_hex)),
                ("LINEBEFORE", (0, 0), (0, 0), 3.0, colors.HexColor(accent_hex)),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("BOX", (0, 0), (-1, -1), 0.45, colors.HexColor(accent_hex)),
            ]
        )
    )
    return table


def _diagram_table(
    block: DiagramBlock,
    *,
    styles: dict[str, ParagraphStyle],
    width: float,
) -> list[object]:
    flowables: list[object] = []
    if block.title:
        flowables.append(
            Paragraph(_safe(block.title), styles["figure_label"])
        )
    if not block.steps:
        return flowables
    rows: list[list[object]] = []
    for index, step in enumerate(block.steps):
        rows.append(
            [
                Paragraph(str(index + 1), styles["table_header"]),
                Paragraph(_safe(step), styles["table_body"]),
            ]
        )
    table = Table(
        rows,
        colWidths=[12 * mm, width - 12 * mm],
        hAlign="LEFT",
        splitByRow=1,
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), _ACCENT_DARK),
                ("BACKGROUND", (1, 0), (1, -1), colors.HexColor("#F7FAF9")),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D7E3DF")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (0, -1), "CENTER"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    flowables.extend([table, Spacer(1, 8)])
    return flowables


def _chart_cache_key(block: ChartBlock) -> str:
    payload = repr(
        (
            block.title,
            block.labels,
            tuple((series.name, series.values) for series in block.series),
            block.chart_type,
            block.x_label,
            block.y_label,
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def _chart_flowables(
    block: ChartBlock,
    *,
    figure_number: int,
    asset_directory: Path,
    document_width: float,
    styles: dict[str, ParagraphStyle],
    cache: dict[str, Path],
) -> list[object]:
    key = _chart_cache_key(block)
    chart_path = cache.get(key)
    if chart_path is None:
        chart_path = asset_directory / f"chart-{key}.png"
        render_chart_image(block, chart_path)
        cache[key] = chart_path

    with PILImage.open(chart_path) as rendered:
        pixel_width, pixel_height = rendered.size
    aspect = pixel_height / max(pixel_width, 1)
    target_width = document_width * 0.90
    target_height = min(target_width * aspect, 92 * mm)
    if target_width * aspect > 92 * mm:
        target_width = target_height / aspect
    image = Image(
        str(chart_path),
        width=target_width,
        height=target_height,
    )
    label = Paragraph(
        f"FIGURE {figure_number}",
        styles["figure_label"],
    )
    caption_text = block.caption or block.title
    caption = Paragraph(
        f"<b>{_safe(block.title)}</b><br/>{_safe(caption_text)}",
        styles["caption"],
    )
    return [
        CondPageBreak(target_height + 25 * mm),
        KeepTogether([label, image, caption]),
    ]


def _document_statistics(artifact: ArtifactDocument) -> tuple[int, int, int, int]:
    sections = len(artifact.sections)
    charts = 0
    tables = 0
    equations = 0
    for section in artifact.sections:
        for block in section.blocks:
            charts += isinstance(block, ChartBlock)
            tables += isinstance(block, TableBlock)
            equations += isinstance(block, EquationBlock)
    return sections, charts, tables, equations


def _cover_profile(
    artifact: ArtifactDocument,
    *,
    styles: dict[str, ParagraphStyle],
    width: float,
) -> Table:
    sections, charts, tables, equations = _document_statistics(artifact)
    values = (
        ("SECTIONS", str(sections)),
        ("FIGURES", str(charts)),
        ("TABLES", str(tables)),
        ("EQUATIONS", str(equations)),
    )
    cells: list[object] = []
    for label, value in values:
        cells.append(
            Paragraph(
                f"<font size='15'><b>{value}</b></font><br/>"
                f"<font size='7' color='#667085'>{label}</font>",
                styles["metadata"],
            )
        )
    table = Table([cells], colWidths=[width / 4] * 4, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), _SOFT),
                ("BOX", (0, 0), (-1, -1), 0.5, _LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, _LINE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return table


def _default_subtitle(family: str) -> str:
    return {
        "executive_report": "Operational analysis, evidence, risks and recommended actions",
        "research_paper": "Research context, analysis, findings and limitations",
        "academic_textbook": "Concepts, worked examples, visual explanations and review",
        "technical_spec": "Scope, architecture, implementation and control requirements",
        "proposal_document": "Opportunity, proposed approach, delivery plan and outcomes",
        "data_report": "Key metrics, comparative analysis, visual findings and actions",
        "case_study": "Context, challenge, approach, outcomes and lessons learned",
        "modern_summary": "A clear, structured and professionally presented document",
    }.get(family, "A clear, structured and professionally presented document")


def _cover_story(
    artifact: ArtifactDocument,
    *,
    styles: dict[str, ParagraphStyle],
    document: _Template,
) -> list[object]:
    brief = artifact.layout_brief
    theme = _theme(brief)
    top_space = {
        "technical_spec": 20,
        "academic_textbook": 27,
        "research_paper": 31,
        "case_study": 27,
        "modern_summary": 35,
    }.get(brief.family, 25)
    top_space = {
        "technical_grid": 30,
        "classic_university": 38,
        "minimal_academic": 34,
        "formal_research": 32,
        "data_rich_analytical": 29,
        "visual_learning": 31,
        "code_first_technical": 28,
        "print_optimized_monochrome": 36,
        "accessible_reading": 30,
        "modern_engineering": 27,
    }.get(brief.visual_system, top_space)
    story: list[object] = [Spacer(1, top_space * mm)]
    if brief.cover_eyebrow:
        story.append(
            Paragraph(_safe(brief.cover_eyebrow), styles["eyebrow"])
        )
    story.extend(
        [
            Paragraph(_safe(artifact.title), styles["title"]),
            HRFlowable(
                width=("18%" if brief.family in {"research_paper", "academic_textbook"} else "26%"),
                thickness=2.0,
                color=theme.accent,
                hAlign="LEFT",
            ),
        ]
    )
    if brief.cover_show_subtitle:
        subtitle = artifact.subtitle or _default_subtitle(brief.family)
        if subtitle:
            story.extend(
                [
                    Spacer(1, 5 * mm),
                    Paragraph(_safe(subtitle), styles["subtitle"]),
                ]
            )
    if brief.cover_show_profile:
        story.extend(
            [
                Spacer(1, 9 * mm),
                _cover_profile(artifact, styles=styles, width=document.width),
            ]
        )
    metadata: list[object] = []
    if brief.cover_show_author and artifact.author:
        metadata.append(
            Paragraph(f"Prepared by <b>{_safe(artifact.author)}</b>", styles["metadata"])
        )
    if brief.cover_show_date:
        metadata.append(
            Paragraph(date.today().strftime("%B %d, %Y"), styles["metadata"])
        )
    if metadata:
        story.extend([Spacer(1, 12 * mm), *metadata])
    story.append(PageBreak())
    return story


def _section_heading_flowables(
    section,
    *,
    index: int,
    brief: ArtifactLayoutBrief,
    styles: dict[str, ParagraphStyle],
) -> list[object]:
    theme = _theme(brief)
    if section.title.startswith("Part "):
        return [
            CondPageBreak(66 * mm),
            Paragraph(_safe(section.title), styles["part"]),
        ]

    section_style = (
        styles["h1"]
        if section.level <= 1
        else styles["h2"]
        if section.level == 2
        else styles["h3"]
    )
    if brief.include_section_openers and section.level <= 1:
        return [
            CondPageBreak(52 * mm),
            KeepTogether(
                [
                    Paragraph(
                        f"SECTION {index + 1:02d}",
                        styles["eyebrow"],
                    ),
                    Paragraph(
                        _safe(section.title),
                        section_style,
                    ),
                    HRFlowable(
                        width="100%",
                        thickness=0.55,
                        color=theme.line,
                        hAlign="LEFT",
                        spaceAfter=8,
                    ),
                ]
            ),
        ]
    return [
        CondPageBreak(34 * mm),
        Paragraph(_safe(section.title), section_style),
    ]


def _remove_implicit_pdf_dates(output_path: Path) -> None:
    """Remove automatic PDF timestamps when the user did not request a date."""

    temporary_path = output_path.with_suffix(".metadata-clean.pdf")
    reader = PdfReader(output_path)
    writer = PdfWriter(clone_from=output_path)
    metadata = dict(writer.metadata or reader.metadata or {})
    metadata.pop("/CreationDate", None)
    metadata.pop("/ModDate", None)
    writer.metadata = metadata
    with temporary_path.open("wb") as stream:
        writer.write(stream)
    temporary_path.replace(output_path)


def render_pdf(artifact: ArtifactDocument, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fonts = _register_fonts()
    styles = _styles(fonts, artifact.layout_brief)
    document = _Template(
        str(output_path),
        document_title=artifact.title,
        author=artifact.author,
        fonts=fonts,
        layout_brief=artifact.layout_brief,
    )

    story: list[object] = _cover_story(
        artifact,
        styles=styles,
        document=document,
    )

    if (
        artifact.layout_brief.include_table_of_contents
        and len(artifact.sections) >= 3
    ):
        story.extend(
            [
                Paragraph("Contents", styles["h1"]),
                Spacer(1, 2 * mm),
            ]
        )
        toc = TableOfContents()
        toc.levelStyles = [
            ParagraphStyle(
                "TOCLevel1",
                fontName=fonts["bold"],
                fontSize=9.2,
                leading=13.6,
                textColor=_INK,
                leftIndent=0,
                firstLineIndent=0,
                spaceBefore=4,
            ),
            ParagraphStyle(
                "TOCLevel2",
                fontName=fonts["regular"],
                fontSize=8.7,
                leading=12.4,
                textColor=_BODY,
                leftIndent=12,
                firstLineIndent=0,
                spaceBefore=2,
            ),
        ]
        story.extend([toc, PageBreak()])

    with TemporaryDirectory(
        prefix="professional-pdf-layout-"
    ) as temporary_directory:
        asset_directory = Path(temporary_directory)
        chart_cache: dict[str, Path] = {}
        equation_cache: dict[str, Path] = {}
        figure_number = 0
        table_number = 0

        for section_index, section in enumerate(artifact.sections):
            story.extend(
                _section_heading_flowables(
                    section,
                    index=section_index,
                    brief=artifact.layout_brief,
                    styles=styles,
                )
            )

            blocks = list(section.blocks)
            block_index = 0
            while block_index < len(blocks):
                block = blocks[block_index]
                if isinstance(block, ParagraphBlock):
                    story.append(Paragraph(_safe(block.text), styles["body"]))
                elif isinstance(block, QuoteBlock):
                    story.append(Paragraph(_safe(block.text), styles["quote"]))
                elif isinstance(block, CalloutBlock):
                    story.extend(
                        [
                            _callout_table(
                                block,
                                styles=styles,
                                width=document.width,
                            ),
                            Spacer(1, 8),
                        ]
                    )
                elif isinstance(block, BulletListBlock):
                    items = [
                        ListItem(
                            Paragraph(_safe(item), styles["list_body"]),
                            leftIndent=4,
                        )
                        for item in block.items
                    ]
                    story.append(
                        ListFlowable(
                            items,
                            bulletType="1" if block.ordered else "bullet",
                            leftIndent=18,
                            bulletFontName=fonts["regular"],
                            bulletFontSize=8.5,
                            bulletColor=_theme(
                                artifact.layout_brief
                            ).body,
                            spaceAfter=8,
                        )
                    )
                elif isinstance(block, TableBlock):
                    table_number += 1
                    wide = (
                        artifact.layout_brief.use_landscape_for_wide_tables
                        and _is_wide_table(block)
                    )
                    if wide:
                        story.extend(
                            [
                                NextPageTemplate("landscape"),
                                PageBreak(),
                                Paragraph(f"TABLE {table_number}", styles["figure_label"]),
                                _table(
                                    block,
                                    styles=styles,
                                    width=document.landscape_width,
                                    compact=True,
                                ),
                            ]
                        )
                        if block.caption:
                            story.append(Paragraph(_safe(block.caption), styles["caption"]))
                        has_following_content = (
                            block_index < len(blocks) - 1
                            or section_index < len(artifact.sections) - 1
                        )
                        if has_following_content:
                            story.extend(
                                [
                                    NextPageTemplate("portrait"),
                                    PageBreak(),
                                ]
                            )
                    else:
                        story.extend(
                            [
                                CondPageBreak(42 * mm),
                                Paragraph(f"TABLE {table_number}", styles["figure_label"]),
                                _table(
                                    block,
                                    styles=styles,
                                    width=document.width,
                                ),
                            ]
                        )
                        if block.caption:
                            story.append(Paragraph(_safe(block.caption), styles["caption"]))
                        else:
                            story.append(Spacer(1, 7))
                elif isinstance(block, ChartBlock):
                    figure_number += 1
                    story.extend(
                        _chart_flowables(
                            block,
                            figure_number=figure_number,
                            asset_directory=asset_directory,
                            document_width=document.width,
                            styles=styles,
                            cache=chart_cache,
                        )
                    )
                elif isinstance(block, DiagramBlock):
                    story.extend(
                        _diagram_table(
                            block,
                            styles=styles,
                            width=document.width,
                        )
                    )
                elif isinstance(block, EquationBlock):
                    group: list[EquationBlock] = [block]
                    lookahead = block_index + 1
                    while (
                        lookahead < len(blocks)
                        and isinstance(blocks[lookahead], EquationBlock)
                        and len(group) < 3
                    ):
                        group.append(blocks[lookahead])
                        lookahead += 1
                    story.extend(
                        _equation_group(
                            group,
                            styles=styles,
                            width=document.width,
                            asset_directory=asset_directory,
                            cache=equation_cache,
                        )
                    )
                    block_index = lookahead - 1
                elif isinstance(block, PageBreakBlock):
                    story.append(PageBreak())
                elif isinstance(block, CodeBlock):
                    story.append(Preformatted(block.code, styles["code"]))
                block_index += 1

        document.multiBuild(story)

    if not artifact.layout_brief.cover_show_date:
        _remove_implicit_pdf_dates(output_path)

    if not output_path.exists() or output_path.stat().st_size <= 0:
        raise RuntimeError("PDF rendering failed.")
    return output_path
