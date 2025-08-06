import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus
import re
import validators
import io

st.set_page_config(page_title="EDS Scraper v2", layout="wide")
st.title("📊 Express Database Solutions – Enhanced Vendor Scraper")

st.markdown("""
Use this tool to find potential vendor clients by industry.
You can request additional data fields and specify how many companies to return (max 500).
""")

# --- Input Section ---
industry = st.text_input("Industry (e.g., veterinary clinics, dentist offices, etc.):")
num_results = st.number_input("Number of companies to return (max 500):", min_value=1, max_value=500, value=20)

# Additional data fields user wants scraped
additional_fields = st.multiselect(
    "Additional data fields to scrape:",
    options=["Email", "Phone", "Address", "Facebook", "LinkedIn", "Twitter", "Instagram"],
    default=["Email", "Phone", "Address"]
)

run_button = st.button("Run Scraper")

# --- Helper Functions ---

def scrape_bing(query, max_results):
    headers = {"User-Agent": "Mozilla/5.0"}
    query_encoded = quote_plus(query)
    results = []
    page = 0

    while len(results) < max_results:
        url = f"https://www.bing.com/search?q={query_encoded}&first={page * 10 + 1}"
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            st.warning(f"Failed to fetch results from Bing, status code {resp.status_code}")
            break
        soup = BeautifulSoup(resp.text, "html.parser")

        links = soup.find_all("li", class_="b_algo")
        if not links:
            break  # No more results

        for link in links:
            title_tag = link.find("h2")
            url_tag = link.find("a")
            snippet_tag = link.find("p")
            if title_tag and url_tag:
                name = title_tag.get_text(strip=True)
                website = url_tag.get("href", "")
                description = snippet_tag.get_text(strip=True) if snippet_tag else ""
                # Basic filter: ignore results with suspicious or irrelevant keywords
                if any(bad_word in name.lower() for bad_word in ["sex offender", "arrest", "inmate", "wikipedia", "facebook.com", "youtube.com"]):
                    continue
                if len(results) >= max_results:
                    break
                results.append({
                    "Business Name": name,
                    "Website": website,
                    "Description": description,
                    "Phone": "",
                    "Email": "",
                    "Address": "",
                    "Facebook": "",
                    "LinkedIn": "",
                    "Twitter": "",
                    "Instagram": "",
                    "Verified": False
                })
        page += 1
        if page > 50:  # Safety limit to avoid endless loops
            break
    return results

def extract_contact_info(website_url, fields):
    phone = ""
    email = ""
    address = ""
    facebook = ""
    linkedin = ""
    twitter = ""
    instagram = ""

    if not website_url or not validators.url(website_url):
        return phone, email, address, facebook, linkedin, twitter, instagram

    try:
        page = requests.get(website_url, timeout=5)
        soup = BeautifulSoup(page.text, "html.parser")
        text = soup.get_text(separator=' ')
        html = page.text

        if "Phone" in fields or "phone" in fields:
            phone_match = re.search(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', text)
            phone = phone_match.group(0) if phone_match else ""

        if "Email" in fields or "email" in fields:
            email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
            email = email_match.group(0) if email_match else ""

        if "Address" in fields or "address" in fields:
            addr_match = re.search(r'\d{1,5}\s+\w+\s+(Street|St|Road|Rd|Avenue|Ave|Boulevard|Blvd|Lane|Ln|Drive|Dr)\.?', text, re.I)
            address = addr_match.group(0) if addr_match else ""

        if "Facebook" in fields:
            fb_match = re.search(r'(https?://(www\.)?facebook\.com/[A-Za-z0-9_.-]+)', html)
            facebook = fb_match.group(1) if fb_match else ""
        if "LinkedIn" in fields:
            li_match = re.search(r'(https?://(www\.)?linkedin\.com/in/[A-Za-z0-9_-]+)', html)
            linkedin = li_match.group(1) if li_match else ""
        if "Twitter" in fields:
            tw_match = re.search(r'(https?://(www\.)?twitter\.com/[A-Za-z0-9_]+)', html)
            twitter = tw_match.group(1) if tw_match else ""
        if "Instagram" in fields:
            ig_match = re.search(r'(https?://(www\.)?instagram\.com/[A-Za-z0-9_.]+)', html)
            instagram = ig_match.group(1) if ig_match else ""

    except Exception:
        # Fail quietly and return empty strings
        pass

    return phone, email, address, facebook, linkedin, twitter, instagram

def verify_business(biz):
    url_valid = validators.url(biz["Website"])
    contact_info_found = any(biz[field] for field in ["Phone", "Email", "Address", "Facebook", "LinkedIn", "Twitter", "Instagram"])
    return url_valid and contact_info_found

# --- Run the Scraper ---
if run_button and industry:
    with st.spinner("Scraping Bing and verifying data..."):
        query = f"{industry} business"
        raw_results = scrape_bing(query, num_results)

        for business in raw_results:
            phone, email, address, facebook, linkedin, twitter, instagram = extract_contact_info(business["Website"], additional_fields)
            business["Phone"] = phone
            business["Email"] = email
            business["Address"] = address
            business["Facebook"] = facebook
            business["LinkedIn"] = linkedin
            business["Twitter"] = twitter
            business["Instagram"] = instagram
            business["Verified"] = verify_business(business)

        df = pd.DataFrame(raw_results)

        def highlight_unverified(row):
            return ['background-color: #fff3cd' if not row.Verified else '' for _ in row]

        st.subheader("🔎 Scraped Results")
        st.dataframe(df.style.apply(highlight_unverified, axis=1), use_container_width=True)

        # Export to Excel with in-memory buffer
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        output.seek(0)

        st.download_button(
            label="Download Results as Excel",
            data=output,
            file_name="eds_scraped_data.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )


