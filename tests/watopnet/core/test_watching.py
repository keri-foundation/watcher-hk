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
from hio.base import doing
from keri import kering
from keri.app import habbing
from keri.core import eventing
from watopnet.app import watching
from watopnet.core import basing
from watopnet.app.watching import Sentinal, States, Watcher, Watchery

CONTROLLER_AID = "ENsqL5zLYNbZf0kcOlx-ioqNWlatD9rKZZM4hbEI7nza"


def test_isFdExhaustion_handles_oserror_and_lmdb_text():
    assert watching._isFdExhaustion(OSError(errno.EMFILE, "Too many open files"))
    assert watching._isFdExhaustion(RuntimeError("lmdb failure: Too many open files"))
    assert not watching._isFdExhaustion(ValueError("unrelated failure"))


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

    class FakeHab:
        pre = "WATCHER_AID"

    class FakeReceiptor:
        def __init__(self, hby):
            pass

        def ksn(self, pre, src, wit):
            raise kering.MissingEntryError(
                f"unable to query witness {wit}, no http endpoint"
            )

    monkeypatch.setattr("watopnet.app.watching.agenting.Receiptor", FakeReceiptor)

    fakeHby = SimpleNamespace(
        kevers={"OBSERVED_AID": FakeKever()},
        db=SimpleNamespace(
            knas=SimpleNamespace(get=lambda keys: None, rem=lambda keys: None),
            ksns=SimpleNamespace(rem=lambda keys: None),
        ),
    )

    sentinal = Sentinal(
        hby=fakeHby,
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
    assert query.error == "Missing witness endpoint: unable to query witness WIT_1, no http endpoint"


@pytest.mark.parametrize(
    ("escrowTock", "expectedCount"),
    ((None, 2), ("1.0", 1)),
)
def test_escrow_doer_processes_escrows_at_configured_cadence(
    monkeypatch, escrowTock, expectedCount
):
    monkeypatch.delenv("WATOPNET_ESCROW_TOCK", raising=False)
    if escrowTock is not None:
        monkeypatch.setenv("WATOPNET_ESCROW_TOCK", escrowTock)

    kvy = MagicMock()
    rvy = MagicMock()
    tvy = MagicMock()
    exc = MagicMock()
    doer = watching.EscrowDoer(kvy=kvy, rvy=rvy, tvy=tvy, exc=exc)

    doist = doing.Doist(tock=0.03125, limit=1.0, doers=[doer])
    doist.do()

    assert kvy.processEscrows.call_count == expectedCount
    assert rvy.processEscrowReply.call_count == expectedCount
    assert tvy.processEscrows.call_count == expectedCount
    assert exc.processEscrow.call_count == expectedCount


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
