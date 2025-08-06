import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus
import re

st.set_page_config(page_title="EDS Scraper", layout="wide")
st.title("📊 Express Database Solutions – Vendor Scraper")

st.markdown("Use this tool to find potential vendor clients by industry. It will return basic business information and verify available data.")

# --- Input Section ---
industry = st.text_input("Industry (e.g., veterinary clinics, dentist offices, etc.):")
num_results = st.number_input("Number of companies to return:", min_value=1, max_value=100, value=10)

run_button = st.button("Run Scraper")

# --- Scraping Function ---
def scrape_bing(query, num_results):
    headers = {"User-Agent": "Mozilla/5.0"}
    query_encoded = quote_plus(query)
    results = []
    
    for page in range(0, num_results, 10):
        url = f"https://www.bing.com/search?q={query_encoded}&first={page}"
        resp = requests.get(url, headers=headers)
        soup = BeautifulSoup(resp.text, "html.parser")

        links = soup.find_all("li", class_="b_algo")

        for link in links:
            title = link.find("h2")
            url_tag = link.find("a")
            snippet = link.find("p")
            if title and url_tag:
                business = {
                    "Business Name": title.get_text(strip=True),
                    "Website": url_tag["href"],
                    "Description": snippet.get_text(strip=True) if snippet else "",
                    "Phone": "",
                    "Email": "",
                    "Verified": False
                }
                results.append(business)
            if len(results) >= num_results:
                break
        if len(results) >= num_results:
            break
    return results

# --- Helper Functions ---
def extract_contact_info(website_url):
    try:
        page = requests.get(website_url, timeout=5)
        soup = BeautifulSoup(page.text, "html.parser")
        text = soup.get_text()

        email_match = re.search(r'[\w\.-]+@[\w\.-]+', text)
        phone_match = re.search(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', text)

        email = email_match.group(0) if email_match else ""
        phone = phone_match.group(0) if phone_match else ""

        return phone, email
    except:
        return "", ""

# --- Run the Scraper ---
if run_button and industry:
    with st.spinner("Scraping Bing and verifying data..."):
        query = f"{industry} businesses"
        raw_results = scrape_bing(query, num_results)
        
        for business in raw_results:
            phone, email = extract_contact_info(business["Website"])
            business["Phone"] = phone
            business["Email"] = email
            business["Verified"] = bool(phone or email)

        df = pd.DataFrame(raw_results)

        # Highlight unverified rows
        def highlight_unverified(row):
            return ['background-color: #fff3cd' if not row.Verified else '' for _ in row]

        st.subheader("🔎 Scraped Results")
        st.dataframe(df.style.apply(highlight_unverified, axis=1), use_container_width=True)

        # Download
        st.download_button(
            label="Download Results as Excel",
            data=df.to_excel(index=False, engine='openpyxl'),
            file_name="eds_scraped_data.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

