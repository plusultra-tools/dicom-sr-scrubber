# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes       |

## Reporting a vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Send a private report to: plusultra.dev@proton.me (or open a
[GitHub Security Advisory](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing/privately-reporting-a-security-vulnerability)
if the repository is public).

Include:
- A description of the vulnerability and its potential impact.
- Steps to reproduce (minimal reproducer preferred).
- Any known mitigations.

We aim to acknowledge receipt within 48 hours and provide an initial
assessment within 7 days.

## PHI handling disclosure

`dicom-sr-scrubber` processes files that may contain Protected Health Information
(PHI). The library:

- Never transmits data over a network (file-in, file-out only).
- Never persists PHI to disk beyond what the caller explicitly writes.
- Uses SHA-256 for UID/name hashing — the hash is one-way but the per-run salt
  defaults to a static string. **Set `--uid-salt` to a secret per-project value
  to prevent cross-run re-linkage.**
- Does not guarantee complete de-identification on its own; it must be combined
  with a top-level DICOM tag scrubber (e.g. `dcm-anon`) for full anonymisation.

## Threat model

`dicom-sr-scrubber` defends against:
- Inadvertent PHI leakage in SR content items overlooked by generic DICOM
  anonymisers that do not parse the SR content tree.
- Accidental inclusion of SR objects in research exports that should be
  de-identified.

It does NOT defend against:
- Adversarial free-text PHI obfuscation (a name spelled phonetically).
- PHI in pixel data (out of scope; use a pixel-scrubbing tool).
- Deliberate re-identification by a motivated adversary with access to
  auxiliary data.
