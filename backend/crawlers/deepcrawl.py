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
from botocore.exceptions import ClientError, NoCredentialsError
from botocore.config import Config
from docx import Document
from lxml import etree
from pptx import Presentation
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from crawl4ai.content_scraping_strategy import LXMLWebScrapingStrategy
from crawl4ai.deep_crawling import BestFirstCrawlingStrategy
from crawl4ai.deep_crawling.filters import FilterChain, ContentTypeFilter
from crawl4ai.deep_crawling.scorers import KeywordRelevanceScorer
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
S3_BUCKET_NAME = os.getenv("BUCKET")
S3_ENDPOINT_URL = os.getenv("ENDPOINT")
S3_ACCESS_KEY_ID = os.getenv("ACCESS_KEY_ID")
S3_SECRET_ACCESS_KEY = os.getenv("SECRET_ACCESS_KEY")
S3_REGION = os.getenv("REGION", "auto")
S3_URL_STYLE = os.getenv("URL_STYLE", "virtual").lower()
S3_PREFIX = os.getenv("S3_PREFIX", "deep-crawl/")

if not S3_BUCKET_NAME:
    raise ValueError("Missing Railway BUCKET env var.")
if not S3_ENDPOINT_URL:
    raise ValueError("Missing Railway ENDPOINT env var.")
if not S3_ACCESS_KEY_ID or not S3_SECRET_ACCESS_KEY:
    raise ValueError("Missing Railway access credentials.")
s3 = boto3.client(
    "s3",
    endpoint_url=S3_ENDPOINT_URL,
    aws_access_key_id=S3_ACCESS_KEY_ID,
    aws_secret_access_key=S3_SECRET_ACCESS_KEY,
    region_name=S3_REGION,
    config=Config(
        s3={"addressing_style": "virtual" if S3_URL_STYLE == "virtual" else "path"}
    ),
)
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
    parsed = urlparse(original_url)
    domain = parsed.netloc.replace(":", "_")
    file_id = uuid.uuid4().hex
    return f"{S3_PREFIX}{file_type}/{domain}/{file_id}{suffix}"
def upload_file_to_s3(local_path: str, s3_key: str, content_type: str = None):
    if not S3_BUCKET_NAME:
        raise ValueError("S3_BUCKET_NAME environment variable is not set.")
    extra_args = {}
    if content_type:
        extra_args["ContentType"] = content_type
    try:
        s3.upload_file(
            local_path,
            S3_BUCKET_NAME,
            s3_key,
            ExtraArgs=extra_args if extra_args else None
        )
        return {
            "bucket": S3_BUCKET_NAME,
            "key": s3_key,
            "s3_uri": f"s3://{S3_BUCKET_NAME}/{s3_key}"
        }
    except NoCredentialsError:
        raise Exception("AWS credentials not configured.")
    except ClientError as e:
        raise Exception(f"S3 upload failed: {e}")
def upload_json_to_s3(data: dict, s3_key: str):
    if not S3_BUCKET_NAME:
        raise ValueError("S3_BUCKET_NAME environment variable is not set.")
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w", encoding="utf-8") as tf:
            json.dump(data, tf, ensure_ascii=False, indent=2, default=str)
            temp_path = tf.name
        return upload_file_to_s3(temp_path, s3_key, "application/json")
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
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
        s3_key = make_s3_key("json", url, ".json")
        s3_info = upload_file_to_s3(temp_path, s3_key, "application/json")

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
        s3_key = make_s3_key("xml", url, ".xml")
        s3_info = upload_file_to_s3(temp_path, s3_key, "application/xml")
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
        s3_key = make_s3_key("pdf", url, ".pdf")
        s3_info = upload_file_to_s3(temp_path, s3_key, "application/pdf")
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
        s3_key = make_s3_key("excel", url, ".xlsx")
        s3_info = upload_file_to_s3(
            temp_path,
            s3_key,
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
        s3_key = make_s3_key("csv", url, ".csv")
        s3_info = upload_file_to_s3(temp_path, s3_key, "text/csv")

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
        s3_key = make_s3_key("docx", url, ".docx")
        s3_info = upload_file_to_s3(
            temp_path,
            s3_key,
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
        s3_key = make_s3_key("pptx", url, ".pptx")
        s3_info = upload_file_to_s3(
            temp_path,
            s3_key,
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
        s3_key = make_s3_key("txt", url, ".txt")
        s3_info = upload_file_to_s3(temp_path, s3_key, "text/plain")
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
        s3_key = make_s3_key("html", url, ".json")
        s3_info = upload_json_to_s3(output, s3_key)
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
