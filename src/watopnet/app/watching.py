# -*- encoding: utf-8 -*-

"""
KERI
watopnet.app.watching module

Core watcher orchestration: dual HTTP server setup, Watchery lifecycle management,
per-watcher Doer trees, witness-polling Sentinals, and boot API endpoints.
"""
import datetime
import json
import random
from collections import namedtuple
from dataclasses import asdict
from urllib.parse import urlsplit

import falcon
from hio.base import doing, tyming
from hio.core import http
from hio.help import decking
from keri import help
from keri import kering
from keri.app import configing, indirecting, habbing, agenting, querying
from keri.app.oobiing import Oobiery
from keri.core import coring, Salter, routing, eventing, parsing
from keri.db.basing import OobiRecord, BaserDoer
from keri.help import helping
from keri.peer import exchanging
from keri.vdr import verifying
from keri.vdr.eventing import Tevery
from watopnet.core import basing, httping, oobing
from watopnet.core.httping import HttpEnd

logger = help.ogler.getLogger()

Stateage = namedtuple("Stateage", "even ahead behind duplicitous unresponsive")
States = Stateage(
    even="even",
    ahead="ahead",
    behind="behind",
    duplicitous="duplicitous",
    unresponsive="unresponsive",
)


class WitnessState:
    """
    State of an AID according to a particular
    """

    wit: str
    state: Stateage
    sn: int
    dig: str


def setup(
    bootHost="127.0.0.1",
    bootPort=7631,
    base=None,
    headDirPath=None,
    host="127.0.0.1",
    httpport=7632,
    keypath=None,
    certpath=None,
    cafilepath=None,
):
    """Initialize and return the list of doers for the Watcher Operational Network.

    Sets up a dual-server HTTP architecture:
      - Boot server (bootHost:bootPort): management API for provisioning watchers
      - Watcher server (host:httpport): KERI event processing and OOBI resolution

    Parameters:
        bootHost (str): host the boot/management HTTP server listens on
        bootPort (int): port the boot/management HTTP server listens on
        base (str | None): optional path prefix for KERI keystore storage
        headDirPath (str | None): optional override for the config file directory
        host (str): host the main watcher HTTP server listens on
        httpport (int): port the main watcher HTTP server listens on
        keypath (str | None): optional path to TLS private key
        certpath (str | None): optional path to TLS certificate
        cafilepath (str | None): optional path to TLS CA bundle

    Returns:
        list: doers ready to run under a Doist event loop
    """

    db = basing.Baser(name="watopnet", base=base)
    dbDoer = BaserDoer(db)

    cf = configing.Configer(name=db.name, headDirPath=headDirPath)

    wty = Watchery(db, base=base, cf=cf, host=host, httpport=httpport)

    bootApp = falcon.App(
        middleware=falcon.CORSMiddleware(
            allow_origins="*",
            allow_credentials="*",
            expose_headers=[
                "cesr-attachment",
                "cesr-date",
                "content-type",
                "signature",
                "signature-input",
                "signify-resource",
                "signify-timestamp",
            ],
        )
    )

    bootServer = indirecting.createHttpServer(
        host=bootHost,
        port=bootPort,
        app=bootApp,
        keypath=keypath,
        certpath=certpath,
        cafilepath=cafilepath,
    )
    bootSrvrDoer = http.ServerDoer(server=bootServer)
    watColEnd = WatcherCollectionEnd(wty)
    bootApp.add_route("/watchers", watColEnd)
    watResEnd = WatcherResourceEnd(wty)
    bootApp.add_route("/watchers/{eid}", watResEnd)
    watcherStatusEnd = WatcherStatusEnd(wty)
    bootApp.add_route("/watchers/{eid}/status", watcherStatusEnd)

    app = falcon.App(
        middleware=falcon.CORSMiddleware(
            allow_origins="*",
            allow_credentials="*",
            expose_headers=[
                "cesr-attachment",
                "cesr-date",
                "content-type",
                "signature",
                "signature-input",
                "signify-resource",
                "signify-timestamp",
            ],
        )
    )
    app.add_middleware(httping.Throttle(db=db))
    server = http.Server(host=host, port=httpport, app=app)
    serverDoer = http.ServerDoer(server=server)

    oobiEnd = oobing.OOBIEnd(wty=wty)
    app.add_route("/oobi", oobiEnd)
    app.add_route("/oobi/{aid}", oobiEnd)
    app.add_route("/oobi/{aid}/{role}", oobiEnd)
    app.add_route("/oobi/{aid}/{role}/{eid}", oobiEnd)

    httpEnd = HttpEnd(wty=wty)
    app.add_route("/", httpEnd)

    doers = [wty, dbDoer, serverDoer, bootSrvrDoer]

    return doers


