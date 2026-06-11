# -*- encoding: utf-8 -*-

"""
KERI
testing watopnet.core.watching package

"""

import errno
from types import SimpleNamespace
from unittest.mock import MagicMock

import falcon
import pytest
from falcon import testing
from keri import kering
from keri.app import habbing
from keri.app.httping import CESR_DESTINATION_HEADER
from keri.core import eventing

from watopnet.app import watching
from watopnet.core import basing
from watopnet.app.watching import Sentinal, States, Watcher, Watchery

CONTROLLER_AID = "ENsqL5zLYNbZf0kcOlx-ioqNWlatD9rKZZM4hbEI7nza"


def test_watcher_fd_exhaustion_detection_handles_oserror_and_lmdb_text():
    assert watching._isFdExhaustion(OSError(errno.EMFILE, "Too many open files"))
    assert watching._isFdExhaustion(RuntimeError("lmdb failure: Too many open files"))


def test_create_watcher_fd_exhaustion_returns_service_unavailable():
    wty = MagicMock()
    wty.createWatcher.side_effect = RuntimeError("lmdb failure: Too many open files")

    endpoint = watching.WatcherCollectionEnd(wty=wty)
    app = falcon.App()
    app.add_route("/watchers", endpoint)
    client = testing.TestClient(app)

    response = client.simulate_post("/watchers", json={"aid": CONTROLLER_AID})

    assert response.status == falcon.HTTP_503
    assert response.json["title"] == "Watcher service unavailable"
    wty._logFdExhaustion.assert_called_once_with(CONTROLLER_AID)


def test_adding_watched(mockHelpingNowUTC):
    with (
        habbing.openHab(name="bob", salt=b"0123456789fedbob") as (_, bobHab),
        habbing.openHab(name="eve", salt=b"0123456789fedeve") as (_, eveHab),
        habbing.openHab(name="wan", transferable=False, salt=b"0123456789fedcba") as (
            watHby,
            watHab,
        ),
    ):
        assert bobHab.pre == "ENsqL5zLYNbZf0kcOlx-ioqNWlatD9rKZZM4hbEI7nza"
        assert eveHab.pre == "ELiJTS4bBx5gZlT68OjBxFiirP0Qa2XQZ6V5cjHWQR0p"
        assert watHab.pre == "BGbLRtLXIslZvTfYz97dS9_EzQxp8kSTAMMtW-LmlXMI"

        db = basing.Baser(name="bob", temp=True)

        wty = Watchery(db=db, temp=True)
        watcher = Watcher(wty=wty, db=db, hby=watHby, hab=watHab, cid=bobHab.pre)

        route = f"/watcher/{watHab.pre}/add"
        data = dict(cid=bobHab.pre, oid=eveHab.pre, oobi="http://localhost:2701/oobi")

        serder = eventing.reply(
            route=route,
            data=data,
        )
        ims = bobHab.endorse(serder)
        assert bytes(ims).startswith(serder.raw)

        icp = bobHab.msgOwnInception()
        watcher.psr.parseOne(icp, version=kering.Vrsn_1_0)
        assert bobHab.pre in watcher.hby.kevers

        watcher.psr.parseOne(ims, version=kering.Vrsn_1_0)

        keys = (bobHab.pre, watHab.pre, eveHab.pre)

        saider = watcher.hby.db.wwas.get(keys=keys)
        assert saider.qb64 == serder.said

        observed = watcher.hby.db.obvs.get(keys=keys)
        assert observed.enabled is True


