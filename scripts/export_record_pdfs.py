# /// script
# requires-python = ">=3.11"
# dependencies = ["fpdf2>=2.8"]
# ///
"""Export synthetic patient Markdown records to A4 PDFs (demo / hand-in only).

PageIndex and eval read the .md files, not these PDFs.

    uv run scripts/export_record_pdfs.py
    uv run scripts/export_record_pdfs.py --ids p001 p002
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from fpdf import FPDF

ROOT = Path(__file__).resolve().parent.parent
RECORDS = ROOT / "eval" / "records"
PDF_DIR = RECORDS / "pdf"


def _latin1(text: str) -> str:
    """Helvetica core fonts are Latin-1; map common Unicode from the phrase banks."""
    return (
        text.replace("\u2014", "-").replace("\u2013", "-").replace("\u2212", "-")
        .replace("\u00b0", " deg").replace("\u2019", "'").replace("\u2018", "'")
        .replace("\u201c", '"').replace("\u201d", '"')
        .encode("latin-1", "replace").decode("latin-1")
    )


class RecordPDF(FPDF):
    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", size=8)
        self.set_text_color(100)
        self.cell(0, 8, _latin1(f"Page {self.page_no()}/{{nb}} - synthetic demo export"), align="C")


def _write_wrapped(pdf: FPDF, text: str, size: int = 10, style: str = "", indent: float = 0):
    pdf.set_font("Helvetica", style=style, size=size)
    pdf.set_x(pdf.l_margin + indent)
    pdf.multi_cell(pdf.epw - indent, 5, _latin1(text))


def md_to_pdf(md: str, pdf_path: Path) -> None:
    """Render the Markdown subset produced by make_records into an A4 PDF."""
    pdf = RecordPDF(format="A4")
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()
    pdf.set_font("Helvetica", size=9)
    pdf.set_text_color(80)
    pdf.multi_cell(pdf.epw, 5, _latin1(
        "Synthetic record - for demo. Source of truth is the Markdown file."))
    pdf.ln(3)
    pdf.set_text_color(0)

    for raw in md.splitlines():
        line = raw.rstrip()
        if re.match(r"^<!--.*-->$", line.strip()) or not line.strip():
            continue
        if line.startswith("# "):
            pdf.ln(2)
            _write_wrapped(pdf, line[2:].strip(), size=16, style="B")
            pdf.ln(2)
        elif line.startswith("## "):
            pdf.ln(3)
            _write_wrapped(pdf, line[3:].strip(), size=12, style="B")
            pdf.ln(1)
        elif line.startswith("### "):
            pdf.ln(2)
            _write_wrapped(pdf, line[4:].strip(), size=11, style="B")
        elif line.startswith("- "):
            _write_wrapped(pdf, f"- {line[2:].strip()}", size=10, indent=4)
        else:
            _write_wrapped(pdf, line.strip(), size=10)

    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(pdf_path))


def export_one(md_path: Path, pdf_path: Path) -> None:
    md_to_pdf(md_path.read_text(), pdf_path)


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--records", type=Path, default=RECORDS, help="directory with pNNN.md")
    p.add_argument("--out", type=Path, default=PDF_DIR, help="PDF output directory")
    p.add_argument("--ids", nargs="+", help="only these patient ids (e.g. p001 p002)")
    return p.parse_args(argv)


if __name__ == "__main__":
    a = parse_args()
    records = a.records.resolve()
    out = a.out.resolve()
    if a.ids:
        paths = [records / f"{pid}.md" for pid in a.ids]
    else:
        paths = sorted(records.glob("p*.md"))
    missing = [p for p in paths if not p.exists()]
    if missing:
        sys.exit("export_record_pdfs: missing " + ", ".join(str(p) for p in missing))
    if not paths:
        sys.exit(f"export_record_pdfs: no p*.md under {records}")

    for md in paths:
        pdf = out / f"{md.stem}.pdf"
        export_one(md, pdf)
        print(f"wrote {pdf.relative_to(ROOT) if pdf.is_relative_to(ROOT) else pdf}", flush=True)
    print(f"done: {len(paths)} PDFs -> {out}", flush=True)
