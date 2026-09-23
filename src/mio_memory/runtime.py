"""Manual, private lifecycle control. No note writes, autostart, or public listener."""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import signal
import socket
import stat
import subprocess
import sys
import threading
import time
from urllib.parse import urlsplit
import urllib.request


class RuntimeErrorSafe(ValueError):
    """A diagnostic safe to return as JSON without credentials or note bodies."""


def default_state_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/Mio Memory"
    return Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "mio-memory"


def checkout_root() -> Path | None:
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").is_file() and (parent / "src/mio_memory").is_dir():
            return parent
    return None


def _inside(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def _outside_private_source(path: Path, vault: Path | None = None) -> None:
    repo = checkout_root()
    if repo and _inside(path, repo):
        raise RuntimeErrorSafe("State and credentials must be outside the project checkout.")
    if vault and _inside(path, vault):
        raise RuntimeErrorSafe("State and credentials must be outside the note vault.")


def state_path(value: str | Path | None, *, create: bool = False, vault: Path | None = None) -> Path:
    path = Path(value or default_state_dir()).expanduser()
    if path.is_symlink():
        raise RuntimeErrorSafe("The state directory must not be a symbolic link.")
    path = path.resolve()
    _outside_private_source(path, vault)
    if create:
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.exists():
        info = path.stat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
            raise RuntimeErrorSafe("The state directory must be an owned directory.")
        if info.st_mode & 0o077:
            raise RuntimeErrorSafe("The state directory needs owner-only permissions (chmod 700).")
    return path


def read_json(path: Path, *, missing: dict | None = None) -> dict:
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except FileNotFoundError:
        if missing is not None:
            return missing
        raise RuntimeErrorSafe("Configuration is missing; run init first.") from None
    except OSError:
        raise RuntimeErrorSafe("Could not open a private runtime file safely.") from None
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise RuntimeErrorSafe("Runtime files need owner-only permissions (chmod 600).")
        with os.fdopen(fd, encoding="utf-8") as stream:
            fd = -1
            raw = stream.read(128 * 1024 + 1)
        if len(raw) > 128 * 1024:
            raise RuntimeErrorSafe("Runtime configuration is too large.")
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError
        return data
    except RuntimeErrorSafe:
        raise
    except (ValueError, UnicodeError):
        raise RuntimeErrorSafe("Runtime configuration is invalid JSON.") from None
    finally:
        if fd != -1:
            os.close(fd)


def write_json(path: Path, data: dict, *, exclusive: bool = False) -> None:
    temporary = path if exclusive else path.with_name(path.name + "." + secrets.token_hex(6) + ".tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        if not exclusive:
            temporary.replace(path)
    finally:
        if not exclusive:
            temporary.unlink(missing_ok=True)


@contextmanager
def control_lock(directory: Path):
    fd = os.open(directory / "control.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def init(directory: str | Path | None, vault: str | Path, vault_name: str,
         scope: str, files: list[str]) -> dict:
    root = Path(vault).expanduser().resolve(strict=True)
    if not root.is_dir() or not vault_name.strip() or len(vault_name) > 200:
        raise RuntimeErrorSafe("Provide an existing vault directory and a short vault name.")
    if scope not in {"files", "vault_markdown"}:
        raise RuntimeErrorSafe("Scope must be files or vault_markdown.")
    if scope == "files":
        if not 1 <= len(files) <= 128:
            raise RuntimeErrorSafe("Files scope requires 1 to 128 explicit --file paths.")
        for name in files:
            if (PurePosixPath(name).is_absolute() or "\\" in name or "\x00" in name
                    or any(not part or part.startswith(".") for part in name.split("/"))
                    or not name.endswith(".md")):
                raise RuntimeErrorSafe("Each --file must be a visible, relative Markdown path.")
    elif files:
        raise RuntimeErrorSafe("Do not combine whole-vault scope with --file.")
    directory = state_path(directory, create=True, vault=root)
    config = {"root": str(root), "vault_name": vault_name,
              "scope": "explicit_files" if scope == "files" else scope}
    if scope == "files":
        config["files"] = list(dict.fromkeys(files))
    try:
        write_json(directory / "config.json", config, exclusive=True)
    except FileExistsError:
        raise RuntimeErrorSafe("Configuration already exists; init never overwrites it.") from None
    return {"ok": True, "initialized": True, "started": False, "state_dir": str(directory),
            "scope": scope, "read_mode": "locked", "auto_start": False}


def config(directory: Path) -> dict:
    data = read_json(directory / "config.json")
    try:
        root = Path(data["root"]).resolve(strict=True)
        if not root.is_dir():
            raise ValueError
        _outside_private_source(directory, root)
        # Constructing a locked reader validates configuration without reading note bodies.
        from .retrieval import VaultReader
        with_reader = VaultReader(directory / "config.json")
        with_reader.close()
    except RuntimeErrorSafe:
        raise
    except (ValueError, TypeError, KeyError, OSError):
        raise RuntimeErrorSafe("Invalid vault configuration; inspect its paths and scope locally.") from None
    return data


def inspect(directory: Path) -> dict:
    data = config(directory)
    return {"ok": True, "state_dir": str(directory), "vault": data["root"],
            "vault_name": data["vault_name"], "scope": data.get("scope", "explicit_files"),
            "files": data.get("files"), "read_only": True, "auto_start": False,
            "notes_read": False}


def _key(path: Path, vault: Path) -> str:
    _outside_private_source(path.resolve(), vault)
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, "r", encoding="utf-8") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
                raise RuntimeErrorSafe("Credential file must be owned by you with chmod 600 permissions.")
            value = stream.read(8193).strip()
        if value.startswith("OPENAI_API_KEY="):
            value = value.partition("=")[2].strip().strip("\"'")
        if len(value) > 8192 or not re.fullmatch(r"sk-[A-Za-z0-9_-]{16,}", value):
            raise RuntimeErrorSafe("Credential file must contain one API key; its value is withheld.")
        return value
    except (OSError, UnicodeError):
        raise RuntimeErrorSafe("Could not read the owner-only credential file safely.") from None


def _python_paths(binary: str) -> set[str]:
    path = Path(binary)
    resolved = path.resolve()
    result = {str(path), str(resolved)}
    framework_roots = {resolved.parents[1]}
    # A copied venv executable does not resolve back to its base interpreter.
    # pyvenv.cfg identifies the base bin directory for both copies and symlinks.
    # This is interpreter metadata, never a shell file to source or execute.
    configuration = path.parent.parent / "pyvenv.cfg"
    try:
        raw = configuration.read_text(encoding="utf-8")
        if len(raw) < 16384:
            for line in raw.splitlines():
                key, separator, value = line.partition("=")
                if separator and key.strip() == "home":
                    home = Path(value.strip())
                    if home.is_absolute():
                        framework_roots.add(home.resolve().parent)
    except (OSError, UnicodeError):
        pass
    if resolved == Path(sys.executable).resolve():
        base = Path(getattr(sys, "_base_executable", sys.executable)).resolve()
        result.add(str(base))
        framework_roots.add(base.parents[1])
    # macOS venv Python can re-exec the framework application binary.
    for root in framework_roots:
        framework = root / "Resources/Python.app/Contents/MacOS/Python"
        if framework.is_file():
            result.add(str(framework.resolve()))
    return result


def fingerprint(pid: int, argv: list[str]) -> str | None:
    """Match full command AND process start time; handle framework Python and Homebrew wrappers."""
    if type(pid) is not int or pid <= 1 or not argv:
        return None
    result = subprocess.run(["/bin/ps", "-ww", "-p", str(pid), "-o", "lstart=", "-o", "command="],
                            capture_output=True, text=True)
    fields = result.stdout.strip().split(maxsplit=5)
    if result.returncode or len(fields) != 6:
        return None
    binary = Path(argv[0])
    allowed = {str(binary), str(binary.resolve())}
    if len(argv) > 2 and argv[1] == "-m" and argv[2].startswith("mio_memory."):
        allowed |= _python_paths(argv[0])
    elif len(argv) > 1 and argv[1] == "run":
        # Homebrew's bin/tunnel-client may exec the sibling libexec executable.
        allowed.add(str(binary.resolve().parents[1] / "libexec/tunnel-client"))
    expected = {" ".join([item, *argv[1:]]) for item in allowed}
    # Keep an allowed exec transition stable: macOS may replace venv Python with
    # framework Python immediately after Popen, preserving PID and start time.
    return " ".join(fields[:5]) + "\n" + " ".join(argv) if fields[5] in expected else None


def _verified(item: dict | None) -> bool:
    if not isinstance(item, dict) or not item.get("identity"):
        return False
    try:
        return fingerprint(item["pid"], item["argv"]) == item["identity"]
    except (KeyError, TypeError, ValueError):
        return False


def _listener(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.2):
            return True
    except (OSError, TypeError, ValueError):
        return False


def _tunnel_ready(directory: Path) -> bool:
    path = directory / "tunnel-health.url"
    if path.is_symlink():
        return False
    try:
        url = path.read_text().strip()
        parts = urlsplit(url)
        if parts.scheme != "http" or parts.hostname != "127.0.0.1" or not parts.port:
            return False
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(url.rstrip("/") + "/readyz", timeout=0.5) as response:
            return response.status == 200
    except (OSError, ValueError):
        return False


def status(directory: Path) -> dict:
    data = read_json(directory / "state.json", missing={})
    supervisor = _verified(data.get("supervisor"))
    server = _verified(data.get("server"))
    tunnel = _verified(data.get("tunnel"))
    port = data.get("port")
    listening = _listener(port) if port else False
    needs_tunnel = bool(data.get("tunnel_enabled"))
    ready = bool(tunnel and _tunnel_ready(directory)) if needs_tunnel else None
    mode = data.get("mode", "locked")
    if mode == "timed" and time.time() >= data.get("reads_expire_at", 0):
        mode = "locked"
    if server:
        process_state = "running" if supervisor else "orphaned"
    elif listening:
        process_state = "unmanaged"
    else:
        process_state = "starting" if supervisor else "stopped"
    return {"ok": True, "state_dir": str(directory), "running": supervisor,
            "server_tracked": server, "local_service": bool(server and listening),
            "tunnel_enabled": needs_tunnel, "tunnel_tracked": tunnel,
            "tunnel_ready": ready, "read_mode": mode if server else "unknown" if listening else "stopped",
            "process_state": process_state,
            "port": port, "auto_start": False,
            "degraded": bool((server or tunnel) and not supervisor
                             or listening and not server
                             or supervisor and (not server or not listening or needs_tunnel and not ready)),
            "unmanaged_listener": bool(listening and not server),
            "shutdown_incomplete": bool(data.get("shutdown_incomplete")),
            "reads_expire_at": data.get("reads_expire_at")}


def doctor(directory: Path) -> dict:
    try:
        sdk_version = importlib.metadata.version("mcp")
    except importlib.metadata.PackageNotFoundError:
        sdk_version = None
    checks = {"python_supported": sys.version_info >= (3, 10), "posix_platform": os.name == "posix",
              "mcp_installed": importlib.util.find_spec("mcp") is not None,
              "mcp_version_supported": sdk_version == "2.2.0",
              "initialized": (directory / "config.json").exists()}
    if checks["initialized"]:
        config(directory)
        checks["configuration_valid"] = True
    return {"ok": all(checks.values()), "checks": checks, "mcp_version": sdk_version, "status": status(directory),
            "notes_read": False, "credentials_printed": False}


def _environment() -> dict[str, str]:
    # Neither the server nor a launcher needs inherited API keys or proxy settings.
    allowed = {"PATH", "HOME", "LANG", "LC_ALL", "LC_CTYPE", "TMPDIR", "SSL_CERT_FILE", "SSL_CERT_DIR"}
    result = {key: value for key, value in os.environ.items() if key in allowed}
    result["PYTHONDONTWRITEBYTECODE"] = "1"
    return result


def _record(process: subprocess.Popen, argv: list[str], done: threading.Event) -> dict:
    for _ in range(100):
        identity = fingerprint(process.pid, argv)
        if identity:
            return {"pid": process.pid, "argv": argv, "identity": identity}
        if done.is_set() or process.poll() is not None:
            break
        done.wait(0.05)
    raise RuntimeErrorSafe("A child process failed identity verification during startup.")


def _stop_child(process: subprocess.Popen | None) -> bool:
    if process is None or process.poll() is not None:
        return True
    # Every child starts its own session. The Popen handle belongs to this supervisor.
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(process.pid, sig)
            process.wait(timeout=4)
            return True
        except ProcessLookupError:
            return process.poll() is not None
        except subprocess.TimeoutExpired:
            continue
    return process.poll() is not None


def serve(directory: Path, token: str) -> None:
    launch = read_json(directory / "launch.json")
    if launch.get("token") != token:
        raise RuntimeErrorSafe("Startup token changed; refusing to start.")
    config_data = config(directory)
    port = launch["port"]
    if _listener(port):
        raise RuntimeErrorSafe("The selected local port is already in use.")
    done = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: done.set())
    own_argv = [sys.executable, "-m", "mio_memory.cli", "_serve", "--state-dir", str(directory), "--token", token]
    own_identity = fingerprint(os.getpid(), own_argv)
    if not own_identity:
        raise RuntimeErrorSafe("Supervisor process identity could not be verified.")
    data = {"supervisor": {"pid": os.getpid(), "argv": own_argv, "identity": own_identity},
            "token": token, "port": port, "tunnel_enabled": bool(launch.get("tunnel_id")),
            "mode": "continuous" if launch["continuous_read"] else "timed" if launch["open_seconds"] else "locked",
            "started_at": time.time(),
            "reads_expire_at": time.time() + launch["open_seconds"] if launch["open_seconds"] else None}
    write_json(directory / "state.json", data)
    server = tunnel = None
    try:
        argv = [sys.executable, "-m", "mio_memory.server", "--config", str(directory / "config.json"),
                "--port", str(port)]
        argv += ["--continuous-read"] if launch["continuous_read"] else ["--open-seconds", str(launch["open_seconds"])]
        server = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL, env=_environment(), start_new_session=True)
        data["server"] = _record(server, argv, done)
        write_json(directory / "state.json", data)
        for _ in range(100):
            if done.is_set() or server.poll() is not None:
                raise RuntimeErrorSafe("Local MCP server exited before becoming ready.")
            if _listener(port):
                break
            done.wait(0.1)
        else:
            raise RuntimeErrorSafe("Local MCP startup timed out.")
        if launch.get("tunnel_id"):
            health = directory / "tunnel-health.url"
            health.unlink(missing_ok=True)
            env = _environment()
            env["CONTROL_PLANE_API_KEY"] = _key(Path(launch["key_file"]), Path(config_data["root"]))
            argv = [launch["tunnel_client"], "run", "--control-plane.api-key", "env:CONTROL_PLANE_API_KEY",
                    "--control-plane.base-url", "https://api.openai.com",
                    "--control-plane.tunnel-id", launch["tunnel_id"],
                    "--mcp.server-url", f"http://127.0.0.1:{port}/mcp", "--mcp.startup-wait-timeout", "10s",
                    "--health.listen-addr", "127.0.0.1:0", "--health.url-file", str(health),
                    "--log.format", "json", "--log.level", "warn",
                    "--log.http-raw-unsafe=false", "--harpoon.capture-payloads=false"]
            tunnel = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                      stderr=subprocess.DEVNULL, env=env, start_new_session=True)
            del env["CONTROL_PLANE_API_KEY"]
            data["tunnel"] = _record(tunnel, argv, done)
            write_json(directory / "state.json", data)
        while not done.wait(0.25):
            if server.poll() is not None or (tunnel is not None and tunnel.poll() is not None):
                raise RuntimeErrorSafe("A bridge process exited; check configuration and restart manually.")
    finally:
        children_stopped = True
        # Attempt both children even if one cannot be terminated. Keep their
        # recorded fingerprints when recovery is still needed.
        for child in (tunnel, server):
            try:
                children_stopped = _stop_child(child) and children_stopped
            except OSError:
                children_stopped = False
        latest = read_json(directory / "state.json", missing={})
        if latest.get("token") == token:
            if children_stopped and not _listener(port):
                (directory / "state.json").unlink(missing_ok=True)
                (directory / "tunnel-health.url").unlink(missing_ok=True)
            else:
                latest["shutdown_incomplete"] = True
                write_json(directory / "state.json", latest)
                raise RuntimeErrorSafe("Shutdown is incomplete; process state was preserved for recovery.")


