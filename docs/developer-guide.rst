Developer Guide
===============

Watopnet is a `KERI <https://github.com/WebOfTrust/keri>`_ watcher service that monitors
Autonomic Identifiers (AIDs) and verifies key-event consistency across witnesses. Watchers
are provisioned dynamically via a management API, track observed AIDs, poll witnesses for
key state, and process KERI query messages from authorized controllers.

Environment
-----------

The current package metadata requires Python ``>=3.14.0``. Use Python ``3.14`` for
development and documentation work — this matches the Read the Docs build configuration.

Watopnet also requires ``libsodium``, which is a dependency of the ``keri`` package.

**macOS:**

.. code-block:: bash

   brew install libsodium

**Ubuntu/Debian:**

.. code-block:: bash

   sudo apt-get install libsodium-dev

Setup
-----

From the repository root:

.. code-block:: bash

   python3.14 -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   python -m pip install -e .

For development with test dependencies:

.. code-block:: bash

   python -m pip install -e ".[dev]"

End-to-End Walkthrough
----------------------

This section walks through starting the service, provisioning a watcher for a
controller, and checking watcher status.
Follow these steps in order. If you get stuck, see the :ref:`troubleshooting` section.

.. note::

   Watchers depend on witnesses for key-state verification during monitoring.
   The walkthrough below covers starting the service and provisioning — witness
   interaction occurs after the watcher is provisioned and receiving events.
   Start the witness service (``witopnet``) first if you plan to exercise the
   full monitoring flow. See the
   `witness-hk developer guide <https://github.com/keri-foundation/witness-hk>`_.

Step 1: Prepare the config directory
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Create a config directory with the KERI config file structure:

.. code-block:: bash

   mkdir -p /tmp/watcher-demo/keri/cf

   cat > /tmp/watcher-demo/keri/cf/watopnet.json <<'EOF'
   {
     "dt": "2022-01-20T12:57:59.823350+00:00",
     "watopnet": {
       "dt": "2022-01-20T12:57:59.823350+00:00",
       "curls": ["http://localhost:7632/"]
     }
   }
   EOF

.. note::

   ``--config-dir`` must point to ``/tmp/watcher-demo`` (one level *above*
   ``keri/``), not to ``/tmp/watcher-demo/keri/cf/``. KERI appends
   ``keri/cf/`` internally and looks for ``watopnet.json`` there.

Step 2: Start the watcher
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   watopnet start -H 7632 --bootport 7631 --config-dir /tmp/watcher-demo

Where ``-H`` is the main watcher HTTP port and ``--bootport`` is the boot server port.

The startup log includes a message reporting both configured ports:

.. code-block:: text

   Starting Watcher Operational Network service internally: http/7631, externally: http/7632

Step 3: Provision the watcher for your controller
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   curl -X POST http://127.0.0.1:7631/watchers \
     -H "Content-Type: application/json" \
     -d '{"aid": "<your-controller-aid>"}'

The response includes the watcher's endpoint identifier (``eid``) and OOBI URLs.

Step 4: Check watcher status
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   curl "http://127.0.0.1:7631/watchers/<watcher-eid>/status"

Returns the watcher's current state including the controller AID, total
witnesses, and responsive witness count.

Architecture
------------

Watopnet runs two HTTP servers side by side:

- **Boot server** (default ``127.0.0.1:7631``): management API. Use this to provision
  new watchers (``POST /watchers``) and delete watchers (``DELETE /watchers/{eid}``).

- **Watcher server** (default ``127.0.0.1:7632``): KERI event processing. Handles
  event intake (``POST /``) and OOBI resolution (``GET /oobi/...``).

Each provisioned watcher gets its own non-transferable KERI identifier (Hab) and its own
keystore. The :class:`~watopnet.app.watching.Watchery` class
manages all running watchers and persists their records in an LMDB database via
:class:`~watopnet.core.basing.Baser`.

Configuration
-------------

The watcher server is configured via a KERI config file. A sample is provided at
``scripts/keri/cf/watopnet.json``:

.. code-block:: json

   {
     "dt": "2022-01-20T12:57:59.823350+00:00",
     "watopnet": {
       "dt": "2022-01-20T12:57:59.823350+00:00",
       "curls": ["http://localhost:7632/"]
     }
   }

The first ``curls`` entry sets the watcher's advertised HTTP scheme,
hostname, and port.  If a second entry is present, watcher-hk uses its
port as the TCP port value. Pass the
directory containing ``keri/cf/watopnet.json`` to ``--config-dir``.

Running the Watcher
-------------------

After installation, the ``watopnet`` CLI is available:

.. code-block:: bash

   watopnet start -H 7632 --bootport 7631 --config-dir /path/to/scripts

