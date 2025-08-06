import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus, urlparse
import re
import validators
import io
import tldextract
from dateutil.parser import parse as date_parse
import logging

# Configure logger
logger = logging.getLogger("eds_scraper")
logger.setLevel(logging.INFO)
if not logger.hasHandlers():
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

# --- Helper functions ---

def is_valid_business_domain(url):
    """
    Check if domain is a common business TLD (not personal/social media, etc.)
    """
    valid_tlds = {'com', 'org', 'net', 'biz', 'co', 'io', 'us', 'info', 'health', 'law', 'edu', 'gov', 'ca', 'uk', 'de', 'au'}
    ext = tldextract.extract(url)
    domain_tld = ext.suffix.lower()
    if domain_tld in valid_tlds:
        return True
    return False

def clean_text(text):
    return re.sub(r'\s+', ' ', text).strip()

def scrape_bing(query, max_results, industry_keywords):
    """
    Scrapes Bing search results with:
    - deduplication
    - filtering on bad keywords
    - industry keyword presence in title/snippet
    Returns list of dicts with basic info.
    """
    headers = {"User-Agent": "Mozilla/5.0"}
    query_encoded = quote_plus(query)
    results = []
    seen_urls = set()
    page = 0

    bad_words = [
        "sex offender", "arrest", "inmate", "wikipedia", "facebook.com",
        "youtube.com", "twitter.com", "instagram.com", "linkedin.com",
        "craigslist", "reddit", "pinterest", "tumblr", "myspace",
        "porn", "escort", "gambling", "casino", "shopify", "amazon.com"
    ]

    while len(results) < max_results:
        url = f"https://www.bing.com/search?q={query_encoded}&first={page * 10 + 1}"
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
        except Exception as e:
            logger.warning(f"Bing request failed on page {page + 1}: {e}")
            break

        soup = BeautifulSoup(resp.text, "html.parser")
        links = soup.find_all("li", class_="b_algo")
        if not links:
            break

        for link in links:
            if len(results) >= max_results:
                break

            title_tag = link.find("h2")
            url_tag = link.find("a")
            snippet_tag = link.find("p")

            if not (title_tag and url_tag):
                continue

            name = clean_text(title_tag.get_text())
            website = url_tag.get("href", "").strip()
            description = clean_text(snippet_tag.get_text()) if snippet_tag else ""

            # Deduplicate by URL & Name
            if website in seen_urls or any(res['Business Name'].lower() == name.lower() for res in results):
                continue

            # Filter bad keywords
            if any(bad_word in name.lower() for bad_word in bad_words):
                continue

            # Must include at least one industry keyword in name or description
            if not any(keyword.lower() in (name + " " + description).lower() for keyword in industry_keywords):
                continue

            # Filter domain TLD whitelist
            if not is_valid_business_domain(website):
                continue

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
            seen_urls.add(website)

        page += 1
        if page > 50:
            logger.info("Reached page limit 50 for Bing scraping.")
            break

    return results

def extract_contact_info(website_url, fields):
    """
    Visit website and scrape for contact info.
    Tries to extract phone, email, address, social links if requested.
    """
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
        page = requests.get(website_url, timeout=8)
        page.raise_for_status()
        soup = BeautifulSoup(page.text, "html.parser")
        text = soup.get_text(separator=' ')
        html = page.text

        if "Phone" in fields:
            phone_match = re.search(r'\(?\b\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b', text)
            phone = phone_match.group(0) if phone_match else ""

        if "Email" in fields:
            email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
            email = email_match.group(0) if email_match else ""

        if "Address" in fields:
            addr_match = re.search(
                r'\d{1,5}\s+[\w\s]{1,20}\s+(Street|St|Road|Rd|Avenue|Ave|Boulevard|Blvd|Lane|Ln|Drive|Dr|Court|Ct|Circle|Cir|Way)\b',
                text, re.I)
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

    except Exception as e:
        logger.info(f"Failed to scrape {website_url} for contact info: {e}")

    return phone, email, address, facebook, linkedin, twitter, instagram

