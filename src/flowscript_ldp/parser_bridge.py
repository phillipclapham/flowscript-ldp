"""
Parser Bridge: Subprocess wrapper for FlowScript CLI.

Thin bridge that calls the FlowScript parser (Node.js CLI) and returns
typed IR models. Supports both FlowScript text input and pre-compiled IR JSON.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from .ir import IR


def _find_flowscript_cli() -> Optional[Path]:
    """Search for the FlowScript CLI on PATH."""
    which = shutil.which("flowscript")
    if which is not None:
        return Path(which)
    return None


class ParserError(Exception):
    """Raised when FlowScript CLI parsing fails."""

    def __init__(self, message: str, stderr: str = "", exit_code: int = -1):
        self.stderr = stderr
        self.exit_code = exit_code
        super().__init__(message)


class ParserBridge:
    """Bridge to FlowScript CLI for parsing .fs text into IR."""

    def __init__(self, cli_path: Optional[Path] = None):
        if cli_path is not None:
            self.cli_path = cli_path
        else:
            found = _find_flowscript_cli()
            if found is None:
                raise FileNotFoundError(
                    "FlowScript CLI not found on PATH. "
                    "Install FlowScript (https://github.com/phillipclapham/flowscript) "
                    "or pass cli_path explicitly."
                )
            self.cli_path = found
        if not self.cli_path.exists():
            raise FileNotFoundError(
                f"FlowScript CLI not found at {self.cli_path}. "
                "Ensure FlowScript is installed and built."
            )

    def parse_text(self, flowscript_text: str) -> IR:
        """Parse FlowScript text into typed IR model.

        Writes text to a temp file, calls `flowscript parse`, reads IR JSON.
        """
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".fs", delete=False
        ) as tmp:
            tmp.write(flowscript_text)
            tmp_path = Path(tmp.name)

        try:
            result = subprocess.run(
                ["node", str(self.cli_path), "parse", str(tmp_path), "-c"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                raise ParserError(
                    f"FlowScript parse failed (exit {result.returncode}): {result.stderr.strip()}",
                    stderr=result.stderr,
                    exit_code=result.returncode,
                )

            ir_data = json.loads(result.stdout)
            return IR.model_validate(ir_data)
        finally:
            tmp_path.unlink(missing_ok=True)

    def parse_file(self, file_path: Path) -> IR:
        """Parse a .fs file into typed IR model."""
        if not file_path.exists():
            raise FileNotFoundError(f"FlowScript file not found: {file_path}")

        result = subprocess.run(
            ["node", str(self.cli_path), "parse", str(file_path), "-c"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            raise ParserError(
                f"FlowScript parse failed (exit {result.returncode}): {result.stderr.strip()}",
                stderr=result.stderr,
                exit_code=result.returncode,
            )

        ir_data = json.loads(result.stdout)
        return IR.model_validate(ir_data)

    @staticmethod
    def load_ir_json(json_path: Path) -> IR:
        """Load pre-compiled IR JSON and validate against Pydantic models."""
        if not json_path.exists():
            raise FileNotFoundError(f"IR JSON file not found: {json_path}")

        with open(json_path) as f:
            ir_data = json.load(f)

        return IR.model_validate(ir_data)

    @staticmethod
    def from_dict(data: dict) -> IR:
        """Create IR from a dictionary (e.g., decoded JSON payload)."""
        return IR.model_validate(data)

    def lint(self, file_path: Path) -> dict:
        """Lint a FlowScript file. Returns JSON lint results."""
        result = subprocess.run(
            ["node", str(self.cli_path), "lint", str(file_path), "-j"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode not in (0, 1):  # 1 = lint warnings, not errors
            raise ParserError(
                f"FlowScript lint failed: {result.stderr.strip()}",
                stderr=result.stderr,
                exit_code=result.returncode,
            )

        return json.loads(result.stdout)

    def validate_ir(self, json_path: Path) -> dict:
        """Validate IR JSON against canonical schema. Returns validation results."""
        result = subprocess.run(
            ["node", str(self.cli_path), "validate", str(json_path), "-v"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        return {
            "valid": result.returncode == 0,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }
