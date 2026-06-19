import os
import json
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "Corpus" / "raw"
PROCESSED_DIR = BASE_DIR / "data" / "Corpus" / "processed"
DB_DIR = BASE_DIR / "data" / "chromadb"

# Ensure directories exist
DB_DIR.mkdir(parents=True, exist_ok=True)

# Legacy alias for backward compatibility
DATA_DIR = RAW_DIR

# Defaults
AMC_NAME = "HDFC Mutual Fund"
EMBEDDING_MODEL_NAME = "BAAI/bge-small-en-v1.5"
GROQ_MODEL = "llama-3.1-8b-instant"

# Supported Schemes and target Groww URLs Defaults
SCHEME_URLS = {
    "HDFC Mid-Cap Opportunities Fund": "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth",
    "HDFC Small Cap Fund": "https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth",
    "HDFC Gold ETF Fund of Fund": "https://groww.in/mutual-funds/hdfc-gold-etf-fund-of-fund-direct-plan-growth",
    "HDFC Multi Cap Fund": "https://groww.in/mutual-funds/hdfc-multi-cap-fund-direct-growth",
    "HDFC Large Cap Fund": "https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth"
}

SCHEME_CATEGORIES = {
    "HDFC Mid-Cap Opportunities Fund": "Mid Cap",
    "HDFC Small Cap Fund": "Small Cap",
    "HDFC Gold ETF Fund of Fund": "Gold / Commodity",
    "HDFC Multi Cap Fund": "Multi Cap",
    "HDFC Large Cap Fund": "Large Cap"
}

SCHEMES_LIST = []
OFFICIAL_SCHEME_LINKS = {}
OFFICIAL_GUIDANCE_LINKS = {}

# Attempt dynamic JSON loading for ease of expansion
SCHEMES_JSON_PATH = BASE_DIR / "config" / "schemes.json"
if SCHEMES_JSON_PATH.exists():
    try:
        with open(SCHEMES_JSON_PATH, "r", encoding="utf-8") as f:
            config_data = json.load(f)
            EMBEDDING_MODEL_NAME = config_data.get("embedding_model", EMBEDDING_MODEL_NAME)
            GROQ_MODEL = config_data.get("groq_model", GROQ_MODEL)
            
            # Load guidance links dynamically
            OFFICIAL_GUIDANCE_LINKS = config_data.get("official_guidance_links", {})
            
            amcs_list = config_data.get("amcs", [])
            if amcs_list:
                temp_urls = {}
                for amc in amcs_list:
                    amc_name = amc.get("amc_name", "Unknown AMC")
                    for scheme in amc.get("schemes", []):
                        s_name = scheme.get("name")
                        s_url = scheme.get("url")
                        s_category = scheme.get("category", "N/A")
                        
                        SCHEMES_LIST.append({
                            "name": s_name,
                            "amc_name": amc_name,
                            "url": s_url,
                            "category": s_category
                        })
                        if s_name and s_url:
                            temp_urls[s_name] = s_url
                            
                        # Load scheme-specific links dynamically
                        if s_name and "official_links" in scheme:
                            OFFICIAL_SCHEME_LINKS[s_name] = scheme["official_links"]
                if SCHEMES_LIST:
                    SCHEME_URLS = temp_urls
            else:
                # Fallback parser for old schemes array format
                json_schemes = config_data.get("schemes", [])
                if json_schemes:
                    temp_urls = {}
                    for s in json_schemes:
                        s_name = s.get("name")
                        s_url = s.get("url")
                        s_category = s.get("category", "N/A")
                        SCHEMES_LIST.append({
                            "name": s_name,
                            "amc_name": AMC_NAME,
                            "url": s_url,
                            "category": s_category
                        })
                        if s_name and s_url:
                            temp_urls[s_name] = s_url
                            
                        # Load scheme-specific links dynamically
                        if s_name and "official_links" in s:
                            OFFICIAL_SCHEME_LINKS[s_name] = s["official_links"]
                    SCHEME_URLS = temp_urls
    except Exception as e:
        print(f"Warning: Failed to load {SCHEMES_JSON_PATH} due to: {e}. Using default values.")

# Re-verify and back-populate list if empty
if not SCHEMES_LIST:
    for name, url in SCHEME_URLS.items():
        SCHEMES_LIST.append({
            "name": name,
            "amc_name": AMC_NAME,
            "url": url,
            "category": SCHEME_CATEGORIES.get(name, "N/A")
        })

# Ingestion / Scraping configurations
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# Embedding & Vector DB Configs
CHROMA_COLLECTION_NAME = "mutual_fund_corpus"

# Refusal redirect portals
AMFI_EDUCATIONAL_URL = "https://www.amfiindia.com/investor-corner"
SEBI_EDUCATIONAL_URL = "https://www.sebi.gov.in/"
HDFC_AMC_PORTAL = "https://www.hdfcfund.com"

# Standard Compliance / Refusal Responses
REFUSAL_MESSAGES = {
    "advisory": (
        "I can only provide factual, objective details about mutual fund schemes. "
        "I cannot provide investment advice or recommendations. "
        f"For official education resources, please visit AMFI: {AMFI_EDUCATIONAL_URL}"
    ),
    "pii": (
        "For your security and privacy, please do not share personal information "
        "like Aadhaar numbers, PAN cards, OTPs, or bank account numbers. "
        "Please check your account portal directly on the official AMC website."
    ),
    "out_of_context": (
        "I do not have access to official documents containing that information. "
        f"You can verify official guidelines and filings directly on SEBI: {SEBI_EDUCATIONAL_URL}"
    ),
    "error": (
        "Our RAG services are currently busy. Please consult the official AMC website."
    )
}

# URLs are loaded dynamically from config/schemes.json