def test_sentinal_queries_witness_state_with_http_ksn(monkeypatch):
    class FakeStore:
        def __init__(self):
            self.values = {}

        def get(self, keys):
            return self.values.get(keys)

        def rem(self, keys):
            self.values.pop(keys, None)

        def put(self, keys, val):
            self.values[keys] = val

    class FakeWitnessQueryStore:
        def __init__(self):
            self.calls = []

        def pin(self, *, keys, val):
            self.calls.append((keys, val))

    knas = FakeStore()
    ksns = FakeStore()
    witq = FakeWitnessQueryStore()
    db = SimpleNamespace(knas=knas, ksns=ksns, witq=witq)

    requests = []
    parsed = []

    class FakeKever:
        wits = ["WIT_1"]
        sn = 0

        @staticmethod
        def state():
            return "local-state"

    class FakeHab:
        pre = "WATCHER_AID"
        kever = FakeKever()

        def __init__(self):
            self.db = db
            self.psr = SimpleNamespace(
                parseOne=lambda **kwa: (
                    parsed.append(kwa),
                    knas.put(
                        ("OBSERVED_AID", "WIT_1"),
                        SimpleNamespace(qb64="SAID_1"),
                    ),
                    ksns.put(("SAID_1",), "witness-state"),
                )
            )

    class FakeClient:
        def __init__(self):
            self.responses = [SimpleNamespace(status=200, body=b"ksn-reply")]

        def request(self, *, method, path, headers):
            requests.append((method, path, headers))

        def respond(self):
            return self.responses.pop(0)

    client = FakeClient()
    client_doer = object()
    monkeypatch.setattr(
        "watopnet.app.watching.agenting.httpClient",
        lambda hab, wit: (client, client_doer),
    )
    monkeypatch.setattr(
        "watopnet.app.watching.serdering.SerderKERI",
        lambda raw: SimpleNamespace(
            proto=kering.Protocols.keri,
            pvrsn=kering.Vrsn_1_0,
        ),
    )
    monkeypatch.setattr(
        Sentinal,
        "diffState",
        staticmethod(
            lambda wit, preksn, witksn: SimpleNamespace(
                wit=wit,
                state=States.even,
                sn=0,
                dig="DIG_1",
            )
        ),
    )

    sentinal = Sentinal(
        hby=SimpleNamespace(db=db, kevers={"OBSERVED_AID": FakeKever()}),
        hab=FakeHab(),
        oid="OBSERVED_AID",
        cid="CONTROLLER_AID",
        oobi="http://watcher.example/oobi",
        db=SimpleNamespace(witq=witq),
    )
    monkeypatch.setattr(sentinal, "extend", lambda doers: None)
    monkeypatch.setattr(sentinal, "remove", lambda doers: None)

    do = sentinal.watch(lambda: 0.0, tock=0.0)
    assert next(do) == 0.0
    with pytest.raises(StopIteration) as stop:
        next(do)

    assert stop.value.value is True
    assert requests == [
        (
            "GET",
            "/ksn?pre=OBSERVED_AID",
            {CESR_DESTINATION_HEADER: "WIT_1"},
        )
    ]
    assert parsed == [
        {
            "ims": bytearray(b"ksn-reply"),
            "local": False,
            "version": kering.Vrsn_1_0,
        }
    ]
    assert len(witq.calls) == 1
    keys, query = witq.calls[0]
    assert keys == ("WATCHER_AID", "OBSERVED_AID", "WIT_1")
    assert query.response_received is True
    assert query.state == States.even
    assert query.keystate == "witness-state"


def test_query_witness_state_parses_real_keri10_ksn_reply(monkeypatch):
    with (
        habbing.openHab(name="wit", transferable=False, salt=b"0123456789fedwit") as (
            _,
            witHab,
        ),
        habbing.openHab(
            name="bob",
            salt=b"0123456789fedbob",
            wits=[witHab.pre],
            toad=1,
        ) as (_, bobHab),
        habbing.openHab(name="wan", transferable=False, salt=b"0123456789fedwan") as (
            watHby,
            watHab,
        ),
    ):
        watHab.psr.parseOne(bobHab.msgOwnInception(), local=False, version=kering.Vrsn_1_0)
        rserder = eventing.reply(
            route=f"/ksn/{witHab.pre}",
            data=bobHab.kever.state()._asdict(),
        )
        body = witHab.endorse(rserder)

        class FakeClient:
            def __init__(self):
                self.responses = [SimpleNamespace(status=200, body=body)]

            def request(self, *, method, path, headers):
                assert (method, path, headers) == (
                    "GET",
                    f"/ksn?pre={bobHab.pre}",
                    {CESR_DESTINATION_HEADER: witHab.pre},
                )

            def respond(self):
                return self.responses.pop(0)

        client_doer = object()
        monkeypatch.setattr(
            "watopnet.app.watching.agenting.httpClient",
            lambda hab, wit: (FakeClient(), client_doer),
        )

        sentinal = Sentinal(
            hby=watHby,
            hab=watHab,
            oid=bobHab.pre,
            cid=bobHab.pre,
            oobi="http://watcher.example/oobi",
            db=SimpleNamespace(),
        )
        monkeypatch.setattr(sentinal, "extend", lambda doers: None)
        monkeypatch.setattr(sentinal, "remove", lambda doers: None)

        query = sentinal.queryWitnessState(
            wit=witHab.pre,
            pre=bobHab.pre,
            tymth=lambda: 0.0,
        )
        with pytest.raises(StopIteration) as stop:
            next(query)

        assert stop.value.value is None
        saider = watHab.db.knas.get(keys=(bobHab.pre, witHab.pre))
        assert saider is not None
        ksn = watHab.db.ksns.get(keys=(saider.qb64,))
        assert ksn.i == bobHab.pre
        assert ksn.d == bobHab.kever.serder.said


