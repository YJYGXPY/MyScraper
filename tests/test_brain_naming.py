import unittest
import ast
from pathlib import Path


def _load_brain_ast() -> ast.Module:
    brain_path = Path(__file__).resolve().parents[1] / "brain.py"
    source = brain_path.read_text(encoding="utf-8")
    return ast.parse(source)


def _collect_function_arg_names(module: ast.Module) -> set[str]:
    arg_names: set[str] = set()
    for node in ast.walk(module):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for arg in node.args.posonlyargs:
                arg_names.add(arg.arg)
            for arg in node.args.args:
                arg_names.add(arg.arg)
            if node.args.vararg is not None:
                arg_names.add(node.args.vararg.arg)
            for arg in node.args.kwonlyargs:
                arg_names.add(arg.arg)
            if node.args.kwarg is not None:
                arg_names.add(node.args.kwarg.arg)
    return arg_names


def _collect_module_level_names(module: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in module.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
                elif isinstance(target, (ast.Tuple, ast.List)):
                    for elt in target.elts:
                        if isinstance(elt, ast.Name):
                            names.add(elt.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


class TestBrainNaming(unittest.TestCase):
    def test_no_provider_in_function_param_names(self) -> None:
        module = _load_brain_ast()
        arg_names = _collect_function_arg_names(module)
        self.assertNotIn("provider", arg_names)

    def test_no_ark_names_in_module_level_symbols(self) -> None:
        module = _load_brain_ast()
        module_level_names = _collect_module_level_names(module)
        forbidden_names = {"ARK_API_KEY", "ARK_BASE_URL", "ARK_MODEL"}
        self.assertTrue(forbidden_names.isdisjoint(module_level_names))

    def test_lightweight_text_regression_for_ark_tokens(self) -> None:
        brain_path = Path(__file__).resolve().parents[1] / "brain.py"
        content = brain_path.read_text(encoding="utf-8")
        for token in ("ARK_API_KEY", "ARK_BASE_URL", "ARK_MODEL"):
            self.assertNotIn(token, content)
