import asyncio
import httpx
import json
import logging
import mimetypes
import os
import tempfile
import uuid
from urllib.parse import urlparse

import boto3
import fitz
import pandas as pd
from botocore.config import Config
from botocore.exceptions import ClientError, NoCredentialsError
from docx import Document
from lxml import etree
from pptx import Presentation

from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from crawl4ai.content_scraping_strategy import LXMLWebScrapingStrategy
from crawl4ai.deep_crawling import BestFirstCrawlingStrategy
from crawl4ai.deep_crawling.filters import FilterChain, ContentTypeFilter
from crawl4ai.deep_crawling.scorers import KeywordRelevanceScorer

try:
    from storage import (
        is_bucket_configured as storage_is_bucket_configured,
        make_object_key,
        upload_file,
    )
except ModuleNotFoundError:
    from backend.storage import (
        is_bucket_configured as storage_is_bucket_configured,
        make_object_key,
        upload_file,
    )

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)

SUPPORTED_TYPES = {
    ".html": "html",
    ".htm": "html",
    ".php": "html",
    ".asp": "html",
    ".aspx": "html",
    ".pdf": "pdf",
    ".csv": "csv",
    ".xls": "excel",
    ".xlsx": "excel",
    ".doc": "docx",
    ".docx": "docx",
    ".ppt": "pptx",
    ".pptx": "pptx",
    ".txt": "txt",
    ".json": "json",
    ".xml": "xml",
}


def get_bucket_settings():
    return {
        "bucket_name": os.getenv("BUCKET") or os.getenv("AWS_S3_BUCKET_NAME"),
        "endpoint_url": os.getenv("ENDPOINT") or os.getenv("AWS_ENDPOINT_URL"),
        "access_key_id": os.getenv("ACCESS_KEY_ID") or os.getenv("AWS_ACCESS_KEY_ID"),
        "secret_access_key": os.getenv("SECRET_ACCESS_KEY") or os.getenv("AWS_SECRET_ACCESS_KEY"),
        "region": os.getenv("REGION") or os.getenv("AWS_DEFAULT_REGION") or "auto",
        "url_style": (os.getenv("URL_STYLE") or os.getenv("AWS_S3_URL_STYLE") or "virtual").lower(),
        "prefix": os.getenv("S3_PREFIX", "deep-crawl/"),
    }


def is_bucket_configured():
    return storage_is_bucket_configured()


def get_s3_client_and_bucket():
    s = get_bucket_settings()

    if not all([s["bucket_name"], s["endpoint_url"], s["access_key_id"], s["secret_access_key"]]):
        raise RuntimeError(
            "Railway bucket is not configured. "
            "Set BUCKET/ENDPOINT/ACCESS_KEY_ID/SECRET_ACCESS_KEY "
            "or AWS_S3_BUCKET_NAME/AWS_ENDPOINT_URL/AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY."
        )

    client = boto3.client(
        "s3",
        endpoint_url=s["endpoint_url"],
        aws_access_key_id=s["access_key_id"],
        aws_secret_access_key=s["secret_access_key"],
        region_name=s["region"],
        config = CrawlerRunConfig(
    deep_crawl_strategy=BFSDeepCrawlStrategy(
        max_depth=1,
        max_pages=10,
        include_external=False,
    ),
    scraping_strategy=LXMLWebScrapingStrategy(),
    verbose=False,
    page_timeout=30000,
    wait_until="domcontentloaded",
),
    )
    return client, s["bucket_name"], s["prefix"]


def validate_url(url: str):
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Only HTTP and HTTPS URLs are allowed.")
    if not parsed.netloc:
        raise ValueError("Invalid URL.")


def build_response(success: bool, file_type: str, data=None, message=""):
    return {
        "success": success,
        "file_type": file_type,
        "message": message,
        "data": data
    }


def guess_content_type(file_path: str, fallback="application/octet-stream"):
    content_type, _ = mimetypes.guess_type(file_path)
    return content_type or fallback


def make_s3_key(file_type: str, original_url: str, suffix: str):
    filename = f"{file_type}{suffix}"
    return make_object_key(f"deep-crawl/{file_type}", original_url, filename)


def upload_file_to_s3(local_path: str, s3_key: str, content_type: str = None):
    try:
        return upload_file(local_path, s3_key)
    except NoCredentialsError:
        raise RuntimeError("Railway bucket credentials are not configured.")
    except ClientError as e:
        raise RuntimeError(f"S3 upload failed: {e}")
    except Exception as e:
        raise RuntimeError(f"Storage upload failed: {e}")


