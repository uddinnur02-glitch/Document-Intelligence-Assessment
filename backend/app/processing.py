"""Bounded, per-page/per-sheet extraction. No LLMs or invoice inference in Phase 2."""
import csv
import io
import os
from pathlib import Path

MAX_PAGES = int(os.getenv("MAX_PDF_PAGES", "1200"))
MAX_CHARS = int(os.getenv("MAX_EXTRACTED_CHARS", "250000"))
MAX_ROWS = int(os.getenv("MAX_SPREADSHEET_ROWS", "25000"))
MAX_SHEETS = int(os.getenv("MAX_SHEETS", "50"))


def extract_file(filepath: str, original_filename: str) -> dict:
    path = Path(filepath)
    suffix = Path(original_filename).suffix.lower()
    if not path.is_file():
        raise ValueError("Uploaded file is missing from storage")
    if suffix == ".pdf":
        return _pdf(path)
    if suffix in {".png", ".jpg", ".jpeg", ".tif", ".tiff"}:
        return _image(path)
    if suffix == ".csv":
        return _csv(path)
    if suffix in {".xlsx", ".xls"}:
        return _excel(path, suffix)
    raise ValueError("Unsupported document type")


def _ocr(image):
    import pytesseract
    from PIL import ImageOps, ImageEnhance
    image = ImageOps.exif_transpose(image).convert("RGB")
    image = ImageOps.grayscale(image)
    image = ImageEnhance.Contrast(image).enhance(1.6)
    return pytesseract.image_to_string(image, config="--psm 3").strip()


def _image(path):
    from PIL import Image, ImageSequence
    pages = []
    with Image.open(path) as im:
        for index, frame in enumerate(ImageSequence.Iterator(im)):
            if index >= MAX_PAGES:
                raise ValueError(f"Image has more than {MAX_PAGES} frames")
            text = _ocr(frame.copy())
            pages.append({"page": index + 1, "method": "ocr", "text": text[:4000], "characters": len(text)})
    return _finish("image", pages)


def _pdf(path):
    import fitz
    pages = []
    try:
        with fitz.open(path) as doc:
            if doc.needs_pass:
                raise ValueError("Encrypted PDF is not supported")
            if doc.page_count > MAX_PAGES:
                raise ValueError(f"PDF has {doc.page_count} pages; configured limit is {MAX_PAGES}")
            all_tables = []
            for i in range(doc.page_count):
                page = doc.load_page(i)
                content = page.get_text("text").strip()
                method = "digital"
                if len(content) < 25:
                    from PIL import Image
                    import io
                    # Render one page at a time; do not hold the PDF images in memory.
                    pix = page.get_pixmap(matrix=fitz.Matrix(1.8, 1.8), alpha=False)
                    with Image.open(io.BytesIO(pix.tobytes("png"))) as im:
                        ocr_text = _ocr(im)
                    if len(ocr_text) > len(content):
                        content = ocr_text
                    method = "ocr"
                # Native PDF table detection on vector/text PDFs (not OCR table reconstruction).
                # Errors in layout heuristics do not prevent plain-text extraction.
                page_tables = []
                if hasattr(page, "find_tables"):
                    try:
                        for table_number, table in enumerate(page.find_tables().tables[:30], start=1):
                            rows = [[str(cell or "").strip()[:350] for cell in row[:60]]
                                    for row in table.extract()[:500]]
                            if rows:
                                page_tables.append({"table": table_number, "rows": rows,
                                                    "row_count": len(rows), "limited": len(rows) >= 500})
                    except (ValueError, RuntimeError, TypeError, AttributeError):
                        pass
                all_tables.append({"page": i + 1, "tables": page_tables})
                pages.append({"page": i + 1, "method": method, "text": content[:4000], "characters": len(content)})
    except (ValueError, RuntimeError):
        raise
    except Exception as error:
        raise ValueError(f"Cannot read PDF: {error}") from error
    result = _finish("pdf", pages)
    result["pdf_tables"] = all_tables
    result["warning"] += " PDF tables are detected heuristically, up to 30 per page and 500 rows per table; scanned tables may be missed."
    return result


def _cell(value):
    if value is None:
        return ""
    text = str(value)
    # Keep previews text-safe and bounded; Excel formulas are never evaluated.
    return text[:350]


