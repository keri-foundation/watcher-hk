# -*- encoding: utf-8 -*-

"""
KERI
watopnet.core.tcp.serving module

TCP server layer for the watcher: Directant accepts incoming connections and
spawns a Reactant per connection to parse CESR query messages and send signed replies.
"""

from hio.base import doing
from hio.help import decking
from keri import help
from keri.core import parsing

from watopnet.core import eventing

logger = help.ogler.getLogger()


class Directant(doing.DoDoer):
    """DoDoer that manages a TCP server and spawns a Reactant for each accepted connection.

    Runs a ``serviceDo`` generator that polls the server's connection table, creates a
    new Reactant for each fresh connection, and closes connections that have timed out
    or been cut off.
    """

    def __init__(self, server, wty, doers=None, **kwa):
        """
        Parameters:
            server (ServerIocp): hio TCP server instance (managed externally by another doer)
            wty (Watchery): registry of active watcher instances
            doers (list | None): additional doers to include
            **kwa: forwarded to DoDoer
        """
        self.wty = wty
        self.server = server
        self.rants = dict()
        doers = doers if doers is not None else []
        doers.extend([doing.doify(self.serviceDo)])
        super(Directant, self).__init__(doers=doers, **kwa)
        if self.tymth:
            self.server.wind(self.tymth)

    def wind(self, tymth):
        """Propagate the injected tymist to both the DoDoer and the TCP server.

        Parameters:
            tymth: injected tymist wrapper
        """
        super(Directant, self).wind(tymth)
        self.server.wind(tymth)

    def serviceDo(self, tymth=None, tock=0.0, **kwa):
        """Generator that services incoming TCP connections indefinitely.

        For each accepted connection, creates a Reactant doer and adds it to
        the running scheduler.  Closes timed-out and cut-off connections.

        Parameters:
            tymth: injected tymist wrapper
            tock (float): scheduling interval
        """
        self.wind(tymth)
        self.tock = tock
        yield self.tock

        while True:
            for ca, ix in list(self.server.ixes.items()):
                if ix.cutoff:
                    self.closeConnection(ca)
                    continue

                if ca not in self.rants:
                    rant = Reactant(tymth=self.tymth, wty=self.wty, remoter=ix)
                    self.rants[ca] = rant
                    self.extend(doers=[rant])

                if ix.tymeout > 0.0 and ix.tymer.expired:
                    self.closeConnection(ca)

            yield

    def closeConnection(self, ca):
        """Flush pending sends, remove the connection, and stop the associated Reactant.

        Parameters:
            ca: connection address key used in the server's ``ixes`` table
        """
        if ca in self.server.ixes:
            self.server.ixes[ca].serviceSends()
        self.server.removeIx(ca)
        if ca in self.rants:
            self.remove([self.rants[ca]])
            del self.rants[ca]


class Reactant(doing.DoDoer):
    """DoDoer that handles a single TCP connection: parses inbound CESR and sends replies.

    Owns a ``KeveryQueryShim`` parser that accepts only query messages and routes them
    to the appropriate watcher.  Reply and replay cues produced by the shim are
    sent back over the TCP connection by ``cueDo``.
    """

    def __init__(self, wty, remoter, doers=None, **kwa):
        """
        Parameters:
            wty (Watchery): registry of active watcher instances
            remoter (RemoteTcpIocp): hio TCP remoter for this connection
            doers (list | None): additional doers to include
            **kwa: forwarded to DoDoer
        """
        self.cues = decking.Deck()
        self.wty = wty
        self.kvy = eventing.KeveryQueryShim(wty=wty, cues=self.cues)
        self.remoter = remoter

        doers = doers if doers is not None else []
        doers.extend([doing.doify(self.remoteDo), doing.doify(self.cueDo)])

        self.parser = parsing.Parser(ims=self.remoter.rxbs, kvy=self.kvy, framed=True)

        super(Reactant, self).__init__(doers=doers, **kwa)
        if self.tymth:
            self.remoter.wind(self.tymth)

    def wind(self, tymth):
        """Propagate the injected tymist to both the DoDoer and the TCP remoter.

        Parameters:
            tymth: injected tymist wrapper
        """
        super(Reactant, self).wind(tymth)
        self.remoter.wind(tymth)

    def remoteDo(self, tymth=None, tock=0.0, **kwa):
        """Generator that drives the CESR parser over the TCP receive buffer indefinitely.

        Parameters:
            tymth: injected tymist wrapper
            tock (float): scheduling interval
        """
        self.wind(tymth)
        self.tock = tock
        yield self.tock

        done = yield from self.parser.parsator(local=True)
        return done

    def cueDo(self, tymth=None, tock=0.0, **kwa):
        """Generator that drains the cue deck and sends signed replies back to the client.

        Handles ``replay`` cues by forwarding raw messages, and ``reply`` cues by
        endorsing the serder with the watcher's hab and sending the result.

        Parameters:
            tymth: injected tymist wrapper
            tock (float): scheduling interval
        """
        self.wind(tymth)
        self.tock = tock
        yield self.tock

        while True:
            while self.cues:
                cue = self.cues.pull()
                cueKin = cue["kin"]

                if cueKin in ("replay",):
                    msgs = cue["msgs"]
                    for msg in msgs:
                        self.sendMessage(msg)

                elif cueKin in ("reply",):
                    serder = cue["serder"]
                    wid = cue["src"]
                    watcher = self.wty.lookup(wid)

                    msg = watcher.hab.endorse(serder=serder)
                    self.sendMessage(msg)

                yield
            yield

    def sendMessage(self, msg):
        """Send bytes to the remote TCP client.

        Parameters:
            msg (bytes | bytearray): CESR message to transmit
        """
        self.remoter.tx(msg)
