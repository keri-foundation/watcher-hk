# -*- encoding: utf-8 -*-

"""
KERI
testing watopnet.core.watching package

"""
from types import SimpleNamespace

import pytest
from keri import kering
from keri.app import habbing
from keri.core import eventing
from watopnet.core import basing
from watopnet.app.watching import Sentinal, States, Watcher, Watchery


def test_adding_watched(mockHelpingNowUTC):
    with (
        habbing.openHab(name="bob", salt=b"0123456789fedbob") as (bobHby, bobHab),
        habbing.openHab(name="eve", salt=b"0123456789fedeve") as (eveHby, eveHab),
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

        # with trans cid for nel and eid for wat
        route = f"/watcher/{watHab.pre}/add"
        data = dict(cid=bobHab.pre, oid=eveHab.pre, oobi="http://localhost:2701/oobi")

        serder = eventing.reply(
            route=route,
            data=data,
        )
        ims = bobHab.endorse(serder)
        assert ims == (
            b'{"v":"KERI10JSON000152_","t":"rpy","d":"EK_hu3_toGjYLYqmHMeMAMdf'
            b'7FVlWHktd2P6nn8o2ad6","dt":"2021-01-01T00:00:00.000000+00:00","r'
            b'":"/watcher/BGbLRtLXIslZvTfYz97dS9_EzQxp8kSTAMMtW-LmlXMI/add","a'
            b'":{"cid":"ENsqL5zLYNbZf0kcOlx-ioqNWlatD9rKZZM4hbEI7nza","oid":"E'
            b'LiJTS4bBx5gZlT68OjBxFiirP0Qa2XQZ6V5cjHWQR0p","oobi":"http://loca'
            b'lhost:2701/oobi"}}-VA0-FABENsqL5zLYNbZf0kcOlx-ioqNWlatD9rKZZM4hb'
            b"EI7nza0AAAAAAAAAAAAAAAAAAAAAAAENsqL5zLYNbZf0kcOlx-ioqNWlatD9rKZZ"
            b"M4hbEI7nza-AABAABMkyXJW9f-ZxfSmu7Wses7EPEe_c17TRFSW1d9At-RF4WKms"
            b"5lDCUrOooCi9Ndkan3UxtbKqG6oApOgsbPqUYI"
        )

        icp = bobHab.makeOwnInception()
        watcher.psr.parseOne(icp)
        assert bobHab.pre in watcher.hby.kevers

        watcher.psr.parseOne(ims)

        keys = (bobHab.pre, watHab.pre, eveHab.pre)

        saider = watcher.hby.db.wwas.get(keys=keys)
        assert saider.qb64 == serder.said

        observed = watcher.hby.db.obvs.get(keys=keys)
        assert observed.enabled is True


def test_sentinal_queries_witness_state_with_messenger(monkeypatch):
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

    query_calls = []

    class FakeKever:
        wits = ["WIT_1"]
        sn = 0

        @staticmethod
        def state():
            return "local-state"

    class FakeHab:
        pre = "WATCHER_AID"
        kever = FakeKever()

        @staticmethod
        def query(*, pre, src, route):
            query_calls.append((pre, src, route))
            return b"ksn-query"

    class FakeMessenger:
        def __init__(self):
            self.idle = False

            class Messages(list):
                def append(inner_self, item):
                    assert item == bytearray(b"ksn-query")
                    knas.put(("OBSERVED_AID", "WIT_1"), SimpleNamespace(qb64="SAID_1"))
                    ksns.put(("SAID_1",), "witness-state")
                    self.idle = True
                    super().append(item)

            self.msgs = Messages()

    monkeypatch.setattr(
        "watopnet.app.watching.agenting.messenger",
        lambda hab, wit: FakeMessenger(),
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
        hab=SimpleNamespace(pre=FakeHab.pre, db=db, kever=FakeHab.kever, query=FakeHab.query),
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
    assert query_calls == [("OBSERVED_AID", "WIT_1", "ksn")]
    assert len(witq.calls) == 1
    keys, query = witq.calls[0]
    assert keys == ("WATCHER_AID", "OBSERVED_AID", "WIT_1")
    assert query.response_received is True
    assert query.state == States.even
    assert query.keystate == "witness-state"


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

    query_calls = []

    class FakeKever:
        wits = ["WIT_1"]
        sn = 0

        @staticmethod
        def state():
            return "local-state"

    class FakeHab:
        pre = "WATCHER_AID"
        kever = FakeKever()

        @staticmethod
        def query(*, pre, src, route):
            query_calls.append((pre, src, route))
            return b"ksn-query"

    class FakeMessenger:
        def __init__(self):
            self.idle = False

            class Messages(list):
                def append(inner_self, item):
                    assert item == bytearray(b"ksn-query")
                    self.idle = True
                    super().append(item)

            self.msgs = Messages()

    monkeypatch.setattr(
        "watopnet.app.watching.agenting.messenger",
        lambda hab, wit: FakeMessenger(),
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
        hab=SimpleNamespace(pre=FakeHab.pre, db=db, kever=FakeHab.kever, query=FakeHab.query),
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
    assert query_calls == [("OBSERVED_AID", "WIT_1", "ksn")]
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

    query_calls = []

    class FakeHab:
        pre = "WATCHER_AID"
        db = SimpleNamespace(
            knas=SimpleNamespace(get=lambda keys: None, rem=lambda keys: None),
            ksns=SimpleNamespace(rem=lambda keys: None),
        )
        kever = FakeKever()

        @staticmethod
        def query(*, pre, src, route):
            query_calls.append((pre, src, route))
            return b"ksn-query"

    def fake_messenger(hab, wit):
        raise kering.ConfigurationError(
            f"unable to find a valid endpoint for witness={wit}"
        )

    monkeypatch.setattr("watopnet.app.watching.agenting.messenger", fake_messenger)

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
    assert query_calls == []
    assert len(witq.calls) == 1
    keys, query = witq.calls[0]
    assert keys == ("WATCHER_AID", "OBSERVED_AID", "WIT_1")
    assert query.response_received is False
    assert query.state == States.unresponsive
    assert query.error == "Missing witness endpoint: unable to find a valid endpoint for witness=WIT_1"
