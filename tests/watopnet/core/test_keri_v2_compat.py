# -*- encoding: utf-8 -*-

import datetime
import importlib
import json
from types import SimpleNamespace

import falcon
import pytest
from falcon import testing
from hio.help import decking
from keri import kering
from keri.app import habbing
from keri.app.httping import CESR_DESTINATION_HEADER
from keri.core import coring, eventing
from keri.db.basing import ObservedRecord

from watopnet.app import watching
from watopnet.app.watching import Sentinal, SentinalDoer, States, Watcher, Watchery
from watopnet.core import basing
from watopnet.core import eventing as wat_eventing
from watopnet.core import httping as wat_httping
from watopnet.core import oobing as wat_oobing
from watopnet.core.tcp.serving import Reactant

CONTROLLER_AID = "ENsqL5zLYNbZf0kcOlx-ioqNWlatD9rKZZM4hbEI7nza"
OBSERVED_AID = "ELiJTS4bBx5gZlT68OjBxFiirP0Qa2XQZ6V5cjHWQR0p"
WATCHER_AID = "BGbLRtLXIslZvTfYz97dS9_EzQxp8kSTAMMtW-LmlXMI"
OLD_TIMESTAMP = "2000-01-01T00:00:00.000000+00:00"


class Response:
    def __init__(self):
        self.headers = {}
        self.status = None
        self.content_type = None
        self.data = None

    def set_header(self, name, value):
        self.headers[name] = value


def test_package_imports_under_keri_v2():
    modules = [
        "watopnet.app.watching",
        "watopnet.core.basing",
        "watopnet.core.httping",
        "watopnet.core.tcp.serving",
        "watopnet.core.oobing",
        "watopnet.core.eventing",
        "watopnet.app.cli.watcher",
        "watopnet.app.cli.commands.start",
    ]

    for module in modules:
        importlib.import_module(module)


def test_custom_baser_stores_round_trip_and_top_iteration():
    db = basing.Baser(name="keri-v2-store-compat", temp=True)
    try:
        db.ips.pin(
            keys=("127.0.0.1",),
            val=basing.Requests(dt=OLD_TIMESTAMP, count=1),
        )
        db.wats.pin(
            keys=(WATCHER_AID,),
            val=basing.Wat(name="wan", wid=WATCHER_AID, cid=CONTROLLER_AID),
        )
        db.witq.pin(
            keys=(WATCHER_AID, OBSERVED_AID, CONTROLLER_AID),
            val=basing.WitnessQuery(
                watcher_id=WATCHER_AID,
                aid=OBSERVED_AID,
                wit=CONTROLLER_AID,
                query_timestamp=OLD_TIMESTAMP,
                response_received=True,
                state=States.even,
            ),
        )

        assert db.ips.get(keys=("127.0.0.1",)).count == 1
        wats = list(db.wats.getTopItemIter(keys=(WATCHER_AID,)))
        assert wats[0][1].cid == CONTROLLER_AID
        assert (
            list(db.witq.getTopItemIter(keys=(WATCHER_AID,)))[0][1].state == States.even
        )
    finally:
        db.close(clear=True)


def test_watchery_temp_true_preserved_and_create_watcher_uses_temp_habery():
    db = basing.Baser(name="keri-v2-temp-compat", temp=True)
    wty = Watchery(db=db, temp=True)

    try:
        assert wty.temp is True

        watcher = wty.createWatcher(cid=CONTROLLER_AID)

        assert watcher.hby.temp is True
        assert watcher.hab.pre in wty.wats
        assert watcher.hab.kever.serder.kind == kering.Kinds.cesr
        assert db.wats.get(keys=(watcher.hab.pre,)).cid == CONTROLLER_AID
    finally:
        for watcher in list(wty.wats.values()):
            if watcher.verifier.reger.opened:
                watcher.verifier.reger.close(clear=True)
            watcher.hby.close(clear=True)
        db.close(clear=True)


