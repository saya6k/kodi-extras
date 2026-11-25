"""Tests of threadbridge's Kodi-free logic. Run: python3 -m unittest discover -s tests"""

import json
import os
import socket
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "addons", "script.service.threadbridge"))

import common  # noqa: E402


class ConfigTest(unittest.TestCase):
    def test_defaults_match_the_package(self):
        self.assertEqual(common.values({}), {
            "RADIO_DEVICE": "", "RADIO_BAUDRATE": "460800", "RADIO_FLOW_CONTROL": "1", "BACKBONE_IF": "eth0",
            "REST_ADDRESS": "127.0.0.1", "REST_PORT": "8081", "NAT64": "1", "FIREWALL": "1",
        })

    def test_settings_become_the_environment(self):
        config = common.values({
            "device": " /dev/serial/by-id/usb-Nordic_nRF52840-if00 ", "baudrate": "115200",
            "flow_control": "false", "backbone": "wlan0", "rest_public": "true", "rest_port": "8082",
            "nat64": "false", "firewall": "false",
        })
        self.assertEqual(config["RADIO_DEVICE"], "/dev/serial/by-id/usb-Nordic_nRF52840-if00")
        self.assertEqual(config["RADIO_BAUDRATE"], "115200")
        self.assertEqual(config["RADIO_FLOW_CONTROL"], "0")
        self.assertEqual(config["BACKBONE_IF"], "wlan0")
        self.assertEqual(config["REST_ADDRESS"], "0.0.0.0")
        self.assertEqual(config["REST_PORT"], "8082")
        self.assertEqual(config["NAT64"], "0")
        self.assertEqual(config["FIREWALL"], "0")

    def test_unknown_baudrate_falls_back(self):
        self.assertEqual(common.values({"baudrate": "9600"})["RADIO_BAUDRATE"], "460800")

    def test_config_text_quotes_for_systemd(self):
        self.assertEqual(common.config_text({"A": 'x"y', "B": "1"}), 'A="x\\"y"\nB="1"\n')


class DiscoveryTest(unittest.TestCase):
    def test_serial_devices_sorted_with_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            for name in ["usb-b", "usb-a"]:
                open(os.path.join(directory, name), "w").close()
            self.assertEqual(common.serial_devices(directory),
                             [os.path.join(directory, "usb-a"), os.path.join(directory, "usb-b")])

    def test_missing_directory_means_none(self):
        self.assertEqual(common.serial_devices("/nonexistent/by-id"), [])
        self.assertEqual(common.network_interfaces("/nonexistent/net"), [])

    def test_interfaces_leave_out_loopback_and_thread(self):
        with tempfile.TemporaryDirectory() as directory:
            for name in ["lo", "wpan0", "wlan0", "eth0"]:
                os.mkdir(os.path.join(directory, name))
            self.assertEqual(common.network_interfaces(directory), ["eth0", "wlan0"])


class InputTest(unittest.TestCase):
    DATASET = "0E080000000000010000000300000F35060004001FFFE0"

    def test_dataset_whitespace_and_case(self):
        self.assertEqual(common.normalize_dataset(" 0e08000000\n0000010000 \n"), "0E080000000000010000")

    def test_dataset_with_ot_ctl_prefix(self):
        self.assertEqual(common.normalize_dataset("dataset " + self.DATASET), self.DATASET)

    def test_not_a_dataset(self):
        for raw in ["", "   ", "0E0", "XYZ123", "0E08 00G0"]:
            self.assertIsNone(common.normalize_dataset(raw), raw)

    def test_pskd(self):
        self.assertTrue(common.valid_pskd("J01NME"))
        self.assertTrue(common.valid_pskd("ABCDEFGH12345678ABCDEFGH12345678"))
        for pskd in ["J01NM", "j01nme", "J01NMEI", "QQQQQQ", "ZZZZZZ", "OOOOOO", "A" * 33]:
            self.assertFalse(common.valid_pskd(pskd), pskd)

    def test_eui64(self):
        self.assertTrue(common.valid_eui64("0123456789abcdef"))
        self.assertFalse(common.valid_eui64("0123456789abcde"))
        self.assertFalse(common.valid_eui64("0123456789abcdeg"))

    def test_network_name_counts_bytes(self):
        self.assertTrue(common.valid_network_name("threadbridge-01"))
        self.assertFalse(common.valid_network_name(""))
        # Six Hangul syllables are 18 bytes in UTF-8.
        self.assertFalse(common.valid_network_name("스레드브리지"))

    def test_form_dataset(self):
        self.assertEqual(common.form_dataset("home"), {"networkName": "home"})
        self.assertEqual(common.form_dataset("home", "15"), {"networkName": "home", "channel": 15})


