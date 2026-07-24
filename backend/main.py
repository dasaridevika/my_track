import os
import sys
import asyncio
import logging

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from crawlers.page_snapshot import page_snapshot
from crawlers.deep_crawling_dynamic_pages import deep_crawl_bfs
from models import CrawlRequest
from crawlers.single_page import crawl_single_page
from crawlers.deepcrawl import deep_crawl
from crawlers.jsonCssExtraction import css_extract
from crawlers.jsonXpathExtraction import xpath_extract
from crawlers.RegexExtraction import regex_extract
from crawlers.pdfExtraction import pdf_extract
from llm_analysis import analyze_extracted_data, extract_text_for_llm

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    force=True
)
logger = logging.getLogger(__name__)
logger.info(f"RUNNING main.py SHA={os.getenv('RAILWAY_GIT_COMMIT_SHA')}")
logger.info("SAFE MAIN.PY LOADED")

app = FastAPI(
    title="Crawl4AI API",
    version="1.0.0"
)

FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "*")
PUBLIC_BASE_URL = os.getenv(
    "PUBLIC_BASE_URL",
    "https://grateful-caring-production-d098.up.railway.app"
).rstrip("/")

if FRONTEND_ORIGIN == "*":
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[FRONTEND_ORIGIN],
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

@app.get("/")
async def root():
    return {
        "message": "Crawl4AI API Running 🚀",
        "version_marker": "safe-llm-v5"
    }

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    favicon_path = "favicon.ico"
    if os.path.exists(favicon_path):
        return FileResponse(favicon_path)
    raise HTTPException(status_code=404, detail="Favicon not found")

CRAWL_HANDLERS = {
    "single": crawl_single_page,
    "deep": deep_crawl,
    "dynamic": deep_crawl_bfs,
    "snapshot": page_snapshot,
    "css": css_extract,
    "xpath": xpath_extract,
    "regex": regex_extract,
    "pdf": pdf_extract,
}

def build_file_entry(value, public_base_url, kind):
    if not value:
        return None

    if isinstance(value, dict):
        return value

    entry = {"local_path": value}

    if isinstance(value, str) and (value.startswith("http://") or value.startswith("https://")):
        entry = {"url": value}
    elif isinstance(value, str) and value.startswith("/files/"):
        entry = {"url": f"{public_base_url}{value}"}
    elif isinstance(value, str) and value.startswith("files/"):
        entry = {"url": f"{public_base_url}/{value}"}
    elif isinstance(value, str) and value.startswith("snapshots/"):
        entry = {
            "bucket_key": value,
            "url": f"{public_base_url}/files/{value}"
        }

    entry["type"] = kind
    return entry

def normalize_snapshot_result(result, request_url, public_base_url):
    if not isinstance(result, dict):
        return {
            "success": True,
            "method": "snapshot",
            "url": request_url,
            "files": {}
        }

    files = result.get("files", {})

    screenshot_value = (
        files.get("screenshot")
        or result.get("screenshot")
        or result.get("screenshot_url")
    )
    pdf_value = (
        files.get("pdf")
        or result.get("pdf")
        or result.get("pdf_url")
    )
    mhtml_value = (
        files.get("mhtml")
        or result.get("mhtml")
        or result.get("mhtml_url")
    )

    normalized_files = {}

    screenshot_entry = build_file_entry(screenshot_value, public_base_url, "screenshot")
    pdf_entry = build_file_entry(pdf_value, public_base_url, "pdf")
    mhtml_entry = build_file_entry(mhtml_value, public_base_url, "mhtml")

    if screenshot_entry:
        normalized_files["screenshot"] = screenshot_entry
    if pdf_entry:
        normalized_files["pdf"] = pdf_entry
    if mhtml_entry:
        normalized_files["mhtml"] = mhtml_entry

    return {
        "success": result.get("success", True),
        "method": "snapshot",
        "url": result.get("url", request_url),
        "job_id": result.get("job_id"),
        "files": normalized_files
    }

@app.post("/crawl")
async def crawl(request: CrawlRequest):
    try:
        method = request.method.lower()
        logger.info(f"Incoming Request | Method={method} | URL={request.url}")

        handler = CRAWL_HANDLERS.get(method)
        if handler is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Invalid method. "
                    "Choose one of: "
                    "single, deep, dynamic, snapshot, css, xpath, regex, pdf"
                ),
            )

        result = await handler(request.url)

        if method == "snapshot":
            result = normalize_snapshot_result(result, request.url, PUBLIC_BASE_URL)

        analysis = None
        analysis_error = None

        try:
            extracted_text = extract_text_for_llm(result)
            logger.info(f"LLM text length for method={method}: {len(extracted_text or '')}")

            if method == "snapshot" or not extracted_text or not extracted_text.strip():
                analysis = {
                    "success": False,
                    "skipped": True,
                    "reason": "LLM analysis skipped because no extracted text was available for this crawl method."
                }
                logger.info(f"Completed Request | Method={method} | LLM Skipped")
            else:
                analysis = await analyze_extracted_data(
                    url=request.url,
                    title="",
                    extracted_text=extracted_text,
                    analysis_type="summary"
                )
                logger.info(f"Completed Request | Method={method} | AI Analysis Done")

        except Exception as e:
            logger.exception("LLM analysis failed but crawl will continue")
            analysis_error = str(e)

        return {
            "success": True,
            "method": method,
            "url": request.url,
            "extracted_data": result,
            "llm_analysis": analysis,
            "llm_analysis_error": analysis_error
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled Exception")
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )
