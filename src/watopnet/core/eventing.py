# -*- encoding: utf-8 -*-

"""
KERI
watopnet.core.eventing module

Kevery shims that restrict event processing to query messages only,
routing each query to the appropriate watcher instance.
"""

from hio.help import decking
from keri import help, kering
from keri.core import eventing

logger = help.ogler.getLogger()
DEFAULT_REPLY_VERSION = kering.Vrsn_2_0


def _processQueryFixedV2(*, db, cues, serder, source, sigers, cigars, reply_pre):
    """Delegate query processing to KERI and normalize KSN replies into v2 JSON messages."""

    # Create a local deck to capture cues from the Kevery
    local_cues = decking.Deck()
    kvy = eventing.Kevery(db=db, local=False, cues=local_cues)
    kvy.processQuery(serder=serder, source=source, sigers=sigers, cigars=cigars)

    # Iterate the cues produced for normalization
    while local_cues:
        cue = local_cues.pull()

        # Check if the cue is a KSN reply, if not push it and continue
        if cue.get("kin") != "reply" or cue.get("route") != "/ksn":
            cues.push(cue)
            continue

        # Check that the reply is already in the split-transport body format
        reply = cue["serder"]
        if (
            reply.pvrsn == DEFAULT_REPLY_VERSION
            and reply.kind == eventing.Kinds.json
        ):
            cues.push(cue)
            continue

        # Normalize the reply into a v2 JSON message and push it
        updated = dict(cue)
        updated["serder"] = eventing.reply(
            pre=reply_pre,
            route=reply.ked["r"],
            data=reply.ked["a"],
            stamp=reply.ked.get("dt"),
            version=DEFAULT_REPLY_VERSION,
            pvrsn=DEFAULT_REPLY_VERSION,
            kind=eventing.Kinds.json,
        )
        cues.push(updated)


class KeveryQueryShim:
    """Kevery adapter for the TCP layer that routes incoming queries to the correct watcher.

    Exposes only ``processQuery``; all other event types are silently dropped.
    Validates that the query names a known watcher via ``q.src`` and that the
    querying source matches that watcher's authorised controller AID.
    """

    def __init__(self, wty, cues=None):
        """
        Parameters:
            wty (Watchery): registry of active watcher instances used for lookup
            cues (Deck | None): deck to receive reply cues from the underlying Kevery
        """
        self.wty = wty
        self.cues = cues if cues is not None else decking.Deck()

    def processQuery(self, serder, source=None, sigers=None, cigars=None):
        """Route an incoming query to the watcher named in ``q.src``.

        Looks up the target watcher from the ``src`` field in the query body,
        verifies that the querying source matches the watcher's controller AID,
        then delegates to a fresh ``Kevery.processQuery``.

        Parameters:
            serder (SerderKERI): query message serder
            source (Prefixer): identifier prefix of the querier
            sigers (list[Siger] | None): attached controller-indexed signatures
            cigars (list[Cigar] | None): attached non-transferable signatures
        """
        query = serder.sad["q"]

        if not query or "src" not in query:
            logger.error(f"invalid query={serder.sad}, missing src in q")
            return

        wid = query["src"]
        watcher = self.wty.lookup(wid)

        if not watcher:
            logger.error(f"Query received for invalid watcher={wid}")
            return

        if source is None:
            logger.error("Query received without an authenticated controller source")
            return

        if source.qb64 != watcher.cid:
            logger.error(
                f"Query received from invalid controller: {source.qb64} != {watcher.cid}"
            )
            return

        _processQueryFixedV2(
            db=watcher.hab.db,
            cues=self.cues,
            serder=serder,
            source=source,
            sigers=sigers,
            cigars=cigars,
            reply_pre=watcher.hab.pre,
        )


class QueryKeveryShim:
    """Kevery adapter for the HTTP layer that restricts processing to a single watcher.

    Exposes ``processMsg`` (the f4b9 V2 parser dispatch entry point for query
    messages) and ``processQuery``; all other event types are silently dropped.
    Validates that the querying source matches the watcher's authorised controller AID.
    """

    def __init__(self, watcher, cues=None):
        """
        Parameters:
            watcher (Watcher): the watcher instance that will handle the query
            cues (Deck | None): deck to receive reply cues from the underlying Kevery
        """
        self.watcher = watcher
        self.cues = cues if cues is not None else decking.Deck()

    def processMsg(self, kwa=None):
        """Process one non-key-event KERI message, dispatching only ``qry`` messages.

        f4b9's Parser routes V2 query messages through this consolidated entry
        point (the same one a real Kevery uses). The source and controller
        sigers are recovered from the attached signature groups (``lsgs``) or,
        failing that, the query's own ``i`` field, mirroring
        ``keri.core.eventing.Kevery.processMsg``. All other message types are
        dropped because this shim only answers queries for its one watcher.

        Parameters:
            kwa (dict | None): parser attachment dict containing ``serder``,
                ``sigers``, ``cigars``, ``lsgs``, ``local``, etc.
        """
        kwa = dict(kwa or {})
        serder = kwa.pop("serder", None)
        if serder is None:
            raise kering.ValidationError("Missing serder for message processing.")

        if serder.ilk != kering.Ilks.qry:
            # This shim only answers queries; other non-key-event types are
            # silently dropped (they belong to a different watcher surface).
            return

        kwa.setdefault("sigers", [])
        if kwa.get("lsgs"):
            # last signature groups carry the querier's prefix + controller sigs
            pre, sigers = kwa["lsgs"][-1]
            kwa["source"] = pre
            kwa["sigers"] = sigers
        elif kwa["sigers"] and not kwa.get("source"):
            kwa["source"] = eventing.Prefixer(qb64=serder.pre)

        if not (kwa.get("source") or kwa.get("cigars", [])):
            raise kering.ValidationError(
                f"Missing attached requester source for query msg = {serder.pretty()}."
            )

        route = serder.ked["r"]
        if route in ("logs", "ksn", "mbx"):
            self.processQuery(
                serder,
                source=kwa.get("source"),
                sigers=kwa.get("sigers"),
                cigars=kwa.get("cigars"),
            )
        # Other query routes (tels/tsn) target TEL state, which this watcher
        # does not serve; they are dropped here.

    def processQuery(self, serder, source=None, sigers=None, cigars=None):
        """Process an incoming query if the source matches this watcher's controller.

        Parameters:
            serder (SerderKERI): query message serder
            source (Prefixer): identifier prefix of the querier
            sigers (list[Siger] | None): attached controller-indexed signatures
            cigars (list[Cigar] | None): attached non-transferable signatures
        """
        if source is None:
            logger.error("Query received without an authenticated controller source")
            return

        if source.qb64 != self.watcher.cid:
            logger.error(
                f"Query received from invalid controller: {source.qb64} != {self.watcher.cid}"
            )
            return

        _processQueryFixedV2(
            db=self.watcher.hab.db,
            cues=self.cues,
            serder=serder,
            source=source,
            sigers=sigers,
            cigars=cigars,
            reply_pre=self.watcher.hab.pre,
        )