def test_watchery_delete_watcher_removes_registry_entry():
    db = basing.Baser(name="keri-v2-delete-compat", temp=True)
    wty = Watchery(db=db, temp=True)

    try:
        watcher = wty.createWatcher(cid=CONTROLLER_AID)
        eid = watcher.hab.pre

        assert wty.lookup(eid) is watcher

        wty.deleteWatcher(eid)

        assert wty.lookup(eid) is None
        assert db.wats.get(keys=(eid,)) is None
        assert db.cids.get(keys=(eid, CONTROLLER_AID)) is None
    finally:
        db.close(clear=True)


def test_watcher_parser_accepts_keri10_inception_and_add_reply(mockHelpingNowUTC):
    with (
        habbing.openHab(name="bob", salt=b"0123456789fedbob") as (_, bobHab),
        habbing.openHab(name="eve", salt=b"0123456789fedeve") as (_, eveHab),
        habbing.openHab(name="wan", transferable=False, salt=b"0123456789fedcba") as (
            watHby,
            watHab,
        ),
    ):
        db = basing.Baser(name="keri-v2-parser-compat", temp=True)
        wty = Watchery(db=db, temp=True)
        watcher = Watcher(wty=wty, db=db, hby=watHby, hab=watHab, cid=bobHab.pre)

        route = f"/watcher/{watHab.pre}/add"
        data = dict(
            cid=bobHab.pre,
            oid=eveHab.pre,
            oobi="http://localhost:2701/oobi",
        )
        serder = eventing.reply(route=route, data=data)

        assert watcher.psr.version == kering.Vrsn_2_0

        watcher.psr.parseOne(bobHab.msgOwnInception(), version=kering.Vrsn_1_0)
        watcher.psr.parseOne(bobHab.endorse(serder), version=kering.Vrsn_1_0)

        keys = (bobHab.pre, watHab.pre, eveHab.pre)
        assert watcher.hby.db.wwas.get(keys=keys).qb64 == serder.said
        assert watcher.hby.db.obvs.get(keys=keys).enabled is True

        db.close(clear=True)


def test_http_query_parser_uses_inbound_keri10_version(monkeypatch):
    captured = {}

    class CapturingParser:
        def __init__(self, **kwa):
            captured.update(kwa)

        def parseOne(self, ims, local=False):
            captured["local"] = local
            captured["ims"] = bytes(ims)

    serder = eventing.query(
        pre=CONTROLLER_AID,
        route="ksn",
        query={"src": WATCHER_AID},
    )

    monkeypatch.setattr(wat_httping.parsing, "Parser", CapturingParser)
    monkeypatch.setattr(
        wat_httping.httping,
        "parseCesrHttpRequest",
        lambda req: SimpleNamespace(payload=serder.ked, attachments=""),
    )

    watcher = SimpleNamespace(cid=CONTROLLER_AID, hab=SimpleNamespace())
    wty = SimpleNamespace(lookup=lambda aid: watcher if aid == WATCHER_AID else None)
    req = SimpleNamespace(
        method="POST",
        headers={CESR_DESTINATION_HEADER: WATCHER_AID},
    )
    rep = Response()

    wat_httping.HttpEnd(wty=wty).on_post(req, rep)

    assert captured["version"] == kering.Vrsn_1_0
    assert captured["local"] is False
    assert rep.status == falcon.HTTP_204


def test_http_query_parser_uses_inbound_keri2_version(monkeypatch):
    captured = {}

    class CapturingParser:
        def __init__(self, **kwa):
            captured.update(kwa)

        def parseOne(self, ims, local=False):
            captured["local"] = local
            captured["ims"] = bytes(ims)

    serder = eventing.query(
        pre=CONTROLLER_AID,
        route="ksn",
        query={"src": WATCHER_AID},
        version=kering.Vrsn_2_0,
        pvrsn=kering.Vrsn_2_0,
        kind=eventing.Kinds.json,
    )

    monkeypatch.setattr(wat_httping.parsing, "Parser", CapturingParser)
    monkeypatch.setattr(
        wat_httping.httping,
        "parseCesrHttpRequest",
        lambda req: SimpleNamespace(payload=serder.ked, attachments=""),
    )

    watcher = SimpleNamespace(cid=CONTROLLER_AID, hab=SimpleNamespace())
    wty = SimpleNamespace(lookup=lambda aid: watcher if aid == WATCHER_AID else None)
    req = SimpleNamespace(
        method="POST",
        headers={CESR_DESTINATION_HEADER: WATCHER_AID},
    )
    rep = Response()

    wat_httping.HttpEnd(wty=wty).on_post(req, rep)

    assert captured["version"] == kering.Vrsn_2_0
    assert captured["local"] is False
    assert rep.status == falcon.HTTP_204


def test_http_post_rejects_unsupported_acdc_payload_without_internal_error(monkeypatch):
    monkeypatch.setattr(
        wat_httping.httping,
        "parseCesrHttpRequest",
        lambda req: SimpleNamespace(payload={"v": "ACDC10JSON000000_"}, attachments=""),
    )

    watcher = SimpleNamespace(cid=CONTROLLER_AID, hab=SimpleNamespace())
    wty = SimpleNamespace(lookup=lambda aid: watcher if aid == WATCHER_AID else None)
    req = SimpleNamespace(
        method="POST",
        headers={CESR_DESTINATION_HEADER: WATCHER_AID},
    )
    rep = Response()

    wat_httping.HttpEnd(wty=wty).on_post(req, rep)

    assert rep.status == falcon.HTTP_UNPROCESSABLE_ENTITY


def test_http_post_rejects_unsupported_keri_ilk(monkeypatch):
    serder = SimpleNamespace(
        raw=b"{}",
        ked={"v": "KERI10JSON000000_", "t": "rct"},
    )
    monkeypatch.setattr(
        wat_httping.httping,
        "parseCesrHttpRequest",
        lambda req: SimpleNamespace(payload=serder.ked, attachments=""),
    )
    monkeypatch.setattr(wat_httping.serdering, "SerderKERI", lambda **kwa: serder)

    watcher = SimpleNamespace(cid=CONTROLLER_AID, hab=SimpleNamespace())
    wty = SimpleNamespace(lookup=lambda aid: watcher if aid == WATCHER_AID else None)
    req = SimpleNamespace(
        method="POST",
        headers={CESR_DESTINATION_HEADER: WATCHER_AID},
    )
    rep = Response()

    wat_httping.HttpEnd(wty=wty).on_post(req, rep)

    assert rep.status == falcon.HTTP_UNPROCESSABLE_ENTITY


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
        pre=CONTROLLER_AID,
        route="ksn",
        query={"src": WATCHER_AID},
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


def test_http_put_rejects_invalid_raw_cesr_with_bad_request():
    """Return a client error when raw PUT bytes are not a valid KERI message prefix."""

    # Use a fake parser
    watcher = SimpleNamespace(psr=SimpleNamespace(parseOne=lambda **kwa: None))
    wty = SimpleNamespace(lookup=lambda aid: watcher if aid == WATCHER_AID else None)

    # Feed an invalid raw payload 
    req = SimpleNamespace(
        method="PUT",
        headers={CESR_DESTINATION_HEADER: WATCHER_AID},
        bounded_stream=SimpleNamespace(read=lambda: b"x" * 40),
    )
    rep = Response()

    # Assert that the request gets rejected
    with pytest.raises(falcon.HTTPBadRequest) as exc:
        wat_httping.HttpEnd(wty=wty).on_put(req, rep)

    # The error text should identify the raw CESR payload as invalid
    assert "invalid CESR payload" in exc.value.description


def test_http_put_parses_mixed_version_stream_one_message_at_a_time(monkeypatch):
    """Test that each raw PUT message is parsed using the version declared by that message."""
    # Capture the versions passed into parseOne() for each message in the stream
    versions = []

    # Simulate a stream whose first byte identifies which protocol version to use
    def fake_serder(*, raw):
        return SimpleNamespace(
            pvrsn=(
                kering.Vrsn_1_0 if raw.startswith(b"1") else kering.Vrsn_2_0
            )
        )

    # Each parse consumes one byte so the outer loop advances to the next message
    def parse_one(**kwa):
        versions.append(kwa["version"])
        del kwa["ims"][:1]

    monkeypatch.setattr(wat_httping.serdering, "SerderKERI", fake_serder)

    # Inject the fake parser 
    watcher = SimpleNamespace(psr=SimpleNamespace(parseOne=parse_one))
    wty = SimpleNamespace(lookup=lambda aid: watcher if aid == WATCHER_AID else None)

    # The body contains two synthetic messages: one v1 marker and one v2 marker
    req = SimpleNamespace(
        method="PUT",
        headers={CESR_DESTINATION_HEADER: WATCHER_AID},
        bounded_stream=SimpleNamespace(read=lambda: b"12"),
        remote_addr="127.0.0.1",
        access_route=["127.0.0.1"],
    )
    rep = Response()

    # Run the handler so it drains both messages from the raw stream
    wat_httping.HttpEnd(wty=wty).on_put(req, rep)

    # Each message should be parsed with its own declared version
    assert versions == [kering.Vrsn_1_0, kering.Vrsn_2_0]
    
    # Assert successfull processing
    assert rep.status == falcon.HTTP_204


def test_http_put_maps_parser_errors_to_bad_request():
    """Map parser-level raw PUT failures to a deliberate client error."""

    # Set up a valid serder
    serder = eventing.reply(route="/watcher/add", data={})

    # Simulate a deeper parser failure after ingress validation succeeds
    def fail_parse_one(**kwa):
        raise kering.ValidationError("bad stream")

    # Use the failing parser stub behind a normal watcher lookup.
    watcher = SimpleNamespace(psr=SimpleNamespace(parseOne=fail_parse_one))
    wty = SimpleNamespace(lookup=lambda aid: watcher if aid == WATCHER_AID else None)
    req = SimpleNamespace(
        method="PUT",
        headers={CESR_DESTINATION_HEADER: WATCHER_AID},
        bounded_stream=SimpleNamespace(read=lambda: serder.raw),
    )
    rep = Response()

    # The HTTP layer should translate parser exceptions into a client error
    with pytest.raises(falcon.HTTPBadRequest) as exc:
        wat_httping.HttpEnd(wty=wty).on_put(req, rep)

    # Assert clear error message that indicate the stream failed KERI parsing
    assert "invalid KERI stream" in exc.value.description


def test_throttle_uses_remote_addr_instead_of_forwarded_route():
    """Test that rate-limit is done by the connected peer address instead of forwarded client hints."""
    
    # Set up a fake DB
    db = basing.Baser(name="keri-v2-throttle-compat", temp=True)
    try:
        throttle = wat_httping.Throttle(db=db)

        # Present conflicting values so the test can distinguish trusted from untrusted sources
        req = SimpleNamespace(
            remote_addr="127.0.0.1",
            access_route=["203.0.113.10", "127.0.0.1"],
        )
        rep = SimpleNamespace(complete=False, status=None)

        # Two requests from the same connected peer should hit the same bucket
        throttle.process_request(req, rep)
        throttle.process_request(req, rep)

        # The trusted peer address should be the only bucket that increments
        assert db.ips.get(keys=("127.0.0.1",)).count == 2

        # A spoofable forwarded address must not create its own throttle bucket
        assert db.ips.get(keys=("203.0.113.10",)) is None

        # The limit is not reached
        assert rep.complete is False
    finally:
        db.close(clear=True)


