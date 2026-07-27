from __future__ import annotations

from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    Image,
    ListFlowable,
    ListItem,
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
from artifacts.models import (
    ArtifactDocument,
    BulletListBlock,
    ChartBlock,
    CodeBlock,
    ParagraphBlock,
    TableBlock,
)


def _safe(value: str) -> str:
    return escape(value.strip()).replace("\n", "<br/>")


def _styles() -> dict[str, ParagraphStyle]:
    sample = getSampleStyleSheet()

    return {
        "title": ParagraphStyle(
            "ArtifactTitle",
            parent=sample["Title"],
            fontName="Helvetica-Bold",
            fontSize=28,
            leading=34,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#172033"),
            spaceAfter=12,
        ),
        "subtitle": ParagraphStyle(
            "ArtifactSubtitle",
            parent=sample["Normal"],
            fontName="Helvetica",
            fontSize=13,
            leading=18,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#556072"),
            spaceAfter=12,
        ),
        "metadata": ParagraphStyle(
            "ArtifactMetadata",
            parent=sample["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=15,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#697386"),
        ),
        "h1": ParagraphStyle(
            "ArtifactHeading1",
            parent=sample["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=23,
            textColor=colors.HexColor("#172033"),
            spaceBefore=14,
            spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "ArtifactHeading2",
            parent=sample["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=18,
            textColor=colors.HexColor("#28364D"),
            spaceBefore=11,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "ArtifactBody",
            parent=sample["BodyText"],
            fontName="Helvetica",
            fontSize=10.3,
            leading=15,
            alignment=TA_LEFT,
            textColor=colors.HexColor("#242B38"),
            spaceAfter=8,
        ),
        "caption": ParagraphStyle(
            "ArtifactCaption",
            parent=sample["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=8.6,
            leading=12,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#636C7C"),
            spaceBefore=4,
            spaceAfter=9,
        ),
        "code": ParagraphStyle(
            "ArtifactCode",
            parent=sample["Code"],
            fontName="Courier",
            fontSize=8.3,
            leading=11,
            leftIndent=7,
            rightIndent=7,
            borderWidth=0.5,
            borderColor=colors.HexColor("#D5DAE3"),
            borderPadding=7,
            backColor=colors.HexColor("#F5F7FA"),
            spaceBefore=5,
            spaceAfter=9,
        ),
    }


class _Template(BaseDocTemplate):
    def __init__(self, filename: str, *, document_title: str) -> None:
        self.document_title = document_title

        super().__init__(
            filename,
            pagesize=A4,
            leftMargin=18 * mm,
            rightMargin=18 * mm,
            topMargin=20 * mm,
            bottomMargin=18 * mm,
            title=document_title,
            author="Authentic AI",
        )

        frame = Frame(
            self.leftMargin,
            self.bottomMargin,
            self.width,
            self.height,
            id="content",
        )

        self.addPageTemplates(
            [
                PageTemplate(
                    id="professional",
                    frames=[frame],
                    onPage=self._draw_page,
                )
            ]
        )

    def _draw_page(self, canvas, document) -> None:
        canvas.saveState()

        if document.page > 1:
            canvas.setStrokeColor(colors.HexColor("#D5DAE3"))
            canvas.setFillColor(colors.HexColor("#646D7D"))
            canvas.setFont("Helvetica", 8)

            canvas.drawString(
                self.leftMargin,
                A4[1] - 12 * mm,
                self.document_title[:72],
            )

            canvas.line(
                self.leftMargin,
                A4[1] - 14 * mm,
                A4[0] - self.rightMargin,
                A4[1] - 14 * mm,
            )

        canvas.setFillColor(colors.HexColor("#646D7D"))
        canvas.setFont("Helvetica", 8)

        canvas.drawString(
            self.leftMargin,
            9 * mm,
            "Authentic AI",
        )

        canvas.drawRightString(
            A4[0] - self.rightMargin,
            9 * mm,
            f"Page {document.page}",
        )

        canvas.restoreState()

    def afterFlowable(self, flowable) -> None:
        if not isinstance(flowable, Paragraph):
            return

        style_name = flowable.style.name

        if style_name not in {
            "ArtifactHeading1",
            "ArtifactHeading2",
        }:
            return

        level = 0 if style_name == "ArtifactHeading1" else 1
        text = flowable.getPlainText()
        bookmark = (
            f"heading-{level}-{self.seq.nextf('heading')}"
        )

        self.canv.bookmarkPage(bookmark)

        self.canv.addOutlineEntry(
            text,
            bookmark,
            level=level,
            closed=False,
        )

        self.notify(
            "TOCEntry",
            (
                level,
                text,
                self.page,
                bookmark,
            ),
        )


def _table(
    block: TableBlock,
    *,
    styles: dict[str, ParagraphStyle],
    width: float,
) -> Table:
    column_count = max(len(block.columns), 1)

    rows = [
        [
            Paragraph(_safe(value), styles["body"])
            for value in block.columns
        ]
    ]

    rows.extend(
        [
            [
                Paragraph(_safe(value), styles["body"])
                for value in row
            ]
            for row in block.rows
        ]
    )

    table = Table(
        rows,
        repeatRows=1,
        colWidths=[width / column_count] * column_count,
        hAlign="LEFT",
    )

    table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor("#E9EDF4"),
                ),
                (
                    "FONTNAME",
                    (0, 0),
                    (-1, 0),
                    "Helvetica-Bold",
                ),
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.45,
                    colors.HexColor("#CDD3DD"),
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP",
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
            ]
        )
    )

    return table


