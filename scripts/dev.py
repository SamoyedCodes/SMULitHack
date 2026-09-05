"""Run the local API and UI with one validated configuration and clean shutdown."""
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.config import Config


def main():
    try:
        config = Config()
    except ValueError as exc:
        raise SystemExit(str(exc))
    pnpm = shutil.which("pnpm")
    if not pnpm:
        raise SystemExit("pnpm is missing from PATH. Install the version in frontend/package.json.")
    for port in (config.api_port, config.web_port):
        with socket.socket() as probe:
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                raise SystemExit(f"Port {port} is unavailable. Stop its owner or change the configured port.") from None
    env = {**os.environ, "AITHENA_API_PORT": str(config.api_port), "AITHENA_WEB_PORT": str(config.web_port)}
    # Never forward provider credentials to the frontend child process.
    web_env = {key: value for key, value in env.items() if key not in {"GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENROUTER_API_KEY"}}
    children = []
    def stop(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop)
    try:
        children.append(subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.api:app", "--host", "127.0.0.1", "--port", str(config.api_port)], cwd=ROOT, env=env, start_new_session=True))
        children.append(subprocess.Popen([pnpm, "run", "dev"], cwd=ROOT / "frontend", env=web_env, start_new_session=True))
        print(f"AITHENA UI http://127.0.0.1:{config.web_port}\nAPI http://127.0.0.1:{config.api_port}\nCtrl+C stops both services.", flush=True)
        while all(child.poll() is None for child in children):
            time.sleep(.2)
        raise SystemExit("An application process exited. Both services have been stopped.")
    except KeyboardInterrupt:
        pass
    finally:
        for child in children:
            try:
                os.killpg(child.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        for child in children:
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()


if __name__ == "__main__":
    main()