Key flags:

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Flag
     - Default
     - Description
   * - ``-H`` / ``--http``
     - ``7632``
     - Port the watcher server listens on
   * - ``-o`` / ``--host``
     - ``127.0.0.1``
     - Host IP address the watcher server listens on
   * - ``-bp`` / ``--bootport``
     - ``7631``
     - Port the boot server listens on
   * - ``-bh`` / ``--boothost``
     - ``127.0.0.1``
     - Host IP address the boot server listens on
   * - ``--config-dir`` / ``-c``
     - —
     - Directory one level above ``keri/cf/`` containing the config file
   * - ``--config-file``
     - —
     - Config filename override
   * - ``--loglevel``
     - ``INFO``
     - Log level: ``DEBUG``, ``INFO``, ``WARNING``, ``ERROR``, ``CRITICAL``
   * - ``--logfile``
     - —
     - Path to write log output to file

Set ``DEBUG_WATCHER=1`` in your environment to print full tracebacks on errors.

Provisioning a Watcher
----------------------

To provision a new watcher for a controller AID, send a request to the boot server:

.. code-block:: bash

   curl -X POST http://127.0.0.1:7631/watchers \
        -H "Content-Type: application/json" \
        -d '{"aid": "<qb64-controller-aid>"}'

The response contains:

- ``cid``: the controller AID
- ``eid``: the watcher AID
- ``oobis``: list of OOBI URLs the controller should resolve

HTTP API Reference
------------------

.. _api-reference:

Boot server (``localhost:7631``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 10 30 60

   * - Method
     - Path
     - Description
   * - ``POST``
     - ``/watchers``
     - Provision a new watcher. Body: ``{"aid": "<qb64-AID>"}``
   * - ``DELETE``
     - ``/watchers/{eid}``
     - Delete a watcher by its endpoint identifier
   * - ``GET``
     - ``/watchers/{eid}/status``
     - Get watcher status: watcher/controller IDs, witness-query summaries, and stored per-AID witness results

Watcher server (``localhost:7632``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 10 30 60

   * - Method
     - Path
     - Description
   * - ``POST``
     - ``/``
     - Submit a KERI event (KEL/EXN/RPY/QRY) with CESR attachments
   * - ``PUT``
     - ``/``
     - Push CESR bytes into the inbound stream
   * - ``GET``
     - ``/oobi``
     - OOBI resolution (default AID)
   * - ``GET``
     - ``/oobi/{aid}``
     - OOBI resolution endpoint
   * - ``GET``
     - ``/oobi/{aid}/{role}``
     - OOBI with role
   * - ``GET``
     - ``/oobi/{aid}/{role}/{eid}``
     - OOBI with role and participant EID

Testing
-------

.. code-block:: bash

   pip install -e ".[dev]"
   pytest tests/

Tests under ``tests/`` include coverage for watcher provisioning, OOBI
handling, and witness-state query processing. The test suite uses temporary in-memory
KERI keystores so no external services are required.

To run a specific test file:

.. code-block:: bash

   pytest tests/watopnet/core/test_watching.py -v

.. _troubleshooting:

Troubleshooting
---------------

**"No such file or directory" when starting**
    Ensure ``--config-dir`` points one level *above* ``keri/``, not inside
    ``keri/cf/``. KERI looks for ``<config-dir>/keri/cf/watopnet.json``.

**Port already in use**
    Change ``-H`` or ``--bootport``. Both servers must bind to unique ports.
    Kill any existing ``watopnet`` processes first: ``pkill -f watopnet``.

**"Unknown sender key state"**
    This error can occur during KERI protocol exchanges (such as event submission
    through ``POST /``) when the sender's key state is not yet known to the
    watcher. Ensure the controller AID has been incepted (``kli incept``) and its
    key events have propagated.

**ImportError: libsodium not found**
    Install libsodium: ``brew install libsodium`` (macOS) or
    ``sudo apt-get install libsodium-dev`` (Ubuntu/Debian).

**ModuleNotFoundError: No module named 'watopnet'**
    Install the package in development mode: ``pip install -e .`` from the
    repository root.

Building the Docs
-----------------

From the repository root:

.. code-block:: bash

   pip install -e .
   pip install sphinx sphinx-rtd-theme
   cd docs
   sphinx-build -b dirhtml . _build/html

To do a clean rebuild:

.. code-block:: bash

   rm -rf _build

Next: Witness
-------------

This watcher service is paired with ``witopnet`` (``witness-hk``), a KERI
witness that provides authenticated event receipting. Watchers depend on
witnesses for key-state verification. See the
`witness-hk repository <https://github.com/keri-foundation/witness-hk>`_
for its developer guide.
