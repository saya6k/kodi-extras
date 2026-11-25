"""The add-on's REST client against a running otbr-agent (see run.sh)."""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "addons", "script.service.threadbridge"))

import common  # noqa: E402

rest = common.Rest(port=8081)


def wait(predicate, seconds=60):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            if predicate():
                return True
        except common.RestError:
            pass
        time.sleep(1)
    return False


class LiveTest(unittest.TestCase):
    def test_network_lifecycle(self):
        self.assertTrue(wait(lambda: rest.state() is not None), "the REST API did not come up")
        self.assertIsNone(rest.active_dataset())

        common.replace_network(rest, common.form_dataset("tb-test", "15"))
        self.assertTrue(wait(lambda: rest.state() == "leader"), rest.state())
        status = dict(common.status_lines(rest.node(), rest.active_dataset(), rest.coprocessor_version()))
        print(status)
        self.assertEqual(status["network_name"], "tb-test")
        self.assertEqual(status["channel"], "15")
        self.assertIn("coprocessor", status)

        tlvs = rest.active_dataset_tlvs()
        self.assertEqual(common.normalize_dataset(tlvs), tlvs.upper())
        ext_pan_id = rest.node()["extPanId"]

        # Replacing a dataset that already exists, with what was exported,
        # pasted the way ot-ctl prints it.
        common.replace_network(rest, common.normalize_dataset("dataset " + tlvs.lower()))
        self.assertTrue(wait(lambda: rest.state() == "leader"), rest.state())
        self.assertEqual(rest.node()["extPanId"], ext_pan_id)

        rest.set_commissioner(True)
        self.assertTrue(wait(lambda: rest.commissioner_state() == "active", 30), rest.commissioner_state())
        rest.add_joiner("J01NME", None, 120)
        joiners = rest.json("GET", "/node/commissioner/joiner")
        print(joiners)
        self.assertTrue(any(j.get("pskd") == "J01NME" for j in joiners))

        with self.assertRaises(common.RestError) as raised:
            rest.set_active_dataset("0E08")
        self.assertIsNotNone(raised.exception.status)


if __name__ == "__main__":
    unittest.main()
