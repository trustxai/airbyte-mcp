# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.0](https://github.com/trustxai/airbyte-mcp/compare/v0.3.0...v0.4.0) (2026-07-02)


### Features

* harden log reads, add cloud log tool, and standardize distribution ([81d9701](https://github.com/trustxai/airbyte-mcp/commit/81d9701915b9aa220de4ef63cb6a0fed369a2c48))
* harden log reads, add cloud log tool, and standardize distribution ([05c5ff4](https://github.com/trustxai/airbyte-mcp/commit/05c5ff4153f1869b9bcc13d20f5a91bb2ded2e36))

## [0.3.0](https://github.com/trustxai/airbyte-mcp/compare/v0.2.2...v0.3.0) (2026-07-02)


### Features

* add refresh job tools (trigger + list) via internal API ([2bd29be](https://github.com/trustxai/airbyte-mcp/commit/2bd29be8e4942526c3579a6e678c9979f5381f11))
* add refresh/clear/wait job tools with pytest suite ([d7b3d2a](https://github.com/trustxai/airbyte-mcp/commit/d7b3d2afbc0c35984fa74ab5501984402e050c70))
* refresh/clear/wait job tools and pytest suite ([6d215b4](https://github.com/trustxai/airbyte-mcp/commit/6d215b4098f4460d3482bbf7881d240555d137ed))

## [0.2.2](https://github.com/trustxai/airbyte-mcp/compare/v0.2.1...v0.2.2) (2026-04-20)


### Bug Fixes

* remove deprecated enhanced-mcp-builder and mcp-builder skills ([635c180](https://github.com/trustxai/airbyte-mcp/commit/635c180cfb89f39b3f05924f4cc69b552c2c33b8))

## [0.2.1](https://github.com/trustxai/airbyte-mcp/compare/v0.2.0...v0.2.1) (2026-04-19)


### Bug Fixes

* enhance README and architecture documentation, add job log utilities, and improve log handling ([75b608b](https://github.com/trustxai/airbyte-mcp/commit/75b608bb82e9ca00818b6860ace76e611a182ad1))

## [0.2.0](https://github.com/trustxai/airbyte-mcp/compare/v0.1.1...v0.2.0) (2026-04-19)


### Features

* expand MCP server with CRUD, job logs, tags, streams, and definitions ([7b58e87](https://github.com/trustxai/airbyte-mcp/commit/7b58e875e60645f6a0c3fdb50bd22238b019458e))
* expand MCP server with CRUD, job logs, tags, streams, and definitions ([908c272](https://github.com/trustxai/airbyte-mcp/commit/908c2728893628c86231169191445e34bb9fd53a))


### Bug Fixes

* handle list-type logs in job log tools to prevent AttributeError ([9514f1e](https://github.com/trustxai/airbyte-mcp/commit/9514f1efd51784f34f485488d840fd9a3113bf9e))

## [0.1.1](https://github.com/trustxai/airbyte-mcp/compare/v0.1.0...v0.1.1) (2026-04-19)


### Bug Fixes

* chain publish job in release-please workflow ([c8d050d](https://github.com/trustxai/airbyte-mcp/commit/c8d050d230875f5a6235cafb3a529ba06f0dc24a))

## 0.1.0 (2026-04-19)


### Features

* initial project configuration and CI/CD setup for Airbyte MCP server ([80e3e98](https://github.com/trustxai/airbyte-mcp/commit/80e3e987736128dd4173528de8dce312407e6081))

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
