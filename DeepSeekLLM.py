import json
import os
from openai import OpenAI
import requests


class DeepSeekLLM:
    def __init__(self, temperature=0.2, max_tokens=3000, top_p=0.7):
        self.api_endpoint = "https://api.nvcf.nvidia.com/v2/nvcf/pexec/functions/1361fa56-61d7-4a12-af32-69a3825746fa"
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_p = top_p


    def get_answer(self, prompt: str) -> str:

        api_key = os.environ["NVIDIA_API_KEY"]
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com/v1")

        response = client.chat.completions.create(
            model="deepseek-coder",
            messages=[
                {"role": "user", "content": prompt},
            ]
        )

        print(response.choices[0].message.content)
