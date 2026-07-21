import re

class PostRetrievalGuard:
    """Handles verification of chatbot output constraints (sentence count and citation verification)."""
    
    @staticmethod
    def count_sentences(answer: str) -> int:
        """Counts sentences in the answer text using custom regex to handle decimal numbers and abbreviations."""
        lines = answer.split('\n')
        cleaned_lines = []
        for line in lines:
            # Ignore lines specifying source/citation to prevent counting the URL block as a sentence
            if line.strip().lower().startswith(('source:', 'source ', 'citation:', 'citation ')):
                continue
            cleaned_lines.append(line)
        text_without_source = "\n".join(cleaned_lines)
        
        # Remove URLs to avoid dot separation issues
        text_without_urls = re.sub(r'https?://\S+', '', text_without_source)
        
        # Clean common abbreviations with dots.
        # No trailing \b here: these abbreviations are normally followed by a space,
        # and \b after a literal '.' only matches when a word character follows,
        # which would leave the trailing dot to be miscounted as a sentence end.
        text_abbr = re.sub(r'\bp\.\s*a\.', 'pa', text_without_urls, flags=re.IGNORECASE)
        text_abbr = re.sub(r'\be\.\s*g\.', 'eg', text_abbr, flags=re.IGNORECASE)
        text_abbr = re.sub(r'\bi\.\s*e\.', 'ie', text_abbr, flags=re.IGNORECASE)
        
        # Common word abbreviations
        text_abbr = re.sub(r'\b(sip|amc|cr|ltd|co|inc|mr|mrs|dr|vs)\.', r'\1', text_abbr, flags=re.IGNORECASE)
        
        # Split sentences based on punctuation (., !, ?) followed by whitespace or end of string.
        # Negative lookbehind ensures decimal numbers (like 1.5% or 97,350.48) are not split.
        sentence_end = re.compile(r'(?<!\b\d)\s*[.!?]+(?:\s+|\s*$|\n)')
        sentences = sentence_end.split(text_abbr)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        return len(sentences)

    @staticmethod
    def validate_output(query: str, answer: str, context_urls: list) -> bool:
        """
        Validates LLM output against strict constraints:
        1. Sentence count <= 3.
        2. Contains exactly one source URL, which must exist in context_urls.
        Returns True if valid, else False.
        """
        # 1. Extract URLs from answer
        urls = re.findall(r'https?://\S+', answer)
        cleaned_urls = []
        for url in urls:
            # Strip trailing punctuation commonly added at the end of a sentence
            cleaned_url = url.rstrip('.,;)!?]')
            cleaned_urls.append(cleaned_url)
            
        # Must contain exactly one citation URL
        if len(cleaned_urls) != 1:
            return False
            
        target_url = cleaned_urls[0]
        
        # Normalize URLs for matching
        def normalize_url(u):
            u = re.sub(r'^https?://(www\.)?', '', u.lower())
            return u.rstrip('/')
            
        norm_target = normalize_url(target_url)
        norm_contexts = [normalize_url(cu) for cu in context_urls]
        
        if norm_target not in norm_contexts:
            return False
            
        # 2. Count sentences
        sentence_count = PostRetrievalGuard.count_sentences(answer)
        
        # Sentence count must be between 1 and 3 inclusive
        if sentence_count < 1 or sentence_count > 3:
            return False
            
        return True
