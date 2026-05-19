from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any


class PDFReportGenerator:
    """Generates strategy and SEO reports as standard PDF files without external library dependencies."""

    def __init__(self, title: str):
        self.title = title
        self.pages: list[list[str]] = []
        self.current_page_commands: list[str] = []
        self.y_cursor = 780
        self.margin_left = 50
        self.margin_right = 545
        self.page_width = 595
        self.page_height = 842
        self.font_size_regular = 10
        self.font_size_header = 14
        self.font_size_title = 18

    def _start_new_page(self) -> None:
        if self.current_page_commands:
            self.pages.append(self.current_page_commands)
        self.current_page_commands = []
        self.y_cursor = 780
        # Draw header boundary
        self._add_text(f"Report: {self.title}", self.margin_left, 810, font="F2", size=8)
        self.current_page_commands.append(f"0.5 w 50 802 m 545 802 l S")

    def _add_text(self, text: str, x: float, y: float, font: str = "F1", size: float = 10) -> None:
        escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        self.current_page_commands.extend([
            "BT",
            f"/{font} {size} Tf",
            f"{size * 1.2} TL",
            f"{x} {y} Td",
            f"({escaped}) Tj",
            "ET"
        ])

    def add_title(self, text: str) -> None:
        if not self.current_page_commands:
            self._start_new_page()
        self.y_cursor -= 10
        self._add_text(text, self.margin_left, self.y_cursor, font="F2", size=self.font_size_title)
        self.y_cursor -= 28

    def add_header(self, text: str) -> None:
        if self.y_cursor < 100:
            self._start_new_page()
        self.y_cursor -= 15
        self._add_text(text, self.margin_left, self.y_cursor, font="F2", size=self.font_size_header)
        self.y_cursor -= 20

    def add_subheader(self, text: str) -> None:
        if self.y_cursor < 80:
            self._start_new_page()
        self.y_cursor -= 10
        self._add_text(text, self.margin_left, self.y_cursor, font="F2", size=11)
        self.y_cursor -= 16

    def add_paragraph(self, text: str) -> None:
        # Wrap at ~85 chars for 10pt font
        wrapped_lines = textwrap.wrap(text, width=85)
        for line in wrapped_lines:
            if self.y_cursor < 60:
                self._start_new_page()
            self._add_text(line, self.margin_left, self.y_cursor, font="F1", size=self.font_size_regular)
            self.y_cursor -= 14
        self.y_cursor -= 6

    def add_bullet(self, text: str) -> None:
        # Bullet point with bullet symbol
        bullet_char = "-"
        wrapped_lines = textwrap.wrap(text, width=80)
        for i, line in enumerate(wrapped_lines):
            if self.y_cursor < 60:
                self._start_new_page()
            if i == 0:
                self._add_text(f"{bullet_char} {line}", self.margin_left + 10, self.y_cursor, font="F1", size=self.font_size_regular)
            else:
                self._add_text(line, self.margin_left + 20, self.y_cursor, font="F1", size=self.font_size_regular)
            self.y_cursor -= 14
        self.y_cursor -= 4

    def add_table(self, headers: list[str], rows: list[list[str]], col_widths: list[int]) -> None:
        """Render a neat text-based table with background boxes and lines."""
        if self.y_cursor < (len(rows) + 2) * 20 + 50:
            self._start_new_page()

        # Draw Table Headers
        self.y_cursor -= 10
        current_x = self.margin_left
        for header, width in zip(headers, col_widths):
            self._add_text(header, current_x + 4, self.y_cursor + 3, font="F2", size=9)
            current_x += width

        # Header background divider line
        self.current_page_commands.append(f"1 w 50 {self.y_cursor} m 545 {self.y_cursor} l S")
        self.y_cursor -= 18

        # Draw Table Rows
        for row in rows:
            if self.y_cursor < 60:
                self._start_new_page()
                # Redraw table headers on new page
                self.y_cursor -= 10
                current_x = self.margin_left
                for header, width in zip(headers, col_widths):
                    self._add_text(header, current_x + 4, self.y_cursor + 3, font="F2", size=9)
                    current_x += width
                self.current_page_commands.append(f"1 w 50 {self.y_cursor} m 545 {self.y_cursor} l S")
                self.y_cursor -= 18

            current_x = self.margin_left
            for val, width in zip(row, col_widths):
                truncated = val[:int(width / 5)]  # Simple truncation to prevent overflow
                self._add_text(truncated, current_x + 4, self.y_cursor + 2, font="F1", size=8)
                current_x += width

            # Row bottom divider line
            self.current_page_commands.append(f"0.5 w 50 {self.y_cursor} m 545 {self.y_cursor} l S")
            self.y_cursor -= 16

        self.y_cursor -= 10

    def generate_bytes(self) -> bytes:
        """Assembles standard PDF file format bytes."""
        if self.current_page_commands:
            self.pages.append(self.current_page_commands)

        # Build PDF structure
        # Object index tracker
        objects: list[bytes] = []
        offsets: dict[int, int] = {}

        def add_obj(data: bytes) -> int:
            obj_id = len(objects) + 1
            objects.append(data)
            return obj_id

        # Placements mapping
        # Catalog (will be Obj 1)
        # Pages root (will be Obj 2)
        # Font regular F1 (will be Obj 3)
        # Font bold F2 (will be Obj 4)
        
        # Predefine font objects
        f1_desc = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"
        f2_desc = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>"
        
        # We need catalog and page list reference
        # We will write Catalog as Obj 1, Pages as Obj 2, Fonts as 3 and 4.
        # Pages will have Kids IDs starting from 5.
        
        page_ids = []
        page_contents_ids = []
        
        # Populate pages
        for i, cmd_list in enumerate(self.pages):
            content_str = "\n".join(cmd_list)
            content_bytes = content_str.encode("utf-8")
            stream_obj = f"<< /Length {len(content_bytes)} >>\nstream\n".encode("utf-8") + content_bytes + b"\nendstream"
            
            # Page object ID is calculated after fonts + other page components
            # Let's say: 
            # Obj 1: Catalog
            # Obj 2: Pages Root
            # Obj 3: Font F1
            # Obj 4: Font F2
            # For each page:
            # Obj 2k + 3: Page Object
            # Obj 2k + 4: Content Stream
            # Let's write them cleanly.
            pass

        # To build cleanly without math complexity, let's assemble objects array sequentially
        # Obj 1 placeholder (Catalog)
        # Obj 2 placeholder (Pages Root)
        # Obj 3: Font F1
        # Obj 4: Font F2
        
        # Let's populate objects list sequentially
        # We will construct them correctly.
        objects_data: list[bytes] = [b""] * 4
        objects_data[2] = f1_desc
        objects_data[3] = f2_desc
        
        for cmd_list in self.pages:
            content_str = "\n".join(cmd_list)
            content_bytes = content_str.encode("utf-8")
            stream_content = f"<< /Length {len(content_bytes)} >>\nstream\n".encode("utf-8") + content_bytes + b"\nendstream"
            
            p_obj_id = len(objects_data) + 1
            c_obj_id = p_obj_id + 1
            
            page_ids.append(p_obj_id)
            page_contents_ids.append(c_obj_id)
            
            p_desc = f"<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents {c_obj_id} 0 R /MediaBox [0 0 595 842] >>".encode("utf-8")
            
            objects_data.append(p_desc)
            objects_data.append(stream_content)

        # Now fill in Catalog (Obj 1) and Pages Root (Obj 2)
        objects_data[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
        kids_str = " ".join(f"{pid} 0 R" for pid in page_ids)
        objects_data[1] = f"<< /Type /Pages /Kids [{kids_str}] /Count {len(page_ids)} >>".encode("utf-8")

        # Now assemble bytes
        out = bytearray()
        out.extend(b"%PDF-1.4\n")
        
        for i, data in enumerate(objects_data):
            obj_id = i + 1
            offsets[obj_id] = len(out)
            out.extend(f"{obj_id} 0 obj\n".encode("utf-8"))
            out.extend(data)
            out.extend(b"\nendobj\n")

        xref_start = len(out)
        out.extend(b"xref\n")
        out.extend(f"0 {len(objects_data) + 1}\n".encode("utf-8"))
        out.extend(b"0000000000 65535 f \n")
        for obj_id in range(1, len(objects_data) + 1):
            offset = offsets[obj_id]
            out.extend(f"{offset:010d} 00000 n \n".encode("utf-8"))

        out.extend(b"trailer\n")
        out.extend(f"<< /Size {len(objects_data) + 1} /Root 1 0 R >>\n".encode("utf-8"))
        out.extend(b"startxref\n")
        out.extend(f"{xref_start}\n".encode("utf-8"))
        out.extend(b"%%EOF\n")
        return bytes(out)

    def save(self, filepath: str | Path) -> Path:
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        pdf_bytes = self.generate_bytes()
        path.write_bytes(pdf_bytes)
        return path


def generate_pdf_strategy_report(report_data: dict[str, Any], filepath: str | Path) -> Path:
    """Helper to convert structured strategy report JSON to a beautiful PDF document."""
    brand = report_data.get("site", {}).get("brand", "MeetLyra")
    gen_time = report_data.get("generated_at", "2026-05-19")
    
    pdf = PDFReportGenerator(f"{brand} SEO Strategy Report")
    
    pdf.add_title(f"{brand} SEO Strategy & GEO Report")
    pdf.add_paragraph(f"Generated At: {gen_time}")
    pdf.add_paragraph("This report presents a strict, evidence-backed strategy audit combining page intelligence, technical checks, competitor content gap research, and generative engine optimization (GEO) scoring.")
    
    # 1. GEO Scores
    pdf.add_header("1. Generative Engine Optimization (GEO) Overview")
    pdf.add_paragraph("GEO readiness determines how frequently your site content is retrieved and cited by AI engines like ChatGPT, Bing Copilot, Perplexity, and Google AI Overviews.")
    
    matrix = report_data.get("claude_seo_capability_matrix", [])
    headers = ["Capability", "Status", "Deployment Detail"]
    rows = []
    for cap in matrix:
        rows.append([cap.get("capability", ""), cap.get("status", ""), cap.get("detail", "")])
    
    pdf.add_table(headers, rows, [110, 80, 305])
    
    # 2. Key Actions
    pdf.add_header("2. Prioritized Roadmap & Next Actions")
    actions = report_data.get("next_actions", [])
    for act in actions:
        priority = act.get("priority", "medium").upper()
        pdf.add_bullet(f"[{priority}] {act.get('action')} - Impact: {act.get('impact')}")

    # 3. Competitor gaps
    pdf.add_header("3. Competitor Gap Analysis")
    gaps = report_data.get("competitor_research", {}).get("content_gaps", [])
    for gap in gaps[:5]:
        pdf.add_bullet(gap)
        
    # 4. Schema Engine
    pdf.add_header("4. Schema Graph Requirements")
    schema_engine = report_data.get("schema_engine", {})
    pdf.add_paragraph(f"Strategy target: {schema_engine.get('strategy', 'yoast_schema_api')}")
    pdf.add_subheader("Required Schema Graph Pieces:")
    for piece in schema_engine.get("required_graph_pieces", []):
        pdf.add_bullet(piece)

    return pdf.save(filepath)
