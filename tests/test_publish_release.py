from argparse import Namespace

import pytest

from scripts.publish_release import build_release_notes, normalize_version, require_confirmation


def test_normalize_version_accepts_optional_v_prefix():
    assert normalize_version("1.4.1") == ("v1.4.1", "1.4.1")
    assert normalize_version("v1.4.1") == ("v1.4.1", "1.4.1")


def test_build_release_notes_uses_changelog_sections():
    notes = build_release_notes(
        "v1.4.1",
        "9297AE46BCC6FEC4AD34A6F09849BCDCEAFDCF04EC1AAC757ABD5F960499B009",
    )

    assert "## Release Description" in notes
    assert "## Infrastructure" in notes
    assert "background worker" in notes
    assert "## Tests" in notes
    assert "update-check timeout/error tests" in notes
    assert "## Breaking Changes\n\nNone." in notes
    assert "9297AE46BCC6FEC4AD34A6F09849BCDCEAFDCF04EC1AAC757ABD5F960499B009" in notes


def test_publish_github_refuses_skip_tests():
    args = Namespace(
        commit=False,
        tag=False,
        push=False,
        publish_github=True,
        yes=True,
        skip_tests=True,
    )

    with pytest.raises(SystemExit, match="skip-tests"):
        require_confirmation(args)
