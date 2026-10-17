"""Opt-in export of a *selected* public, reviewed AgentBroker note to Notion.

No automatic sync; no API key exposure; use a database shared with integration.
"""
import json
import os
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit

NOTION_VERSION = "2022-06-28"
API = "https://api.notion.com/v1"
MAX_NOTE = 1800


class NotionSyncError(Exception):
    pass


def configured():
    return bool(os.getenv("NOTION_API_KEY") and os.getenv("NOTION_KNOWLEDGE_DATABASE_ID"))


def preview(note):
    """Make a bounded payload, without touching network. Reviewed/public notes only."""
    if not isinstance(note, dict):
        raise ValueError("Expected knowledge note")
    title = note.get("topic", "")
    body = note.get("note", "")
    sources = note.get("sources", [])
    if not isinstance(title, str) or not title.strip() or len(title) > 200:
        raise ValueError("Invalid note title")
    if not isinstance(body, str) or not body.strip() or len(body) > MAX_NOTE:
        raise ValueError("Note must contain 1-1800 characters; shorten before export")
    if not isinstance(sources, list) or not sources or len(sources) > 10:
        raise ValueError("At least one source is required")
    first = sources[0]
    url = first.get("url", "") if isinstance(first, dict) else ""
    if not isinstance(url, str) or not url.startswith("https://") or len(url) > 2000:
        raise ValueError("First source requires an HTTPS URL")
    # No text is sent merely because a note was saved locally.
    return {
        "parent": {"database_id": os.getenv("NOTION_KNOWLEDGE_DATABASE_ID", "")},
        "properties": {
            "Topic": {"title": [{"text": {"content": title}}]},
            "Summary": {"rich_text": [{"text": {"content": body}}]},
            "Source URL": {"url": url},
            "Source Type": {"select": {"name": "Research"}},
            "Category": {"select": {"name": "Other"}},
            "Status": {"status": {"name": "Done"}},
            "Tags": {"multi_select": [{"name": "AgentBroker"}]},
        },
    }


def publish(payload, timeout=12):
    if not configured():
        raise NotionSyncError("Notion sync is not configured")
    expected = os.environ["NOTION_KNOWLEDGE_DATABASE_ID"]
    if payload.get("parent", {}).get("database_id") != expected:
        raise NotionSyncError("Unexpected target database")
    request = Request(
        API + "/pages",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + os.environ["NOTION_API_KEY"],
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            result = json.load(response)
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        raise NotionSyncError("Notion request failed; check integration access and schema") from exc
    return {"id": result.get("id"), "url": result.get("url")}

def pull_records(limit=20, timeout=12):
    """Read trusted Notion database properties; does not modify local memory."""
    if not configured():
        raise NotionSyncError("Notion sync is not configured")
    if not isinstance(limit, int) or not 1 <= limit <= 50:
        raise ValueError("limit must be 1-50")
    database_id = os.environ["NOTION_KNOWLEDGE_DATABASE_ID"]
    if not all(c.isalnum() or c == "-" for c in database_id):
        raise NotionSyncError("Invalid Notion database ID")
    request = Request(
        API + "/databases/" + database_id + "/query",
        data=json.dumps({"page_size": limit, "filter": {
            "property": "Status", "status": {"equals": "Done"}
        }}).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + os.environ["NOTION_API_KEY"],
            "Notion-Version": NOTION_VERSION, "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            response_data = json.load(response)
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        raise NotionSyncError("Unable to read Notion database") from exc
    notes = []
    for page in response_data.get("results", []):
        props = page.get("properties", {})
        title = "".join(part.get("plain_text", "") for part in props.get("Topic", {}).get("title", []))
        body = "".join(part.get("plain_text", "") for part in props.get("Summary", {}).get("rich_text", []))
        source = props.get("Source URL", {}).get("url", "")
        # Only vetted, fully specified pages enter a retrieval preview.
        if (title.strip() and body.strip() and len(body) <= MAX_NOTE
                and isinstance(source, str) and source.startswith("https://")
                and urlsplit(source).hostname):
            notes.append({
                "id": page.get("id"), "topic": title, "note": body,
                "sources": [{"title": "Notion source", "url": source, "content": ""}],
                "created_at": page.get("created_time", ""),
            })
    return {"notes": notes, "has_more": bool(response_data.get("has_more"))}
