"""
====================================================
  Agent Trace — Thought → Action → Observation
  ReAct-style execution trace for chat & analyze.
  VinUni AI20k Batch 02 · Day 06
====================================================

Each step records:
  Thought   — why this action is being taken
  Action    — what function/tool is called + args
  Observation — result (success, blocked, or error)
"""

import time
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

trace_logger = logging.getLogger("agent.trace")


@dataclass
class TraceStep:
    step: int
    thought: str
    action: str
    action_args: Dict[str, Any]
    observation: str = ""
    status: str = "pending"       # pending | success | blocked | error
    duration_ms: float = 0.0
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "step": self.step,
            "thought": self.thought,
            "action": self.action,
            "action_args": self.action_args,
            "observation": self.observation,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "error": self.error,
        }


class AgentTrace:
    """
    Collects and logs a Thought→Action→Observation trace for one request.

    Usage:
        trace = AgentTrace(session_id, user_id, user_message)

        step = trace.begin("Checking rate limit", "check_rate_limit", user_id=uid)
        if limited:
            trace.block(step, "Rate limit exceeded: 5/5 messages in 60s")
        else:
            trace.ok(step, "Rate limit OK — 2/5 messages used")

        trace.finish("success")
        return trace.to_dict()
    """

    def __init__(self, session_id: str, user_id: str, user_message: str = ""):
        self.session_id = session_id
        self.user_id = user_id
        self.user_message = user_message
        self.steps: List[TraceStep] = []
        self._started_at = time.monotonic()
        self._wall_start = datetime.now(timezone.utc)
        self._step_start = self._started_at
        self.final_status = "pending"
        self.final_error: Optional[str] = None

    # ── Step lifecycle ────────────────────────────────────────────────

    def begin(self, thought: str, action: str, **action_args) -> TraceStep:
        """Start a new trace step. Returns the step for later completion."""
        step = TraceStep(
            step=len(self.steps) + 1,
            thought=thought,
            action=action,
            action_args={k: self._truncate(v) for k, v in action_args.items()},
        )
        self.steps.append(step)
        self._step_start = time.monotonic()

        trace_logger.info(
            "[%s] ── Thought %d: %s",
            self.session_id, step.step, thought
        )
        trace_logger.info(
            "[%s] ── Action  %d: %s(%s)",
            self.session_id, step.step, action, self._fmt_args(action_args)
        )
        return step

    def ok(self, step: TraceStep, observation: str) -> TraceStep:
        """Mark step as successful."""
        step.duration_ms = self._elapsed_ms()
        step.status = "success"
        step.observation = observation
        trace_logger.info(
            "[%s] ── Obs.    %d ✅ %s  [%.0fms]",
            self.session_id, step.step, observation, step.duration_ms
        )
        return step

    def block(self, step: TraceStep, observation: str) -> TraceStep:
        """Mark step as blocked (guardrail / rate limit / quiz gate)."""
        step.duration_ms = self._elapsed_ms()
        step.status = "blocked"
        step.observation = observation
        trace_logger.warning(
            "[%s] ── Obs.    %d 🚫 BLOCKED: %s  [%.0fms]",
            self.session_id, step.step, observation, step.duration_ms
        )
        return step

    def error(self, step: TraceStep, error_msg: str, observation: str = "") -> TraceStep:
        """Mark step as errored."""
        step.duration_ms = self._elapsed_ms()
        step.status = "error"
        step.error = error_msg
        step.observation = observation or f"ERROR: {error_msg}"
        trace_logger.error(
            "[%s] ── Obs.    %d ❌ ERROR: %s  [%.0fms]",
            self.session_id, step.step, error_msg, step.duration_ms
        )
        return step

    # ── Trace completion ──────────────────────────────────────────────

    def finish(self, status: str = "success", error: Optional[str] = None):
        self.final_status = status
        self.final_error = error
        total_ms = (time.monotonic() - self._started_at) * 1000

        if status == "success":
            trace_logger.info(
                "[%s] ═══ TRACE COMPLETE ✅ %s in %.0fms — %d steps ═══",
                self.session_id, status, total_ms, len(self.steps)
            )
        else:
            trace_logger.warning(
                "[%s] ═══ TRACE COMPLETE %s %s in %.0fms — %d steps ═══",
                self.session_id,
                "🚫" if status == "blocked" else "❌",
                status, total_ms, len(self.steps)
            )
            if error:
                trace_logger.error("[%s] Final error: %s", self.session_id, error)

    # ── Serialization ─────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "started_at": self._wall_start.isoformat(),
            "total_ms": round((time.monotonic() - self._started_at) * 1000, 1),
            "final_status": self.final_status,
            "final_error": self.final_error,
            "steps": [s.to_dict() for s in self.steps],
        }

    # ── Helpers ───────────────────────────────────────────────────────

    def _elapsed_ms(self) -> float:
        return round((time.monotonic() - self._step_start) * 1000, 1)

    @staticmethod
    def _truncate(v: Any, max_len: int = 60) -> Any:
        if isinstance(v, str) and len(v) > max_len:
            return v[:max_len] + "…"
        return v

    @staticmethod
    def _fmt_args(args: dict) -> str:
        parts = []
        for k, v in args.items():
            if isinstance(v, str):
                display = v[:50] + "…" if len(v) > 50 else v
                parts.append(f'{k}="{display}"')
            else:
                parts.append(f"{k}={v}")
        return ", ".join(parts)
