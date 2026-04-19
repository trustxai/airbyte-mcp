# Project Scaffolding Reference

Complete templates for every file in the project skeleton.

## pyproject.toml

```toml
[project]
name = "{service}-mcp"
version = "0.1.0"
description = "MCP server for the {Service} API."
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
    "mcp[cli]>=1.1.0",
    "httpx>=0.27",
    "pydantic>=2.7",
    "pydantic-settings>=2.4",
    "python-dotenv>=1.0",
]

[project.scripts]
{service}-mcp      = "{service}_mcp.server:main_stdio"
{service}-mcp-http = "{service}_mcp.server:main_http"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/{service}_mcp"]

[dependency-groups]
dev = ["pre-commit>=4.0", "ruff>=0.11", "mypy>=1.14"]

[tool.ruff]
target-version = "py313"
line-length = 120

[tool.ruff.lint]
select = ["E", "W", "F", "I", "B", "C4", "UP"]
ignore = ["E501"]

[tool.ruff.lint.isort]
known-third-party = ["mcp", "pydantic", "httpx"]

[tool.mypy]
python_version = "3.13"
strict = true
warn_return_any = true
warn_unused_configs = true
```

## src/{service}_mcp/__init__.py

```python
"""MCP server for the {Service} API."""
__version__ = "0.1.0"
```

## src/{service}_mcp/__main__.py

```python
from {service}_mcp.server import main_stdio
main_stdio()
```

## src/{service}_mcp/server.py

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("{service}_mcp")

from {service}_mcp.tools import register_all
register_all(mcp)

def main_stdio() -> None:
    mcp.run()

def main_http() -> None:
    from {service}_mcp.config import get_settings
    s = get_settings()
    mcp.settings.host = s.http_host
    mcp.settings.port = s.http_port
    mcp.run(transport="streamable-http")

if __name__ == "__main__":
    main_stdio()
```

## src/{service}_mcp/config.py

```python
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore",
    )

    {service}_api_url: str = "https://api.example.com/v1"
    {service}_client_id: str = ""
    {service}_client_secret: str = ""
    {service}_access_token: str = ""
    http_host: str = "127.0.0.1"
    http_port: int = 8080

    @property
    def has_static_token(self) -> bool:
        return bool(self.{service}_access_token)

    @property
    def can_exchange_token(self) -> bool:
        return bool(self.{service}_client_id and self.{service}_client_secret)

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
```

## src/{service}_mcp/client.py

```python
import time
from typing import Any
import httpx
from {service}_mcp.config import get_settings

_TOKEN_SAFETY_MARGIN = 30

class {Service}Client:
    def __init__(self) -> None:
        self._token: str = ""
        self._expires_at: float = 0.0

    async def _ensure_token(self, client: httpx.AsyncClient) -> str:
        settings = get_settings()
        if settings.has_static_token:
            return settings.{service}_access_token
        if self._token and time.time() < self._expires_at:
            return self._token
        if not settings.can_exchange_token:
            raise RuntimeError(
                "No credentials configured. Set {SERVICE}_CLIENT_ID + "
                "{SERVICE}_CLIENT_SECRET, or provide {SERVICE}_ACCESS_TOKEN."
            )
        # Adapt this to the API's token endpoint
        resp = await client.post(
            f"{settings.{service}_api_url}/auth/token",
            json={
                "client_id": settings.{service}_client_id,
                "client_secret": settings.{service}_client_secret,
                "grant_type": "client_credentials",
            },
        )
        resp.raise_for_status()
        body = resp.json()
        self._token = body["access_token"]
        self._expires_at = time.time() + body.get("expires_in", 900) - _TOKEN_SAFETY_MARGIN
        return self._token

    async def request(
        self, method: str, path: str, *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        _retried: bool = False,
    ) -> httpx.Response:
        settings = get_settings()
        url = f"{settings.{service}_api_url}/{path.lstrip('/')}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            token = await self._ensure_token(client)
            headers = {
                "accept": "application/json",
                "authorization": f"Bearer {token}",
            }
            resp = await client.request(method, url, headers=headers, params=params, json=json_body)
            if resp.status_code == 401 and not _retried:
                self._token = ""
                self._expires_at = 0.0
                return await self.request(method, path, params=params, json_body=json_body, _retried=True)
            resp.raise_for_status()
            return resp

_client: {Service}Client | None = None

def get_client() -> {Service}Client:
    global _client
    if _client is None:
        _client = {Service}Client()
    return _client
```

## src/{service}_mcp/errors.py

```python
import httpx

