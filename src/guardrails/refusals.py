from src.config import REFUSAL_MESSAGES


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
