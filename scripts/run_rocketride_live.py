#!/usr/bin/env python3
"""Run GraphJudge's RocketRide proof path and write sanitized artifacts."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from dotenv import load_dotenv

REPO = Path(__file__).resolve().parents[1]
PIPE_PATH = REPO / "pipeline" / "graphjudge.pipe"
DOCS = REPO / "docs"
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

DEMO_EMAIL = "demo-999@graphjudge.demo"
DEMO_PASSWORD = "GraphJudge!2026"
DEMO_TEXT = (
    "Corwin Mavik manages Jessa Minlow. Arlen Veyro owns a pet named Bramble. "
    "Gavo Rellin lives in Dovemarsh. Della Quorin was born in 1992. "
    "Brisa Nalore is married to Corwin Mavik. Mira Vell works at Aster Quay Group. "
    "Zavren Pell works at Cindrel Motive Office. Ostia Kel works at Cindrel Motive Office. "
    "Zavren Pell manages Ostia Kel. Ostia Kel leads Project Sablewick. "
    "Noll Varen leads Project Sablewick. Noll Varen manages Zavren Pell."
)


class ProofLogger:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self.path.open("w", encoding="utf-8")
        self._redactions: list[str] = []

    def add_secret(self, value: str | None) -> None:
        if value and value not in self._redactions:
            self._redactions.append(value)

    def redact(self, value: Any) -> str:
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
        for secret in self._redactions:
            text = text.replace(secret, "[REDACTED]")
        for key in ("OPENROUTER_API_KEY", "BUTTERBASE_API_KEY", "GATEWAY_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
            secret = os.environ.get(key)
            if secret:
                text = text.replace(secret, "[REDACTED]")
        return text

    def step(self, name: str, fields: dict[str, Any] | None = None, **kwargs: Any) -> None:
        payload = fields if fields is not None else kwargs
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        line = f"{ts} | {name}"
        if payload:
            line += " | " + self.redact(payload)
        print(line, flush=True)
        self._fh.write(line + "\n")
        self._fh.flush()

    def close(self) -> None:
        self._fh.close()


def post_json(url: str, body: dict[str, Any], headers: dict[str, str] | None = None, timeout: int = 30) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8")
    return json.loads(raw) if raw else {}


def require_env(name: str) -> None:
    if not os.environ.get(name):
        raise RuntimeError(f"{name} is not set")


def load_pipeline_config() -> dict[str, Any]:
    data = json.loads(PIPE_PATH.read_text(encoding="utf-8"))
    return data.get("pipeline", data)


def rocketride_pythonpath() -> str:
    entries = [str(REPO)]
    for site_packages in sorted((REPO / ".venv" / "lib").glob("python*/site-packages")):
        if site_packages.is_dir():
            entries.append(str(site_packages))
    existing = os.environ.get("PYTHONPATH")
    if existing:
        entries.append(existing)
    return os.pathsep.join(dict.fromkeys(entries))


def login(email: str, password: str, logger: ProofLogger) -> tuple[str, str]:
    auth_base = os.environ.get("BUTTERBASE_AUTH_BASE", "https://api.butterbase.ai/auth/app_r1568bo1iteg").rstrip("/")
    logger.step("auth.login.start", {"auth_base": auth_base, "email": email})
    data = post_json(f"{auth_base}/login", {"email": email, "password": password})
    token = data.get("access_token")
    user_id = (data.get("user") or {}).get("id")
    if not token or not user_id:
        raise RuntimeError("Butterbase login did not return access_token and user.id")
    logger.add_secret(token)
    logger.step("auth.login.done", {"user_id": user_id, "token": "[REDACTED]"})
    return user_id, token


async def try_rocketride(args: argparse.Namespace, body: dict[str, Any], logger: ProofLogger) -> dict[str, Any] | None:
    from rocketride import RocketRideClient
    from pipeline.graphjudge_runtime import extract_verdict_from_result, validate_verdict

    async def on_event(event: dict[str, Any]) -> None:
        logger.step("rocketride.event", event)

    async def on_sse(event_type: str, data: dict[str, Any]) -> None:
        logger.step("rocketride.sse", {"type": event_type, **(data or {})})

    logger.step("rocketride.connect.start", {"uri": args.rocketride_uri})
    client = RocketRideClient(
        uri=args.rocketride_uri,
        auth=args.rocketride_auth or "",
        request_timeout=args.request_timeout_ms,
        on_event=on_event,
        on_connect_error=lambda message: logger.step("rocketride.connect.error", {"message": message}),
    )
    token: str | None = None
    try:
        await client.connect(timeout=args.connect_timeout_ms)
        logger.step("rocketride.connect.done", client.get_connection_info())

        services = await client.get_services()
        count = len(services.get("services", services)) if isinstance(services, dict) else len(services)
        logger.step("rocketride.services", {"count": count})

        try:
            config = load_pipeline_config()
            validation = await client.validate(config, source=config.get("source"))
            logger.step("rocketride.validate", validation)
        except Exception as exc:
            logger.step("rocketride.validate.error", {"error": repr(exc)})

        env = {
            "PYTHONPATH": rocketride_pythonpath(),
            "GRAPHJUDGE_REPO_ROOT": str(REPO),
        }
        for key in (
            "SCORER_URL",
            "CONSUME_CREDIT_URL",
            "OPENROUTER_API_KEY",
            "PERSIST_RESULT_URL",
            "BUTTERBASE_API_KEY",
        ):
            if os.environ.get(key):
                env[key] = os.environ[key]

        logger.step("rocketride.use.start", {"pipe": str(PIPE_PATH)})
        started = await client.use(
            filepath=str(PIPE_PATH),
            use_existing=False,
            env=env,
            name=f"graphjudge-live-{body['job_id']}",
        )
        token = started.get("token")
        logger.add_secret(token)
        logger.step("rocketride.use.done", started)
        if not token:
            return None

        try:
            await client.set_events(
                token,
                [
                    "TASK_EVENT",
                    "TASK_EVENT_FLOW",
                    "TASK_EVENT_RUNNING",
                    "TASK_EVENT_BEGIN",
                    "TASK_EVENT_END",
                    "apaevt_status_processing",
                ],
            )
            logger.step("rocketride.events.enabled")
        except Exception as exc:
            logger.step("rocketride.events.warning", {"error": repr(exc)})

        logger.step("rocketride.send.start", {"mimetype": "text/plain"})
        result = await client.send(
            token,
            json.dumps(body),
            objinfo={"name": "graphjudge-live.json"},
            mimetype="text/plain",
            on_sse=on_sse,
        )
        logger.step("rocketride.send.done", result)
        verdict = extract_verdict_from_result(result)
        if verdict is None:
            logger.step("rocketride.verdict.missing", {"fallback": "python_production_steps"})
            return None
        return validate_verdict(verdict)
    except Exception as exc:
        logger.step("rocketride.error", {"error": repr(exc)})
        return None
    finally:
        if token:
            try:
                await client.terminate(token)
                logger.step("rocketride.terminate.done")
            except Exception as exc:
                logger.step("rocketride.terminate.warning", {"error": repr(exc)})
        try:
            await client.disconnect()
        except Exception:
            pass


async def main_async(args: argparse.Namespace) -> int:
    load_dotenv(REPO / ".env")
    for name in ("SCORER_URL", "CONSUME_CREDIT_URL", "OPENROUTER_API_KEY"):
        require_env(name)

    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    log_path = DOCS / f"rocketride-live-{run_id}.log"
    verdict_path = DOCS / f"rocketride-live-{run_id}.verdict.json"
    meta_path = DOCS / f"rocketride-live-{run_id}.meta.json"
    logger = ProofLogger(log_path)

    try:
        for key in ("OPENROUTER_API_KEY", "BUTTERBASE_API_KEY", "GATEWAY_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
            logger.add_secret(os.environ.get(key))

        logger.step("proof.start", {"run_id": run_id, "pipe": str(PIPE_PATH)})
        logger.step(
            "env.required",
            {
                "SCORER_URL": "set",
                "CONSUME_CREDIT_URL": "set",
                "OPENROUTER_API_KEY": "set",
                "ROCKETRIDE_URI": args.rocketride_uri,
            },
        )

        user_id, bearer = login(args.email, args.password, logger)
        job_id = args.job_id or str(uuid4())
        body = {
            "user_id": user_id,
            "job_id": job_id,
            "text": args.text,
            "bearer": bearer,
            "strict": True,
            "credit_already_consumed": False,
        }

        verdict = await try_rocketride(args, body, logger)
        engine_returned_verdict = verdict is not None
        if verdict is None:
            if args.require_engine_verdict:
                raise RuntimeError("RocketRide did not return a section 4.2 verdict")
            logger.step("python_harness.start", {"reason": "RocketRide result did not contain section 4.2 verdict"})
            from pipeline.graphjudge_runtime import run_production_steps

            verdict = run_production_steps(
                user_id=user_id,
                job_id=job_id,
                text=args.text,
                bearer=bearer,
                log_step=logger.step,
            )
            logger.step("python_harness.done")

        verdict_path.write_text(json.dumps(verdict, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        meta = {
            "run_id": run_id,
            "job_id": job_id,
            "rocketride_uri": args.rocketride_uri,
            "rocketride_engine_returned_verdict": engine_returned_verdict,
            "log": str(log_path),
            "verdict": str(verdict_path),
        }
        meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
        logger.step(
            "verdict.ok",
            {
                "job_id": verdict.get("job_id"),
                "doc_score": verdict.get("doc_score"),
                "claims": len(verdict.get("claims", [])),
                "statuses": [(c.get("cid"), c.get("status")) for c in verdict.get("claims", [])],
            },
        )
        logger.step("artifacts", {"log": str(log_path), "verdict": str(verdict_path), "meta": str(meta_path)})
        return 0
    finally:
        logger.step("proof.end")
        logger.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rocketride-uri", default=os.environ.get("ROCKETRIDE_URI", "ws://localhost:5565"))
    parser.add_argument("--rocketride-auth", default=os.environ.get("ROCKETRIDE_APIKEY", ""))
    parser.add_argument("--connect-timeout-ms", type=int, default=30000)
    parser.add_argument("--request-timeout-ms", type=int, default=90000)
    parser.add_argument("--email", default=os.environ.get("GRAPHJUDGE_DEMO_EMAIL", DEMO_EMAIL))
    parser.add_argument("--password", default=os.environ.get("GRAPHJUDGE_DEMO_PASSWORD", DEMO_PASSWORD))
    parser.add_argument("--job-id")
    parser.add_argument("--run-id")
    parser.add_argument("--text", default=DEMO_TEXT)
    parser.add_argument("--require-engine-verdict", action="store_true")
    return parser.parse_args()


def main() -> int:
    try:
        return asyncio.run(main_async(parse_args()))
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
