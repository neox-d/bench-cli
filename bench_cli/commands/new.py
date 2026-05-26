import tomllib
from collections import defaultdict
from pathlib import Path

from bench_cli.exceptions import BenchError
from bench_cli.utils import write_toml


_DEFAULT_PORTS = {
    "http_port":            8000,
    "socketio_port":        9000,
    "admin_port":           8002,
    "redis_port":          13000,
    "redis_cache_port":    13000,
    "redis_queue_port":    11000,
    "redis_socketio_port": 12000,
}


class NewCommand:
    def __init__(self, target_directory: Path, name: str) -> None:
        self.target_directory = target_directory
        self.name = name

    def run(self) -> None:
        bench_toml = self.target_directory / "bench.toml"
        if bench_toml.exists():
            raise BenchError(
                f"A bench named '{self.name}' already exists at {self.target_directory}. "
                "Choose a different name or remove the existing bench."
            )

        benches_dir = self.target_directory.parent
        if not benches_dir.exists():
            print(f"Creating benches directory at {benches_dir}")
            benches_dir.mkdir(parents=True, exist_ok=True)

        ports = self._allocate_ports(benches_dir)

        print(f"Creating bench directory: {self.target_directory}")
        self.target_directory.mkdir(parents=True, exist_ok=True)

        print("Writing bench.toml")
        write_toml(bench_toml, self._build_config(ports))

        print(f"\nBench '{self.name}' created at {self.target_directory}")
        print("\nNext steps:")
        print(f"  1. Edit the config:  {bench_toml}")
        print( "  2. Run:              bench init")
        print( "  3. Create a site:    bench new-site site1.localhost")

    def _build_config(self, ports: dict[str, int]) -> dict:
        return {
            "bench": {
                "name": self.name,
                "python": "3.14",
                "http_port": ports["http_port"],
                "socketio_port": ports["socketio_port"],
            },
            "apps": [
                {
                    "name": "frappe",
                    "repo": "https://github.com/frappe/frappe",
                    "branch": "version-16",
                },
            ],
            "mariadb": {
                "host": "localhost",
                "port": 3306,
                "root_password": "root",
            },
            "redis": {
                "port": ports["redis_port"],
            },
            "workers": {
                "default": 2,
                "short": 1,
                "long": 1,
            },
            "admin": {
                "port": ports["admin_port"],
                "enabled": False,
                "timeout": 180,
            },
        }

    def _allocate_ports(self, benches_dir: Path) -> dict[str, int]:
        # Ports drift upward over time — we never reclaim freed ports from
        # deleted benches. Fine for a dev tool; revisit if it becomes a problem.
        claimed: dict[str, list[int]] = defaultdict(list)
        if benches_dir.is_dir():
            for entry in benches_dir.iterdir():
                if entry.is_dir() and not entry.name.startswith("."):
                    for key, port in self._get_existing_ports(entry / "bench.toml").items():
                        claimed[key].append(port)

        ports: dict[str, int] = {}
        for key, default in _DEFAULT_PORTS.items():
            if claimed[key]:
                ports[key] = max(claimed[key]) + 1
            else:
                ports[key] = default
        return ports

    def _get_existing_ports(self, toml_path: Path) -> dict[str, int]:
        """Return ports declared in one bench.toml. Missing/unreadable -> empty dict."""
        if not toml_path.is_file():
            return {}
        try:
            with toml_path.open("rb") as fh:
                config = tomllib.load(fh)
        except (tomllib.TOMLDecodeError, OSError):
            return {}

        ports: dict[str, int] = {}

        # 1. Extract [bench] ports
        bench = config.get("bench", {})
        for key in ("http_port", "socketio_port"):
            if isinstance(val := bench.get(key), int):
                ports[key] = val

        # 2. Extract [admin] port
        if isinstance(val := config.get("admin", {}).get("port"), int):
            ports["admin_port"] = val

        # 3. Extract [redis] ports (shared and split modes are mutually exclusive)
        redis = config.get("redis", {})
        if isinstance(shared_port := redis.get("port"), int):
            ports["redis_port"] = shared_port
        else:
            for key in ("cache_port", "queue_port", "socketio_port"):
                if isinstance(val := redis.get(key), int):
                    ports[f"redis_{key}"] = val

        return ports
