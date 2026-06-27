def test_release_validator_keeps_installer_optional_by_default(tmp_path, monkeypatch):
    from scripts import validate_release

    monkeypatch.setattr(validate_release, "ROOT", tmp_path)
    validator = validate_release.ReleaseValidator("v1.6.1")

    validator.validate_installer_artifact()

    assert not validator.failures
    assert any("MUG_Setup_v1.6.1.exe does not exist yet" in line for line in validator.infos)


def test_release_validator_requires_installer_in_strict_mode(tmp_path, monkeypatch):
    from scripts import validate_release

    monkeypatch.setattr(validate_release, "ROOT", tmp_path)
    validator = validate_release.ReleaseValidator("v1.6.1", require_installer=True)

    validator.validate_installer_artifact()

    assert validator.failures == ["MUG_Setup_v1.6.1.exe does not exist yet"]


def test_release_validator_reports_installer_size_and_sha256(tmp_path, monkeypatch):
    from scripts import validate_release

    installer_dir = tmp_path / "installer"
    installer_dir.mkdir()
    installer = installer_dir / "MUG_Setup_v1.6.1.exe"
    installer.write_bytes(b"installer")

    monkeypatch.setattr(validate_release, "ROOT", tmp_path)
    validator = validate_release.ReleaseValidator("v1.6.1", require_installer=True)

    validator.validate_installer_artifact()

    assert not validator.failures
    assert any("size: 9 bytes" in line for line in validator.infos)
    assert any("SHA256 MUG_Setup_v1.6.1.exe:" in line for line in validator.infos)
