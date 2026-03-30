# -*- encoding: utf-8 -*-

"""
KERI
watopnet.core.oobing module

OOBI (Out-of-Band Introduction) endpoint for the watcher server.
"""

import falcon
from keri import kering
from keri.end import ending


class OOBIEnd:
    """GET endpoint for resolving watcher OOBI requests (``/oobi/{aid}[/{role}[/{eid}]]``).

    Looks up the watcher for the requested AID, verifies the AID is fully witnessed,
    and returns a signed OOBI reply message in ``application/json+cesr`` format.
    Falls back to a witness-role OOBI plus a KEL replay when no role is specified.
    """

    def __init__(self, wty, default=None):
        """
        Parameters:
            wty (Watchery): registry of active watcher instances
            default (str | None): qb64 AID to use when no ``aid`` path parameter is given
        """
        self.wty = wty
        self.default = default

    def on_get(self, req, rep, aid=None, role=None, eid=None):
        """Return the OOBI reply for the requested AID, role, and optional participant EID.

        Parameters:
            req (Request): Falcon HTTP request object
            rep (Response): Falcon HTTP response object
            aid (str | None): qb64 AID whose OOBI is requested; falls back to ``default``
            role (str | None): requested role for the OOBI reply message
            eid (str | None): qb64 AID of the participant in the requested role

        Raises:
            falcon.HTTPNotFound: if no default AID is configured, the AID is unknown
                to this node, or the AID is not yet fully witnessed
            falcon.HTTPNotAcceptable: if the AID is known but not owned by this node
        """
        if aid is None:
            if self.default is None:
                raise falcon.HTTPNotFound(description="no blind oobi for this node")

            aid = self.default

        watcher = self.wty.lookup(aid)
        if watcher is None:
            raise falcon.HTTPNotFound(description=f"aid {aid} not found")

        if aid not in watcher.hby.kevers:
            raise falcon.HTTPNotFound(description=f"aid {aid} not found")

        kever = watcher.hby.kevers[aid]
        if not watcher.hby.db.fullyWitnessed(kever.serder):
            raise falcon.HTTPNotFound(description=f"aid {aid} not found")

        if kever.prefixer.qb64 in watcher.hby.prefixes:
            hab = watcher.hby.habs[kever.prefixer.qb64]
        else:
            raise falcon.HTTPNotAcceptable(description="invalid OOBI request")

        eids = []
        if eid:
            eids.append(eid)

        msgs = hab.replyToOobi(aid=aid, role=role, eids=eids)
        if not msgs and role is None:
            msgs = hab.replyToOobi(aid=aid, role=kering.Roles.witness, eids=eids)
            msgs.extend(hab.replay(aid))

        if msgs:
            rep.status = falcon.HTTP_200
            rep.set_header(ending.OOBI_AID_HEADER, aid)
            rep.content_type = "application/json+cesr"
            rep.data = bytes(msgs)

        else:
            rep.status = falcon.HTTP_NOT_FOUND
