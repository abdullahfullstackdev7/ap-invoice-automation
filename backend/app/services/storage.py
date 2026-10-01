import secrets
from pathlib import Path

from app.core.settings import get_settings


def storage_path_for(original_filename: str) -> tuple[str, Path]:
    """Returns (relative_path, absolute_path) for a new upload.

    The on-disk name is randomized (never the client-supplied filename) so
    a predictable path can't be guessed, per Plan.md section 7.
    """
    settings = get_settings()
    suffix = Path(original_filename).suffix.lower()
    random_name = secrets.token_hex(24) + suffix
    relative = f"invoices/{random_name}"
    absolute = Path(settings.file_storage_path) / relative
    return relative, absolute


def write_file(absolute_path: Path, content: bytes) -> None:
    absolute_path.parent.mkdir(parents=True, exist_ok=True)
    absolute_path.write_bytes(content)


def read_file(relative_path: str) -> bytes:
    settings = get_settings()
    return (Path(settings.file_storage_path) / relative_path).read_bytes()
