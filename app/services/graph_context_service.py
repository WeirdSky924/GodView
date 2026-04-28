"""关系图上下文读取服务。"""

import logging
import inspect
from typing import Any, Dict, List, Optional, Tuple

from app.models.graph_context import (
    GraphContextOptions,
    GraphContextResponse,
    GraphContextSource,
    GraphEdge,
    GraphNode,
)

logger = logging.getLogger(__name__)


class GraphContextService:
    """从 NebulaGraph 读取局部关系图，并在不可用时回退 Postgres。"""

    def __init__(self, postgres_db: Any, nebula_db: Any = None):
        self.postgres_db = postgres_db
        self.nebula_db = nebula_db

    async def get_character_relationships(
        self,
        character_id: str,
        project_id: Optional[str] = None,
        allow_fallback: bool = True,
    ) -> List[Dict[str, Any]]:
        """返回兼容旧 API 的角色关系列表。"""
        context = await self.get_local_graph_context(
            "character",
            character_id,
            project_id=project_id,
            options=GraphContextOptions(
                include_world=False,
                include_region=False,
                include_hooks=False,
                allow_fallback=allow_fallback,
            ),
        )
        return context.relationships

    async def get_local_graph_context(
        self,
        anchor_type: str,
        anchor_id: str,
        project_id: Optional[str] = None,
        options: Optional[GraphContextOptions] = None,
    ) -> GraphContextResponse:
        """获取 anchor 周边的紧凑图上下文。"""
        opts = options or GraphContextOptions()
        warnings: List[str] = []

        anchor_data = await self._load_anchor_from_postgres(anchor_type, anchor_id)
        if not anchor_data:
            return GraphContextResponse(
                source=GraphContextSource.UNAVAILABLE,
                partial=True,
                warnings=[f"{anchor_type} 不存在"],
                metadata={"anchor_type": anchor_type, "anchor_id": anchor_id},
            )

        if project_id and anchor_data.get("project_id") and str(anchor_data.get("project_id")) != str(project_id):
            return GraphContextResponse(
                source=GraphContextSource.UNAVAILABLE,
                partial=True,
                warnings=["anchor 不属于指定项目"],
                metadata={"anchor_type": anchor_type, "anchor_id": anchor_id, "project_id": project_id},
            )

        effective_world_id = await self._resolve_effective_world_id(anchor_type, anchor_id, anchor_data, opts)
        if opts.world_id and project_id and hasattr(self.postgres_db, "assert_world_belongs_to_project"):
            try:
                belongs = await self.postgres_db.assert_world_belongs_to_project(str(opts.world_id), str(project_id))
                if not belongs:
                    return GraphContextResponse(
                        source=GraphContextSource.UNAVAILABLE,
                        partial=True,
                        warnings=["world_id 不属于指定项目"],
                        metadata={"anchor_type": anchor_type, "anchor_id": anchor_id, "project_id": project_id, "world_id": opts.world_id},
                    )
            except Exception as exc:
                logger.warning("校验 graph_context world 归属失败: %s", exc)

        anchor = self._entity_to_node(anchor_type, anchor_data)
        if opts.source != GraphContextSource.POSTGRES:
            nebula_context = await self._load_from_nebula(anchor_type, anchor_id, anchor, opts)
            if nebula_context and (nebula_context.nodes or nebula_context.edges or not opts.allow_fallback):
                if nebula_context.partial and opts.allow_fallback:
                    fallback = await self._load_postgres_fallback(anchor_type, anchor_data, opts, effective_world_id)
                    return self._merge_contexts(nebula_context, fallback, [*nebula_context.warnings, "NebulaGraph 结果不完整，已合并 Postgres fallback"])
                nebula_context.metadata["world_id"] = effective_world_id
                return nebula_context
            if opts.source == GraphContextSource.NEBULA and not opts.allow_fallback:
                return GraphContextResponse(
                    source=GraphContextSource.UNAVAILABLE,
                    partial=True,
                    warnings=["NebulaGraph 未返回可用图上下文"],
                    anchor=anchor,
                    metadata={"anchor_type": anchor_type, "anchor_id": anchor_id, "world_id": effective_world_id},
                )
            warnings.append("NebulaGraph 未返回可用图上下文，使用 Postgres fallback")

        if opts.allow_fallback or opts.source == GraphContextSource.POSTGRES:
            fallback = await self._load_postgres_fallback(anchor_type, anchor_data, opts, effective_world_id)
            fallback.warnings = [*warnings, *fallback.warnings]
            return fallback

        return GraphContextResponse(
            source=GraphContextSource.UNAVAILABLE,
            partial=True,
            warnings=[*warnings, "fallback 已禁用"],
            anchor=anchor,
            metadata={"anchor_type": anchor_type, "anchor_id": anchor_id},
        )

    async def _resolve_effective_world_id(
        self,
        anchor_type: str,
        anchor_id: str,
        anchor_data: Dict[str, Any],
        options: GraphContextOptions,
    ) -> Optional[str]:
        if options.world_id:
            return str(options.world_id)
        if anchor_data.get("world_id"):
            return str(anchor_data.get("world_id"))
        if anchor_type == "world":
            return str(anchor_id)
        return None

    async def _load_anchor_from_postgres(self, anchor_type: str, anchor_id: str) -> Optional[Dict[str, Any]]:
        if anchor_type == "character" and hasattr(self.postgres_db, "get_character"):
            return await self.postgres_db.get_character(anchor_id)
        if anchor_type == "world" and hasattr(self.postgres_db, "get_world"):
            return await self.postgres_db.get_world(anchor_id)
        if anchor_type == "region" and hasattr(self.postgres_db, "get_region"):
            return await self.postgres_db.get_region(anchor_id)
        if anchor_type == "hook" and hasattr(self.postgres_db, "get_hook"):
            return await self.postgres_db.get_hook(anchor_id)
        return None

    async def _load_from_nebula(
        self,
        anchor_type: str,
        anchor_id: str,
        anchor: GraphNode,
        options: GraphContextOptions,
    ) -> Optional[GraphContextResponse]:
        if not self.nebula_db:
            return None
        try:
            if anchor_type == "character" and hasattr(self.nebula_db, "get_local_character_graph"):
                raw = await self.nebula_db.get_local_character_graph(
                    anchor_id,
                    depth=options.depth,
                    max_nodes=options.max_nodes,
                )
                return self._normalize_nebula_result(anchor, raw, options)
            if anchor_type == "character" and hasattr(self.nebula_db, "get_relationships"):
                relationships = await self.nebula_db.get_relationships(anchor_id)
                nodes = [anchor]
                edges: List[GraphEdge] = []
                for index, rel in enumerate(relationships[: options.max_nodes - 1]):
                    target_id = str(rel.get("target_id") or rel.get("target_name") or f"relationship_{index}")
                    nodes.append(GraphNode(
                        id=target_id,
                        type="character",
                        name=rel.get("target_name") or target_id,
                        summary=rel.get("type"),
                        properties=rel,
                    ))
                    edges.append(GraphEdge(
                        source=anchor.id,
                        target=target_id,
                        type="knows",
                        label=rel.get("type"),
                        properties=rel,
                    ))
                return self._build_response(GraphContextSource.NEBULA, anchor, nodes, edges, relationships, [])
        except Exception as exc:
            logger.warning("NebulaGraph 图上下文读取失败: %s", exc)
            return GraphContextResponse(
                source=GraphContextSource.NEBULA,
                partial=True,
                warnings=[f"NebulaGraph 图上下文读取失败: {exc}"],
                anchor=anchor,
                metadata={"anchor_type": anchor_type, "anchor_id": anchor_id},
            )
        return None

    def _normalize_nebula_result(
        self,
        anchor: GraphNode,
        raw: Dict[str, Any],
        options: GraphContextOptions,
    ) -> GraphContextResponse:
        warnings = list(raw.get("warnings") or [])
        nodes = [anchor]
        seen = {anchor.id}
        for node_data in raw.get("nodes") or raw.get("vertices") or []:
            node = self._raw_node_to_graph_node(node_data)
            if node.id not in seen:
                nodes.append(node)
                seen.add(node.id)
            if len(nodes) >= options.max_nodes:
                break

        edges = [
            self._raw_edge_to_graph_edge(edge)
            for edge in (raw.get("edges") or [])
            if edge
        ]
        relationships = raw.get("relationships") or self._relationships_from_edges(anchor.id, nodes, edges)
        partial = bool(raw.get("partial")) or (not nodes and not edges)
        return self._build_response(GraphContextSource.NEBULA, anchor, nodes, edges, relationships, warnings, partial=partial)

    async def _load_postgres_fallback(
        self,
        anchor_type: str,
        anchor_data: Dict[str, Any],
        options: GraphContextOptions,
        world_id: Optional[str] = None,
    ) -> GraphContextResponse:
        if anchor_type != "character":
            anchor = self._entity_to_node(anchor_type, anchor_data)
            nodes: Dict[str, GraphNode] = {anchor.id: anchor}
            edges: List[GraphEdge] = []
            relationships: List[Dict[str, Any]] = []
            project_id = anchor_data.get("project_id")

            if anchor_type == "world":
                world_id = str(anchor_data.get("id"))
                if options.include_world:
                    await self._add_parent_world_fallback(anchor_data, nodes, edges)
                if options.include_region:
                    await self._add_world_regions_fallback(anchor_data, nodes, edges, options.max_nodes)
                if options.include_hooks:
                    await self._add_scoped_hooks_fallback(
                        project_id,
                        world_id,
                        nodes,
                        edges,
                        options.max_nodes,
                        source_id=anchor.id,
                        include_inherited=options.include_inherited,
                    )
            elif anchor_type == "region":
                world_id = world_id or (str(anchor_data.get("world_id")) if anchor_data.get("world_id") else None)
                if options.include_world and world_id:
                    await self._add_world_node_by_id(world_id, nodes, edges, source_id=anchor.id, edge_type="located_in_world", label="所属世界")
                if options.include_hooks:
                    await self._add_scoped_hooks_fallback(
                        project_id,
                        world_id,
                        nodes,
                        edges,
                        options.max_nodes,
                        source_id=anchor.id,
                        related_location_id=anchor.id,
                        include_inherited=options.include_inherited,
                    )
            elif anchor_type == "hook":
                world_id = world_id or (str(anchor_data.get("world_id")) if anchor_data.get("world_id") else None)
                if options.include_world and world_id:
                    await self._add_world_node_by_id(world_id, nodes, edges, source_id=anchor.id, edge_type="scoped_to_world", label="所属世界")
                await self._add_hook_related_characters(anchor_data, nodes, edges, options.max_nodes)

            limited_nodes = list(nodes.values())[: options.max_nodes]
            allowed_ids = {node.id for node in limited_nodes}
            limited_edges = [edge for edge in edges if edge.source in allowed_ids and edge.target in allowed_ids]
            return self._build_response(GraphContextSource.POSTGRES, anchor, limited_nodes, limited_edges, relationships, [])

        anchor = self._entity_to_node("character", anchor_data)
        nodes: Dict[str, GraphNode] = {anchor.id: anchor}
        edges: List[GraphEdge] = []
        relationships: List[Dict[str, Any]] = []

        await self._add_character_relationship_fallback(anchor_data, nodes, edges, relationships, options.max_nodes)
        if options.include_world:
            await self._add_world_fallback(anchor_data, nodes, edges, world_id)
        if options.include_region:
            await self._add_region_fallback(anchor_data, nodes, edges, world_id)
        if options.include_hooks:
            await self._add_hook_fallback(anchor_data, nodes, edges, options.max_nodes, world_id, options.include_inherited)

        limited_nodes = list(nodes.values())[: options.max_nodes]
        allowed_ids = {node.id for node in limited_nodes}
        limited_edges = [edge for edge in edges if edge.source in allowed_ids and edge.target in allowed_ids]
        return self._build_response(GraphContextSource.POSTGRES, anchor, limited_nodes, limited_edges, relationships, [])

    async def _add_character_relationship_fallback(
        self,
        character: Dict[str, Any],
        nodes: Dict[str, GraphNode],
        edges: List[GraphEdge],
        relationships: List[Dict[str, Any]],
        max_nodes: int,
    ) -> None:
        anchor_id = str(character.get("id"))
        key_relationships = _as_dict(character.get("key_relationships"))
        for target_id, relation in key_relationships.items():
            if len(nodes) >= max_nodes:
                break
            target = await self.postgres_db.get_character(str(target_id)) if hasattr(self.postgres_db, "get_character") else None
            node = self._entity_to_node("character", target or {"id": str(target_id), "name": str(target_id), "description": ""})
            nodes[node.id] = node
            relation_text = str(relation or "related")
            edge = GraphEdge(source=anchor_id, target=node.id, type="knows", label=relation_text, properties={"relationship_type": relation_text})
            edges.append(edge)
            relationships.append({
                "target_id": node.id,
                "target_name": node.name or node.id,
                "type": relation_text,
                "strength": 0.5,
                "source": "postgres",
            })

        project_id = character.get("project_id")
        if hasattr(self.postgres_db, "get_all_characters") and project_id and len(nodes) < max_nodes:
            for other in await self.postgres_db.get_all_characters(project_id=project_id, limit=500):
                other_id = str(other.get("id"))
                if other_id == anchor_id or other_id in nodes:
                    continue
                reverse_relationships = _as_dict(other.get("key_relationships"))
                if anchor_id not in {str(key) for key in reverse_relationships.keys()}:
                    continue
                relation_text = str(reverse_relationships.get(anchor_id) or reverse_relationships.get(str(anchor_id)) or "related")
                node = self._entity_to_node("character", other)
                nodes[node.id] = node
                edges.append(GraphEdge(source=node.id, target=anchor_id, type="knows", label=relation_text, properties={"relationship_type": relation_text}))
                relationships.append({
                    "target_id": node.id,
                    "target_name": node.name or node.id,
                    "type": relation_text,
                    "strength": 0.5,
                    "direction": "incoming",
                    "source": "postgres",
                })
                if len(nodes) >= max_nodes:
                    break

    async def _add_world_fallback(
        self,
        character: Dict[str, Any],
        nodes: Dict[str, GraphNode],
        edges: List[GraphEdge],
        world_id: Optional[str] = None,
    ) -> None:
        target_world_id = world_id or character.get("world_id")
        if not target_world_id:
            return
        await self._add_world_node_by_id(str(target_world_id), nodes, edges, source_id=str(character.get("id")), edge_type="belongs_to", label="所属世界")

    async def _add_world_node_by_id(
        self,
        world_id: str,
        nodes: Dict[str, GraphNode],
        edges: List[GraphEdge],
        source_id: str,
        edge_type: str,
        label: str,
    ) -> Optional[Dict[str, Any]]:
        if not world_id or not hasattr(self.postgres_db, "get_world"):
            return None
        world = await self.postgres_db.get_world(str(world_id))
        if not world:
            return None
        node = self._entity_to_node("world", world)
        nodes[node.id] = node
        edges.append(GraphEdge(source=source_id, target=node.id, type=edge_type, label=label))
        return world

    async def _add_parent_world_fallback(self, world: Dict[str, Any], nodes: Dict[str, GraphNode], edges: List[GraphEdge]) -> None:
        parent_world_id = world.get("parent_world_id")
        if not parent_world_id:
            return
        await self._add_world_node_by_id(
            str(parent_world_id),
            nodes,
            edges,
            source_id=str(world.get("id")),
            edge_type="inherits_from",
            label="父级世界观",
        )

    async def _add_region_fallback(
        self,
        character: Dict[str, Any],
        nodes: Dict[str, GraphNode],
        edges: List[GraphEdge],
        world_id: Optional[str] = None,
    ) -> None:
        region_id = character.get("current_region_id")
        if not region_id or not hasattr(self.postgres_db, "get_region"):
            return
        region = await self.postgres_db.get_region(str(region_id))
        if not region:
            return
        if world_id and region.get("world_id") and str(region.get("world_id")) != str(world_id):
            return
        node = self._entity_to_node("region", region)
        nodes[node.id] = node
        edges.append(GraphEdge(
            source=str(character.get("id")),
            target=node.id,
            type="located_in",
            label=character.get("current_location_reason") or "当前位置",
        ))

    async def _add_world_regions_fallback(
        self,
        world: Dict[str, Any],
        nodes: Dict[str, GraphNode],
        edges: List[GraphEdge],
        max_nodes: int,
    ) -> None:
        if not hasattr(self.postgres_db, "get_regions_by_world"):
            return
        world_id = str(world.get("id"))
        for region in await self.postgres_db.get_regions_by_world(world_id):
            if len(nodes) >= max_nodes:
                break
            node = self._entity_to_node("region", region)
            nodes[node.id] = node
            edges.append(GraphEdge(source=node.id, target=world_id, type="located_in_world", label="属于世界"))

    async def _add_hook_fallback(
        self,
        character: Dict[str, Any],
        nodes: Dict[str, GraphNode],
        edges: List[GraphEdge],
        max_nodes: int,
        world_id: Optional[str] = None,
        include_inherited: bool = True,
    ) -> None:
        character_id = str(character.get("id"))
        project_id = character.get("project_id")
        await self._add_scoped_hooks_fallback(
            project_id,
            world_id or (str(character.get("world_id")) if character.get("world_id") else None),
            nodes,
            edges,
            max_nodes,
            source_id=character_id,
            character_id=character_id,
            include_inherited=include_inherited,
        )

    async def _add_scoped_hooks_fallback(
        self,
        project_id: Optional[str],
        world_id: Optional[str],
        nodes: Dict[str, GraphNode],
        edges: List[GraphEdge],
        max_nodes: int,
        source_id: str,
        character_id: Optional[str] = None,
        related_location_id: Optional[str] = None,
        include_inherited: bool = True,
    ) -> None:
        if not hasattr(self.postgres_db, "get_all_hooks"):
            return
        get_all_hooks = self.postgres_db.get_all_hooks
        hook_kwargs = {
            "project_id": project_id,
            "limit": 200,
        }
        try:
            signature = inspect.signature(get_all_hooks)
            if "world_id" in signature.parameters:
                hook_kwargs["world_id"] = world_id
            if "include_inherited" in signature.parameters:
                hook_kwargs["include_inherited"] = bool(world_id and include_inherited)
        except (TypeError, ValueError):
            hook_kwargs.update({
                "world_id": world_id,
                "include_inherited": bool(world_id and include_inherited),
            })
        hooks = await get_all_hooks(**hook_kwargs)
        for hook in hooks:
            if len(nodes) >= max_nodes:
                break
            related_characters = [str(item) for item in _as_list(hook.get("related_characters"))]
            related_locations = [str(item) for item in _as_list(hook.get("related_locations"))]
            hook_character_id = str(hook.get("character_id")) if hook.get("character_id") else None
            if character_id and character_id not in related_characters and hook_character_id != character_id:
                continue
            if related_location_id and related_location_id not in related_locations:
                continue
            node = self._entity_to_node("hook", hook)
            nodes[node.id] = node
            if character_id:
                edges.append(GraphEdge(source=node.id, target=source_id, type="involves_character", label="相关角色"))
            elif related_location_id:
                edges.append(GraphEdge(source=node.id, target=source_id, type="involves_location", label="相关地点"))
            else:
                edges.append(GraphEdge(source=node.id, target=source_id, type="scoped_to", label="作用域伏笔"))

    async def _add_hook_related_characters(
        self,
        hook: Dict[str, Any],
        nodes: Dict[str, GraphNode],
        edges: List[GraphEdge],
        max_nodes: int,
    ) -> None:
        if not hasattr(self.postgres_db, "get_character"):
            return
        related_ids = [str(item) for item in _as_list(hook.get("related_characters"))]
        if hook.get("character_id"):
            related_ids.append(str(hook.get("character_id")))
        for character_id in dict.fromkeys(related_ids):
            if len(nodes) >= max_nodes:
                break
            character = await self.postgres_db.get_character(character_id)
            if not character:
                continue
            node = self._entity_to_node("character", character)
            nodes[node.id] = node
            edges.append(GraphEdge(source=str(hook.get("id")), target=node.id, type="involves_character", label="相关角色"))

    def _merge_contexts(
        self,
        primary: GraphContextResponse,
        fallback: GraphContextResponse,
        warnings: List[str],
    ) -> GraphContextResponse:
        nodes: Dict[str, GraphNode] = {node.id: node for node in fallback.nodes}
        nodes.update({node.id: node for node in primary.nodes})
        edge_keys = set()
        edges: List[GraphEdge] = []
        for edge in [*primary.edges, *fallback.edges]:
            key = (edge.source, edge.target, edge.type, edge.label)
            if key in edge_keys:
                continue
            edge_keys.add(key)
            edges.append(edge)
        relationships = primary.relationships or fallback.relationships
        return self._build_response(
            GraphContextSource.MIXED,
            primary.anchor or fallback.anchor,
            list(nodes.values()),
            edges,
            relationships,
            warnings,
            partial=True,
        )

    def _entity_to_node(self, entity_type: str, entity: Dict[str, Any]) -> GraphNode:
        entity_id = str(entity.get("id") or entity.get(f"{entity_type}_id") or "")
        if entity_type == "hook":
            name = entity.get("title") or entity.get("name") or entity_id
            summary = entity.get("description") or entity.get("plant_context") or entity.get("resolution_hint")
        else:
            name = entity.get("name") or entity.get("title") or entity_id
            summary = entity.get("description") or entity.get("summary") or entity.get("background_story") or entity.get("background")
        return GraphNode(id=entity_id, type=entity_type, name=name, summary=summary, properties=_compact_properties(entity))

    def _raw_node_to_graph_node(self, node: Dict[str, Any]) -> GraphNode:
        properties = _as_dict(node.get("properties")) or {k: v for k, v in node.items() if k not in {"id", "type", "tag", "name", "summary"}}
        node_type = str(node.get("type") or node.get("tag") or properties.get("type") or "unknown")
        node_id = str(node.get("id") or node.get("vid") or properties.get("id") or properties.get("name") or "")
        return GraphNode(
            id=node_id,
            type=node_type,
            name=node.get("name") or properties.get("name") or properties.get("title") or node_id,
            summary=node.get("summary") or properties.get("description") or properties.get("status"),
            properties=properties,
        )

    def _raw_edge_to_graph_edge(self, edge: Dict[str, Any]) -> GraphEdge:
        properties = _as_dict(edge.get("properties")) or {k: v for k, v in edge.items() if k not in {"source", "src", "target", "dst", "type", "edge", "label"}}
        return GraphEdge(
            source=str(edge.get("source") or edge.get("src") or ""),
            target=str(edge.get("target") or edge.get("dst") or ""),
            type=str(edge.get("type") or edge.get("edge") or "related"),
            label=edge.get("label") or properties.get("relationship_type") or properties.get("role") or properties.get("context"),
            properties=properties,
        )

    def _relationships_from_edges(self, anchor_id: str, nodes: List[GraphNode], edges: List[GraphEdge]) -> List[Dict[str, Any]]:
        node_by_id = {node.id: node for node in nodes}
        relationships = []
        for edge in edges:
            if edge.type != "knows" or edge.source != anchor_id:
                continue
            target = node_by_id.get(edge.target)
            relationships.append({
                "target_id": edge.target,
                "target_name": target.name if target else edge.target,
                "type": edge.label or edge.properties.get("relationship_type") or "related",
                "strength": edge.properties.get("strength", 0.0),
                "source": "nebula",
            })
        return relationships

    def _build_response(
        self,
        source: GraphContextSource,
        anchor: Optional[GraphNode],
        nodes: List[GraphNode],
        edges: List[GraphEdge],
        relationships: List[Dict[str, Any]],
        warnings: List[str],
        partial: bool = False,
    ) -> GraphContextResponse:
        summary = self._build_summary(anchor, nodes, edges, relationships)
        return GraphContextResponse(
            source=source,
            partial=partial,
            warnings=warnings,
            anchor=anchor,
            nodes=nodes,
            edges=edges,
            relationships=relationships,
            summary=summary,
            metadata={"node_count": len(nodes), "edge_count": len(edges), "relationship_count": len(relationships)},
        )

    def _build_summary(
        self,
        anchor: Optional[GraphNode],
        nodes: List[GraphNode],
        edges: List[GraphEdge],
        relationships: List[Dict[str, Any]],
    ) -> str:
        if not anchor:
            return ""
        parts = [f"{anchor.name or anchor.id} 的局部关系图包含 {len(nodes)} 个节点、{len(edges)} 条关系"]
        if relationships:
            names = [str(item.get("target_name") or item.get("target_id")) for item in relationships[:5]]
            parts.append(f"直接角色关系：{', '.join(names)}")
        return "；".join(parts)


def _as_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _as_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def _compact_properties(entity: Dict[str, Any]) -> Dict[str, Any]:
    allowed = {
        "id", "name", "title", "description", "summary", "role", "status", "world_id",
        "project_id", "current_region_id", "current_location", "current_location_reason",
        "hook_type", "priority", "state", "state_summary", "region_type", "terrain_type",
        "importance_tier", "plot_priority",
    }
    return {key: value for key, value in entity.items() if key in allowed and value is not None}
