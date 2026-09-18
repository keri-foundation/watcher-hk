# -*- encoding: utf-8 -*-

"""
KERI
testing watopnet.core.httping module

"""
from types import SimpleNamespace

import falcon
import pytest
from keri import kering
from keri.app.httping import CESR_DESTINATION_HEADER
from keri.core import eventing

from watopnet.core import httping as wat_httping

CONTROLLER_AID = "ENsqL5zLYNbZf0kcOlx-ioqNWlatD9rKZZM4hbEI7nza"
WATCHER_AID = "BGbLRtLXIslZvTfYz97dS9_EzQxp8kSTAMMtW-LmlXMI"


class Response:
    def __init__(self):
        self.headers = {}
        self.status = None
        self.content_type = None
        self.data = None

    def set_header(self, name, value):
        self.headers[name] = value


def test_http_post_maps_event_parser_errors_to_bad_request(monkeypatch):
    serder = eventing.reply(route="/watcher/add", data={})
    monkeypatch.setattr(
        wat_httping.httping,
        "parseCesrHttpRequest",
        lambda req: SimpleNamespace(payload=serder.ked, attachments=""),
    )

    def fail_parse_one(**kwa):
        raise kering.ValidationError("bad event")

    watcher = SimpleNamespace(
        cid=CONTROLLER_AID,
        hab=SimpleNamespace(),
        psr=SimpleNamespace(parseOne=fail_parse_one),
    )
    wty = SimpleNamespace(lookup=lambda aid: watcher if aid == WATCHER_AID else None)
    req = SimpleNamespace(
        method="POST",
        headers={CESR_DESTINATION_HEADER: WATCHER_AID},
    )
    rep = Response()

    with pytest.raises(falcon.HTTPBadRequest) as exc:
        wat_httping.HttpEnd(wty=wty).on_post(req, rep)

    assert "invalid KERI message" in exc.value.description


def test_http_post_maps_query_parser_errors_to_bad_request(monkeypatch):
    serder = eventing.query(
        route="ksn",
        query={"pre": CONTROLLER_AID, "src": WATCHER_AID},
    )
    monkeypatch.setattr(
        wat_httping.httping,
        "parseCesrHttpRequest",
        lambda req: SimpleNamespace(payload=serder.ked, attachments=""),
    )

    class FailingParser:
        def __init__(self, **kwa):
            pass

        def parseOne(self, ims, local=False):
            raise kering.ValidationError("bad query")

    monkeypatch.setattr(wat_httping.parsing, "Parser", FailingParser)

    watcher = SimpleNamespace(cid=CONTROLLER_AID, hab=SimpleNamespace())
    wty = SimpleNamespace(lookup=lambda aid: watcher if aid == WATCHER_AID else None)
    req = SimpleNamespace(
        method="POST",
        headers={CESR_DESTINATION_HEADER: WATCHER_AID},
    )
    rep = Response()

    with pytest.raises(falcon.HTTPBadRequest) as exc:
        wat_httping.HttpEnd(wty=wty).on_post(req, rep)

    assert "invalid KERI query" in exc.value.description


def test_http_put_maps_parser_errors_to_bad_request():
    serder = eventing.reply(route="/watcher/add", data={})

    def fail_parse(**kwa):
        raise kering.ValidationError("bad stream")

    watcher = SimpleNamespace(psr=SimpleNamespace(parse=fail_parse))
    wty = SimpleNamespace(lookup=lambda aid: watcher if aid == WATCHER_AID else None)
    req = SimpleNamespace(
        method="PUT",
        headers={CESR_DESTINATION_HEADER: WATCHER_AID},
        bounded_stream=SimpleNamespace(read=lambda: serder.raw),
    )
    rep = Response()

    with pytest.raises(falcon.HTTPBadRequest) as exc:
        wat_httping.HttpEnd(wty=wty).on_put(req, rep)

    assert "invalid KERI stream" in exc.value.description