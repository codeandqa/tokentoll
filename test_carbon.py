import argparse
import http.client
import json
import os
import socket
import subprocess
import sys
import tempfile
import unittest
from datetime import date, datetime, timezone

import carbon

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "carbon.py")


def line(mid, model, out, ts="2026-10-20T12:00:00Z"):
    return json.dumps({"type": "assistant", "timestamp": ts, "requestId": "r" + mid, "cwd": "/x/proj",
                       "message": {"id": mid, "model": model, "usage": {"output_tokens": out, "input_tokens": 0}}}) + "\n"


class CarbonTest(unittest.TestCase):
    def test_dedupes_and_scales_by_model(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, "p", "sub"))
            with open(os.path.join(root, "p", "a.jsonl"), "w") as f:
                f.write(line("m1", "claude-sonnet-5-5", 1000) * 3)  # same response logged 3 times
                f.write(line("m2", "claude-haiku-5-5", 1000))
                f.write(line("m3", "claude-sonnet-5-5", 1000, ts="2026-01-01T00:00:00Z"))  # before window
                f.write(json.dumps({"type": "custom-title", "customTitle": "<b>Carbon</b>", "sessionId": "a"}) + "\n")
                f.write(json.dumps({"type": "ai-title", "aiTitle": "AI name", "sessionId": "a"}) + "\n")  # loses to the rename
            with open(os.path.join(root, "p", "sub", "b.jsonl"), "w") as f:
                f.write(line("m1", "claude-sonnet-5-5", 1000))  # copied into a subagent/resumed log
            state = {}
            rows = carbon.load(root, date(2026, 10, 1), state)
            total, by = carbon.summarize(rows)
        self.assertEqual(len(rows), 2)
        self.assertEqual(list(by["session"]), ["a"])
        self.assertEqual(carbon.session_title(state, "a"), "<b>Carbon</b>")
        page = carbon.render_body(total, by, date(2026, 10, 1), date(2026, 10, 27), 400, 1.0, state, {"a"})
        self.assertIn("&lt;b&gt;Carbon&lt;/b&gt; <span class=live>● live</span><div class=sub>proj · a</div>", page)
        sonnet = 0.6 * carbon.PUE
        self.assertAlmostEqual(total[1], sonnet * (1 + 0.33))
        self.assertEqual(list(by["project"]), ["proj"])
        self.assertLess(total[0], total[1])
        self.assertLess(total[1], total[2])

    def test_incremental_reads_only_new_complete_lines(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "a.jsonl")
            with open(path, "w") as f:
                f.write(line("m1", "sonnet", 1000))
            state = {}
            self.assertEqual(len(carbon.load(root, date(2026, 10, 1), state)), 1)
            half = line("m2", "sonnet", 1000)
            with open(path, "a") as f:
                f.write(half[:20])  # still being written
            self.assertEqual(carbon.load(root, date(2026, 10, 1), state), [])
            with open(path, "a") as f:
                f.write(half[20:])
            self.assertEqual([r["model"] for r in carbon.load(root, date(2026, 10, 1), state)], ["sonnet"])

    def test_session_filter_reads_only_that_sessions_logs(self):
        with tempfile.TemporaryDirectory() as root:
            for sid in ("s1", "s2"):
                with open(os.path.join(root, sid + ".jsonl"), "w") as f:
                    f.write(line("m-" + sid, "sonnet", 1000))
            rows = carbon.load(root, date(2026, 10, 1), session="s2")
        self.assertEqual([r["session"] for r in rows], ["s2"])

    def test_json_summary_keeps_the_keys_the_band_reads(self):
        with tempfile.TemporaryDirectory() as root:
            now = datetime.now(timezone.utc).isoformat()
            with open(os.path.join(root, "s1.jsonl"), "w") as f:
                f.write(line("m1", "claude-sonnet-5-5", 1000, ts=now))
            args = argparse.Namespace(root=root, grid=400, wue=1.0, days=30, session="s1")
            out = carbon.json_summary(args)
        # 1k sonnet output tokens = 0.6 Wh x PUE 1.2 = 0.72 Wh = 0.288 g at 400 g/kWh
        self.assertEqual(out, {"today": {"g": 0.29, "kwh": 0.0007, "water_l": 0.001},
                               "session": {"g": 0.29, "kwh": 0.0007, "water_l": 0.001, "tokens": 1000}})

    def test_bad_flags_exit_with_a_message(self):
        for flags, message in ((["--days", "0"], "--days must be 1 or more"),
                               (["--grid", "-1"], "cannot be negative")):
            run = subprocess.run([sys.executable, SCRIPT, *flags], capture_output=True, text=True)
            self.assertEqual(run.returncode, 2)
            self.assertIn(message, run.stderr)

    def test_live_server_refuses_other_host_names(self):
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        with tempfile.TemporaryDirectory() as root:
            server = subprocess.Popen([sys.executable, SCRIPT, "--live", "--port", str(port), "--root", root],
                                      stdout=subprocess.PIPE, text=True)
            try:
                for out in server.stdout:
                    if "Live dashboard" in out:
                        break
                for host, status in ((f"evil.example:{port}", 403), (f"127.0.0.1:{port}", 200), (f"localhost:{port}", 200)):
                    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
                    conn.request("GET", "/data.json", headers={"Host": host})
                    self.assertEqual(conn.getresponse().status, status, host)
                    conn.close()
            finally:
                server.terminate()
                server.wait()
                server.stdout.close()

    def test_cache_reads_are_cheapest(self):
        out = carbon.energy_wh({"output_tokens": 1000}, "x")[1]
        fresh = carbon.energy_wh({"input_tokens": 1000}, "x")[1]
        cached = carbon.energy_wh({"cache_read_input_tokens": 1000}, "x")[1]
        self.assertGreater(out, fresh)
        self.assertGreater(fresh, cached)


if __name__ == "__main__":
    unittest.main()
