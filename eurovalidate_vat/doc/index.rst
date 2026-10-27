===========================
EuroValidate VAT Validation
===========================

Validate EU and UK VAT numbers on partners through the EuroValidate API and
pre-fill the registered company name and address — including while VIES is down.

Configuration
=============

#. Get a free API key (100 validations/month, no card) at
   https://eurovalidate.com/v1/auth/signup
#. Settings → General Settings → *EuroValidate*: paste the key.
#. Keep *Fill in name and address from the register* enabled; optionally enable
   *Block saving partners whose VAT number is invalid*.

Usage
=====

* Saving a partner with a VAT number validates it automatically.
* The *Validate with EuroValidate* button next to the VAT field re-checks on demand.
* The *EuroValidate* tab on the partner shows status, confidence, source, request
  id and the registered name/address.
* Statuses: ``valid``, ``invalid``, ``unavailable`` (register down — pending),
  ``unverified`` (format check only), ``error``, ``unknown`` (not checked).

Scheduled re-validation
=======================

*EuroValidate: re-validate partner VAT numbers* (inactive by default) re-checks
up to 200 partners per run whose last verification is older than 30 days.

Limits
======

* Odoo Online (SaaS) cannot install third-party Python modules: use Odoo.sh or
  on-premise.
* Germany and Spain never expose name/address through VIES.
* UK (GB) numbers need a paid EuroValidate plan.

Support
=======

support@eurovalidate.com · https://eurovalidate.com/odoo-vat-validation
