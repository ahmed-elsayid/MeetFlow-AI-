from fastapi import FastAPI
from fastapi.responses import RedirectResponse
import os
from pathlib import Path
import httpx
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================
# Environment variables
# ============================

NOTION_CLIENT_ID = os.getenv("NOTION_CLIENT_ID")
NOTION_CLIENT_SECRET = os.getenv("NOTION_CLIENT_SECRET")

REDIRECT_URI = "http://localhost:8000/auth/notion/callback"


# Notion OAuth authorization URL
AUTH_URL = (
    "https://api.notion.com/v1/oauth/authorize"
    f"?client_id={NOTION_CLIENT_ID}"
    "&response_type=code"
    "&owner=user"
    f"&redirect_uri={REDIRECT_URI}"
)


# ============================
# Test server
# ============================

@app.get("/")
def home():
    return {
        "message": "Notion OAuth Server Running"
    }


# ============================
# Step 1:
# Redirect user to Notion OAuth
# ============================

@app.get("/auth/notion")
def notion_login():

    return RedirectResponse(AUTH_URL)


# ============================
# Step 2:
# Notion redirects here
# ============================

@app.get("/auth/notion/callback")
async def notion_callback(code: str):

    token_url = "https://api.notion.com/v1/oauth/token"

    async with httpx.AsyncClient() as client:

        response = await client.post(
            token_url,
            auth=(
                NOTION_CLIENT_ID,
                NOTION_CLIENT_SECRET
            ),
            json={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URI
            }
        )
        

    data = response.json()
    if "access_token" in data:
        # Write token to project root so notetaker.py can find it reliably
        token_path = Path(__file__).resolve().parent.parent.parent / "notion_token.txt"
        token_path.write_text(data["access_token"], encoding="utf-8")
        return {
            "message": "OAuth successful",
            "access_token": data["access_token"],
            "workspace": data.get("workspace_name"),
        }

    return {"message": "OAuth failed", "error": data}