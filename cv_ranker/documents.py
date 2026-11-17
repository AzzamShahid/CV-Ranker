from pathlib import Path


SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf", ".docx"}


class DocumentError(RuntimeError):
    pass


def extract_text(path: str | Path) -> str:
    path = Path(path)
    if not path.exists():
        raise DocumentError(f"File not found: {path}")
    if not path.is_file():
        raise DocumentError(f"Expected a file but received: {path}")

    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise DocumentError(f"Unsupported file type: {suffix}")

    if suffix in {".txt", ".md"}:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            raise DocumentError(f"Could not read text file {path.name}: {exc}") from exc

    elif suffix == ".pdf":
        try:
            import fitz  # PyMuPDF
        except ImportError as exc:
            raise DocumentError("PyMuPDF is required for PDF files.") from exc
        try:
            with fitz.open(path) as doc:
                extracted_pages: list[str] = []
                unreadable_pages: list[int] = []
                for number, page in enumerate(doc, 1):
                    page_text = page.get_text("text")
                    extracted_pages.append(page_text)
                    if len(page_text.strip()) >= 20:
                        continue
                    # A text-rich page must not hide an image-only CV page.
                    # Large raster images imply *possible* unseen source data;
                    # small logos on otherwise blank pages are not sufficient.
                    extent = max(1.0, float(page.rect.get_area()))
                    if any((fitz.Rect(item["bbox"]).get_area() / extent) >= 0.15
                           for item in page.get_image_info()):
                        unreadable_pages.append(number)
                if unreadable_pages:
                    pages = ", ".join(str(p) for p in unreadable_pages)
                    raise DocumentError(
                        f"PDF {path.name} has potentially unreadable image-only "
                        f"page(s): {pages}. Review or transcribe those pages "
                        "before assessing qualifications; partial text is unsafe.")
                text = "\n".join(extracted_pages)
        except DocumentError:
            raise
        except Exception as exc:
            raise DocumentError(f"Could not read PDF {path.name}: {exc}") from exc

    else:  # .docx
        try:
            from docx import Document
        except ImportError as exc:
            raise DocumentError("python-docx is required for DOCX files.") from exc
        try:
            from docx.table import Table
            from docx.text.paragraph import Paragraph

            doc = Document(path)
            parts: list[str] = []
            # Headers/footers frequently contain the only degree/qualification
            # or employer data in legitimate CVs. Deduplicate linked headers
            # shared by multiple sections, but preserve original exact words.
            def iter_container(container):
                for child in container._element.iterchildren():
                    tag = child.tag.rsplit("}", 1)[-1]
                    if tag == "p":
                        value = Paragraph(child, container).text
                        if value.strip():
                            yield value
                    elif tag == "tbl":
                        table = Table(child, container)
                        for row in table.rows:
                            value = " | ".join(cell.text for cell in row.cells)
                            if value.strip():
                                yield value
            headers: list[str] = []
            footers: list[str] = []
            seen_parts: set[str] = set()
            for section in doc.sections:
                for name, destination in (("header", headers), ("footer", footers)):
                    container = getattr(section, name)
                    identity = str(container.part.partname)
                    if identity in seen_parts:
                        continue
                    seen_parts.add(identity)
                    destination.extend(iter_container(container))
            parts.extend(headers)
            # Preserve the actual DOCX body order. ``doc.paragraphs`` followed by
            # ``doc.tables`` destroys interleaving and can move Skills/Experience
            # evidence into the wrong context.
            for child in doc.element.body.iterchildren():
                tag = child.tag.rsplit("}", 1)[-1]
                if tag == "p":
                    value = Paragraph(child, doc).text
                    if value.strip():
                        parts.append(value)
                elif tag == "tbl":
                    table = Table(child, doc)
                    for row in table.rows:
                        value = " | ".join(cell.text for cell in row.cells)
                        if value.strip():
                            parts.append(value)
            parts.extend(footers)
            text = "\n".join(parts)
        except Exception as exc:
            raise DocumentError(f"Could not read DOCX {path.name}: {exc}") from exc

    if len(text.strip()) < 20:
        raise DocumentError(
            f"Very little extractable text in {path.name}. "
            "Scanned/image-only PDFs are not supported in this MVP."
        )
    return text


def collect_resume_paths(input_paths: list[str]) -> list[Path]:
    results: list[Path] = []
    for raw in input_paths:
        path = Path(raw)
        if path.is_dir():
            try:
                results.extend(
                    sorted(
                        p for p in path.iterdir()
                        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
                    )
                )
            except OSError:
                continue
        elif path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
            results.append(path)
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in results:
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path.absolute()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(path)
    return unique
