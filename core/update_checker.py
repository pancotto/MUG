import requests
from packaging.version import Version


GITHUB_RELEASE_API = (
    "https://api.github.com/repos/pancotto/MUG/releases/latest"
)

GITHUB_RELEASE_DOWNLOAD_BASE = (
    "https://github.com/pancotto/MUG/releases/download"
)


class UpdateChecker:

    @staticmethod
    def build_installer_download_url(version: str) -> str:
        tag = version.strip()
        if not tag.startswith("v"):
            tag = f"v{tag}"

        return (
            f"{GITHUB_RELEASE_DOWNLOAD_BASE}/{tag}/"
            f"MUG_Setup_{tag}.exe"
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

            return {
                "version": version,
                "name": data.get("name", ""),
                "html_url": data.get("html_url", ""),
                "download_url": UpdateChecker.build_installer_download_url(version),
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
                    "html_url": latest["html_url"],
                    "download_url": latest["download_url"],
                    "body": latest.get("body", ""),
                }

        except Exception as e:

            print(f"[UPDATE CHECK ERROR] {e}")

        return None
