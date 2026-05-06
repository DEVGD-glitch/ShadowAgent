# ADR-007: Disable no_code_injection and no_pii_leak Input Guardrails by Default

**Date:** 2026-05-04
**Status:** Accepted
**Impact:** Security, UX

## Context

The `GuardrailManager.setup_defaults()` method registered three input guardrails:
`no_code_injection`, `no_pii_leak`, and `max_length`. After real-world testing,
the first two produce unacceptable false-positive rates:

### `no_code_injection`
- The regex `r"`[^`]*`"` blocks **any** text in backticks — including legitimate
  markdown formatting and command examples like "exécute `python script.py`".
- Users who write markdown in their queries are systematically blocked.
- The pattern cannot distinguish between code injection attempts and normal
  markdown usage without significantly more sophisticated parsing.

### `no_pii_leak`
- The email regex `[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}` blocks
  any input containing an email address — including legitimate requests like
  "envoie un email à sarah@company.com" or "configure mon SMTP sur admin@example.com".
- This makes the agent unusable for email-related tasks.

### `factuality_check` (output guardrail)
- Blocks responses containing 3+ expressions of uncertainty. This censors
  honest, appropriate responses when the agent lacks information.
- Not enabled in `setup_defaults()`, but documented as problematic for future use.

## Decision

1. **Disable** `no_code_injection` and `no_pii_leak` in `setup_defaults()`.
2. **Keep** `max_length` (50K chars) — safe, no false positives.
3. **Keep** output guardrails `no_harmful_content` and `no_pii_exposure` —
   these are less prone to false positives since they validate agent output,
   not user input.
4. Users can **opt-in** to the stricter guardrails by calling
   `add_input_guardrail()` explicitly after testing on their workload.
5. `factuality_check` remains **not registered by default** and should be
   removed or completely redesigned before activation.

## Consequences

- **Positive:** Users can send emails, use markdown, and configure the agent
  without being blocked by false positives.
- **Negative:** The agent no longer filters code injection or PII in user
  input by default. The LLM provider's own safety filters remain active.
- **Mitigation:** Output PII exposure is still checked. Input guardrails can
  be re-enabled per-deployment after testing.
