import json
import os

import requests


class NvidiaLLM:
    def __init__(self, temperature=0.2, max_tokens=3000, top_p=0.7):
        self.api_endpoint = "https://api.nvcf.nvidia.com/v2/nvcf/pexec/functions/1361fa56-61d7-4a12-af32-69a3825746fa"
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_p = top_p

    def get_answer(self, prompt: str, ) -> str:
        messages = [{'role': 'user', 'content': prompt}]
        api_key = os.environ["NVIDIA_API_KEY"]
        headers = {
            "Authorization": f"Bearer {api_key}",
            "accept": "text/event-stream",
            "content-type": "application/json",
        }

        payload = {
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
            "seed": 42,
            "stream": True
        }
        print(prompt)
        api_endpoint = "https://api.nvcf.nvidia.com/v2/nvcf/pexec/functions/008cff6d-4f4c-4514-b61e-bcfad6ba52a7"
        response = requests.post(api_endpoint, headers=headers, json=payload, stream=True)
        res_text = []
        for line in response.iter_lines():
            if line:
                try:
                    res_text.append(
                        json.loads(line.decode("utf-8").split('data: ')[1])['choices'][0]['delta']['content'])
                except:
                    pass
        print(''.join(res_text))
        return ''.join(res_text)
