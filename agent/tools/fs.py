from pathlib import Path


def read_file(path: str) -> str:
    return Path(path).read_text()


def write_file(path: str, content: str) -> None:
    Path(path).write_text(content)


def apply_patch(path: str, unified_diff: str) -> str:
    from git import Repo

    repo = Repo(Path(path).resolve().parent)
    return repo.git.apply("--unsafe-paths", "--", "-", input=unified_diff)
