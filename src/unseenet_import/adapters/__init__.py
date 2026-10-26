"""Adapters: one per network, each turning that network's export into a ``Source``
(#1). An export is read where it lies - a zip or a folder on this machine - and never
uploaded (UN-RFC 0049 section 6.1).

    open_source(path, passphrase=None) -> Source     # finds the adapter itself

Each adapter has ``NETWORK``, ``recognise(files) -> bool`` (the names in the export)
and ``read(export) -> Source``.
"""

from __future__ import annotations

import html
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from ..model import Source


class Export:
    """The files of an export, from a zip or a folder, by their path inside it."""

    def __init__(self, path):
        self.path = Path(path)
        self._zip = None
        if self.path.is_dir():
            self._names = [p.relative_to(self.path).as_posix()
                           for p in self.path.rglob("*") if p.is_file()]
        else:
            self._zip = zipfile.ZipFile(self.path)
            self._names = [n for n in self._zip.namelist() if not n.endswith("/")]

    @classmethod
    def from_bytes(cls, data: bytes) -> "Export":
        import io
        self = cls.__new__(cls)
        self.path = Path("export.zip")
        self._zip = zipfile.ZipFile(io.BytesIO(data))
        self._names = [n for n in self._zip.namelist() if not n.endswith("/")]
        return self

    def names(self) -> list[str]:
        return list(self._names)

    def has(self, name: str) -> bool:
        return name in self._names

    def read(self, name: str) -> bytes:
        name = str(PurePosixPath(name)).lstrip("/")
        if name not in self._names:
            raise KeyError(name)
        if self._zip is not None:
            return self._zip.read(name)
        return (self.path / name).read_bytes()

    def find(self, pattern: str) -> list[str]:
        rx = re.compile(pattern)
        return sorted(n for n in self._names if rx.search(n))


# --- shared helpers -----------------------------------------------------------------
def from_epoch(ts) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(ts), timezone.utc)
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def from_iso(text) -> datetime | None:
    try:
        d = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d.astimezone(timezone.utc) if d.tzinfo else d.replace(tzinfo=timezone.utc)


_URL = re.compile(r"https?://[^\s<>\"')\]]+")


def links_in(text: str) -> list[str]:
    return list(dict.fromkeys(_URL.findall(text or "")))


def html_text(source: str) -> str:
    """HTML from a post (Mastodon's) as plain text with paragraphs and links kept."""
    s = re.sub(r"(?i)<br\s*/?>", "\n", source or "")
    s = re.sub(r"(?i)</p>\s*<p[^>]*>", "\n\n", s)
    def link(m):
        text = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        return text if text.startswith(("#", "@")) else m.group(1)    # tags and mentions as text
    s = re.sub(r'(?is)<a [^>]*href="([^"]+)"[^>]*>(.*?)</a>', link, s)
    s = re.sub(r"<[^>]+>", "", s)
    return html.unescape(s).strip()


def _adapters():
    from . import facebook, mastodon, unseenet
    return [unseenet, facebook, mastodon]


def recognise(export: Export):
    """The adapter module for an export, or None."""
    names = export.names()
    return next((a for a in _adapters() if a.recognise(names)), None)


def open_source(path, passphrase: str | None = None) -> Source:
    """Read an export: a zip, a folder, or an encrypted Unseenet export (``.sealed``,
    opened with ``passphrase``). ``ValueError`` when no adapter knows it."""
    p = Path(path)
    if p.name.endswith(".sealed"):
        from unseenet.core.vault import unseal
        if not passphrase:
            raise ValueError("this export is encrypted: give its passphrase")
        export = Export.from_bytes(unseal(p.read_bytes(), passphrase))
    else:
        export = Export(p)
    adapter = recognise(export)
    if adapter is None:
        raise ValueError("not an export this knows: Facebook (JSON), Mastodon, or Unseenet")
    return adapter.read(export)
