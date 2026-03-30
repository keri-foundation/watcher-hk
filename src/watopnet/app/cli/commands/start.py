# -*- encoding: utf-8 -*-
"""
KERI
watopnet.app.cli.commands.start module

``watopnet start`` subcommand: configures logging, validates arguments,
and launches the Watcher Operational Network under a real-time Doist.
"""
import argparse
import logging

from hio.base import doing
from keri import __version__
from keri import help
from watopnet.app import watching

d = "Runs KERI watcher operational network.\n"
d += "Example:\nwatcher -H 7631 -t 7632\n"
parser = argparse.ArgumentParser(description=d)
parser.set_defaults(handler=lambda args: launch(args))
parser.add_argument(
    "-V",
    "--version",
    action="version",
    version=__version__,
    help="Prints out version of script runner.",
)
parser.add_argument(
    "-H",
    "--http",
    action="store",
    default=7632,
    help="Local port number the HTTP server listens on. Default is 7632.",
)
parser.add_argument(
    "-o",
    "--host",
    action="store",
    default="127.0.0.1",
    help="Local host IP address HTTP server listens on. Default is 127.0.0.1.",
)
parser.add_argument(
    "--bootport",
    "-bp",
    action="store",
    default=7631,
    help="Local port number the HTTP server listens on. Default is 7631.",
)
parser.add_argument(
    "--boothost",
    "-bh",
    action="store",
    default="127.0.0.1",
    help="Local host IP address HTTP server listens on. Default is 127.0.0.1.",
)
parser.add_argument(
    "--base",
    "-b",
    help="additional optional prefix to file location of KERI keystore",
    required=False,
    default="",
)
parser.add_argument(
    "--passcode",
    "-p",
    help="22 character encryption passcode for keystore (is not saved)",
    dest="bran",
    default=None,
)  # passcode => bran
parser.add_argument(
    "--config-dir",
    "-c",
    dest="configDir",
    help="directory override for configuration data",
)
parser.add_argument(
    "--config-file",
    dest="configFile",
    action="store",
    default=None,
    help="configuration filename override",
)
parser.add_argument(
    "--loglevel",
    action="store",
    required=False,
    default="INFO",
    help="Set log level to DEBUG | INFO | WARNING | ERROR | CRITICAL. Default is INFO",
)
parser.add_argument(
    "--logfile",
    action="store",
    required=False,
    default=None,
    help="path of the log file. If not defined, logs will not be written to the file.",
)
parser.add_argument("--keypath", action="store", required=False, default=None)
parser.add_argument("--certpath", action="store", required=False, default=None)
parser.add_argument("--cafilepath", action="store", required=False, default=None)

FORMAT = "%(asctime)s [watopnet] %(levelname)-8s %(message)s"


def launch(args):
    """Configure logging and start the watcher service from parsed CLI arguments.

    Parameters:
        args (Namespace): parsed argparse namespace from the ``watopnet start`` parser
    """
    help.ogler.level = logging.getLevelName(args.loglevel)
    baseFormatter = logging.Formatter(FORMAT)  # basic format
    baseFormatter.default_msec_format = None
    help.ogler.baseConsoleHandler.setFormatter(baseFormatter)
    help.ogler.level = logging.getLevelName(args.loglevel)

    if args.logfile is not None:
        help.ogler.headDirPath = args.logfile
        help.ogler.reopen(name="watopnet", temp=False, clear=True)

    logger = help.ogler.getLogger()

    logger.info(
        "******* Starting Watcher Operational Network service internally: http/%s, externally: http/%s"
        ".******",
        args.bootport,
        args.http,
    )

    runWatcher(args)

    logger.info(
        "******* Ended Watcher Operational Network service internally: http/%s, externally: http/%s"
        ".******",
        args.bootport,
        args.http,
    )


def runWatcher(args, expire=0.0):
    """Set up and run the watcher service under a Doist event loop.

    Parameters:
        args (Namespace): parsed argparse namespace containing host, port, and
            config path options
        expire (float): Doist limit in seconds; 0.0 means run indefinitely
    """

    doers = watching.setup(
        base=args.base,
        host=args.host,
        httpport=int(args.http),
        bootHost=args.boothost,
        bootPort=int(args.bootport),
        headDirPath=args.configDir,
        keypath=args.keypath,
        certpath=args.certpath,
        cafilepath=args.cafilepath,
    )

    tock = 0.00125
    doist = doing.Doist(limit=expire, tock=tock, real=True)
    doist.do(doers=doers)
