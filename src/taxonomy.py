"""Load and query the tag taxonomy (``lib/taxonomy.json``).

The taxonomy is the source of truth for what tags exist, whether a section is
single- or multi-select, and whether unknown tags should be flagged. The UI is
generated from whatever sections this file declares, so adding a section to the
JSON surfaces it in the app with no code changes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


class TaxonomyError(Exception):
    """Raised when the taxonomy file is missing or malformed."""


@dataclass
class Section:
    """One annotation field and its allowed tags."""

    name: str
    label: str
    selection: str  # "single" or "multi"
    validated: bool
    tags: dict[str, str] = field(default_factory=dict)
    # Ordered sub-groups: list of (group_name, [tag codes]). Empty -> flat.
    groups: list[tuple[str, list[str]]] = field(default_factory=list)

    @property
    def is_multi(self) -> bool:
        return self.selection == "multi"

    def has(self, code: str) -> bool:
        return code in self.tags

    def describe(self, code: str) -> str:
        return self.tags.get(code, "")

    def options(self) -> list[tuple[str, str]]:
        """Return ``[(code, description)]`` sorted by code, for the picker."""
        return sorted(self.tags.items(), key=lambda kv: kv[0])

    def grouped_options(self) -> list[tuple[str, list[tuple[str, str]]]]:
        """Return ``[(group_name, [(code, description)])]`` following taxonomy
        sub-groups. Tags not assigned to any group fall under ``"Other"``. When
        the section declares no groups, a single unnamed group is returned.
        """
        if not self.groups:
            return [("", self.options())]
        result: list[tuple[str, list[tuple[str, str]]]] = []
        used: set[str] = set()
        for name, codes in self.groups:
            opts = [(c, self.tags[c]) for c in codes if c in self.tags]
            used.update(codes)
            if opts:
                result.append((name, opts))
        leftover = [(c, d) for c, d in self.options() if c not in used]
        if leftover:
            result.append(("Other", leftover))
        return result

    def unknown(self, values) -> list[str]:
        """Tags present in ``values`` that are not in the taxonomy.

        Always empty for non-validated (freeform) sections.
        """
        if not self.validated:
            return []
        if isinstance(values, str):
            values = [values]
        return [v for v in (values or []) if v not in self.tags]


@dataclass
class Taxonomy:
    sections: dict[str, Section]

    def get(self, name: str) -> Section | None:
        return self.sections.get(name)

    def __iter__(self):
        return iter(self.sections.values())


def load_taxonomy(path: str | Path) -> Taxonomy:
    """Load ``taxonomy.json`` into a :class:`Taxonomy`.

    Raises :class:`TaxonomyError` with a human-readable message on any problem so
    callers can show a clear startup dialog.
    """
    path = Path(path)
    if not path.exists():
        raise TaxonomyError(f"Taxonomy file not found: {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise TaxonomyError(f"Could not read taxonomy file {path}: {exc}") from exc

    sections_raw = raw.get("sections")
    if not isinstance(sections_raw, dict) or not sections_raw:
        raise TaxonomyError("Taxonomy file has no 'sections' object.")

    sections: dict[str, Section] = {}
    for name, spec in sections_raw.items():
        if not isinstance(spec, dict):
            raise TaxonomyError(f"Section '{name}' must be an object.")
        selection = spec.get("selection", "multi")
        if selection not in ("single", "multi"):
            raise TaxonomyError(
                f"Section '{name}' has invalid selection '{selection}'."
            )
        tags = spec.get("tags") or {}
        if not isinstance(tags, dict):
            raise TaxonomyError(f"Section '{name}' tags must be an object.")
        groups: list[tuple[str, list[str]]] = []
        for grp in spec.get("groups") or []:
            if isinstance(grp, dict) and "name" in grp:
                groups.append((str(grp["name"]), [str(t) for t in grp.get("tags", [])]))
        sections[name] = Section(
            name=name,
            label=spec.get("label", name),
            selection=selection,
            validated=bool(spec.get("validated", True)),
            tags={str(k): str(v) for k, v in tags.items()},
            groups=groups,
        )
    return Taxonomy(sections=sections)
