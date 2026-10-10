"""Abstract forensic tool interface and registry.

Seven forensic tools are defined (search_logs, get_host_context,
get_user_context, lookup_mitre_technique, enrich_ip, build_timeline,
submit_incident_report). Stage B owner: tools-engineer (feat/forensic-tools).

All tools are read-only with respect to incident state except
submit_incident_report, which creates a report artifact.
"""

from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from typing import Any, ClassVar

from pydantic import BaseModel, ValidationError

from contracts.tools import ToolError, ToolInvocation


class ForensicToolError(RuntimeError):
    """Tool execution failure (carries a structured ToolError)."""

    def __init__(self, error: ToolError) -> None:
        super().__init__(error.message)
        self.error = error


class ForensicTool(ABC):
    """Base class for every forensic tool.

    Subclasses declare `name`, `description`, `args_model`, `result_model`,
    and implement `run`. `invoke` validates arguments, enforces `timeout_s`,
    never raises, and always returns a ToolInvocation audit record.
    """

    name: ClassVar[str]
    description: ClassVar[str]
    args_model: ClassVar[type[BaseModel]]
    result_model: ClassVar[type[BaseModel]]
    timeout_s: ClassVar[float] = 10.0
    read_only: ClassVar[bool] = True

    @abstractmethod
    def run(self, args: Any) -> BaseModel:
        """Execute the tool with validated arguments."""

    def _run_with_timeout(self, args: BaseModel) -> BaseModel:
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(self.run, args)
        try:
            return future.result(timeout=self.timeout_s)
        except FutureTimeoutError as exc:
            raise ForensicToolError(
                ToolError(
                    error_code="TIMEOUT",
                    message=f"{self.name} exceeded {self.timeout_s}s",
                    retriable=True,
                )
            ) from exc
        finally:
            # Do not block on a hung worker thread.
            executor.shutdown(wait=False, cancel_futures=True)

    def invoke(self, arguments: dict[str, Any], incident_id: str) -> ToolInvocation:
        """Validate, run with timeout, and return an audit record (never raises)."""
        invocation_id = f"inv-{uuid.uuid4()}"
        start = time.monotonic()
        error: ToolError | None = None
        result_dict: dict[str, Any] | None = None
        referenced: list[str] = []

        try:
            try:
                args = self.args_model.model_validate(arguments)
            except ValidationError as exc:
                raise ForensicToolError(
                    ToolError(error_code="INVALID_ARGUMENTS", message=str(exc)[:2000])
                ) from exc

            result = self._run_with_timeout(args)
            if not isinstance(result, self.result_model):
                raise ForensicToolError(
                    ToolError(
                        error_code="INVALID_RESULT",
                        message=f"{self.name} returned {type(result).__name__}, "
                        f"expected {self.result_model.__name__}",
                    )
                )
            result_dict = result.model_dump(mode="json")
            referenced = list(getattr(result, "matched_evidence_ids", []) or [])
        except ForensicToolError as exc:
            error = exc.error
        except Exception as exc:  # noqa: BLE001 - tools must never crash the agent
            error = ToolError(error_code="INTERNAL_ERROR", message=str(exc)[:2000])

        return ToolInvocation(
            invocation_id=invocation_id,
            incident_id=incident_id,
            tool_name=self.name,
            arguments=arguments,
            result=result_dict,
            referenced_evidence_ids=referenced,
            error=error,
            duration_ms=int((time.monotonic() - start) * 1000),
        )


class ToolRegistry:
    """Registers tool instances by name; shared by inference and reasoning."""

    def __init__(self) -> None:
        self._tools: dict[str, ForensicTool] = {}

    def register(self, tool: ForensicTool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> ForensicTool:
        if name not in self._tools:
            raise KeyError(f"unknown forensic tool: {name}")
        return self._tools[name]

    def names(self) -> list[str]:
        return sorted(self._tools)

    def as_tool_specs(self) -> list[dict[str, Any]]:
        """Export tool specs (JSON Schema parameters) for inference backends."""
        return [
            {
                "name": n,
                "description": self._tools[n].description,
                "parameters": self._tools[n].args_model.model_json_schema(),
            }
            for n in self.names()
        ]
