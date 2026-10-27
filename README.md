# Odoo integration

`eurovalidate_vat/` is a self-contained Odoo module (17.0 / 18.0, LGPL-3).

It is kept here so EuroValidate's CI covers its HTTP mapping
(`tests/test_odoo_client.py`). For distribution it is meant to live in its own
public repository (`Nitrych/eurovalidate-odoo`) with branches `17.0` and `18.0`,
which is what apps.odoo.com expects:

```bash
git subtree split --prefix=integrations/odoo -b odoo-export
# push odoo-export to the new repo as 18.0, then branch 17.0 and set
# "version": "17.0.1.0.0" in eurovalidate_vat/__manifest__.py
```

Keep this copy and the public repo in sync when the module changes.