class Watchery(doing.DoDoer):
    """Manages the lifecycle of all active Watcher instances.

    Reads watcher records from the watopnet database on startup and instantiates
    a Watcher DoDoer for each. Exposes lookup, creation, and deletion of watchers
    for use by the boot HTTP API.
    """

    def __init__(
        self,
        db,
        base="",
        temp=False,
        cf=None,
        scheme=kering.Schemes.http,
        qrycues=None,
        host="127.0.0.1",
        httpport=7632,
        tcpport=7633,
    ):
        """
        Parameters:
            db (Baser): watopnet LMDB database
            base (str): optional path prefix for KERI keystore storage
            temp (bool): if True, use temporary in-memory keystores
            cf (Configer | None): KERI configuration file reader
            scheme (str): URL scheme advertised by this watcher (http or https)
            qrycues (Deck | None): shared deck for query-reply cues
            host (str): hostname advertised in OOBI URLs
            httpport (int): HTTP port advertised in OOBI URLs
            tcpport (int): TCP port for direct connections
        """
        self.db = db
        self.base = base
        self.temp = temp
        self.cf = cf
        self.scheme = scheme
        self.host = host
        self.httpport = httpport
        self.tcpport = tcpport

        if self.cf is not None:
            conf = self.cf.get()
            conf = conf.get("watopnet", {})
            if "dt" in conf:  # datetime of config file
                if "curls" in conf:
                    curls = conf["curls"]

                    url = curls[0]
                    splits = urlsplit(url)
                    self.host = splits.hostname
                    self.httpport = splits.port
                    self.scheme = (
                        splits.scheme
                        if splits.scheme in kering.Schemes
                        else kering.Schemes.http
                    )
                    if len(curls) > 1:
                        url = curls[1]
                        splits = urlsplit(url)
                        self.tcpport = splits.port

        self.qrycues = qrycues if qrycues is not None else decking.Deck()

        self.wats = dict()

        self.reload()
        doers = list(self.wats.values())

        super(Watchery, self).__init__(doers=doers, always=True)

    def reload(self):
        """Load all watcher records from the database and instantiate Watcher doers."""
        for said, wat in self.db.wats.getItemIter():
            hby = habbing.Habery(name=wat.name, base=self.base, temp=self.temp)
            hab = hby.habByName(wat.name)

            watcher = Watcher(wty=self, db=self.db, hby=hby, hab=hab, cid=wat.cid)
            self.wats[hab.pre] = watcher

    def lookup(self, aid):
        """Return the Watcher for the given AID, or None if not found.

        Parameters:
            aid (str): qb64 AID of the watcher

        Returns:
            Watcher | None: the matching Watcher instance, or None
        """
        if aid in self.wats:
            return self.wats[aid]

        return None

    @property
    def url(self):
        """Base URL advertised by this watcher service (scheme://host[:port]).

        Returns:
            str: base URL string
        """
        if self.httpport is None:
            return f"{self.scheme}://{self.host}"
        else:
            return f"{self.scheme}://{self.host}:{self.httpport}"

    def createWatcher(self, cid):
        """Provision a new Watcher for the given controller AID.

        Generates a new non-transferable signing identifier (hab), registers its
        endpoint role and URL scheme in the keystore, persists the watcher record
        to the database, and adds it to the running set of doers.

        Parameters:
            cid (str): qb64 AID of the controller to be watched

        Returns:
            Watcher: the newly created and running Watcher instance
        """
        # Create a random name from Salter
        name = Salter().qb64

        # We need to manage keys from an HSM here
        hby = habbing.Habery(name=name, base=self.base, bran=None)
        hab = hby.makeHab(name=name, transferable=False)
        dt = helping.nowIso8601()

        msgs = bytearray()
        msgs.extend(
            hab.makeEndRole(eid=hab.pre, role=kering.Roles.controller, stamp=dt)
        )
        msgs.extend(hab.makeLocScheme(url=f"{self.url}/", scheme=self.scheme, stamp=dt))
        hab.psr.parse(ims=msgs)

        wat = basing.Wat(name=name, cid=cid, wid=hab.pre)

        self.db.wats.pin(keys=(hab.pre,), val=wat)
        self.db.cids.pin(keys=(hab.pre, cid), val=coring.Dater())

        watcher = Watcher(
            wty=self,
            db=self.db,
            hby=hby,
            hab=hab,
            cid=cid,
        )
        self.wats[hab.pre] = watcher

        self.extend([watcher])

        return watcher

    def deleteWatcher(self, eid):
        """Remove a running Watcher by its endpoint identifier.

        Closes the Watcher doer, removes its record from the database, and
        deletes it from the in-memory registry.

        Parameters:
            eid (str): qb64 AID (endpoint identifier) of the watcher to remove

        Returns:
            bool: True if the watcher was found and removed, False if not found
        """
        if eid not in self.wats:
            raise ValueError(
                f"Unable to delete watcher, {eid} is not a valid watcheridentifier"
            )

        watcher = self.wats[eid]

        cid = watcher.cid
        self.db.wats.rem(keys=(eid,))
        self.db.cids.rem(keys=(eid, cid))
        watcher.hby.close(clear=True)

        self.remove([watcher])


