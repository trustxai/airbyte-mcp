# Security Policy

## Supported Versions

| Version | Supported |
| ------- | --------- |
| 0.1.x   | Yes       |

## Reporting a Vulnerability

If you discover a security vulnerability in this project, please report it responsibly.

**Do NOT open a public GitHub issue for security vulnerabilities.**

Instead:

1. **GitHub Security Advisory** (preferred): Go to the repository's "Security" tab and click "Report a vulnerability" to create a private advisory.
2. **Email**: Send details to the repository maintainers via the contact information on their GitHub profiles.

### What to include

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

### What to expect

- **Acknowledgment** within 48 hours of your report.
- **Status update** within 7 days with our assessment and planned fix timeline.
- **Credit** in the release notes (unless you prefer to remain anonymous).

## Security Best Practices for Users

- **Never commit `.env` files** or expose `AIRBYTE_CLIENT_ID`, `AIRBYTE_CLIENT_SECRET`, or `AIRBYTE_ACCESS_TOKEN` in issues, logs, or public repositories.
- **Rotate credentials** if you suspect they have been compromised.
- **Use environment variables** or a secrets manager rather than hardcoded values.
