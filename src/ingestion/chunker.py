import os
import json
import hashlib
from pathlib import Path
from datetime import datetime
from transformers import AutoTokenizer

from src.config import OFFICIAL_SCHEME_LINKS, OFFICIAL_GUIDANCE_LINKS

class DocumentChunker:
    """Reads processed JSON files and segments their content into logical chunks for vector database indexing."""
    try:
        tokenizer = AutoTokenizer.from_pretrained("BAAI/bge-small-en-v1.5")
    except Exception:
        tokenizer = None

    @staticmethod
    def count_tokens(text):
        if DocumentChunker.tokenizer is not None:
            return len(DocumentChunker.tokenizer.encode(text, add_special_tokens=False))
        return len(text.split())
    @staticmethod
    def slugify(text):
        import re
        return re.sub(r'[^a-z0-9]+', '_', text.lower()).strip('_')

    @staticmethod
    def compile_chunks_from_json(processed_dir):
        """
        Reads processed JSON files from processed_dir (recursively), builds preambles,
        splits text into paragraph chunks, and returns chunks, metadatas, and ids.
        """
        chunks = []
        chunk_metadatas = []
        chunk_ids = []
        
        # Section titles detection triggers
        known_sections = [
            ("holdings", "Holdings"),
            ("minimum investments", "Minimum Investments"),
            ("returns and rankings", "Returns and Rankings"),
            ("exit load, stamp duty and tax", "Exit Load, Stamp Duty and Tax"),
            ("fund management", "Fund Management"),
            ("about", "About Fund"),
            ("return calculator", "Return Calculator"),
            ("compare similar funds", "Compare Similar Funds")
        ]
        
        print(f"-> Chunker scanning folder: {processed_dir}")
        for root, dirs, files in os.walk(processed_dir):
            for file in files:
                if file.endswith(".json"):
                    json_path = Path(root) / file
                    try:
                        with open(json_path, "r", encoding="utf-8") as f:
                            doc = json.load(f)
                            
                            scheme_name = doc["scheme_name"]
                            amc_name = doc["amc_name"]
                            url = doc["source_url"]
                            category = doc["category"]
                            scraped_text = doc["raw_text_content"]
                            fields = doc.get("structured_fields", {})
                            
                            scheme_slug = url.split('/')[-1] if url else DocumentChunker.slugify(scheme_name)
                            category_slug = category.lower().replace(" / ", "-").replace("/", "-").replace(" ", "-") if category else "n/a"
                            last_updated_str = datetime.today().strftime('%Y-%m-%d')
                            
                            # Find matched official links robustly
                            scheme_links = {}
                            scheme_slug_norm = DocumentChunker.slugify(scheme_name)
                            for k, v in OFFICIAL_SCHEME_LINKS.items():
                                k_norm = DocumentChunker.slugify(k).replace("_opportunities", "")
                                if k_norm in scheme_slug_norm:
                                    scheme_links = v
                                    break
                                    
                            sid_url = scheme_links.get("sid", "N/A")
                            kim_url = scheme_links.get("kim", "N/A")
                            factsheet_url = scheme_links.get("factsheet", "N/A")

                            # Build a highly factual preamble from structured JSON fields
                            managers_str = ", ".join(fields.get("fund_managers", [])) if fields.get("fund_managers") else "N/A"
                            preamble = (
                                f"Scheme: {scheme_name} | Section: Factsheet Details\n"
                                f"Scheme Context: {scheme_name}\n"
                                f"Asset Management Company (AMC): {amc_name}\n"
                                f"Fund Category: {category}\n"
                                f"Latest NAV: {fields.get('nav', 'N/A')}\n"
                                f"Expense Ratio: {fields.get('expense_ratio', 'N/A')}\n"
                                f"Exit Load Details: {fields.get('exit_load', 'N/A')}\n"
                                f"Fund Size (AUM): {fields.get('fund_size_aum', 'N/A')}\n"
                                f"Minimum SIP: {fields.get('minimum_sip', 'N/A')}\n"
                                f"Benchmark Index: {fields.get('benchmark', 'N/A')}\n"
                                f"Riskometer Rating: {fields.get('riskometer', 'N/A')}\n"
                                f"Fund Managers: {managers_str}\n"
                                f"About Fund: {fields.get('about', 'N/A')}\n"
                                f"Official Scheme Information Document (SID) Link: {sid_url}\n"
                                f"Official Key Information Memorandum (KIM) Link: {kim_url}\n"
                                f"Official Factsheet Link: {factsheet_url}\n"
                            )
                            
                            # Add the pure structured fields context block as the first chunk
                            chunks.append(preamble)
                            
                            preamble_hash = f"sha256:{hashlib.sha256(preamble.encode('utf-8')).hexdigest()}"
                            chunk_metadatas.append({
                                "source_url": url,
                                "source_type": "scheme_page",
                                "doc_type": "factsheet",
                                "amc": amc_name,
                                "amc_name": amc_name,
                                "scheme_name": scheme_name,
                                "scheme_category": category_slug,
                                "section_title": "Factsheet Details",
                                "page_number": 1,
                                "last_updated": last_updated_str,
                                "last_updated_date": last_updated_str,
                                "content_hash": preamble_hash
                            })
                            chunk_ids.append(f"{scheme_slug}:chunk-0")
                            
                            # Parse raw text and associate each line with a section
                            raw_lines = [p.strip() for p in scraped_text.split("\n") if p.strip()]
                            line_data = []
                            active_section = "General Info"
                            for line in raw_lines:
                                line_lower = line.lower()
                                for trigger, label in known_sections:
                                    if trigger in line_lower and len(line) < 60:
                                        active_section = label
                                        break
                                line_data.append((line, active_section))
                                
                            # Token-based sliding window chunking (400-600 tokens with 50-80 token overlap)
                            start_idx = 0
                            n_lines = len(line_data)
                            chunk_idx = 1
                            
                            while start_idx < n_lines:
                                # Determine section from the first line in this chunk window
                                chunk_section = line_data[start_idx][1]
                                prefix = f"Scheme: {scheme_name} | Section: {chunk_section}\n"
                                prefix_tokens = DocumentChunker.count_tokens(prefix)
                                
                                current_lines = []
                                current_tokens = prefix_tokens
                                
                                end_idx = start_idx
                                while end_idx < n_lines:
                                    line_text, _ = line_data[end_idx]
                                    # Count tokens of this line plus the newline joining it
                                    line_tok = DocumentChunker.count_tokens("\n" + line_text if current_lines else line_text)
                                    
                                    # Stop if adding this line exceeds 600 tokens (but make sure chunk has at least 1 line)
                                    if current_tokens + line_tok > 600 and len(current_lines) > 0:
                                        break
                                        
                                    current_lines.append(line_text)
                                    current_tokens += line_tok
                                    end_idx += 1
                                    
                                chunk_text = prefix + "\n".join(current_lines)
                                chunks.append(chunk_text)
                                
                                chunk_hash = f"sha256:{hashlib.sha256(chunk_text.encode('utf-8')).hexdigest()}"
                                chunk_metadatas.append({
                                    "source_url": url,
                                    "source_type": "scheme_page",
                                    "doc_type": "webpage",
                                    "amc": amc_name,
                                    "amc_name": amc_name,
                                    "scheme_name": scheme_name,
                                    "scheme_category": category_slug,
                                    "section_title": chunk_section,
                                    "page_number": (chunk_idx // 8) + 1,
                                    "last_updated": last_updated_str,
                                    "last_updated_date": last_updated_str,
                                    "content_hash": chunk_hash
                                })
                                chunk_ids.append(f"{scheme_slug}:chunk-{chunk_idx}")
                                chunk_idx += 1
                                
                                # If we reached the end of all lines, we are done
                                if end_idx >= n_lines:
                                    break
                                    
                                # Calculate overlap: find a starting index for the next window
                                # that gives an overlap of around 65 tokens (between 50 and 80).
                                overlap_tokens = 0
                                next_start_idx = end_idx - 1
                                min_start_idx = start_idx + 1
                                
                                while next_start_idx >= min_start_idx:
                                    line_text, _ = line_data[next_start_idx]
                                    line_tok = DocumentChunker.count_tokens("\n" + line_text if next_start_idx < end_idx - 1 else line_text)
                                    if overlap_tokens + line_tok > 70:
                                        break
                                    overlap_tokens += line_tok
                                    next_start_idx -= 1
                                    
                                next_start_idx = max(min_start_idx, next_start_idx + 1)
                                start_idx = next_start_idx
                    except Exception as ex:
                        print(f"--> Error parsing processed file {json_path}: {ex}")

        # Add General Help & Guidance Resources as global chunks
        general_preamble = (
            "Scheme: General Mutual Fund Guidance | Section: Help and Support\n"
            "Asset Management Company (AMC): HDFC Mutual Fund\n"
            f"Official AMC FAQ/Help Page: {OFFICIAL_GUIDANCE_LINKS['amc_faq']}\n"
            f"Systematic Investment Plan (SIP) FAQs: {OFFICIAL_GUIDANCE_LINKS['sip_faq']}\n"
            f"Redemption & Exit FAQs: {OFFICIAL_GUIDANCE_LINKS['redemption_faq']}\n"
            f"Account Statement Download Guide: {OFFICIAL_GUIDANCE_LINKS['account_statement_guide']}\n"
            f"Capital Gains & Tax Statement Guide: {OFFICIAL_GUIDANCE_LINKS['tax_statement_guide']}\n"
            f"AMFI Investor Corner: {OFFICIAL_GUIDANCE_LINKS['amfi_education']}\n"
            f"SEBI Investor Education Resources: {OFFICIAL_GUIDANCE_LINKS['sebi_education']}\n"
        )
        chunks.append(general_preamble)
        
        general_hash = f"sha256:{hashlib.sha256(general_preamble.encode('utf-8')).hexdigest()}"
        chunk_metadatas.append({
            "source_url": OFFICIAL_GUIDANCE_LINKS['amc_faq'],
            "source_type": "guidance_page",
            "doc_type": "guidance",
            "amc": "HDFC Mutual Fund",
            "amc_name": "HDFC Mutual Fund",
            "scheme_name": "General Mutual Fund Guidance",
            "scheme_category": "general-guidance",
            "section_title": "Help and Support",
            "page_number": 1,
            "last_updated": datetime.today().strftime('%Y-%m-%d'),
            "last_updated_date": datetime.today().strftime('%Y-%m-%d'),
            "content_hash": general_hash
        })
        chunk_ids.append("general_guidance:help_and_support")
                        
        print(f"-> Total chunks generated: {len(chunks)}")
        return chunks, chunk_metadatas, chunk_ids
