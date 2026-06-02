import requests
from packaging.version import Version


GITHUB_RELEASE_API = (
    "https://api.github.com/repos/pancotto/MUG/releases/latest"
)


class UpdateChecker:

    @staticmethod
    def _find_windows_installer_asset(data: dict) -> dict:
        assets = data.get("assets") or []
        if not isinstance(assets, list):
            return {}

        exe_assets = []
        for asset in assets:
            if not isinstance(asset, dict):
                continue

            raw_name = str(asset.get("name", "")).strip()
            name = raw_name.lower()
            browser_download_url = str(asset.get("browser_download_url", "")).strip()
            if not name.endswith(".exe") or not browser_download_url:
                continue

            score = 0
            if "setup" in name or "installer" in name:
                score += 2
            if "mug" in name:
                score += 1

            exe_assets.append((score, name, raw_name, browser_download_url, asset.get("size", 0)))

        if not exe_assets:
            return {}

        exe_assets.sort(key=lambda item: (-item[0], item[1]))
        selected = exe_assets[0]
        return {
            "asset_name": selected[2],
            "browser_download_url": selected[3],
            "asset_size": selected[4] or 0,
        }

    @staticmethod
    def get_release_page_url(update: dict | None) -> str:
        if not update:
            return ""

        return str(
            update.get("release_page_url")
            or update.get("html_url")
            or ""
        ).strip()

    @staticmethod
    def get_direct_download_url(update: dict | None) -> str:
        if not update:
            return ""

        return str(
            update.get("browser_download_url")
            or update.get("direct_download_url")
            or update.get("download_url")
            or ""
        ).strip()

    @staticmethod
    def get_preferred_download_url(update: dict | None) -> str:
        return (
            UpdateChecker.get_direct_download_url(update)
            or UpdateChecker.get_release_page_url(update)
        )

    @staticmethod
    def get_latest_release():

        try:

            response = requests.get(
                GITHUB_RELEASE_API,
                timeout=5,
                headers={
                    "User-Agent": "MUG"
                }
            )

            if response.status_code != 200:
                return None

            data = response.json()

            version = (
                data.get("tag_name", "")
                .replace("v", "")
                .strip()
            )
            installer_asset = UpdateChecker._find_windows_installer_asset(data)
            browser_download_url = installer_asset.get("browser_download_url", "")

            return {
                "version": version,
                "name": data.get("name", ""),
                "release_page_url": data.get("html_url", ""),
                "browser_download_url": browser_download_url,
                "asset_name": installer_asset.get("asset_name", ""),
                "asset_size": installer_asset.get("asset_size", 0),
                "direct_download_url": browser_download_url,
                "html_url": data.get("html_url", ""),
                "download_url": browser_download_url,
                "body": data.get("body", ""),
            }

        except Exception as e:

            print(f"[UPDATE CHECK ERROR] {e}")

            return None

    @staticmethod
    def is_update_available(current_version: str):

        latest = UpdateChecker.get_latest_release()

        if not latest:
            return None

        try:

            current = Version(current_version)
            remote = Version(latest["version"])

            print(f"Atual: {current}")
            print(f"Remota: {remote}")

            if remote > current:

                print("[UPDATE CHECK] Atualização disponível")

                return {
                    "version": latest["version"],
                    "release_page_url": latest.get("release_page_url") or latest.get("html_url", ""),
                    "browser_download_url": latest.get("browser_download_url") or latest.get("direct_download_url") or latest.get("download_url", ""),
                    "asset_name": latest.get("asset_name", ""),
                    "asset_size": latest.get("asset_size", 0),
                    "direct_download_url": latest.get("direct_download_url") or latest.get("browser_download_url") or latest.get("download_url", ""),
                    "html_url": latest.get("html_url") or latest.get("release_page_url", ""),
                    "download_url": latest.get("download_url") or latest.get("browser_download_url") or latest.get("direct_download_url", ""),
                    "body": latest.get("body", ""),
                }

        except Exception as e:

            print(f"[UPDATE CHECK ERROR] {e}")

        return None