def test_throttle_resets_count_after_window_rollover(monkeypatch):
    """Test reset the stored request count once a client falls outside the throttle window."""

    # Set up fake DB
    db = basing.Baser(name="keri-v2-throttle-rollover", temp=True)
    try:
        throttle = wat_httping.Throttle(db=db)

        # Set up IP 
        req = SimpleNamespace(
            remote_addr="127.0.0.1",
            access_route=["127.0.0.1"],
        )
        rep = SimpleNamespace(complete=False, status=None)

        # Drive time manually so we can cover both "inside window" and "after rollover"
        start = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
        times = iter(
            [
                start,
                start + datetime.timedelta(seconds=1),
                start + wat_httping.Throttle.Window + datetime.timedelta(seconds=1),
            ]
        )
        monkeypatch.setattr(wat_httping.helping, "nowUTC", lambda: next(times))

        # First request initializes the per-IP counter
        throttle.process_request(req, rep)
        assert db.ips.get(keys=("127.0.0.1",)).count == 1

        # Second request lands inside the same window and increments the count
        throttle.process_request(req, rep)
        assert db.ips.get(keys=("127.0.0.1",)).count == 2

        # Third request lands after the window and should reset the stored count
        throttle.process_request(req, rep)
        assert db.ips.get(keys=("127.0.0.1",)).count == 1

        # A rollover should not trigger rate-limit rejection
        assert rep.complete is False
    finally:
        db.close(clear=True)


def test_query_replies_are_normalized_to_fixed_v2_cesr(monkeypatch):
    class FakeKevery:
        def __init__(self, db, local, cues):
            self.cues = cues

        def processQuery(self, serder, source=None, sigers=None, cigars=None):
            self.cues.push(
                dict(
                    kin="reply",
                    src=WATCHER_AID,
                    route="/ksn",
                    serder=eventing.reply(
                        route=f"/ksn/{WATCHER_AID}",
                        data={"i": OBSERVED_AID},
                    ),
                    dest=source.qb64,
                )
            )

    monkeypatch.setattr(wat_eventing.eventing, "Kevery", FakeKevery)

    watcher = SimpleNamespace(
        cid=CONTROLLER_AID,
        hab=SimpleNamespace(pre=WATCHER_AID, db=SimpleNamespace()),
    )
    shims = [
        wat_eventing.QueryKeveryShim(watcher=watcher, cues=decking.Deck()),
        wat_eventing.KeveryQueryShim(
            wty=SimpleNamespace(
                lookup=lambda aid: watcher if aid == WATCHER_AID else None
            ),
            cues=decking.Deck(),
        ),
    ]

    for pvrsn in (kering.Vrsn_1_0, kering.Vrsn_2_0):
        query = eventing.query(
            pre=CONTROLLER_AID,
            route="ksn",
            query={"i": OBSERVED_AID, "src": WATCHER_AID},
            version=pvrsn,
            pvrsn=pvrsn,
            kind=eventing.Kinds.json,
        )

        for shim in shims:
            shim.processQuery(
                serder=query,
                source=SimpleNamespace(qb64=CONTROLLER_AID),
                sigers=[],
                cigars=[],
            )
            cue = shim.cues.pull()
            assert kering.deversify(cue["serder"].ked["v"]).pvrsn == kering.Vrsn_2_0
            assert cue["serder"].kind == kering.Kinds.cesr
            assert cue["serder"].ked["i"] == WATCHER_AID


def test_query_shims_ignore_missing_authenticated_source():
    watcher = SimpleNamespace(
        cid=CONTROLLER_AID,
        hab=SimpleNamespace(pre=WATCHER_AID, db=SimpleNamespace()),
    )
    query = eventing.query(
        pre=CONTROLLER_AID,
        route="ksn",
        query={"i": OBSERVED_AID, "src": WATCHER_AID},
    )

    http_shim = wat_eventing.QueryKeveryShim(watcher=watcher, cues=decking.Deck())
    tcp_shim = wat_eventing.KeveryQueryShim(
        wty=SimpleNamespace(lookup=lambda aid: watcher if aid == WATCHER_AID else None),
        cues=decking.Deck(),
    )

    http_shim.processQuery(serder=query, source=None, sigers=[], cigars=[])
    tcp_shim.processQuery(serder=query, source=None, sigers=[], cigars=[])

    assert not http_shim.cues
    assert not tcp_shim.cues


