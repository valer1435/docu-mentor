import os
from openai import OpenAI


class DeepSeekLLM:
    def __init__(self, temperature=0.2, max_tokens=3000, top_p=0.7):
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_p = top_p

    def get_answer(self, prompt: str) -> str:
        api_key = os.environ["DEEPSEEK_API_KEY"]
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com/v1")

        response = client.chat.completions.create(
            model="deepseek-coder",
            messages=[
                {"role": "user", "content": prompt},
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            top_p=self.top_p
        )

        return response.choices[0].message.content
