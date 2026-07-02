# Airbyte API Endpoint Checklist

Complete list of Airbyte Public API endpoints grouped by resource.
Implemented endpoints are marked `[x]`, pending ones `[ ]`.

## Health

- [x] `GET /health` — Health check

## Workspaces (6 endpoints)

- [x] `GET /workspaces` — List workspaces
- [x] `GET /workspaces/{workspaceId}` — Get workspace
- [ ] `POST /workspaces` — Create workspace
- [ ] `PATCH /workspaces/{workspaceId}` — Update workspace
- [ ] `DELETE /workspaces/{workspaceId}` — Delete workspace
- [ ] `PUT /workspaces/{workspaceId}/oauthCredentials` — Set OAuth credentials

## Sources (7 endpoints)

- [x] `GET /sources` — List sources
- [x] `GET /sources/{sourceId}` — Get source
- [x] `POST /sources` — Create source
- [x] `PATCH /sources/{sourceId}` — Update source
- [ ] `PUT /sources/{sourceId}` — Replace source
- [ ] `DELETE /sources/{sourceId}` — Delete source
- [ ] `POST /sources/{sourceId}/checkConnection` — Check source connection

## Destinations (6 endpoints)

- [x] `GET /destinations` — List destinations
- [x] `GET /destinations/{destinationId}` — Get destination
- [x] `POST /destinations` — Create destination
- [x] `PATCH /destinations/{destinationId}` — Update destination
- [ ] `PUT /destinations/{destinationId}` — Replace destination
- [ ] `DELETE /destinations/{destinationId}` — Delete destination

## Connections (5 endpoints)

- [x] `GET /connections` — List connections
- [x] `GET /connections/{connectionId}` — Get connection
- [x] `POST /connections` — Create connection
- [x] `PATCH /connections/{connectionId}` — Update connection
- [ ] `DELETE /connections/{connectionId}` — Delete connection

## Jobs (4 endpoints)

- [x] `GET /jobs` — List jobs
- [x] `GET /jobs/{jobId}` — Get job
- [x] `POST /jobs` — Trigger sync or reset job
- [x] `DELETE /jobs/{jobId}` — Cancel job

## Streams (1 endpoint)

- [x] `GET /streams` — Get stream properties for a source/destination pair

## Permissions (5 endpoints)

- [ ] `GET /permissions` — List permissions
- [ ] `GET /permissions/{permissionId}` — Get permission
- [ ] `POST /permissions` — Create permission
- [ ] `PATCH /permissions/{permissionId}` — Update permission
- [ ] `DELETE /permissions/{permissionId}` — Delete permission

## Users (1 endpoint)

- [ ] `GET /users` — List users within an organization

## Organizations (1 endpoint)

- [ ] `GET /organizations` — List organizations

## Tags (4 endpoints)

- [x] `GET /tags` — List tags
- [x] `POST /tags` — Create tag
- [x] `PATCH /tags/{tagId}` — Update tag
- [x] `DELETE /tags/{tagId}` — Delete tag

## Source Definitions (custom connectors)

- [x] `GET /workspaces/{workspaceId}/definitions/sources` — List source definitions
- [ ] `POST /workspaces/{workspaceId}/definitions/sources` — Create source definition
- [x] `GET /workspaces/{workspaceId}/definitions/sources/{definitionId}` — Get source definition
- [ ] `PUT /workspaces/{workspaceId}/definitions/sources/{definitionId}` — Update source definition
- [ ] `DELETE /workspaces/{workspaceId}/definitions/sources/{definitionId}` — Delete source definition

## Destination Definitions (custom connectors)

- [x] `GET /workspaces/{workspaceId}/definitions/destinations` — List destination definitions
- [ ] `POST /workspaces/{workspaceId}/definitions/destinations` — Create destination definition
- [x] `GET /workspaces/{workspaceId}/definitions/destinations/{definitionId}` — Get destination definition
- [ ] `PUT /workspaces/{workspaceId}/definitions/destinations/{definitionId}` — Update destination definition
- [ ] `DELETE /workspaces/{workspaceId}/definitions/destinations/{definitionId}` — Delete destination definition

## Declarative Sources (YAML, custom connectors)

- [ ] `GET /workspaces/{workspaceId}/definitions/declarative_sources` — List YAML source definitions
- [ ] `POST /workspaces/{workspaceId}/definitions/declarative_sources` — Create YAML source definition
- [ ] `GET /workspaces/{workspaceId}/definitions/declarative_sources/{definitionId}` — Get YAML source definition
- [ ] `PUT /workspaces/{workspaceId}/definitions/declarative_sources/{definitionId}` — Update YAML source definition
- [ ] `DELETE /workspaces/{workspaceId}/definitions/declarative_sources/{definitionId}` — Delete YAML source definition

## Internal Configuration API (self-managed only)

- [x] `POST /api/v1/jobs/get` — Get job details with attempt stats and failure summaries
- [x] `POST /api/v1/jobs/get_debug_info` — Get job debug info with full logs
- [x] `POST /api/v1/jobs/list` — List ALL job types (sync, reset, refresh, clear, etc.)
- [x] `POST /api/v1/attempt/get_for_job` — Get attempt logs for a specific attempt
- [x] Cloud Config API `POST /jobs/get` — Full-text sync logs via `airbyte_get_cloud_sync_logs` (Cloud only)
- [x] `POST /api/v1/connections/refresh` — Trigger a per-stream refresh
- [x] `POST /api/v1/connections/clear` — Clear destination data for streams

---

**Summary**: 36 / ~50+ endpoints implemented (read + write for core resources, internal API for logs, refresh, and clear, Cloud full-text logs).
