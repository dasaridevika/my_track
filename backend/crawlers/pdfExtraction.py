import asyncio
import json
import logging
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from urllib.parse import urlparse

import fitz
import httpx
from playwright.async_api import async_playwright

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

PDF_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "application/pdf,application/octet-stream;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def upload_or_report(local_path: str, category: str, url: str, filename: str):
    if not is_bucket_configured():
        return {
            "filename": filename,
            "storage": "bucket",
            "upload_error": bucket_not_configured_message(f"uploading {filename}"),
            "storage_config": get_bucket_config_status(),
        }

    object_key = make_object_key(category, url, filename)
    try:
        return upload_file(local_path, object_key)
    except Exception as upload_error:
        logger.exception("Could not upload PDF artifact")
        return {
            "filename": filename,
            "key": object_key,
            "storage": "bucket",
            "upload_error": str(upload_error),
        }


def write_json_temp(payload: dict):
    temp_path = None
    with tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w", encoding="utf-8") as temp_file:
        json.dump(payload, temp_file, ensure_ascii=False, indent=2, default=str)
        temp_path = temp_file.name
    return temp_path


async def download_pdf(url: str, destination: Path):
    parsed = urlparse(url)
    headers = dict(PDF_HEADERS)
    if parsed.scheme and parsed.netloc:
        headers["Referer"] = f"{parsed.scheme}://{parsed.netloc}/"

    async with httpx.AsyncClient(follow_redirects=True, timeout=120.0, headers=headers) as client:
        response = await client.get(url)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code in {401, 403, 406, 429}:
                logger.warning(
                    "Direct PDF download blocked with HTTP %s; trying browser fallback",
                    e.response.status_code,
                )
                return await download_pdf_with_browser(url, destination)
            raise

    content_type = response.headers.get("content-type", "").lower()
    content = response.content
    is_pdf = content.lstrip().startswith(b"%PDF")

    if not is_pdf:
        preview = content[:200].decode("utf-8", errors="replace")
        raise ValueError(
            "URL did not return a valid PDF. "
            f"content_type={content_type or 'unknown'}, bytes={len(content)}, preview={preview!r}"
        )

    destination.write_bytes(content)
    return {
        "content_type": content_type or "application/pdf",
        "bytes": len(content),
        "final_url": str(response.url),
        "download_method": "httpx",
    }


async def download_pdf_with_browser(url: str, destination: Path):
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}/" if parsed.scheme and parsed.netloc else None

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        context = await browser.new_context(
            accept_downloads=True,
            extra_http_headers=PDF_HEADERS,
            user_agent=PDF_HEADERS["User-Agent"],
        )

        try:
            page = await context.new_page()
            if origin:
                try:
                    await page.goto(origin, wait_until="domcontentloaded", timeout=30000)
                except Exception as warmup_error:
                    logger.warning("PDF browser warmup failed: %s", warmup_error)

            response = await context.request.get(
                url,
                headers={
                    **PDF_HEADERS,
                    "Referer": origin or url,
                },
                timeout=120000,
            )

            if not response.ok:
                raise ValueError(f"Browser PDF download failed with HTTP {response.status}.")

            content = await response.body()
            content_type = (response.headers.get("content-type") or "").lower()

            if not content.lstrip().startswith(b"%PDF"):
                preview = content[:200].decode("utf-8", errors="replace")
                raise ValueError(
                    "Browser fallback did not return a valid PDF. "
                    f"content_type={content_type or 'unknown'}, bytes={len(content)}, preview={preview!r}"
                )

            destination.write_bytes(content)
            return {
                "content_type": content_type or "application/pdf",
                "bytes": len(content),
                "final_url": response.url,
                "download_method": "playwright",
            }
        finally:
            await context.close()
            await browser.close()


def extract_pdf_content(pdf_path: Path, image_dir: Path):
    pages = []
    images = []
    markdown_parts = []

    document = fitz.open(pdf_path)
    try:
        for page_index, page in enumerate(document):
            page_number = page_index + 1
            text = page.get_text("text").strip()
            pages.append({
                "page": page_number,
                "text": text,
            })

            if text:
                markdown_parts.append(f"## Page {page_number}\n\n{text}")

            for image_index, image_info in enumerate(page.get_images(full=True), start=1):
                xref = image_info[0]
                extracted = document.extract_image(xref)
                image_bytes = extracted.get("image")
                extension = extracted.get("ext", "png")

                if not image_bytes:
                    continue

                image_name = f"page-{page_number}-image-{image_index}.{extension}"
                image_path = image_dir / image_name
                image_path.write_bytes(image_bytes)
                images.append({
                    "page": page_number,
                    "filename": image_name,
                    "extension": extension,
                    "bytes": len(image_bytes),
                })
    finally:
        document.close()

    return {
        "page_count": len(pages),
        "pages": pages,
        "markdown": "\n\n".join(markdown_parts),
        "images": images,
        "image_count": len(images),
    }


async def pdf_extract(url: str):
    job_id = uuid.uuid4().hex
    work_dir = Path(tempfile.mkdtemp(prefix=f"pdf-extract-{job_id}-"))
    image_dir = work_dir / "images"
    image_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = work_dir / "source.pdf"

    try:
        download_info = await download_pdf(url, pdf_path)
        extracted = await asyncio.to_thread(extract_pdf_content, pdf_path, image_dir)

        response_payload = {
            "success": True,
            "url": url,
            "job_id": job_id,
            "download": download_info,
            "page_count": extracted["page_count"],
            "markdown": extracted["markdown"],
            "pages": extracted["pages"],
            "images": extracted["images"],
            "image_count": extracted["image_count"],
            "storage_config": get_bucket_config_status(),
        }

        uploaded_images = []
        for image in extracted["images"]:
            image_path = image_dir / image["filename"]
            file_data = upload_or_report(
                str(image_path),
                f"pdf-extractions/{job_id}/images",
                url,
                image["filename"],
            )
            file_data["page"] = image["page"]
            uploaded_images.append(file_data)

        extraction_json_path = write_json_temp(response_payload)
        try:
            extraction_file = upload_or_report(
                extraction_json_path,
                f"pdf-extractions/{job_id}",
                url,
                "extraction.json",
            )
        finally:
            if os.path.exists(extraction_json_path):
                os.remove(extraction_json_path)

        source_file = upload_or_report(
            str(pdf_path),
            f"pdf-extractions/{job_id}",
            url,
            "source.pdf",
        )

        response_payload["storage_mode"] = "bucket" if is_bucket_configured() else "bucket_unconfigured"
        response_payload["files"] = {
            "source_pdf": source_file,
            "extraction": extraction_file,
            "images": uploaded_images,
        }
        return response_payload

    except httpx.HTTPStatusError as e:
        logger.exception("PDF download failed")
        return {
            "success": False,
            "url": url,
            "error": f"PDF download failed with HTTP {e.response.status_code}.",
            "storage_config": get_bucket_config_status(),
        }
    except Exception as e:
        logger.exception("PDF extraction failed")
        return {
            "success": False,
            "url": url,
            "error": str(e),
            "storage_config": get_bucket_config_status(),
        }
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == "__main__":
    async def main():
        data = await pdf_extract(
            "https://adk.elsevierpure.com/ws/portalfiles/portal/59225442/1_EDS_basics.pdf"
        )
        print(json.dumps(data, indent=4, default=str))

    asyncio.run(main())
