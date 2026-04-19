# Contributing to airbyte-mcp

Thank you for your interest in contributing! This document explains how to set up a local development environment and submit changes.

## Prerequisites

- **Python 3.13+**
- **[uv](https://docs.astral.sh/uv/)** package manager
- A running **Airbyte** instance (local via [abctl](https://docs.airbyte.com/platform/deploying-airbyte/abctl/) or Cloud)

## Getting Started

```bash
# 1. Fork and clone the repository
git clone https://github.com/<your-username>/airbyte-mcp.git
cd airbyte-mcp

# 2. Install dependencies
uv sync

# 3. Copy and fill in credentials
cp .env.example .env
# Edit .env with your Airbyte client_id and client_secret

# 4. Verify the server starts
uv run airbyte-mcp  # stdio mode — Ctrl-C to stop
```

## Development Workflow

### Running the MCP Inspector

The MCP Inspector provides an interactive UI for testing your tools:

```bash
uv run mcp dev src/airbyte_mcp/server.py
```

### Running Scripts

Smoke-test scripts live in `scripts/`. See [scripts/README.md](../scripts/README.md) for details.

```bash
uv run python scripts/get_token.py         # Verify credentials
uv run python scripts/list_workspaces.py    # Direct API call
uv run python scripts/mcp_stdio_smoke.py    # Full end-to-end
```

### Code Style

- Follow existing patterns in the codebase.
- Use type hints for all function signatures.
- Use Pydantic `BaseModel` for all tool input models.
- Each tool needs comprehensive docstrings (see existing tools for examples).

## Submitting Changes

### Branch Naming

Use descriptive branch names:

```
feat/add-streams-tool
fix/token-refresh-race
docs/update-endpoints-checklist
```

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add airbyte_get_stream_properties tool
fix: handle 401 during token exchange retry
docs: update endpoints checklist with streams
chore: bump mcp sdk to 1.28
```

### Pull Request Checklist

Before submitting a PR, verify:

- [ ] `uv sync` completes without errors
- [ ] `uv run python -c "from airbyte_mcp.server import mcp"` imports successfully
- [ ] New tools have Pydantic input models, docstrings, and proper annotations
- [ ] `docs/endpoints.md` is updated if you added new tool coverage
- [ ] No secrets or `.env` values are committed

### Pull Request Process

1. Create a feature branch from `main`.
2. Make your changes with clear, focused commits.
3. Open a pull request against `main`.
4. Fill in the PR description with a summary and test plan.
5. Address reviewer feedback.

## Adding a New Tool

1. Create or edit the appropriate file in `src/airbyte_mcp/tools/`.
2. Define a Pydantic `BaseModel` for input validation.
3. Register the tool with `@mcp.tool(name="airbyte_...", annotations={...})`.
4. Add markdown + JSON formatting in your tool function.
5. Import the module in `src/airbyte_mcp/tools/__init__.py` if it is new.
6. Update `docs/endpoints.md` to mark the endpoint as implemented.
7. Test with the MCP Inspector.

## Questions?

Open an issue if you have questions about contributing. We're happy to help!
