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
    extracted_data = data.get("extracted_data")
    if isinstance(extracted_data, dict):
        pages = extracted_data.get("pages") or data.get("pages") or []
        categories = extracted_data.get("categories") or data.get("categories") or []
    else:
        pages = data.get("pages", [])
        categories = data.get("categories", [])


    if pages:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("Crawl Overview")

        if categories:
            badges = "".join([f'<span class="badge">{c}</span>' for c in categories])
            st.markdown(f"**Best-First Focus Categories:** {badges}", unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)

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

        with st.expander("View Pages Content"):
            for idx, p in enumerate(pages, 1):
                st.markdown(f"#### Page {idx}: [{p.get('title') or 'Untitled'}]({p.get('url')})")
                md_text = p.get("markdown") or p.get("content") or ""
                if md_text:
                    st.text_area(f"Content Preview ({p.get('url')})", md_text[:2000], height=150, key=f"page_preview_{idx}")
                else:
                    st.caption("No text extracted for this page.")
                st.divider()

        all_links = extracted.get("all_links", [])
        if not all_links:
            all_links = []
            seen_hrefs = set()
            for p in pages:
                p_links = p.get("links", {})
                if isinstance(p_links, dict):
                    combined = p_links.get("internal", []) + p_links.get("external", [])
                    for l in combined:
                        href = l.get("href") if isinstance(l, dict) else str(l)
                        if href and href not in seen_hrefs:
                            seen_hrefs.add(href)
                            all_links.append({
                                "href": href,
                                "text": l.get("text", "") if isinstance(l, dict) else href,
                                "type": l.get("type", "internal") if isinstance(l, dict) else "internal"
                            })

        with st.expander(f"View Discovered Links ({len(all_links)} links)"):
            if all_links:
                links_table = [
                    {
                        "URL": l.get("href"),
                        "Anchor Text": l.get("text") or "N/A",
                        "Type": l.get("type", "internal"),
                    }
                    for l in all_links[:250]
                ]
                st.dataframe(links_table, use_container_width=True)
            else:
                st.caption("No internal or external links were extracted.")

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

    :root {
        --bg-main: #06152d;
        --bg-card: #0a1f44;
        --bg-card-2: #0d2a57;
        --bg-soft: #102f63;
        --border: #294a7a;

        --text-main: #ffffff;
        --text-muted: #dbeafe;
        --text-soft: #bfdbfe;

        --accent-1: #38bdf8;
        --accent-2: #60a5fa;

        --success: #22c55e;
        --danger: #ef4444;
        --warning: #f59e0b;
    }
    a[kind="primary"],
