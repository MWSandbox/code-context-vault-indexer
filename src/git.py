"""Utilities for extracting metadata from the local git repository."""

from __future__ import annotations

import subprocess
from collections import Counter
from pathlib import Path


def _git(*args: str) -> str:
    """Run a git command and return its stdout, stripped of whitespace."""
    result = subprocess.run(
        ['git', *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def get_git_url() -> str:
    """Return the URL of the 'origin' remote for the current repository."""
    return _git('remote', 'get-url', 'origin')


def get_repo_name(git_url: str) -> str:
    """Parse the repo name from an HTTPS or SSH remote URL."""
    # https://github.com/user/repo.git  →  repo
    # git@github.com:user/repo.git      →  repo
    name = git_url.rstrip('/').rsplit('/', 1)[-1].rsplit(':', 1)[-1]
    if name.endswith('.git'):
        name = name[:-4]
    return name


# Maps file extension → canonical language name.
_EXT_TO_LANGUAGE: dict[str, str] = {
    '.py': 'Python',
    '.js': 'JavaScript',
    '.ts': 'TypeScript',
    '.jsx': 'JavaScript',
    '.tsx': 'TypeScript',
    '.java': 'Java',
    '.kt': 'Kotlin',
    '.kts': 'Kotlin',
    '.cs': 'C#',
    '.cpp': 'C++',
    '.cc': 'C++',
    '.cxx': 'C++',
    '.c': 'C',
    '.h': 'C',
    '.hpp': 'C++',
    '.go': 'Go',
    '.rs': 'Rust',
    '.rb': 'Ruby',
    '.php': 'PHP',
    '.swift': 'Swift',
    '.scala': 'Scala',
    '.r': 'R',
    '.R': 'R',
    '.m': 'Objective-C',
    '.sh': 'Shell',
    '.bash': 'Shell',
    '.zsh': 'Shell',
    '.ps1': 'PowerShell',
    '.lua': 'Lua',
    '.ex': 'Elixir',
    '.exs': 'Elixir',
    '.erl': 'Erlang',
    '.hs': 'Haskell',
    '.clj': 'Clojure',
    '.dart': 'Dart',
    '.vim': 'Vim script',
    '.tf': 'HCL',
    '.ml': 'OCaml',
    '.mli': 'OCaml',
}


def get_files_for_language(language: str) -> list[str]:
    """
    Return paths of all git-tracked files whose extension maps to the given
    language. Paths are relative to the repository root.
    """
    extensions = {ext for ext, lang in _EXT_TO_LANGUAGE.items() if lang == language}
    output = _git('ls-files')
    return [path for path in output.splitlines() if Path(path).suffix in extensions]


def get_primary_language() -> str | None:
    """
    Return the primary programming language used in the current repository.

    Lists all files tracked by git and counts occurrences of each mapped
    extension. Returns the language with the highest file count, or None if
    no recognised extension is found.
    """
    output = _git('ls-files')
    counts: Counter[str] = Counter()
    for path in output.splitlines():
        ext = Path(path).suffix.lower() or Path(path).suffix  # preserve case for .R
        # Try exact case first (for .R), then lowercase
        language = _EXT_TO_LANGUAGE.get(Path(path).suffix) or _EXT_TO_LANGUAGE.get(ext)
        if language:
            counts[language] += 1
    if not counts:
        return None
    return counts.most_common(1)[0][0]


def get_default_branch() -> str:
    """
    Return the default branch name for the 'origin' remote.

    First tries to read the local symbolic ref (fast, no network call).
    Falls back to querying the remote directly if the ref is not set.
    """
    # Fast path: read the local tracking ref (set after a clone/fetch)
    try:
        ref = _git('symbolic-ref', 'refs/remotes/origin/HEAD')
        # ref is like "refs/remotes/origin/main"
        return ref.rsplit('/', 1)[-1]
    except subprocess.CalledProcessError:
        pass

    # Fallback: ask the remote directly
    result = subprocess.run(
        ['git', 'remote', 'show', 'origin'],
        capture_output=True,
        text=True,
        check=True,
    )
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if stripped.startswith('HEAD branch:'):
            return stripped.split(':', 1)[1].strip()

    raise RuntimeError('Could not determine default branch from remote.')
