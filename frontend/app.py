import os
import json
from urllib.parse import urlparse

import requests
import streamlit as st

# -----------------------------
# Page Configuration
# -----------------------------
st.set_page_config(
    page_title="Crawl4AI Developer Scraper",
    page_icon="🕸️",
    layout="wide",
)

# -----------------------------
# Backend API URL
# -----------------------------
API_URL = os.getenv("API_URL", "http://127.0.0.1:8000/crawl")
PDF_UPLOAD_URL = os.getenv(
    "PDF_UPLOAD_URL",
    f"{API_URL.rstrip('/').rsplit('/', 1)[0]}/pdf/upload",
)
MAX_PDF_UPLOAD_BYTES = 50 * 1024 * 1024


# -----------------------------
# Session State Defaults
# -----------------------------
if "show_pdf_upload" not in st.session_state:
    st.session_state.show_pdf_upload = False

if "pdf_upload_error" not in st.session_state:
    st.session_state.pdf_upload_error = None


# -----------------------------
# Helpers
# -----------------------------
def url_looks_like_pdf(url: str) -> bool:
    return urlparse(url.strip()).path.lower().endswith(".pdf")


def post_pdf_upload(uploaded_file):
    file_bytes = uploaded_file.getvalue()

    if len(file_bytes) > MAX_PDF_UPLOAD_BYTES:
        raise ValueError("PDF is too large. The upload limit is 50 MB.")

    return requests.post(
        PDF_UPLOAD_URL,
        files={
            "file": (
                uploaded_file.name,
                file_bytes,
                uploaded_file.type or "application/pdf",
            )
        },
        timeout=300,
    )


