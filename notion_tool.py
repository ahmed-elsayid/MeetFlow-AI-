import os
import json
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

def _heading(text: str, level: int = 2) -> dict:
    key = f"heading_{level}"
    return {"object": "block", key: {"rich_text": [{"text": {"content": text}}]}}


def _paragraph(text: str) -> dict:
    return {
        "object": "block",
        "paragraph": {"rich_text": [{"text": {"content": text[:2000]}}]},
    }


def _bullet(text: str) -> dict:
    return {
        "object": "block",
        "bulleted_list_item": {"rich_text": [{"text": {"content": text}}]},
    }


def _build_blocks(analysis: dict, transcript: str) -> list:
    """Convert analysis dict + transcript into Notion block children."""
    blocks = []
    blocks.append(_heading("Summary"))
    blocks.append(_paragraph(analysis.get("summary", "")))

    if analysis.get("key_points"):
        blocks.append(_heading("Key Discussion Points"))
        for point in analysis["key_points"]:
            blocks.append(_bullet(point))

    if analysis.get("decisions"):
        blocks.append(_heading("Decisions Made"))
        for d in analysis["decisions"]:
            blocks.append(_bullet(d))

    if analysis.get("action_items"):
        blocks.append(_heading("Action Items"))
        for item in analysis["action_items"]:
            owner = item.get("owner", "")
            task  = item.get("task", "")
            label = f"[{owner}] {task}" if owner else task
            blocks.append(_bullet(label))

    if transcript:
        blocks.append(_heading("Full Transcript"))
        for i in range(0, min(len(transcript), 10_000), 2000):
            blocks.append(_paragraph(transcript[i : i + 2000]))

    return blocks

async def _save_async(analysis: dict, transcript: str) -> str:
    server_script = os.path.join(os.path.dirname(__file__), "notion_mcp_server.py")
    server_params = StdioServerParameters(
        command="C:/Users/CARNIVAL/miniconda3/python.exe",
        args=[server_script],
        env={
            "NOTION_TOKEN": os.environ["NOTION_TOKEN"],
            "PATH": os.environ.get("PATH", ""),  
        },
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools_resp  = await session.list_tools()
            tool_names  = [t.name for t in tools_resp.tools]
            print(f"[MCP] Notion MCP tools available: {tool_names}")

            create_tool = next(
                (n for n in tool_names if "create" in n and "page" in n),
                None,
            )
            if not create_tool:
                raise RuntimeError(
                    f"No create_page tool found. Available: {tool_names}"
                )

            title     = analysis.get("title", "Meeting Notes")
            parent_id = os.environ["NOTION_PARENT_PAGE_ID"]
            blocks    = _build_blocks(analysis, transcript)

            print(f"[MCP] Creating Notion page: '{title}'...")
            result = await session.call_tool(
                name=create_tool,
                arguments={
                    "parent":     {"page_id": parent_id},
                    "properties": {
                        "title": [{"text": {"content": title}}]
                    },
                    "children": blocks,
                },
            )

            try:
                data = json.loads(result.content[0].text)
                return data.get("url", "")
            except Exception:
                return ""


def save_to_notion(analysis: dict, transcript: str) -> str:
    """Synchronous wrapper -- creates the Notion page and returns its URL."""
    return asyncio.run(_save_async(analysis, transcript))
