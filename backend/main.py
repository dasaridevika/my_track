import os
import sys
import asyncio
import logging
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # Replace with your frontend URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# -------------------------------------------------------
# Root Endpoint
# -------------------------------------------------------
@app.get("/")
async def root():
    return {
        "message": "Crawl4AI API Running 🚀"
    }
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
        logger.info(
            f"Incoming Request | Method={method} | URL={request.url}"
        )

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

        analysis = await analyze_extracted_data(
    url=request.url,
    title="",
    extracted_text=extract_text_for_llm(result),
    analysis_type="summary"
)

        logger.info(
            f"Completed Request | Method={method} | AI Analysis Done"
        )

        return {
            "success": True,
            "method": method,
            "url": request.url,
            "extracted_data": result,
            "llm_analysis": analysis
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled Exception")
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )
