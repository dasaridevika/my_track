import asyncio
import json
import logging
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from urllib.parse import urljoin, urlparse

import fitz
import httpx
import requests
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

PDF_EXTRACTOR_VERSION = "direct-v7-http-client-fallback"


def is_pdf_content(content: bytes) -> bool:
    """Validate by signature because many servers send PDFs as octet-stream."""
    return content.lstrip().startswith(b"%PDF")


def is_pdf_response(content_type: str, content: bytes) -> bool:
    return "pdf" in (content_type or "").lower() or is_pdf_content(content)


def save_pdf_response(response, destination: Path, download_method: str, content=None, **extra):
    content = response.content if content is None else content
    content_type = response.headers.get("content-type", "").lower()
    if not is_pdf_content(content):
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
        "download_method": download_method,
        **extra,
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
    headers = dict(PDF_HEADERS)

    async with httpx.AsyncClient(follow_redirects=True, timeout=120.0, headers=headers) as client:
        response = await client.get(url)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code in {401, 403, 406, 429}:
                range_result = await download_pdf_with_range_request(
                    client,
                    url,
                    destination,
                    headers,
                    e.response.status_code,
                )
                if range_result:
                    return range_result

                requests_result = await download_pdf_with_requests(
                    url,
                    destination,
                    headers,
                    e.response.status_code,
                )
                if requests_result:
                    return requests_result

                logger.warning(
                    "Direct PDF download blocked with HTTP %s; trying browser fallback",
                    e.response.status_code,
                )
                return await download_pdf_with_browser(url, destination)
            raise

    if not is_pdf_content(response.content):
        # A URL can be a journal/repository landing page rather than the PDF
        # itself.  Let the browser discover the document it embeds or links to.
        return await download_pdf_with_browser(url, destination)

    return save_pdf_response(response, destination, "httpx")


async def download_pdf_with_requests(
    url: str,
    destination: Path,
    headers: dict,
    blocked_status: int,
):
    """Retry with Requests before escalating to a browser.

    CDNs sometimes apply different policies to distinct TLS/HTTP client
    implementations.  This is a normal public-URL retry, not an attempt to
    bypass authentication or access controls.
    """

    def request_pdf():
        with requests.Session() as session:
            return session.get(
                url,
                headers=headers,
                allow_redirects=True,
                timeout=(30, 120),
            )

    try:
        response = await asyncio.to_thread(request_pdf)
    except requests.RequestException as requests_error:
        logger.warning(
            "Requests PDF retry failed after HTTP %s block: %s",
            blocked_status,
            requests_error,
        )
        return None

    if not response.ok:
        logger.warning(
            "Requests PDF retry returned HTTP %s after HTTP %s block",
            response.status_code,
            blocked_status,
        )
        return None

    if not is_pdf_content(response.content):
        logger.warning(
            "Requests PDF retry returned non-PDF content_type=%s bytes=%s",
            response.headers.get("content-type", "unknown"),
            len(response.content),
        )
        return None

    return save_pdf_response(
        response,
        destination,
        "requests",
        recovered_from_status=blocked_status,
    )


async def download_pdf_with_range_request(
    client: httpx.AsyncClient,
    url: str,
    destination: Path,
    headers: dict,
    blocked_status: int,
):
    range_headers = {
        **headers,
        "Range": "bytes=0-",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }

    try:
        response = await client.get(url, headers=range_headers)
        response.raise_for_status()
    except Exception as range_error:
        logger.warning(
            "Range PDF retry failed after HTTP %s block: %s",
            blocked_status,
            range_error,
        )
        return None

    content = response.content
    content_type = response.headers.get("content-type", "").lower()

    if not is_pdf_content(content):
        preview = content[:200].decode("utf-8", errors="replace")
        logger.warning(
            "Range PDF retry returned non-PDF content_type=%s bytes=%s preview=%r",
            content_type or "unknown",
            len(content),
            preview,
        )
        return None

    return save_pdf_response(
        response,
        destination,
        "httpx-range",
        recovered_from_status=blocked_status,
    )