def render_pdf(
    artifact: ArtifactDocument,
    output_path: Path,
) -> Path:
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    styles = _styles()

    document = _Template(
        str(output_path),
        document_title=artifact.title,
    )

    story = [
        Spacer(1, 40 * mm),
        Paragraph(
            _safe(artifact.title),
            styles["title"],
        ),
    ]

    if artifact.subtitle:
        story.append(
            Paragraph(
                _safe(artifact.subtitle),
                styles["subtitle"],
            )
        )

    story.extend(
        [
            Spacer(1, 10 * mm),
            HRFlowable(
                width="44%",
                thickness=1,
                color=colors.HexColor("#AAB3C2"),
                hAlign="CENTER",
            ),
            Spacer(1, 8 * mm),
            Paragraph(
                _safe(artifact.author or "Authentic AI"),
                styles["metadata"],
            ),
            Paragraph(
                date.today().strftime("%B %d, %Y"),
                styles["metadata"],
            ),
            PageBreak(),
            Paragraph("Contents", styles["h1"]),
        ]
    )

    toc = TableOfContents()

    toc.levelStyles = [
        ParagraphStyle(
            "TOCLevel1",
            fontName="Helvetica",
            fontSize=10.5,
            leading=15,
            leftIndent=0,
            firstLineIndent=0,
            spaceBefore=4,
        ),
        ParagraphStyle(
            "TOCLevel2",
            fontName="Helvetica",
            fontSize=9.5,
            leading=13,
            leftIndent=14,
            firstLineIndent=0,
            spaceBefore=2,
        ),
    ]

    story.extend([toc, PageBreak()])

    with TemporaryDirectory(
        prefix="authentic-pdf-charts-",
    ) as temporary_directory:
        chart_directory = Path(temporary_directory)
        chart_index = 0

        for section in artifact.sections:
            story.append(
                Paragraph(
                    _safe(section.title),
                    (
                        styles["h1"]
                        if section.level <= 1
                        else styles["h2"]
                    ),
                )
            )

            for block in section.blocks:
                if isinstance(block, ParagraphBlock):
                    story.append(
                        Paragraph(
                            _safe(block.text),
                            styles["body"],
                        )
                    )

                elif isinstance(block, BulletListBlock):
                    items = [
                        ListItem(
                            Paragraph(
                                _safe(item),
                                styles["body"],
                            )
                        )
                        for item in block.items
                    ]

                    story.append(
                        ListFlowable(
                            items,
                            bulletType=(
                                "1"
                                if block.ordered
                                else "bullet"
                            ),
                            leftIndent=18,
                            bulletFontName="Helvetica",
                            bulletFontSize=9,
                            spaceAfter=8,
                        )
                    )

                elif isinstance(block, TableBlock):
                    story.append(
                        _table(
                            block,
                            styles=styles,
                            width=document.width,
                        )
                    )

                    if block.caption:
                        story.append(
                            Paragraph(
                                _safe(block.caption),
                                styles["caption"],
                            )
                        )

                    story.append(Spacer(1, 7))

                elif isinstance(block, ChartBlock):
                    chart_index += 1

                    chart_path = (
                        chart_directory
                        / f"chart-{chart_index}.png"
                    )

                    render_chart_image(
                        block,
                        chart_path,
                    )

                    image = Image(str(chart_path))
                    image.drawWidth = document.width
                    image.drawHeight = document.width * 0.56

                    story.append(image)

                    story.append(
                        Paragraph(
                            _safe(
                                block.caption
                                or block.title
                            ),
                            styles["caption"],
                        )
                    )

                elif isinstance(block, CodeBlock):
                    story.append(
                        Preformatted(
                            block.code,
                            styles["code"],
                        )
                    )

        document.multiBuild(story)

    if (
        not output_path.exists()
        or output_path.stat().st_size <= 0
    ):
        raise RuntimeError(
            "PDF rendering failed."
        )

    return output_path