def handle_api_error(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        detail = ""
        try:
            body = exc.response.json()
            detail = body.get("message", body.get("detail", ""))
        except Exception:
            detail = exc.response.text[:300]
        messages = {
            400: f"Bad request – the API rejected the input. {detail}",
            401: "Unauthorized – the access token is invalid or expired.",
            403: "Forbidden – you do not have permission for this resource.",
            404: "Not found – double-check the resource ID.",
            429: "Rate limited – wait a moment before retrying.",
        }
        return f"Error ({status}): {messages.get(status, f'API error. {detail}')}"
    if isinstance(exc, httpx.TimeoutException):
        return "Error: request timed out. Is the server running?"
    if isinstance(exc, httpx.ConnectError):
        return "Error: could not connect. Verify the API URL and that the server is running."
    return f"Error: unexpected failure – {type(exc).__name__}: {exc}"
```

## src/{service}_mcp/formatters.py

```python
import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

class ResponseFormat(StrEnum):
    MARKDOWN = "markdown"
    JSON = "json"

def to_json(data: Any) -> str:
    return json.dumps(data, indent=2, default=str)

def epoch_to_human(ts: int | float | None) -> str:
    if ts is None:
        return "N/A"
    return datetime.fromtimestamp(ts, tz=UTC).strftime("%Y-%m-%d %H:%M:%S UTC")

def paginated_response(
    *, items: list[dict[str, Any]], total: int | None = None,
    limit: int, offset: int, fmt: ResponseFormat,
    item_formatter: Any | None = None, title: str = "Results",
) -> str:
    count = len(items)
    has_more = (total is not None and total > offset + count) or count == limit
    if fmt == ResponseFormat.JSON:
        payload: dict[str, Any] = {
            "count": count, "offset": offset,
            "has_more": has_more, "data": items,
        }
        if total is not None:
            payload["total"] = total
        return to_json(payload)
    lines = [f"# {title}", ""]
    meta = [f"Showing **{count}** items (offset {offset})"]
    if total is not None:
        meta.append(f"total **{total}**")
    if has_more:
        meta.append(f"next offset → **{offset + count}**")
    lines.append(", ".join(meta))
    lines.append("")
    for item in items:
        if item_formatter:
            lines.append(item_formatter(item))
        else:
            for k, v in item.items():
                lines.append(f"- **{k}**: {v}")
            lines.append("")
    return "\n".join(lines)
```

## src/{service}_mcp/tools/__init__.py

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

def register_all(mcp: FastMCP) -> None:
    from {service}_mcp.tools import (
        health,
        {resource_a},
        {resource_b},
    )
```

## Tool file template — src/{service}_mcp/tools/{resource}.py

```python
from pydantic import BaseModel, ConfigDict, Field
from {service}_mcp.client import get_client
from {service}_mcp.errors import handle_api_error
from {service}_mcp.formatters import ResponseFormat, paginated_response, to_json
from {service}_mcp.server import mcp

class List{Resources}Input(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    limit: int = Field(default=20, ge=1, le=100, description="Max results to return.")
    offset: int = Field(default=0, ge=0, description="Pagination offset.")
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)

class Get{Resource}Input(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    {resource}_id: str = Field(..., min_length=1, description="UUID of the {resource}.")
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)

def _fmt_{resource}(item: dict) -> str:
    return (
        f"## {item.get('name', 'Unnamed')} (`{item.get('{resource}Id', '?')}`)\n"
        f"- **Type**: {item.get('{resource}Type', '?')}\n"
    )

@mcp.tool(
    name="{service}_list_{resources}",
    annotations={
        "readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": True,
    },
)
async def {service}_list_{resources}(params: List{Resources}Input) -> str:
    """<rich docstring — see rich-docstrings.md>"""
    try:
        client = get_client()
        resp = await client.request("GET", "/{resources}", params={
            "limit": params.limit, "offset": params.offset,
        })
        body = resp.json()
        return paginated_response(
            items=body.get("data", []),
            limit=params.limit, offset=params.offset,
            fmt=params.response_format,
            item_formatter=_fmt_{resource},
            title="{Service} {Resources}",
        )
    except Exception as exc:
        return handle_api_error(exc)

@mcp.tool(
    name="{service}_get_{resource}",
    annotations={
        "readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": True,
    },
)
async def {service}_get_{resource}(params: Get{Resource}Input) -> str:
    """<rich docstring — see rich-docstrings.md>"""
    try:
        client = get_client()
        resp = await client.request("GET", f"/{resources}/{params.{resource}_id}")
        data = resp.json()
        if params.response_format == ResponseFormat.JSON:
            return to_json(data)
        return _fmt_{resource}(data)
    except Exception as exc:
        return handle_api_error(exc)
```

## .env.example

```ini
{SERVICE}_API_URL=https://api.example.com/v1
{SERVICE}_CLIENT_ID=
{SERVICE}_CLIENT_SECRET=
# {SERVICE}_ACCESS_TOKEN=
# HTTP_HOST=127.0.0.1
# HTTP_PORT=8080
```

## .gitignore additions

```
.env
.venv/
__pycache__/
*.pyc
.mypy_cache/
.ruff_cache/
dist/
*.egg-info/
.DS_Store
Thumbs.db
```
