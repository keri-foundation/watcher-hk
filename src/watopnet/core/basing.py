# -*- encoding: utf-8 -*-

"""
KERI
watopnet.core.basing module

Database layer for the Watcher Operational Network.
"""

from dataclasses import dataclass

from keri.core import coring
from keri.db import dbing, koming, subing


@dataclass
class Wat:
    """Persisted record for a single provisioned watcher.

    Attributes:
        name (str): internal keystore name for the watcher Hab
        wid (str): qb64 AID of the watcher identifier
        cid (str): qb64 AID of the controller this watcher serves
    """

    name: str
    wid: str
    cid: str


@dataclass
class WitnessQuery:
    """Record of a single witness key-state query made by a watcher.

    Attributes:
        watcher_id (str): qb64 AID of the watcher that issued the query
        aid (str): qb64 AID of the observed identifier being monitored
        wit (str): qb64 AID of the witness that was queried
        query_timestamp (str): ISO 8601 timestamp when the query was issued
        response_received (bool): True if the witness responded before timeout
        state (str): consistency state — one of even, ahead, behind, duplicitous, unresponsive
        keystate (str | None): serialised key state notice returned by the witness
        sn (int | None): sequence number reported by the witness
        dig (str | None): event digest reported by the witness
        error (str | None): error message if response_received is False
    """

    watcher_id: str
    aid: str
    wit: str
    query_timestamp: str
    response_received: bool
    state: str
    keystate: str = None
    sn: int = None
    dig: str = None
    error: str = None


@dataclass
class Requests:
    """Per-IP request-rate tracking record for a single throttle window.

    Attributes:
        dt (str): ISO 8601 timestamp of the first request in this window
        count (int): number of requests received within this window
    """

    dt: str
    count: int


class Baser(dbing.LMDBer):
    """LMDB database for the Watcher Operational Network.

    Extends the base KERI LMDBer with four sub-databases:
        - ``ips``: per-IP request-rate records keyed by IP address string
        - ``wats``: watcher records keyed by watcher AID
        - ``cids``: controller-AID-to-datetime-processed index keyed by (watcher AID, controller AID)
        - ``witq``: most recent witness query records keyed by (watcher AID, observed AID, witness AID)
    """

    TailDirPath = "keri/watopnet"
    AltTailDirPath = ".keri/watopnet"
    TempPrefix = "keri_watopnet_"

    def __init__(self, name="watopnet", headDirPath=None, reopen=True, **kwa):
        """
        Parameters:
            name (str): database name, also used as the directory name
            headDirPath (str | None): optional override for the database head directory
            reopen (bool): if True, open the database immediately on construction
            **kwa: additional keyword arguments forwarded to LMDBer
        """
        self.ips = None
        self.wats = None
        self.cids = None
        self.witq = None

        super(Baser, self).__init__(
            name=name, headDirPath=headDirPath, reopen=reopen, **kwa
        )

    def reopen(self, **kwa):
        """Reopen database and initialize sub-dbs."""
        super(Baser, self).reopen(**kwa)

        self.ips = koming.Komer(db=self, subkey="ips.", schema=Requests)
        self.wats = koming.Komer(db=self, subkey="wats.", schema=Wat)
        self.cids = subing.CesrSuber(db=self, subkey="cids.", klas=coring.Dater)
        self.witq = koming.Komer(db=self, subkey="witq.", schema=WitnessQuery)

        return self.env