class Watcher(doing.DoDoer):
    """Doer that manages KERI event processing for a single provisioned watcher.

    Each Watcher owns a Habery keystore, a CESR parser pipeline (Kevery, Revery,
    Tevery, Exchanger), an Oobiery for OOBI resolution, and a SentinalDoer that
    periodically polls witnesses for observed AIDs.
    """

    def __init__(self, wty, db, hby, hab, cid):
        """
        Parameters:
            wty (Watchery): parent Watchery registry
            db (Baser): watopnet LMDB database for watcher-specific records
            hby (Habery): KERI keystore environment for this watcher
            hab (Hab): non-transferable Hab for this watcher's own AID
            cid (str): qb64 AID of the controller this watcher serves
        """
        self.wty = wty
        self.cid = cid
        self.db = db
        self.hby = hby
        self.hab = hab
        self.cues = decking.Deck()

        self.rtr = routing.Router()
        self.rvy = routing.Revery(
            db=self.hby.db, rtr=self.rtr, cues=self.cues, lax=True, local=False
        )

        #  needs unique kevery with ims per remoter connnection
        self.kvy = eventing.Kevery(
            db=self.hby.db,
            cues=self.cues,
            rvy=self.rvy,
            lax=True,
            local=False,
            direct=False,
        )
        self.kvy.registerReplyRoutes(self.rtr)

        self.verifier = verifying.Verifier(hby=self.hby)
        self.tvy = Tevery(
            reger=self.verifier.reger,
            db=self.hby.db,
            rvy=self.rvy,
            lax=True,
            local=False,
            cues=self.cues,
        )
        self.tvy.registerReplyRoutes(self.rtr)

        self.exc = exchanging.Exchanger(hby=self.hby, handlers=[])

        self.psr = parsing.Parser(
            framed=True,
            kvy=self.kvy,
            tvy=self.tvy,
            exc=self.exc,
            rvy=self.rvy,
            vry=self.verifier,
        )

        self.oobiery = Oobiery(self.hby, rvy=self.rvy)
        oobis = self.oobis()
        oobi = oobis[0] if len(oobis) > 0 else None
        doers = [
            *self.oobiery.doers,
            WatcherStart(hab=self.hab),
            MessageDoer(parser=self.psr),
            EscrowDoer(kvy=self.kvy, rvy=self.rvy, tvy=self.tvy, exc=self.exc),
            SentinalDoer(
                db=self.db, hby=self.hby, hab=self.hab, cid=self.cid, oobi=oobi
            ),
        ]

        super(Watcher, self).__init__(doers=doers)

    def enter(self, doers=None, *, temp=None):
        """Ensure the TEL credential registry is open before starting child doers."""
        if not self.verifier.reger.opened:
            self.verifier.reger.reopen()

        super(Watcher, self).enter(doers=doers, temp=temp)

    def exit(self, deeds=None, **kwa):
        """Close the Habery keystore and TEL registry on shutdown."""
        if self.hby:
            logger.info(f"Closing watcher database {self.hby.name}")
            self.hby.close()

        if self.verifier:
            self.verifier.reger.close()

    def oobis(self):
        """Return the list of OOBI URLs this watcher advertises.

        Returns:
            list[str]: OOBI URLs in the form ``{wty.url}/oobi/{watcher-AID}/controller``
        """
        oobis = [f"{self.wty.url}/oobi/{self.hab.pre}/controller"]

        return oobis


