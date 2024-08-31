import json
import logging
import os
from datetime import datetime
from typing import Any

from util import is_micropython

from eventbus import bus

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class Config:
    def __init__(self):
        self.CONFIG_DIR = self._config_dir()
        self.CONFIG_FILE = os.path.join(self.CONFIG_DIR, "config.json")
        self._config = {}  # load may call get
        self._config = self._load()

        @bus.on("?config")
        async def on_config_get(topic, src, dst, path=None, default=None):
            """Get config values."""
            await bus.emit(topic="!config", dst=src, config=self.get(path, default))

        @bus.on("?config-version")
        async def on_config_version_get(topic, src, dst):
            """Get config version."""
            await bus.emit(topic="!config-version", dst=src, config=self.get("version"))

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
    
    def update(self):
        import glob, yaml

        # compile from yaml
        version = max(
            [
                os.path.getmtime(file)
                for file in glob.iglob(
                    os.path.join(self.CONFIG_DIR, "yaml-config", "**/*.yaml"), recursive=True
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

        # now load the config from yaml files
        cfg = {}
        for file in glob.iglob(
            os.path.join(self.CONFIG_DIR, "**/*.yaml"), recursive=True
        ):
            basename = os.path.splitext(os.path.basename(file))[0]
            cfg[basename] = yaml.safe_load(open(file, "r"))

        # save as json
        json.dump(cfg, open(self.CONFIG_FILE, "w"), indent=2)
        self.push_to_git(f"update to {version}")

        # advertise new version
        bus.emit_sync(topic="!config-version", version=version, dst="root")
        bus.emit_sync(topic="!config-version", version=version, dst="#leaves")

    def push_to_git(self, commit_msg: str):
        # push changes to git
        import git
        g = git.cmd.Git(self.CONFIG_DIR)  # type: ignore
        g.add(".")
        g.commit("-m", commit_msg)
        g.push()

    def pull_from_git(self):
        import git
        g = git.cmd.Git(self.CONFIG_DIR)
        g.pull()

    def _load(self):
        if is_micropython():
            return json.loads(open("/config.json").read())
        else:
            if not os.path.isfile(self.CONFIG_FILE):
                # fetch from github
                self.pull_from_git()
            if not os.path.isfile(self.CONFIG_FILE):
                # create from yaml
                self.update()
            return json.load(open(self.CONFIG_FILE))

    def _config_dir(self):
        repo_dir = "/home/repo"
        for repo_dir in os.getenv("REPO_DIR", repo_dir).split(":"):
            if os.path.isdir(repo_dir):
                break
        return os.path.join(repo_dir, f"{os.getenv('DEPLOY_NAME', '')}-config")

    async def leaf_id(self) -> str:
        """Get leaf id."""
        from app import radio
        mac_addr = await radio.mac_address()
        for leaf_id, leaf in self.get("leaves", {}).items():
            if leaf.get("mac_addr") == mac_addr:
                return leaf_id
        # create new leaf for this mac
        with open(os.path.join(self.CONFIG_DIR, "yaml-config", "leaves", "new_leaf.yaml"), "w") as f:
            f.write(f"mac_addr: {mac_addr}")
        self.push_to_git(f"new leaf with mac-address {mac_addr}")

        logger.info(f"new leaf with mac-address {mac_addr}")
        return "new_leaf"
