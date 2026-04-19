# Authentication

The Airbyte MCP server authenticates against the Airbyte Public API using short-lived access tokens obtained via client credentials.

## How It Works

```
┌────────────┐    client_id + secret    ┌──────────────┐
│ airbyte_mcp │ ───────────────────────> │ Airbyte API  │
│  (client)   │ <─────────────────────── │  /token       │
│             │    access_token (15min)  │              │
│             │                          │              │
│             │    Bearer <token>        │              │
│             │ ───────────────────────> │  /workspaces │
│             │ <─────────────────────── │  /sources    │
└────────────┘    JSON response          └──────────────┘
```

## Getting Your Credentials

### Self-Managed (abctl)

Run the following command to retrieve your `client-id` and `client-secret`:

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

### Airbyte Cloud

1. In the Airbyte UI, go to **User Settings > Applications**.
2. Click **Create an application**.
3. Copy the **client ID** and **client secret**.

## Token Exchange

The MCP server exchanges credentials automatically. Under the hood it calls:

```bash
curl --request POST \
     --url http://localhost:8000/api/public/v1/applications/token \
     --header 'content-type: application/json' \
     --data '{
       "client_id": "<YOUR_CLIENT_ID>",
       "client_secret": "<YOUR_CLIENT_SECRET>",
       "grant-type": "client_credentials"
     }'
```

Response:

```json
{
  "access_token": "<TOKEN>",
  "token_type": "Bearer",
  "expires_in": 900
}
```

Tokens expire after **15 minutes** (900 seconds). The MCP server caches the token in memory and refreshes it automatically ~30 seconds before expiry.

## Configuration

Set these in your `.env` file:

| Variable | Required | Description |
|---|---|---|
| `AIRBYTE_API_URL` | No | Defaults to `http://localhost:8000/api/public/v1` |
| `AIRBYTE_CLIENT_ID` | Yes* | From `abctl local credentials` or Airbyte UI |
| `AIRBYTE_CLIENT_SECRET` | Yes* | From `abctl local credentials` or Airbyte UI |
| `AIRBYTE_ACCESS_TOKEN` | No | If set, skips token exchange entirely |

*Not required if `AIRBYTE_ACCESS_TOKEN` is provided.

## Known Issues

- **Airbyte 1.8.x**: Some versions had a bug where the client ID was empty in the UI and token generation failed. This was resolved in Airbyte 2.0.0. If you encounter `Invalid client id or token` errors, upgrade to Airbyte >= 2.0.0.
- **401 handling**: The MCP server will automatically retry once on a `401 Unauthorized` response by requesting a fresh token.

## Testing Credentials

Use the provided script to verify your credentials work:

```bash
uv run python scripts/get_token.py
```
