import os
import signal
import subprocess
import sys
import time

import requests

# Get the absolute path of the directory where this script is located
# e.g., /path/to/vocaloid-rate/scripts
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Go up one level to get the project's root directory
# e.g., /path/to/vocaloid-rate
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

# Define the paths we need based on the project root
DOCS_DIR = os.path.join(PROJECT_ROOT, "docs")
OPENAPI_SPEC_PATH = os.path.join(DOCS_DIR, "static", "openapi.json")

GENERATE_DB_DOCS_SCRIPT = os.path.join(SCRIPT_DIR, "generate_db_docs.py")
GENERATE_README_DOCS_SCRIPT = os.path.join(SCRIPT_DIR, "generate_readme_docs.py")


def start_fastapi():
    """Start FastAPI in the background."""
    # The command itself is fine, as it's found in the system's PATH
    cmd = ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

    # We need to run this command from the project root so uvicorn can find "app.main"
    # Note: On Windows, shell=True is often needed for commands like uvicorn if they are scripts.
    # The Popen object needs to know the correct CWD.
    if sys.platform == "win32":
        return subprocess.Popen(cmd, shell=True, cwd=PROJECT_ROOT)
    else:
        return subprocess.Popen(cmd, preexec_fn=os.setsid, cwd=PROJECT_ROOT)


def stop_fastapi(process):
    """Stop the FastAPI process."""
    if sys.platform == "win32":
        process.terminate()
    else:
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
    process.wait()


def fetch_openapi():
    """Fetch the OpenAPI spec and save it."""
    url = "http://localhost:8000/openapi.json"
    for _ in range(10):
        try:
            response = requests.get(url)
            response.raise_for_status()

            # Use the robust, absolute path
            with open(OPENAPI_SPEC_PATH, "w") as f:
                f.write(response.text)
            print("OpenAPI spec saved successfully.")
            return
        except requests.ConnectionError:
            print("Waiting for FastAPI to start...")
            time.sleep(1)
    raise RuntimeError("Failed to fetch OpenAPI spec after 10 seconds.")


def generate_api_docs():
    """Run Docusaurus API doc generation."""
    print(f"Running Docusaurus command in: {DOCS_DIR}")
    subprocess.run(
        ["npm", "run", "gen-api-docs"],
        # Use the robust, absolute path for cwd
        cwd=DOCS_DIR,
        check=True,
        shell=sys.platform == "win32",
    )
    print("API docs generated successfully.")


def generate_db_docs():
    """Run the database schema documentation generation script."""
    print("Generating database schema documentation...")
    subprocess.run(
        [sys.executable, GENERATE_DB_DOCS_SCRIPT],
        cwd=PROJECT_ROOT,
        check=True,
    )
    print("Database schema docs generated successfully.")


def generate_readme_docs():
    """Run the README documentation generation script."""
    print("Generating README documentation...")
    subprocess.run(
        [sys.executable, GENERATE_README_DOCS_SCRIPT],
        cwd=PROJECT_ROOT,
        check=True,
    )
    print("README docs generated successfully.")


def main():
    data_dir = os.path.join(DOCS_DIR, "docs")
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)

    fastapi_process = start_fastapi()
    try:
        fetch_openapi()
        generate_api_docs()
        generate_db_docs()
        generate_readme_docs()
    finally:
        stop_fastapi(fastapi_process)
        print("FastAPI server stopped.")


if __name__ == "__main__":
    main()
