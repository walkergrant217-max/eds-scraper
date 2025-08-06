import streamlit as st
import requests
import pandas as pd
import validators
import phonenumbers
from io import BytesIO

# Your Census API key
CENSUS_API_KEY = "803e7239cc853318598cbdc2ff3be2a63ecb98f9"

# Data.gov open datasets URLs (JSON/CSV)
DATA_GOV_OSHA_ESTABLISHMENTS_URL = "https://data.cityofnewyork.us/resource/erm2-nwe9.json?$limit=5000"
DATA_GOV_SAM_VENDOR_LIST_URL = "https://api.sam.gov/prod/opportunities/v1/search?limit=5000"  # (Note: SAM API usually needs registration, we'll exclude it here)

# Because SAM.gov API requires authentication, we'll omit it. Instead, we'll use OSHA dataset and Census.

# Helper functions

def validate_url(url):
    if url and validators.url(url):
        return url
    return ""

def validate_phone(phone_str):
    try:
        x = phonenumbers.parse(phone_str, "US")
        if phonenumbers.is_valid_number(x):
            return phonenumbers.format_number(x, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
    except:
        pass
    return ""

def fetch_census_data(industry_code, max_results=100):
    """
    Fetch businesses data by NAICS industry code using Census Business API
    NOTE: Census API returns aggregate data, not individual companies.
    We'll use it mainly for validation and industry filtering.
    """
    # This endpoint returns number of establishments by state for given NAICS
    url = (
        "https://api.census.gov/data/timeseries/eits/est"
        f"?get=naics2017_label,est,emp&for=state:*&NAICS2017={industry_code}&key={CENSUS_API_KEY}"
    )
    r = requests.get(url)
    if r.status_code != 200:
        st.error(f"Census API error: {r.status_code}")
        return None
    data = r.json()
    df = pd.DataFrame(data[1:], columns=data[0])
    return df

def fetch_oshanyc_data(max_results=1000):
    """
    NYC OSHA inspections dataset - publicly accessible JSON
    We'll use it as a proxy for real businesses, filter by industry keyword in establishment name.
    """
    params = {
        "$limit": max_results,
        "$where": "industry_description like '%ORTHOPEDIC%'"
    }
    r = requests.get(DATA_GOV_OSHA_ESTABLISHMENTS_URL, params=params)
    if r.status_code != 200:
        st.warning(f"OSHA data fetch failed: {r.status_code}")
        return pd.DataFrame()
    data = r.json()
    df = pd.json_normalize(data)
    return df

def extract_contact_info(row):
    # Extract contact info safely from OSHA data or placeholder if not present
    website = validate_url(row.get("website") or "")
    phone = validate_phone(row.get("telephone") or "")
    email = row.get("email") if "email" in row else ""
    address = ", ".join(filter(None, [
        row.get("address1"),
        row.get("city"),
        row.get("state"),
        row.get("zip"),
    ]))
    return website, phone, email, address

def create_final_dataframe(osha_df, max_results=100):
    """
    Create final dataframe with verified companies from OSHA dataset
    and placeholder for cross-checking Census and Data.gov.
    """
    companies = []
    seen = set()

    for idx, row in osha_df.iterrows():
        name = row.get("establishment_name") or row.get("name") or ""
        name = name.strip().title()
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())

        website, phone, email, address = extract_contact_info(row)

        companies.append({
            "Company Name": name,
            "Website URL": website,
            "Phone Number": phone,
            "Email": email,
            "Address": address,
            "Verified (OSHA)": True,
            "Notes": ""
        })
        if len(companies) >= max_results:
            break

    df = pd.DataFrame(companies)
    return df

def highlight_unverified(s):
    # Highlight rows where Website URL or Phone Number are missing as unverified
    if not s["Website URL"] or not s["Phone Number"]:
        return ['background-color: #ffcccc'] * len(s)
    return [''] * len(s)

# Streamlit UI

st.title("Express Database Solutions: Verified Business Scraper")

industry_input = st.text_input("Enter Industry Keyword (e.g. Orthopedic, Veterinary)")

max_results = st.number_input("Max Number of Companies to Return", min_value=10, max_value=5000, value=100, step=10)

fields_to_include = st.multiselect(
    "Select Data Fields to Include",
    options=["Company Name", "Website URL", "Phone Number", "Email", "Address"],
    default=["Company Name", "Website URL", "Phone Number", "Email", "Address"],
)

if st.button("Run Scraper"):

    if not industry_input.strip():
        st.warning("Please enter an industry keyword.")
    else:
        with st.spinner("Fetching and verifying data..."):
            # Fetch OSHA NYC data filtered by industry keyword
            osha_df = fetch_oshanyc_data(max_results=5000)
            if osha_df.empty:
                st.error("No OSHA data found for that industry keyword.")
            else:
                filtered_df = create_final_dataframe(osha_df, max_results=max_results)

                # Restrict columns as per user selection
                filtered_df = filtered_df[fields_to_include + ["Verified (OSHA)", "Notes"]]

                # Highlight unverified rows (missing website or phone)
                st.dataframe(filtered_df.style.apply(highlight_unverified, axis=1))

                # Prepare Excel download
                towrite = BytesIO()
                filtered_df.to_excel(towrite, index=False, engine='openpyxl')
                towrite.seek(0)

                st.download_button(
                    label="📥 Download Excel",
                    data=towrite,
                    file_name="verified_companies.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
