# -*- encoding: utf-8 -*-

from types import SimpleNamespace

import falcon
import pytest
from falcon import testing

from watopnet.core import basing
from watopnet.core import httping as wat_httping


def test_throttle_process_request_unwraps_tuple_remote_addr():
    """Under the Ioflo WSGI server ``remote_addr`` is a ``(host, port)`` tuple.

    Regression test: a tuple ``remote_addr`` previously crashed with
    ``TypeError: sequence item 0: expected str instance, tuple found``
    inside the Komer key serialization, producing an HTTP 500 on every
    public request to the watcher. The tuple must be unwrapped to the
    host string before it is used as a database key.
    """
    db = basing.Baser(name="keri-v2-throttle-tuple", temp=True)
    try:
        throttle = wat_httping.Throttle(db=db)
        req = SimpleNamespace(remote_addr=("1.2.3.4", 7632), access_route=[])
        resp = SimpleNamespace(complete=False, status=None)

        throttle.process_request(req, resp)

        assert resp.complete is False
        assert resp.status is None
        reqs = db.ips.get(keys=("1.2.3.4",))
        assert reqs is not None
        assert reqs.count == 1
    finally:
        db.close(clear=True)


def test_throttle_process_request_does_not_trust_route_without_peer():
    """Missing socket-peer data must not make a forwarding route authoritative."""
    db = basing.Baser(name="keri-v2-throttle-fallback", temp=True)
    try:
        throttle = wat_httping.Throttle(db=db)
        req = SimpleNamespace(remote_addr=None, access_route=["5.6.7.8"])
        resp = SimpleNamespace(complete=False, status=None)

        throttle.process_request(req, resp)

        assert resp.complete is False
        assert resp.status is None
        reqs = db.ips.get(keys=("5.6.7.8",))
        assert reqs is None
        reqs = db.ips.get(keys=("unknown",))
        assert reqs is not None
        assert reqs.count == 1
    finally:
        db.close(clear=True)


def test_throttle_process_request_rejects_when_over_limit(mockHelpingNowUTC):
    """Requests beyond ``MaximumRequests`` within a window receive HTTP 429."""
    db = basing.Baser(name="keri-v2-throttle-limit", temp=True)
    try:
        throttle = wat_httping.Throttle(db=db)
        req = SimpleNamespace(remote_addr="9.9.9.9", access_route=[])
        resp = SimpleNamespace(complete=False, status=None)

        for _ in range(throttle.MaximumRequests + 1):
            throttle.process_request(req, resp)

        assert resp.complete is True
        assert resp.status == falcon.HTTP_TOO_MANY_REQUESTS
    finally:
        db.close(clear=True)


@pytest.mark.parametrize(
    "headers",
    [
        {"X-Forwarded-For": "198.51.100.99"},
        {"Forwarded": "for=198.51.100.99"},
        {"X-Real-IP": "198.51.100.99"},
    ],
    ids=("x-forwarded-for", "forwarded", "x-real-ip"),
)
def test_throttle_process_request_ignores_direct_client_forwarding_data(headers):
    """Forwarding data cannot replace the identity of a direct client."""
    req = testing.create_req(remote_addr="203.0.113.10", headers=headers)

    assert req.access_route[0] == "198.51.100.99"
    assert wat_httping._client_ip(req) == "203.0.113.10"


def test_throttle_process_request_uses_direct_ipv6_peer():
    """A direct IPv6 socket peer is used without forwarding data."""
    assert wat_httping._client_ip(
        SimpleNamespace(remote_addr="2001:db8::10", access_route=[])
    ) == "2001:db8::10"


def test_throttle_process_request_uses_route_from_trusted_ipv4_proxy():
    """A loopback proxy may supply Falcon's original-client route."""
    req = testing.create_req(
        remote_addr="127.0.0.1", headers={"X-Forwarded-For": "203.0.113.10"}
    )

    assert req.access_route == ["203.0.113.10", "127.0.0.1"]
    assert wat_httping._client_ip(req) == "203.0.113.10"


def test_throttle_process_request_uses_route_from_trusted_ipv6_proxy():
    """IPv6 loopback has the same explicit trusted-proxy behavior."""
    req = testing.create_req(
        remote_addr="::1", headers={"Forwarded": 'for="[2001:db8::10]"'}
    )

    assert req.access_route == ["2001:db8::10", "::1"]
    assert wat_httping._client_ip(req) == "2001:db8::10"


def test_throttle_process_request_uses_first_falcon_route_hop_for_proxy():
    """Falcon orders access_route from original client through proxy hops."""
    req = testing.create_req(
        remote_addr="127.0.0.1",
        headers={"X-Forwarded-For": "203.0.113.10, 198.51.100.20"},
    )

    assert req.access_route == ["203.0.113.10", "198.51.100.20", "127.0.0.1"]
    assert wat_httping._client_ip(req) == "203.0.113.10"


@pytest.mark.parametrize("route", ([], ["not-an-ip"], ["", "127.0.0.1"]))
def test_throttle_process_request_falls_back_safely_for_invalid_proxy_route(route):
    """Malformed or absent forwarding data keeps the trusted peer as the key."""
    assert wat_httping._client_ip(
        SimpleNamespace(remote_addr="127.0.0.1", access_route=route)
    ) == "127.0.0.1"
