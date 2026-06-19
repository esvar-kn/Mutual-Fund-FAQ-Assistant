import re
from pathlib import Path

class PreRetrievalGuard:
    """Handles query validation before database retrieval (PII checks and intent routing)."""
    
    @staticmethod
    def detect_pii(query: str) -> bool:
        """
        Scans query for personally identifiable information (PII).
        Returns True if PII is detected, else False.
        """
        # 1. Aadhaar Card: 12 digits, with or without spaces
        aadhaar_pattern = re.compile(r'\b\d{4}\s?\d{4}\s?\d{4}\b')
        
        # 2. PAN Card: 5 capital letters, 4 numbers, 1 capital letter
        pan_pattern = re.compile(r'\b[A-Z]{5}\d{4}[A-Z]\b', re.IGNORECASE)
        
        # 3. Email: standard email regex
        email_pattern = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
        
        # 4. Indian Phone Number: 10 digits (typically starting with 6-9)
        phone_pattern = re.compile(r'\b[6-9]\d{9}\b')
        
        # 5. OTP keywords: "otp" or "one time password"
        otp_pattern = re.compile(r'\b(otp|one[- ]time[- ]password)\b', re.IGNORECASE)
        
        if (aadhaar_pattern.search(query) or 
            pan_pattern.search(query) or 
            email_pattern.search(query) or 
            phone_pattern.search(query) or 
            otp_pattern.search(query)):
            return True
            
        return False

    @staticmethod
    def classify_intent(query: str) -> str:
        """
        Classifies query intent to detect advisory requests, comparisons, or factual lookups.
        Returns one of: 'advisory', 'performance_comparison', or 'factual'.
        """
        # Advisory triggers
        advisory_patterns = [
            r"should\s+i\s+(buy|invest|sell|hold|choose)",
            r"which\s+(is|would\s+be)\s+(better|best|preferred)",
            r"where\s+to\s+invest",
            r"\b(recommend|advice|advisable|recommendation)\b",
            r"is\s+it\s+(good|better|safe|risky)\s+to\s+invest"
        ]
        
        # Performance comparison triggers
        comparison_patterns = [
            r"\bvs\b",
            r"\bcompare\b",
            r"performance\s+of",
            r"returns\s+of"
        ]
        
        query_lower = query.lower()
        
        for pattern in advisory_patterns:
            if re.search(pattern, query_lower):
                return "advisory"
                
        for pattern in comparison_patterns:
            if re.search(pattern, query_lower):
                return "performance_comparison"
                
        return "factual"