class SentinalDoer(doing.DoDoer):
    """DoDoer that periodically launches Sentinal instances to check observed AIDs.

    On each recur tick it scans the observed-AID table (``obvs``) for enabled entries
    whose last-check timestamp is older than ``WATCHERRETRY`` seconds, and the
    controller-tracking table (``cids``) for entries older than ``CONTROLLERRETRY``
    seconds.  A fresh Sentinal doer is launched for each qualifying entry.

    Class attributes:
        WATCHERRETRY (int): minimum seconds between witness polls for observed AIDs
        CONTROLLERRETRY (int): minimum seconds between witness polls for the controller AID
    """

    WATCHERRETRY = 30
    CONTROLLERRETRY = 60

    def __init__(self, db, hby, hab, cid, oobi):
        """
        Parameters:
            db (Baser): watopnet LMDB database
            hby (Habery): KERI keystore environment for this watcher
            hab (Hab): non-transferable Hab for this watcher's own AID
            cid (str): qb64 AID of the controller this watcher serves
            oobi (str): OOBI URL of this watcher, passed to Sentinal instances
        """
        self.db = db
        self.hab = hab
        self.hby = hby
        self.cid = cid
        self.oobi = oobi
        self.sentinals = dict()
        super(SentinalDoer, self).__init__(doers=[], always=True)

    def recur(self, tyme, deeds=None):
        """Check both observed-AID and controller tables and launch Sentinals as needed."""
        self.watchWatched()
        self.watchControllers()
        for wid, sentinal in list(self.sentinals.items()):
            if sentinal.done:
                del self.sentinals[wid]

        return super(SentinalDoer, self).recur(tyme, deeds=None)

    def watchWatched(self):
        """Launch a Sentinal for each enabled observed AID that is due for a check."""
        for (_, _, oid), observed in self.hby.db.obvs.getItemIter(
            keys=(
                self.cid,
                self.hab.pre,
            )
        ):
            if observed.enabled and oid not in self.sentinals:
                dtnow = helping.nowUTC()
                dte = helping.fromIso8601(observed.datetime)
                if (dtnow - dte) > datetime.timedelta(seconds=self.WATCHERRETRY):
                    sentinal = Sentinal(
                        self.hby, self.hab, oid, self.cid, self.oobi, self.db
                    )
                    self.sentinals[oid] = sentinal
                    self.extend([sentinal])
                    observed.datetime = helping.toIso8601(dtnow)
                    self.hby.db.obvs.pin(
                        keys=(self.cid, self.hab.pre, oid), val=observed
                    )

    def watchControllers(self):
        """Launch a Sentinal for the controller AID if it is due for a check."""
        for (_, _), dater in self.db.cids.getItemIter(keys=(self.hab.pre, self.cid)):
            if self.cid not in self.sentinals:
                dtnow = helping.nowUTC()
                dte = helping.fromIso8601(dater.dts)
                if (dtnow - dte) > datetime.timedelta(seconds=self.CONTROLLERRETRY):
                    sentinal = Sentinal(
                        self.hby, self.hab, self.cid, self.cid, self.oobi, self.db
                    )
                    self.sentinals[self.cid] = sentinal
                    self.extend([sentinal])
                    self.db.cids.pin(
                        keys=(
                            self.hab.pre,
                            self.cid,
                        ),
                        val=coring.Dater(),
                    )


class WatcherStart(doing.Doer):
    """One-shot Doer that logs watcher identity after the Hab finishes initialising."""

    def __init__(self, hab):
        """
        Parameters:
            hab (Hab): Hab whose prefix will be logged once initialised
        """
        self.hab = hab
        super(WatcherStart, self).__init__()

    def recur(self, tyme=None):
        """Return True (done) once the Hab is initialised and its prefix has been logged."""
        if not self.hab.inited:
            return False

        logger.info(f"Watcher {self.hab.name} : {self.hab.pre}")
        return True


