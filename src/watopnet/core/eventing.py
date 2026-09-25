# -*- encoding: utf-8 -*-

"""
KERI
watopnet.core.eventing module

Watcher query processing built on ``keri.core.eventing.Kevery``.

``QueryKevery`` inherits KERI's message processing and overrides only the
watcher-specific query policy. ``QueryRouter`` is the small TCP-side router that
selects the watcher a query names; both transports share one implementation.
"""

from hio.help import decking
from keri import help, kering
from keri.core import eventing

logger = help.ogler.getLogger()
DEFAULT_REPLY_VERSION = kering.Vrsn_2_0


class QueryKevery(eventing.Kevery):
    """Watcher-bound Kevery that inherits KERI's message processing.

    A watcher answers queries for exactly one identifier, so this subclass
    inherits ``keri.core.eventing.Kevery.processMsg`` unchanged and overrides
    only the watcher-specific query policy:

    - the requester must present an authenticated source
    - that source must be the watcher's configured controller AID
    - key state is looked up in the watcher's own database

    Keripy answers a ``ksn`` query using the *requester's* version and kind and
    stamps the reply with ``pre = q.i``. A watcher must always answer with a V2
    JSON reply attributed to the watcher's own AID, so that reply framing is the
    one watcher-specific transformation applied here.
    """

    def __init__(self, watcher, cues=None):
        """
        Parameters:
            watcher (Watcher): watcher instance whose state answers the query
            cues (Deck | None): deck that receives reply and replay cues
        """
        super().__init__(
            cues=cues if cues is not None else decking.Deck(),
            db=watcher.hab.db,
            local=False,
        )
        self.watcher = watcher

    def processQuery(self, serder, *, source=None, sigers=None, cigars=None, **kwa):
        """Authorize the requester, then let KERI process the query.

        Parameters:
            serder (SerderKERI): query message serder
            source (Prefixer | None): authenticated requester prefix
            sigers (list[Siger] | None): attached controller-indexed signatures
            cigars (list[Cigar] | None): attached non-transferable signatures
            **kwa: remaining parser attachment keys, forwarded to KERI
        """
        if source is None:
            logger.error("Query received without an authenticated controller source")
            return

        if source.qb64 != self.watcher.cid:
            logger.error(
                f"Query received from invalid controller: {source.qb64} != {self.watcher.cid}"
            )
            return

        self._processQueryV2Reply(
            serder, source=source, sigers=sigers, cigars=cigars, **kwa
        )

    def _processQueryV2Reply(self, serder, *, source, sigers, cigars, **kwa):
        """Run inherited query processing and normalize the watcher's reply framing.

        KERI's cues are captured in a local deck so that only the cues produced by
        this query are re-framed; the shared deck still receives every cue.
        """
        local_cues = decking.Deck()
        shared_cues = self.cues
        self.cues = local_cues
        try:
            super().processQuery(
                serder, source=source, sigers=sigers, cigars=cigars, **kwa
            )
        finally:
            self.cues = shared_cues

        while local_cues:
            shared_cues.push(self._watcherReply(local_cues.pull()))

    def _watcherReply(self, cue):
        """Return ``cue`` unchanged, or re-framed as a V2 JSON watcher reply."""
        if cue.get("kin") != "reply" or cue.get("route") != "/ksn":
            return cue

        reply = cue["serder"]
        # Keripy answers a ``ksn`` query with ``pre = q.i`` and mirrors the requester's
        # version and kind, so an incoming V2 JSON reply can already be correctly framed
        # while still being attributed to the queried AID. Only a reply that is already
        # addressed by the watcher may pass through unchanged.
        if (
            reply.pvrsn == DEFAULT_REPLY_VERSION
            and reply.kind == eventing.Kinds.json
            and reply.ked["i"] == self.watcher.hab.pre
        ):
            return cue

        updated = dict(cue)
        updated["serder"] = eventing.reply(
            pre=self.watcher.hab.pre,
            route=reply.ked["r"],
            data=reply.ked["a"],
            stamp=reply.ked.get("dt"),
            version=DEFAULT_REPLY_VERSION,
            pvrsn=DEFAULT_REPLY_VERSION,
            kind=eventing.Kinds.json,
        )
        return updated


class QueryRouter:
    """Minimal router that selects the watcher a query names via ``q.src``.

    The TCP listener carries no transport-level destination, unlike the HTTP
    ``CESR-Destination`` header, so it must pick a watcher before a ``QueryKevery``
    can process the message. This router performs only that selection and then
    delegates to the shared implementation; it holds no query policy, no
    authorization, and no reply construction of its own.
    """

    def __init__(self, wty, cues=None):
        """
        Parameters:
            wty (Watchery): registry of active watcher instances used for lookup
            cues (Deck | None): deck shared with the transport's reply loop
        """
        self.wty = wty
        self.cues = cues if cues is not None else decking.Deck()

    def processMsg(self, kwa=None):
        """Route a V2 non-key-event message; only queries name a watcher.

        Parameters:
            kwa (dict | None): parser attachment dict containing ``serder``
        """
        serder = (kwa or {}).get("serder")
        if serder is None or serder.ilk != kering.Ilks.qry:
            return

        watcher = self._watcherFor(serder)
        if watcher is None:
            return

        QueryKevery(watcher=watcher, cues=self.cues).processMsg(kwa)

    def processQuery(self, serder, **kwa):
        """Route a V1-framed query through the same shared implementation.

        Parameters:
            serder (SerderKERI): query message serder
            **kwa: parser attachment keys, forwarded unchanged
        """
        watcher = self._watcherFor(serder)
        if watcher is None:
            return

        QueryKevery(watcher=watcher, cues=self.cues).processQuery(serder, **kwa)

    def _watcherFor(self, serder):
        """Return the watcher named by ``q.src``, or ``None`` when unroutable."""
        query = serder.sad.get("q") or {}
        wid = query.get("src")
        if not wid:
            logger.error(f"invalid query={serder.sad}, missing src in q")
            return None

        watcher = self.wty.lookup(wid)
        if not watcher:
            logger.error(f"Query received for invalid watcher={wid}")
            return None

        return watcher