async def download_pdf_with_browser(url: str, destination: Path):
    """Download a direct PDF or discover one from an accessible landing page.

    ``context.request`` shares the browser's cookies, but it is still not a
    navigation.  Some repositories enforce navigation/referrer checks, so we
    first load the URL in a real page and then use the warmed session for any
    PDF links or embedded viewers found there.
    """
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
            observed_pdf_responses = []

            def remember_pdf_response(response):
                """Remember browser-loaded PDF assets from dynamic viewers."""
                try:
                    content_type = response.headers.get("content-type", "").lower()
                    if "pdf" in content_type or ".pdf" in response.url.lower():
                        observed_pdf_responses.append(response)
                except Exception:
                    # Response metadata is optional diagnostic data.  A failed
                    # inspection must not break navigation or extraction.
                    pass

            page.on("response", remember_pdf_response)
            if origin:
                try:
                    await page.goto(origin, wait_until="domcontentloaded", timeout=30000)
                except Exception as warmup_error:
                    logger.warning("PDF browser warmup failed: %s", warmup_error)

            navigation = None
            try:
                navigation = await page.goto(url, wait_until="domcontentloaded", timeout=120000)
            except Exception as navigation_error:
                # A browser may report ERR_ABORTED for an attachment download;
                # the context request below can still retrieve it with cookies.
                logger.info("PDF browser navigation did not complete: %s", navigation_error)
            if navigation and navigation.ok:
                content = await navigation.body()
                if is_pdf_response(navigation.headers.get("content-type", ""), content):
                    return save_pdf_response(
                        navigation,
                        destination,
                        "playwright-navigation",
                        content=content,
                    )

            # Give a client-rendered viewer a brief opportunity to request its
            # source document before inspecting the DOM and network responses.
            await page.wait_for_timeout(1000)

            candidate_urls = await page.evaluate(
                """() => [...new Set([
                    ...[...document.querySelectorAll('a[href], iframe[src], embed[src], object[data]')]
                        .map(node => node.href || node.src || node.data)
                        .filter(Boolean),
                    ...[...document.querySelectorAll('[data-pdf], [data-url]')]
                        .map(node => node.dataset.pdf || node.dataset.url)
                        .filter(Boolean),
                ])]"""
            )
            # Do not invent a Referer for the original direct URL.  Some CDN
            # WAF rules (including CloudFront deployments) reject same-origin
            # or fabricated referers even though the public object is readable
            # without one.  Links discovered in a page do retain that page as
            # their genuine referer.
            candidates = [(url, None)]
            candidates.extend(
                (urljoin(page.url, candidate), page.url)
                for candidate in candidate_urls
                if ".pdf" in candidate.lower() or "pdf" in candidate.lower()
            )

            for response in observed_pdf_responses:
                if not response.ok:
                    continue
                try:
                    content = await response.body()
                except Exception as response_body_error:
                    logger.debug(
                        "Could not read a browser-observed PDF response: %s",
                        response_body_error,
                    )
                    continue
                if is_pdf_response(response.headers.get("content-type", ""), content):
                    return save_pdf_response(
                        response,
                        destination,
                        "playwright-viewer-network",
                        content=content,
                    )

            failures = []
            for candidate, referer in dict.fromkeys(candidates):
                request_headers = dict(PDF_HEADERS)
                if referer:
                    request_headers["Referer"] = referer
                response = await context.request.get(
                    candidate,
                    headers=request_headers,
                    timeout=120000,
                )
                if not response.ok:
                    failures.append(f"{response.status} {candidate}")
                    continue
                content = await response.body()
                if is_pdf_response(response.headers.get("content-type", ""), content):
                    return save_pdf_response(
                        response,
                        destination,
                        "playwright-session",
                        content=content,
                    )
                failures.append(f"non-PDF {candidate}")

            status = navigation.status if navigation else "no response"
            attempted = "; ".join(failures[:3]) or "no PDF links were found"
            raise ValueError(
                "PDF access was denied or the page does not expose a downloadable PDF "
                f"(navigation status: {status}; attempts: {attempted}). "
                "Use a public direct PDF URL or provide the required authenticated session."
            )
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


