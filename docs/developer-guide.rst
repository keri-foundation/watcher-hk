Developer Guide
===============

Environment
-----------
The current package metadata allows Python ``>=3.12.6``, but the team has already seen
local issues on Python ``3.14``. Until that runtime is verified, use Python ``3.13`` for
local development and documentation work.

Setup
-----

From the repository root:

.. code-block:: bash

   python3.13 -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   python -m pip install -e .