def upload_json_to_s3(data: dict, s3_key: str):
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w", encoding="utf-8") as tf:
            json.dump(data, tf, ensure_ascii=False, indent=2, default=str)
            temp_path = tf.name
        return upload_file_to_s3(temp_path, s3_key, "application/json")
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


def maybe_upload_file(local_path: str, file_type: str, url: str, suffix: str, content_type: str):
    if not is_bucket_configured():
        return None
    s3_key = make_s3_key(file_type, url, suffix)
    return upload_file_to_s3(local_path, s3_key, content_type)


def maybe_upload_json(data: dict, file_type: str, url: str, suffix: str):
    if not is_bucket_configured():
        return None
    s3_key = make_s3_key(file_type, url, suffix)
    return upload_json_to_s3(data, s3_key)


async def detect_file_type(url: str):
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
            response = await client.head(url)
            content_type = response.headers.get("content-type", "").lower()

            if not content_type:
                response = await client.get(url, headers={"Range": "bytes=0-0"})
                content_type = response.headers.get("content-type", "").lower()

            if "text/html" in content_type:
                return "html"
            elif "application/pdf" in content_type:
                return "pdf"
            elif "spreadsheet" in content_type or "excel" in content_type:
                return "excel"
            elif "csv" in content_type:
                return "csv"
            elif "word" in content_type or "officedocument.wordprocessingml" in content_type:
                return "docx"
            elif "presentation" in content_type or "officedocument.presentationml" in content_type:
                return "pptx"
            elif "json" in content_type:
                return "json"
            elif "xml" in content_type:
                return "xml"
            elif "text/plain" in content_type:
                return "txt"
    except Exception as e:
        logger.warning(f"HTTP detection failed: {e}")

    extension = os.path.splitext(urlparse(url).path)[1].lower()
    return SUPPORTED_TYPES.get(extension, "html")


async def download_file(url: str, suffix: str):
    async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as client:
        response = await client.get(url)
        response.raise_for_status()

        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        temp_file.write(response.content)
        temp_file.close()
        return temp_file.name


