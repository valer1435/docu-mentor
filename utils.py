import base64
import os
import time

import jwt
import requests
from dotenv import load_dotenv

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
        if item['type'] == 'blob' and item['path'] in actual_file_names:
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
    res = {}
    diff_files = diff.split('diff --git ')
    for i in diff_files:
        current_file = i.split(" ")[0]
        res[current_file] = []
        splits = re.split(r'@@.*@@', i)
        for j in splits[1::]:
            res[current_file].append(j)


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


if __name__ == '__main__':
    s = """diff --git a/fedot/core/operations/evaluation/operation_implementations/data_operations/sklearn_transformations.py b/fedot/core/operations/evaluation/operation_implementations/data_operations/sklearn_transformations.py
index d1be4d3d1b..644f878691 100644
--- a/fedot/core/operations/evaluation/operation_implementations/data_operations/sklearn_transformations.py
+++ b/fedot/core/operations/evaluation/operation_implementations/data_operations/sklearn_transformations.py
@@ -13,6 +13,7 @@
 from fedot.core.operations.evaluation.operation_implementations. \
     implementation_interfaces import DataOperationImplementation, EncodedInvariantImplementation
 from fedot.core.operations.operation_parameters import OperationParameters
+from fedot.core.repository.dataset_types import DataTypesEnum
 from fedot.preprocessing.data_types import TYPE_TO_ID


@@ -23,6 +24,8 @@ class ComponentAnalysisImplementation(DataOperationImplementation):
         params: OpearationParameters with the arguments
     

+    MIN_THRESHOLD_TS = 7
+
     def __init__(self, params: Optional[OperationParameters]):
         super().__init__(params)
         self.pca = None
@@ -42,7 +45,7 @@ def fit(self, input_data: InputData):
         self.number_of_samples, self.number_of_features = np.array(input_data.features).shape

         if self.number_of_features > 1:
-            self.check_and_correct_params()
+            self.check_and_correct_params(is_ts_data=input_data.data_type is DataTypesEnum.ts)
             self.pca.fit(input_data.features)

         return self.pca
@@ -68,7 +71,7 @@ def transform(self, input_data: InputData) -> OutputData:
         self.update_column_types(output_data)
         return output_data

diff --git a/test/integration/real_applications/test_examples.py b/test/integration/real_applications/test_examples.py
index 8b5796c787..681e6fae9b 100644
--- a/test/integration/real_applications/test_examples.py
+++ b/test/integration/real_applications/test_examples.py
@@ -1,7 +1,6 @@
 from datetime import timedelta

 import numpy as np
-import pytest
 from sklearn.metrics import mean_squared_error

 from examples.advanced.multimodal_text_num_example import run_multi_modal_example
@@ -84,7 +83,6 @@ def test_api_classification_example():
     assert prediction is not None


-@pytest.mark.skip(reason="topo features fail")  # TODO resolve
 def test_api_ts_forecasting_example():
     forecast = run_ts_forecasting_example(dataset='salaries', timeout=2, with_tuning=False)
     assert forecast is not None

"""

import re

sp_files = s.split('diff --git ')
for i in sp_files:
    current_file = i.split(" ")[0]
    print(current_file)
    res = re.split(r'@@.*@@', i)
    for j in res[1::]:
        print('------------------')
        print(j)
