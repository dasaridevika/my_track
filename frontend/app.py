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
API_URL = "https://universal-extractor-5.onrender.com/crawl"

# -----------------------------
# UI
# -----------------------------
st.title("🕷️ Crawl4AI Web Scraper")
st.write("Extract structured information from websites using Crawl4AI.")

url = st.text_input("🌐 Enter Website URL")
method = st.selectbox(
    "📌 Select Extraction Method",
    [
        "single",
        "deep",
        "css",
        "xpath",
        "regex",
        "pdf"
    ]
)

# -----------------------------
# Crawl Button
# -----------------------------
if st.button("🚀 Start Crawling", use_container_width=True):
    if url.strip() == "":
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
                st.success("✅ Crawling Completed!")
                res_data = response.json()

                # -----------------------------
                # Deep Crawl Results
                # -----------------------------
                if method == "deep":
                    st.subheader("🌐 Deep Crawl Results")
                    
                    # Target nested payload returned by build_response
                    crawl_payload = res_data.get("data", {}) if isinstance(res_data, dict) else {}
                    pages = crawl_payload.get("pages", [])

                    if pages:
                        st.write(f"**Total Pages Crawled:** {crawl_payload.get('total_pages', len(pages))}")
                        for i, page in enumerate(pages, start=1):
                            st.markdown(f"### 📄 Page {i}")
                            st.write(f"**URL:** {page['url']}")
                            st.write(f"**Success:** {page['success']}")
                            
                            if page.get("metadata"):
                                with st.expander("Metadata"):
                                    st.json(page["metadata"])
                                    
                            if page.get("markdown"):
                                with st.expander("Show Extracted Markdown"):
                                    st.markdown(page["markdown"][:2000])  # Display preview
                            st.divider()
                    else:
                        st.warning("No pages found or crawl failed.")

                # -----------------------------
                # Other Extraction Methods
                # -----------------------------
                else:
                    st.subheader("📄 Extraction Result")
                    st.json(res_data)

            else:
                st.error(f"❌ API Error: {response.status_code}")
                st.text(response.text)

        except requests.exceptions.Timeout:
            st.error("⏳ Request timed out. Render may be waking up or processing took too long. Please try again.")
        except requests.exceptions.ConnectionError:
            st.error("❌ Unable to connect to the backend API. Please check whether the Render service is running.")
        except Exception as e:
            st.error(f"Unexpected Error: {e}")
