Watopnet
========

Watopnet (Watcher Operational Network) is a KERI watcher service. It monitors
Autonomic Identifiers (AIDs) and verifies key-event consistency across
witnesses. It exposes a dual-HTTP-server architecture — a management (boot)
API for provisioning watchers and a main API for KERI event intake, OOBI
resolution, and key-state query replies.

.. note::

   This documentation covers the Watopnet HTTP API, developer workflow, and
   configuration. The developer guide includes an end-to-end walkthrough.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   developer-guide

.. autosummary::
   :toctree: api
   :recursive:

   watopnet

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
