Developer Guide
===============

Watopnet is a `KERI <https://github.com/WebOfTrust/keri>`_ watcher service that monitors
Autonomic Identifiers (AIDs) and verifies key-event consistency across witnesses. Watchers
are provisioned dynamically via a management API, track observed AIDs, poll witnesses for
key state, and process KERI query messages from authorized controllers.

Environment
-----------

The current package metadata requires Python ``>=3.12.6``. Use Python ``3.12`` for
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

   python3.12 -m venv .venv
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

   mkdir -p /tmp/watcher-demo/keri/cf/main

   cat > /tmp/watcher-demo/keri/cf/main/watopnet.json <<'EOF'
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
   ``keri/``), not to ``/tmp/watcher-demo/keri/cf/main/``. KERI appends
   ``keri/cf/main/`` internally and looks for ``watopnet.json`` there.

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

The response includes the controller AID (``cid``), the watcher's endpoint
identifier (``eid``) and its OOBI URLs (``oobis``). Give the OOBI to the
controller so it can resolve the watcher.

Step 4: Check watcher status
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   curl "http://127.0.0.1:7631/watchers/<watcher-eid>/status"

Returns ``watcher_id``, ``controller_id``, a per-AID map of witness results
(``aids``), and a ``summary`` with ``total_aids``, ``total_witnesses``,
``responsive_witnesses`` and ``last_query_time``. Results appear only after
the watcher has polled at least one observed AID, so a freshly provisioned
watcher returns empty ``aids`` until the controller has registered an AID
to watch (for example with ``kli watcher add``; see ``scripts/verifier.sh``).

Architecture
------------

Watopnet runs two HTTP servers side by side:

- **Boot server** (default ``127.0.0.1:7631``): management API. Use this to provision
  new watchers (``POST /watchers``) and delete watchers (``DELETE /watchers/{eid}``).

- **Watcher server** (default ``127.0.0.1:7632``): KERI event processing. Handles
  event intake (``POST /``) and OOBI resolution (``GET /oobi/...``).

Each provisioned watcher gets its own non-transferable KERI identifier (Hab) and its own
keystore, and serves exactly one controller AID. A single process hosts any number of
watchers, told apart on the watcher server by the ``CESR-Destination`` header. The
:class:`~watopnet.app.watching.Watchery` class
manages all running watchers and persists their records in an LMDB database via
:class:`~watopnet.core.basing.Baser`. Watcher keystores are unencrypted, and the boot
server is unauthenticated: keep it on localhost or cluster-internal.

How watching works
~~~~~~~~~~~~~~~~~~

1. ``POST /watchers`` creates the watcher identifier and records its controller.
2. The controller posts its KEL and a signed ``/watcher/<eid>/add`` reply to
   ``POST /`` (``kli watcher add`` does this). The reply names the AID to observe
   and an OOBI the watcher resolves to fetch that AID's KEL.
