import random

import pytest
import requests

from zensvi.download.base import BaseDownloader


class DummyDownloader(BaseDownloader):
    """Concrete implementation of ``BaseDownloader`` for testing."""

    def _filter_pids_date(self, pid_df, start_date, end_date):  # pragma: no cover - not used in tests
        return pid_df

    def download_svi(self, *args, **kwargs):  # pragma: no cover - not used in tests
        raise NotImplementedError


class DummyResponse:
    def __init__(self):
        self.status_code = 200

    def raise_for_status(self):
        return None


@pytest.fixture
def downloader():
    dl = DummyDownloader()
    dl._proxies = [{"http": "proxy"}]  # Reduce proxy pool for deterministic tests
    return dl


def test_request_get_attempts_direct_first(monkeypatch, downloader):
    calls = []

    def fake_get(url, **kwargs):
        calls.append(kwargs.get("proxies"))
        return DummyResponse()

    monkeypatch.setattr(requests, "get", fake_get)

    response = downloader._request_get("http://example.com", max_attempts=3, check_status=True)

    assert isinstance(response, DummyResponse)
    assert calls == [None]


def test_request_get_falls_back_to_proxy(monkeypatch, downloader):
    calls = []

    def fake_get(url, **kwargs):
        calls.append(kwargs.get("proxies"))
        if kwargs.get("proxies") is None:
            raise requests.exceptions.Timeout("timeout")
        return DummyResponse()

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])

    response = downloader._request_get("http://example.com", max_attempts=3, check_status=True)

    assert isinstance(response, DummyResponse)
    assert calls[0] is None
    assert calls[1] == {"http": "proxy"}
