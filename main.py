import asyncio
import logging
import os
import string
import sys

import httpx
import openai
import ray
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from ray import serve

from utils import (
    generate_jwt,
    get_installation_access_token,
    get_diff_url,
    get_branch_files,
    get_pr_head_branch,
    parse_diff_to_line_numbers,
    get_context_from_files,
    get_answer
)

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger("Open code helper")

GREETING = """
👋 Hi, I'm @docu-mentor, an LLM-powered GitHub app
powered by [Anyscale Endpoints](https://app.endpoints.anyscale.com/)
that gives you actionable feedback on your writing.

Simply create a new comment in this PR that says:

@docu-mentor run

and I will start my analysis. I only look at what you changed
in this PR. If you only want me to look at specific files or folders,
you can specify them like this:

@docu-mentor run doc/ README.md

In this example, I'll have a look at all files contained in the "doc/"
folder and the file "README.md". All good? Let's get started!
"""

load_dotenv()

# If the app was installed, retrieve the installation access token through the App's
# private key and app ID, by generating an intermediary JWT token.

ANYSCALE_API_ENDPOINT = "https://api.endpoints.anyscale.com/v1"
openai.api_base = ANYSCALE_API_ENDPOINT
openai.api_key = os.environ.get("ANYSCALE_API_KEY")

SYSTEM_CONTENT = """You are a helpful assistant who helps developers improve their code in pull-request.
Improve the following <content>. Criticise syntax, grammar, punctuation, style, etc.
Recommend common technical writing knowledge, such as used in Vale
and the Google developer documentation style guide.
For Python docstrings, make sure input arguments and return values are documented.
Also, docstrings should have good descriptions and come with examples.
If the content is good, don't comment on it.
You can use GitHub-flavored markdown syntax in your answer.
If you encounter several files, give very concise feedback per file.
"""

PROMPT = """Improve this content.
Don't comment on file names or other meta data, just the actual text.
The <content> will be in JSON format.
Make sure to give very concise feedback per file.
"""


def mentor(
        content,
        prompt=PROMPT
):
    content = get_answer(f"This is the content: {content}. {prompt}", SYSTEM_CONTENT)

    return content


try:
    ray.init()
except:
    logger.info("Ray init failed.")


@ray.remote
def mentor_task(content, prompt):
    return mentor(content, prompt)


def ray_mentor(
        content: dict,
        prompt=PROMPT
):
    futures = [
        mentor_task.remote(v, prompt)
        for v in content.values()
    ]
    suggestions = ray.get(futures)
    content = {k: v[0] for k, v in zip(content.keys(), suggestions)}

    print_content = ""
    for k, v in content.items():
        print_content += f"{k}:\n\t\{v}\n\n"
    # logger.info(print_content)

    return print_content


app = FastAPI()


async def handle_webhook(request: Request):
    data = await request.json()

    installation = data.get("installation")
    if installation and installation.get("id"):
        installation_id = installation.get("id")
        logger.info(f"Installation ID: {installation_id}")

        JWT_TOKEN = generate_jwt()

        installation_access_token = await get_installation_access_token(
            JWT_TOKEN, installation_id
        )
        headers = {
            "Authorization": f"token {installation_access_token}",
            "User-Agent": "open-code-helper",
            "Accept": "application/vnd.github.VERSION.diff",
        }
    else:
        raise ValueError("No app installation found.")

    # If PR exists and is opened
    if "pull_request" in data.keys() and (
            data["action"] in ["opened", "reopened"]
    ):  # use "synchronize" for tracking new commits
        pr = data.get("pull_request")

        # Greet the user and show instructions.
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{pr['issue_url']}/comments",
                json={"body": GREETING},
                headers=headers,
            )
        return JSONResponse(content={}, status_code=200)
    # Check if the event is a new or modified issue comment
    if "issue" in data.keys() and data.get("action") in ["created", "edited"]:
        issue = data["issue"]

        # Check if the issue is a pull request
        if "/pull/" in issue["html_url"]:
            pr = issue.get("pull_request")

            # Get the comment body
            comment = data.get("comment")
            comment_body = comment.get("body")
            # Remove all whitespace characters except for regular spaces
            comment_body = comment_body.translate(
                str.maketrans("", "", string.whitespace.replace(" ", ""))
            )

            # Skip if the bot talks about itself
            author_handle = comment["user"]["login"]

            # Check if the bot is mentioned in the comment
            if (
                    author_handle != "open-code-helper[bot]"
                    and "@open-code-helper run" in comment_body
            ):

                async with httpx.AsyncClient(timeout=1000) as client:  # Fetch diff from GitHub
                    files_to_keep = comment_body.replace(
                        "@open-code-helper run", ""
                    ).split(" ")
                    files_to_keep = [item for item in files_to_keep if item]

                    # logger.info(files_to_keep)

                    url = get_diff_url(pr)
                    diff_response = await client.get(url, headers=headers)
                    diff = diff_response.text

                    files_with_lines = parse_diff_to_line_numbers(diff)

                    # Get head branch of the PR
                    headers["Accept"] = "application/vnd.github.full+json"
                    head_branch = await get_pr_head_branch(pr, headers)

                    # Get files from head branch
                    head_branch_files = await get_branch_files(pr, head_branch, headers)

                    # Enrich diff data with context from the head branch.
                    context_files = get_context_from_files(head_branch_files, files_with_lines)

                    # Filter the dictionary
                    if files_to_keep:
                        context_files = {
                            k: context_files[k]
                            for k in context_files
                            if any(sub in k for sub in files_to_keep)
                        }
                    print(context_files)
                    # Get suggestions from Open code helper
                    content = mentor(context_files)
                    print(content)

                    # Let's comment on the PR
                    await client.post(
                        f"{comment['issue_url']}/comments",
                        json={
                            "body": f":rocket: Open code helper finished "
                                    + "analysing your PR! :rocket:\n\n"
                                    + "Take a look at your results:\n"
                                    + f"{content}\n\n"
                                    + "This bot is powered by "
                                    + "[NVIDIA AI Foundation Models and Endpoints](https://catalog.ngc.nvidia.com/ai-foundation-models).\n"
                        },
                        headers=headers
                    )


@serve.deployment(route_prefix="/")
@serve.ingress(app)
class ServeBot:
    @app.get("/")
    async def root(self):
        return {"message": "Open code helper reporting for duty!"}

    @app.post("/webhook/")
    async def handle_webhook_route(self, request: Request):
        return await handle_webhook(request)


# Run with: serve run main:bot
bot = ServeBot.bind()