async def extract_json(url: str):
    temp_path = await download_file(url, ".json")
    try:
        s3_info = maybe_upload_file(temp_path, "json", url, ".json", "application/json")

        with open(temp_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return build_response(
            True,
            "json",
            {
                "s3": s3_info,
                "content": data
            }
        )
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


async def extract_xml(url: str):
    temp_path = await download_file(url, ".xml")
    try:
        s3_info = maybe_upload_file(temp_path, "xml", url, ".xml", "application/xml")

        tree = etree.parse(temp_path)
        root = tree.getroot()

        return build_response(
            True,
            "xml",
            {
                "s3": s3_info,
                "content": etree.tostring(root, pretty_print=True, encoding="unicode")
            }
        )
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


async def extract_pdf(url: str):
    logger.info(f"Extracting PDF: {url}")
    temp_path = await download_file(url, ".pdf")
    try:
        s3_info = maybe_upload_file(temp_path, "pdf", url, ".pdf", "application/pdf")

        document = fitz.open(temp_path)
        pages = []
        full_text = ""

        for page_number, page in enumerate(document):
            text = page.get_text()
            pages.append({
                "page": page_number + 1,
                "text": text
            })
            full_text += text + "\n"

        document.close()

        return build_response(
            True,
            "pdf",
            {
                "s3": s3_info,
                "page_count": len(pages),
                "pages": pages,
                "text": full_text
            }
        )
    except Exception as e:
        logger.exception(e)
        return build_response(False, "pdf", None, str(e))
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


async def extract_excel(url: str):
    logger.info(f"Extracting Excel: {url}")
    temp_path = await download_file(url, ".xlsx")
    try:
        s3_info = maybe_upload_file(
            temp_path,
            "excel",
            url,
            ".xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        excel = pd.ExcelFile(temp_path)
        sheets = {}

        for sheet in excel.sheet_names:
            df = pd.read_excel(temp_path, sheet_name=sheet)
            sheets[sheet] = {
                "rows": len(df),
                "columns": list(df.columns),
                "preview": df.head(10).to_dict(orient="records")
            }

        return build_response(
            True,
            "excel",
            {
                "s3": s3_info,
                "sheets": sheets
            }
        )
    except Exception as e:
        logger.exception(e)
        return build_response(False, "excel", None, str(e))
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


async def extract_csv(url: str):
    temp_path = await download_file(url, ".csv")
    try:
        s3_info = maybe_upload_file(temp_path, "csv", url, ".csv", "text/csv")

        df = pd.read_csv(temp_path)

        return build_response(
            True,
            "csv",
            {
                "s3": s3_info,
                "rows": len(df),
                "columns": list(df.columns),
                "preview": df.head(10).to_dict(orient="records")
            }
        )
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


async def extract_docx(url: str):
    temp_path = await download_file(url, ".docx")
    try:
        s3_info = maybe_upload_file(
            temp_path,
            "docx",
            url,
            ".docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

        document = Document(temp_path)
        text = "\n".join(para.text for para in document.paragraphs)

        return build_response(
            True,
            "docx",
            {
                "s3": s3_info,
                "text": text
            }
        )
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


async def extract_pptx(url: str):
    temp_path = await download_file(url, ".pptx")
    try:
        s3_info = maybe_upload_file(
            temp_path,
            "pptx",
            url,
            ".pptx",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        )

        presentation = Presentation(temp_path)
        slides = []

        for slide_number, slide in enumerate(presentation.slides):
            text = []
            for shape in slide.shapes:
                if hasattr(shape, "text"):
                    text.append(shape.text)
            slides.append({
                "slide": slide_number + 1,
                "text": "\n".join(text)
            })

        return build_response(
            True,
            "pptx",
            {
                "s3": s3_info,
                "slides": slides
            }
        )
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


async def extract_txt(url: str):
    temp_path = await download_file(url, ".txt")
    try:
        s3_info = maybe_upload_file(temp_path, "txt", url, ".txt", "text/plain")

        with open(temp_path, "r", encoding="utf-8", errors="ignore") as file:
            text = file.read()

        return build_response(
            True,
            "txt",
            {
                "s3": s3_info,
                "text": text
            }
        )
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


async def extract_webpage(url: str):
    logger.info(f"Starting deep crawl for {url}")
    try:
        keyword_scorer = KeywordRelevanceScorer(
            keywords=["news", "press", "media", "news-releases"],
            weight=0.7
        )

        filter_chain = FilterChain([
            ContentTypeFilter(allowed_types=["text/html"])
        ])

        config = CrawlerRunConfig(
            deep_crawl_strategy=BestFirstCrawlingStrategy(
                max_depth=1,
                max_pages=3,
                include_external=False,
                filter_chain=filter_chain,
                url_scorer=keyword_scorer
            ),
            scraping_strategy=LXMLWebScrapingStrategy(),
            verbose=False,
            page_timeout=20000
        )

        async with asyncio.timeout(80):
            async with AsyncWebCrawler() as crawler:
                result = await crawler.arun(url=url, config=config)

        output = {
            "url": getattr(result, "url", url),
            "title": getattr(result, "title", None),
            "markdown": getattr(result, "markdown", None),
            "html": getattr(result, "html", None),
            "metadata": getattr(result, "metadata", {}),
            "links": getattr(result, "links", {}),
            "media": getattr(result, "media", {})
        }

        s3_info = maybe_upload_json(output, "html", url, ".json")

        return build_response(
            True,
            "html",
            {
                "s3": s3_info,
                "crawl_result": output
            }
        )
    except asyncio.TimeoutError:
        logger.warning(f"Crawl reached timeout for {url}")
        return build_response(False, "html", None, "Crawl reached timeout limit.")
    except Exception as e:
        logger.exception(e)
        return build_response(False, "html", None, str(e))


async def deep_crawl(url: str):
    try:
        validate_url(url)
        file_type = await detect_file_type(url)
        logger.info(f"Detected file type: {file_type}")

        if file_type == "html":
            return await extract_webpage(url)
        elif file_type == "pdf":
            return await extract_pdf(url)
        elif file_type == "excel":
            return await extract_excel(url)
        elif file_type == "csv":
            return await extract_csv(url)
        elif file_type == "docx":
            return await extract_docx(url)
        elif file_type == "pptx":
            return await extract_pptx(url)
        elif file_type == "txt":
            return await extract_txt(url)
        elif file_type == "json":
            return await extract_json(url)
        elif file_type == "xml":
            return await extract_xml(url)
        else:
            return build_response(
                False,
                file_type,
                None,
                f"Unsupported file type: {file_type}"
            )
    except Exception as e:
        logger.exception(e)
        return build_response(False, "unknown", None, str(e))


if __name__ == "__main__":
    TEST_URL = "https://www.geeksforgeeks.org/"

    async def main():
        result = await deep_crawl(TEST_URL)
        print(json.dumps(result, indent=4, default=str))

    asyncio.run(main())
