from serpapi import GoogleSearch


class SearchEngine:
    def __init__(self, api_key):
        self.api_key = api_key

    def get_search_results(self, query):
        params = self._get_search_params(query)
        results = self._get_google_search_results(params)
        return self._format_search_results(results)

    def _get_search_params(self, query):
        return {
            "q": query,
            "num": 10,
            "google_domain": "google.com",
            "api_key": self.api_key
        }

    def _get_google_search_results(self, params):
        search = GoogleSearch(params)
        return search.get_dict().get("organic_results", [])

    def _format_search_results(self, results):
        return [
            {
                "title": result.get("title", ""),
                "link": result.get("link", ""),
                "snippet": result.get("snippet", "")
            }
            for result in results
        ]