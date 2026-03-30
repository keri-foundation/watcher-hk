# -*- encoding: utf-8 -*-

"""
KERI
testing watopnet.core.watching package

"""
from keri.app import habbing
from keri.core import eventing
from watopnet.core import basing
from watopnet.app.watching import Watcher, Watchery


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
