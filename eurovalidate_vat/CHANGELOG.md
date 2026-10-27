# Changelog

## 18.0.1.0.0 — 2026-10-27

First release.

- Validate partner VAT numbers through EuroValidate on create/write, on change and on demand.
- Autofill of registered name and address (empty fields only).
- Status, confidence, source, request id and timestamp stored on the partner.
- Optional blocking of invalid numbers; outages and quota never block a save.
- Weekly re-validation cron (inactive by default).
