from fastapi import HTTPException, UploadFile

from app.constants import MAX_UPLOAD_SIZE_BYTES


async def read_upload_with_size_limit(
    upload_file: UploadFile, max_bytes: int = MAX_UPLOAD_SIZE_BYTES
) -> bytes:
    chunks = []
    total_size = 0
    while True:
        chunk = await upload_file.read(1024 * 1024)
        if not chunk:
            break
        total_size += len(chunk)
        if total_size > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"File is too large. Maximum allowed size is {max_bytes // (1024 * 1024)} MB.",
            )
        chunks.append(chunk)
    return b"".join(chunks)