def start(directory: Path, *, port: int = 8789, continuous_read: bool = False, open_seconds: int = 0,
          tunnel_id: str | None = None, tunnel_client: str | None = None, key_file: str | None = None) -> dict:
    data = config(directory)
    if not 0 <= port <= 65535 or not 0 <= open_seconds <= 600 or (continuous_read and open_seconds):
        raise RuntimeErrorSafe("Use a valid port and either continuous reads or a 0–600 second window.")
    if any((tunnel_id, tunnel_client, key_file)) and not all((tunnel_id, tunnel_client, key_file)):
        raise RuntimeErrorSafe("A private tunnel requires --tunnel-id, --tunnel-client, and --key-file together.")
    if tunnel_id:
        if not re.fullmatch(r"tunnel_[A-Za-z0-9_-]+", tunnel_id):
            raise RuntimeErrorSafe("Invalid tunnel ID.")
        binary = Path(tunnel_client).expanduser().absolute()
        if not binary.is_file() or not os.access(binary, os.X_OK):
            raise RuntimeErrorSafe("Provide the installed official tunnel-client executable path.")
        tunnel_client = str(binary)
        key_file = str(Path(key_file).expanduser().absolute())
        _key(Path(key_file), Path(data["root"]))
    with control_lock(directory):
        old = status(directory)
        if old["running"]:
            return dict(old, already_running=True, note="Stop before changing read mode, port, or tunnel options.")
        if old["server_tracked"] or old["tunnel_tracked"]:
            raise RuntimeErrorSafe("Recorded child processes remain; run stop before starting again.")
        with socket.socket() as probe:
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                raise RuntimeErrorSafe("The selected local port is in use. Choose another port or --port 0.") from None
            port = probe.getsockname()[1]
        token = secrets.token_hex(16)
        write_json(directory / "launch.json", {"token": token, "port": port,
                   "continuous_read": continuous_read, "open_seconds": open_seconds,
                   "tunnel_id": tunnel_id, "tunnel_client": tunnel_client, "key_file": key_file})
        error_file = directory / "startup-error.json"
        error_file.unlink(missing_ok=True)
        argv = [sys.executable, "-m", "mio_memory.cli", "_serve", "--state-dir", str(directory), "--token", token]
        supervisor = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                      stderr=subprocess.DEVNULL, env=_environment(), start_new_session=True)
        for _ in range(80):
            result = status(directory)
            if result["running"] and result["local_service"] and (not tunnel_id or result["tunnel_ready"]):
                return result
            if supervisor.poll() is not None:
                error = read_json(error_file, missing={})
                raise RuntimeErrorSafe(error.get("error", "Bridge startup failed; run doctor and inspect configuration."))
            time.sleep(0.15)
        return dict(status(directory), note="Startup is pending; use status to check or stop to cancel.")


