import base64
import json


from dotenv import load_dotenv
import jwt
import os
import time
import requests

load_dotenv()

APP_ID = os.environ.get("APP_ID")

with open('private-key.pem', 'r') as f:
    PRIVATE_KEY = f.read()


def generate_jwt():
    payload = {
        "iat": int(time.time()),
        "exp": int(time.time()) + (10 * 60),
        "iss": APP_ID,
    }
    if PRIVATE_KEY:
        jwt_token = jwt.encode(payload, PRIVATE_KEY, algorithm="RS256")
        return jwt_token
    raise ValueError("PRIVATE_KEY not found.")


def get_installation_access_token(jwt, installation_id):
    url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"
    headers = {
        "Authorization": f"Bearer {jwt.decode()}",
        "Accept": "application/vnd.github.v3+json",
    }

    response = requests.post(url, headers=headers)
    return response.json()["token"]


def get_diff_url(pr):
    """GitHub 302s to this URL."""
    original_url = pr.get("url")
    parts = original_url.split("/")
    owner, repo, pr_number = parts[-4], parts[-3], parts[-1]
    return f"https://patch-diff.githubusercontent.com/raw/{owner}/{repo}/pull/{pr_number}.diff"


def get_branch_files(pr, branch, headers, actual_file_names):
    original_url = pr.get("url")
    parts = original_url.split("/")
    owner, repo = parts[-4], parts[-3]
    url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"

    response = requests.get(url, headers=headers)
    tree = response.json().get('tree', [])
    files = {}
    for item in tree:
        if item['type'] == 'blob' and item['path'] in actual_file_names :
            file_url = item['url']
            print(file_url)
            file_response = requests.get(file_url, headers=headers)
            content = file_response.json().get('content', '')
            try:
                decoded_content = base64.b64decode(content).decode('utf-8')
                files[item['path']] = decoded_content
            except:
                print(f'exp with {file_url}')
    return files


def get_pr_head_branch(pr, headers):
    original_url = pr.get("url")
    parts = original_url.split("/")
    owner, repo, pr_number = parts[-4], parts[-3], parts[-1]
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"

    response = requests.get(url, headers=headers)

    # Check if the response is successful
    if response.status_code != 200:
        print(f"Error: Received status code {response.status_code}")
        return ''

    # Safely get the 'ref'
    data = response.json()
    head_data = data.get('head', {})
    ref = head_data.get('ref', '')
    return ref


def files_to_diff_dict(diff):
    files_with_diff = {}
    current_file = None
    for line in diff.split("\n"):
        if line.startswith("diff --git"):
            current_file = line.split(" ")[2][2:]
            files_with_diff[current_file] = {"text": []}
        elif line.startswith("+") and not line.startswith("+++"):
            files_with_diff[current_file]["text"].append(line[1:])
    return files_with_diff


def parse_diff_to_line_numbers(diff):
    files_with_line_numbers = {}
    current_file = None
    line_number = 0
    for line in diff.split("\n"):
        if line.startswith("diff --git"):
            current_file = line.split(" ")[2][2:]
            files_with_line_numbers[current_file] = []
            line_number = 0
        elif line.startswith("@@"):
            line_number = int(line.split(" ")[2].split(",")[0][1:]) - 1
        elif line.startswith("+") and not line.startswith("+++"):
            files_with_line_numbers[current_file].append(line_number)
            line_number += 1
        elif not line.startswith("-"):
            line_number += 1
    return files_with_line_numbers


def get_context_from_files(files, files_with_line_numbers, context_lines=2):
    context_data = {}
    for file, lines in files_with_line_numbers.items():
        file_content = files[file].split("\n")
        context_data[file] = []
        for line in lines:
            start = max(line - context_lines, 0)
            end = min(line + context_lines + 1, len(file_content))
            context_data[file].append('\n'.join(file_content[start:end]))
    return context_data


def get_answer(prompt: str, system_prompt: str, temperature=0.2, max_tokens=1024, top_p=0.7) -> str:
    messages = [{'role': 'user', 'content': system_prompt + '\n\n' + prompt}]
    api_key = os.environ["NVIDIA_API_KEY"]
    #print(messages[0]['content'])
    headers = {
        "Authorization": f"Bearer {api_key}",
        "accept": "text/event-stream",
        "content-type": "application/json",
    }

    payload = {
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "top_p": top_p,
        "seed": 42,
        "stream": True
    }

    api_endpoint = "https://api.nvcf.nvidia.com/v2/nvcf/pexec/functions/008cff6d-4f4c-4514-b61e-bcfad6ba52a7"
    response = requests.post(api_endpoint, headers=headers, json=payload, stream=True)
    res_text = []
    for line in response.iter_lines():
        if line:
            try:
                res_text.append(json.loads(line.decode("utf-8").split('data: ')[1])['choices'][0]['delta']['content'])
            except:
                pass
    print(''.join(res_text))
    return ''.join(res_text)
