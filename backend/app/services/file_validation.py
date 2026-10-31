import asyncio
import re

from app.core.exceptions import ValidationFailed

_FILENAME_MAX_LEN = 255
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")
_PATH_SEP_RE = re.compile(r"[\\/]+")

ALLOWED_MIME_TYPES = {
    "image/jpeg", "image/png", "image/gif", "image/webp", "image/bmp", "image/svg+xml",
    "video/mp4", "video/webm", "video/x-msvideo", "video/quicktime",
    "audio/mpeg", "audio/wav", "audio/ogg", "audio/x-m4a", "audio/flac",
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "text/plain", "text/csv", "text/html",
    "application/zip", "application/x-rar-compressed", "application/x-7z-compressed",
    "application/octet-stream",
}

_DOCUMENT_MIME_PREFIXES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument",
    "application/vnd.ms-excel",
    "application/vnd.ms-powerpoint",
}
_ARCHIVE_MIME_TYPES = {"application/zip", "application/x-rar-compressed", "application/x-7z-compressed"}

_MIME_ALIASES = {
    ("audio/mpeg", "audio/mp3"),
    ("video/mp4", "application/mp4"),
}


def sanitize_filename(name: str) -> str:
    name = _PATH_SEP_RE.sub("_", name)
    name = _CONTROL_CHARS_RE.sub("", name)
    name = name.strip(" .")
    if not name:
        name = "unknown"
    return name[:_FILENAME_MAX_LEN]


async def detect_real_mime_type(fileobj, declared: str) -> str:
    try:
        import magic
        try:
            if hasattr(fileobj, "seek"):
                fileobj.seek(0)
            head = fileobj.read(2048)
            if hasattr(fileobj, "seek"):
                fileobj.seek(0)
        except Exception:
            head = None
        if head:
            if isinstance(head, str):
                head = head.encode("utf-8")
            detected = await asyncio.to_thread(magic.from_buffer, head, True)
            if detected and detected in ALLOWED_MIME_TYPES:
                return detected
    except Exception:
        pass
    return declared


def validate_mime_type(declared: str, detected: str) -> None:
    if detected not in ALLOWED_MIME_TYPES:
        raise ValidationFailed(f"不允许的文件类型: {detected}")
    if declared and declared in ALLOWED_MIME_TYPES and declared != detected:
        if not _is_compatible_mime(declared, detected):
            raise ValidationFailed(f"文件类型与声明不符: 声明 {declared}, 实际 {detected}")


def _is_compatible_mime(declared: str, detected: str) -> bool:
    if declared == detected:
        return True
    if declared == "application/octet-stream":
        return True
    return (declared, detected) in _MIME_ALIASES or (detected, declared) in _MIME_ALIASES


def categorize_file_type(mime_type: str) -> str:
    if mime_type.startswith("image/"):
        return "image"
    if mime_type.startswith("video/"):
        return "video"
    if mime_type.startswith("audio/"):
        return "audio"
    if mime_type.startswith("text/"):
        return "document"
    if any(mime_type == p or mime_type.startswith(p + ".") for p in _DOCUMENT_MIME_PREFIXES):
        return "document"
    if mime_type in _ARCHIVE_MIME_TYPES:
        return "archive"
    return "other"