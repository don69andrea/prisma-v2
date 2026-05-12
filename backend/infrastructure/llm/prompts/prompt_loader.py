"""Jinja2-basierter Loader fuer Prompt-Templates.

Templates leben unter `backend/infrastructure/llm/prompts/*.j2`. Loader
wird beim App-Start einmal instanziiert (DI-Singleton) — Templates werden
lazy beim ersten render gecached.
"""

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape


class PromptTemplateLoader:
    def __init__(self, template_dir: Path | None = None) -> None:
        if template_dir is None:
            template_dir = Path(__file__).resolve().parent

        self._env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(default=False),
            undefined=StrictUndefined,
            trim_blocks=False,
            lstrip_blocks=False,
        )

    def render(self, template_name: str, context: dict[str, Any]) -> str:
        """Rendert ein Template mit dem gegebenen Context-Dict.

        Wirft `jinja2.exceptions.TemplateNotFound` bei unbekanntem Template,
        `jinja2.exceptions.UndefinedError` bei fehlenden Slots
        (StrictUndefined).
        """
        template = self._env.get_template(template_name)
        return template.render(**context)
