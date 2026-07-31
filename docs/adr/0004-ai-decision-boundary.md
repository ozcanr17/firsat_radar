# ADR 0004: AI decision boundary

## Status

Accepted on 2026-07-31.

## Context

Review clustering and commercial briefing can benefit from language models, but a model can invent demand, margin, regulation, or product facts. PazarRadar must remain useful without credentials and must not turn marketplace text into executable instructions.

## Decision

- Deterministic source evidence, freshness, scoring, and unit economics remain the authority.
- A future model adapter may cluster pain themes, summarize evidence, propose search terms, and draft validation questions.
- Model output must use a versioned structured schema and cite persisted evidence identifiers.
- Missing evidence stays missing; the model cannot fill numeric fields or change a GO/NO-GO result.
- Marketplace content is untrusted data and never receives instruction priority.
- Raw reviewer identity, direct contact data, secrets, cost notes, and credentials are excluded from model input.
- Model output is cached by evidence hash and model version, can be reproduced, and is visibly labeled as model-assisted.
- The application remains fully functional when AI is disabled or unavailable.

## Consequences

The current release improves deterministic review clustering and commercial decisions without adding a nonfunctional credential dependency. Model-assisted briefs can be added after API credentials and current official API documentation are available, without changing the core decision contract.
