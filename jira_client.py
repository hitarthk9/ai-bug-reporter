import os
import json
import requests
import time


def attach_file_to_issue(jira_url: str, jira_email: str, jira_token: str, issue_key: str, file_path: str, max_retries: int = 3) -> tuple[bool, str]:
    """Attach a file to a Jira issue with retry logic. Returns (success: bool, error_message: str)."""
    try:
        # Verify file exists and get size
        if not os.path.exists(file_path):
            return False, f"File not found: {file_path}"

        file_size = os.path.getsize(file_path)
        if file_size == 0:
            return False, "File is empty"

        # Jira has a 10MB limit for attachments (can be configured higher)
        if file_size > 10 * 1024 * 1024:
            return False, f"File too large: {file_size / 1024 / 1024:.1f}MB (max 10MB)"

        # Verify it's a valid MP4 by checking file header
        with open(file_path, "rb") as f:
            header = f.read(12)
            # MP4 files start with ftyp box
            if not (header[4:8] == b'ftyp' or header[0:4] == b'\x00\x00\x00\x20ftyp'):
                return False, "File does not appear to be a valid MP4"

        filename = os.path.basename(file_path)
        # Ensure .mp4 extension for proper MIME type detection
        if not filename.lower().endswith('.mp4'):
            filename = filename.rsplit('.', 1)[0] + '.mp4'

        # Retry logic with exponential backoff
        last_error = None
        for attempt in range(max_retries):
            try:
                # Read file fresh for each attempt
                with open(file_path, "rb") as f:
                    # Use proper MIME type for MP4
                    files = {"file": (filename, f, "video/mp4")}
                    headers = {
                        "X-Atlassian-Token": "no-check",
                        "Accept": "application/json"
                    }

                    # Increase timeout based on file size (1 second per MB, minimum 60s, maximum 300s)
                    timeout_seconds = min(max(60, int(file_size / (1024 * 1024))), 300)

                    resp = requests.post(
                        f"{jira_url}/rest/api/3/issue/{issue_key}/attachments",
                        auth=(jira_email, jira_token),
                        headers=headers,
                        files=files,
                        timeout=timeout_seconds
                    )

                    if resp.status_code < 300:
                        return True, ""
                    else:
                        error_text = resp.text[:500] if resp.text else "No error message"
                        last_error = f"HTTP {resp.status_code}: {error_text}"
                        # Don't retry on 4xx errors (client errors)
                        if 400 <= resp.status_code < 500:
                            return False, last_error
            except requests.exceptions.Timeout:
                last_error = f"Upload timeout (attempt {attempt + 1}/{max_retries})"
            except requests.exceptions.RequestException as e:
                last_error = f"Network error (attempt {attempt + 1}/{max_retries}): {str(e)}"
            except Exception as e:
                last_error = f"Unexpected error (attempt {attempt + 1}/{max_retries}): {str(e)}"

            # Wait before retry (exponential backoff)
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # 1s, 2s, 4s
                time.sleep(wait_time)

        return False, last_error or "Upload failed after all retries"
    except Exception as e:
        return False, f"Exception: {str(e)}"


def text_to_adf(text: str) -> dict:
    """Convert plain text to Atlassian Document Format (ADF)."""
    if not text:
        return {
            "version": 1,
            "type": "doc",
            "content": []
        }

    # Split by newlines and create paragraphs
    lines = text.strip().split("\n")
    paragraphs = []
    for line in lines:
        if line.strip():  # Skip empty lines
            paragraphs.append({
                "type": "paragraph",
                "content": [
                        {
                            "type": "text",
                            "text": line.strip()
                        }
                ]
            })

    # If no content, add empty paragraph
    if not paragraphs:
        paragraphs.append({
            "type": "paragraph",
            "content": []
        })

    return {
        "version": 1,
        "type": "doc",
        "content": paragraphs
    }


def create_issues(bugs_list: list, video_clips: dict = None) -> list:
    """
    Create Jira issues for given bug dicts. Attach video clips if provided.
    video_clips: dict mapping bug index to video file path.
    Returns list of error dicts (empty if none).
    """
    jira_url = os.getenv("JIRA_URL")
    jira_token = os.getenv("JIRA_TOKEN")
    jira_email = os.getenv("JIRA_EMAIL")
    project_key = os.getenv("JIRA_PROJECT")

    errors = []
    if not (jira_url and jira_token and jira_email and project_key):
        return [{"error": "Missing Jira environment variables"}]

    video_clips = video_clips or {}

    for idx, b in enumerate(bugs_list):
        description_text = b.get("description", "")
        description_adf = text_to_adf(description_text)

        payload = {
            "fields": {
                "project": {"key": project_key},
                "summary": b.get("summary", "QA Bug"),
                "description": description_adf,
                "issuetype": {"name": "Bug"},
                "priority": {"name": b.get("priority", "Medium")}
            }
        }
        try:
            # Create the issue
            resp = requests.post(
                f"{jira_url}/rest/api/3/issue",
                auth=(jira_email, jira_token),
                headers={"Content-Type": "application/json"},
                data=json.dumps(payload),
                timeout=30
            )
            if resp.status_code >= 300:
                errors.append({"status": resp.status_code, "body": resp.text})
                continue

            # Extract issue key from response
            issue_data = resp.json()
            issue_key = issue_data.get("key")

            # Attach video clip if available
            if issue_key and idx in video_clips:
                video_path = video_clips[idx]
                if os.path.exists(video_path):
                    attached, error_msg = attach_file_to_issue(
                        jira_url, jira_email, jira_token, issue_key, video_path)
                    if not attached:
                        errors.append(
                            {"warning": f"Failed to attach video to {issue_key}: {error_msg}"})
        except Exception as e:
            errors.append({"error": str(e)})
    return errors
