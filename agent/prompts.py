from pathlib import Path
import frontmatter


def load_prompt(name: str) -> tuple[str, dict]:
    raw = (Path("prompts") / f"{name}.md").read_text()
    post = frontmatter.loads(raw)
    return post.content, post.metadata