def render_analysis(analysis: dict | None):
    if not analysis:
        return

    if analysis.get("error"):
        st.warning(f"LLM analysis failed: {analysis['error']}")
        return

    st.markdown('<div class="card summary-card">', unsafe_allow_html=True)
    st.subheader("Executive Summary")
    if summary := analysis.get("summary"):
        st.write(summary)
    else:
        st.info("No executive summary found in response.")
    st.markdown("</div>", unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("Sentiment Analysis")
        sentiment = analysis.get("sentiment", "neutral").lower()

        class_name = "sentiment-neutral"
        if "positive" in sentiment or "good" in sentiment:
            class_name = "sentiment-positive"
        elif "negative" in sentiment or "bad" in sentiment:
            class_name = "sentiment-negative"

        st.markdown(
            f'<span class="sentiment-tag {class_name}">{sentiment}</span>',
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("Topics")
        topics = analysis.get("topics", [])
        if isinstance(topics, list) and topics:
            topic_badges = "".join(
                [f'<span class="badge">{topic}</span>' for topic in topics]
            )
            st.markdown(topic_badges, unsafe_allow_html=True)
        else:
            st.info("No topics classified.")
        st.markdown("</div>", unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("Keywords")
        keywords = analysis.get("keywords", [])
        if isinstance(keywords, list) and keywords:
            keyword_badges = "".join(
                [f'<span class="badge keyword-badge">{keyword}</span>' for keyword in keywords]
            )
            st.markdown(keyword_badges, unsafe_allow_html=True)
        else:
            st.info("No keywords extracted.")
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("Important Takeaways")
    points = analysis.get("important_points", [])
    if isinstance(points, list) and points:
        bullets = "".join([f'<li class="bullet-item">{pt}</li>' for pt in points])
        st.markdown(f'<ul class="bullet-list">{bullets}</ul>', unsafe_allow_html=True)
    else:
        st.info("No key points listed.")
    st.markdown("</div>", unsafe_allow_html=True)

    action_items = analysis.get("action_items", [])
    if isinstance(action_items, list) and action_items:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("Recommended Actions")
        for idx, item in enumerate(action_items):
            st.checkbox(item, key=f"action_item_{idx}")
        st.markdown("</div>", unsafe_allow_html=True)


def render_structured_extraction(data: dict):
    extracted_data = data.get("extracted_data", {})
    extracted_content = extracted_data.get("extracted_content")
    if not extracted_content:
        extracted_content = data.get("extracted_content")

    parsed_content = None
    if isinstance(extracted_content, str):
        try:
            parsed_content = json.loads(extracted_content)
        except Exception:
            parsed_content = None
    elif isinstance(extracted_content, (dict, list)):
        parsed_content = extracted_content

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("Extracted Content")

    if isinstance(parsed_content, list) and parsed_content and isinstance(parsed_content[0], dict):
        st.dataframe(parsed_content, use_container_width=True)
    elif parsed_content:
        st.json(parsed_content)
    elif extracted_content:
        st.code(extracted_content)
    else:
        st.info("No content matched the selection criteria.")

    st.markdown("</div>", unsafe_allow_html=True)


def render_multi_page_result(data: dict, method: str):
    pages = []
    if method == "dynamic":
        pages = data.get("pages", [])
    elif method == "deep":
        extracted_data = data.get("extracted_data", {})
        pages = extracted_data.get("pages", [])

    if pages:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("Crawl Overview")

        col_m1, col_m2 = st.columns(2)
        with col_m1:
            st.metric("Total Pages Crawled", len(pages))
        with col_m2:
            success_count = sum(1 for p in pages if p.get("success", False))
            st.metric("Successful Pages", success_count)

        page_table = [
            {
                "URL": p.get("url"),
                "Title": p.get("title") or "Untitled",
                "Status": "Success" if p.get("success") else "Failed",
            }
            for p in pages
        ]
        st.dataframe(page_table, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)


def render_snapshot_result(data: dict):
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("Page Snapshot Result")

    extracted = data.get("extracted_data", data)
    files = extracted.get("files", {})

    st.write(f"URL: {extracted.get('url')}")
    st.write(f"Status: {'Success' if extracted.get('success') else 'Failed'}")

    col_shot, col_pdf, col_mhtml = st.columns(3)

    with col_shot:
        if "screenshot" in files:
            shot = files["screenshot"]
            st.success("Screenshot Ready")
            if shot.get("url"):
                st.link_button("View Screenshot", shot["url"], use_container_width=True)
            else:
                st.info(f"Saved: {shot.get('local_path')}")

    with col_pdf:
        if "pdf" in files:
            pdf = files["pdf"]
            st.success("PDF Ready")
            if pdf.get("url"):
                st.link_button("Download PDF", pdf["url"], use_container_width=True)
            else:
                st.info(f"Saved: {pdf.get('local_path')}")

    with col_mhtml:
        if "mhtml" in files:
            mhtml = files["mhtml"]
            st.success("MHTML Ready")
            if mhtml.get("url"):
                st.link_button("Download MHTML", mhtml["url"], use_container_width=True)
            else:
                st.info(f"Saved: {mhtml.get('local_path')}")

    st.markdown("</div>", unsafe_allow_html=True)


def render_pdf_result(data: dict):
    extracted = data.get("extracted_data", data)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("PDF Extraction Result")
    st.write(f"Pages extracted: {extracted.get('page_count', 0)}")

    download = extracted.get("download", {})
    if download:
        st.caption(f"Retrieved via: {download.get('download_method', 'unknown')}")

    markdown = extracted.get("markdown", "")
    if markdown:
        st.text_area(
            "Extracted PDF text",
            markdown,
            height=260,
            disabled=True,
            key="pdf_extracted_text_area",
        )
    else:
        st.warning("No selectable text was found in this PDF.")

    st.markdown("</div>", unsafe_allow_html=True)


# -----------------------------
# Styling
# -----------------------------
st.markdown(
    """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&display=swap');

    .stApp {
        background-color: #090d16 !important;
        color: #f1f5f9 !important;
        font-family: 'Outfit', sans-serif !important;
    }

    .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6, .stApp p, .stApp li, .stApp div, .stApp span {
        color: #f1f5f9;
        font-family: 'Outfit', sans-serif !important;
    }

    .stApp label {
        color: #94a3b8 !important;
        font-size: 0.95rem !important;
        font-weight: 600 !important;
        margin-bottom: 8px !important;
    }

    .main-title {
        font-size: 3rem;
        font-weight: 800;
        background: linear-gradient(135deg, #00f2fe 0%, #4facfe 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent !important;
        margin-bottom: 0.2rem;
        letter-spacing: -0.8px;
    }

    .subtitle {
        font-size: 1.05rem;
        color: #94a3b8 !important;
        margin-bottom: 2rem;
    }

    .card {
        background: #111827 !important;
        border: 1px solid #1f2937 !important;
        border-radius: 18px;
        padding: 24px;
        margin-bottom: 24px;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.35);
    }

    .summary-card {
        background: linear-gradient(135deg, #1e1b4b 0%, #111827 100%) !important;
        border-left: 5px solid #00f2fe !important;
    }

    .badge {
        display: inline-block;
        padding: 6px 14px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
        margin-right: 8px;
        margin-bottom: 8px;
        background: rgba(0, 242, 254, 0.12) !important;
        color: #00f2fe !important;
        border: 1px solid rgba(0, 242, 254, 0.25) !important;
    }

    .keyword-badge {
        background: rgba(249, 168, 37, 0.12) !important;
        color: #ffb300 !important;
        border: 1px solid rgba(249, 168, 37, 0.25) !important;
    }

    .sentiment-tag {
        display: inline-flex;
        align-items: center;
        padding: 8px 18px;
        border-radius: 12px;
        font-weight: 700;
        font-size: 0.95rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    .sentiment-positive {
        background: rgba(76, 175, 80, 0.15) !important;
        color: #4caf50 !important;
        border: 1px solid rgba(76, 175, 80, 0.3) !important;
    }

    .sentiment-negative {
        background: rgba(244, 67, 54, 0.15) !important;
        color: #f44336 !important;
        border: 1px solid rgba(244, 67, 54, 0.3) !important;
    }

    .sentiment-neutral {
        background: rgba(158, 158, 158, 0.15) !important;
        color: #e2e8f0 !important;
        border: 1px solid rgba(158, 158, 158, 0.3) !important;
    }

    .bullet-list {
        list-style-type: none;
        padding-left: 0;
    }

    .bullet-item {
        position: relative;
        padding-left: 28px;
        margin-bottom: 12px;
        font-size: 1rem;
        line-height: 1.5;
        color: #e2e8f0 !important;
    }

    .bullet-item::before {
        content: "✦";
        position: absolute;
        left: 4px;
        top: 0;
        color: #00f2fe !important;
        font-size: 1.1rem;
    }

    .stCheckbox label p {
        color: #e2e8f0 !important;
        font-size: 1rem !important;
        font-family: 'Outfit', sans-serif !important;
    }

    div[data-baseweb="input"] {
        background-color: #ffffff !important;
        border: 1px solid #cbd5e1 !important;
        border-radius: 8px !important;
    }

    div[data-baseweb="input"] input {
        color: #000000 !important;
    }

    div[data-baseweb="select"] {
        background-color: #ffffff !important;
        border: 1px solid #cbd5e1 !important;
        border-radius: 8px !important;
    }

    div[data-baseweb="select"] > div {
        color: #000000 !important;
    }

    div[role="listbox"] {
        background-color: #ffffff !important;
        border: 1px solid #cbd5e1 !important;
    }

    div[role="option"] {
        color: #000000 !important;
    }

    div[role="option"]:hover {
        background-color: #f1f5f9 !important;
    }

    .stButton button {
        background: linear-gradient(135deg, #00f2fe 0%, #4facfe 100%) !important;
        color: #090d16 !important;
        border: none !important;
        font-weight: 700 !important;
        border-radius: 12px !important;
        padding: 12px 24px !important;
        font-size: 1rem !important;
        box-shadow: 0 4px 14px rgba(0, 242, 254, 0.25) !important;
    }

    .stButton button:hover {
        color: #090d16 !important;
    }
</style>
""",
    unsafe_allow_html=True,
)

# -----------------------------
# Header
# -----------------------------
st.markdown(
    '<div class="main-title">Crawl4AI Developer Scraper</div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="subtitle">Extract and auto-summarize web content with zero-boilerplate context cleaning</div>',
    unsafe_allow_html=True,
)

# -----------------------------
# Layout
# -----------------------------
col1, col2 = st.columns([1, 2], gap="large")

with col1:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("Extraction Target")

    input_url = st.text_input(
        "Website or PDF URL",
        placeholder="https://example.com",
        key="input_url",
    )

    selected_method = st.selectbox(
        "Extraction Method",
        ["single", "deep", "dynamic", "snapshot", "css", "xpath", "regex", "pdf"],
        key="selected_method",
    )

    show_pdf_upload = (
        selected_method == "pdf"
        or url_looks_like_pdf(input_url)
        or st.session_state.show_pdf_upload
    )

    uploaded_pdf = None
    if show_pdf_upload:
        st.caption("Use a public PDF URL, or upload the file when its URL is blocked or unsupported.")
        if st.session_state.pdf_upload_error:
            st.warning(
                f"The URL PDF could not be downloaded: {st.session_state.pdf_upload_error}"
            )
            st.info("Upload the PDF file below to continue.")

        uploaded_pdf = st.file_uploader(
            "Upload PDF",
            type=["pdf"],
            key="uploaded_pdf",
            help="Uploaded PDFs are extracted and analyzed with the same LLM workflow.",
        )

    st.markdown("<br>", unsafe_allow_html=True)
    start_btn = st.button("Start Extraction", use_container_width=True, key="start_btn")
    st.markdown("</div>", unsafe_allow_html=True)

with col2:
    if start_btn:
        if not input_url.strip() and uploaded_pdf is None:
            st.warning("Enter a URL or upload a PDF file.")
        else:
            try:
                request_method = "pdf" if url_looks_like_pdf(input_url) else selected_method

                if uploaded_pdf is not None:
                    with st.spinner("Uploading PDF, extracting, and analyzing..."):
                        response = post_pdf_upload(uploaded_pdf)
                    st.session_state.show_pdf_upload = False
                    st.session_state.pdf_upload_error = None

                else:
                    payload = {
                        "url": input_url.strip(),
                        "method": request_method,
                    }
                    with st.spinner("Crawling content and analyzing context..."):
                        response = requests.post(
                            API_URL,
                            json=payload,
                            timeout=300,
                        )

                if response.status_code != 200:
                    st.error(f"Backend API returned error code {response.status_code}")
                    try:
                        st.json(response.json())
                    except Exception:
                        st.text(response.text)
                    st.stop()

                res_data = response.json()
                data = res_data.get("data", res_data)

                backend_method = data.get("method", request_method)
                llm_analysis = data.get("llm_analysis")

                extracted_result = data.get("extracted_data", data)
                extraction_succeeded = data.get(
                    "success",
                    extracted_result.get("success", True),
                )

                if not extraction_succeeded:
                    error = extracted_result.get("error", "Extraction failed.")

                    if request_method == "pdf" and uploaded_pdf is None:
                        st.session_state.show_pdf_upload = True
                        st.session_state.pdf_upload_error = (
            "This PDF URL is blocked by the source server (HTTP 403). "
            "Please upload the PDF file directly."
        )
                         if "start_btn" in st.session_state:
                             del st.session_state["start_btn"]
                         st.rerun()
                    st.error(f"Extraction failed: {error}")
                    with st.expander("Debug: Raw Crawl Metadata"):
                        st.json(data)
                    st.stop()
                st.toast("Extraction completed successfully!")

                if backend_method in ["css", "xpath", "regex"]:
                    render_structured_extraction(data)

                elif backend_method in ["dynamic", "deep"]:
                    render_multi_page_result(data, backend_method)

                elif backend_method == "snapshot":
                    render_snapshot_result(data)

                elif backend_method == "pdf":
                    render_pdf_result(data)

                else:
                    st.markdown('<div class="card">', unsafe_allow_html=True)
                    st.subheader("Extracted Result")

                    extracted = data.get("extracted_data", data)

                    if extracted.get("title"):
                        st.write(f"**Title:** {extracted.get('title')}")

                    if extracted.get("url"):
                        st.write(f"**URL:** {extracted.get('url')}")

                    markdown = extracted.get("markdown") or extracted.get("content") or ""
                    if markdown:
                        st.text_area(
                            "Extracted Content",
                            markdown,
                            height=350,
                            disabled=True,
                            key="generic_extracted_content",
                        )
                    else:
                        st.info("No extracted text content available.")

                    st.markdown("</div>", unsafe_allow_html=True)

                if llm_analysis:
                    render_analysis(llm_analysis)
                elif backend_method != "snapshot":
                    st.markdown('<div class="card">', unsafe_allow_html=True)
                    st.warning("No AI summary analysis was generated for this method or site.")
                    st.markdown("</div>", unsafe_allow_html=True)

                with st.expander("Debug: Raw Crawl Metadata"):
                    st.json(data)

            except requests.exceptions.Timeout:
                st.error("Connection timed out. The backend is taking too long to respond.")
            except requests.exceptions.ConnectionError:
                st.error("Unable to connect to the backend server. Please verify it is running.")
            except ValueError as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"Unexpected error occurred: {e}")
    else:
        st.markdown(
            """
            <div class="card" style="text-align: center; padding: 60px 40px; border-style: dashed; border-width: 2px;">
                <h2>Ready to extract content</h2>
                <p style="color: rgba(255, 255, 255, 0.65);">
                    Enter a URL and select an extraction method on the left to begin.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
