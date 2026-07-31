from pathlib import Path

from app.sources.robots import CachedPolicy
from app.sources.robots import RobotsPolicy as BaseRobotsPolicy

__all__ = ["CachedPolicy", "RobotsPolicy"]

BLOCK_MARKERS = ("hbblockandcaptcha", "access denied", "captcha")


class RobotsPolicy(BaseRobotsPolicy):
    def __init__(self, cache_directory: Path, cache_hours: int) -> None:
        super().__init__(
            cache_directory,
            cache_hours,
            robots_url="https://www.hepsiburada.com/robots.txt",
            user_agent="FirsatRadar",
            cache_name="hepsiburada-robots.json",
            block_markers=BLOCK_MARKERS,
        )