def test_oobi_always_uses_fixed_legacy_v1_json():
    aid = WATCHER_AID
    calls = []

    class FakeHab:
        def replyToOobi(self, **kwa):
            calls.append(kwa)
            return bytearray(b"oobi")

        def replay(self, aid):
            return bytearray()

    watcher = SimpleNamespace(
        hby=SimpleNamespace(
            kevers={
                aid: SimpleNamespace(
                    serder=object(), prefixer=SimpleNamespace(qb64=aid)
                )
            },
            db=SimpleNamespace(fullyWitnessed=lambda serder: True),
            prefixes={aid},
            habs={aid: FakeHab()},
        )
    )
    wty = SimpleNamespace(lookup=lambda target: watcher if target == aid else None)

    endpoint = wat_oobing.OOBIEnd(wty=wty)
    app = falcon.App()
    app.add_route("/oobi/{aid}/{role}", endpoint)
    client = testing.TestClient(app)

    response = client.simulate_get(f"/oobi/{aid}/controller")
    assert response.status_code == 200
    assert calls[0]["version"] == kering.Vrsn_1_0
    assert calls[0]["pvrsn"] == kering.Vrsn_1_0
    assert calls[0]["kind"] == kering.Kinds.json


def test_tcp_reactant_parser_defaults_to_keri20():
    remoter = SimpleNamespace(rxbs=bytearray(), wind=lambda tymth: None)
    reactant = Reactant(wty=SimpleNamespace(), remoter=remoter)

    assert reactant.parser.version == kering.Vrsn_2_0


def test_tcp_reactant_drops_invalid_prefix_without_crashing():
    remoter = SimpleNamespace(rxbs=bytearray(b"x" * 40), wind=lambda tymth: None)
    reactant = Reactant(
        wty=SimpleNamespace(lookup=lambda aid: None),
        remoter=remoter,
    )
    parsed = []
    reactant.parser = SimpleNamespace(parseOne=lambda **kwa: parsed.append(kwa))

    do = reactant.remoteDo(lambda: 0.0, tock=0.0)
    assert next(do) == 0.0
    assert next(do) == 0.0

    assert remoter.rxbs == bytearray()
    assert parsed == []


def test_tcp_reactant_drops_stale_reply_cue_without_crashing():
    remoter = SimpleNamespace(rxbs=bytearray(), wind=lambda tymth: None, tx=lambda msg: None)
    reactant = Reactant(
        wty=SimpleNamespace(lookup=lambda aid: None),
        remoter=remoter,
    )
    sent = []
    reactant.sendMessage = lambda msg: sent.append(msg)
    reactant.cues.push(
        dict(
            kin="reply",
            src=WATCHER_AID,
            serder=SimpleNamespace(),
        )
    )

    do = reactant.cueDo(lambda: 0.0, tock=0.0)
    assert next(do) == 0.0
    assert next(do) is None

    assert sent == []
    assert not reactant.cues