class MessageDoer(doing.Doer):
    """Doer that continuously drives a CESR Parser, processing inbound KERI messages."""

    def __init__(self, parser):
        """
        Parameters:
            parser (Parser): CESR event-stream parser to drive
        """
        self.parser = parser

        super(MessageDoer, self).__init__()

    def recur(self, tyme=None):
        """Yield from the parser's parsator loop until the connection closes."""
        logger.info("Watcher message processing loop ready")

        done = yield from self.parser.parsator(
            local=True
        )  # process messages continuously
        return done  # should never get here except on forced close


class EscrowDoer(doing.Doer):
    """Doer that drains pending escrows for all KERI message processors on each tick."""

    def __init__(self, kvy, rvy, tvy, exc=None):
        """
        Parameters:
            kvy (Kevery): key event log processor
            rvy (Revery): reply message processor
            tvy (Tevery): transaction event log processor
            exc (Exchanger | None): exchange message processor
        """
        self.kvy = kvy
        self.rvy = rvy
        self.tvy = tvy
        self.exc = exc

        super(EscrowDoer, self).__init__()

    def recur(self, tyme=None):
        """Process all pending escrows for kvy, rvy, tvy, and exc."""

        self.kvy.processEscrows()
        self.rvy.processEscrowReply()
        if self.tvy is not None:
            self.tvy.processEscrows()
        self.exc.processEscrow()

        return False


class CueDoer(doing.Doer):
    """Doer that classifies inbound cues and forwards appropriate replies to the response deck.

    Handles receipt/notice cues (forwards a signed KSN), replay cues (forwards
    log messages after verifying the AID is observed), and reply/ksn cues
    (forwards KSN replies for observed AIDs).
    """

    def __init__(self, db, hab, aid, cues, responses):
        """
        Parameters:
            db (Baser): watopnet LMDB database
            hab (Hab): Hab for this watcher's own AID
            aid (str): qb64 AID of the controller this watcher serves
            cues (Deck): incoming cue deck produced by the KERI event processors
            responses (Deck): outgoing response deck consumed by the transport layer
        """
        self.db = db
        self.hab = hab
        self.aid = aid
        self.cues = cues
        self.responses = responses

        super(CueDoer, self).__init__()

    def recur(self, tyme=None):
        """Drain all available cues and route each to the response deck or log."""
        while self.cues:
            cue = self.cues.pull()
            cueKin = cue["kin"]  # type or kind of cue
            route = cue["route"] if "route" in cue else None

            if cueKin in (
                "receipt",
                "notice",
            ):  # cue to receipt a received event from other pre
                cuedSerder = cue["serder"]  # Serder of received event for other pre
                oid = cuedSerder.pre
                if (
                    cid := self.hab.db.obvs.get(
                        keys=(
                            self.aid,
                            self.hab.pre,
                            oid,
                        )
                    )
                ) is not None:
                    kever = self.hab.kevers[oid]
                    ksr = kever.state()
                    rpy = eventing.reply(route=f"/ksn/{self.hab.pre}", data=asdict(ksr))
                    rep = dict(kin="reply", src=self.hab.pre, dest=self.aid, serder=rpy)
                    self.responses.append(rep)

                    logger.info(
                        f"watcher forwarding ksn for {cuedSerder.pre} at {cuedSerder.sn} to cid={cid}"
                    )

                else:
                    logger.info(
                        "watcher not receipting %s for evt said=%s",
                        cuedSerder.pre,
                        cuedSerder.said,
                    )

            if cueKin in ("stream",):  # cue to receipt a received event from other pre
                cuedSerder = cue["serder"]  # Serder of received event for other pre
                logger.info(
                    "watcher does not support streaming said=%s", cuedSerder.said
                )

            if cueKin in ("invalid",):  # cue to receipt a received event from other pre
                cuedSerder = cue["serder"]  # Serder of received event for other pre
                logger.info(
                    "invalid query route %s from said=%s",
                    cuedSerder.ked["r"],
                    cuedSerder.ked["t"],
                )

            elif cueKin in ("replay",):  # this is logs
                # For logs, watcher needs to ensure KSNs match and if so just yield back these messages
                pre = cue["pre"]
                if self.hab.db.obvs.get(keys=(self.aid, self.hab.pre, pre)) is None:
                    logger.info(f"watcher not replaying unknown aid {pre}")
                    continue

                self.responses.append(cue)

            elif cueKin in ("reply",) and route == "/ksn":
                # This is a KSN reply, watcher needs to check key state for all witnesses and craft a full reply
                serder = cue["serder"]
                if (
                    self.hab.db.obvs.get(keys=(self.aid, self.hab.pre, serder.pre))
                    is None
                ):
                    logger.info(
                        f"watcher not replying KSN for unknown aid {serder.pre}"
                    )
                    continue

                self.responses.append(cue)

        return False


