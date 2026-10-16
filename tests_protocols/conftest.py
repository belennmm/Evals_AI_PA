"""MCP en un proceso real; readiness TCP/HTTP y cierre explícito del proceso.

En Windows restringido que bloquee socketpair/asyncio, ejecutar la prueba con
permisos de red local. No modifica las dependencias de embeddings.
"""
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

import pytest


ROOT = Path(__file__).resolve().parents[1]


def tcp_ready(port: int) -> bool:
    with socket.socket() as probe:
        probe.settimeout(0.2)
        return probe.connect_ex(("127.0.0.1", port)) == 0


def endpoint_ready(url: str) -> bool:
    # GET sin Accept SSE recibe 406 JSON-RPC. La inicialización real se prueba
    # después por POST; esta comprobación solo verifica que /mcp responde.
    opener = build_opener(ProxyHandler({}))
    try:
        with opener.open(Request(url, headers={"Accept": "application/json"}), timeout=1):
            return False
    except HTTPError as error:
        with error:
            body = error.read()
            if error.code != 406:
                return False
            try:
                payload = json.loads(body)
            except (ValueError, UnicodeError):
                return False
            return payload.get("jsonrpc") == "2.0" and payload.get("error", {}).get("code") == -32600
    except (URLError, TimeoutError, ConnectionError):
        return False


@pytest.fixture
def mcp_url(tmp_path):
    # Elegir un puerto libre sin dejarlo escuchando antes de Uvicorn.
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    url = f"http://127.0.0.1:{port}/mcp"
    log_path = tmp_path / "mcp-server.log"
    environment = {
        **os.environ,
        "MCP_HOST": "127.0.0.1", "MCP_PORT": str(port),
        "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1",
    }
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
    with log_path.open("w", encoding="utf-8") as output:
        started = time.perf_counter()
        process = subprocess.Popen(
            [sys.executable, "-B", "-u", "-m", "protocols.mcp_server"],
            cwd=ROOT, env=environment, creationflags=flags,
            stdout=output, stderr=subprocess.STDOUT,
        )
        forced_stop = False
        try:
            # Incluye importaciones: no confundir lentitud con fallo a 30s.
            deadline = time.monotonic() + 600
            tcp_seconds = None
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    pytest.fail(f"MCP terminó antes de readiness (code={process.returncode}).\n"
                                + log_path.read_text(encoding="utf-8"))
                if tcp_ready(port):
                    if tcp_seconds is None:
                        tcp_seconds = time.perf_counter() - started
                    if endpoint_ready(url):
                        break
                time.sleep(0.2)
            else:
                pytest.fail("MCP no alcanzó readiness TCP/HTTP en 600s.\n"
                            + log_path.read_text(encoding="utf-8"))
            print(f"\nMCP subprocess pid={process.pid}; TCP={tcp_seconds:.3f}s; "
                  f"HTTP={time.perf_counter() - started:.3f}s; endpoint={url}")
            yield url
        finally:
            if process.poll() is None:
                try:
                    # El grupo incluye el launcher del venv y Python en Windows.
                    stop_signal = signal.CTRL_BREAK_EVENT if sys.platform == "win32" else signal.SIGINT
                    process.send_signal(stop_signal)
                    process.wait(timeout=60)
                except (OSError, subprocess.TimeoutExpired):
                    forced_stop = True
                    if sys.platform == "win32":
                        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                                       capture_output=True, check=False)
                    else:
                        process.kill()
                    process.wait(timeout=30)
            logs = log_path.read_text(encoding="utf-8")
            assert not forced_stop, "MCP necesitó cierre forzado.\n" + logs
            # CTRL_BREAK puede devolver 3 aun con cierre ordenado ASGI.
            expected_codes = (0, 3) if sys.platform == "win32" else (0, -signal.SIGINT, 130)
            assert process.returncode in expected_codes, logs
            assert "Application shutdown complete." in logs, logs
            assert "Finished server process" in logs, logs
            assert not tcp_ready(port), "El puerto MCP sigue ocupado tras el cierre"
            assert "Herramienta solicitada" not in logs, "El catálogo no debe ejecutar herramientas"
            print(f"MCP cerrado: code={process.returncode}; lifespan cerrado; puerto liberado")
