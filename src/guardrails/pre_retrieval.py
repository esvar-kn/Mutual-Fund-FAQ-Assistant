import re


class PreRetrievalGuard:
    """Handles query validation before database retrieval (PII checks and intent routing)."""

    # Patterns that mark a query as soliciting investment advice.
    #
    # This list errs towards over-blocking on purpose: wrongly refusing a factual
    # question is a mild annoyance, while answering "which fund should I pick"
    # is unlicensed investment advice. Keep that asymmetry in mind when editing.
    ADVISORY_PATTERNS = [
        # --- Direct requests for a decision -------------------------------
        # "should i buy/invest/...", and the bare "should i" catch-all
        r"\bshould\s+(i|we|my|one)\b",
        r"\b(can|could|would)\s+you\s+(recommend|suggest|advise|tell\s+me\s+which)\b",
        r"\bwhat\s+(should|would)\s+(i|we|you)\s+(do|buy|invest|pick|choose)\b",
        r"\bhelp\s+me\s+(choose|pick|select|decide|invest)\b",
        r"\b(recommend|suggest|advise|advice|advisable|recommendation)\b",

        # --- Superlative / ranking requests --------------------------------
        # "best fund", "top scheme", "ideal plan", "best returns"
        r"\b(best|top|ideal|right|safest|worst|highest[- ]returning)\s+"
        r"(fund|funds|scheme|schemes|option|options|choice|investment|"
        r"investments|plan|plans|amc|returns|performer|performing)\b",
        r"\bwhich\s+(is|are|one|fund|funds|scheme|schemes|amc)\b.{0,40}"
        r"\b(better|best|safer|preferred|should|gives?|worth)\b",
        r"\bwhich\s+(is|would\s+be)\s+(better|best|preferred)\b",

        # --- Suitability / judgement framing --------------------------------
        # "is X a good investment", "is it safe to invest", "worth investing"
        r"\b(good|bad|safe|risky|smart|wise|poor|solid)\s+"
        r"(investment|choice|option|idea|bet|pick|buy)\b",
        r"\bis\s+it\s+(good|better|safe|risky|wise|worth)\b",
        r"\bworth\s+(it|investing|buying|considering|the\s+risk)\b",
        r"\bgood\s+(for|to)\s+(me|invest|buy|my)\b",

        # --- Portfolio / allocation guidance --------------------------------
        r"\bwhere\s+(to|should\s+i)\s+invest\b",
        r"\bhow\s+much\s+should\s+i\b",
        r"\b(my|for\s+my)\s+(portfolio|goals?|retirement|risk\s+appetite)\b",
        r"\b(suitable|appropriate|right)\s+for\s+(me|my|us)\b",
    ]


    @staticmethod
    def detect_pii(query: str) -> bool:
        """
        Scans query for personally identifiable information (PII).
        Returns True if PII is detected, else False.
        """
        # 1. Aadhaar Card: 12 digits, with or without spaces.
        # Spaced/hyphenated groups are unambiguous, but a bare 12-digit run also matches
        # figures like a fund size, so that form additionally requires an identity keyword.
        aadhaar_grouped = re.compile(r'\b\d{4}[\s-]\d{4}[\s-]\d{4}\b')
        aadhaar_bare = re.compile(r'\b\d{12}\b')
        aadhaar_keyword = re.compile(r'\b(aadhaar|aadhar|uidai|kyc)\b', re.IGNORECASE)
        aadhaar_hit = bool(
            aadhaar_grouped.search(query)
            or (aadhaar_bare.search(query) and aadhaar_keyword.search(query))
        )
        
        # 2. PAN Card: 5 capital letters, 4 numbers, 1 capital letter
        pan_pattern = re.compile(r'\b[A-Z]{5}\d{4}[A-Z]\b', re.IGNORECASE)
        
        # 3. Email: standard email regex
        email_pattern = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
        
        # 4. Indian Phone Number: 10 digits (typically starting with 6-9)
        phone_pattern = re.compile(r'\b[6-9]\d{9}\b')
        
        # 5. OTP keywords: "otp" or "one time password"
        otp_pattern = re.compile(r'\b(otp|one[- ]time[- ]password)\b', re.IGNORECASE)
        
        if (aadhaar_hit or
            pan_pattern.search(query) or
            email_pattern.search(query) or 
            phone_pattern.search(query) or 
            otp_pattern.search(query)):
            return True
            
        return False

    @staticmethod
    def classify_intent(query: str) -> str:
        """
        Classifies query intent to separate advisory requests from factual lookups.
        Returns 'advisory' or 'factual'.

        Note: comparison/performance queries are deliberately routed to 'factual'.
        They are constrained at generation time instead, where the system prompt
        forbids calculating or comparing returns and redirects to the factsheet.
        """
        query_lower = query.lower()

        for pattern in PreRetrievalGuard.ADVISORY_PATTERNS:
            if re.search(pattern, query_lower):
                return "advisory"

        return "factual"
