import ast
import copy

_COMPARISON = {
    ast.Lt: ast.LtE,
    ast.LtE: ast.Lt,
    ast.Gt: ast.GtE,
    ast.GtE: ast.Gt,
    ast.Eq: ast.NotEq,
    ast.NotEq: ast.Eq,
}
_ARITHMETIC = {ast.Add: ast.Sub, ast.Sub: ast.Add, ast.Mult: ast.FloorDiv, ast.FloorDiv: ast.Mult}


class _Mutator(ast.NodeTransformer):
    def __init__(self, operator: str) -> None:
        self.operator = operator
        self.changed = False
        self.parents: list[ast.AST] = []

    def visit(self, node: ast.AST) -> ast.AST:
        if not self.changed:
            if self.operator == "comparison" and isinstance(node, ast.Compare):
                for i, op in enumerate(node.ops):
                    if type(op) in _COMPARISON:
                        node.ops[i] = _COMPARISON[type(op)]()
                        self.changed = True
                        break
            elif self.operator == "off_by_one" and isinstance(node, ast.Constant):
                if type(node.value) is int and not self._boolean_context(node):
                    node.value += 1
                    self.changed = True
            elif self.operator == "arithmetic" and isinstance(node, ast.BinOp):
                if type(node.op) in _ARITHMETIC:
                    node.op = _ARITHMETIC[type(node.op)]()
                    self.changed = True
            elif self.operator == "boundary_slice" and isinstance(node, ast.Slice):
                if node.upper is not None:
                    node.upper = ast.BinOp(node.upper, ast.Sub(), ast.Constant(1))
                    self.changed = True
        self.parents.append(node)
        result = self.generic_visit(node)
        self.parents.pop()
        return result

    def _boolean_context(self, node: ast.Constant) -> bool:
        if node.value not in (0, 1) or not self.parents:
            return False
        parent = self.parents[-1]
        return (
            isinstance(parent, ast.BoolOp)
            or isinstance(parent, ast.UnaryOp)
            and isinstance(parent.op, ast.Not)
            or isinstance(parent, (ast.If, ast.While, ast.IfExp, ast.Assert))
            and parent.test is node
        )


def mutants(source: str) -> list[tuple[str, str]]:
    tree = ast.parse(source)
    results = []
    for operator in ("comparison", "off_by_one", "arithmetic", "boundary_slice"):
        mutator = _Mutator(operator)
        changed = mutator.visit(copy.deepcopy(tree))
        if mutator.changed:
            results.append((operator, ast.unparse(ast.fix_missing_locations(changed))))
    return results
