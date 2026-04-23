---
title: "FAQ: Security"
---

# Security FAQ

## Is my data private?

Yes. All data stays on your local network. No telemetry or data is sent externally. Models run locally via Ollama.

## How is authentication handled?

Memex uses JWT profiles managed through SPIRE for service-to-service authentication. The Hive UI currently operates on the local network without user authentication (it's designed for trusted, private networks).

## What is SPIRE?

SPIRE (SPIFFE Runtime Environment) provides cryptographic identity to each service. It issues short-lived X.509 certificates (SVIDs) that services use to authenticate with each other over mTLS.

See [Security Model](../architecture/security-model.md).

## How are secrets managed?

Secrets are stored in `network.env` and injected as environment variables. For production hardening:

- Use Docker secrets instead of environment variables
- Rotate credentials regularly
- See [Secrets Management](../admin-guide/operations/secrets.md)

## Can I expose it to the internet?

This is **not recommended** without additional security measures:

- Add proper user authentication (OAuth2/OIDC)
- Enable TLS on all endpoints
- Set up firewall rules
- Implement rate limiting
- Regular security updates

## Is the Verifier a safety filter?

Yes. The MarsRL verifier ({{ verifier_model }}) checks every response for safety, quality, and policy compliance before sending it to the user. Responses that fail verification are regenerated.

## What about prompt injection?

The system uses several defenses:

- System prompts are protected from overwrite
- The Verifier checks for suspicious outputs
- Tool execution is sandboxed
- File operations are scoped to the workspace directory


