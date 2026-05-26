import tomllib
from pathlib import Path

from bench_cli.exceptions import BenchError

_BENCH_TOML_TEMPLATE = """\
[bench]
name = "{name}"
python = "3.14"
http_port = {http_port}
socketio_port = {socketio_port}

[[apps]]
name = "frappe"
repo = "https://github.com/frappe/frappe"
branch = "version-16"

[mariadb]
host = "localhost"
port = 3306
root_password = "root"
# version = "10.6"

[redis]
port = {redis_port}
# or use separate ports:
# cache_port = {redis_cache_port}
# queue_port = {redis_queue_port}
# socketio_port = {redis_socketio_port}

[workers]
default = 2
short = 1
long = 1

[admin]
port = {admin_port}
enabled = false
timeout = 180
"""

_DEFAULT_PORTS = {
    "http_port":             8000,
    "socketio_port":         9000,
    "admin_port":            8002,
    "redis_port":           13000,
    "redis_cache_port":     13000,
    "redis_queue_port":     11000,
    "redis_socketio_port":  12000,
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

        ports = self._make_ports(benches_dir)

        print(f"Creating bench directory: {self.target_directory}")
        self.target_directory.mkdir(parents=True, exist_ok=True)

        print("Writing bench.toml")
        bench_toml.write_text(_BENCH_TOML_TEMPLATE.format(name=self.name, **ports))

        print(f"\nBench '{self.name}' created at {self.target_directory}")
        print(f"\nNext steps:")
        print(f"  1. Edit the config:  {bench_toml}")
        print(f"  2. Run:              bench init")
        print(f"  3. Create a site:    bench new-site site1.localhost")

    def _make_ports(self, benches_dir: Path) -> dict[str, int]:
        """Pick ports as max+1 of sibling claims, or defaults if no siblings."""
        ports = dict(_DEFAULT_PORTS)
        existing_ports: dict[str, list[int]] = {key: [] for key in ports}

        if benches_dir.is_dir():
            for entry in benches_dir.iterdir():
                if not entry.is_dir():
                    continue
                for key, value in self._get_existing_ports(entry / "bench.toml").items():
                    existing_ports[key].append(value)

        for key, claimed in existing_ports.items():
            if claimed:
                ports[key] = max(claimed) + 1

        return ports

    def _get_existing_ports(self, toml_path: Path) -> dict[str, int]:
        """Return ports declared in one bench.toml. Missing/unreadable → empty dict."""
        ports: dict[str, int] = {}
        if not toml_path.is_file():
            return ports
        try:
            with toml_path.open("rb") as fh:
                config = tomllib.load(fh)
        except (tomllib.TOMLDecodeError, OSError):
            return ports

        bench = config.get("bench") or {}
        admin = config.get("admin") or {}
        redis = config.get("redis") or {}

        if isinstance(bench.get("http_port"), int):
            ports["http_port"] = bench["http_port"]
        if isinstance(bench.get("socketio_port"), int):
            ports["socketio_port"] = bench["socketio_port"]
        if isinstance(admin.get("port"), int):
            ports["admin_port"] = admin["port"]

        if isinstance(redis.get("port"), int):
            ports["redis_port"] = redis["port"]
        if isinstance(redis.get("cache_port"), int):
            ports["redis_cache_port"] = redis["cache_port"]
        if isinstance(redis.get("queue_port"), int):
            ports["redis_queue_port"] = redis["queue_port"]
        if isinstance(redis.get("socketio_port"), int):
            ports["redis_socketio_port"] = redis["socketio_port"]

        return ports
