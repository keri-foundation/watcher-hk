# -*- encoding: utf-8 -*-

"""
KERI
watopnet.core.eventing module

Kevery shims that restrict event processing to query messages only,
routing each query to the appropriate watcher instance.
"""

from hio.help import decking
from keri import help
from keri.core import eventing

logger = help.ogler.getLogger()


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

        if not source.qb64 == watcher.cid:
            logger.error(
                f"Query received from invalid controller: {source.qb64} != {watcher.cid}"
            )
            return

        kvy = eventing.Kevery(db=watcher.hab.db, local=False, cues=self.cues)
        kvy.processQuery(serder=serder, source=source, sigers=sigers, cigars=cigars)


class QueryKeveryShim:
    """Kevery adapter for the HTTP layer that restricts processing to a single watcher.

    Exposes only ``processQuery``; all other event types are silently dropped.
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

    def processQuery(self, serder, source=None, sigers=None, cigars=None):
        """Process an incoming query if the source matches this watcher's controller.

        Parameters:
            serder (SerderKERI): query message serder
            source (Prefixer): identifier prefix of the querier
            sigers (list[Siger] | None): attached controller-indexed signatures
            cigars (list[Cigar] | None): attached non-transferable signatures
        """
        if not source.qb64 == self.watcher.cid:
            logger.error(
                f"Query received from invalid controller: {source.qb64} != {self.watcher.cid}"
            )
            return

        kvy = eventing.Kevery(db=self.watcher.hab.db, local=False, cues=self.cues)
        kvy.processQuery(serder=serder, source=source, sigers=sigers, cigars=cigars)
