import requests
import time
import uuid
import json
import re
import typer
import os
from rich.console import Console
from rich.table import Table

from dotenv import load_dotenv

load_dotenv()  # reads variables from a .env file and sets them in os.environ

app = typer.Typer(help="Mirror URLs to Google Drive via GitHub Actions")
console = Console()

OWNER = os.environ["OWNER"]
REPO = os.getenv("REPO", "myuploader")
WORKFLOW = os.getenv("WORKFLOW", "multi-drive.yaml")
TOKEN = os.environ["TOKEN"]


HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
}


def github_get(url: str):
    r = requests.get(url, headers=HEADERS)
    r.raise_for_status()
    return r


def github_post(url: str, payload: dict):
    r = requests.post(url, headers=HEADERS, json=payload)
    r.raise_for_status()
    return r


def trigger_workflow(urls: list[str], request_id: str):
    payload = {
        "ref": "main",
        "inputs": {
            "urls_json": json.dumps(urls),
            "request_id": request_id,
        },
    }

    github_post(
        f"https://api.github.com/repos/{OWNER}/{REPO}/actions/workflows/{WORKFLOW}/dispatches",
        payload,
    )


def find_run_by_request_id(request_id: str):
    runs = github_get(
        f"https://api.github.com/repos/{OWNER}/{REPO}/actions/runs?per_page=20"
    ).json()["workflow_runs"]

    for run in runs:
        run_id = run["id"]

        jobs = github_get(
            f"https://api.github.com/repos/{OWNER}/{REPO}/actions/runs/{run_id}/jobs"
        ).json()["jobs"]

        for job in jobs:
            if request_id in (job.get("name") or ""):
                return run

        # fallback: compare workflow title timing/name
        if run["name"] == "Multi URL Download and Upload to Google Drive":
            return run

    return None


def wait_for_run(request_id: str):
    console.print("[cyan]Waiting for workflow to start...[/cyan]")

    run = None
    while not run:
        run = find_run_by_request_id(request_id)
        if not run:
            time.sleep(5)

    run_id = run["id"]
    console.print(f"[green]Workflow started[/green] (run id: {run_id})")

    while True:
        run = github_get(
            f"https://api.github.com/repos/{OWNER}/{REPO}/actions/runs/{run_id}"
        ).json()

        status = run["status"]
        conclusion = run.get("conclusion")

        console.print(
            f"[yellow]Status:[/yellow] {status} "
            f"{f'({conclusion})' if conclusion else ''}"
        )

        if status == "completed":
            if conclusion != "success":
                raise RuntimeError(f"Workflow failed: {conclusion}")
            return run_id

        time.sleep(10)


def download_logs(run_id: int):
    r = github_get(
        f"https://api.github.com/repos/{OWNER}/{REPO}/actions/runs/{run_id}/logs"
    )
    return r.content


def extract_links_from_logs(log_bytes: bytes):
    import zipfile
    import io

    z = zipfile.ZipFile(io.BytesIO(log_bytes))

    full_logs = ""

    for file in z.namelist():
        with z.open(file) as f:
            full_logs += f.read().decode(errors="ignore") + "\n"

    match = re.search(r"GDRIVE_LINKS_JSON=(\{.*\})", full_logs)

    if not match:
        raise RuntimeError("Could not find output links in workflow logs.")

    return json.loads(match.group(1))


def print_links(links: dict):
    table = Table(title="Google Drive Direct Links")

    table.add_column("Filename", style="cyan")
    table.add_column("Direct Link", style="green")

    for filename, url in links.items():
        table.add_row(filename, url)

    console.print(table)


@app.command()
def mirror(urls: list[str]):
    """
    Mirror one or multiple URLs to Google Drive.

    Example:
        python mirror_cli.py mirror https://a.com/file1.zip
        python mirror_cli.py mirror https://a.com/f1 https://b.com/f2
    """

    if not urls:
        console.print("[red]No URLs provided[/red]")
        raise typer.Exit(1)

    request_id = str(uuid.uuid4())

    console.print(f"[bold blue]Request ID:[/bold blue] {request_id}")
    console.print(f"[bold blue]Files queued:[/bold blue] {len(urls)}")

    for u in urls:
        console.print(f"  • {u}")

    try:
        console.print("\n[cyan]Triggering workflow...[/cyan]")
        trigger_workflow(urls, request_id)

        run_id = wait_for_run(request_id)

        console.print("\n[cyan]Fetching workflow logs...[/cyan]")
        logs = download_logs(run_id)

        console.print("[cyan]Extracting links...[/cyan]")
        links = extract_links_from_logs(logs)

        console.print("\n[bold green]Done![/bold green]\n")
        print_links(links)

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
