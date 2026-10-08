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
                text = "\n".join(page.get_text("text") for page in doc)
        except Exception as exc:
            raise DocumentError(f"Could not read PDF {path.name}: {exc}") from exc

    else:  # .docx
        try:
            from docx import Document
        except ImportError as exc:
            raise DocumentError("python-docx is required for DOCX files.") from exc
        try:
            doc = Document(path)
            parts = [p.text for p in doc.paragraphs]
            for table in doc.tables:
                for row in table.rows:
                    parts.append(" | ".join(cell.text for cell in row.cells))
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
