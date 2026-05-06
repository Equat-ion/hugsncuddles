from pathlib import Path


def read_file(path: str) -> str:
    return Path(path).read_text()


def write_file(path: str, content: str) -> None:
    Path(path).write_text(content)


def _validate_patch_paths(unified_diff: str) -> None:
    for line in unified_diff.splitlines():
        if line.startswith("*** Update File:") or line.startswith("*** Add File:"):
            path = line.split(":", 1)[1].strip()
            if path.startswith("/") or ".." in Path(path).parts:
                raise ValueError("patch path must be relative and non-traversing")


def apply_patch(path: str, unified_diff: str) -> str:
    from git import Repo

    _validate_patch_paths(unified_diff)
    repo = Repo(Path(path).resolve().parent)
    return repo.git.apply("--", "-", input=unified_diff)