class Sentinal(doing.DoDoer):
    """One-shot DoDoer that queries each of an observed AID's witnesses for key state.

    For each witness, issues a KSN query via ``Receiptor.ksn``, then compares the
    returned state against the local KEL using ``diffState``.  Detects even,
    behind, ahead, and duplicitous conditions and logs the results.  Extends
    itself with a ``SeqNoQuerier`` when witnesses are ahead of the local KEL.

    Persists per-witness query results to ``Baser.witq`` for later retrieval by
    ``WatcherStatusEnd``.
    """

    def __init__(self, hby, hab, oid, cid, oobi, db, **opts):
        """
        Parameters:
            hby (Habery): KERI keystore environment for this watcher
            hab (Hab): non-transferable Hab for this watcher's own AID
            oid (str): qb64 AID of the observed identifier to poll
            cid (str): qb64 AID of the controller on whose behalf the check is done
            oobi (str): OOBI URL of this watcher
            db (Baser): watopnet LMDB database for persisting query results
            **opts: additional keyword arguments forwarded to DoDoer
        """
        self.hby = hby
        self.hab = hab
        self.oid = oid
        self.cid = cid
        self.oobi = oobi
        self.db = db

        super(Sentinal, self).__init__(doers=[doing.doify(self.watch)], **opts)

    def watch(self, tymth, tock=0.0, **kwa):
        """Poll each witness of the observed AID and record the key-state comparison result.

        Parameters:
            tymth: injected tymist wrapper
            tock (float): scheduling interval injected by the Doist
        """
        # enter context
        self.wind(tymth)
        self.tock = tock
        _ = yield self.tock

        logger.info(
            f"Launching watcher {self.hab.pre} for {self.oid} on behalf of {self.cid}"
        )
        if self.oid not in self.hby.kevers:
            logger.info(f"Unable to watch unknown aid={self.oid}")
            return True  # We are done, time to exit

        kever = self.hby.kevers[self.oid]
        if len(kever.wits) == 0:
            logger.info(f"No witnesses for {self.oid} at {kever.sn}, skipping.")
            return True

        states = []
        queryTimestamp = helping.nowIso8601()

        for wit in kever.wits:
            keys = (self.oid, wit)
            witQuery = basing.WitnessQuery(
                watcher_id=self.hab.pre,
                aid=self.oid,
                wit=wit,
                query_timestamp=queryTimestamp,
                response_received=False,
                state=States.unresponsive,
            )

            # Check for Key State from this Witness and remove if exists
            saider = self.hab.db.knas.get(keys)
            if saider is not None:
                self.hab.db.knas.rem(keys)
                self.hab.db.ksns.rem((saider.qb64,))

            try:
                witer = agenting.messenger(self.hab, wit)
            except kering.ConfigurationError as ex:
                witQuery.error = f"Missing witness endpoint: {ex}"
                self.db.witq.pin(keys=(self.hab.pre, self.oid, wit), val=witQuery)
                continue
            self.extend([witer])

            msg = self.hab.query(pre=self.oid, src=wit, route="ksn")
            witer.msgs.append(bytearray(msg))

            sendTymer = tyming.Tymer(tymth=self.tymth, duration=10.0)
            while not witer.idle and not sendTymer.expired:
                yield self.tock

            self.remove([witer])

            saider = None
            responseTymer = tyming.Tymer(tymth=self.tymth, duration=10.0)
            while True:
                if (saider := self.hab.db.knas.get(keys)) is not None:
                    break

                if responseTymer.expired:
                    witQuery.error = "No response received within timeout"
                    self.db.witq.pin(keys=(self.hab.pre, self.oid, wit), val=witQuery)
                    break

                yield self.tock

            if saider is None:
                continue

            mystate = kever.state()
            witstate = self.hby.db.ksns.get((saider.qb64,))

            diffstate = self.diffState(wit, mystate, witstate)
            witQuery.response_received = True
            witQuery.state = diffstate.state
            witQuery.keystate = witstate
            witQuery.sn = diffstate.sn
            witQuery.dig = diffstate.dig

            self.db.witq.pin(keys=(self.hab.pre, self.oid, wit), val=witQuery)

            # TODO: store diffstate here!
            states.append(diffstate)

        # First check for any duplicity, if so get out of here
        dups = [state for state in states if state.state == States.duplicitous]
        ahds = [state for state in states if state.state == States.ahead]

        if len(dups) > 0:
            logger.info(f"{len(dups)} witnesses have a duplicitous event")
            for state in dups:
                logger.info(
                    f"Duplicitous witness state for {state.wit} at Seq No. {state.sn} with digest: {state.dig}"
                )
            return True

        elif len(ahds) > 0:
            # First check for duplicity among the witnesses that are ahead (possible only if toad is below
            # super majority)
            digs = set([state.dig for state in ahds])
            if len(digs) > 1:  # Duplicity across witness sets
                logger.info(
                    f"There are multiple duplicitous events on witnesses for {self.oid}"
                )
                return True

            else:  # all witnesses that are ahead agree on the event
                logger.info(
                    f"{len(ahds)} witnesses have an event that is ahead of the local KEL:"
                )

            state = random.choice(ahds)
            fn = self.hby.kevers[self.oid].sn + 1 if self.oid in self.hby.kevers else 0

            qry = querying.SeqNoQuerier(
                self.hby, self.hab, pre=self.oid, fn=fn, sn=state.sn
            )
            self.extend([qry])

        elif len(states) == 0:
            logger.info(f"Zero witnesses for {self.oid} responded.")
            return True
        else:
            state = random.choice(states)
            logger.info(
                f"Local key state for {self.oid} is consistent at seq no. {state.sn} with the "
                f"{len(states)} (out of {len(kever.wits)} total) witnesses that responded."
            )
            return True

    @staticmethod
    def diffState(wit, preksn, witksn):
        """Compare the watcher's local key state against a witness's reported key state.

        Parameters:
            wit (str): qb64 AID of the witness being compared
            preksn: local key state notice (from ``kever.state()``)
            witksn: witness key state notice (from ``hby.db.ksns``)

        Returns:
            WitnessState: result with ``state`` set to one of
                ``States.even``, ``States.behind``, ``States.ahead``, or
                ``States.duplicitous``, plus the witness's ``sn`` and ``dig``
        """
        witstate = WitnessState()
        witstate.wit = wit
        mysn = int(preksn.s, 16)
        mydig = preksn.d
        witstate.sn = int(witksn.f, 16)
        witstate.dig = witksn.d

        # At the same sequence number, check the DIGs
        if mysn == witstate.sn:
            if mydig == witstate.dig:
                witstate.state = States.even
            else:
                witstate.state = States.duplicitous

        # This witness is behind and will need to be caught up.
        elif mysn > witstate.sn:
            witstate.state = States.behind

        # mysn < witstate.sn - We are behind this witness (multisig or restore situation).
        # Must ensure that controller approves this event or a recovery rotation is needed
        else:
            witstate.state = States.ahead

        return witstate


