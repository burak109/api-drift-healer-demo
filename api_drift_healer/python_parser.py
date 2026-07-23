from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SUPPORTED_REQUEST_METHODS = {
    "post",
    "put",
    "patch",
}


class PythonParseError(Exception):
    """Raised when a Python test file cannot be parsed safely."""


@dataclass(frozen=True)
class PythonPayload:
    """A literal dictionary used as an HTTP request payload."""

    variable_name: str | None
    fields: tuple[str, ...]
    values: dict[str, Any]
    line_number: int
    end_line_number: int | None


@dataclass(frozen=True)
class PythonRequest:
    """A supported requests call found in a Python test file."""

    method: str
    url: str
    payload: PythonPayload
    line_number: int


@dataclass(frozen=True)
class PythonParseResult:
    """Result of static analysis for one Python source file."""

    requests: tuple[PythonRequest, ...]
    skipped_reasons: tuple[str, ...]


class PythonRequestParser(ast.NodeVisitor):
    """Find simple requests calls and their literal JSON payloads."""

    def __init__(self) -> None:
        self._dict_assignments: dict[str, ast.Dict] = {}
        self._requests: list[PythonRequest] = []
        self._skipped_reasons: list[str] = []

    def parse(self, source: str) -> PythonParseResult:
        """Parse Python source without executing it."""

        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            raise PythonParseError(
                "Python source could not be parsed: "
                f"line {exc.lineno}: {exc.msg}"
            ) from exc

        self.visit(tree)

        return PythonParseResult(
            requests=tuple(self._requests),
            skipped_reasons=tuple(self._skipped_reasons),
        )

    def visit_Assign(self, node: ast.Assign) -> None:
        """Store simple variable assignments containing literal dictionaries."""

        if isinstance(node.value, ast.Dict):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self._dict_assignments[target.id] = node.value

        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        """Store annotated assignments containing literal dictionaries."""

        if (
            isinstance(node.target, ast.Name)
            and isinstance(node.value, ast.Dict)
        ):
            self._dict_assignments[node.target.id] = node.value

        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Find supported requests calls."""

        request_method = self._get_request_method(node)

        if request_method is None:
            self.generic_visit(node)
            return

        url = self._get_literal_url(node)

        if url is None:
            self._skipped_reasons.append(
                f"Line {node.lineno}: dynamic or missing request URL"
            )
            self.generic_visit(node)
            return

        payload = self._get_payload(node)

        if payload is None:
            self._skipped_reasons.append(
                f"Line {node.lineno}: "
                "unsupported or missing json payload"
            )
            self.generic_visit(node)
            return

        self._requests.append(
            PythonRequest(
                method=request_method.upper(),
                url=url,
                payload=payload,
                line_number=node.lineno,
            )
        )

        self.generic_visit(node)

    @staticmethod
    def _get_request_method(
        node: ast.Call,
    ) -> str | None:
        """Return the supported requests method used by a call."""

        function = node.func

        if not isinstance(function, ast.Attribute):
            return None

        if not isinstance(function.value, ast.Name):
            return None

        if function.value.id != "requests":
            return None

        method = function.attr.lower()

        if method not in SUPPORTED_REQUEST_METHODS:
            return None

        return method

    @staticmethod
    def _get_literal_url(
        node: ast.Call,
    ) -> str | None:
        """Read a literal URL from positional or keyword arguments."""

        if node.args:
            first_argument = node.args[0]

            if (
                isinstance(first_argument, ast.Constant)
                and isinstance(first_argument.value, str)
            ):
                return first_argument.value

        for keyword in node.keywords:
            if (
                keyword.arg == "url"
                and isinstance(keyword.value, ast.Constant)
                and isinstance(keyword.value.value, str)
            ):
                return keyword.value.value

        return None

    def _get_payload(
        self,
        node: ast.Call,
    ) -> PythonPayload | None:
        """Resolve a literal dictionary passed through the json argument."""

        json_value: ast.expr | None = None

        for keyword in node.keywords:
            if keyword.arg == "json":
                json_value = keyword.value
                break

        if json_value is None:
            return None

        if isinstance(json_value, ast.Dict):
            return self._build_payload(
                dictionary=json_value,
                variable_name=None,
            )

        if isinstance(json_value, ast.Name):
            dictionary = self._dict_assignments.get(
                json_value.id
            )

            if dictionary is None:
                return None

            return self._build_payload(
                dictionary=dictionary,
                variable_name=json_value.id,
            )

        return None

    @staticmethod
    def _build_payload(
        dictionary: ast.Dict,
        variable_name: str | None,
    ) -> PythonPayload | None:
        """Convert a safe literal dictionary into a PythonPayload."""

        try:
            literal_value = ast.literal_eval(dictionary)
        except (ValueError, TypeError, SyntaxError):
            return None

        if not isinstance(literal_value, dict):
            return None

        if not all(
            isinstance(key, str) and bool(key)
            for key in literal_value
        ):
            return None

        try:
            json.dumps(
                literal_value,
                allow_nan=False,
            )
        except (TypeError, ValueError):
            return None

        return PythonPayload(
            variable_name=variable_name,
            fields=tuple(literal_value.keys()),
            values=dict(literal_value),
            line_number=dictionary.lineno,
            end_line_number=getattr(
                dictionary,
                "end_lineno",
                None,
            ),
        )


def parse_python_source(
    source: str,
) -> PythonParseResult:
    """Parse Python source code without changing or executing it."""

    return PythonRequestParser().parse(source)


def parse_python_file(
    file_path: str | Path,
) -> PythonParseResult:
    """Read and parse a Python source file."""

    path = Path(file_path)

    if not path.exists():
        raise PythonParseError(
            f"Python file does not exist: {path}"
        )

    if not path.is_file():
        raise PythonParseError(
            f"Python path is not a file: {path}"
        )

    try:
        source = path.read_text(
            encoding="utf-8",
        )
    except OSError as exc:
        raise PythonParseError(
            f"Python file could not be read: {path}"
        ) from exc

    return parse_python_source(source)