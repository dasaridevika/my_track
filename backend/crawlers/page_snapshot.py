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
try:
    from storage import (
        bucket_not_configured_message,
        get_bucket_config_status,
        is_bucket_configured,
        make_object_key,
        upload_file,
    )
except ModuleNotFoundError:
    from backend.storage import (
        bucket_not_configured_message,
        get_bucket_config_status,
        is_bucket_configured,
        make_object_key,
        upload_file,
    )
logger = logging.getLogger(__name__)

SNAPSHOT_TIMEOUT_SECONDS = 80

async def run_snapshot_capture(url: str, **capture_flags):
    browser_config = BrowserConfig(
        headless=True,
        verbose=True,
    )

    crawler_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        page_timeout=60000,
        **capture_flags,
    )

    async with AsyncWebCrawler(config=browser_config) as crawler:
        async with asyncio.timeout(SNAPSHOT_TIMEOUT_SECONDS):
            return await crawler.arun(
                url=url,
                config=crawler_config,
            )

async def page_snapshot(url: str):
    job_id = str(uuid.uuid4())
    output_dir = os.path.join("outputs", job_id)
    os.makedirs(output_dir, exist_ok=True)

    uploaded_files = {}
    capture_errors = {}

    async def capture_artifact(name: str, **capture_flags):
        try:
            result = await run_snapshot_capture(url, **capture_flags)
        except asyncio.TimeoutError:
            capture_errors[name] = (
                f"{name} capture timed out after {SNAPSHOT_TIMEOUT_SECONDS} seconds."
            )
            return None
        except Exception as e:
            logger.exception("%s capture failed", name)
            capture_errors[name] = str(e)
            return None

        if not result.success:
            capture_errors[name] = getattr(result, "error_message", None) or f"{name} capture failed."
            return None

        return result

    def handle_file(file_type: str, local_path: str):
        filename = os.path.basename(local_path)
        bucket_key = make_object_key(f"page-snapshots/{job_id}", url, filename)

        try:
            if not is_bucket_configured():
                return {
                    "filename": filename,
                    "type": file_type,
                    "storage": "bucket",
                    "upload_error": bucket_not_configured_message(f"uploading {file_type}"),
                    "storage_config": get_bucket_config_status(),
                }

            file_data = upload_file(local_path, bucket_key)
            file_data["type"] = file_type
            return file_data

        except Exception as upload_error:
            logger.exception(upload_error)
            return {
                "filename": filename,
                "storage": "bucket",
                "upload_error": str(upload_error),
            }
        finally:
            try:
                os.remove(local_path)
            except FileNotFoundError:
                pass
            except Exception as cleanup_error:
                logger.warning(f"Could not delete {local_path}: {cleanup_error}")

    screenshot_result = await capture_artifact("screenshot", screenshot=True)
    if screenshot_result and screenshot_result.screenshot:
        screenshot_path = os.path.join(output_dir, "screenshot.png")
        screenshot_data = screenshot_result.screenshot
        if isinstance(screenshot_data, str) and "," in screenshot_data:
            screenshot_data = screenshot_data.split(",", 1)[1]
        with open(screenshot_path, "wb") as f:
            f.write(base64.b64decode(screenshot_data))

        uploaded_files["screenshot"] = handle_file(
            "screenshot",
            screenshot_path,
        )

    pdf_result = await capture_artifact("pdf", pdf=True)
    if pdf_result and pdf_result.pdf:
        pdf_path = os.path.join(output_dir, "page.pdf")
        with open(pdf_path, "wb") as f:
            if isinstance(pdf_result.pdf, str):
                with open(pdf_result.pdf, "rb") as source_pdf:
                    f.write(source_pdf.read())
            else:
                f.write(pdf_result.pdf)

        uploaded_files["pdf"] = handle_file(
            "pdf",
            pdf_path,
        )

    mhtml_result = await capture_artifact("mhtml", capture_mhtml=True)
    if mhtml_result and mhtml_result.mhtml:
        mhtml_path = os.path.join(output_dir, "page.mhtml")
        if isinstance(mhtml_result.mhtml, bytes):
            with open(mhtml_path, "wb") as f:
                f.write(mhtml_result.mhtml)
        else:
            with open(mhtml_path, "w", encoding="utf-8") as f:
                f.write(mhtml_result.mhtml)

        uploaded_files["mhtml"] = handle_file(
            "mhtml",
            mhtml_path,
        )

    if os.path.isdir(output_dir) and not os.listdir(output_dir):
        shutil.rmtree(output_dir, ignore_errors=True)

    if not uploaded_files:
        return {
            "success": False,
            "method": "snapshot",
            "url": url,
            "job_id": job_id,
            "message": "Snapshot capture failed for all artifact types.",
            "errors": capture_errors,
        }

    return {
        "success": True,
        "method": "snapshot",
        "url": url,
        "job_id": job_id,
        "storage_mode": "bucket" if is_bucket_configured() else "bucket_unconfigured",
        "files": uploaded_files,
        "errors": capture_errors,
        "storage_config": get_bucket_config_status(),
    }