def test_query_witness_state_parses_real_keri2_ksn_reply(monkeypatch):
    with (
        habbing.openHab(name="wit", transferable=False, salt=b"0123456789fedw20") as (
            _,
            witHab,
        ),
        habbing.openHab(
            name="bob",
            salt=b"0123456789fedb20",
            wits=[witHab.pre],
            toad=1,
        ) as (_, bobHab),
        habbing.openHab(name="wan", transferable=False, salt=b"0123456789fedwa2") as (
            watHby,
            watHab,
        ),
    ):
        watHab.psr.parseOne(bobHab.msgOwnInception(), local=False, version=kering.Vrsn_1_0)
        rserder = eventing.reply(
            pre=witHab.pre,
            route=f"/ksn/{witHab.pre}",
            data=bobHab.kever.state()._asdict(),
            version=kering.Vrsn_2_0,
            pvrsn=kering.Vrsn_2_0,
            kind=eventing.Kinds.cesr,
        )
        body = witHab.endorse(rserder)

        class FakeClient:
            def __init__(self):
                self.responses = [SimpleNamespace(status=200, body=body)]

            def request(self, *, method, path, headers):
                assert (method, path, headers) == (
                    "GET",
                    f"/ksn?pre={bobHab.pre}",
                    {CESR_DESTINATION_HEADER: witHab.pre},
                )

            def respond(self):
                return self.responses.pop(0)

        client_doer = object()
        monkeypatch.setattr(
            "watopnet.app.watching.agenting.httpClient",
            lambda hab, wit: (FakeClient(), client_doer),
        )

        sentinal = Sentinal(
            hby=watHby,
            hab=watHab,
            oid=bobHab.pre,
            cid=bobHab.pre,
            oobi="http://watcher.example/oobi",
            db=SimpleNamespace(),
        )
        monkeypatch.setattr(sentinal, "extend", lambda doers: None)
        monkeypatch.setattr(sentinal, "remove", lambda doers: None)

        query = sentinal.queryWitnessState(
            wit=witHab.pre,
            pre=bobHab.pre,
            tymth=lambda: 0.0,
        )
        with pytest.raises(StopIteration) as stop:
            next(query)

        assert stop.value.value is None
        saider = watHab.db.knas.get(keys=(bobHab.pre, witHab.pre))
        assert saider is not None
        ksn = watHab.db.ksns.get(keys=(saider.qb64,))
        assert ksn.i == bobHab.pre
        assert ksn.d == bobHab.kever.serder.said


