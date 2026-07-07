from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from rocketlib import Entry, IInstanceBase, warning

from .IGlobal import IGlobal


class IInstance(IInstanceBase):
    IGlobal: IGlobal

    def open(self, entry: Entry):
        self._chunks: list[str] = []

    def writeText(self, text: str):
        self._chunks.append(text)
        return self.preventDefault()

    def _emit_step(self, name: str, fields: dict[str, Any] | None = None) -> None:
        payload = fields or {}
        safe_payload = {
            key: ("[REDACTED]" if key.lower() in {"bearer", "token", "authorization"} else value)
            for key, value in payload.items()
        }
        line = f"graphjudge.pipe.{name} {json.dumps(safe_payload, ensure_ascii=False, default=str)}"
        print(line, flush=True)
        try:
            self.instance.sendSSE("graphjudge_step", step=name, **safe_payload)
        except Exception:
            pass

    def _ensure_repo_on_path(self) -> None:
        for item in os.environ.get("PYTHONPATH", "").split(os.pathsep):
            if item and item not in sys.path:
                sys.path.insert(0, item)
        repo_root = os.environ.get("GRAPHJUDGE_REPO_ROOT")
        if not repo_root:
            for item in os.environ.get("PYTHONPATH", "").split(os.pathsep):
                candidate = Path(item) / "pipeline" / "graphjudge_runtime.py"
                if item and candidate.exists():
                    repo_root = item
                    break
        if repo_root and repo_root not in sys.path:
            sys.path.insert(0, repo_root)

    def closing(self):
        raw = "".join(self._chunks).strip()
        if not raw:
            return self.preventDefault()

        self._emit_step("input.received", {"bytes": len(raw.encode("utf-8"))})
        try:
            payload = json.loads(raw)
            self._ensure_repo_on_path()
            from pipeline.graphjudge_runtime import run_production_steps, validate_verdict

            verdict = run_production_steps(
                user_id=payload["user_id"],
                job_id=payload["job_id"],
                text=payload["text"],
                bearer=payload.get("bearer"),
                credit_already_consumed=payload.get("credit_already_consumed", False),
                log_step=self._emit_step,
            )
            validate_verdict(verdict)
            self._emit_step(
                "verdict.ready",
                {
                    "job_id": verdict.get("job_id"),
                    "doc_score": verdict.get("doc_score"),
                    "claims": len(verdict.get("claims", [])),
                },
            )
            self.instance.writeText(json.dumps(verdict, ensure_ascii=False, separators=(",", ":")))
        except Exception as exc:
            warning(f"GraphJudge runner failed: {exc}")
            self._emit_step("error", {"error": repr(exc)})
            raise
