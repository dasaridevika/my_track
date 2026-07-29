import os
import streamlit as st
import requests
import json

# -----------------------------
# Page Configuration
# -----------------------------
st.set_page_config(
    page_title="Crawl4AI Web Scraper",
    page_icon="C",
    layout="wide"
)

# -----------------------------
# Backend API URL
# -----------------------------
API_URL = os.getenv(
    "API_URL",
    "http://127.0.0.1:8000/crawl"
)
PDF_UPLOAD_URL = os.getenv(
    "PDF_UPLOAD_URL",
    f"{API_URL.rstrip('/').rsplit('/', 1)[0]}/pdf/upload",
)

# -----------------------------
# Premium Styling Enforced Dark Theme
# -----------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&display=swap');
    
    /* Enforce Dark Theme Background on App Container */
    .stApp {
        background-color: #090d16 !important;
        color: #f1f5f9 !important;
        font-family: 'Outfit', sans-serif !important;
    }
    
    /* Enforce Visibility for Global Text Elements */
    .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6, .stApp p, .stApp li {
        color: #f1f5f9 !important;
        font-family: 'Outfit', sans-serif !important;
    }
    
    /* Input Labels */
    .stApp label {
        color: #94a3b8 !important;
        font-size: 0.95rem !important;
        font-weight: 600 !important;
        margin-bottom: 8px !important;
    }
    
    /* Custom Title Gradient */
    .main-title {
        font-size: 3.2rem;
        font-weight: 800;
        background: linear-gradient(135deg, #00f2fe 0%, #4facfe 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent !important;
        margin-bottom: 0.2rem;
        letter-spacing: -0.8px;
    }
    
    .subtitle {
        font-size: 1.15rem;
        color: #94a3b8 !important;
        margin-bottom: 2rem;
    }
    
    /* Card Container */
    .card {
        background: #111827 !important;
        border: 1px solid #1f2937 !important;
        border-radius: 18px;
        padding: 24px;
        margin-bottom: 24px;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4);
        transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1), border-color 0.3s ease;
    }
    
    .card:hover {
        transform: translateY(-2px);
        border-color: rgba(0, 242, 254, 0.3) !important;
    }
    
    .summary-card {
        background: linear-gradient(135deg, #1e1b4b 0%, #111827 100%) !important;
        border-left: 5px solid #00f2fe !important;
    }
    
    /* Styled Interactive Pills/Badges */
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
        transition: all 0.2s ease;
    }
    .badge:hover {
        background: rgba(0, 242, 254, 0.25) !important;
        transform: scale(1.05);
    }
    
    .keyword-badge {
        background: rgba(249, 168, 37, 0.12) !important;
        color: #ffb300 !important;
        border: 1px solid rgba(249, 168, 37, 0.25) !important;
    }
    .keyword-badge:hover {
        background: rgba(249, 168, 37, 0.25) !important;
    }
    
    /* Sentiment Badges */
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
    
    /* Bullet list overrides */
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
    
    /* Checkbox Labels */
    .stCheckbox label p {
        color: #e2e8f0 !important;
        font-size: 1rem !important;
        font-family: 'Outfit', sans-serif !important;
    }
    
    /* Override native Streamlit Inputs/Selectbox to be light with black text */
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
    
    /* Option dropdown items */
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

    /* Premium Glow Button Override */
    .stButton button {
        background: linear-gradient(135deg, #00f2fe 0%, #4facfe 100%) !important;
        color: #090d16 !important;
        border: none !important;
        font-weight: 700 !important;
        border-radius: 12px !important;
        padding: 12px 24px !important;
        font-size: 1rem !important;
        box-shadow: 0 4px 14px rgba(0, 242, 254, 0.25) !important;
        transition: transform 0.2s ease, box-shadow 0.2s ease !important;
    }
    .stButton button:hover {
        transform: translateY(-1.5px) !important;
        box-shadow: 0 6px 20px rgba(0, 242, 254, 0.45) !important;
        color: #090d16 !important;
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------
# Header Layout
# -----------------------------
st.markdown('<div class="main-title">Crawl4AI Developer Scraper</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Extract and auto-summarize web content with zero-boilerplate context cleaning</div>', unsafe_allow_html=True)

# -----------------------------
# Main Columns
# -----------------------------
col1, col2 = st.columns([1, 2], gap="large")

with col1:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("Extraction Target")
    url = st.text_input("Website URL", placeholder="https://example.com")
    method = st.selectbox(
        "Extraction Method",
        ["single", "deep", "dynamic", "snapshot", "css", "xpath", "regex", "pdf"]
    )

    uploaded_pdf = None
    if method == "pdf":
        st.caption("Use a public PDF URL, or upload the file when its URL is blocked or unsupported.")
        uploaded_pdf = st.file_uploader(
            "Upload PDF",
            type=["pdf"],
            help="Uploaded PDFs are extracted and analyzed with the same LLM workflow.",
        )
    
    st.markdown("<br>", unsafe_allow_html=True)
    start_btn = st.button("Start Extraction", use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

with col2:
    if start_btn:
        if not url.strip() and uploaded_pdf is None:
            st.warning("Enter a URL or upload a PDF file.")
        else:
            try:
                if uploaded_pdf is not None:
                    with st.spinner("Extracting the uploaded PDF and analyzing its contents... Please wait..."):
                        response = requests.post(
                            PDF_UPLOAD_URL,
                            files={
                                "file": (
                                    uploaded_pdf.name,
                                    uploaded_pdf.getvalue(),
                                    "application/pdf",
                                )
                            },
                            timeout=300,
                        )
                else:
                    payload = {
                        "url": url,
                        "method": method
                    }
                    with st.spinner("Crawling web pages and analyzing context... Please wait..."):
                        response = requests.post(
                            API_URL,
                            json=payload,
                            timeout=300
                        )
                
                if response.status_code == 200:
                    res_data = response.json()
                    data = res_data.get("data", res_data)
                    llm_analysis = data.get("llm_analysis")

                    extracted_result = data.get("extracted_data", data)
                    extraction_succeeded = data.get(
                        "success", extracted_result.get("success", True)
                    )
                    if not extraction_succeeded:
                        error = extracted_result.get("error", "The PDF could not be extracted.")
                        st.error(f"Extraction failed: {error}")
                        if method == "pdf" and uploaded_pdf is None:
                            st.info("Try uploading the PDF with the Upload PDF control, then start extraction again.")
                        with st.expander("Debug: Raw Crawl Metadata"):
                            st.json(data)
                        st.stop()

                    st.toast("Extraction completed successfully!")
                    
                    # 1. SPECIAL INTERFACES FOR STRUCTURAL EXTRACTION (css, xpath, regex)
                    if method in ["css", "xpath", "regex"]:
                        extracted_data = data.get("extracted_data", {})
                        extracted_content = extracted_data.get("extracted_content")
                        if not extracted_content:
                            extracted_content = data.get("extracted_content")
                            
                        parsed_content = None
                        if isinstance(extracted_content, str):
                            try:
                                parsed_content = json.loads(extracted_content)
                            except Exception:
                                pass
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
                            
                        st.markdown('</div>', unsafe_allow_html=True)

                    # 2. SPECIAL INTERFACES FOR MULTI-PAGE CRAWLS (dynamic, deep)
                    elif method in ["dynamic", "deep"]:
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
                                    "Status": "Success" if p.get("success") else "Failed"
                                } 
                                for p in pages
                            ]
                            st.dataframe(page_table, use_container_width=True)
                            st.markdown('</div>', unsafe_allow_html=True)

                    # 3. SPECIAL INTERFACE FOR SNAPSHOT
                    elif method == "snapshot":
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
                        
                        st.markdown('</div>', unsafe_allow_html=True)

                    # 4. SPECIAL INTERFACE FOR PDF EXTRACTION
                    elif method == "pdf":
                        extracted = data.get("extracted_data", data)
                        st.markdown('<div class="card">', unsafe_allow_html=True)
                        st.subheader("PDF Extraction Result")
                        st.write(f"Pages extracted: {extracted.get('page_count', 0)}")
                        download = extracted.get("download", {})
                        if download:
                            st.caption(
                                f"Retrieved via: {download.get('download_method', 'unknown')}"
                            )
                        markdown = extracted.get("markdown", "")
                        if markdown:
                            st.text_area(
                                "Extracted PDF text",
                                markdown,
                                height=260,
                                disabled=True,
                            )
                        else:
                            st.warning("No selectable text was found in this PDF.")
                        st.markdown('</div>', unsafe_allow_html=True)

                    # AI SUMMARY DASHBOARD
                    if llm_analysis:
                        st.markdown('<div class="card summary-card">', unsafe_allow_html=True)
                        st.subheader("Executive Summary")
                        summary = llm_analysis.get("summary", "")
                        if summary:
                            st.write(summary)
                        else:
                            st.info("No executive summary found in response.")
                        st.markdown('</div>', unsafe_allow_html=True)
                        
                        col_info1, col_info2 = st.columns(2)
                        
                        with col_info1:
                            st.markdown('<div class="card">', unsafe_allow_html=True)
                            st.subheader("Sentiment Analysis")
                            sentiment = llm_analysis.get("sentiment", "neutral").lower()
                            
                            class_name = "sentiment-neutral"
                            if "positive" in sentiment or "good" in sentiment:
                                class_name = "sentiment-positive"
                            elif "negative" in sentiment or "bad" in sentiment:
                                class_name = "sentiment-negative"
                                
                            st.markdown(f'<span class="sentiment-tag {class_name}">{sentiment}</span>', unsafe_allow_html=True)
                            st.markdown('</div>', unsafe_allow_html=True)
                            
                            st.markdown('<div class="card">', unsafe_allow_html=True)
                            st.subheader("Topics")
                            topics = llm_analysis.get("topics", [])
                            if isinstance(topics, list) and topics:
                                topic_badges = "".join([f'<span class="badge">{topic}</span>' for topic in topics])
                                st.markdown(topic_badges, unsafe_allow_html=True)
                            else:
                                st.info("No topics classified.")
                            st.markdown('</div>', unsafe_allow_html=True)
                            
                        with col_info2:
                            st.markdown('<div class="card">', unsafe_allow_html=True)
                            st.subheader("Keywords")
                            keywords = llm_analysis.get("keywords", [])
                            if isinstance(keywords, list) and keywords:
                                keyword_badges = "".join([f'<span class="badge keyword-badge">{keyword}</span>' for keyword in keywords])
                                st.markdown(keyword_badges, unsafe_allow_html=True)
                            else:
                                st.info("No keywords extracted.")
                            st.markdown('</div>', unsafe_allow_html=True)
                            
                        st.markdown('<div class="card">', unsafe_allow_html=True)
                        st.subheader("Important Takeaways")
                        points = llm_analysis.get("important_points", [])
                        if isinstance(points, list) and points:
                            bullets = "".join([f'<li class="bullet-item">{pt}</li>' for pt in points])
                            st.markdown(f'<ul class="bullet-list">{bullets}</ul>', unsafe_allow_html=True)
                        else:
                            st.info("No key points listed.")
                        st.markdown('</div>', unsafe_allow_html=True)
                        
                        action_items = llm_analysis.get("action_items", [])
                        if isinstance(action_items, list) and action_items:
                            st.markdown('<div class="card">', unsafe_allow_html=True)
                            st.subheader("Recommended Actions")
                            for idx, item in enumerate(action_items):
                                st.checkbox(item, key=f"action_{idx}")
                            st.markdown('</div>', unsafe_allow_html=True)
                            
                    elif method != "snapshot":
                        st.markdown('<div class="card">', unsafe_allow_html=True)
                        st.warning("No AI summary analysis was generated for this method or site.")
                        st.markdown('</div>', unsafe_allow_html=True)
                        
                    # Collapsible debug section
                    with st.expander("Debug: Raw Crawl Metadata"):
                        st.json(data)
                        
                else:
                    st.error(f"Backend API returned error code {response.status_code}")
                    try:
                        st.json(response.json())
                    except Exception:
                        st.text(response.text)
                        
            except requests.exceptions.Timeout:
                st.error("Connection timed out. The backend is taking too long to respond.")
            except requests.exceptions.ConnectionError:
                st.error("Unable to connect to the backend server. Please verify it is running on port 8000.")
            except Exception as e:
                st.error(f"Unexpected error occurred: {e}")
    else:
        # Default placeholder panel
        st.markdown("""
        <div class="card" style="text-align: center; padding: 60px 40px; border-style: dashed; border-width: 2px;">
            <h2>Ready to extract content</h2>
            <p style="color: rgba(255, 255, 255, 0.5);">Enter a URL and select an extraction method on the left to begin.</p>
        </div>
        """, unsafe_allow_html=True)