def test_sentinal_waits_for_delayed_witness_state(monkeypatch):
    class FakeStore:
        def __init__(self):
            self.values = {}

        def get(self, keys):
            return self.values.get(keys)

        def rem(self, keys):
            self.values.pop(keys, None)

        def put(self, keys, val):
            self.values[keys] = val

    class FakeWitnessQueryStore:
        def __init__(self):
            self.calls = []

        def pin(self, *, keys, val):
            self.calls.append((keys, val))

    knas = FakeStore()
    ksns = FakeStore()
    witq = FakeWitnessQueryStore()
    db = SimpleNamespace(knas=knas, ksns=ksns, witq=witq)

    class FakeKever:
        wits = ["WIT_1"]
        sn = 0

        @staticmethod
        def state():
            return "local-state"

    class FakeHab:
        pre = "WATCHER_AID"
        kever = FakeKever()

    def delayed_query(self, *, wit, pre, tymth):
        assert (wit, pre) == ("WIT_1", "OBSERVED_AID")
        yield self.tock
        knas.put(("OBSERVED_AID", "WIT_1"), SimpleNamespace(qb64="SAID_1"))
        ksns.put(("SAID_1",), "witness-state")
        return None

    monkeypatch.setattr(Sentinal, "queryWitnessState", delayed_query)
    monkeypatch.setattr(
        Sentinal,
        "diffState",
        staticmethod(
            lambda wit, preksn, witksn: SimpleNamespace(
                wit=wit,
                state=States.even,
                sn=0,
                dig="DIG_1",
            )
        ),
    )

    sentinal = Sentinal(
        hby=SimpleNamespace(db=db, kevers={"OBSERVED_AID": FakeKever()}),
        hab=SimpleNamespace(pre=FakeHab.pre, db=db, kever=FakeHab.kever),
        oid="OBSERVED_AID",
        cid="CONTROLLER_AID",
        oobi="http://watcher.example/oobi",
        db=SimpleNamespace(witq=witq),
    )
    monkeypatch.setattr(sentinal, "extend", lambda doers: None)
    monkeypatch.setattr(sentinal, "remove", lambda doers: None)

    do = sentinal.watch(lambda: 0.0, tock=0.0)
    assert next(do) == 0.0
    assert next(do) == 0.0

    knas.put(("OBSERVED_AID", "WIT_1"), SimpleNamespace(qb64="SAID_1"))
    ksns.put(("SAID_1",), "witness-state")

    with pytest.raises(StopIteration) as stop:
        next(do)

    assert stop.value.value is True
    assert len(witq.calls) == 1
    keys, query = witq.calls[0]
    assert keys == ("WATCHER_AID", "OBSERVED_AID", "WIT_1")
    assert query.response_received is True
    assert query.state == States.even
    assert query.keystate == "witness-state"


def test_sentinal_pins_unresolved_witness_endpoint_without_crashing(monkeypatch):
    class FakeWitnessQueryStore:
        def __init__(self):
            self.calls = []

        def pin(self, *, keys, val):
            self.calls.append((keys, val))

    witq = FakeWitnessQueryStore()

    class FakeKever:
        wits = ["WIT_1"]
        sn = 0

        @staticmethod
        def state():
            return "local-state"

    class FakeHab:
        pre = "WATCHER_AID"
        db = SimpleNamespace(
            knas=SimpleNamespace(get=lambda keys: None, rem=lambda keys: None),
            ksns=SimpleNamespace(rem=lambda keys: None),
        )
        kever = FakeKever()

    def fake_http_client(hab, wit):
        raise kering.MissingEntryError(
            f"unable to query witness {wit}, no http endpoint"
        )

    monkeypatch.setattr("watopnet.app.watching.agenting.httpClient", fake_http_client)

    sentinal = Sentinal(
        hby=SimpleNamespace(kevers={"OBSERVED_AID": FakeKever()}),
        hab=FakeHab(),
        oid="OBSERVED_AID",
        cid="CONTROLLER_AID",
        oobi="http://watcher.example/oobi",
        db=SimpleNamespace(witq=witq),
    )
    monkeypatch.setattr(sentinal, "extend", lambda doers: None)
    monkeypatch.setattr(sentinal, "remove", lambda doers: None)

    do = sentinal.watch(lambda: 0.0, tock=0.0)
    assert next(do) == 0.0
    with pytest.raises(StopIteration) as stop:
        next(do)

    assert stop.value.value is True
    assert len(witq.calls) == 1
    keys, query = witq.calls[0]
    assert keys == ("WATCHER_AID", "OBSERVED_AID", "WIT_1")
    assert query.response_received is False
    assert query.state == States.unresponsive
    assert query.error == (
        "Missing witness endpoint: unable to query witness WIT_1, no http endpoint"
    )


