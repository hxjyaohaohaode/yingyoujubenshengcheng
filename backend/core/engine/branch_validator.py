from collections import deque
from dataclasses import dataclass, field


@dataclass
class NodeInfo:
    node_id: str
    is_reachable: bool = False
    is_ending: bool = False
    is_dead_end: bool = False
    is_isolated: bool = True
    depth: int = -1
    incoming_paths: int = 0
    outgoing_choices: list[str] = field(default_factory=list)


@dataclass
class ReachabilityReport:
    total_nodes: int = 0
    reachable_nodes: int = 0
    unreachable_nodes: int = 0
    reachable_endings: list[str] = field(default_factory=list)
    unreachable_endings: list[str] = field(default_factory=list)
    dead_ends: list[str] = field(default_factory=list)
    isolated_nodes: list[str] = field(default_factory=list)
    max_depth: int = 0
    node_details: dict[str, NodeInfo] = field(default_factory=dict)
    all_endings_reachable: bool = False


class BranchValidator:
    def validate_reachability(
        self,
        scenes: list[dict],
        choices: list[dict],
        endings: list[str],
    ) -> ReachabilityReport:
        graph: dict[str, list[str]] = {}
        reverse_graph: dict[str, list[str]] = {}
        all_nodes: set[str] = set()
        choice_map: dict[str, dict] = {}

        for scene in scenes:
            scene_id = str(scene.get("id", scene.get("scene_id", scene.get("scene_code", ""))))
            if not scene_id:
                continue
            all_nodes.add(scene_id)
            if scene_id not in graph:
                graph[scene_id] = []
            if scene_id not in reverse_graph:
                reverse_graph[scene_id] = []

        for choice in choices:
            choice_id = str(choice.get("id", ""))
            source_scene = str(choice.get("source_scene", choice.get("section_id", "")))
            target_scene = str(choice.get("branch_target", choice.get("next_scene", "")))

            if not source_scene or not target_scene:
                continue

            all_nodes.add(source_scene)
            all_nodes.add(target_scene)

            if source_scene not in graph:
                graph[source_scene] = []
            if target_scene not in graph:
                graph[target_scene] = []
            if source_scene not in reverse_graph:
                reverse_graph[source_scene] = []
            if target_scene not in reverse_graph:
                reverse_graph[target_scene] = []

            graph[source_scene].append(target_scene)
            reverse_graph[target_scene].append(source_scene)
            choice_map[choice_id] = choice

        ending_set = set(endings)
        for ending in endings:
            if ending not in all_nodes:
                all_nodes.add(ending)
            if ending not in graph:
                graph[ending] = []
            if ending not in reverse_graph:
                reverse_graph[ending] = []

        start_node = self._find_start_node(scenes, all_nodes, graph, reverse_graph)

        reachable = self._bfs_reachability(start_node, graph)
        node_details = self._build_node_details(all_nodes, reachable, graph, reverse_graph, ending_set)

        reachable_endings = [e for e in endings if e in reachable]
        unreachable_endings = [e for e in endings if e not in reachable]

        dead_ends = [
            node_id for node_id, info in node_details.items()
            if info.is_reachable and not info.outgoing_choices and not info.is_ending
        ]

        isolated_nodes = [
            node_id for node_id, info in node_details.items()
            if info.is_isolated
        ]

        max_depth = max((info.depth for info in node_details.values() if info.depth >= 0), default=0)

        report = ReachabilityReport(
            total_nodes=len(all_nodes),
            reachable_nodes=len(reachable),
            unreachable_nodes=len(all_nodes) - len(reachable),
            reachable_endings=reachable_endings,
            unreachable_endings=unreachable_endings,
            dead_ends=dead_ends,
            isolated_nodes=isolated_nodes,
            max_depth=max_depth,
            node_details=node_details,
            all_endings_reachable=len(unreachable_endings) == 0,
        )

        return report

    def _find_start_node(
        self,
        scenes: list[dict],
        all_nodes: set[str],
        graph: dict[str, list[str]],
        reverse_graph: dict[str, list[str]],
    ) -> str:
        for scene in scenes:
            scene_id = str(scene.get("id", scene.get("scene_id", scene.get("scene_code", ""))))
            if scene_id and scene_id in all_nodes and not reverse_graph.get(scene_id):
                return scene_id

        if scenes:
            scene_id = str(scenes[0].get("id", scenes[0].get("scene_id", scenes[0].get("scene_code", ""))))
            if scene_id:
                return scene_id

        if all_nodes:
            return next(iter(all_nodes))

        return ""

    def _bfs_reachability(self, start: str, graph: dict[str, list[str]]) -> set[str]:
        if not start:
            return set()

        visited: set[str] = set()
        queue: deque[str] = deque([start])
        visited.add(start)

        while queue:
            current = queue.popleft()
            for neighbor in graph.get(current, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)

        return visited

    def _build_node_details(
        self,
        all_nodes: set[str],
        reachable: set[str],
        graph: dict[str, list[str]],
        reverse_graph: dict[str, list[str]],
        ending_set: set[str],
    ) -> dict[str, NodeInfo]:
        details: dict[str, NodeInfo] = {}

        start_node = ""
        for node_id in all_nodes:
            if node_id in all_nodes and not reverse_graph.get(node_id):
                start_node = node_id
                break

        depth_map = self._compute_depths(start_node, graph)

        for node_id in all_nodes:
            outgoing = graph.get(node_id, [])
            incoming = reverse_graph.get(node_id, [])

            is_isolated = len(outgoing) == 0 and len(incoming) == 0
            is_dead_end = node_id in reachable and len(outgoing) == 0 and node_id not in ending_set

            details[node_id] = NodeInfo(
                node_id=node_id,
                is_reachable=node_id in reachable,
                is_ending=node_id in ending_set,
                is_dead_end=is_dead_end,
                is_isolated=is_isolated,
                depth=depth_map.get(node_id, -1),
                incoming_paths=len(incoming),
                outgoing_choices=outgoing,
            )

        return details

    def _compute_depths(self, start: str, graph: dict[str, list[str]]) -> dict[str, int]:
        if not start:
            return {}

        depths: dict[str, int] = {start: 0}
        queue: deque[str] = deque([start])

        while queue:
            current = queue.popleft()
            current_depth = depths[current]
            for neighbor in graph.get(current, []):
                if neighbor not in depths:
                    depths[neighbor] = current_depth + 1
                    queue.append(neighbor)

        return depths
