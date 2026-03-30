# -*- encoding: utf-8 -*-

import pytest
import random
import io
from keri.help import helping


@pytest.fixture()
def mockHelpingNowUTC(monkeypatch):
    """
    Replace nowUTC universally with fixed value for testing
    """

    def mockNowUTC():
        """
        Use predetermined value for now (current time)
        '2021-01-01T00:00:00.000000+00:00'
        """
        return helping.fromIso8601("2021-01-01T00:00:00.000000+00:00")

    monkeypatch.setattr(helping, "nowUTC", mockNowUTC)


@pytest.fixture
def multipart():
    return Multipart


class Multipart:
    @staticmethod
    def create(fargs, content_type="text/plain; charset=utf-8"):
        """
        Basic emulation of a browser's multipart file upload
        """
        boundary = "____________{0:012x}".format(
            random.randint(123456789, 0xFFFFFFFFFFFF)
        )
        buff = io.BytesIO()
        for fieldname, data in fargs.items():
            buff.write(b"--")
            buff.write(boundary.encode())
            buff.write(b"\r\n")
            buff.write(f'Content-Disposition: form-data; name="{fieldname}"'.encode())
            buff.write(b"\r\n")
            buff.write(f"Content-Type: {content_type}".encode())
            buff.write(b"\r\n")
            buff.write(b"\r\n")
            buff.write(data)
            buff.write(b"\r\n--")
            buff.write(boundary.encode())
            buff.write(b"--\r\n")

        headers = {
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Content-Length": str(buff.tell()),
        }
        return buff.getvalue(), headers
