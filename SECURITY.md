# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 0.8.x   | :white_check_mark: |
| < 0.8   | :x:                |

## Reporting a Vulnerability

Report security vulnerabilities to **elderreimondpena@gmail.com**.

Do not open public issues for verified or suspected security vulnerabilities.

Response timeline:
- Acknowledgment within 72 hours
- Fix target within 14 days for critical issues
- Disclosure coordinated after patch release

## Scope

RecoverX is a forensic file recovery and carving tool. It operates on disk images
and block devices provided by the user. The tool itself does not transmit data
over a network. Security concerns are primarily related to:
- Maliciously crafted disk images that could trigger unexpected code paths
- Command injection via file paths or device names
- Resource exhaustion from pathological inputs

## Best Practices

- Always scan disk images from trusted sources
- Run with minimal required privileges
- Validate inputs when using programmatic APIs
