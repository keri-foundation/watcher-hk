# -*- encoding: utf-8 -*-

"""
KERI
watopnet.core.httping module

HTTP endpoint and throttle middleware for the watcher server.
"""

import datetime

import falcon
from keri.app import httping
from keri.app.httping import CESR_DESTINATION_HEADER
from keri.core import eventing, coring, parsing
from keri.help import helping
from keri.kering import Ilks

from watopnet.core import basing
from watopnet.core.eventing import QueryKeveryShim


class HttpEnd:
    """HTTP endpoint that accepts KERI events posted with CESR attachment headers.

    Handles POST (single event) and PUT (raw CESR stream) on ``/``.  Incoming
    events are routed to the watcher identified by the ``CESR-Destination`` header.
    KEL, EXN, and RPY messages are parsed and stored; QRY messages are answered
    inline via ``QueryKeveryShim``.
    """

    def __init__(self, wty, rxbs=None):
        """
        Parameters:
            wty (Watchery): registry of active watcher instances
            rxbs (bytearray | None): optional shared inbound byte buffer
        """
        self.wty = wty
        self.rxbs = rxbs if rxbs is not None else bytearray()

    def on_post(self, req, rep):
        """Accept a KERI event with CESR attachment headers and route it to the target watcher.

        The ``CESR-Destination`` header must name a provisioned watcher AID.
        KEL/EXN/RPY messages are parsed into the watcher's keystore (204).
        QRY messages are answered synchronously and the reply is returned (200),
        or 204 if no cue was produced.

        Parameters:
            req (Request): Falcon HTTP request object
            rep (Response): Falcon HTTP response object

        ---
        summary: Accept KERI events with attachment headers and parse
        description: Accept KERI events with attachment headers and parse.
        tags:
           - Events
        requestBody:
           required: true
           content:
             application/json:
               schema:
                 type: object
                 description: KERI event message
        responses:
           200:
              description: QRY reply returned inline
           204:
              description: KEL or EXN event accepted
        """
        if req.method == "OPTIONS":
            rep.status = falcon.HTTP_200
            return

        if CESR_DESTINATION_HEADER not in req.headers:
            raise falcon.HTTPBadRequest(title="CESR request destination header missing")

        aid = req.headers[CESR_DESTINATION_HEADER]
        watcher = self.wty.lookup(aid)
        if watcher is None:
            raise falcon.HTTPNotFound(title=f"unknown destination AID {aid}")

        rep.set_header("Cache-Control", "no-cache")
        rep.set_header("connection", "close")

        cr = httping.parseCesrHttpRequest(req=req)
        sadder = coring.Sadder(ked=cr.payload, kind=eventing.Kinds.json)
        msg = bytearray(sadder.raw)
        msg.extend(cr.attachments.encode("utf-8"))

        if sadder.proto in ("ACDC",):
            rep.set_header("Content-Type", "application/json")
            rep.status = falcon.HTTP_UNPROCESSABLE_ENTITY
        else:
            ilk = sadder.ked["t"]
            if ilk in (
                Ilks.icp,
                Ilks.rot,
                Ilks.ixn,
                Ilks.dip,
                Ilks.drt,
                Ilks.exn,
                Ilks.rpy,
            ):
                watcher.psr.parseOne(ims=msg, local=True)

                rep.set_header("Content-Type", "application/json")
                rep.status = falcon.HTTP_204
            elif ilk in (Ilks.vcp, Ilks.vrt, Ilks.iss, Ilks.rev, Ilks.bis, Ilks.brv):
                rep.set_header("Content-Type", "application/json")
                rep.status = falcon.HTTP_UNPROCESSABLE_ENTITY

            elif ilk in (Ilks.qry,):
                kvy = QueryKeveryShim(watcher=watcher)
                parsing.Parser(kvy=kvy).parseOne(ims=msg, local=False)

                if not kvy.cues:
                    rep.set_header("Content-Type", "application/json")
                    rep.status = falcon.HTTP_204
                    return

                for cue in kvy.cues:
                    cueKin = cue["kin"]

                    if cueKin in ("replay",):
                        msgs = cue["msgs"]
                        data = bytearray()
                        for msg in msgs:
                            data.extend(msg)

                        rep.set_header("Content-Type", "application/json+cesr")
                        rep.status = falcon.HTTP_200
                        rep.data = bytes(data)

                    elif cueKin in ("reply",):
                        serder = cue["serder"]
                        msg = watcher.hab.endorse(serder=serder)
                        rep.set_header("Content-Type", "application/json+cesr")
                        rep.status = falcon.HTTP_200
                        rep.data = msg

    def on_put(self, req, rep):
        """Accept raw CESR bytes and push them into the target watcher's inbound stream.

        The ``CESR-Destination`` header must name a provisioned watcher AID.

        Parameters:
            req (Request): Falcon HTTP request object
            rep (Response): Falcon HTTP response object

        ---
        summary: Push raw CESR bytes into the watcher's inbound stream
        description: Accept KERI events with attachment headers and parse.
        tags:
           - Events
        requestBody:
           required: true
           content:
             application/json:
               schema:
                 type: object
                 description: KERI event message
        responses:
           204:
              description: bytes accepted
        """
        if req.method == "OPTIONS":
            rep.status = falcon.HTTP_200
            return

        rep.set_header("Cache-Control", "no-cache")
        rep.set_header("connection", "close")

        if CESR_DESTINATION_HEADER not in req.headers:
            raise falcon.HTTPBadRequest(title="CESR request destination header missing")

        aid = req.headers[CESR_DESTINATION_HEADER]
        watcher = self.wty.lookup(aid)
        if watcher is None:
            raise falcon.HTTPNotFound(title=f"unknown destination AID {aid}")

        watcher.psr.parse(ims=req.bounded_stream.read(), local=True)

        rep.set_header("Content-Type", "application/json")
        rep.status = falcon.HTTP_204


def getRequiredParam(body, name):
    """Extract a required field from a parsed request body dict.

    Parameters:
        body (dict): parsed JSON request body
        name (str): field name to extract

    Returns:
        object: the field value

    Raises:
        falcon.HTTPBadRequest: if the field is absent or None
    """
    param = body.get(name)
    if param is None:
        raise falcon.HTTPBadRequest(
            description=f"required field '{name}' missing from request"
        )

    return param


class Throttle(object):
    """Falcon middleware that rate-limits requests by client IP address.

    Allows at most ``MaximumRequests`` requests per IP within a ``Window``
    time window. Requests that exceed the limit receive 429 Too Many Requests
    and bypass all further Falcon processing.
    """

    Window = datetime.timedelta(seconds=10)
    MaximumRequests = 100

    def __init__(self, db):
        """
        Parameters:
            db (Baser): watopnet database used to persist per-IP request counts
        """
        self.db = db

    def process_request(self, req, resp):
        """Check and update the request count for the client IP; reject if over limit.

        Parameters:
            req (Request): Falcon HTTP request object
            resp (Response): Falcon HTTP response object
        """
        client = req.access_route[0]
        ip = client[0]
        now = helping.nowUTC()

        reqs = self.db.ips.get(keys=(ip,))
        if reqs is None:
            reqs = basing.Requests(helping.toIso8601(now), 1)
        else:
            dt = helping.fromIso8601(reqs.dt)
            if now - dt < self.Window:
                if reqs.count >= self.MaximumRequests:
                    resp.complete = True
                    resp.status = falcon.HTTP_TOO_MANY_REQUESTS
                    return
                reqs.count += 1
            else:
                reqs = basing.Requests(helping.toIso8601(now), 1)

        self.db.ips.pin(ip, reqs)
