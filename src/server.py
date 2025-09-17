#!/usr/bin/env python3
import os
import re
from typing import Optional, Dict, Any
import httpx
from fastmcp import FastMCP

mcp = FastMCP("Sample MCP Server")

@mcp.tool(description="Greet a user by name with a welcome message from the MCP server")
def greet(name: str) -> str:
    return f"Hello, {name}! Welcome to our Empath MCP server running on Render!"

@mcp.tool(description="Get information about the MCP server including name, version, environment, and Python version")
def get_server_info() -> dict:
    return {
        "server_name": "Empath MCP Server",
        "version": "1.0.0",
        "environment": os.environ.get("ENVIRONMENT", "development"),
        "python_version": os.sys.version.split()[0]
    }

@mcp.tool(description="Create a text journal entry in Empath")
def create_empath_journal_entry(
    text_journal: str,
    user_phone_number: str,
) -> Dict[str, Any]:
    base_url = os.environ.get("EMPATH_BASE_URL", "https://app.empathdash.com")
    endpoint = f"{base_url.rstrip('/')}/api/journals/createTextEntryOrRegister"

    headers: Dict[str, str] = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    # Minimal client-side validation
    normalized_text = (text_journal or "").strip()
    normalized_phone = (user_phone_number or "").strip()
    validation_errors: Dict[str, str] = {}

    if not normalized_text:
        validation_errors["text_journal"] = "Must be non-empty after trimming."

    # Strict E.164: + followed by 2-15 digits, first digit non-zero
    if not re.fullmatch(r"\+[1-9]\d{1,14}", normalized_phone):
        validation_errors["user_phone_number"] = "Must be E.164, e.g., +15551234567."

    if validation_errors:
        return {
            "ok": False,
            "status_code": 400,
            "url": endpoint,
            "request_payload": {
                "textJournal": normalized_text,
                "userPhoneNumber": normalized_phone,
            },
            "response": {
                "message": "Invalid input",
                "errors": validation_errors,
            },
        }

    payload: Dict[str, Any] = {
        "textJournal": normalized_text,
        "userPhoneNumber": normalized_phone,
    }

    timeout_seconds = float(os.environ.get("EMPATH_TIMEOUT", "15"))
    try:
        response = httpx.post(
            endpoint,
            json=payload,
            headers=headers,
            timeout=timeout_seconds,
        )

        content_type = response.headers.get("content-type", "")
        try:
            if "application/json" in content_type:
                response_data: Any = response.json()
            else:
                response_data = response.text
        except Exception:
            response_data = response.text

        return {
            "ok": response.is_success,
            "status_code": response.status_code,
            "url": endpoint,
            "request_payload": payload,
            "response": response_data,
        }
    except httpx.HTTPError as e:
        return {
            "ok": False,
            "error": str(e),
            "url": endpoint,
            "request_payload": payload,
        }

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    host = "0.0.0.0"
    
    print(f"Starting FastMCP server on {host}:{port}")
    
    mcp.run(
        transport="http",
        host=host,
        port=port,
        stateless_http=True
    )
