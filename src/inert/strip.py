import ast
import io
import tokenize

_SCOPES = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


def _is_docstring(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    )


def strip_text(source: str) -> str:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, _SCOPES) and node.body and _is_docstring(node.body[0]):
            node.body.pop(0)
            if not node.body:
                node.body.append(ast.Pass())
    return ast.unparse(ast.fix_missing_locations(tree))


def natural_text(source: str) -> str:
    tree = ast.parse(source)
    parts: list[tuple[int, int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, _SCOPES) and node.body and _is_docstring(node.body[0]):
            doc = node.body[0]
            parts.append((doc.lineno, doc.col_offset, doc.value.value))
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT:
            parts.append((*token.start, token.string[1:].lstrip()))
    return "\n".join(text for _, _, text in sorted(parts))
