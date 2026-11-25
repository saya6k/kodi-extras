"""Tests of atmos67's Kodi-free logic. Run: python3 -m unittest discover -s tests"""

import importlib.util
import os
import socket
import tempfile
import threading
import unittest

# Loaded under its own name: other add-ons' tests import a `common` too.
_path = os.path.join(os.path.dirname(__file__), "..", "addons", "service.atmos67", "common.py")
_spec = importlib.util.spec_from_file_location("atmos67_common", _path)
common = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(common)

SETTINGS = {
    "layout": "7.1.4", "interface": "eth0", "address": "239.69.67.1",
    "ptp_domain": "0", "buffer_ms": "100", "mode": "1", "subs": "2", "slope": "24",
    "xo_front": "80", "xo_center": "90", "xo_surround": "0", "xo_back": "80", "xo_top": "100",
}
LEVELS = {"L": {"trim": -1.5, "distance": 3.0}, "R": {"trim": 0.0, "distance": 3.343}, "SW1": {"trim": 2.0}}


class ConfigTest(unittest.TestCase):
    def test_manual_mode_carries_crossovers_trims_and_delays(self):
        values = common.values(SETTINGS, LEVELS, "/p", -20.0)
        self.assertEqual(values["MODE"], "manual")
        self.assertEqual(values["CROSSOVER"], "front=80 center=90 back=80 top=100")
        self.assertEqual(values["TRIMS"], "L=-1.5 SW1=2.0")
        # R is 34.3 cm farther, so L waits 1 ms for it.
        self.assertEqual(values["DELAYS"], "L=1.0")
        self.assertEqual(values["AUTO_DESIGN"], "/p/designs/current")
        text = common.config_text(values)
        self.assertIn('MODE="manual"\n', text)
        self.assertIn('VOLUME_DB="-20.0"\n', text)

    def test_volume_changes_alone(self):
        text = common.config_text(common.values(SETTINGS, LEVELS, "/p", -20.0))
        changed = common.replace_volume(text, -35.5)
        self.assertEqual(changed, common.config_text(common.values(SETTINGS, LEVELS, "/p", -35.5)))

    def test_measured_correction_keeps_trims_but_not_distances(self):
        values = common.values(dict(SETTINGS, mode="2"), LEVELS, "/p", 0)
        self.assertEqual((values["MODE"], values["TRIMS"], values["DELAYS"]), ("auto", "L=-1.5 SW1=2.0", ""))

    def test_measuring_runs_without_processing(self):
        values = common.values(SETTINGS, LEVELS, "/p", 0, mode="measure")
        self.assertEqual((values["CROSSOVER"], values["TRIMS"], values["DELAYS"]), ("", "", ""))
        self.assertEqual(values["SUBS"], "2")

    def test_quotes_survive_the_environment_file(self):
        self.assertEqual(common.quote('a "b" \\c'), '"a \\"b\\" \\\\c"')


class VolumeTest(unittest.TestCase):
    def test_maps_kodi_percent_onto_60_db_below_the_maximum(self):
        self.assertEqual(common.volume_db(100, False, -3.0), -3.0)
        self.assertEqual(common.volume_db(50, False, 0.0), -30.0)
        self.assertEqual(common.volume_db(0, False, 0.0), common.MUTED_DB)
        self.assertEqual(common.volume_db(80, True, 0.0), common.MUTED_DB)


class SyncTest(unittest.TestCase):
    def test_holds_the_picture_back_by_the_whole_audio_path(self):
        # Sender 71.3 ms, decoder allowance 40 ms, receiver 5 ms, trim -6.3 ms.
        self.assertEqual(common.av_offset(71.3, 5.0, -6.3), -0.11)

    def test_reads_the_status_answer(self):
        status = common.answer_json('ok {"grandmaster": "00-11", "streams": [], "playing": true}')
        self.assertTrue(status["playing"])
        with self.assertRaises(ValueError):
            common.answer_json("error: unknown command")

    def test_reads_sender_answers(self):
        self.assertEqual(common.answer_value("ok 71.3"), 71.3)
        for answer in ["ok", "error: unknown command", ""]:
            with self.assertRaises(ValueError):
                common.answer_value(answer)


class SocketTest(unittest.TestCase):
    def test_sends_a_line_and_reads_the_answer(self):
        path = os.path.join(tempfile.mkdtemp(), "control")
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(path)
        server.listen(1)
        received = []

        def answer():
            connection, _ = server.accept()
            received.append(connection.recv(64))
            connection.sendall(b"ok\n")
            connection.close()

        thread = threading.Thread(target=answer)
        thread.start()
        self.assertEqual(common.command("volume -12.5", path), "ok")
        thread.join()
        server.close()
        self.assertEqual(received, [b"volume -12.5\n"])

    def test_reads_calibration_progress(self):
        self.assertEqual(common.progress('{"step": "measuring", "detail": "position 2"}\n'), ("measuring", "position 2"))
        self.assertIsNone(common.progress("atmos67: something on stderr"))


class StreamsTest(unittest.TestCase):
    OUTPUTS = ["L", "R", "C", "Ls", "Rs", "Lb", "Rb", "Tfl", "Tfr", "Tbl", "Tbr", "SW1"]

    def test_defaults_to_8_channels_a_stream(self):
        streams = common.default_streams(self.OUTPUTS, "239.69.67.255")
        self.assertEqual([s["name"] for s in streams], ["atmos67 ch 1-8", "atmos67 ch 9-12"])
        self.assertEqual(streams[1]["address"], "239.69.68.0")
        self.assertEqual(streams[1]["channels"], ["Tfr", "Tbl", "Tbr", "SW1"])

    def test_finds_what_the_sender_would_refuse(self):
        self.assertIsNone(common.stream_problem({"address": "239.1.2.3", "channels": ["L"] * 8}))
        self.assertEqual(common.stream_problem({"address": "239.1.2.3", "channels": ["L"] * 9}), "channels")
        self.assertEqual(common.stream_problem({"address": "10.0.0.1", "channels": []}), "address")
        self.assertEqual(common.stream_problem({"address": "239.1.x.3", "channels": []}), "address")

    def test_plan_reaches_the_service_only_when_there_is_one(self):
        profile = tempfile.mkdtemp()
        self.assertEqual(common.values(SETTINGS, {}, profile, 0)["STREAMS"], "")
        plan = [{"name": "front", "address": "239.1.1.1", "channels": ["L", "R", "C", "SW1"]}]
        common.write_streams(profile, plan)
        self.assertEqual(common.read_streams(profile), plan)
        self.assertEqual(common.values(SETTINGS, {}, profile, 0)["STREAMS"], common.streams_path(profile))
        self.assertEqual(common.unassigned(self.OUTPUTS, plan)[:2], ["Ls", "Rs"])
        common.write_streams(profile, [])
        self.assertEqual(common.read_streams(profile), [])


class LevelsTest(unittest.TestCase):
    def test_round_trips(self):
        profile = tempfile.mkdtemp()
        self.assertEqual(common.read_levels(profile), {})
        common.write_levels(profile, LEVELS)
        self.assertEqual(common.read_levels(profile), LEVELS)


if __name__ == "__main__":
    unittest.main()