class WatcherCollectionEnd:
    """Boot API endpoint for provisioning new watcher instances (``POST /watchers``)."""

    def __init__(self, wty: Watchery):
        """
        Parameters:
            wty (Watchery): watcher registry
        """
        self.wty = wty

    def on_post(self, req, rep):
        """Provision a new watcher for the supplied controller AID.

        Body fields:
            aid (str): required — qb64 AID of the controller to be watched
            oobi (str): optional — OOBI URL for the controller; if provided, queued for resolution

        Returns a JSON object with ``cid``, ``eid``, and ``oobis`` for the new watcher.

        Parameters:
            req (Request): Falcon HTTP request object
            rep (Response): Falcon HTTP response object
        """
        body = req.get_media()
        aid = httping.getRequiredParam(body, "aid")
        oobi = body.get("oobi")

        try:
            prefixer = coring.Prefixer(qb64=aid)
        except Exception as e:
            raise falcon.HTTPBadRequest(
                description=f"invalid AID for witnessing: {e.args[0]}"
            )

        try:
            watcher = self.wty.createWatcher(cid=aid)
        except kering.ConfigurationError as e:
            raise falcon.HTTPBadRequest(description=e.args[0])

        if oobi:
            watcher.hby.db.oobis.pin(
                keys=(oobi,), val=OobiRecord(date=help.nowIso8601())
            )

        oobis = watcher.oobis()

        data = dict(cid=prefixer.qb64, eid=watcher.hab.pre, oobis=oobis)
        rep.status = falcon.HTTP_200
        rep.content_type = "application/json"
        rep.data = json.dumps(data).encode("utf-8")


