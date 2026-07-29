import os
import streamlit as st
import requests
# -----------------------------
# Page Configuration
# -----------------------------
st.set_page_config(
    page_title="Crawl4AI Web Scraper",
    page_icon="🕷️",
    layout="wide"
)
# -----------------------------
# Backend API URL
# -----------------------------
API_URL = os.getenv(
    "API_URL",
    "http://127.0.0.1:8000/crawl"
)
PDF_UPLOAD_API_URL = os.getenv(
    "PDF_UPLOAD_API_URL",
    f"{API_URL.rsplit('/', 1)[0]}/pdf/upload",
)
# -----------------------------
# UI
# -----------------------------
st.title("🕷️ Crawl4AI Web Scraper")
st.write("Extract structured information from websites using Crawl4AI.")
url = st.text_input(" Enter Website URL")
method = st.selectbox(
    " Select Extraction Method",
    [
        "single",
        "deep",
        "dynamic",
        "snapshot",
        "css",
        "xpath",
        "regex",
        "pdf"
    ]
)
uploaded_pdf = None
if method == "pdf":
    st.caption("If a website blocks the backend from downloading a PDF, download it in your browser and upload it here.")
    uploaded_pdf = st.file_uploader("Or upload a PDF (50 MB maximum)", type=["pdf"])