def test_sentinal_pins_non_200_witness_ksn_response(monkeypatch):
    class FakeWitnessQueryStore:
        def __init__(self):
            self.calls = []

        def pin(self, *, keys, val):
            self.calls.append((keys, val))

    class FakeKever:
        wits = ["WIT_1"]
        sn = 0

    class FakeHab:
        pre = "WATCHER_AID"
        db = SimpleNamespace(
            knas=SimpleNamespace(get=lambda keys: None, rem=lambda keys: None),
            ksns=SimpleNamespace(rem=lambda keys: None),
        )

    class FakeClient:
        def __init__(self):
            self.responses = [SimpleNamespace(status=503, body=b"down")]

        def request(self, *, method, path, headers):
            pass

        def respond(self):
            return self.responses.pop(0)

    witq = FakeWitnessQueryStore()
    monkeypatch.setattr(
        "watopnet.app.watching.agenting.httpClient",
        lambda hab, wit: (FakeClient(), object()),
    )

    sentinal = Sentinal(
        hby=SimpleNamespace(kevers={"OBSERVED_AID": FakeKever()}),
        hab=FakeHab(),
        oid="OBSERVED_AID",
        cid="CONTROLLER_AID",
        oobi="http://watcher.example/oobi",
        db=SimpleNamespace(witq=witq),
    )
    monkeypatch.setattr(sentinal, "extend", lambda doers: None)
    monkeypatch.setattr(sentinal, "remove", lambda doers: None)

    do = sentinal.watch(lambda: 0.0, tock=0.0)
    assert next(do) == 0.0
    with pytest.raises(StopIteration) as stop:
        next(do)

    assert stop.value.value is True
    _, query = witq.calls[0]
    assert query.response_received is False
    assert query.state == States.unresponsive
    assert query.error == "Witness KSN query failed with HTTP 503"


def test_sentinal_pins_timeout_when_witness_ksn_response_never_arrives(monkeypatch):
    class FakeWitnessQueryStore:
        def __init__(self):
            self.calls = []

        def pin(self, *, keys, val):
            self.calls.append((keys, val))

    class FakeKever:
        wits = ["WIT_1"]
        sn = 0

    class FakeHab:
        pre = "WATCHER_AID"
        db = SimpleNamespace(
            knas=SimpleNamespace(get=lambda keys: None, rem=lambda keys: None),
            ksns=SimpleNamespace(rem=lambda keys: None),
        )

    class FakeClient:
        def __init__(self):
            self.responses = []

        def request(self, *, method, path, headers):
            pass

    witq = FakeWitnessQueryStore()
    monkeypatch.setattr(
        "watopnet.app.watching.agenting.httpClient",
        lambda hab, wit: (FakeClient(), object()),
    )

    sentinal = Sentinal(
        hby=SimpleNamespace(kevers={"OBSERVED_AID": FakeKever()}),
        hab=FakeHab(),
        oid="OBSERVED_AID",
        cid="CONTROLLER_AID",
        oobi="http://watcher.example/oobi",
        db=SimpleNamespace(witq=witq),
    )
    monkeypatch.setattr(sentinal, "extend", lambda doers: None)
    monkeypatch.setattr(sentinal, "remove", lambda doers: None)

    tyme = {"value": 0.0}
    do = sentinal.watch(lambda: tyme["value"], tock=0.0)
    assert next(do) == 0.0
    assert next(do) == 0.0
    tyme["value"] = 11.0
    with pytest.raises(StopIteration) as stop:
        next(do)

    assert stop.value.value is True
    _, query = witq.calls[0]
    assert query.response_received is False
    assert query.state == States.unresponsive
    assert query.error == "No response received within timeout"


def test_sentinal_pins_no_ksn_when_parsed_reply_is_not_accepted(monkeypatch):
    class FakeWitnessQueryStore:
        def __init__(self):
            self.calls = []

        def pin(self, *, keys, val):
            self.calls.append((keys, val))

    class FakeKever:
        wits = ["WIT_1"]
        sn = 0

        @staticmethod
        def state():
            return "local-state"

    class FakeHab:
        pre = "WATCHER_AID"
        db = SimpleNamespace(
            knas=SimpleNamespace(get=lambda keys: None, rem=lambda keys: None),
            ksns=SimpleNamespace(rem=lambda keys: None),
        )
        psr = SimpleNamespace(parseOne=lambda **kwa: None)

    class FakeClient:
        def __init__(self):
            self.responses = [SimpleNamespace(status=200, body=b"not-a-verified-ksn")]

        def request(self, *, method, path, headers):
            pass

        def respond(self):
            return self.responses.pop(0)

    witq = FakeWitnessQueryStore()
    monkeypatch.setattr(
        "watopnet.app.watching.agenting.httpClient",
        lambda hab, wit: (FakeClient(), object()),
    )

    sentinal = Sentinal(
        hby=SimpleNamespace(kevers={"OBSERVED_AID": FakeKever()}),
        hab=FakeHab(),
        oid="OBSERVED_AID",
        cid="CONTROLLER_AID",
        oobi="http://watcher.example/oobi",
        db=SimpleNamespace(witq=witq),
    )
    monkeypatch.setattr(sentinal, "extend", lambda doers: None)
    monkeypatch.setattr(sentinal, "remove", lambda doers: None)

    do = sentinal.watch(lambda: 0.0, tock=0.0)
    assert next(do) == 0.0
    with pytest.raises(StopIteration) as stop:
        next(do)

    assert stop.value.value is True
    _, query = witq.calls[0]
    assert query.response_received is False
    assert query.state == States.unresponsive
    assert query.error == "No key state notice received from witness"


