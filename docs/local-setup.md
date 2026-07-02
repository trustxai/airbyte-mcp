# Local Setup with abctl

This guide walks through setting up a local Airbyte instance using `abctl` and connecting the MCP server to it.

## Prerequisites

- Docker Desktop running
- `abctl` installed ([installation guide](https://docs.airbyte.com/platform/deploying-airbyte/abctl/))

## 1. Install Airbyte

```bash
abctl local install
```

This may take up to 30 minutes on first run. When complete, Airbyte is accessible at `http://localhost:8000`.

## 2. Verify Airbyte Is Running

```bash
abctl local status
```

Expected output:

```
Existing cluster 'airbyte-abctl' found
Found helm chart 'airbyte-abctl'
  Status: deployed
  ...
Airbyte should be accessible via http://localhost:8000
```

You can also confirm the API is reachable:

```bash
curl -s http://localhost:8000/api/public/v1/health
```

## 3. Retrieve Credentials

```bash
abctl local credentials
```

Output:

```json
{
  "email": "user@example.com",
  "password": "...",
  "client-id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "client-secret": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
}
```

Copy the `client-id` and `client-secret` values.

## 4. Configure the MCP Server

```bash
cp .env.example .env
```

Edit `.env`:

```
AIRBYTE_API_URL=http://localhost:8000/api/public/v1
AIRBYTE_CLIENT_ID=<paste client-id here>
AIRBYTE_CLIENT_SECRET=<paste client-secret here>
```

## 5. Test Connectivity

```bash
# Verify credentials work
uv run python scripts/get_token.py

# Verify API access
uv run python scripts/list_workspaces.py
```

## 6. Start the MCP Server

```bash
uv run airbyte-mcp
```

## Troubleshooting

### "Invalid client id or token"

- Ensure you are running Airbyte >= 2.0.0 (versions 1.8.x had a known bug with client credentials).
- Re-run `abctl local credentials` and update your `.env`.

### "Could not connect to Airbyte API"

- Verify Airbyte is running: `abctl local status`
- Verify the URL: `curl http://localhost:8000/api/public/v1/health`
- Check that `AIRBYTE_API_URL` in `.env` matches your Airbyte instance.

### Port conflicts

If port 8000 is in use by another service, you can install Airbyte on a different port:

```bash
abctl local install --port 8001
```

Then update `AIRBYTE_API_URL=http://localhost:8001/api/public/v1` in your `.env`.
