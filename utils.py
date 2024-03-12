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


# def parse_diff_to_line_numbers(diff):
#     print(diff)
#     files_with_line_numbers = {}
#     current_file = None
#     line_number = 0
#     for line in diff.split("\n"):
#         if line.startswith("diff --git"):
#             current_file = line.split(" ")[2][2:]
#             files_with_line_numbers[current_file] = []
#             line_number = 0
#         elif line.startswith("@@"):
#             line_number = int(line.split(" ")[2].split(",")[0][1:]) - 1
#         elif line.startswith("+") and not line.startswith("+++"):
#             files_with_line_numbers[current_file].append(line_number)
#             line_number += 1
#         elif not line.startswith("-"):
#             line_number += 1
#     return files_with_line_numbers

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
            files_with_line_numbers[current_file].append(line)
            line_number += 1
        elif not line.startswith("-"):
            line_number += 1
            files_with_line_numbers[current_file].append(line)
        else:
            files_with_line_numbers[current_file].append(line)
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

