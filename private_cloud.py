import requests
import time
import uuid
import json
import re
import typer
import io
import zipfile
import os

from rich.console import Console
from rich.table import Table

from dotenv import load_dotenv

load_dotenv()  # reads variables from a .env file and sets them in os.environ

app = typer.Typer(help="Mirror URLs to private cloud storage")
console = Console()

OWNER = os.environ["OWNER"]
REPO = os.getenv("REPO", "myuploader")
WORKFLOW = os.getenv("WORKFLOW", "multi-private-cloud.yaml")
TOKEN = os.environ["TOKEN"]

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
}


def get(url):
    r = requests.get(url, headers=HEADERS)
    r.raise_for_status()
    return r


def post(url, payload):
    r = requests.post(url, headers=HEADERS, json=payload)
    r.raise_for_status()
    return r


def trigger(urls, request_id):
    payload = {
        "ref": "main",
        "inputs": {
            "urls_json": json.dumps(urls),
            "request_id": request_id,
        },
    }

    post(
        f"https://api.github.com/repos/{OWNER}/{REPO}/actions/workflows/{WORKFLOW}/dispatches",
        payload,
    )


def latest_run():
    runs = get(
        f"https://api.github.com/repos/{OWNER}/{REPO}/actions/runs?per_page=5"
    ).json()["workflow_runs"]

    return runs[0]["id"]


def wait(run_id):
    while True:
        run = get(
            f"https://api.github.com/repos/{OWNER}/{REPO}/actions/runs/{run_id}"
        ).json()

        status = run["status"]
        conclusion = run.get("conclusion")

        console.print(f"Status: {status} {conclusion or ''}")

        if status == "completed":
            if conclusion != "success":
                raise RuntimeError(f"Workflow failed: {conclusion}")
            return

        time.sleep(10)


def get_logs(run_id):
    return get(
        f"https://api.github.com/repos/{OWNER}/{REPO}/actions/runs/{run_id}/logs"
    ).content


def extract(log_zip):
    z = zipfile.ZipFile(io.BytesIO(log_zip))
    logs = ""

    for name in z.namelist():
        logs += z.read(name).decode(errors="ignore")

    match = re.search(r"CLOUD_LINKS_JSON=(\{.*\})", logs)

    if not match:
        raise RuntimeError("Could not find signed URLs in logs")

    return json.loads(match.group(1))


def show(data):
    table = Table(title="Signed Download Links")
    table.add_column("Filename", style="cyan")
    table.add_column("Signed URL", style="green")

    for k, v in data.items():
        table.add_row(k, v)

    console.print(table)


@app.command()
def mirror(urls: list[str]):
    request_id = str(uuid.uuid4())

    console.print(f"[blue]Request ID:[/blue] {request_id}")

    trigger(urls, request_id)

    run_id = latest_run()
    wait(run_id)

    result = extract(get_logs(run_id))
    show(result)


if __name__ == "__main__":
    app()
