import os
import json
import urllib.request
import urllib.error
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Notion Storage Server")

NOTION_TOKEN = os.environ.get("NOTION_TOKEN")

@mcp.tool()
def create_page(parent: dict, properties: dict, children: list = None) -> str:
    """
    Create a new page in Notion.
    
    :param parent: Parent object, e.g., {"page_id": "..."} or {"database_id": "..."}
    :param properties: Page properties, e.g., {"title": [{"text": {"content": "..."}}]}
    :param children: Optional block children to populate the page content.
    """
    if not NOTION_TOKEN:
        raise ValueError("NOTION_TOKEN environment variable is not set")

    url = "https://api.notion.com/v1/pages"
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    payload = {
        "parent": parent,
        "properties": properties
    }
    if children is not None:
        payload["children"] = children

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req) as response:
            return response.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        raise RuntimeError(f"Notion API error (HTTP {e.code}): {error_body}")
    except Exception as e:
        raise RuntimeError(f"Failed to communicate with Notion API: {e}")

if __name__ == "__main__":
    mcp.run()
