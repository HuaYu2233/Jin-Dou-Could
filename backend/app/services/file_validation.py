import asyncio
import re

from app.core.exceptions import ValidationFailed

_FILENAME_MAX_LEN = 255
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")
_PATH_SEP_RE = re.compile(r"[\\/]+")

ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "image/bmp",
    "image/svg+xml",
    "video/mp4",
    "video/webm",
    "video/x-msvideo",
    "video/quicktime",
    "audio/mpeg",
    "audio/wav",
    "audio/ogg",
    "audio/x-m4a",
    "audio/flac",
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "text/plain",
    "text/csv",
    "text/html",
    "application/zip",
    "application/x-rar-compressed",
    "application/x-7z-compressed",
    "application/gzip",
    "application/x-gzip",
    "application/x-tar",
    "application/x-bzip2",
    "application/x-xz",
    "application/octet-stream",
}

_DOCUMENT_MIME_PREFIXES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument",
    "application/vnd.ms-excel",
    "application/vnd.ms-powerpoint",
}
_ARCHIVE_MIME_TYPES = {
    "application/zip",
    "application/x-rar-compressed",
    "application/x-7z-compressed",
    "application/gzip",
    "application/x-gzip",
    "application/x-tar",
    "application/x-bzip2",
    "application/x-xz",
}

_MIME_ALIASES = {
    ("audio/mpeg", "audio/mp3"),
    ("video/mp4", "application/mp4"),
}
_ALIAS_TO_CANONICAL = {alias: canonical for canonical, alias in _MIME_ALIASES}
_TEXT_SUBTYPE_FALLBACK = "text/plain"


def _canonical_mime(mime_type: str) -> str:
    canonical = _ALIAS_TO_CANONICAL.get(mime_type, mime_type)
    if canonical.startswith("text/") and canonical not in ALLOWED_MIME_TYPES:
        return _TEXT_SUBTYPE_FALLBACK
    return canonical


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
    except Exception as exc:
        raise ValidationFailed("文件类型检测组件不可用") from exc

    try:
        if hasattr(fileobj, "seek"):
            fileobj.seek(0)
        head = fileobj.read(2048)
        if hasattr(fileobj, "seek"):
            fileobj.seek(0)
    except Exception as exc:
        raise ValidationFailed("无法读取文件内容进行类型检测") from exc

    if isinstance(head, str):
        head = head.encode("utf-8")
    if not head:
        return declared

    try:
        detected = await asyncio.to_thread(magic.from_buffer, head, True)
    except Exception as exc:
        raise ValidationFailed("文件类型检测失败") from exc
    return detected or declared


def ensure_mime_allowed(mime_type: str, allowed: set[str] | None = None) -> None:
    canonical = _canonical_mime(mime_type)
    if canonical not in (ALLOWED_MIME_TYPES if allowed is None else allowed):
        raise ValidationFailed(f"不允许的文件类型: {mime_type}")


def validate_mime_type(declared: str, detected: str) -> None:
    detected_canonical = _canonical_mime(detected)
    if detected_canonical not in ALLOWED_MIME_TYPES:
        raise ValidationFailed(f"不允许的文件类型: {detected}")
    if declared and declared in ALLOWED_MIME_TYPES and not _is_compatible_mime(declared, detected_canonical):
        raise ValidationFailed(f"文件类型与声明不符: 声明 {declared}, 实际 {detected}")


def _is_compatible_mime(declared: str, detected: str) -> bool:
    declared_canonical = _canonical_mime(declared)
    if declared_canonical == detected:
        return True
    if declared_canonical == "application/octet-stream":
        return True
    return (declared_canonical, detected) in _MIME_ALIASES or (detected, declared_canonical) in _MIME_ALIASES


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
