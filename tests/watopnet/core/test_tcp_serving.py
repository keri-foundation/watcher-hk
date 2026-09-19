# -*- encoding: utf-8 -*-

"""
KERI
testing watopnet.core.tcp.serving module

"""

from types import SimpleNamespace

from watopnet.core.tcp.serving import Reactant

WATCHER_AID = "BGbLRtLXIslZvTfYz97dS9_EzQxp8kSTAMMtW-LmlXMI"


def test_tcp_reactant_drops_stale_reply_cue_without_crashing():
    remoter = SimpleNamespace(
        rxbs=bytearray(), wind=lambda tymth: None, tx=lambda msg: None
    )
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
