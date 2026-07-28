import os
import base64
import uuid
import shutil
import logging
import asyncio
from crawl4ai import (
    AsyncWebCrawler,
    BrowserConfig,
    CrawlerRunConfig,
    CacheMode,
)
from storage import is_bucket_configured, upload_file, get_download_url
logger = logging.getLogger(__name__)
async def page_snapshot(url: str):
    job_id = str(uuid.uuid4())
    output_dir = os.path.join("outputs", job_id)
    os.makedirs(output_dir, exist_ok=True)

    browser_config = BrowserConfig(
        headless=True,
        verbose=True,
    )

    crawler_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        screenshot=True,
        pdf=True,
        capture_mhtml=True,
    )

    try:
        async with AsyncWebCrawler(config=browser_config) as crawler:
            async with asyncio.timeout(80):
                result = await crawler.arun(
                    url=url,
                    config=crawler_config,
                )

        if not result.success:
            return {
                "success": False,
                "method": "snapshot",
                "url": url,
                "message": "Crawl failed",
            }

    except asyncio.TimeoutError:
        return {
            "success": False,
            "method": "snapshot",
            "url": url,
            "message": "Crawler request timed out after 80 seconds.",
        }

    except Exception as e:
        logger.exception("Snapshot failed")
        return {
            "success": False,
            "method": "snapshot",
            "url": url,
            "message": str(e),
        }

    uploaded_files = {}

    def handle_file(file_type: str, local_path: str, bucket_key: str):
        filename = os.path.basename(local_path)

        try:
            if is_bucket_configured():
                upload_file(local_path, bucket_key)

                file_data = {
                    "filename": filename,
                    "key": bucket_key,
                    "url": get_download_url(bucket_key, filename=filename),
                    "storage": "bucket",
                }

                try:
                    os.remove(local_path)
                except Exception as cleanup_error:
                    logger.warning(f"Could not delete {local_path}: {cleanup_error}")

                return file_data

            return {
                "filename": filename,
                "local_path": local_path,
                "storage": "local",
            }

        except Exception as upload_error:
            logger.exception(upload_error)
            return {
                "filename": filename,
                "local_path": local_path,
                "storage": "local",
                "upload_error": str(upload_error),
            }

    if result.screenshot:
        screenshot_path = os.path.join(output_dir, "screenshot.png")
        with open(screenshot_path, "wb") as f:
            f.write(base64.b64decode(result.screenshot))

        uploaded_files["screenshot"] = handle_file(
            "screenshot",
            screenshot_path,
            f"pagesnapshots/{job_id}/screenshot.png",
        )

    if result.pdf:
        pdf_path = os.path.join(output_dir, "page.pdf")
        with open(pdf_path, "wb") as f:
            f.write(result.pdf)

        uploaded_files["pdf"] = handle_file(
            "pdf",
            pdf_path,
            f"pagesnapshots/{job_id}/page.pdf",
        )

    if result.mhtml:
        mhtml_path = os.path.join(output_dir, "page.mhtml")
        with open(mhtml_path, "w", encoding="utf-8") as f:
            f.write(result.mhtml)

        uploaded_files["mhtml"] = handle_file(
            "mhtml",
            mhtml_path,
            f"pagesnapshots/{job_id}/page.mhtml",
        )

    if os.path.isdir(output_dir) and not os.listdir(output_dir):
        shutil.rmtree(output_dir, ignore_errors=True)

    return {
        "success": True,
        "method": "snapshot",
        "url": url,
        "job_id": job_id,
        "storage_mode": "bucket" if is_bucket_configured() else "local",
        "files": uploaded_files,
    }
