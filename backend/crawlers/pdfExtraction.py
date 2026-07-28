import os
import uuid
import json
import shutil
import asyncio
import tempfile
import logging
from pathlib import Path
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, BrowserConfig
from crawl4ai.processors.pdf import (
    PDFCrawlerStrategy,
    PDFContentScrapingStrategy,
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


def upload_extracted_json(payload: dict, url: str, job_id: str):
    if not is_bucket_configured():
        return {
            "filename": "extraction.json",
            "storage": "bucket",
            "upload_error": bucket_not_configured_message("uploading PDF extraction JSON"),
            "storage_config": get_bucket_config_status(),
        }

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w", encoding="utf-8") as temp_file:
            json.dump(payload, temp_file, ensure_ascii=False, indent=2, default=str)
            temp_path = temp_file.name

        object_key = make_object_key(f"pdf-extractions/{job_id}", url, "extraction.json")
        return upload_file(temp_path, object_key)
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


def upload_extracted_images(image_dir: Path, url: str, job_id: str):
    uploaded_images = []

    if not image_dir.exists():
        return uploaded_images

    for image_path in sorted(path for path in image_dir.rglob("*") if path.is_file()):
        object_key = make_object_key(f"pdf-extractions/{job_id}/images", url, image_path.name)
        try:
            if not is_bucket_configured():
                uploaded_images.append({
                    "filename": image_path.name,
                    "storage": "bucket",
                    "upload_error": bucket_not_configured_message("uploading PDF images"),
                    "storage_config": get_bucket_config_status(),
                })
                continue

            file_data = upload_file(str(image_path), object_key)
            file_data["source_filename"] = image_path.name
            uploaded_images.append(file_data)
        except Exception as upload_error:
            logger.exception("Could not upload extracted PDF image")
            uploaded_images.append({
                "filename": image_path.name,
                "storage": "bucket",
                "upload_error": str(upload_error),
            })

    return uploaded_images


def sanitize_image_metadata(images):
    sanitized = []
    local_path_keys = {"path", "local_path", "localPath", "file_path", "filePath"}

    for image in images or []:
        if isinstance(image, dict):
            sanitized.append({
                key: value
                for key, value in image.items()
                if key not in local_path_keys
            })
        else:
            sanitized.append(image)

    return sanitized


async def pdf_extract(url: str):
    job_id = uuid.uuid4().hex
    image_dir = Path("pdf_images") / job_id
    image_dir.mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------
    # STEP 1: Use the headless browser to bypass the anti-bot
    # protection. We navigate to the base domain first, wait
    # for the JS challenge to resolve, and then try the PDF.
    # ---------------------------------------------------------
    browser_config = BrowserConfig(
        headless=True,
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    )

    run_config = CrawlerRunConfig(
        delay_before_return_html=5.0,
        page_timeout=60000,
    )

    try:
        # 1. Browser solves the Cloudflare challenge
        async with AsyncWebCrawler(config=browser_config) as crawler:
            async with asyncio.timeout(80):
                result = await crawler.arun(url=url, config=run_config)

        # If the browser successfully fetched the PDF text content natively, we can return it
        if result.success and result.markdown:
            markdown = (
                result.markdown.raw_markdown
                if hasattr(result.markdown, "raw_markdown")
                else result.markdown
            )
            
            # If significant content was extracted, the browser handled it perfectly
            if markdown and len(markdown.strip()) > 50:
                response_payload = {
                    "success": True,
                    "url": url,
                    "job_id": job_id,
                    "metadata": result.metadata,
                    "markdown": markdown,
                    "images": sanitize_image_metadata(result.media.get("images", [])),
                    "image_count": len(result.media.get("images", [])),
                    "storage_config": get_bucket_config_status(),
                }
                
                try:
                    uploaded_images = upload_extracted_images(image_dir, url, job_id)
                    extracted_json = upload_extracted_json(response_payload, url, job_id)
                    response_payload["storage_mode"] = "bucket"
                    response_payload["files"] = {
                        "extraction": extracted_json,
                        "images": uploaded_images,
                    }
                    return response_payload
                finally:
                    shutil.rmtree(image_dir, ignore_errors=True)

    except asyncio.TimeoutError:
        shutil.rmtree(image_dir, ignore_errors=True)
        return {
            "success": False,
            "error": "Browser timeout while trying to bypass anti-bot protection."
        }
    except Exception as e:
        # If it threw ERR_ABORTED because of the PDF viewer, we intentionally ignore it
        # and fall back to Step 2.
        logger.warning(f"Browser navigation failed (expected for PDFs): {str(e)}")

    # ---------------------------------------------------------
    # STEP 2: The browser failed to load the PDF natively 
    # (ERR_ABORTED). We now use the PDFCrawlerStrategy to 
    # download the raw PDF via HTTP. Since the browser already 
    # solved the challenge, the server will usually allow the 
    # direct HTTP request momentarily.
    # ---------------------------------------------------------
    pdf_scraper = PDFContentScrapingStrategy(
        extract_images=True,
        save_images_locally=True,
        image_save_dir=str(image_dir),
        batch_size=2,
    )

    run_config_pdf = CrawlerRunConfig(
        scraping_strategy=pdf_scraper,
        page_timeout=60000,
    )

    try:
        async with AsyncWebCrawler(
            crawler_strategy=PDFCrawlerStrategy()
        ) as crawler:
            async with asyncio.timeout(80):
                result = await crawler.arun(
                    url=url,
                    config=run_config_pdf
                )
    except asyncio.TimeoutError:
        shutil.rmtree(image_dir, ignore_errors=True)
        return {
            "success": False,
            "error": "PDF Crawler request timed out after 80 seconds."
        }
    except Exception as e:
        shutil.rmtree(image_dir, ignore_errors=True)
        logger.exception("PDF extraction failed")
        return {
            "success": False,
            "url": url,
            "error": str(e),
        }

    if not result.success:
        shutil.rmtree(image_dir, ignore_errors=True)
        return {
            "success": False,
            "error": result.error_message
        }

    markdown = (
        result.markdown.raw_markdown
        if hasattr(result.markdown, "raw_markdown")
        else result.markdown
    )

    response_payload = {
        "success": True,
        "url": url,
        "job_id": job_id,
        "metadata": result.metadata,
        "markdown": markdown,
        "images": sanitize_image_metadata(result.media.get("images", [])),
        "image_count": len(result.media.get("images", [])),
        "storage_config": get_bucket_config_status(),
    }

    try:
        uploaded_images = upload_extracted_images(image_dir, url, job_id)
        extracted_json = upload_extracted_json(response_payload, url, job_id)
        response_payload["storage_mode"] = "bucket"
        response_payload["files"] = {
            "extraction": extracted_json,
            "images": uploaded_images,
        }
        return response_payload
    finally:
        shutil.rmtree(image_dir, ignore_errors=True)


# Optional: Run directly for testing
if __name__ == "__main__":
    import asyncio
    import json
    
    async def main():
        data = await pdf_extract(
            "https://shadowland.online/images/uploads/17fc6ef0-f7be-45ed-8c49-c0ed4115f5aa/EDS%20Packet.pdf"
        )
        print(json.dumps(data, indent=4, default=str))
        
    asyncio.run(main())