class WatcherResourceEnd:
    """Boot API endpoint for removing a running watcher instance (``DELETE /watchers/{eid}``)."""

    def __init__(self, wty: Watchery):
        """
        Parameters:
            wty (Watchery): watcher registry
        """
        self.wty = wty

    def on_delete(self, _, rep, eid):
        """Delete a running watcher. This operation is not reversible.

        Parameters:
            _ (Request): Falcon HTTP request object (unused)
            rep (Response): Falcon HTTP response object
            eid (str): qb64 AID (endpoint identifier) of the watcher to delete
        """
        try:
            coring.Prefixer(qb64=eid)
        except Exception as e:
            raise falcon.HTTPBadRequest(
                description=f"invalid AID for a watcher: {e.args[0]}"
            )

        try:
            self.wty.deleteWatcher(eid=eid)
        except kering.ConfigurationError as e:
            raise falcon.HTTPBadRequest(description=e.args[0])

        rep.status = falcon.HTTP_204


class WatcherStatusEnd:
    """Boot API endpoint for retrieving watcher status (``GET /watchers/{eid}/status``).

    Returns the full set of observed AIDs and the most recent per-witness key-state
    query results stored in ``Baser.witq``.
    """

    def __init__(self, wty: Watchery):
        """
        Parameters:
            wty (Watchery): watcher registry
        """
        self.wty = wty

    def on_get(self, req, rep, eid):
        """Return status for the watcher identified by ``eid``.

        Parameters:
            req (Request): Falcon HTTP request object
            rep (Response): Falcon HTTP response object
            eid (str): qb64 AID of the watcher whose status is requested
        """

        try:
            coring.Prefixer(qb64=eid)
        except Exception as e:
            raise falcon.HTTPBadRequest(description=f"invalid watcher EID: {e.args[0]}")

        watcher = self.wty.lookup(eid)
        if not watcher:
            raise falcon.HTTPNotFound(description=f"No watcher found with EID: {eid}")

        status_data = {
            "watcher_id": eid,
            "controller_id": watcher.cid,
            "aids": {},
            "summary": {
                "total_aids": 0,
                "total_witnesses": 0,
                "responsive_witnesses": 0,
                "last_query_time": None,
            },
        }

        aids_data = {}
        latest_query_time = None

        for (watcher_id, aid, wit), query_record in watcher.db.witq.getItemIter(
            keys=(eid,)
        ):

            if watcher_id != eid:
                continue

            if aid not in aids_data:
                aids_data[aid] = {
                    "aid": aid,
                    "witnesses": {},
                    "witness_summary": {
                        "total": 0,
                        "responsive": 0,
                        "states": {
                            "even": 0,
                            "ahead": 0,
                            "behind": 0,
                            "duplicitous": 0,
                            "unresponsive": 0,
                        },
                    },
                }

            witness_data = {
                "witness_id": wit,
                "last_query_timestamp": query_record.query_timestamp,
                "response_received": query_record.response_received,
                "state": query_record.state,
                "keystate": query_record.keystate,
                "sequence_number": query_record.sn,
                "digest": query_record.dig,
                "error": query_record.error,
            }

            aids_data[aid]["witnesses"][wit] = witness_data
            aids_data[aid]["witness_summary"]["total"] += 1

            if query_record.response_received:
                aids_data[aid]["witness_summary"]["responsive"] += 1
                status_data["summary"]["responsive_witnesses"] += 1

            if query_record.state in aids_data[aid]["witness_summary"]["states"]:
                aids_data[aid]["witness_summary"]["states"][query_record.state] += 1

            status_data["summary"]["total_witnesses"] += 1

            if (
                not latest_query_time
                or query_record.query_timestamp > latest_query_time
            ):
                latest_query_time = query_record.query_timestamp

        status_data["aids"] = aids_data
        status_data["summary"]["total_aids"] = len(aids_data)
        status_data["summary"]["last_query_time"] = latest_query_time

        rep.status = falcon.HTTP_200
        rep.content_type = "application/json"
        rep.data = json.dumps(status_data, indent=2).encode("utf-8")
