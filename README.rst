pretix Bank Transfer (Custom)
===============================

Custom pretix payment plugin based on the official bank transfer plugin.

This version matches incoming bank transfers by a unique randomized three-digit
amount suffix instead of a personal reference code.

Installation
------------

Install the plugin into your pretix virtual environment::

    pip install -e /path/to/pretix-csutom-banktransfer

Or from a git repository::

    pip install git+https://example.com/pretix-csutom-banktransfer.git

After installation, restart pretix and enable **Bank transfer - custom** for your
event or organizer in the pretix control panel.

Important: disable the built-in **Bank transfer** plugin
--------------------------------------------------------

pretix ships with ``pretix.plugins.banktransfer`` enabled by default. This custom
plugin reuses the same database tables, so you must not run both at the same time.

1. Remove ``pretix.plugins.banktransfer`` from your pretix ``INSTALLED_APPS`` if you
   added it manually, or exclude it in ``pretix.cfg``::

       [pretix]
       plugins_exclude=pretix.plugins.banktransfer

2. Enable ``pretix_banktransfer_custom`` for your event/organizer instead of the
   built-in bank transfer plugin.

Development
-----------

From the repository root::

    pip install -e .

Then run pretix migrations as usual::

    python -m pretix migrate
