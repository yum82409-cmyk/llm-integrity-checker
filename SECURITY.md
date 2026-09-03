# Security Policy

## Scope

This project is designed for local inspection of third-party LLM API
channels. The checker binds to `127.0.0.1` and should not be exposed to a
LAN, reverse proxy, or public interface without an independent security
review.

## Secret handling

- Never commit `.env`, API keys, access tokens, or request captures.
- Enter API keys only in the local browser form when running a test.
- The integration does not write API keys to source files or static config.
- Do not enable verbose HTTP logging around requests containing credentials.
- Revoke a key immediately if it was pasted into an unintended destination.

## Reporting

For a suspected security issue, do not open a public issue with credentials
or exploit details. Contact the repository maintainers privately and include
the affected version, reproduction steps, and a minimal redacted example.
