"""
File Validation & Security Sanitizer for Vertex Construction & PCCC
Enforces strict file type whitelisting, Magic Bytes signature verification,
Maximum File Size protection (50MB), and Path Traversal prevention.
"""
import re
import os
from pathlib import Path
from typing import Tuple
from fastapi import UploadFile, HTTPException, status

ALLOWED_EXTENSIONS = {".xlsx", ".xls", ".dxf", ".dwg", ".pdf", ".csv"}
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB

# Magic byte signatures
MAGIC_SIGNATURES = {
    ".xlsx": [b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"],
    ".xls": [b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"],
    ".pdf": [b"%PDF-"],
    ".dwg": [b"AC10", b"AC00", b"AC", b"AutoCAD"]
}


class FileValidator:
    """
    Validates uploaded file authenticity and prevents malicious uploads.
    """

    @classmethod
    def sanitize_filename(cls, filename: str) -> str:
        """
        Removes path traversal attempts (../, null bytes, shell characters).
        """
        if not filename:
            return "uploaded_file.xlsx"

        # Remove path separators
        base_name = Path(filename).name
        # Remove null bytes
        base_name = base_name.replace("\x00", "").strip()
        # Keep alphanumeric, dots, dashes, underscores, spaces
        cleaned = re.sub(r"[^a-zA-Z0-9._\-\s]", "_", base_name)
        # Collapse repeated underscores
        cleaned = re.sub(r"_+", "_", cleaned).strip("._ ")
        return cleaned if cleaned else "boq_file.xlsx"

    @classmethod
    async def validate_and_save(
        cls,
        upload_file: UploadFile,
        destination_dir: str
    ) -> Tuple[str, str]:
        """
        Validates file extension, magic bytes, size limit, and saves to storage asynchronously.
        Returns: (saved_absolute_path, clean_original_filename)
        """
        original_name = upload_file.filename or "unknown_file"
        clean_name = cls.sanitize_filename(original_name)
        ext = Path(clean_name).suffix.lower()

        # 1. Extension Whitelist Check
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Định dạng tệp '{ext}' không được hỗ trợ! Chỉ chấp nhận: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
            )

        # 2. Read first chunk for Magic Byte verification
        header_chunk = await upload_file.read(2048)
        if not header_chunk:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tệp tải lên rỗng (0 bytes)!"
            )

        # Validate Magic Bytes for binary formats
        if ext in MAGIC_SIGNATURES:
            signatures = MAGIC_SIGNATURES[ext]
            valid_sig = any(header_chunk.startswith(sig) for sig in signatures)
            if not valid_sig:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Nội dung tệp không hợp lệ! Tệp '{clean_name}' không phải là định dạng chuẩn {ext.upper()}."
                )

        # Validate Text formats (.dxf, .csv)
        if ext in {".dxf", ".csv"}:
            if b"\x00" in header_chunk:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Tệp chứa dữ liệu nhị phân không hợp lệ cho định dạng bản vẽ CAD/CSV!"
                )

        # 3. Stream to destination file with Max File Size enforcement
        Path(destination_dir).mkdir(parents=True, exist_ok=True)
        unique_prefix = str(int(os.path.getmtime("."))) if os.path.exists(".") else "upload"
        import time
        unique_prefix = f"{int(time.time())}"
        target_filename = f"{unique_prefix}_{clean_name}"
        save_path = Path(destination_dir) / target_filename

        total_bytes = len(header_chunk)
        if total_bytes > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Dung lượng tệp vượt quá giới hạn cho phép (Tối đa {MAX_FILE_SIZE_BYTES // (1024 * 1024)}MB)!"
            )

        with open(save_path, "wb") as f_out:
            f_out.write(header_chunk)
            
            # Read in 64KB chunks
            while True:
                chunk = await upload_file.read(65536)
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > MAX_FILE_SIZE_BYTES:
                    f_out.close()
                    if save_path.exists():
                        save_path.unlink()
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"Dung lượng tệp vượt quá giới hạn tối đa {MAX_FILE_SIZE_BYTES // (1024 * 1024)}MB!"
                    )
                f_out.write(chunk)

        # Reset upload file pointer
        await upload_file.seek(0)

        return str(save_path), clean_name
