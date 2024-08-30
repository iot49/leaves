import glob
import json
import logging
import os
from datetime import datetime
from typing import Any

import yaml
from util import is_micropython, mac_address

from eventbus import bus

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class Config:
    def __init__(self):
        self.CONFIG_DIR = self._config_dir()
        self._config = self._load()

        @bus.on("?config")
        async def on_config_get(topic, src, dst, path=None, default=None):
            """Get config values."""
            await bus.emit(topic="!config", dst=src, config=self.get(path, default))

        @bus.on("?config-version")
        async def on_config_version_get(topic, src, dst):
            """Get config version."""
            await bus.emit(topic="!config-version", dst=src, config=self.get("version"))

        @bus.on("!config-update")
        async def on_config_update(topic, src, dst):
            """Push changes to github and update config to newest version from yaml files on `root` leaf"""
            if dst != "root":
                logger.error("only root is allowed to push/update config")
                return
            await self.update()

    def get(self, path=None, default=None) -> Any:
        """Get configuration value.

        Examples:
            config.get("version")
            config.get("wifi")
        """
        if not path:
            return self._config
        path = path.split("/")
        res = self._config
        try:
            for p in path:
                res = res[p]
        except (KeyError, AttributeError):
            return default
        return res

    async def update(self):
        """Push changes to the git repo and set version."""

        # determine version from file modification times
        version = max(
            [
                os.path.getmtime(file)
                for file in glob.iglob(
                    os.path.join(self.CONFIG_DIR, "**/*.yaml"), recursive=True
                )
            ]
        )
        version = datetime.fromtimestamp(version).isoformat()
        if version == self.get("version"):
            print("already up to date")
            return
        print(
            f'# machine generated\nversion: "{version}"',
            file=open(os.path.join(self.CONFIG_DIR, "version.yaml"), "w"),
        )

        # push changes to git
        import git

        g = git.cmd.Git(self.CONFIG_DIR)  # type: ignore
        g.add(".")
        g.commit("-m", f"update to {version}")
        g.push()

        # load new config
        self._config = self._load()

        # advertise new version
        await bus.emit(topic="!config-version", version=version)

    def _load(self):
        if is_micropython():
            # micropython ports don't have yaml
            return json.loads(open("/config/config.json").read())
        else:
            # fetch latest version
            import git

            g = git.cmd.Git(self.CONFIG_DIR)  # type: ignore
            g.pull()

            # now load the config from yaml files
            cfg = {}
            for file in glob.iglob(
                os.path.join(self.CONFIG_DIR, "**/*.yaml"), recursive=True
            ):
                basename = os.path.splitext(os.path.basename(file))[0]
                cfg[basename] = yaml.safe_load(open(file, "r"))
            return cfg

    def _config_dir(self):
        cfg_dir = "/home/config/config"
        for cfg_dir in os.getenv("CONFIG_DIR", cfg_dir).split(":"):
            if os.path.isdir(cfg_dir):
                break
        return cfg_dir

    def leaf_id(self) -> str:
        """Get leaf id."""
        mac_addr = mac_address()
        for leaf_id, leaf in self.get("leaves", {}).items():
            if leaf.get("mac_addr") == mac_addr:
                return leaf_id
        # leaf not in config ... (MacOS returns random mac addresses)
        # return mac_addr
        return "root"
