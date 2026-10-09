"""Check the actual CLI and Tornado timeout without starting a server or OCR."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest


HAS_APP_DEPS = importlib.util.find_spec("streamlit") is not None and importlib.util.find_spec("tornado") is not None
ROOT = Path(__file__).resolve().parents[1]


def run_probe(code, *args):
    # A fresh process isolates Streamlit's global config from other AppTest cases.
    result = subprocess.run(
        [sys.executable, "-c", code, *args], cwd=ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace", timeout=30,
    )
    if result.returncode != 0:
        raise AssertionError(f"Offline runtime probe failed: {result.stderr}")
    return json.loads(result.stdout)


@unittest.skipUnless(HAS_APP_DEPS, "Install the project's pinned dependencies for runtime compatibility tests")
class RuntimeCompatibilityTests(unittest.TestCase):
    def test_docker_cli_retains_30_second_timeout_and_protection(self):
        command_line = next(line for line in (ROOT / "Dockerfile").read_text().splitlines() if line.startswith("CMD "))
        command = json.loads(command_line[4:])
        self.assertEqual(command[:3], ["python", "-m", "streamlit"])
        observed = run_probe("""
import json
import sys
from types import SimpleNamespace
from unittest.mock import patch
from click.testing import CliRunner
from streamlit import config
from streamlit.web import cli
from streamlit.web.server.server import get_tornado_settings
from tornado.websocket import WebSocketProtocol13, _WebSocketParams

observed = {}
def stopped_before_server(file, is_hello, args, flag_options):
    settings = get_tornado_settings()
    protocol = WebSocketProtocol13(SimpleNamespace(), False, _WebSocketParams(
        ping_interval=settings['websocket_ping_interval'],
        ping_timeout=settings['websocket_ping_timeout'],
    ))
    observed.update(
        interval=settings['websocket_ping_interval'],
        requested_timeout=settings['websocket_ping_timeout'],
        effective_timeout=protocol.ping_timeout,
        cli_ping_option=flag_options['server_websocketPingInterval'],
        cors=config.get_option('server.enableCORS'),
        xsrf=config.get_option('server.enableXsrfProtection'),
    )

with patch.object(config, 'get_config_files', return_value=[]), patch.object(cli, 'check_credentials'), patch.object(cli.bootstrap, 'run', side_effect=stopped_before_server) as run:
    result = CliRunner().invoke(cli.main, json.loads(sys.argv[1]))
    if result.exit_code != 0:
        raise AssertionError(result.output) from result.exception
    assert run.call_count == 1
print(json.dumps(observed))
""", json.dumps(command[3:]))
        self.assertEqual(observed["cli_ping_option"], 30)
        self.assertEqual(observed["interval"], 30)
        self.assertEqual(observed["requested_timeout"], 30)
        self.assertEqual(observed["effective_timeout"], 30)
        self.assertTrue(observed["cors"])
        self.assertTrue(observed["xsrf"])

    def test_current_default_avoids_legacy_one_second_clamp(self):
        observed = run_probe("""
import json
from types import SimpleNamespace
from unittest.mock import patch
from packaging.version import Version
import tornado
from tornado.websocket import WebSocketProtocol13, _WebSocketParams
from streamlit import config
from streamlit.web.server.server import get_tornado_settings

assert Version(tornado.version) >= Version('6.5.0'), 'Test needs the modern Tornado behavior that exposed the old mismatch'
with patch.object(config, 'get_config_files', return_value=[]):
    config.set_option('server.websocketPingInterval', None)
settings = get_tornado_settings()
current = WebSocketProtocol13(SimpleNamespace(), False, _WebSocketParams(
    ping_interval=settings['websocket_ping_interval'],
    ping_timeout=settings['websocket_ping_timeout'],
))
legacy = WebSocketProtocol13(SimpleNamespace(), False, _WebSocketParams(ping_interval=1, ping_timeout=30))
with patch('tornado.websocket.de_dupe_gen_log'):
    legacy_timeout = legacy.ping_timeout
print(json.dumps(dict(interval=settings['websocket_ping_interval'], requested_timeout=settings['websocket_ping_timeout'], effective_timeout=current.ping_timeout, legacy_effective_timeout=legacy_timeout)))
""")
        self.assertEqual(observed["interval"], 30)
        self.assertEqual(observed["requested_timeout"], 30)
        self.assertEqual(observed["effective_timeout"], 30)
        self.assertEqual(observed["legacy_effective_timeout"], 1)


if __name__ == "__main__":
    unittest.main()
