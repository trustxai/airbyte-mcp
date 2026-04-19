# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-04-19

### Added

- FastMCP-based MCP server for the Airbyte Public API.
- Two transport entry points: `airbyte-mcp` (stdio) and `airbyte-mcp-http` (streamable HTTP).
- Automatic token exchange with in-memory caching and 401 retry.
- 11 read-only tools:
  - `airbyte_health_check`
  - `airbyte_list_workspaces` / `airbyte_get_workspace`
  - `airbyte_list_sources` / `airbyte_get_source`
  - `airbyte_list_destinations` / `airbyte_get_destination`
  - `airbyte_list_connections` / `airbyte_get_connection`
  - `airbyte_list_jobs` / `airbyte_get_job`
- Markdown and JSON response formats for all tools.
- Pagination support (limit/offset) on all list tools.
- Dockerfile for stdio transport.
- Dockerfile.http scaffolded for future HTTP deployment.
- CLI test scripts (`scripts/`).
- Documentation: endpoints checklist, authentication guide, architecture diagram, local setup guide.
- CONTRIBUTING.md, SECURITY.md, CHANGELOG.md.
