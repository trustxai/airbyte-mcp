# Comparison vs the Official Airbyte MCPs

How this project (`airbyte-mcp`) compares to Airbyte's official MCP surfaces.
Positioning: **open-source / self-managed first** — a clean, predictable API
wrapper for people who run and manage their own Airbyte.

## The three official surfaces

Airbyte ships three distinct MCP products. Only one is a direct competitor.

| Surface | What it is | Endpoint / invocation | Relationship to us |
|---|---|---|---|
| **Agent MCP** | Hosted, remote-only agent platform with OAuth 2.1 and a Context Store. A *different product* — managed, multi-tenant. | `https://mcp.airbyte.ai/mcp` | Not a direct competitor; different category (managed remote). |
| **Knowledge MCP** | Docs Q&A over Airbyte's documentation. | `airbyte.mcp.kapa.ai` | Not a competitor; complementary docs helper. |
| **Replication MCP** | PyAirbyte-powered MCP that manages pipelines and can *run* connectors locally. | `uvx --from=airbyte@latest airbyte-mcp` | **Direct competitor** — the head-to-head below. |

## Head-to-head vs the Replication MCP

| Axis | This project (`airbyte-mcp`) | Official Replication MCP |
|---|---|---|
| **Architecture** | Thin FastMCP wrapper over the Airbyte REST Public API + internal Config API. ~35 focused tools. Tiny `httpx` footprint. | PyAirbyte-powered, ~50 tools. Actually runs connectors locally (pip/uv/Docker) and can extract into DuckDB. Heavier. |
| **Target environment** | Self-managed (abctl / OSS) is first-class, **and** Cloud. | Cloud-first; no supported self-managed path. |
| **Logs** | Richer **structured self-managed diagnostics** — failure reasons, per-stream stats, per-attempt structured entries (internal Config API) — **plus** a Cloud-only full-text parity tool. | One Cloud-only full-text tool (`get_cloud_sync_logs`). |
| **Auth** | OAuth client-credentials token exchange, or a static `AIRBYTE_ACCESS_TOKEN`. | Cloud client credentials + Google Secret Manager secret resolution; HTTP transport can use optional Keycloak OIDC. |
| **Transports** | stdio (local). No remote HTTP — run it next to your client. | stdio-oriented (Cloud-first), plus a hosted remote via Agent MCP. |
| **Runtime footprint** | No connector runtime — pure API calls; no absolute-path fragility. | Runs connectors locally; needs a connector runtime and local extract targets. |

## Where we're better

- **Self-managed is a first-class target.** abctl / OSS is the best-supported
  path, not an afterthought — the opposite of the Cloud-first Replication MCP.
- **Richer self-managed diagnostics.** Structured failure reasons, per-stream
  stats, and per-attempt entries via the internal Config API, which the official
  MCP does not surface for self-managed.
- **Predictable REST surface.** A thin, focused wrapper over the documented
  Public API — easy to reason about, easy to extend, small dependency footprint.
- **No connector-runtime fragility.** No local connector execution, no
  absolute-path/DuckDB setup to get wrong — just API calls.

## Where they're ahead

- **Cloud logs work today** via the mature PyAirbyte full-text path.
- **Secret handling by name.** The LLM only sees secret *names* (GSM resolution),
  not values.
- **Safe-mode / read-only gating** to restrict mutating operations.
- **Local extract-to-DuckDB** for quick local data pulls.
- **Connector registry / builder tools** — discovering and scaffolding
  connectors (PyAirbyte's niche).
- **Real hosted remote** via the managed, multi-tenant Agent MCP (OAuth 2.1).

## Verdict

The official Replication MCP is the broader, Cloud-first, connector-runtime
product; it wins on Cloud logs, secret-by-name safety, read-only gating, local
extraction, and connector tooling, and Airbyte's Agent MCP offers a genuinely
hosted multi-tenant remote.

For the job of **managing a self-managed Airbyte via a clean, predictable API**,
this project is **more usable** than the official Replication MCP: a small,
focused tool surface, first-class self-managed support, richer structured
diagnostics, and no connector-runtime fragility.
