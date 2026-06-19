from pathlib import Path

# Try-except absolute/local import for configuration resilience
try:
    from src.config import REFUSAL_MESSAGES
except ModuleNotFoundError:
    import sys
    current_dir = Path(__file__).resolve().parent
    sys.path.append(str(current_dir.parent.parent))
    sys.path.append(str(current_dir.parent))
    
    try:
        from src.config import REFUSAL_MESSAGES
    except ModuleNotFoundError:
        # Fallback dictionary if config cannot be loaded directly
        REFUSAL_MESSAGES = {
            "advisory": (
                "I can only provide factual, objective details about mutual fund schemes. "
                "I cannot provide investment advice or recommendations. "
                "For official education resources, please visit AMFI: https://www.amfiindia.com/investor-corner"
            ),
            "pii": (
                "For your security and privacy, please do not share personal information "
                "like Aadhaar numbers, PAN cards, OTPs, or bank account numbers. "
                "Please check your account portal directly on the official AMC website."
            ),
            "out_of_context": (
                "I do not have access to official documents containing that information. "
                "You can verify official guidelines and filings directly on SEBI: https://www.sebi.gov.in/"
            ),
            "error": (
                "Our RAG services are currently busy. Please consult the official AMC website."
            )
        }

class RefusalFormatter:
    """Formats and retrieves standard system refusals."""
    
    @staticmethod
    def get_advisory_refusal() -> str:
        return REFUSAL_MESSAGES["advisory"]
        
    @staticmethod
    def get_pii_refusal() -> str:
        return REFUSAL_MESSAGES["pii"]
        
    @staticmethod
    def get_out_of_context_refusal() -> str:
        return REFUSAL_MESSAGES["out_of_context"]
