import os
import mimetypes
import uuid
from pathlib import Path
from urllib.parse import urlparse

import boto3
from botocore.config import Config

def get_bucket_settings():
    return {
        "bucket": os.getenv("BUCKET") or os.getenv("AWS_S3_BUCKET_NAME"),
        "endpoint": os.getenv("ENDPOINT") or os.getenv("AWS_ENDPOINT_URL"),
        "region": os.getenv("REGION") or os.getenv("AWS_DEFAULT_REGION") or "auto",
        "access_key_id": os.getenv("ACCESS_KEY_ID") or os.getenv("AWS_ACCESS_KEY_ID"),
        "secret_access_key": os.getenv("SECRET_ACCESS_KEY") or os.getenv("AWS_SECRET_ACCESS_KEY"),
        "url_style": (os.getenv("URL_STYLE") or os.getenv("AWS_S3_URL_STYLE") or "virtual").lower(),
        "prefix": os.getenv("S3_PREFIX", "").strip("/"),
    }

def is_bucket_configured():
    settings = get_bucket_settings()
    return all([
        settings["bucket"],
        settings["endpoint"],
        settings["access_key_id"],
        settings["secret_access_key"],
    ])

def get_s3_client():
    settings = get_bucket_settings()
    if not is_bucket_configured():
        raise RuntimeError("Railway bucket is not configured correctly.")

    return boto3.client(
        "s3",
        endpoint_url=settings["endpoint"],
        region_name=settings["region"],
        aws_access_key_id=settings["access_key_id"],
        aws_secret_access_key=settings["secret_access_key"],
        config=Config(
            signature_version="s3v4",
            s3={
                "addressing_style": "virtual" if settings["url_style"] == "virtual" else "path"
            },
        ),
    )

def make_object_key(category: str, source_url: str, filename: str):
    settings = get_bucket_settings()
    parsed = urlparse(source_url)
    domain = (parsed.netloc or "unknown-source").replace(":", "_")
    category = category.strip("/")
    filename = Path(filename).name
    key = f"{category}/{domain}/{uuid.uuid4().hex}/{filename}"

    if settings["prefix"]:
        return f"{settings['prefix']}/{key}"

    return key

def upload_file(local_path: str, object_key: str):
    if not is_bucket_configured():
        raise RuntimeError("Bucket credentials are missing.")

    settings = get_bucket_settings()
    path = Path(local_path)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"File not found: {local_path}")

    s3 = get_s3_client()
    content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"

    with path.open("rb") as f:
        s3.upload_fileobj(
            f,
            settings["bucket"],
            object_key,
            ExtraArgs={"ContentType": content_type},
        )

    download_url = get_download_url(object_key, filename=path.name)

    return {
        "bucket": settings["bucket"],
        "key": object_key,
        "s3_uri": f"s3://{settings['bucket']}/{object_key}",
        "url": download_url,
        "content_type": content_type,
        "filename": path.name,
        "storage": "bucket",
    }

def get_download_url(object_key: str, expires_in: int = 3600, filename: str | None = None):
    if not is_bucket_configured():
        raise RuntimeError("Bucket credentials are missing.")

    settings = get_bucket_settings()
    s3 = get_s3_client()
    params = {
        "Bucket": settings["bucket"],
        "Key": object_key,
    }

    if filename:
        params["ResponseContentDisposition"] = f'attachment; filename="{filename}"'

    return s3.generate_presigned_url(
        "get_object",
        Params=params,
        ExpiresIn=expires_in,
    )