def _make_table_result(kind, sheet_data):
    """Keep bounded full row text for searching and separate 20-row previews for display.

    Exhaustiveness is capped by MAX_ROWS/MAX_SHEETS/MAX_CHARS and MAX_CELL_CHARS.
    No formulas are evaluated. The preview alone is not used for search.
    """
    portions = []
    remaining = MAX_CHARS
    total_chars = 0
    truncated = False
    sheets = []
    all_items = []
    coverage = []
    from .reconciliation import StreamingLineItems
    for name, row_iterator in sheet_data:
        rows, preview = 0, []
        parser = StreamingLineItems("sheet:" + str(name))
        header = f"### {name}\n"
        total_chars += len(header)
        if remaining >= len(header):
            portions.append(header); remaining -= len(header)
        else:
            truncated = True
        for row in row_iterator:
            rows += 1
            if rows > MAX_ROWS:
                raise ValueError(f"Sheet {name} exceeds configured {MAX_ROWS} row limit")
            cells = [_cell(v) for v in row[:60]]
            parser.feed(cells, rows)
            if rows <= 20:
                preview.append(cells)
            line = " | ".join(cells) + "\n"
            total_chars += len(line)
            if remaining >= len(line):
                portions.append(line)
                remaining -= len(line)
            else:
                truncated = True
                if remaining:
                    portions.append(line[:remaining])
                    remaining = 0
        sheets.append({"name": name, "rows": rows, "preview": preview})
        all_items.extend(parser.items)
        coverage.append(parser.coverage())
    return {"kind": kind, "pages": [], "sheets": sheets, "page_count": 0,
            "sheet_count": len(sheets), "text": "".join(portions),
            "extracted_chars": total_chars, "truncated": truncated,
            "structured_line_items": all_items, "table_coverage": coverage,
            "warning": ("Spreadsheet preview shows 20 rows per sheet, but line-item parsing scans "
                        "all rows up to configured per-sheet limits. Missing headers, unparsed rows, "
                        "item caps, or text truncation require manual review.")}


def _csv(path):
    raw = path.read_bytes()
    decoded = None
    for encoding in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            decoded = raw.decode(encoding)
            break
        except UnicodeError:
            continue
    if decoded is None:
        raise ValueError("Unsupported CSV character encoding")
    reader = csv.reader(io.StringIO(decoded, newline=""))
    return _make_table_result("csv", [(path.name, reader)])


def _excel(path, suffix):
    if suffix == ".xlsx":
        import openpyxl
        try:
            wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
            try:
                if len(wb.sheetnames) > MAX_SHEETS:
                    raise ValueError(f"Excel workbook exceeds {MAX_SHEETS} sheets")
                return _make_table_result("spreadsheet", [
                    (ws.title, ws.iter_rows(values_only=True)) for ws in wb.worksheets
                ])
            finally:
                wb.close()
        except ValueError:
            raise
        except Exception as error:
            raise ValueError(f"Cannot read XLSX: {error}") from error
    import xlrd
    try:
        wb = xlrd.open_workbook(path, on_demand=True)
        if wb.nsheets > MAX_SHEETS:
            raise ValueError(f"Excel workbook exceeds {MAX_SHEETS} sheets")
        try:
            def rows_for(sheet):
                for row_index in range(sheet.nrows):
                    yield sheet.row_values(row_index)
            return _make_table_result("spreadsheet", [
                (ws.name, rows_for(ws)) for ws in wb.sheets()
            ])
        finally:
            wb.release_resources()
    except ValueError:
        raise
    except Exception as error:
        raise ValueError(f"Cannot read XLS: {error}") from error


def _finish(kind, pages):
    # Store a bounded concatenation of page previews for the web interface.
    text = "\n\n".join(f"Page {p['page']} ({p['method']}):\n{p['text']}" for p in pages)
    return {"kind": kind, "pages": pages, "sheets": [], "page_count": len(pages),
            "sheet_count": 0, "text": text[:MAX_CHARS],
            "extracted_chars": sum(p['characters'] for p in pages),
            "truncated": len(text) > MAX_CHARS or any(p['characters'] > 4000 for p in pages),
            "warning": "Page text previews are capped at 4,000 characters per page."}
