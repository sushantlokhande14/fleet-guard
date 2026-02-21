"""Thin, typed wrapper around the fgsim binary.

The simulator is a separate C++ process on purpose: it is the part that has to be
fast and bit-for-bit reproducible, and keeping it behind a CLI means any drive the
platform reports can be replayed by hand with the exact same command.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .config import REPO_ROOT, get_settings


class FgsimError(RuntimeError):
    pass


def find_fgsim(explicit: str | None = None) -> str:
    candidates = [explicit, get_settings().fgsim, shutil.which("fgsim")]
    candidates += [str(REPO_ROOT / "build" / "fgsim"), "/usr/local/bin/fgsim"]
    for c in candidates:
        if c and Path(c).is_file() and os.access(c, os.X_OK):
            return c
    raise FgsimError("fgsim binary not found; set FG_FGSIM or put it on PATH")


class Fgsim:
    def __init__(self, path: str | None = None):
        self.path = find_fgsim(path)

    # -- plumbing ---------------------------------------------------------------
    def _run(self, *args: str) -> str:
        proc = subprocess.run([self.path, *args], capture_output=True, text=True)
        if proc.returncode != 0:
            msg = proc.stderr.strip().splitlines()
            raise FgsimError(msg[0] if msg else f"fgsim exited with {proc.returncode}")
        return proc.stdout

    def _json(self, *args: str) -> Any:
        return json.loads(self._run(*args))

    @staticmethod
    def _build_file(build: dict | None, tmp: str, name: str) -> list[str]:
        if build is None:
            return []
        path = Path(tmp) / f"{name}.json"
        path.write_text(json.dumps(build))
        return [str(path)]

    # -- commands ---------------------------------------------------------------
    def version(self) -> str:
        return self._run("version").strip()

    def families(self) -> list[str]:
        return self._run("families").split()

    def defaults(self) -> dict:
        return self._json("defaults")

    def scenario(self, family: str, seed: int, geometry: bool = False) -> dict:
        args = ["scenario", "--family", family, "--seed", str(seed)]
        if geometry:
            args.append("--geometry")
        return self._json(*args)

    def run(self, family: str, seed: int, build: dict | None = None, frames_path: str | None = None) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            args = ["run", "--family", family, "--seed", str(seed), "--events"]
            bf = self._build_file(build, tmp, "build")
            if bf:
                args += ["--build", bf[0]]
            if frames_path:
                args += ["--frames", frames_path]
            return self._json(*args)

    def compare(self, family: str, seed: int, baseline: dict, candidate: dict,
                frames_prefix: str | None = None) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            args = ["compare", "--family", family, "--seed", str(seed),
                    "--baseline", self._build_file(baseline, tmp, "baseline")[0],
                    "--candidate", self._build_file(candidate, tmp, "candidate")[0]]
            if frames_prefix:
                args += ["--frames-prefix", frames_prefix]
            return self._json(*args)

    def batch(self, *, count: int, out_dir: str | Path, baseline: dict, candidate: dict,
              families: list[str] | None = None, seed_start: int = 0, threads: int = 0,
              frames: str = "flagged", max_frame_pairs: int = 500, chunk: int = 1024,
              on_progress: Callable[[int, int], None] | None = None) -> dict:
        """Drive `count` scenarios with both builds. Streams progress from stderr."""
        with tempfile.TemporaryDirectory() as tmp:
            args = [self.path, "batch", "--count", str(count), "--out", str(out_dir),
                    "--seed-start", str(seed_start), "--threads", str(threads),
                    "--frames", frames, "--max-frame-pairs", str(max_frame_pairs), "--chunk", str(chunk),
                    "--baseline", self._build_file(baseline, tmp, "baseline")[0],
                    "--candidate", self._build_file(candidate, tmp, "candidate")[0]]
            if families:
                args += ["--families", ",".join(families)]
            proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            errors: list[str] = []
            assert proc.stderr is not None and proc.stdout is not None
            for line in proc.stderr:
                parts = line.split()
                if len(parts) == 3 and parts[0] == "progress":
                    if on_progress:
                        on_progress(int(parts[1]), int(parts[2]))
                elif line.strip():
                    errors.append(line.strip())
            out = proc.stdout.read()
            if proc.wait() != 0:
                raise FgsimError(errors[0] if errors else "fgsim batch failed")
            return json.loads(out)
