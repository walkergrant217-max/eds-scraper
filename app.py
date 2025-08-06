import streamlit as st
import pandas as pd

st.set_page_config(page_title="EDS Scraper", layout="wide")

st.title("Express Database Solutions: Web Scraper (Beta)")

# Form for user input
with st.form("input_form"):
    industry = st.text_input("Enter target industry (e.g., veterinary clinics, dental suppliers):")
    num_results = st.number_input("How many companies would you like returned?", min_value=1, max_value=1000, value=25)
    submitted = st.form_submit_button("Generate Company List")

if submitted:
    st.write(f"Generating {num_results} results for industry: **{industry}**...")
    
    # Placeholder dataframe
    data = {
        "Company Name": [f"Sample Co {i+1}" for i in range(num_results)],
        "URL": ["" for _ in range(num_results)],
        "Phone Number": ["" for _ in range(num_results)],
        "Email": ["" for _ in range(num_results)],
        "Address": ["" for _ in range(num_results)],
        "Verified": ["❌" for _ in range(num_results)],
    }

    df = pd.DataFrame(data)

    # Highlight unverified rows
    def highlight_unverified(row):
        return ['background-color: #ffe6e6' if row["Verified"] == "❌" else '' for _ in row]

    st.dataframe(df.style.apply(highlight_unverified, axis=1), use_container_width=True)

    # Option to download
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button("Download CSV", csv, "scraped_data.csv", "text/csv")
