import os
import mimetypes
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
    return boto3.client(
        "s3",
        endpoint_url=BUCKET_ENDPOINT,
        region_name=BUCKET_REGION,
        aws_access_key_id=ACCESS_KEY_ID,
        aws_secret_access_key=SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4"),
    )

def upload_file(local_path: str, object_key: str):
    s3 = get_s3_client()
    content_type = mimetypes.guess_type(local_path)[0] or "application/octet-stream"

    with open(local_path, "rb") as f:
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
    }

def get_download_url(object_key: str, expires_in: int = 3600):
    s3 = get_s3_client()
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": BUCKET_NAME, "Key": object_key},
        ExpiresIn=expires_in,
    )
