import asyncio
import json
import logging
import os
import tempfile
from urllib.parse import urlparse
import fitz  # PyMuPDF
import pandas as pd
from docx import Document
from pptx import Presentation
from lxml import etree
from playwright.async_api import async_playwright
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from crawl4ai.content_scraping_strategy import LXMLWebScrapingStrategy
from crawl4ai.deep_crawling import (
    BestFirstCrawlingStrategy,
)
from crawl4ai.deep_crawling.filters import (
    FilterChain,
    ContentTypeFilter,
)
from crawl4ai.deep_crawling.scorers import (
    KeywordRelevanceScorer,
)
##########################################################
# Logging Configuration
##########################################################
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)
from urllib.parse import urlparse
def validate_url(url: str):
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Only HTTP and HTTPS URLs are allowed.")
    if not parsed.netloc:
        raise ValueError("Invalid URL.")
##########################################################
# Supported File Types
##########################################################
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
##########################################################
# Detect File Type Using Playwright
##########################################################
async def detect_file_type(url: str):
    """
    Detect file type using Playwright response headers.
    Falls back to URL extension if needed.
    """
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            response = await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=30000
            )
            content_type = ""
            if response:
                content_type = response.headers.get(
                    "content-type",
                    ""
                ).lower()
            await browser.close()
            if "text/html" in content_type:
                return "html"
            elif "application/pdf" in content_type:
                return "pdf"
            elif "spreadsheet" in content_type:
                return "excel"
            elif "excel" in content_type:
                return "excel"
            elif "csv" in content_type:
                return "csv"
            elif "word" in content_type:
                return "docx"
            elif "presentation" in content_type:
                return "pptx"
            elif "json" in content_type:
                return "json"
            elif "xml" in content_type:
                return "xml"
            elif "text/plain" in content_type:
                return "txt"
    except Exception as e:
        logger.warning(f"Playwright detection failed: {e}")
    extension = os.path.splitext(
        urlparse(url).path
    )[1].lower()
    return SUPPORTED_TYPES.get(extension, "html")
##########################################################
# Download File using Playwright API
##########################################################
async def download_file(url: str, suffix: str):
    async with async_playwright() as p:
        request = await p.request.new_context()
        response = await request.get(url)
        if not response.ok:
            raise Exception(
                f"Unable to download file ({response.status})"
            )
        temp_file = tempfile.NamedTemporaryFile(
            delete=False,
            suffix=suffix
        )
        temp_file.write(await response.body())
        temp_file.close()
        await request.dispose()
        return temp_file.name
    
##########################################################
# Standard Response Builder
##########################################################

def build_response(success: bool, file_type: str, data=None, message=""):
    return {
        "success": success,
        "file_type": file_type,
        "message": message,
        "data": data
    }
async def extract_json(url: str):
    temp_path = await download_file(url, ".json")
    try:
        with open(temp_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return build_response(
            True,
            "json",
            data
        )
    finally:
        os.remove(temp_path)
async def extract_xml(url: str):
    temp_path = await download_file(url, ".xml")
    try:
        tree = etree.parse(temp_path)
        root = tree.getroot()
        return build_response(
            True,
            "xml",
            etree.tostring(
                root,
                pretty_print=True,
                encoding="unicode"
            )
        )
    finally:
        os.remove(temp_path)
##########################################################
# PDF Extraction
##########################################################

async def extract_pdf(url: str):
    logger.info(f"Extracting PDF: {url}")
    temp_path = None
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            download = None
            async with page.expect_download() as download_info:
                await page.goto(url)
            download = await download_info.value
            temp_path = tempfile.mktemp(suffix=".pdf")
            await download.save_as(temp_path)
            await browser.close()
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
                "page_count": len(pages),
                "pages": pages,
                "text": full_text
            }
        )
    except Exception as e:
        logger.exception(e)
        return build_response(
            False,
            "pdf",
            None,
            str(e)
        )
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
##########################################################
# Excel Extraction
##########################################################
async def extract_excel(url: str):
    logger.info(f"Extracting Excel: {url}")
    temp_path = None
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            async with page.expect_download() as download_info:
                await page.goto(url)
            download = await download_info.value
            temp_path = tempfile.mktemp(suffix=".xlsx")
            await download.save_as(temp_path)
            await browser.close()
        excel = pd.ExcelFile(temp_path)
        sheets = {}
        for sheet in excel.sheet_names:
            df = pd.read_excel(
                temp_path,
                sheet_name=sheet
            )
            sheets[sheet] = {
                "rows": len(df),
                "columns": list(df.columns),
                "preview": df.head(10).to_dict(
                    orient="records"
                )
            }
        return build_response(
            True,
            "excel",
            sheets
        )
    except Exception as e:
        logger.exception(e)
        return build_response(
            False,
            "excel",
            None,
            str(e)
        )
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
##########################################################
# CSV Extraction
##########################################################
async def extract_csv(url: str):
    logger.info(f"Extracting CSV: {url}")
    temp_path = None
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            async with page.expect_download() as download_info:
                await page.goto(url)
            download = await download_info.value
            temp_path = tempfile.mktemp(suffix=".csv")
            await download.save_as(temp_path)
            await browser.close()
        df = pd.read_csv(temp_path)
        return build_response(
            True,
            "csv",
            {
                "rows": len(df),
                "columns": list(df.columns),
                "preview": df.head(10).to_dict(
                    orient="records"
                )
            }
        )
    except Exception as e:
        logger.exception(e)
        return build_response(
            False,
            "csv",
            None,
            str(e)
        )
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
##########################################################
# DOCX Extraction
##########################################################
async def extract_docx(url: str):
    temp_path = await download_file(url, ".docx")
    try:
        document = Document(temp_path)
        text = "\n".join(
            para.text
            for para in document.paragraphs
        )
        return build_response(
            True,
            "docx",
            {
                "text": text
            }
        )
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
##########################################################
# PPTX Extraction
##########################################################
async def extract_pptx(url: str):
    temp_path = await download_file(url, ".pptx")
    try:
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
                "slides": slides
            }
        )
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
##########################################################
# TXT Extraction
##########################################################
async def extract_txt(url: str):
    temp_path = await download_file(url, ".txt")
    try:
        with open(
            temp_path,
            "r",
            encoding="utf-8",
            errors="ignore"
        ) as file:
            text = file.read()
        return build_response(
            True,
            "txt",
            {
                "text": text
            }
        )
    finally:
        os.remove(temp_path)
