# -*- encoding: utf-8 -*-
"""
KERI
watopnet.app.cli module

CLI entry point: discovers subcommands via multicommand and runs the resulting
doers under a real-time Doist event loop.
"""
import multicommand
from hio.base import doing
from keri import help

from watopnet.app.cli import commands

logger = help.ogler.getLogger()


def main():
    """Parse arguments and run the selected subcommand under a Doist event loop.

    Subcommands are discovered automatically from the ``commands`` package by
    multicommand.  Each subcommand handler returns a list of doers which are
    driven to completion (or indefinitely when ``limit=0.0``) by a real-time Doist.

    Returns:
        int: -1 on unhandled exception; otherwise implicitly returns None on success.
    """
    parser = multicommand.create_parser(commands)
    args = parser.parse_args()

    if not hasattr(args, "handler"):
        parser.print_help()
        return

    try:
        doers = args.handler(args)
        tock = 0.00125
        doist = doing.Doist(limit=0.0, tock=tock, real=True)
        doist.do(doers=doers)

    except Exception as ex:
        import os

        if os.getenv("DEBUG_WATCHER"):
            import traceback

            traceback.print_exc()
        else:
            print(f"ERR: {ex}")
        return -1


if __name__ == "__main__":
    main()
