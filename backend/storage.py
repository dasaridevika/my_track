import os
import mimetypes
from pathlib import Path
import boto3
from botocore.config import Config
BUCKET_NAME = os.getenv("BUCKET")
BUCKET_ENDPOINT = os.getenv("ENDPOINT")
BUCKET_REGION = os.getenv("REGION", "auto")
ACCESS_KEY_ID = os.getenv("ACCESS_KEY_ID")
SECRET_ACCESS_KEY = os.getenv("SECRET_ACCESS_KEY")
def is_bucket_configured():
    return all([
        BUCKET_NAME,
        BUCKET_ENDPOINT,
        ACCESS_KEY_ID,
        SECRET_ACCESS_KEY,
    ])
def get_s3_client():
    if not is_bucket_configured():
        raise RuntimeError("Railway bucket is not configured correctly.")
    return boto3.client(
        "s3",
        endpoint_url=BUCKET_ENDPOINT,
        region_name=BUCKET_REGION,
        aws_access_key_id=ACCESS_KEY_ID,
        aws_secret_access_key=SECRET_ACCESS_KEY,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
        ),
    )
def upload_file(local_path: str, object_key: str):
    if not is_bucket_configured():
        raise RuntimeError("Bucket credentials are missing.")
    path = Path(local_path)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"File not found: {local_path}")
    s3 = get_s3_client()
    content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    with path.open("rb") as f:
        s3.upload_fileobj(
            f,
            BUCKET_NAME,
            object_key,
            ExtraArgs={"ContentType": content_type},
        )

    return {
        "bucket": BUCKET_NAME,
        "key": object_key,
        "content_type": content_type,
        "filename": path.name,
    }


def get_download_url(object_key: str, expires_in: int = 3600, filename: str | None = None):
    if not is_bucket_configured():
        raise RuntimeError("Bucket credentials are missing.")

    s3 = get_s3_client()

    params = {
        "Bucket": BUCKET_NAME,
        "Key": object_key,
    }

    if filename:
        params["ResponseContentDisposition"] = f'attachment; filename="{filename}"'
    return s3.generate_presigned_url(
        "get_object",
        Params=params,
        ExpiresIn=expires_in,
    )
