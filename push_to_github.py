#!/usr/bin/env python3
"""Push all project files to GitHub via Content API (works with empty repos)."""

import os
import base64
import json
import time
import urllib.request
import urllib.error

TOKEN = open(os.path.expanduser("~/.workbuddy/github-token")).read().strip()
if TOKEN.startswith("\ufeff"):
    TOKEN = TOKEN[1:]
OWNER = "bboytzi"
REPO = "tianfu-doc-assistant"
BRANCH = "main"
PROJECT_ROOT = r"E:\WorkBuddyAI\Claw"

SKIP_DIRS = {".git", "__pycache__", "node_modules", "data", ".venv", "venv", "dist", "push_to_github.py"}
SKIP_FILES = set()


def api_call(url, method="GET", data=None):
    headers = {
        "Authorization": f"token {TOKEN}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
    }
    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    max_retries = 3
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 422 and attempt < max_retries - 1:
                # Already exists or rate limited, try again
                time.sleep(2)
                continue
            err_body = e.read().decode("utf-8")
            try:
                err_json = json.loads(err_body)
                return {"_error": e.code, "_message": err_json.get("message", err_body[:200])}
            except json.JSONDecodeError:
                return {"_error": e.code, "_message": err_body[:200]}
        except urllib.error.URLError as e:
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            return {"_error": "urllib", "_message": str(e)}
    return {"_error": "retries_exhausted"}


def collect_files(root):
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if fn in SKIP_FILES:
                continue
            full_path = os.path.join(dirpath, fn)
            rel_path = os.path.relpath(full_path, root).replace("\\", "/")
            files.append((full_path, rel_path))
    return files


def push_file(full_path, rel_path):
    with open(full_path, "rb") as f:
        content = base64.b64encode(f.read()).decode("utf-8")
    
    url = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{rel_path}"
    data = {
        "message": f"Add: {rel_path}",
        "content": content,
        "branch": BRANCH,
    }
    result = api_call(url, method="PUT", data=data)
    
    if isinstance(result, dict) and result.get("_error"):
        if result.get("_error") == 422:
            # File already exists, update it
            # First get the file's sha
            get_url = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{rel_path}"
            existing = api_call(get_url)
            if isinstance(existing, dict) and "sha" in existing:
                data["sha"] = existing["sha"]
                data["message"] = f"Update: {rel_path}"
                result = api_call(url, method="PUT", data=data)
                if isinstance(result, dict) and result.get("_error"):
                    return False, result["_message"]
            else:
                return False, f"Could not get existing file sha"
        else:
            return False, result.get("_message", "unknown")
    
    return True, "ok"


def push_all():
    print(f"Collecting files from {PROJECT_ROOT}...")
    files = collect_files(PROJECT_ROOT)
    print(f"Found {len(files)} files\n")
    
    success = 0
    failed = []
    
    for i, (full_path, rel_path) in enumerate(files):
        print(f"[{i+1}/{len(files)}] {rel_path}...", end=" ")
        ok, msg = push_file(full_path, rel_path)
        if ok:
            print("OK")
            success += 1
        else:
            print(f"FAILED: {msg}")
            failed.append((rel_path, msg))
        # Small delay to avoid rate limiting
        time.sleep(0.3)
    
    print(f"\n{'='*60}")
    print(f"Done: {success}/{len(files)} files pushed")
    if failed:
        print(f"Failed ({len(failed)}):")
        for path, msg in failed:
            print(f"  {path}: {msg}")
    print(f"\nRepository: https://github.com/{OWNER}/{REPO}")


if __name__ == "__main__":
    push_all()
