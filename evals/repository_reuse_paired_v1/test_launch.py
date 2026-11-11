import sys
import tempfile
import time
import unittest
import threading
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch
import launch


class LaunchTests(unittest.TestCase):
    def test_timeout_joins_actual_worker_before_final_receipt(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            row = {
                "attempt_id": "probe",
                "fixture": "addition-repair",
                "arm": "direct",
                "repeat": 1,
            }
            result = launch.run_one(
                root,
                row,
                dry=True,
                command=[sys.executable, "-c", "import time;time.sleep(60)"],
                attempt_seconds=0.1,
                cooperative_seconds=0.1,
            )
            self.assertEqual(result["state"], "timeout")
            self.assertTrue(result["cleanup"]["joined"], result)
            self.assertTrue((root / "attempt.json").exists())
            self.assertFalse(result["accepted"])

    def test_setup_failure_keeps_fixed_remaining_denominator(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name) / "cohort"
            with patch.object(launch, "run_one", side_effect=OSError("setup fault")):
                receipt = launch.execute(root, dry=True)
            self.assertEqual(len(receipt["attempts"]), 12)
            self.assertEqual(receipt["attempts"][0]["state"], "setup_failed")
            self.assertTrue(all(row["state"] == "NOT_RUN" for row in receipt["attempts"][1:]))
            self.assertFalse(receipt["qualification_pass"])

    def test_primary_interrupt_waits_for_owned_cleanup(self):
        completed = []

        class Owner:
            def stop(self):
                time.sleep(0.1)
                completed.append(True)
                return {"joined": True}

        real = threading.Event()

        class InterruptedEvent:
            raised = False

            def set(self):
                real.set()

            def is_set(self):
                return real.is_set()

            def wait(self, timeout):
                if not self.raised:
                    self.raised = True
                    raise KeyboardInterrupt("first")
                return real.wait(timeout)

        with patch.object(
            launch, "threading", SimpleNamespace(Event=InterruptedEvent, Thread=threading.Thread)
        ):
            value = launch.close_owned(Owner())
        self.assertEqual(str(value["_primary_exception"]), "first")
        self.assertEqual(completed, [True])


if __name__ == "__main__":
    unittest.main()


class ProcessTests(unittest.TestCase):
    def test_actual_descendant_is_gone_before_final_receipt(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            marker = root / "child.pid"
            code = "import subprocess,sys,time,pathlib; child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)']); pathlib.Path(sys.argv[1]).write_text(str(child.pid)); time.sleep(60)"
            row = {
                "attempt_id": "descendant",
                "fixture": "addition-repair",
                "arm": "direct",
                "repeat": 1,
            }
            result = launch.run_one(
                root,
                row,
                dry=True,
                command=[sys.executable, "-c", code, str(marker)],
                attempt_seconds=0.8,
                cooperative_seconds=0.1,
            )
            self.assertTrue(marker.exists())
            pid = int(marker.read_text())
            stat = Path("/proc") / str(pid) / "stat"
            if stat.exists():
                self.assertEqual(stat.read_text().rsplit(")", 1)[1].split()[0], "Z")
            self.assertTrue(result["cleanup"]["joined"], result)
            self.assertTrue(result["finalized_after_owned_cleanup"])


class ReceiptTruthTests(unittest.TestCase):
    def test_worker_nonzero_exit_cannot_publish_success(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            code = "import json,pathlib,sys; pathlib.Path(sys.argv[1]).write_text(json.dumps({'state':'finished','cleanup_joined':True,'oracle':{'accepted':True},'denials':[]}));sys.exit(2)"
            row = {
                "attempt_id": "exit-failure",
                "fixture": "addition-repair",
                "arm": "direct",
                "repeat": 1,
            }
            result = launch.run_one(
                root,
                row,
                dry=True,
                command=[sys.executable, "-c", code, str(root / "worker.json")],
                attempt_seconds=5,
            )
            self.assertFalse(result["accepted"])
            self.assertEqual(result["state"], "worker_exit_failed")


class NativeInterruptTests(unittest.TestCase):
    def test_repeated_real_sigint_joins_worker_before_return(self):
        import json
        import os
        import signal
        import contract as c
        import subprocess

        script = """import json,os,signal,subprocess,sys,threading,time
from launch import close_owned
child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'])
ready=threading.Event();counter=0
def interrupt(signum,frame):
 global counter
 counter+=1
 raise KeyboardInterrupt('interrupt-'+str(counter))
signal.signal(signal.SIGINT,interrupt)
class Owner:
 def stop(self):
  ready.set();time.sleep(.2);child.terminate();child.wait(timeout=3)
  return {'joined':True}
def signal_twice():
 ready.wait();os.kill(os.getpid(),signal.SIGINT);time.sleep(.03);os.kill(os.getpid(),signal.SIGINT)
t=threading.Thread(target=signal_twice);t.start()
try:
 result=close_owned(Owner());t.join();assert child.poll() is not None
 print(json.dumps({'reason':str(result.pop('_primary_exception')),'joined':result['joined'],'returncode':child.returncode}))
finally:
 if child.poll() is None:child.kill();child.wait()
"""
        process = subprocess.Popen(
            [sys.executable, "-c", script],
            cwd=c.HERE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        try:
            stdout, stderr = process.communicate(timeout=8)
            self.assertEqual(process.returncode, 0, stderr.decode())
            row = json.loads(stdout)
            self.assertEqual(row["reason"], "interrupt-1")
            self.assertTrue(row["joined"])
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
