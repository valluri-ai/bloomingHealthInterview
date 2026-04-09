from __future__ import annotations

from app.domain.models import HierarchyNodeRecord


class HierarchyService:
    def build_path(self, kind: str, dotted_path: str) -> list[HierarchyNodeRecord]:
        segments = [segment for segment in dotted_path.split(".") if segment]
        nodes: list[HierarchyNodeRecord] = []
        parent_path: str | None = None
        for depth, value in enumerate(segments):
            full_path = ".".join(segments[: depth + 1])
            nodes.append(
                HierarchyNodeRecord(
                    node_id=f"{kind}:{full_path}",
                    kind=kind,
                    value=value,
                    full_path=full_path,
                    depth=depth,
                    parent_path=parent_path,
                )
            )
            parent_path = full_path
        return nodes

    def build_lineage(self, dotted_path: str) -> tuple[str, ...]:
        return tuple(node.full_path for node in self.build_path("lineage", dotted_path))

    def prompt_parent(self, prompt_id: str) -> str:
        parts = [segment for segment in prompt_id.split(".") if segment]
        return ".".join(parts[:-1]) if len(parts) > 1 else prompt_id

    def seed_layer_taxonomy(self) -> list[HierarchyNodeRecord]:
        return self.build_path("layer_path", "org.os.team.engine.directive")

    def resolve_layer_value(self, layer_value: str) -> str:
        canonical = {
            "org": "org",
            "os": "org.os",
            "team": "org.os.team",
            "engine": "org.os.team.engine",
            "directive": "org.os.team.engine.directive",
        }
        return canonical.get(layer_value, layer_value)
