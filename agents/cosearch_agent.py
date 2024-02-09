import os
import openai
import time
import backoff
import html2text
import concurrent.futures
import requests

text_extractor = html2text.HTML2Text()
text_extractor.ignore_links = True
text_extractor.ignore_images = True
text_extractor.ignore_tables = True
text_extractor.ignore_emphasis = True


class CoSearchAgent:
    def __init__(self, search_engine, api_key, model_name="gpt-3.5-turbo-1106",
                 prompt_dir="prompts/en_complete_agent", temperature=0, n=1):
        self.api_key = api_key
        self.initialize_openai()

        self.model_name = model_name
        self.temperature = temperature
        self.n = n
        self.prompt_dir = prompt_dir
        assert os.path.exists(prompt_dir)

        self.search_engine = search_engine

    def initialize_openai(self):
        openai.api_key = self.api_key

    @backoff.on_exception(backoff.expo, openai.error.RateLimitError)
    def generate_openai_response(self, prompt):
        response = openai.ChatCompletion.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.temperature,
            n=self.n
        )["choices"][0]["message"]["content"]
        response = "\n".join(response.split("\n\n"))
        return response

    def load_prompt_from_file(self, prompt_type, placeholders, replacements):
        prompt_file = os.path.join(self.prompt_dir, f"{prompt_type}.txt")
        assert os.path.exists(prompt_file)

        with open(prompt_file, "r", encoding="utf8") as file:
            prompt = file.read()

        for placeholder, replacement in zip(placeholders, replacements):
            prompt = prompt.replace(placeholder, replacement)

        return prompt

    def generate_agent_response(self, prompt_type, placeholders, replacements):
        prompt = self.load_prompt_from_file(prompt_type, placeholders, replacements)
        #print(prompt)
        return self.generate_openai_response(prompt)

    def rewrite_query(self, query, user, convs):
        start_time = time.time()
        output = self.generate_agent_response("rewrite_query", ["[query]", "[user]", "[convs]"],
                                              [query, user, convs])
        return output, time.time() - start_time

    def ask_clarify_query(self, query, user, convs):
        start_time = time.time()
        output = self.generate_agent_response("ask_clarify_query", ["[query]", "[user]", "[convs]"],
                                              [query, user, convs])
        return output, time.time() - start_time

    def fetch_webpage_source(self, url):
        try:
            response = requests.get(url)
            response.raise_for_status()
            response.encoding = response.apparent_encoding
            return response.text
        except Exception as e:
            print(f"An fetch error occurred：{e}")
            return None

    def extract_raw_text(self, webpage):
        try:
            raw_text = text_extractor.handle(webpage)
            return raw_text
        except Exception as e:
            print(f"An extract error occurred: {e}")
            return None

    def extract_reference(self, query, link, max_text_length=5000):
        webpage = self.fetch_webpage_source(link)
        if not webpage:
            return None

        raw_text = self.extract_raw_text(webpage)
        if not raw_text:
            return None

        raw_text = "\n".join(raw_text.split("\n\n"))
        truncated_text = raw_text[:max_text_length]
        reference = self.generate_agent_response("extract_reference", ["[query]", "[document]"],
                                                 [query, truncated_text])
        if "不存在摘要" in reference or "None" in reference:
            return None

        return reference

    def generate_answer(self, query):
        search_results = self.search_engine.get_search_results(query)

        start_time = time.time()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            references = list(
                executor.map(lambda result: self.extract_reference(query, result["link"]), search_results))
        extract_time = time.time() - start_time

        search_results = [
            {"title": search_result["title"], "link": search_result["link"], "snippet": ref}
            for search_result, ref in zip(search_results, references) if ref
        ]
        references = [ref for ref in references if ref]
        references = "\n".join([f"[{i + 1}] {ref}" for i, ref in enumerate(references)])

        start_time = time.time()
        answer = self.generate_agent_response("generate_answer", ["[query]", "[references]"],
                                              [query, references])
        answer_time = time.time() - start_time

        return answer, search_results, extract_time, answer_time