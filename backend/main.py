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

# -------------------------------------------------------
# Logging
# -------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)
logger.info(f"RUNNING main.py SHA={os.getenv('RAILWAY_GIT_COMMIT_SHA')}")
logger.info("NEW MAIN.PY VERSION WITH SAFE LLM HANDLING LOADED")

# -------------------------------------------------------
# FastAPI
# -------------------------------------------------------
app = FastAPI(
    title="Crawl4AI API",
    version="1.0.0"
)

# -------------------------------------------------------
# CORS
# -------------------------------------------------------
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "*")

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

# -------------------------------------------------------
# Root Endpoint
# -------------------------------------------------------
@app.get("/")
async def root():
    return {
        "message": "Crawl4AI API Running 🚀",
        "version_marker": "safe-llm-v3"
    }

# -------------------------------------------------------
# Optional favicon route
# -------------------------------------------------------
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    favicon_path = "favicon.ico"
    if os.path.exists(favicon_path):
        return FileResponse(favicon_path)
    raise HTTPException(status_code=404, detail="Favicon not found")

# -------------------------------------------------------
# Supported Crawlers
# -------------------------------------------------------
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

# -------------------------------------------------------
# Crawl Endpoint
# -------------------------------------------------------
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
            else:
                analysis = await analyze_extracted_data(
                    url=request.url,
                    title="",
                    extracted_text=extracted_text,
                    analysis_type="summary"
                )

        except Exception as e:
            logger.exception("LLM analysis failed but crawl will continue")
            analysis_error = str(e)

        logger.info(f"Completed Request | Method={method}")

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
