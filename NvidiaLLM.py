import json
import os

import requests


class NvidiaLLM:
    def __init__(self, system_prompt,model_config):
        self.system_prompt = system_prompt
        self.model_config = model_config
        self.api_endpoint = "https://api.nvcf.nvidia.com/v2/nvcf/pexec/functions/2ae529dc-f728-4a46-9b8d-2697213666d8"

    def get_answer(self, prompt: str) -> str:
        messages = [{'role': 'user', 'content': prompt}, {'role': 'user', 'content': prompt}]
        api_key = os.environ["NVIDIA_API_KEY"]

        headers = {
            "Authorization": f"Bearer {api_key}",
            "accept": "text/event-stream",
            "content-type": "application/json",
        }

        payload = {
            "messages": messages,
            "temperature": self.model_config['temperature'],
            "max_tokens":  self.model_config['max_tokens'],
            "seed": 42,
            "stream": True
        }
        if self.model_config['top_p']:
            payload["top_p"] = self.model_config['top_p']

        response = requests.post(self.api_endpoint, headers=headers, json=payload, stream=True)

        res_text = []
        for line in response.iter_lines():
            if line:
                try:
                    res_text.append(
                        json.loads(line.decode("utf-8").split('data: ')[1])['choices'][0]['delta']['content'])
                except:
                    pass
        return ''.join(res_text)