def test_sentinal_doer_scans_real_obvs_and_cids_top_iteration(monkeypatch):
    launched = []

    class FakeSentinal:
        done = False

        def __init__(self, hby, hab, oid, cid, oobi, db):
            launched.append((oid, cid, oobi))

    monkeypatch.setattr(watching, "Sentinal", FakeSentinal)

    with habbing.openHab(name="scan", transferable=False, salt=b"0123456789fedsca") as (
        hby,
        hab,
    ):
        db = basing.Baser(name="keri-v2-scan-compat", temp=True)
        try:
            hby.db.obvs.pin(
                keys=(CONTROLLER_AID, hab.pre, OBSERVED_AID),
                val=ObservedRecord(
                    enabled=True,
                    name="observed",
                    datetime=OLD_TIMESTAMP,
                ),
            )
            db.cids.pin(
                keys=(hab.pre, CONTROLLER_AID),
                val=coring.Dater(dts=OLD_TIMESTAMP),
            )

            doer = SentinalDoer(
                db=db,
                hby=hby,
                hab=hab,
                cid=CONTROLLER_AID,
                oobi="http://watcher.example/oobi",
            )
            monkeypatch.setattr(doer, "extend", lambda doers: None)

            doer.watchWatched()
            doer.watchControllers()

            assert (
                OBSERVED_AID,
                CONTROLLER_AID,
                "http://watcher.example/oobi",
            ) in launched
            assert (
                CONTROLLER_AID,
                CONTROLLER_AID,
                "http://watcher.example/oobi",
            ) in launched
        finally:
            db.close(clear=True)


def test_watcher_status_reads_real_witq_top_iteration():
    db = basing.Baser(name="keri-v2-status-compat", temp=True)
    try:
        db.witq.pin(
            keys=(WATCHER_AID, OBSERVED_AID, CONTROLLER_AID),
            val=basing.WitnessQuery(
                watcher_id=WATCHER_AID,
                aid=OBSERVED_AID,
                wit=CONTROLLER_AID,
                query_timestamp=OLD_TIMESTAMP,
                response_received=False,
                state=States.unresponsive,
                error="No response received within timeout",
            ),
        )
        watcher = SimpleNamespace(cid=CONTROLLER_AID, db=db)
        wty = SimpleNamespace(lookup=lambda eid: watcher if eid == WATCHER_AID else None)
        rep = Response()

        watching.WatcherStatusEnd(wty=wty).on_get(
            req=SimpleNamespace(),
            rep=rep,
            eid=WATCHER_AID,
        )

        body = json.loads(rep.data.decode("utf-8"))
        witness = body["aids"][OBSERVED_AID]["witnesses"][CONTROLLER_AID]

        assert body["summary"]["total_aids"] == 1
        assert body["summary"]["total_witnesses"] == 1
        assert witness["state"] == States.unresponsive
        assert witness["error"] == "No response received within timeout"
    finally:
        db.close(clear=True)


def test_sentinal_missing_endpoint_persists_real_witq_error(monkeypatch):
    db = basing.Baser(name="keri-v2-sentinal-compat", temp=True)

    class FakeKever:
        wits = [CONTROLLER_AID]
        sn = 0

    class FakeStore:
        def get(self, keys):
            return None

        def rem(self, keys):
            pass

    class FakeHab:
        pre = WATCHER_AID
        db = SimpleNamespace(knas=FakeStore(), ksns=FakeStore())
        kever = FakeKever()

    def fake_http_client(hab, wit):
        raise kering.MissingEntryError(
            f"unable to query witness {wit}, no http endpoint"
        )

    monkeypatch.setattr("watopnet.app.watching.agenting.httpClient", fake_http_client)

    try:
        sentinal = Sentinal(
            hby=SimpleNamespace(kevers={OBSERVED_AID: FakeKever()}),
            hab=FakeHab(),
            oid=OBSERVED_AID,
            cid=CONTROLLER_AID,
            oobi="http://watcher.example/oobi",
            db=db,
        )
        monkeypatch.setattr(sentinal, "extend", lambda doers: None)
        monkeypatch.setattr(sentinal, "remove", lambda doers: None)

        do = sentinal.watch(lambda: 0.0, tock=0.0)
        assert next(do) == 0.0
        try:
            next(do)
        except StopIteration as stop:
            assert stop.value is True

        query = db.witq.get(keys=(WATCHER_AID, OBSERVED_AID, CONTROLLER_AID))
        assert query.response_received is False
        assert query.state == States.unresponsive
        assert query.error == (
            "Missing witness endpoint: unable to query witness "
            f"{CONTROLLER_AID}, no http endpoint"
        )
    finally:
        db.close(clear=True)
