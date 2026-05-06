# ADR 004: OS Keyring for Credential Storage

## Status

Accepted

## Context

GenericAgent v0.6.0 stored API keys as plaintext Python variables in
`mykey.py`, a file that lives in the project root.  This had several
critical shortcomings:

1. **Secrets in source code.**  `mykey.py` is typically checked into
   version control or shared between machines.  API keys — which grant
   access to paid LLM services — were sitting in plain text, easily
   leaked through git pushes, screenshots, or log output.

2. **No OS-level protection.**  On macOS the keychain encrypts secrets
   at rest; on Windows the Credential Manager does the same.  A plain
   Python file has none of these protections — any process running as
   the user can read it.

3. **Key rotation was manual.**  Changing a key meant editing the Python
   file, reloading the module, and hoping no cached reference still held
   the old value.  There was no single source of truth.

4. **Fallback was insecure.**  When the keyring was unavailable (headless
   Linux without a secret service), the only alternative was to leave
   the key in `mykey.py` — the same insecure default.

The security audit (Phase 0, task 0.4.1) identified this as a P0
vulnerability and mandated OS keyring integration.

## Decision

We use the `keyring` Python library as the **primary** credential store:

| Platform | Backend | Encryption at rest |
|----------|---------|--------------------|
| macOS | Keychain | AES-256 (hardware-backed on T2/M1+) |
| Windows | Credential Manager | DPAPI (user-profile scoped) |
| Linux | Secret Service (GNOME Keyring / KDE Wallet) | AES-256 (if available) |

### Storage strategy

1. **Primary**: `keyring.get_password("GenericAgent", provider_name)` /
   `keyring.set_password("GenericAgent", provider_name, api_key)`.

2. **Fallback**: If `keyring` is not available (e.g. headless Linux
   without D-Bus secret service), keys are stored in `mykey.enc` — a
   Fernet-encrypted file.  The encryption key is derived from a
   user-supplied password via PBKDF2-SHA256 (600 000 iterations).
   File permissions are set to `0o600`.

3. **Legacy**: `mykey.py` continues to work for **non-sensitive**
   configuration (model names, base URLs, temperature) but API keys
   read from it are migrated to the keyring on first load.

### Key lookup priority

```
1. OS keyring (per-provider)
2. Encrypted fallback file (mykey.enc)
3. Environment variables (GA_API_KEY_*)
4. Legacy mykey.py (with migration prompt)
```

## Consequences

### Positive

- **Secrets are never in source code.**  Even if `mykey.py` is
  accidentally committed, it contains no API keys.
- **OS-level encryption at rest.**  On most platforms the keys are
  protected by the operating system's credential store.
- **Single source of truth.**  `keyring.get_password()` is the canonical
  way to retrieve a key; all modules go through the same path.
- **Migration path.**  Existing `mykey.py` files continue to work;
  keys are automatically migrated to the keyring when first detected.
- **Cross-platform.**  The `keyring` library abstracts over macOS,
  Windows, and Linux backends.

### Negative

- **New dependency.**  `keyring>=25.0.0` must be installed.  On
  headless Linux without D-Bus, the encrypted file fallback is used
  instead, requiring `cryptography>=42.0.0`.
- **Headless friction.**  On headless Linux the user may need to
  unlock the keyring or provide a password for the encrypted fallback.
- **Keyring backend variability.**  Different Linux distributions have
  different secret service implementations; some may not encrypt at
  rest.  The encrypted fallback mitigates this.
- **Testing complexity.**  Tests must mock `keyring` or use the
  `keyring.backends.fail.Keyring` backend to avoid interacting with
  the real OS keychain.

### Risks

- Keyring corruption: if the OS keychain becomes corrupted, the user
  must re-enter all API keys.  Mitigated by the encrypted file fallback
  and the environment variable override.
- Supply chain: the `keyring` package itself could be compromised.
  Mitigated by pinning the version and auditing the dependency.
