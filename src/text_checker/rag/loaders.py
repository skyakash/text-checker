from __future__ import annotations

from pathlib import Path

SUPPORTED_EXTENSIONS = {".md", ".markdown", ".txt", ".html", ".htm", ".pdf"}


class UnsupportedFormatError(ValueError):
    pass


def load(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in {".md", ".markdown", ".txt"}:
        return path.read_text(encoding="utf-8")
    if ext in {".html", ".htm"}:
        return _load_html(path)
    if ext == ".pdf":
        return _load_pdf(path)
    raise UnsupportedFormatError(f"unsupported file extension: {ext}")


def _load_html(path: Path) -> str:
    from bs4 import BeautifulSoup

    html = path.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)


def _load_pdf(path: Path) -> str:
    import pdfplumber

    parts: list[str] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                parts.append(page_text)
    return "\n\n".join(parts)


def discover(root: Path, recursive: bool = False) -> list[Path]:
    if root.is_file():
        return [root] if root.suffix.lower() in SUPPORTED_EXTENSIONS else []
    if not root.is_dir():
        return []
    pattern = "**/*" if recursive else "*"
    return sorted(
        p for p in root.glob(pattern)
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
    )
