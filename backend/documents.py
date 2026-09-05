import io
import json
import re
import subprocess
import tempfile
import os
import zipfile
from pathlib import Path

import pymupdf
import pytesseract
from PIL import Image, ImageOps

from .config import libreoffice_path, tesseract_path
from .models import Page, Span

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".png", ".jpg", ".jpeg"}
MAX_FILE_BYTES = 25 * 1024 * 1024
MAX_PAGES = 200
Image.MAX_IMAGE_PIXELS = 40_000_000


def normalize_pdf(original: Path, target: Path) -> str:
    suffix = original.suffix.lower()
    if suffix == ".pdf":
        with pymupdf.open(original) as pdf:
            if pdf.needs_pass:
                raise ValueError("Password-protected PDF. Provide an unlocked copy.")
            if len(pdf) > MAX_PAGES:
                raise ValueError(f"Document exceeds the {MAX_PAGES}-page local processing limit; no pages were analyzed.")
        target.write_bytes(original.read_bytes())
        return "original"
    if suffix in {".png", ".jpg", ".jpeg"}:
        with Image.open(original) as image:
            if getattr(image, "n_frames", 1) != 1:
                raise ValueError("Animated or multi-frame images are unsupported. Supply every page as a PDF or separate images.")
            image = ImageOps.exif_transpose(image).convert("RGB")
            if image.width * image.height > 40_000_000:
                raise ValueError("Image exceeds the 40 megapixel processing limit.")
            image.save(target, "PDF", resolution=150)
        return "image"
    if suffix == ".docx":
        try:
            with zipfile.ZipFile(original) as archive:
                if 'word/document.xml' not in archive.namelist() or sum(info.file_size for info in archive.infolist()) > 100 * 1024 * 1024:
                    raise ValueError("DOCX is invalid or exceeds the 100 MiB expanded-content limit.")
        except zipfile.BadZipFile:
            raise ValueError("DOCX is not a readable document archive.") from None
        executable = libreoffice_path()
        if not executable:
            raise ValueError("LibreOffice is missing. Install it, then retry this DOCX.")
        with tempfile.TemporaryDirectory(prefix="aithena-office-") as directory:
            profile = (Path(directory) / "profile").as_uri()
            try:
                subprocess.run([executable, "-env:UserInstallation=" + profile, "--headless",
                                "--convert-to", "pdf", "--outdir", directory, str(original)],
                               check=True, capture_output=True, timeout=90)
            except subprocess.TimeoutExpired:
                raise ValueError("LibreOffice conversion timed out after 90 seconds. Inspect the DOCX and retry.") from None
            except subprocess.CalledProcessError:
                raise ValueError("LibreOffice could not convert this DOCX. Check the document and local conversion permissions, then retry.") from None
            converted = Path(directory) / (original.stem + ".pdf")
            if not converted.exists():
                raise ValueError("DOCX conversion produced no PDF.")
            with pymupdf.open(converted) as pdf:
                if not 1 <= len(pdf) <= MAX_PAGES:
                    raise ValueError(f"Converted DOCX must contain 1–{MAX_PAGES} pages; no pages were silently omitted.")
            target.write_bytes(converted.read_bytes())
        return "rendered"
    raise ValueError("Unsupported format. Use PDF, DOCX, PNG, or JPEG.")


def clause_label(text: str) -> str | None:
    match = re.match(r"^\s*((?:(?:Clause|Section)\s+)?\d+(?:\.\d+)*[.)]?)(?:\s|$)", text, flags=re.I)
    return match.group(1).rstrip(".") if match else None