async def create_pdf_response(
    pdf_path: Path,
    image_dir: Path,
    job_id: str,
    source_url: str,
    download_info: dict,
):
    """Extract a local PDF and upload its artifacts using the shared pipeline."""
    extracted = await asyncio.to_thread(extract_pdf_content, pdf_path, image_dir)
    response_payload = {
        "success": True,
        "url": source_url,
        "job_id": job_id,
        "extractor_version": PDF_EXTRACTOR_VERSION,
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
            source_url,
            image["filename"],
        )
        file_data["page"] = image["page"]
        uploaded_images.append(file_data)

    extraction_json_path = write_json_temp(response_payload)
    try:
        extraction_file = upload_or_report(
            extraction_json_path,
            f"pdf-extractions/{job_id}",
            source_url,
            "extraction.json",
        )
    finally:
        if os.path.exists(extraction_json_path):
            os.remove(extraction_json_path)

    source_file = upload_or_report(
        str(pdf_path),
        f"pdf-extractions/{job_id}",
        source_url,
        "source.pdf",
    )

    response_payload["storage_mode"] = "bucket" if is_bucket_configured() else "bucket_unconfigured"
    response_payload["files"] = {
        "source_pdf": source_file,
        "extraction": extraction_file,
        "images": uploaded_images,
    }
    return response_payload


def pdf_error_response(source_url: str, error: Exception | str):
    return {
        "success": False,
        "url": source_url,
        "extractor_version": PDF_EXTRACTOR_VERSION,
        "error": str(error),
        "storage_config": get_bucket_config_status(),
    }


async def pdf_extract(url: str):
    job_id = uuid.uuid4().hex
    work_dir = Path(tempfile.mkdtemp(prefix=f"pdf-extract-{job_id}-"))
    image_dir = work_dir / "images"
    image_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = work_dir / "source.pdf"

    try:
        download_info = await download_pdf(url.strip(), pdf_path)
        return await create_pdf_response(pdf_path, image_dir, job_id, url, download_info)
    except Exception as error:
        logger.exception("PDF URL extraction failed")
        return pdf_error_response(url, error)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


async def pdf_extract_uploaded_file(file_bytes: bytes, filename: str | None):
    """Extract a user-uploaded PDF when remote URL access is unavailable."""
    safe_filename = Path(filename or "uploaded.pdf").name or "uploaded.pdf"
    source_url = f"upload://{safe_filename}"
    job_id = uuid.uuid4().hex
    work_dir = Path(tempfile.mkdtemp(prefix=f"pdf-upload-{job_id}-"))
    image_dir = work_dir / "images"
    image_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = work_dir / "source.pdf"

    try:
        if not is_pdf_content(file_bytes):
            raise ValueError("The uploaded file is not a valid PDF.")

        pdf_path.write_bytes(file_bytes)
        download_info = {
            "content_type": "application/pdf",
            "bytes": len(file_bytes),
            "final_url": source_url,
            "download_method": "upload",
            "filename": safe_filename,
        }
        return await create_pdf_response(pdf_path, image_dir, job_id, source_url, download_info)
    except Exception as error:
        logger.exception("Uploaded PDF extraction failed")
        return pdf_error_response(source_url, error)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == "__main__":
    async def main():
        data = await pdf_extract(
            "https://adk.elsevierpure.com/ws/portalfiles/portal/59225442/1_EDS_basics.pdf"
        )
        print(json.dumps(data, indent=4, default=str))

    asyncio.run(main())
