#!/usr/bin/env python3
import os
import re
from typing import Optional, Dict, Any
import httpx
from fastmcp import FastMCP

mcp = FastMCP("Sample MCP Server")

@mcp.tool(description="Greet a user by name with a welcome message from the MCP server")
def greet(name: str) -> str:
    """Return a friendly greeting.

    Parameters:
    - name: The user's display name.

    Returns:
    - A short greeting string.
    """
    return f"Hello, {name}! Welcome to our Empath MCP server running on Render!"

@mcp.tool(description="Get information about the MCP server including name, version, environment, and Python version")
def get_server_info() -> dict:
    """Return basic server info for diagnostics.

    Returns a dictionary with:
    - server_name: Human-readable name of this server
    - version: Semantic version string
    - environment: Deployment environment (from ENVIRONMENT)
    - python_version: Active Python version
    """
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
    """Create a text journal entry via Empath API.

    Parameters:
    - text_journal: Freeform journal text (non-empty after trimming)
    - user_phone_number: E.164 phone (e.g., +15551234567)

    Validation performed client-side:
    - text_journal must be non-empty after trim
    - user_phone_number must match E.164 ("+" then 2–15 digits, first 1–9)

    Returns a structured object with fields:
    - ok (bool): whether the call succeeded
    - status_code (int): HTTP-like status code
    - url (str): target endpoint
    - request_payload (dict): payload sent or would be sent
    - response (dict|str): Empath JSON or text; on validation error, includes
      { message: "Invalid input", errors: { field: reason } }
    """
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

@mcp.tool(description="Describe available tools, parameters, validation rules, and examples")
def get_empath_tools_help() -> Dict[str, Any]:
    """Return a structured description of this server's tools and usage.

    Useful for LLMs and UI clients to understand parameter names, constraints,
    and example payloads without guessing.
    """
    base_url = os.environ.get("EMPATH_BASE_URL", "https://app.empathdash.com").rstrip("/")
    return {
        "server": {
            "name": "Empath MCP Server",
            "version": "1.0.0",
            "base_url": base_url,
        },
        "tools": [
            {
                "name": "create_empath_journal_entry",
                "description": "Create a text journal entry in Empath",
                "endpoint": f"{base_url}/api/journals/createTextEntryOrRegister",
                "method": "POST",
                "parameters": [
                    {
                        "name": "text_journal",
                        "type": "string",
                        "required": True,
                        "validation": "non-empty after trim",
                        "maps_to": "textJournal",
                        "example": "Had a productive day shipping the MCP tool.",
                    },
                    {
                        "name": "user_phone_number",
                        "type": "string",
                        "required": True,
                        "validation": "E.164 format: +15551234567",
                        "maps_to": "userPhoneNumber",
                        "example": "+15551234567",
                    },
                ],
                "example_request": {
                    "text_journal": "Had a productive day shipping the MCP tool.",
                    "user_phone_number": "+15551234567",
                },
                "example_payload_to_empath": {
                    "textJournal": "Had a productive day shipping the MCP tool.",
                    "userPhoneNumber": "+15551234567",
                },
                "success_response_shape": {
                    "message": "Text entry created",
                    "journalId": "string",
                    "newUser": "boolean",
                    "subscriptionStatus": "string",
                    "callsRemaining": "number",
                    "mentions": "array",
                },
                "error_responses": {
                    "400": {"message": "Invalid phone number format"},
                    "402": {
                        "message": "Free limit reached",
                        "subscriptionStatus": "free",
                        "limitReached": True,
                        "callsRemaining": 0,
                    },
                    "404": {"message": "Client not found"},
                    "500": {"message": "Error creating text entry", "error": "string"},
                },
            }
        ],
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