def ocr_spans(page, document_id: str, page_number: int, index: int, clip=None) -> list[Span]:
    executable = tesseract_path()
    if not executable:
        raise ValueError("Tesseract is missing; scanned content has not been read.")
    pytesseract.pytesseract.tesseract_cmd = executable
    rect = pymupdf.Rect(clip) if clip else page.rect
    # Keep memory bounded for unusually large page sizes.
    scale = min(3, 3600 / max(rect.width, rect.height))
    pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), clip=rect, alpha=False)
    image = Image.open(io.BytesIO(pix.tobytes("png")))
    data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT,
                                    config="--psm 3", timeout=60)
    groups = {}
    for i, word in enumerate(data["text"]):
        if not word.strip() or float(data["conf"][i]) < 0:
            continue
        key = (data["block_num"][i], data["par_num"][i])
        groups.setdefault(key, []).append(i)
    spans = []
    for group in groups.values():
        text = " ".join(data["text"][i] for i in group)
        left = min(data["left"][i] for i in group)
        top = min(data["top"][i] for i in group)
        right = max(data["left"][i] + data["width"][i] for i in group)
        bottom = max(data["top"][i] + data["height"][i] for i in group)
        spans.append(Span(
            id=f"{document_id}:p{page_number}:s{index + len(spans)}",
            document_id=document_id, page=page_number, text=text,
            bbox=[rect.x0 + left / scale, rect.y0 + top / scale,
                  rect.x0 + right / scale, rect.y0 + bottom / scale],
            source="ocr", ocr_confidence=round(min(float(data["conf"][i]) for i in group), 1),
            clause=clause_label(text),
        ))
    return spans


LOW_OCR_WARNING = "Some scanned words have low OCR confidence; source review is needed."


def parse_pdf(path: Path, document_id: str, progress=None, existing: list[Page] | None = None) -> list[Page]:
    pages = []
    cached = {p.number: p for p in (existing or [])}
    with pymupdf.open(path) as pdf:
        if pdf.needs_pass:
            raise ValueError("Password-protected PDF.")
        if not len(pdf) or len(pdf) > MAX_PAGES:
            raise ValueError(f"PDF must contain 1–{MAX_PAGES} pages. No pages were silently omitted.")
        for i, page in enumerate(pdf):
            previous = cached.get(i + 1)
            if previous and previous.status == 'read' and previous.spans and not previous.warnings and previous.width == page.rect.width and previous.height == page.rect.height:
                pages.append(previous)
                if progress:
                    progress(pages, len(pdf))
                continue
            result = Page(number=i + 1, width=page.rect.width, height=page.rect.height)
            try:
                blocks = [b for b in page.get_text("blocks", sort=True) if b[6] == 0 and b[4].strip()]
                # Sparse text (including an invisible defective OCR layer) must not suppress OCR.
                native_size = sum(len(b[4].strip()) for b in blocks)
                result.spans = [
                    Span(id=f"{document_id}:p{i+1}:s{n}", document_id=document_id,
                         page=i + 1, text=b[4].strip(), bbox=list(pymupdf.Rect(b[:4]) * page.rotation_matrix), source="native",
                         clause=clause_label(b[4]))
                    for n, b in enumerate(blocks)
                ]
                if native_size < 40:
                    # Keep any known native text if OCR is unavailable or finds nothing.
                    scanned = ocr_spans(page, document_id, i + 1, len(result.spans))
                    if scanned:
                        result.spans = scanned
                if not result.spans:
                    result.status = "unreadable"
                    result.warnings.append("No legible text on this page. It may be blank or contain unreadable content.")
                if any(s.ocr_confidence is not None and s.ocr_confidence < 70 for s in result.spans):
                    result.warnings.append(LOW_OCR_WARNING)
            except Exception as error:
                result.status = "error"
                result.warnings.append(str(error) if isinstance(error, ValueError) else "Local OCR failed or timed out; this page has not been fully read.")
            pages.append(result)
            if progress:
                progress(pages, len(pdf))
    return pages


def save_pages(path: Path, pages: list[Page]):
    # Checkpoints must be complete JSON even if the process stops during a write.
    temporary = path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps([p.model_dump() for p in pages]), encoding="utf-8")
    os.replace(temporary, path)


def load_pages(path: Path) -> list[Page]:
    return [Page.model_validate(p) for p in json.loads(path.read_text(encoding="utf-8"))]


def render_page(pdf_path: Path, number: int) -> bytes:
    with pymupdf.open(pdf_path) as pdf:
        if number < 1 or number > len(pdf):
            raise ValueError("Page does not exist")
        page = pdf[number - 1]
        scale = min(2, 2200 / max(page.rect.width, page.rect.height))
        return page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False).tobytes("png")
