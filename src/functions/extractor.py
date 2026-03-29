"""Tree-sitter–based extraction of top-level functions and class methods."""

from __future__ import annotations

import hashlib

from tree_sitter import Language, Node, Parser

from functions.models import FunctionDef


_SUPPORTED_LANGUAGES = {'Python', 'JavaScript', 'TypeScript'}

_FUNCTION_TYPES = frozenset({'function_definition', 'function_declaration'})
_CLASS_TYPES = frozenset({'class_definition', 'class_declaration'})


def _get_language(language: str) -> Language:
    """
    Return the tree-sitter Language object for the given language name.
    Raises ImportError if the grammar package is not installed.
    """
    if language == 'Python':
        import tree_sitter_python as _ts  # type: ignore[import]

        return Language(_ts.language())  # TODO: deprecated
    if language == 'JavaScript':
        import tree_sitter_javascript as _ts  # type: ignore[import]

        return Language(_ts.language())
    if language == 'TypeScript':
        import tree_sitter_typescript as _ts  # type: ignore[import]

        return Language(_ts.language_typescript())
    raise ValueError(f'Unsupported language: {language}')


def _make_function_def(node: Node, source: bytes) -> FunctionDef | None:
    """
    Build a FunctionDef from a tree-sitter function or method node.
    Returns None if the node has no name field.
    """
    name_node = node.child_by_field_name('name')
    if name_node is None:
        return None

    name = source[name_node.start_byte : name_node.end_byte].decode('utf-8')
    body = source[node.start_byte : node.end_byte].decode('utf-8')
    signature = body.split('\n')[0].rstrip()
    start_line = node.start_point[0] + 1  # convert 0-indexed to 1-indexed
    end_line = node.end_point[0] + 1
    checksum = hashlib.sha256(body.encode('utf-8')).hexdigest()

    return FunctionDef(
        name=name,
        signature=signature,
        start_line=start_line,
        end_line=end_line,
        body=body,
        checksum=checksum,
    )


def _collect_class_methods(
    class_node: Node, source: bytes, results: list[FunctionDef]
) -> None:
    """
    Collect all direct method definitions from a class body node.
    Handles decorated methods (Python @staticmethod / @property etc.).
    """
    body = class_node.child_by_field_name('body')
    if body is None:
        return

    for child in body.children:
        if child.type in _FUNCTION_TYPES or child.type == 'method_definition':
            fn = _make_function_def(child, source)
            if fn:
                results.append(fn)
        elif child.type == 'decorated_definition':
            # Python: @decorator\ndef method(): …
            for sub in child.children:
                if sub.type in _FUNCTION_TYPES:
                    fn = _make_function_def(sub, source)
                    if fn:
                        results.append(fn)


def _collect_top_level(node: Node, source: bytes, results: list[FunctionDef]) -> None:
    """
    Walk the root node and collect top-level functions and class methods.
    Only descends one level into class bodies.
    """
    for child in node.children:
        if child.type in _FUNCTION_TYPES:
            fn = _make_function_def(child, source)
            if fn:
                results.append(fn)
        elif child.type in _CLASS_TYPES:
            _collect_class_methods(child, source, results)
        elif child.type == 'decorated_definition':
            # Python: @decorator\ndef func(): … or @decorator\nclass C: …
            for sub in child.children:
                if sub.type in _FUNCTION_TYPES:
                    fn = _make_function_def(sub, source)
                    if fn:
                        results.append(fn)
                elif sub.type in _CLASS_TYPES:
                    _collect_class_methods(sub, source, results)


def extract_functions(path: str, content: str, language: str) -> list[FunctionDef]:
    """
    Parse a source file with tree-sitter and return all top-level functions
    and class methods found in it.

    Only Python, JavaScript, and TypeScript are supported; other languages
    return an empty list without error.

    Args:
        path: Relative file path (used only for context/logging by callers).
        content: Full UTF-8 decoded source text of the file.
        language: Language name as detected by the indexer (e.g. 'Python').

    Returns:
        Ordered list of FunctionDef instances, one per extracted definition.
    """
    if language not in _SUPPORTED_LANGUAGES:
        return []

    try:
        lang = _get_language(language)
    except (ImportError, ValueError):
        return []

    parser = Parser(lang)
    source = content.encode('utf-8')
    tree = parser.parse(source)

    results: list[FunctionDef] = []
    _collect_top_level(tree.root_node, source, results)
    return results