# -----------------------------
# Crawl Button
# -----------------------------
if st.button(" Start Crawling", use_container_width=True):
    if not url.strip() and not uploaded_pdf:
        st.warning("Please enter a URL or upload a PDF.")
    else:
        try:
            with st.spinner("🕷️ Crawling website... Please wait..."):
                if method == "pdf" and uploaded_pdf:
                    response = requests.post(
                        PDF_UPLOAD_API_URL,
                        files={
                            "file": (
                                uploaded_pdf.name,
                                uploaded_pdf.getvalue(),
                                uploaded_pdf.type or "application/pdf",
                            )
                        },
                        timeout=300,
                    )
                else:
                    response = requests.post(
                        API_URL,
                        json={"url": url, "method": method},
                        timeout=300,
                    )
            if response.status_code == 200:
                st.success("Crawling Completed!")
                res_data = response.json()
                data = res_data.get("data", res_data)
                # ===========================================
                # Deep Crawl / Dynamic Crawl
                # ===========================================
                if method in ["deep", "dynamic"]:
                    st.subheader("🌐 Crawl Results")
                    extracted = data.get("extracted_data", data)
                    pages = extracted.get("pages", [])
                    if pages:
                        st.write(
                            f"**Total Pages Crawled:** {extracted.get('total_pages', len(pages))}"
                        )
                        for i, page in enumerate(pages, start=1):
                            st.markdown(f"### 📄 Page {i}")
                            st.write(f"**URL:** {page.get('url')}")
                            st.write(f"**Success:** {page.get('success')}")
                            if page.get("metadata"):
                                with st.expander(f"Metadata - Page {i}"):
                                    st.json(page["metadata"])
                            if page.get("markdown"):
                                with st.expander(f"Markdown Preview - Page {i}"):
                                    st.markdown(page["markdown"])
                            st.divider()
                    else:
                        st.warning("No pages were returned.")
                # ===========================================
                # Snapshot
                # ===========================================
                elif method == "snapshot":
                    st.subheader("📸 Page Snapshot")
                    extracted = data.get("extracted_data", data)
                    files = extracted.get("files", {})
                    st.write(f"**URL:** {extracted.get('url')}")
                    st.write(f"**Success:** {extracted.get('success')}")
                    st.write(f"**Job ID:** {extracted.get('job_id', 'N/A')}")
                    if not extracted.get("success", False):
                        st.error(extracted.get("message", "Snapshot failed."))
                    elif extracted.get("errors"):
                        st.warning("Snapshot completed with partial artifact failures.")
                    if extracted.get("errors"):
                        with st.expander("Snapshot Errors"):
                            st.json(extracted["errors"])
                    if "screenshot" in files:
                        shot = files["screenshot"]
                        if shot.get("upload_error"):
                            st.error(f"Screenshot upload failed: {shot['upload_error']}")
                        elif shot.get("url"):
                            st.success("Screenshot generated")
                            st.markdown(f"[Open Screenshot]({shot['url']})")
                        elif shot.get("local_path"):
                            st.success("Screenshot generated")
                            st.info(f"Saved locally: {shot['local_path']}")
                    if "pdf" in files:
                        pdf = files["pdf"]
                        if pdf.get("upload_error"):
                            st.error(f"PDF upload failed: {pdf['upload_error']}")
                        elif pdf.get("url"):
                            st.success("PDF generated")
                            st.markdown(f"[Open PDF]({pdf['url']})")
                        elif pdf.get("local_path"):
                            st.success("PDF generated")
                            st.info(f"Saved locally: {pdf['local_path']}")
                    if "mhtml" in files:
                        mhtml = files["mhtml"]
                        if mhtml.get("upload_error"):
                            st.error(f"MHTML upload failed: {mhtml['upload_error']}")
                        elif mhtml.get("url"):
                            st.success("MHTML generated")
                            st.markdown(f"[Download MHTML]({mhtml['url']})")
                        elif mhtml.get("local_path"):
                            st.success("MHTML generated")
                            st.info(f"Saved locally: {mhtml['local_path']}")
                    with st.expander("Snapshot Response"):
                        st.json(extracted)
                # ===========================================
                # PDF Extraction
                # ===========================================
                elif method == "pdf":
                    st.subheader(" PDF Extraction")
                    extracted = data.get("extracted_data", data)
                    if not extracted.get("success", False):
                        st.error(extracted.get("error", "PDF extraction failed."))
                    else:
                        st.write(f"**Pages:** {extracted.get('page_count', 0)}")
                        st.write(f"**Images:** {extracted.get('image_count', 0)}")

                        files = extracted.get("files", {})
                        source_pdf = files.get("source_pdf")
                        extraction = files.get("extraction")
                        images = files.get("images", [])

                        if source_pdf:
                            if source_pdf.get("url"):
                                st.success("Source PDF uploaded")
                                st.markdown(f"[Open Source PDF]({source_pdf['url']})")
                            elif source_pdf.get("upload_error"):
                                st.error(f"Source PDF upload failed: {source_pdf['upload_error']}")

                        if extraction:
                            if extraction.get("url"):
                                st.success("Extraction JSON uploaded")
                                st.markdown(f"[Open Extraction JSON]({extraction['url']})")
                            elif extraction.get("upload_error"):
                                st.error(f"Extraction JSON upload failed: {extraction['upload_error']}")

                        uploaded_image_count = sum(1 for image in images if image.get("url"))
                        if images:
                            st.write(f"**Uploaded Images:** {uploaded_image_count}/{len(images)}")
                            with st.expander("PDF Image Files"):
                                for image in images:
                                    label = image.get("filename", "image")
                                    if image.get("url"):
                                        st.markdown(f"- [{label}]({image['url']})")
                                    elif image.get("upload_error"):
                                        st.error(f"{label}: {image['upload_error']}")

                    with st.expander("PDF Response"):
                        st.json(extracted)
                # ===========================================
                # CSS / XPath / Regex / Single
                # ===========================================
                else:
                    st.subheader("Extraction Result")
                    extracted = data.get("extracted_data", data)
                    st.json(extracted)
                if data.get("llm_analysis"):
                    st.subheader(" AI Analysis")
                    st.write(data["llm_analysis"])
            else:
                st.error(f" API Error: {response.status_code}")
                try:
                    st.json(response.json())
                except Exception:
                    st.text(response.text)
        except requests.exceptions.Timeout:
            st.error(
                "⏳ Request timed out. The backend may still be processing. Please try again."
            )
        except requests.exceptions.ConnectionError:
            st.error(
                "Unable to connect to the backend API. Please ensure the backend is running."
            )
        except Exception as e:
            st.error(f"Unexpected Error: {e}")
