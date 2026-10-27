# EuroValidate VAT Validation for Odoo

Validate EU and UK VAT numbers on partners through the [EuroValidate](https://eurovalidate.com) API
and pre-fill the registered company name and address — including while VIES is down.

| | Odoo built-in `base_vat` | This module |
|---|---|---|
| Checks the number against the register | VIES, when reachable | EuroValidate → VIES/HMRC/Brønnøysund/UID/ABR |
| When VIES times out | silently falls back to a checksum, field turns green | last known answer with `confidence: medium`, or `unavailable` (never a false "valid") |
| Name and address | not filled | filled when empty, stored as evidence |
| Audit trail | none | `request_id`, `source`, `last_verified` on the partner |
| Coverage | EU | EU, UK (paid plans), NO, CH, AU + format checks for CL/TR/IL/MX/CA/PH |

## Requirements

* Odoo **17.0** or **18.0** (Community or Enterprise), **Odoo.sh or on-premise**.
  Odoo Online (SaaS) does not install third-party Python modules.
* Python package `requests` (already present in a standard Odoo install).
* A EuroValidate API key — free tier: 100 validations/month, no card:
  <https://eurovalidate.com/v1/auth/signup?utm_source=odoo&utm_medium=module&utm_campaign=readme>

## Install

1. Copy `eurovalidate_vat` into your addons path (or add this repository to Odoo.sh).
2. Update the apps list and install **EuroValidate VAT Validation**.
3. Settings → General Settings → **EuroValidate**: paste the API key, keep *Autofill* on.
   Optionally enable *Block invalid numbers*.

That's it. From now on, saving a partner with a VAT number validates it; the
**Validate with EuroValidate** button next to the VAT field re-checks on demand,
and the *EuroValidate* tab shows status, confidence and the registered details.

## Behaviour

| Answer | Effect |
|---|---|
| `valid` | status + confidence stored; empty name/street/zip/city/country filled |
| `invalid` (confidence high/medium) | warning on the form; save refused only if *Block invalid* is on |
| `unavailable` (register down) | partner saved, status `unavailable` — re-validate later (or let the weekly cron do it) |
| `unverified` | format/checksum only (countries without a public register) |
| quota reached (HTTP 429) | one warning with the upgrade link, then silent for 10 minutes; saves go through |
| network error | partner saved, status `unavailable`, nothing blocks |

Germany and Spain never return name/address through VIES (national law); the
number is still validated.

## Weekly re-validation

A scheduled action **EuroValidate: re-validate partner VAT numbers** is shipped
*inactive*. Enable it under Settings → Technical → Scheduled Actions when your
plan's quota covers your partner count (200 partners per run, oldest first; stops
on quota).

## Security and data

* The API key lives in `ir.config_parameter` (`eurovalidate.api_key`) and is
  readable by Settings administrators. Use a dedicated key and rotate it from the
  EuroValidate dashboard if needed.
* Only the VAT number is sent to `api.eurovalidate.com`. Logs never contain the
  full number (masked as `DE***69`).
* EuroValidate's privacy policy: <https://eurovalidate.com/privacy.html>.

## 17.0 vs 18.0

The code is the same. On 17.0 the `invisible="not vat"` view attributes work as
on 18.0; the `optional="hide"` list column needs Odoo ≥ 16. Set `version` in
`__manifest__.py` to `17.0.1.0.0` on the 17.0 branch.

## Tests

Odoo tests (mocked HTTP, no network):

```bash
odoo-bin -d test_ev --addons-path=addons,/path/to/integrations/odoo \
  --test-enable --test-tags /eurovalidate_vat -i eurovalidate_vat --stop-after-init
```

The HTTP → outcome mapping (`models/eurovalidate_client.py`) is Odoo-free and is
also covered by EuroValidate's own CI (`tests/test_odoo_client.py`).

## License

LGPL-3.0-or-later. © 2026 EuroValidate.
