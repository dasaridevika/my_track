import os
import sys
# Ensure backend directory is in python module search path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
import time
import uuid
import asyncio
import logging
from contextlib import asynccontextmanager, suppress
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
try:
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
except ModuleNotFoundError:
    from backend.crawlers.page_snapshot import page_snapshot
    from backend.crawlers.deep_crawling_dynamic_pages import deep_crawl_bfs
    from backend.models import CrawlRequest
    from backend.crawlers.single_page import crawl_single_page
    from backend.crawlers.deepcrawl import deep_crawl
    from backend.crawlers.jsonCssExtraction import css_extract
    from backend.crawlers.jsonXpathExtraction import xpath_extract
    from backend.crawlers.RegexExtraction import regex_extract
    from backend.crawlers.pdfExtraction import pdf_extract
    from backend.llm_analysis import analyze_extracted_data, extract_text_for_llm
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    force=True
)
logger = logging.getLogger(__name__)
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "*")
PUBLIC_BASE_URL = os.getenv(
    "PUBLIC_BASE_URL",
    ""
).rstrip("/")
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
analysis_jobs: dict = {}
analysis_queue: asyncio.Queue = asyncio.Queue(maxsize=100)
analysis_semaphore = asyncio.Semaphore(1)
crawl_semaphore = asyncio.Semaphore(3)
async def process_analysis_job(job_id: str, payload: dict):
    try:
        analysis_jobs[job_id]["status"] = "running"
        async with analysis_semaphore:
            result = await analyze_extracted_data(
                url=payload["url"],
                title=payload.get("title", ""),
                extracted_text=payload["text"],
                analysis_type=payload.get("analysis_type", "summary")
            )
        analysis_jobs[job_id]["status"] = "done"
        analysis_jobs[job_id]["result"] = result
        analysis_jobs[job_id]["completed_at"] = time.time()
        logger.info(f"Analysis completed | job_id={job_id}")
    except Exception as e:
        logger.exception("Analysis failed | job_id=%s",job_id)
        analysis_jobs[job_id]["status"] = "failed"
        analysis_jobs[job_id]["error"] = str(e)
async def analysis_worker():
    logger.info("Analysis worker started")
    while True:
        job_id, payload = await analysis_queue.get()
        try:
            await process_analysis_job(job_id, payload)
        finally:
            analysis_queue.task_done()
@asynccontextmanager
async def lifespan(app: FastAPI):
    worker_task = asyncio.create_task(analysis_worker())
    try:
        yield
    finally:
        worker_task.cancel()
        with suppress(asyncio.CancelledError):
            await worker_task
app = FastAPI(
    title="Crawl4AI API",
    version="1.0.0",
    lifespan=lifespan
)
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
        "version_marker": "queue-v1"
    }
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    favicon_path = "favicon.ico"
    if os.path.exists(favicon_path):
        return FileResponse(favicon_path)
    raise HTTPException(status_code=404, detail="Favicon not found")
@app.get("/analysis/{job_id}")
async def get_analysis_status(job_id: str):
    job = analysis_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Analysis job not found")
    return {"job_id": job_id, **job}
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
        "message": result.get("message"),
        "errors": result.get("errors", {}),
        "storage_mode": result.get("storage_mode"),
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
                detail="Invalid method. Choose one of: single, deep, dynamic, snapshot, css, xpath, regex, pdf",
            )
        async with crawl_semaphore:
            result = await handler(request.url)
        if method == "snapshot":
            result = normalize_snapshot_result(result, request.url, PUBLIC_BASE_URL)
        extracted_text = extract_text_for_llm(result)
        logger.info(f"LLM text length for method={method}: {len(extracted_text or '')}")
        analysis_job_id = None
        analysis_status = "skipped"
        if method != "snapshot" and extracted_text and extracted_text.strip():
            analysis_job_id = str(uuid.uuid4())
            analysis_jobs[analysis_job_id] = {
                "status": "queued",
                "result": None,
                "error": None,
                "source_url": request.url
            }
            await analysis_queue.put((
                analysis_job_id,
                {
                    "url": request.url,
                    "title": "",
                    "text": extracted_text,
                    "analysis_type": "summary"
                }
            ))
            analysis_status = "queued"
            logger.info(f"Analysis queued | job_id={analysis_job_id} | method={method}")
        else:
            logger.info(f"LLM analysis skipped | method={method}")
        return JSONResponse(
            status_code=200,
            content={
            "success": result.get("success", True) if isinstance(result, dict) else True,
            "method": method,
            "url": request.url,
            "extracted_data": result,
            "analysis_job_id": analysis_job_id,
            "analysis_status": analysis_status
        }
    )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled Exception")
        raise HTTPException(status_code=500, detail=str(e))
@app.get("/health")
async def health():
    return {"status": "ok"}