def test_sentinal_pins_invalid_witness_ksn_without_aborting_other_witnesses(
    monkeypatch,
):
    class FakeStore:
        def __init__(self):
            self.values = {}

        def get(self, keys):
            return self.values.get(keys)

        def rem(self, keys):
            self.values.pop(keys, None)

        def put(self, keys, val):
            self.values[keys] = val

    class FakeWitnessQueryStore:
        def __init__(self):
            self.calls = []

        def pin(self, *, keys, val):
            self.calls.append((keys, val))

    knas = FakeStore()
    ksns = FakeStore()
    witq = FakeWitnessQueryStore()
    db = SimpleNamespace(knas=knas, ksns=ksns, witq=witq)

    class FakeKever:
        wits = ["WIT_1", "WIT_2"]
        sn = 0

        @staticmethod
        def state():
            return SimpleNamespace(i="OBSERVED_AID", s="0", d="DIG_0")

    def fake_query(self, *, wit, pre, tymth):
        knas.put((pre, wit), SimpleNamespace(qb64=wit))
        ksns.put((wit,), SimpleNamespace(i=pre, s="0", d=f"DIG_{wit}"))
        if False:
            yield self.tock
        return None

    def fake_diff(wit, preksn, witksn):
        if wit == "WIT_1":
            raise ValueError("can't compare key states from different AIDs OBSERVED_AID/WRONG")

        return SimpleNamespace(
            wit=wit,
            state=States.even,
            sn=0,
            dig=witksn.d,
        )

    monkeypatch.setattr(Sentinal, "queryWitnessState", fake_query)
    monkeypatch.setattr(Sentinal, "diffState", staticmethod(fake_diff))

    sentinal = Sentinal(
        hby=SimpleNamespace(db=db, kevers={"OBSERVED_AID": FakeKever()}),
        hab=SimpleNamespace(pre="WATCHER_AID", db=db, kever=FakeKever()),
        oid="OBSERVED_AID",
        cid="CONTROLLER_AID",
        oobi="http://watcher.example/oobi",
        db=SimpleNamespace(witq=witq),
    )
    monkeypatch.setattr(sentinal, "extend", lambda doers: None)
    monkeypatch.setattr(sentinal, "remove", lambda doers: None)

    do = sentinal.watch(lambda: 0.0, tock=0.0)
    assert next(do) == 0.0
    with pytest.raises(StopIteration) as stop:
        next(do)

    assert stop.value.value is True
    assert len(witq.calls) == 2

    (_, first_query), (_, second_query) = witq.calls
    assert first_query.response_received is False
    assert first_query.state == States.unresponsive
    assert first_query.error.startswith("Invalid key state notice from witness:")
    assert second_query.response_received is True
    assert second_query.state == States.even
    assert second_query.dig == "DIG_WIT_2"


def test_diff_state_uses_ksn_sequence_and_validates_aid():
    ours = Sentinal.diffState(
        "WIT_1",
        SimpleNamespace(i="AID_1", s="5", d="DIG_5"),
        SimpleNamespace(i="AID_1", s="6", f="2", d="DIG_6"),
    )
    assert ours.state == States.ahead
    assert ours.sn == 6
    assert ours.dig == "DIG_6"

    with pytest.raises(ValueError):
        Sentinal.diffState(
            "WIT_1",
            SimpleNamespace(i="AID_1", s="5", d="DIG_5"),
            SimpleNamespace(i="AID_2", s="5", f="5", d="DIG_5"),
        )