a[kind="secondary"],
a[kind="tertiary"] {
    background: linear-gradient(135deg, #38bdf8 0%, #60a5fa 100%) !important;
    color: #000000 !important;
    border: none !important;
    border-radius: 12px !important;
    font-weight: 700 !important;
    box-shadow: 0 4px 14px rgba(56, 189, 248, 0.25) !important;
    text-decoration: none !important;
}

a[kind="primary"]:hover,
a[kind="secondary"]:hover,
a[kind="tertiary"]:hover,
a[kind="primary"]:focus,
a[kind="secondary"]:focus,
a[kind="tertiary"]:focus,
a[kind="primary"]:active,
a[kind="secondary"]:active,
a[kind="tertiary"]:active,
a[kind="primary"]:visited,
a[kind="secondary"]:visited,
a[kind="tertiary"]:visited {
    color: #000000 !important;
    -webkit-text-fill-color: #000000 !important;
    text-decoration: none !important;
    filter: brightness(1.02);
}

a[kind="primary"] *,
a[kind="secondary"] *,
a[kind="tertiary"] * {
    color: #000000 !important;
    -webkit-text-fill-color: #000000 !important;
}
    .stApp {
        background: var(--bg-main) !important;
        color: var(--text-main) !important;
        font-family: 'Outfit', sans-serif !important;
    }

    .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6,
    .stApp p, .stApp li, .stApp label, .stApp span, .stApp div {
        color: var(--text-main) !important;
        font-family: 'Outfit', sans-serif !important;
    }

    .stApp small,
    .stApp .caption,
    .stApp [data-testid="stCaptionContainer"] {
        color: var(--text-soft) !important;
    }

    .main-title {
        font-size: 3rem;
        font-weight: 800;
        background: linear-gradient(135deg, #7dd3fc 0%, #bfdbfe 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent !important;
        margin-bottom: 0.2rem;
        letter-spacing: -0.8px;
    }

    .subtitle {
        font-size: 1.05rem;
        color: var(--text-soft) !important;
        margin-bottom: 2rem;
    }

    .card {
        background: var(--bg-card) !important;
        border: 1px solid var(--border) !important;
        border-radius: 18px;
        padding: 24px;
        margin-bottom: 24px;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.28);
    }

    .summary-card {
        background: linear-gradient(135deg, var(--bg-card-2) 0%, var(--bg-card) 100%) !important;
        border-left: 5px solid var(--accent-1) !important;
    }

    .badge {
        display: inline-block;
        padding: 6px 14px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
        margin-right: 8px;
        margin-bottom: 8px;
        background: #12356c !important;
        color: #ffffff !important;
        border: 1px solid #3b82f6 !important;
    }

    .keyword-badge {
        background: #1e3a5f !important;
        color: #ffffff !important;
        border: 1px solid #60a5fa !important;
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
        color: #ffffff !important;
    }

    .sentiment-positive {
        background: #14532d !important;
        border: 1px solid #22c55e !important;
    }

    .sentiment-negative {
        background: #7f1d1d !important;
        border: 1px solid #ef4444 !important;
    }

    .sentiment-neutral {
        background: #334155 !important;
        border: 1px solid #94a3b8 !important;
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
        color: #ffffff !important;
    }

    .bullet-item::before {
        content: "✦";
        position: absolute;
        left: 4px;
        top: 0;
        color: #7dd3fc !important;
        font-size: 1.1rem;
    }

    .stCheckbox label p,
    .stRadio label p,
    .stMarkdown,
    .stText,
    .stCaption {
        color: #ffffff !important;
    }

    /* Inputs (Text Input, Number Input, Text Area, Selectbox) - Dark Theme & Autofill Fix */
    div[data-baseweb="input"],
    div[data-baseweb="base-input"],
    [data-testid="stTextInput"] > div,
    [data-testid="stTextInput"] input,
    [data-testid="stNumberInput"] input,
    [data-testid="stSelectbox"] > div {
        background-color: #0d2242 !important;
        background: #0d2242 !important;
        border: 1.5px solid #3b82f6 !important;
        border-radius: 10px !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.25) !important;
    }

    div[data-baseweb="input"] input,
    div[data-baseweb="input"] textarea,
    [data-testid="stTextInput"] input,
    [data-testid="stNumberInput"] input {
        background-color: #0d2242 !important;
        background: #0d2242 !important;
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
        caret-color: #ffffff !important;
        font-weight: 500 !important;
    }

    /* Kill Chrome / Edge White Autofill Background */
    div[data-baseweb="input"] input:-webkit-autofill,
    div[data-baseweb="input"] input:-webkit-autofill:hover,
    div[data-baseweb="input"] input:-webkit-autofill:focus,
    div[data-baseweb="input"] input:-webkit-autofill:active,
    [data-testid="stTextInput"] input:-webkit-autofill,
    [data-testid="stTextInput"] input:-webkit-autofill:hover,
    [data-testid="stTextInput"] input:-webkit-autofill:focus,
    [data-testid="stTextInput"] input:-webkit-autofill:active {
        -webkit-text-fill-color: #ffffff !important;
        -webkit-box-shadow: 0 0 0px 1000px #0d2242 inset !important;
        box-shadow: 0 0 0px 1000px #0d2242 inset !important;
        transition: background-color 50000s ease-in-out 0s !important;
        color: #ffffff !important;
    }

    div[data-baseweb="input"] input::placeholder,
    div[data-baseweb="input"] textarea::placeholder,
    [data-testid="stTextInput"] input::placeholder {
        color: #cbd5e1 !important;
        -webkit-text-fill-color: #cbd5e1 !important;
        opacity: 0.85 !important;
    }

    div[data-baseweb="input"]:focus-within,
    div[data-baseweb="select"]:focus-within,
    [data-testid="stTextInput"] div[data-baseweb="input"]:focus-within {
        border-color: #38bdf8 !important;
        box-shadow: 0 0 12px rgba(56, 189, 248, 0.4) !important;
    }


    /* Selectbox */
    div[data-baseweb="select"] {
        color: #ffffff !important;
    }

    div[data-baseweb="select"] > div {
        background-color: #13284c !important;
        border: 1.5px solid #3b82f6 !important;
        border-radius: 10px !important;
        color: #ffffff !important;
    }


    div[data-baseweb="select"] * {
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
    }

    /* Dropdown */
    div[role="listbox"] {
        background-color: var(--bg-card) !important;
        border: 1px solid var(--border) !important;
        border-radius: 10px !important;
    }

    div[role="option"] {
        background-color: var(--bg-card) !important;
        color: #ffffff !important;
    }

    div[role="option"]:hover {
        background-color: var(--bg-soft) !important;
        color: #ffffff !important;
    }

    div[role="option"] * {
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
    }

    /* File uploader */
    [data-testid="stFileUploader"] section,
    [data-testid="stFileUploaderDropzone"] {
        background-color: var(--bg-soft) !important;
        border: 1px dashed var(--border) !important;
        border-radius: 14px !important;
    }

    [data-testid="stFileUploader"] section *,
    [data-testid="stFileUploaderDropzone"] * {
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
    }

    [data-testid="stFileUploaderFile"] {
        background-color: var(--bg-card-2) !important;
        border: 1px solid var(--border) !important;
        border-radius: 10px !important;
    }

    [data-testid="stFileUploaderFile"] * {
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
    }

    /* Text area readability fix */
    .stTextArea textarea,
    .stTextArea textarea:disabled,
    .stTextArea textarea[disabled],
    div[data-baseweb="textarea"] textarea,
    div[data-baseweb="textarea"] textarea:disabled,
    div[data-baseweb="textarea"] * {
        background-color: #0b192e !important;
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
        opacity: 1 !important;
        border: 1px solid #294a7a !important;
    }

    .stTextArea textarea::placeholder {
        color: #cbd5e1 !important;
    }


    /* Expander */
    [data-testid="stExpander"],
    [data-testid="stExpander"] > div,
    [data-testid="stExpanderDetails"] {
        background-color: var(--bg-card) !important;
        border: 1px solid var(--border) !important;
        border-radius: 12px !important;
        color: #ffffff !important;
    }

    [data-testid="stExpander"] summary * {
        color: #ffffff !important;
    }

    /* Metric */
    [data-testid="stMetric"] {
        background-color: var(--bg-card) !important;
        border: 1px solid var(--border) !important;
        border-radius: 14px !important;
        padding: 16px !important;
    }

    [data-testid="stMetric"] * {
        color: #ffffff !important;
    }

    /* Dataframe / code blocks */
    .stDataFrame, .stCodeBlock, pre, code {
        background-color: #06152d !important;
        color: #ffffff !important;
        border-radius: 10px !important;
    }

    /* JSON display - Dark Theme & Contrast Fix */
    [data-testid="stJson"],
    [data-testid="stJson"] pre,
    [data-testid="stJson"] div,
    .react-json-view {
        background-color: #06152d !important;
        border-radius: 10px !important;
        color: #e2e8f0 !important;
    }

    [data-testid="stJson"] * {
        background-color: transparent !important;
        color: #38bdf8 !important;
        -webkit-text-fill-color: #38bdf8 !important;
    }


    /* Buttons */
    .stButton button {
        background: linear-gradient(135deg, var(--accent-1) 0%, var(--accent-2) 100%) !important;
        color: #06152d !important;
        border: none !important;
        font-weight: 700 !important;
        border-radius: 12px !important;
        padding: 12px 24px !important;
        font-size: 1rem !important;
        box-shadow: 0 4px 14px rgba(56, 189, 248, 0.25) !important;
    }

    .stButton button:hover {
        color: #06152d !important;
        filter: brightness(1.04);
    }

    /* Alerts */
    [data-testid="stAlert"] {
        background-color: var(--bg-card) !important;
        border-radius: 12px !important;
    }

    [data-testid="stAlert"] * {
        color: #ffffff !important;
    }

    /* Tabs if any */
    button[role="tab"] {
        background-color: var(--bg-card) !important;
        color: #ffffff !important;
        border-radius: 10px !important;
    }

    /* Horizontal rule / separators */
    hr {
        border-color: var(--border) !important;
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

    categories_list = []
    max_pages_val = 5
    max_depth_val = 1
    regex_patterns_param = None
    css_schema_param = None
    xpath_schema_param = None

    if selected_method in ["deep", "dynamic"]:
        categories_input = st.text_input(
            "Categories / Keywords Filter (comma-separated)",
            placeholder="e.g. python, tutorial, AI",
            key="categories_input",
            help="Best-First crawling strategy prioritizes pages related to these categories.",
        )
        if categories_input.strip():
            categories_list = [c.strip() for c in categories_input.split(",") if c.strip()]

        col_p, col_d = st.columns(2)
        with col_p:
            max_pages_val = st.number_input(
                "Max Pages",
                min_value=1,
                max_value=10,
                value=5,
                step=1,
                key="max_pages_val",
                help="Recommended 5 for Railway Free Tier limit.",
            )
        with col_d:
            max_depth_val = st.number_input(
                "Max Depth",
                min_value=1,
                max_value=2,
                value=1,
                step=1,
                key="max_depth_val",
                help="Recommended 1 for Railway Free Tier limit.",
            )

    elif selected_method == "regex":
        regex_input_raw = st.text_area(
            "Custom Regex Patterns (Optional)",
            placeholder='emails: [A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}\nurls: https?://\\S+',
            key="regex_input_raw",
            help="Provide custom regex patterns (JSON string or line-by-line key:pattern). Leave blank for default patterns.",
        )
        if regex_input_raw.strip():
            regex_patterns_param = regex_input_raw.strip()

    elif selected_method == "css":
        css_input_raw = st.text_area(
            "Custom CSS Extraction Schema (Optional JSON)",
            placeholder='{\n  "name": "Custom",\n  "baseSelector": "body",\n  "fields": [\n    {"name": "title", "selector": "h1", "type": "text"}\n  ]\n}',
            key="css_input_raw",
            help="Provide a JSON CSS extraction schema. Leave blank for default schema.",
        )
        if css_input_raw.strip():
            try:
                css_schema_param = json.loads(css_input_raw.strip())
            except Exception:
                st.warning("Invalid JSON format for CSS schema; using default schema.")

    elif selected_method == "xpath":
        xpath_input_raw = st.text_area(
            "Custom XPath Extraction Schema (Optional JSON)",
            placeholder='{\n  "name": "Custom",\n  "baseSelector": "//body",\n  "fields": [\n    {"name": "title", "selector": "//h1", "type": "text"}\n  ]\n}',
            key="xpath_input_raw",
            help="Provide a JSON XPath extraction schema. Leave blank for default schema.",
        )
        if xpath_input_raw.strip():
            try:
                xpath_schema_param = json.loads(xpath_input_raw.strip())
            except Exception:
                st.warning("Invalid JSON format for XPath schema; using default schema.")

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
                        "categories": categories_list,
                        "max_pages": int(max_pages_val),
                        "max_depth": int(max_depth_val),
                        "regex_patterns": regex_patterns_param,
                        "css_schema": css_schema_param,
                        "xpath_schema": xpath_schema_param,
                    }
                    with st.spinner("Crawling content and analyzing context..."):
                        response = requests.post(
                            API_URL,
                            json=payload,
                            timeout=300,
                        )



                if response.status_code != 200:
                    st.error(f"Backend API returned error code {response.status_code}")
                    if response.status_code == 502:
                        st.warning("HTTP 502 Bad Gateway: The Railway backend service restarted or ran out of RAM (512MB limit) during this heavy crawl. Retrying with 'single' method or lower max pages will resolve this.")
                    elif response.status_code == 504:
                        st.warning("HTTP 504 Gateway Timeout: The request took longer than Railway's proxy limit. Try reducing Max Pages.")
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
