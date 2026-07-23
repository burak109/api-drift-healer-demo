from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


SUPPORTED_REQUEST_METHODS = {"post", "put", "patch"}


class PythonParseError(Exception):
    """Raised when a Python test file cannot be parsed safely."""


@dataclass(frozen=True)
class PythonPayload:
    """A literal dictionary used as an HTTP request payload."""

    variable_name: str | None
    fields: tuple[str, ...]
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
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            raise PythonParseError(
                f"Python source could not be parsed: line {exc.lineno}: {exc.msg}"
            ) from exc

        self.visit(tree)

        return PythonParseResult(
            requests=tuple(self._requests),
            skipped_reasons=tuple(self._skipped_reasons),
        )

    def visit_Assign(self, node: ast.Assign) -> None:
        if isinstance(node.value, ast.Dict):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self._dict_assignments[target.id] = node.value

        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if (
            isinstance(node.target, ast.Name)
            and isinstance(node.value, ast.Dict)
        ):
            self._dict_assignments[node.target.id] = node.value

        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
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
                f"Line {node.lineno}: unsupported or missing json payload"
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
    def _get_request_method(node: ast.Call) -> str | None:
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
    def _get_literal_url(node: ast.Call) -> str | None:
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

    def _get_payload(self, node: ast.Call) -> PythonPayload | None:
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
            dictionary = self._dict_assignments.get(json_value.id)

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
        fields: list[str] = []

        for key in dictionary.keys:
            if not (
                isinstance(key, ast.Constant)
                and isinstance(key.value, str)
            ):
                return None

            fields.append(key.value)

        return PythonPayload(
            variable_name=variable_name,
            fields=tuple(fields),
            line_number=dictionary.lineno,
            end_line_number=getattr(dictionary, "end_lineno", None),
        )


def parse_python_source(source: str) -> PythonParseResult:
    """Parse Python source code without changing it."""

    return PythonRequestParser().parse(source)


def parse_python_file(file_path: str | Path) -> PythonParseResult:
    """Read and parse a Python source file."""

    path = Path(file_path)

    if not path.exists():
        raise PythonParseError(f"Python file does not exist: {path}")

    if not path.is_file():
        raise PythonParseError(f"Python path is not a file: {path}")

    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PythonParseError(
            f"Python file could not be read: {path}"
        ) from exc

    return parse_python_source(source)