3. A :class:`~watopnet.app.watching.SentinalDoer` launches a
   :class:`~watopnet.app.watching.Sentinal` for each enabled observed AID every
   30 seconds (60 seconds for the controller's own AID). The Sentinal asks each of the
   AID's witnesses for key state and compares it with the local KEL, classifying each
   witness as ``even``, ``behind``, ``ahead``, ``duplicitous`` or ``unresponsive``. AIDs
   without witnesses are skipped; if witnesses are ahead, the missing events are queried.
4. Results are stored per (watcher, AID, witness) and served by the status endpoint.
   Duplicity is logged and reported in status; it is not pushed to the controller.

Cross-cutting behavior: the watcher server applies a per-client rate limit
(100 requests per 10 seconds, then ``429``), and its QRY handling only answers
the watcher's own controller. The ``core/tcp`` layer and ``CueDoer`` are not
started by :func:`~watopnet.app.watching.setup`.

Configuration
-------------

The watcher server is configured via a KERI config file. A sample is provided at
``scripts/keri/cf/main/watopnet.json``:

.. code-block:: json

   {
     "dt": "2022-01-20T12:57:59.823350+00:00",
     "watopnet": {
       "dt": "2022-01-20T12:57:59.823350+00:00",
       "curls": ["http://localhost:7632/"]
     }
   }

The first ``curls`` entry sets the advertised HTTP scheme, hostname, and port used in
the OOBIs returned by provisioning; it is only read when the ``watopnet`` section also
has a ``dt`` field. A second entry sets a TCP port, which is currently unused. Pass the
directory *above* ``keri/cf/main/`` (the one containing ``keri/cf/main/watopnet.json``)
to ``--config-dir``. A missing file is not an error: an empty config is used and OOBIs
advertise ``http://127.0.0.1:7632``.

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
     - Directory above ``keri/cf/main/`` containing ``watopnet.json``
   * - ``--config-file``
     - —
     - Accepted but currently ignored (the file is always ``watopnet.json``)
   * - ``--base`` / ``-b``
     - ``""``
     - Optional prefix for the KERI keystore location
   * - ``--passcode`` / ``-p``
     - —
     - Accepted but currently ignored (watcher keystores are unencrypted)
   * - ``--keypath`` / ``--certpath`` / ``--cafilepath``
     - —
     - TLS key, certificate and CA bundle; applied to the boot server only
   * - ``-V`` / ``--version``
     - —
     - Print the installed ``keri`` library version
   * - ``--loglevel``
     - ``INFO``
     - Log level: ``DEBUG``, ``INFO``, ``WARNING``, ``ERROR``, ``CRITICAL``
   * - ``--logfile``
     - —
     - Path to write log output to file

Environment variables:

- ``DEBUG_WATCHER``: if set, print full tracebacks on errors.
- ``WATOPNET_DOIST_TOCK``: main loop tick in seconds (default ``0.03125``).
- ``WATOPNET_ESCROW_TOCK``: escrow processing interval in seconds (default ``0.5``).
- ``KERI_BASER_MAP_SIZE``: LMDB map size; ``scripts/watopnet-sample.sh`` and the Docker
  image set ``1099511627776``.

Provisioning a Watcher
----------------------

To provision a new watcher for a controller AID, send a request to the boot server:

.. code-block:: bash

   curl -X POST http://127.0.0.1:7631/watchers \
        -H "Content-Type: application/json" \
        -d '{"aid": "<qb64-controller-aid>"}'

An optional ``oobi`` field is queued for the new watcher to resolve. Every call
creates a new watcher (no de-duplication). Errors: ``400`` for a missing or invalid
``aid``; ``503`` if the process ran out of file descriptors. The response contains:

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
     - Delete a watcher and its keystore by endpoint identifier (irreversible). ``204`` on success. Known issue: a well-formed but unknown ``eid`` currently returns ``500``, not ``404``
   * - ``GET``
     - ``/watchers/{eid}/status``
     - Get watcher status: watcher/controller IDs, witness-query summaries, and stored per-AID witness results. ``404`` for an unknown ``eid``
   * - ``GET``
     - ``/health``
     - Liveness check, returns ``204``

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
     - Submit one KERI message (KEL/EXN/RPY/QRY) with CESR attachments. Requires the ``CESR-Destination`` header (target watcher AID). QRY is answered inline and only for the watcher's controller; TEL/ACDC messages get ``422``
   * - ``PUT``
     - ``/``
     - Push CESR bytes into the watcher's inbound stream (requires ``CESR-Destination``)
   * - ``GET``
     - ``/oobi``
     - Always ``404`` (no default AID is configured)
   * - ``GET``
     - ``/oobi/{aid}``
     - OOBI resolution for a watcher AID
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
handling, and witness-state query processing. The test suite uses temporary
KERI keystores so no external services are required.

To run a specific test file:

.. code-block:: bash

   pytest tests/watopnet/core/test_watching.py -v

.. _troubleshooting:

Troubleshooting
---------------

**Provisioned OOBIs say ``http://127.0.0.1:7632`` instead of my hostname**
    The config file was not found (or its ``watopnet`` section has no ``dt``), and
    KERI silently fell back to an empty config. Ensure ``--config-dir`` points one
    level *above* ``keri/``; KERI looks for
    ``<config-dir>/keri/cf/main/watopnet.json``.

**Port already in use**
    Change ``-H`` or ``--bootport``. Both servers must bind to unique ports.
    Kill any existing ``watopnet`` processes first: ``pkill -f watopnet``.

**``400 CESR request destination header missing`` / ``404 unknown destination AID``**
    Requests to the watcher server must carry ``CESR-Destination: <watcher eid>``
    naming a provisioned watcher.

**Status shows no AIDs**
    The watcher only polls AIDs its controller has registered (``kli watcher add``),
    whose KEL it has resolved via OOBI, and which have witnesses. Polls run every
    30 seconds, so allow a short delay.

**``429 Too Many Requests``**
    The watcher server allows 100 requests per 10 seconds per client key.

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
