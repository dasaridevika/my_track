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
# -----------------------------
# Crawl Button
# -----------------------------
if st.button(" Start Crawling", use_container_width=True):
    if not url.strip():
        st.warning("Please enter a URL.")
    else:
        payload = {
            "url": url,
            "method": method
        }
        try:
            with st.spinner("🕷️ Crawling website... Please wait..."):
                response = requests.post(
                    API_URL,
                    json=payload,
                    timeout=300
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
