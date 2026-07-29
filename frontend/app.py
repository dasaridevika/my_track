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

# -----------------------------
# Premium Styling Injection
# -----------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }
    
    .main-title {
        font-size: 2.8rem;
        font-weight: 800;
        background: linear-gradient(135deg, #00f2fe 0%, #4facfe 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
        letter-spacing: -0.5px;
    }
    
    .subtitle {
        font-size: 1.1rem;
        color: rgba(255, 255, 255, 0.7);
        margin-bottom: 2rem;
    }
    
    .card {
        background: rgba(255, 255, 255, 0.03);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 18px;
        padding: 24px;
        margin-bottom: 24px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
        transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1), border-color 0.3s ease;
    }
    
    .card:hover {
        transform: translateY(-2px);
        border-color: rgba(0, 242, 254, 0.25);
    }
    
    .summary-card {
        background: linear-gradient(135deg, rgba(79, 172, 254, 0.08) 0%, rgba(0, 242, 254, 0.03) 100%);
        border-left: 5px solid #00f2fe;
    }
    
    .badge {
        display: inline-block;
        padding: 6px 14px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
        margin-right: 8px;
        margin-bottom: 8px;
        background: rgba(0, 242, 254, 0.12);
        color: #00f2fe;
        border: 1px solid rgba(0, 242, 254, 0.25);
        transition: all 0.2s ease;
    }
    .badge:hover {
        background: rgba(0, 242, 254, 0.25);
        transform: scale(1.05);
    }
    
    .keyword-badge {
        background: rgba(249, 168, 37, 0.12);
        color: #ffb300;
        border: 1px solid rgba(249, 168, 37, 0.25);
    }
    .keyword-badge:hover {
        background: rgba(249, 168, 37, 0.25);
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
        background: rgba(76, 175, 80, 0.15);
        color: #4caf50;
        border: 1px solid rgba(76, 175, 80, 0.3);
    }
    .sentiment-negative {
        background: rgba(244, 67, 54, 0.15);
        color: #f44336;
        border: 1px solid rgba(244, 67, 54, 0.3);
    }
    .sentiment-neutral {
        background: rgba(158, 158, 158, 0.15);
        color: #e0e0e0;
        border: 1px solid rgba(158, 158, 158, 0.3);
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
    }
    
    .bullet-item::before {
        content: "✦";
        position: absolute;
        left: 4px;
        top: 0;
        color: #00f2fe;
        font-size: 1.1rem;
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------
# Header Layout
# -----------------------------
st.markdown('<div class="main-title">🕷️ Crawl4AI AI-Scraper</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Extract and auto-summarize web content with zero-boilerplate context cleaning</div>', unsafe_allow_html=True)

# -----------------------------
# Input Sidebar
# -----------------------------
col1, col2 = st.columns([1, 2], gap="large")

with col1:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("🎯 Extraction Target")
    url = st.text_input("Website URL", placeholder="https://example.com")
    method = st.selectbox(
        "Extraction Method",
        ["single", "deep", "dynamic", "snapshot", "css", "xpath", "regex", "pdf"]
    )
    
    st.markdown("<br>", unsafe_allow_html=True)
    start_btn = st.button("Start Extraction", use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

with col2:
    if start_btn:
        if not url.strip():
            st.warning("Please enter a valid website URL.")
        else:
            payload = {
                "url": url,
                "method": method
            }
            try:
                with st.spinner("🕷️ Crawling web pages and analyzing context... Please wait..."):
                    response = requests.post(
                        API_URL,
                        json=payload,
                        timeout=300
                    )
                
                if response.status_code == 200:
                    res_data = response.json()
                    data = res_data.get("data", res_data)
                    llm_analysis = data.get("llm_analysis")
                    
                    st.toast("Extraction completed successfully!", icon="✅")
                    
                    # Display Results
                    if method == "snapshot":
                        # Snapshot method: Show download options & files
                        st.markdown('<div class="card">', unsafe_allow_html=True)
                        st.subheader("📸 Page Snapshot Result")
                        extracted = data.get("extracted_data", data)
                        files = extracted.get("files", {})
                        
                        st.write(f"**URL:** {extracted.get('url')}")
                        st.write(f"**Status:** {'Success' if extracted.get('success') else 'Failed'}")
                        
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
                        
                    elif llm_analysis:
                        # Display clean premium AI Summary dashboard
                        st.markdown('<div class="card summary-card">', unsafe_allow_html=True)
                        st.subheader("📝 Executive Summary")
                        summary = llm_analysis.get("summary", "")
                        if summary:
                            st.write(summary)
                        else:
                            st.info("No executive summary found in response.")
                        st.markdown('</div>', unsafe_allow_html=True)
                        
                        # Columns for Sentiment, Topics, Keywords
                        col_info1, col_info2 = st.columns(2)
                        
                        with col_info1:
                            st.markdown('<div class="card">', unsafe_allow_html=True)
                            st.subheader("📊 Sentiment Analysis")
                            sentiment = llm_analysis.get("sentiment", "neutral").lower()
                            
                            emoji = "😐"
                            class_name = "sentiment-neutral"
                            if "positive" in sentiment or "good" in sentiment:
                                emoji = "😊"
                                class_name = "sentiment-positive"
                            elif "negative" in sentiment or "bad" in sentiment:
                                emoji = "😡"
                                class_name = "sentiment-negative"
                                
                            st.markdown(f'<span class="sentiment-tag {class_name}">{emoji} {sentiment}</span>', unsafe_allow_html=True)
                            st.markdown('</div>', unsafe_allow_html=True)
                            
                            st.markdown('<div class="card">', unsafe_allow_html=True)
                            st.subheader("🏷️ Topics")
                            topics = llm_analysis.get("topics", [])
                            if isinstance(topics, list) and topics:
                                topic_badges = "".join([f'<span class="badge">{topic}</span>' for topic in topics])
                                st.markdown(topic_badges, unsafe_allow_html=True)
                            else:
                                st.info("No topics classified.")
                            st.markdown('</div>', unsafe_allow_html=True)
                            
                        with col_info2:
                            st.markdown('<div class="card">', unsafe_allow_html=True)
                            st.subheader("🔑 Keywords")
                            keywords = llm_analysis.get("keywords", [])
                            if isinstance(keywords, list) and keywords:
                                keyword_badges = "".join([f'<span class="badge keyword-badge">{keyword}</span>' for keyword in keywords])
                                st.markdown(keyword_badges, unsafe_allow_html=True)
                            else:
                                st.info("No keywords extracted.")
                            st.markdown('</div>', unsafe_allow_html=True)
                            
                        # Important points & Action items
                        st.markdown('<div class="card">', unsafe_allow_html=True)
                        st.subheader("📌 Important Takeaways")
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
                            st.subheader("✅ Recommended Actions")
                            for idx, item in enumerate(action_items):
                                st.checkbox(item, key=f"action_{idx}")
                            st.markdown('</div>', unsafe_allow_html=True)
                            
                    else:
                        # Fallback when LLM analysis was skipped or not returned
                        st.markdown('<div class="card">', unsafe_allow_html=True)
                        st.warning("No AI summary analysis was generated for this method or site.")
                        st.subheader("Raw Extracted Data Preview")
                        st.json(data.get("extracted_data", data))
                        st.markdown('</div>', unsafe_allow_html=True)
                        
                    # Collapsible debug section
                    with st.expander("🔧 Debug: Raw Crawl Metadata"):
                        st.json(data)
                        
                else:
                    st.error(f"Backend API returned error code {response.status_code}")
                    try:
                        st.json(response.json())
                    except Exception:
                        st.text(response.text)
                        
            except requests.exceptions.Timeout:
                st.error("⏳ Connection timed out. The backend is taking too long to respond.")
            except requests.exceptions.ConnectionError:
                st.error("🔌 Unable to connect to the backend server. Please verify it is running on port 8000.")
            except Exception as e:
                st.error(f"Unexpected error occurred: {e}")
    else:
        # Default placeholder panel
        st.markdown("""
        <div class="card" style="text-align: center; padding: 60px 40px; border-style: dashed; border-width: 2px;">
            <div style="font-size: 4rem; margin-bottom: 20px;">🕷️</div>
            <h2>Ready to extract content</h2>
            <p style="color: rgba(255, 255, 255, 0.5);">Enter a URL and select an extraction method on the left to begin.</p>
        </div>
        """, unsafe_allow_html=True)
