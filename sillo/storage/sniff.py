"""
sillo.storage.sniff — decide what a file is from what is in it.

The declared type is not evidence.  ``Content-Type`` on an upload is a string
the uploader chose, and the interesting case is not a mistake — it is a file
whose bytes are HTML and whose declared type is ``image/png``.  Serve that
inline from your own origin and you have stored cross-site scripting.

So the sniffer decides, the declared type is recorded for comparison and never
used to serve, and the pairing is completed on the way out by
:mod:`sillo.storage.routes`, which sends ``X-Content-Type-Options: nosniff`` and
a ``Content-Disposition`` on everything.  Sniffing without those headers is
half a defence: the browser will re-sniff and reach its own conclusion.

Magic numbers rather than :mod:`mimetypes`, because ``mimetypes`` reads the
*extension*, which is the same string the uploader chose.

The table is short on purpose.  It covers what applications actually accept —
images, documents, archives, media — and anything unrecognised becomes
``application/octet-stream``, which browsers download rather than render.
Unknown falling back to "download it" is the safe direction.
"""

from __future__ import annotations

__all__ = ["FALLBACK", "PROBE_BYTES", "looks_textual", "sniff"]

#: What an unrecognised file is served as. Browsers download this rather than
#: rendering it, which is the right default for something we cannot identify.
FALLBACK = "application/octet-stream"

#: How much of the file the sniffer needs. Every signature below sits within
#: the first few dozen bytes; 4 kB is generous and is one read.
PROBE_BYTES = 4096

#: Offset, signature, content type. Ordered longest-first within each family so
#: a more specific match is found before a shorter one that would also match.
_SIGNATURES: tuple[tuple[int, bytes, str], ...] = (
    (0, b"\x89PNG\r\n\x1a\n", "image/png"),
    (0, b"\xff\xd8\xff", "image/jpeg"),
    (0, b"GIF89a", "image/gif"),
    (0, b"GIF87a", "image/gif"),
    (0, b"BM", "image/bmp"),
    (0, b"\x00\x00\x01\x00", "image/x-icon"),
    (0, b"%PDF-", "application/pdf"),
    (0, b"\x1f\x8b", "application/gzip"),
    (0, b"BZh", "application/x-bzip2"),
    (0, b"\xfd7zXZ\x00", "application/x-xz"),
    (0, b"7z\xbc\xaf\x27\x1c", "application/x-7z-compressed"),
    (0, b"Rar!\x1a\x07", "application/vnd.rar"),
    (0, b"OggS", "audio/ogg"),
    (0, b"fLaC", "audio/flac"),
    (0, b"ID3", "audio/mpeg"),
    (0, b"\x1aE\xdf\xa3", "video/webm"),
    (0, b"SQLite format 3\x00", "application/vnd.sqlite3"),
    (0, b"\x7fELF", "application/x-executable"),
    (0, b"\xca\xfe\xba\xbe", "application/java-vm"),
    # RIFF and ISO-BMFF carry their real type a few bytes in.
    (8, b"WEBP", "image/webp"),
    (8, b"WAVE", "audio/wav"),
    (8, b"AVI ", "video/x-msvideo"),
    (4, b"ftyp", "video/mp4"),
)

#: Markup a browser will execute if it is allowed to render it. Checked against
#: the *leading* bytes of anything that looks textual, because this is the
#: family that turns a permissive content type into an incident.
_MARKUP: tuple[tuple[bytes, str], ...] = (
    (b"<!doctype html", "text/html"),
    (b"<html", "text/html"),
    (b"<head", "text/html"),
    (b"<body", "text/html"),
    (b"<script", "text/html"),
    (b"<svg", "image/svg+xml"),
    (b"<?xml", "application/xml"),
)

#: Control characters that never appear in text a browser would render as
#: text. Tab, newline, carriage return and escape are deliberately absent.
_CONTROL = frozenset(bytes(range(9)) + bytes(range(14, 27)) + bytes(range(28, 32)))


def sniff(head: bytes, *, declared: str = "", key: str = "") -> str:
    """Decide what to serve a file as.

    Args:
        head: The first :data:`PROBE_BYTES` of the file, or all of it if it is
            shorter.
        declared: What the uploader claimed. Used only to break ties between
            two readings the sniffer considers equally safe — never to override
            what the bytes say.
        key: The object's key. Used only for the same tie-break, and only for
            types that cannot be told apart by content.

    Returns:
        The content type to store and serve.
    """
    if not head:
        # An empty file is not a threat and not a format. Calling it text would
        # be a guess; octet-stream is the honest answer.
        return FALLBACK

    for offset, signature, kind in _SIGNATURES:
        if head[offset : offset + len(signature)] == signature:
            return kind

    if b"\x00" in head[:512] or _has_binary(head[:512]):
        return FALLBACK

    # Textual. Markup first, because that is the family that matters: a file
    # beginning `<script>` is HTML however it was named or declared.
    lowered = head[:512].lstrip().lower()
    for prefix, kind in _MARKUP:
        if lowered.startswith(prefix):
            return kind

    return _textual(declared, key)


def _has_binary(head: bytes) -> bool:
    """Whether a run of bytes is not plausibly text.

    Two checks, and the second is the one that matters. A control character is
    conclusive. Beyond that, text has to *decode*: ``\xde\xad\xbe\xef`` contains
    no control characters and is not UTF-8, and a byte-set check alone called it
    text and served it as ``text/plain``.

    Args:
        head: Leading bytes.

    Returns:
        True when the content is not plausibly text.
    """
    if any(byte in _CONTROL for byte in head):
        return True

    try:
        head.decode("utf-8")
    except UnicodeDecodeError as error:
        # A probe cuts the file at a fixed offset, which can land in the middle
        # of a multi-byte character. A failure in the last few bytes is that,
        # not binary content.
        return error.start < len(head) - 4

    return False


def _textual(declared: str, key: str) -> str:
    """Name a textual file that carried no recognisable signature.

    This is the one place the declared type is consulted, and it can only ever
    choose between types that are all textual and none of which a browser will
    execute — so the worst outcome is a ``.csv`` served as ``text/plain``.

    Args:
        declared: What the uploader claimed.
        key: The object's key.

    Returns:
        A textual content type.
    """
    safe = {
        "text/plain",
        "text/csv",
        "text/markdown",
        "text/tab-separated-values",
        "application/json",
        "application/x-ndjson",
        "text/calendar",
        "text/vcard",
    }

    claim = declared.split(";", 1)[0].strip().lower()
    if claim in safe:
        return claim

    suffix = key.rsplit(".", 1)[-1].lower() if "." in key else ""
    return {
        "csv": "text/csv",
        "md": "text/markdown",
        "markdown": "text/markdown",
        "json": "application/json",
        "ndjson": "application/x-ndjson",
        "tsv": "text/tab-separated-values",
        "ics": "text/calendar",
        "vcf": "text/vcard",
    }.get(suffix, "text/plain")


def looks_textual(content_type: str) -> bool:
    """Whether a type is one a browser renders as text.

    Used by the serving route to decide whether a charset is worth stating.

    Args:
        content_type: The content type.

    Returns:
        True for text and the textual application types.
    """
    return content_type.startswith("text/") or content_type in {
        "application/json",
        "application/xml",
        "application/x-ndjson",
    }