class StatusTest(unittest.TestCase):
    def test_lines_skip_what_is_unknown(self):
        node = {"state": "leader", "networkName": "home", "extPanId": "DEAD00BEEF00CAFE", "routerCount": 1,
                "rloc16": "0x6c00", "baState": "Active"}
        dataset = {"channel": 15, "panId": 4660}
        lines = dict(common.status_lines(node, dataset, None))
        self.assertEqual(lines["state"], "leader")
        self.assertEqual(lines["pan_id"], "0x1234")
        self.assertEqual(lines["channel"], "15")
        self.assertNotIn("coprocessor", lines)

    def test_no_network(self):
        self.assertEqual(common.status_lines({"state": "disabled"}, None, "OPENTHREAD/1.4"),
                         [("state", "disabled"), ("coprocessor", "OPENTHREAD/1.4")])


class FakeAgent(BaseHTTPRequestHandler):
    """Records requests and answers with what the test put in `answers`."""

    requests = []
    answers = {}

    def handle_one(self, method):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length).decode("utf-8") if length else None
        FakeAgent.requests.append((method, self.path, self.headers.get("Content-Type"),
                                   self.headers.get("Accept"), body))
        status, content_type, text = FakeAgent.answers.get((method, self.path), (200, "application/json", ""))
        data = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self.handle_one("GET")

    def do_PUT(self):
        self.handle_one("PUT")

    def do_POST(self):
        self.handle_one("POST")

    def log_message(self, *args):
        pass


class RestTest(unittest.TestCase):
    def setUp(self):
        FakeAgent.requests = []
        FakeAgent.answers = {}
        self.server = HTTPServer(("127.0.0.1", 0), FakeAgent)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.rest = common.Rest(port=self.server.server_address[1], timeout=5)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def test_state_and_node(self):
        FakeAgent.answers[("GET", "/node/state")] = (200, "application/json", '"leader"')
        FakeAgent.answers[("GET", "/node")] = (200, "application/json", '{"state": "leader"}')
        self.assertEqual(self.rest.state(), "leader")
        self.assertEqual(self.rest.node(), {"state": "leader"})

    def test_no_active_dataset(self):
        FakeAgent.answers[("GET", "/node/dataset/active")] = (204, "application/json", "")
        self.assertIsNone(self.rest.active_dataset())
        self.assertIsNone(self.rest.active_dataset_tlvs())

    def test_dataset_tlvs_asks_for_text(self):
        FakeAgent.answers[("GET", "/node/dataset/active")] = (200, "text/plain", "0E08ABCD\n")
        self.assertEqual(self.rest.active_dataset_tlvs(), "0E08ABCD")
        self.assertEqual(FakeAgent.requests[-1][3], "text/plain")

    def test_replace_network_disables_writes_enables(self):
        common.replace_network(self.rest, "0E08ABCD")
        self.assertEqual([(m, p, t, b) for m, p, t, _, b in FakeAgent.requests], [
            ("PUT", "/node/state", "application/json", '"disable"'),
            ("PUT", "/node/dataset/active", "text/plain", "0E08ABCD"),
            ("PUT", "/node/state", "application/json", '"enable"'),
        ])

    def test_form_sends_json_dataset(self):
        self.rest.set_active_dataset(common.form_dataset("home", "15"))
        _, _, content_type, _, body = FakeAgent.requests[-1]
        self.assertEqual(content_type, "application/json")
        self.assertEqual(json.loads(body), {"networkName": "home", "channel": 15})

    def test_joiner_body(self):
        self.rest.add_joiner("J01NME", None, 120)
        self.rest.add_joiner("J01NME", "0123456789ABCDEF", 60)
        bodies = [json.loads(r[4]) for r in FakeAgent.requests]
        self.assertEqual(bodies, [{"pskd": "J01NME", "timeout": 120, "joinerId": "*"},
                                  {"pskd": "J01NME", "timeout": 60, "joinerId": "0123456789abcdef"}])

    def test_error_carries_status_and_message(self):
        FakeAgent.answers[("PUT", "/node/dataset/active")] = (
            409, "application/json", '{"title": "Conflict", "status": 409, "detail": "Thread is active"}')
        with self.assertRaises(common.RestError) as raised:
            self.rest.set_active_dataset("0E08")
        self.assertEqual(raised.exception.status, 409)
        self.assertEqual(str(raised.exception), "Thread is active")

    def test_error_without_detail_uses_title(self):
        FakeAgent.answers[("PUT", "/node/dataset/active")] = (
            400, "application/json", '{"title": "Bad Request", "status": 400}')
        with self.assertRaises(common.RestError) as raised:
            self.rest.set_active_dataset("0E08")
        self.assertEqual(str(raised.exception), "Bad Request")

    def test_not_running(self):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        with self.assertRaises(common.RestError) as raised:
            common.Rest(port=port, timeout=2).state()
        self.assertIsNone(raised.exception.status)


if __name__ == "__main__":
    unittest.main()
