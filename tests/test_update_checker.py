import requests

from core.update_checker import (
    GITHUB_RELEASE_API,
    UPDATE_REQUEST_HEADERS,
    UPDATE_REQUEST_TIMEOUT_SECONDS,
    UpdateChecker,
)
from ui.main_window import UpdateCheckWorker


def _release_payload(assets):
    return {
        "tag_name": "v1.3.4",
        "name": "MUG v1.3.4",
        "html_url": "https://github.com/pancotto/MUG/releases/tag/v1.3.4",
        "body": "release notes",
        "assets": assets,
    }


def _mock_response(monkeypatch, payload):
    class Response:
        status_code = 200

        def json(self):
            return payload

    monkeypatch.setattr(
        "core.update_checker.requests.get",
        lambda *args, **kwargs: Response(),
    )


def test_get_latest_release_uses_timeout_and_user_agent(monkeypatch):
    calls = []

    class Response:
        status_code = 200

        def json(self):
            return _release_payload([])

    def fake_get(*args, **kwargs):
        calls.append((args, kwargs))
        return Response()

    monkeypatch.setattr("core.update_checker.requests.get", fake_get)

    latest = UpdateChecker.get_latest_release()

    assert latest["version"] == "1.3.4"
    assert calls == [
        (
            (GITHUB_RELEASE_API,),
            {
                "timeout": UPDATE_REQUEST_TIMEOUT_SECONDS,
                "headers": UPDATE_REQUEST_HEADERS,
            },
        )
    ]


def test_get_latest_release_returns_none_on_request_error(monkeypatch):
    def raise_timeout(*args, **kwargs):
        raise requests.Timeout("slow network")

    monkeypatch.setattr("core.update_checker.requests.get", raise_timeout)

    assert UpdateChecker.get_latest_release() is None


def test_release_with_one_installer_asset_exposes_browser_download_url(monkeypatch):
    _mock_response(
        monkeypatch,
        _release_payload(
            [
                {
                    "name": "MUG_Setup_v1.3.4.exe",
                    "size": 42_000_000,
                    "browser_download_url": (
                        "https://github.com/pancotto/MUG/releases/download/"
                        "v1.3.4/MUG_Setup_v1.3.4.exe"
                    ),
                }
            ]
        ),
    )

    latest = UpdateChecker.get_latest_release()

    assert latest["version"] == "1.3.4"
    assert latest["html_url"] == "https://github.com/pancotto/MUG/releases/tag/v1.3.4"
    assert latest["browser_download_url"].endswith("MUG_Setup_v1.3.4.exe")
    assert latest["asset_name"] == "MUG_Setup_v1.3.4.exe"
    assert latest["asset_size"] == 42_000_000


def test_release_with_multiple_assets_prefers_setup_installer_exe(monkeypatch):
    _mock_response(
        monkeypatch,
        _release_payload(
            [
                {
                    "name": "MUG-portable.exe",
                    "size": 10,
                    "browser_download_url": "https://example.invalid/MUG-portable.exe",
                },
                {
                    "name": "notes.txt",
                    "size": 1,
                    "browser_download_url": "https://example.invalid/notes.txt",
                },
                {
                    "name": "MUG_Setup_v1.3.4.exe",
                    "size": 20,
                    "browser_download_url": "https://example.invalid/MUG_Setup_v1.3.4.exe",
                },
                {
                    "name": "MUG.zip",
                    "size": 30,
                    "browser_download_url": "https://example.invalid/MUG.zip",
                },
            ]
        ),
    )

    latest = UpdateChecker.get_latest_release()

    assert latest["asset_name"] == "MUG_Setup_v1.3.4.exe"
    assert latest["browser_download_url"] == "https://example.invalid/MUG_Setup_v1.3.4.exe"
    assert latest["asset_size"] == 20