def _stop_verified(item: dict, timeout: float = 5) -> None:
    for sig in (signal.SIGTERM, signal.SIGKILL):
        if not _verified(item):
            return
        try:
            os.killpg(item["pid"], sig)
        except ProcessLookupError:
            return
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not _verified(item):
                return
            time.sleep(0.1)
    if _verified(item):
        raise RuntimeErrorSafe("A verified process did not stop; shutdown is incomplete.")


def stop(directory: Path) -> dict:
    if not directory.exists():
        return {"ok": True, "stopped": True, "already_stopped": True}
    with control_lock(directory):
        data = read_json(directory / "state.json", missing={})
        port = data.get("port")
        errors = []
        try:
            _stop_verified(data.get("supervisor", {}), timeout=10)
        except RuntimeErrorSafe as exc:
            errors.append(str(exc))
        except OSError:
            errors.append("Supervisor signalling failed.")
        # Recover only exact recorded children after a supervisor crash; never kill by port/name.
        for role in ("tunnel", "server"):
            try:
                _stop_verified(data.get(role, {}))
            except RuntimeErrorSafe as exc:
                errors.append(str(exc))
            except OSError:
                errors.append("Child signalling failed.")
        remaining = status(directory)
        recorded_live = any(_verified(data.get(role)) for role in ("supervisor", "tunnel", "server"))
        if recorded_live or remaining["running"] or remaining["server_tracked"] or remaining["tunnel_tracked"]:
            if data:
                write_json(directory / "state.json", dict(data, shutdown_incomplete=True))
            raise RuntimeErrorSafe("Verified bridge processes remain; shutdown is incomplete.")
        # The supervisor may have removed state in its finally block. The port
        # remembered before signalling remains necessary to verify shutdown.
        listening = bool(port and _listener(port))
        if listening:
            if data:
                write_json(directory / "state.json", dict(data, shutdown_incomplete=True))
            return {"ok": False, "stopped": False, "port": port, "unmanaged_listener": True,
                    "note": "The recorded port still has an unverified listener. No unrelated process was signalled; state was preserved."}
        if errors:
            if data:
                write_json(directory / "state.json", dict(data, shutdown_incomplete=True))
            raise RuntimeErrorSafe("Shutdown could not be fully verified; state was preserved for recovery.")
        (directory / "state.json").unlink(missing_ok=True)
        (directory / "tunnel-health.url").unlink(missing_ok=True)
        return {"ok": True, "stopped": True, "unmanaged_listener": False,
                "note": "No unrelated process was signalled."}