def verify_business_data(biz):
    """
    Checks that:
    - Website URL is valid and has valid business TLD
    - At least one contact info field is present (phone, email, or address)
    - Cross-check business name is present in website text (fuzzy contains)
    Returns True if verified else False.
    """
    if not validators.url(biz["Website"]):
        return False
    if not is_valid_business_domain(biz["Website"]):
        return False
    # At least one contact info present
    if not any(biz[field] for field in ["Phone", "Email", "Address"]):
        return False

    # Check business name in website text for added confidence
    try:
        page = requests.get(biz["Website"], timeout=8)
        page.raise_for_status()
        soup = BeautifulSoup(page.text, "html.parser")
        website_text = soup.get_text(separator=' ').lower()
        biz_name = biz["Business Name"].lower()

        # Simple fuzzy check: all words in business name appear in website text
        name_words = [w for w in biz_name.split() if len(w) > 3]
        if not all(word in website_text for word in name_words):
            return False
    except Exception as e:
        logger.info(f"Verification failed for {biz['Website']}: {e}")
        return False

    return True

def highlight_unverified(row):
    return ['background-color: #f8d7da' if not row.Verified else '' for _ in row]

# --- Streamlit UI ---
st.set_page_config(page_title="EDS - Robust Vendor Scraper", layout="wide")
st.title("🔎 Express Database Solutions: Robust Vendor Scraper")

st.markdown("""
Enter an industry or business type below and get back a clean, verified list of potential vendor clients.
Select extra data fields to scrape, and specify how many results you want (max 500).
""")

industry = st.text_input("Industry or Business Type (e.g. orthopedic hospitals, veterinary clinics):")
num_results = st.number_input("Number of companies to return (max 500):", min_value=1, max_value=500, value=25)

additional_fields = st.multiselect(
    "Select additional data fields to scrape:",
    options=["Email", "Phone", "Address", "Facebook", "LinkedIn", "Twitter", "Instagram"],
    default=["Email", "Phone", "Address"]
)

if st.button("Run Scraper"):

    if not industry.strip():
        st.error("Please enter an industry or business type.")
        st.stop()

    with st.spinner("Scraping Bing, extracting and verifying data... This may take a few minutes..."):

        # Prepare keywords for filtering
        industry_keywords = [w.strip().lower() for w in industry.split() if len(w) > 2]

        # Scrape Bing search results with filters + dedupe
        raw_results = scrape_bing(f"{industry} business", num_results*2, industry_keywords)  # Scrape extra for filtering

        businesses = []
        urls_seen = set()

        for biz in raw_results:
            if len(businesses) >= num_results:
                break

            # Avoid duplicates again
            if biz["Website"] in urls_seen:
                continue

            # Extract requested contact info fields
            phone, email, address, facebook, linkedin, twitter, instagram = extract_contact_info(biz["Website"], additional_fields)
            biz.update({
                "Phone": phone,
                "Email": email,
                "Address": address,
                "Facebook": facebook,
                "LinkedIn": linkedin,
                "Twitter": twitter,
                "Instagram": instagram,
            })

            # Verify business info thoroughly
            biz["Verified"] = verify_business_data(biz)

            # Add only verified businesses
            if biz["Verified"]:
                businesses.append(biz)
                urls_seen.add(biz["Website"])

        if not businesses:
            st.warning("No verified businesses found. Try different industry keywords or fewer results.")
            st.stop()

        df = pd.DataFrame(businesses)

        st.subheader(f"Verified Vendor Companies Found: {len(df)}")
        st.dataframe(df.style.apply(highlight_unverified, axis=1), use_container_width=True)

        # Export to Excel with in-memory buffer
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        output.seek(0)

        st.download_button(
            label="Download Results as Excel",
            data=output,
            file_name="eds_verified_companies.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