##########################################################
# HTML / Webpage Extraction using BestFirst Strategy
##########################################################

async def extract_webpage(url: str):
    logger.info(f"Starting BestFirst crawl for {url}")

    pages = []
    try:
        # Prioritize URLs containing these keywords
        keyword_scorer = KeywordRelevanceScorer(
            keywords=["news", "press", "media", "news-releases"],
            weight=0.7
        )

        # Crawl only HTML pages
        filter_chain = FilterChain([
            ContentTypeFilter(allowed_types=["text/html"])
        ])

        config = CrawlerRunConfig(
            deep_crawl_strategy=BestFirstCrawlingStrategy(
                max_depth=1,      # Crawl root + 1 level deep
                max_pages=3,      # Keep page count small for fast execution
                include_external=False,
                filter_chain=filter_chain,
                url_scorer=keyword_scorer
            ),
            scraping_strategy=LXMLWebScrapingStrategy(),
            stream=True,          # ENABLE STREAMING so pages are captured immediately as they finish
            verbose=False,
            page_timeout=20000    # 20s timeout per individual page
        )

        # 80-second overall timeout (safe buffer below Render's 100s proxy limit)
        async with asyncio.timeout(80):
            async with AsyncWebCrawler() as crawler:
                # With stream=True, iterate using async for
                async for result in await crawler.arun(url=url, config=config):
                    if result and getattr(result, "success", False):
                        pages.append({
                            "url": result.url,
                            "success": result.success,
                            "title": getattr(result, "title", None),
                            "score": getattr(result, "metadata", {}).get("score", 0),
                            "depth": getattr(result, "metadata", {}).get("depth", 0),
                            "metadata": getattr(result, "metadata", {}),
                            "markdown": getattr(result, "markdown", None),
                        })

        return build_response(
            True,
            "html",
            {
                "total_pages": len(pages),
                "pages": pages
            }
        )

    except asyncio.TimeoutError:
        logger.warning(f"Crawl reached execution timeout for {url}")
        return build_response(
            True,
            "html",
            {
                "total_pages": len(pages),
                "pages": pages
            },
            message="Crawl reached timeout limit. Returning collected pages."
        )
    except Exception as e:
        logger.exception(e)
        return build_response(
            False,
            "html",
            None,
            str(e)
        )
##########################################################
# Universal Extraction Router
##########################################################
async def deep_crawl(url: str):
    try:
        # Step 1: Validate URL
        validate_url(url)

        # Step 2: Detect File Type
        file_type = await detect_file_type(url)
        logger.info(f"Detected file type: {file_type}")
        # Step 3: Route Based on File Type

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
        return build_response(
            False,
            "unknown",
            None,
            str(e)
        )
##########################################################
# Main (Testing)
##########################################################
if __name__ == "__main__":
    TEST_URL = "https://www.geeksforgeeks.org/"
    async def main():
        result = await deep_crawl(TEST_URL)
        print(
            json.dumps(
                result,
                indent=4,
                default=str
            )
        )
    asyncio.run(main())
