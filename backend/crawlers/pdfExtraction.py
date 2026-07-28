import os
import uuid
import json
import shutil
import asyncio
import tempfile
import logging
from pathlib import Path
from urllib.parse import urlparse
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, BrowserConfig
from crawl4ai.processors.pdf import (
    PDFCrawlerStrategy,          # ← THIS WAS MISSING
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

    browser_config = BrowserConfig(
        headless=True,
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    )

    run_config = CrawlerRunConfig(
        delay_before_return_html=5.0,
        page_timeout=60000,
    )

    # -----------------------------------------------------------------
    # STEP 1: Use the browser to solve the Cloudflare challenge, then 
    # use Playwright's native API to download the PDF bytes directly.
    # -----------------------------------------------------------------
    pdf_bytes = None
    try:
        async with AsyncWebCrawler(config=browser_config) as crawler:
            async with asyncio.timeout(80):
                # 1. Navigate to the base domain to solve the JS challenge
                base_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
                await crawler.arun(url=base_url, config=run_config)

                # 2. Use the browser's internal context to download the PDF
                # This automatically passes the Cloudflare cookies without rendering the PDF
                response = await crawler.browser_manager.page.request.get(url)
                
                if response.ok:
                    pdf_bytes = await response.body()
                    # Verify we got the actual PDF, not the 33-byte block page
                    if pdf_bytes and len(pdf_bytes) > 100 and pdf_bytes[:4] == b'%PDF':
                        logger.info(f"Successfully downloaded PDF via browser context ({len(pdf_bytes)} bytes)")
                    else:
                        logger.warning(f"Anti-bot block page received instead of PDF ({len(pdf_bytes)} bytes)")
                        pdf_bytes = None
                else:
                    logger.warning(f"Failed to download PDF via browser context: HTTP {response.status}")

    except asyncio.TimeoutError:
        shutil.rmtree(image_dir, ignore_errors=True)
        return {
            "success": False,
            "error": "Browser timeout while trying to bypass anti-bot protection."
        }
    except Exception as e:
        logger.warning(f"Browser context download failed: {str(e)}")

    # -----------------------------------------------------------------
    # STEP 2: If the browser context failed, fallback to the raw HTTP 
    # PDFCrawlerStrategy (works for unprotected PDFs)
    # -----------------------------------------------------------------
    if not pdf_bytes:
        logger.info("Falling back to PDFCrawlerStrategy...")
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

    # -----------------------------------------------------------------
    # STEP 3: If we successfully got the PDF bytes from the browser,
    # parse them manually using the PDFContentScrapingStrategy.
    # -----------------------------------------------------------------
    temp_pdf_path = None
    try:
        # Save the PDF bytes to a temporary file for the scraper
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
            temp_pdf.write(pdf_bytes)
            temp_pdf_path = temp_pdf.name

        pdf_scraper = PDFContentScrapingStrategy(
            extract_images=True,
            save_images_locally=True,
            image_save_dir=str(image_dir),
            batch_size=2,
        )

        # Run the scraper directly on the local PDF file
        parsed_result = await pdf_scraper.scrap(
            url=temp_pdf_path, 
            html="",          
            raw_html=b"",     
        )

        markdown = parsed_result.get("markdown", "") if isinstance(parsed_result, dict) else str(parsed_result)

        response_payload = {
            "success": True,
            "url": url,
            "job_id": job_id,
            "metadata": {},
            "markdown": markdown,
            "images": sanitize_image_metadata(parsed_result.get("images", [])) if isinstance(parsed_result, dict) else [],
            "image_count": len(parsed_result.get("images", [])) if isinstance(parsed_result, dict) else 0,
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

    except Exception as e:
        shutil.rmtree(image_dir, ignore_errors=True)
        logger.exception("Local PDF parsing failed")
        return {
            "success": False,
            "url": url,
            "error": str(e),
        }
    finally:
        if temp_pdf_path and os.path.exists(temp_pdf_path):
            os.remove(temp_pdf_path)


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