def test_release_without_assets_keeps_html_url_fallback(monkeypatch):
    _mock_response(monkeypatch, _release_payload([]))

    latest = UpdateChecker.get_latest_release()

    assert latest["browser_download_url"] == ""
    assert latest["asset_name"] == ""
    assert latest["asset_size"] == 0
    assert UpdateChecker.get_preferred_download_url(latest) == latest["html_url"]


def test_update_available_preserves_browser_download_url_and_legacy_aliases(monkeypatch):
    monkeypatch.setattr(
        UpdateChecker,
        "get_latest_release",
        staticmethod(
            lambda: {
                "version": "1.3.4",
                "html_url": "https://github.com/pancotto/MUG/releases/tag/v1.3.4",
                "release_page_url": "https://github.com/pancotto/MUG/releases/tag/v1.3.4",
                "browser_download_url": (
                    "https://github.com/pancotto/MUG/releases/download/"
                    "v1.3.4/MUG_Setup_v1.3.4.exe"
                ),
                "asset_name": "MUG_Setup_v1.3.4.exe",
                "asset_size": 42_000_000,
                "body": "release notes",
            }
        ),
    )

    update = UpdateChecker.is_update_available("1.3.3")

    assert update["version"] == "1.3.4"
    assert update["browser_download_url"].endswith("MUG_Setup_v1.3.4.exe")
    assert update["asset_name"] == "MUG_Setup_v1.3.4.exe"
    assert update["asset_size"] == 42_000_000
    assert update["download_url"] == update["browser_download_url"]
    assert update["direct_download_url"] == update["browser_download_url"]


def test_fallback_to_html_url_when_browser_download_url_is_missing():
    update = {
        "version": "1.3.4",
        "html_url": "https://github.com/pancotto/MUG/releases/tag/v1.3.4",
        "browser_download_url": "",
    }

    assert (
        UpdateChecker.get_preferred_download_url(update)
        == "https://github.com/pancotto/MUG/releases/tag/v1.3.4"
    )


def test_legacy_download_url_still_works():
    update = {
        "version": "1.3.4",
        "html_url": "https://github.com/pancotto/MUG/releases/tag/v1.3.4",
        "download_url": "https://github.com/pancotto/MUG/releases/download/v1.3.4/MUG.exe",
    }

    assert (
        UpdateChecker.get_preferred_download_url(update)
        == "https://github.com/pancotto/MUG/releases/download/v1.3.4/MUG.exe"
    )


def test_asset_selection_is_deterministic_for_equal_scores(monkeypatch):
    _mock_response(
        monkeypatch,
        _release_payload(
            [
                {
                    "name": "z-installer.exe",
                    "size": 10,
                    "browser_download_url": "https://example.invalid/z-installer.exe",
                },
                {
                    "name": "a-installer.exe",
                    "size": 20,
                    "browser_download_url": "https://example.invalid/a-installer.exe",
                },
            ]
        ),
    )

    first = UpdateChecker.get_latest_release()
    second = UpdateChecker.get_latest_release()

    assert first == second
    assert first["asset_name"] == "a-installer.exe"


def test_update_check_worker_emits_update_without_live_network(monkeypatch):
    expected = {
        "version": "9.9.9",
        "browser_download_url": "https://example.invalid/MUG_Setup_v9.9.9.exe",
    }
    monkeypatch.setattr(
        UpdateChecker,
        "is_update_available",
        staticmethod(lambda current_version: expected),
    )

    worker = UpdateCheckWorker("1.4.0")
    finished = []
    errors = []
    worker.finished.connect(finished.append)
    worker.error.connect(errors.append)

    worker.run()

    assert finished == [expected]
    assert errors == []


def test_update_check_worker_emits_none_on_error(monkeypatch):
    def raise_error(current_version):
        raise RuntimeError("offline")

    monkeypatch.setattr(
        UpdateChecker,
        "is_update_available",
        staticmethod(raise_error),
    )

    worker = UpdateCheckWorker("1.4.0")
    finished = []
    errors = []
    worker.finished.connect(finished.append)
    worker.error.connect(errors.append)

    worker.run()

    assert finished == [None]
    assert errors == ["offline"]
