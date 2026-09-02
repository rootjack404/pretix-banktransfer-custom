pretix Bank Transfer (Custom)
===============================

Custom pretix payment plugin based on the official bank transfer plugin.

This version matches incoming bank transfers by a unique randomized three-digit
amount suffix instead of a personal reference code.

This plugin is **separate** from pretix's built-in bank transfer plugin
(``pretix.plugins.banktransfer``). Both can be installed at the same time, but
you should normally enable only one payment method per event.

Installation
------------

Install the plugin into your pretix virtual environment::

    pip install -e /path/to/pretix-csutom-banktransfer

After installation, restart pretix and enable **Bank transfer - custom** for your
event or organizer in the pretix control panel.

Development
-----------

From the repository root::

    pip install -e .

Then run pretix migrations as usual::

    python -m pretix migrate

Plugin identifiers
------------------

- Django app: ``pretix_banktransfer_custom``
- Payment provider: ``banktransfer_custom``
- URL namespace: ``plugins:banktransfer_custom:…``
