import requests
from bs4 import BeautifulSoup

class DocumentFetcher:
    """Handles raw HTML page crawling with request headers and timeout constraints."""
    @staticmethod
    def fetch_and_save_html(url, raw_html_path, headers, amc_slug):
        """
        Fetches raw HTML from a Groww mutual fund page URL.
        Saves raw HTML directly to raw_html_path.
        Returns a tuple: (success: bool, html_content: str)
        """
        print(f"-> Fetching raw HTML from: {url}")
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                html_content = response.text
                soup = BeautifulSoup(response.content, 'html.parser')
                cleaned_text = soup.get_text()
                
                # Check for standard Groww fund page text length
                if len(cleaned_text) > 1000 and amc_slug.split('_')[0] in cleaned_text.lower():
                    with open(raw_html_path, "w", encoding="utf-8") as f:
                        f.write(soup.prettify())
                    return True, html_content
                else:
                    print("--> Warning: Scraped text is too short or indicator keywords are missing.")
            else:
                print(f"--> HTTP status code {response.status_code}.")
        except Exception as e:
            print(f"--> Exception occurred during fetch: {e}")
            
        return False, ""
