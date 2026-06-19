import re
import json
from datetime import datetime
from bs4 import BeautifulSoup

class DocumentParser:
    """Parses raw HTML to extract plain text and dynamic mutual fund metrics (NAV, AUM, etc.)."""
    @staticmethod
    def parse_and_save_json(raw_html_path, processed_json_path, scheme_name, amc_name, url, category):
        """
        Reads raw HTML, extracts plain text using BeautifulSoup, parses specific details
        using regular expressions, and saves as processed JSON.
        """
        print(f"-> Parsing HTML from: {raw_html_path}")
        try:
            with open(raw_html_path, "r", encoding="utf-8") as f:
                html_content = f.read()
        except Exception as e:
            print(f"--> Failed to read raw HTML: {e}")
            html_content = ""

        # Parse text using BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        raw_text = soup.get_text(separator="\n")
        
        # Clean extra whitespace
        raw_text_cleaned = re.sub(r'\n+', '\n', raw_text).strip()
        
        # Extract details using regular expressions
        extracted_details = {}
        
        # 1. NAV (e.g. ₹225.63)
        nav_match = re.search(r"NAV\s*:\s*[^\n]*\n\s*(₹?\s*[0-9.,]+)", raw_text_cleaned, re.IGNORECASE)
        if not nav_match:
            nav_match = re.search(r"NAV\s*(?:as of [^\n]*)?\s*\n\s*(₹?\s*[0-9.,]+)", raw_text_cleaned, re.IGNORECASE)
        extracted_details["nav"] = nav_match.group(1).strip() if nav_match else "N/A"
            
        # 2. Expense Ratio (e.g. 0.76%)
        exp_match = re.search(r"Expense\s+ratio\s*\n\s*([0-9.]+\s*%)", raw_text_cleaned, re.IGNORECASE)
        extracted_details["expense_ratio"] = exp_match.group(1).strip() if exp_match else "N/A"
            
        # 3. Fund size (AUM) (e.g. ₹97,350.48 Cr)
        aum_match = re.search(r"Fund\s+size\s*\(AUM\)\s*\n\s*(₹?\s*[0-9.,]+\s*(?:Cr|Lakh|Crore)?)", raw_text_cleaned, re.IGNORECASE)
        if not aum_match:
            aum_match = re.search(r"Asset Under Management\(AUM\) of\s*(₹?\s*[0-9.,]+\s*(?:Cr|Lakh|Crore)?)", raw_text_cleaned, re.IGNORECASE)
        extracted_details["fund_size_aum"] = aum_match.group(1).strip() if aum_match else "N/A"
            
        # 4. Minimum SIP (e.g. ₹100)
        sip_match = re.search(r"Min\.\s+for\s+SIP\s*\n\s*(₹?\s*[0-9.,]+)", raw_text_cleaned, re.IGNORECASE)
        if not sip_match:
            sip_match = re.search(r"Minimum\s+SIP\s+Investment\s+is\s+set\s+to\s*(₹?\s*[0-9.,]+)", raw_text_cleaned, re.IGNORECASE)
        extracted_details["minimum_sip"] = sip_match.group(1).strip() if sip_match else "N/A"

        # 5. Exit Load
        exit_match = re.search(r"Exit\s+Load\s*\n\s*(?:[0-9]{2}\s+[A-Za-z]{3}\s+[0-9]{4}\s*\n)?\s*(Exit\s+load\s+of\s+[^\n]+)", raw_text_cleaned, re.IGNORECASE)
        if not exit_match:
            exit_match = re.search(r"Exit\s+load\s*\n\s*(Exit\s+load\s+[^\n]+)", raw_text_cleaned, re.IGNORECASE)
        extracted_details["exit_load"] = exit_match.group(1).strip() if exit_match else "N/A"

        # 6. Fund Managers (Fund management)
        managers = []
        fm_match = re.search(r"Fund\s+management\s*\n(.*?)(\n\s*About|\n\s*Investment Objective|$)", raw_text_cleaned, re.DOTALL | re.IGNORECASE)
        if fm_match:
            fm_section = fm_match.group(1)
            name_matches = re.findall(r"\b([A-Z]{2})\b\s*([A-Z][a-z]+(?:[ \t]+[A-Z][a-z]+)+)", fm_section)
            managers = [match[1] for match in name_matches]
            seen = set()
            managers = [x for x in managers if not (x in seen or seen.add(x))]
            
        extracted_details["fund_managers"] = managers

        # 7. Benchmark Index
        bench_match = re.search(r"Fund\s+benchmark\s*\n\s*([^\n]+)", raw_text_cleaned, re.IGNORECASE)
        extracted_details["benchmark"] = bench_match.group(1).strip() if bench_match else "N/A"

        # 8. Riskometer Rating
        risk_match = re.search(r"\b(Very\s+High\s+Risk|High\s+Risk|Moderately\s+High\s+Risk|Moderate\s+Risk|Low\s+to\s+Moderate\s+Risk|Low\s+Risk)\b", raw_text_cleaned, re.IGNORECASE)
        extracted_details["riskometer"] = risk_match.group(1).strip() if risk_match else "N/A"

        # 9. About Fund / Investment Objective
        obj_match = re.search(r"Investment\s+Objective\s*\n\s*([^\n]+)", raw_text_cleaned, re.IGNORECASE)
        extracted_details["about"] = obj_match.group(1).strip() if obj_match else "N/A"

        # Try to find the exact scheme name from the H1 tag
        h1_tag = soup.find('h1')
        display_scheme_name = h1_tag.get_text().strip() if h1_tag else scheme_name

        # Build final processed JSON payload
        processed_doc = {
            "scheme_name": display_scheme_name,
            "amc_name": amc_name,
            "source_url": url,
            "category": category,
            "scraped_at": datetime.now().isoformat(),
            "raw_text_content": raw_text_cleaned,
            "structured_fields": extracted_details
        }

        # Write to JSON file
        try:
            with open(processed_json_path, "w", encoding="utf-8") as f:
                json.dump(processed_doc, f, indent=2, ensure_ascii=False)
            print(f"--> Successfully saved parsed details to: {processed_json_path}")
            return True
        except Exception as e:
            print(f"--> Failed to save processed JSON: {e}")
            return False
