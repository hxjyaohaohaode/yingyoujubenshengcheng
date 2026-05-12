"""
模板加载器: 从 YAML 文件加载编排模板。
"""

try:
    import yaml
except ImportError:
    from typing import Any
    # yaml stubs fallback for type checking without source files
    class yaml:
        @staticmethod
        def safe_load(stream: Any) -> Any: ...
from pathlib import Path
from .template import PipelineTemplate, Phase, Step

TEMPLATE_REGISTRY: dict[str, PipelineTemplate] = {}

TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"


def load_templates():
    for yaml_file in TEMPLATES_DIR.glob("*.yaml"):
        with open(yaml_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        phases = []
        for phase_data in data.get("phases", []):
            steps = []
            for step_data in phase_data.get("steps", []):
                steps.append(Step(
                    agent=step_data["agent"],
                    skill=step_data["skill"],
                    input_from=step_data.get("input_from", []),
                    output_to=step_data.get("output_to", "next_step"),
                    condition=step_data.get("condition"),
                    cost_profile=step_data.get("cost_profile", "balanced"),
                    timeout=step_data.get("timeout", 600),
                ))
            phases.append(Phase(
                name=phase_data["name"],
                steps=steps,
                human_gate=phase_data.get("human_gate", False),
                max_parallel=phase_data.get("max_parallel", 1),
                repeat_until=phase_data.get("repeat_until"),
            ))

        template = PipelineTemplate(
            name=data["name"],
            description=data.get("description", ""),
            phases=phases,
            scale_config=data.get("scale_config", {}),
        )
        TEMPLATE_REGISTRY[template.name] = template


def get_template(name: str) -> PipelineTemplate:
    if not TEMPLATE_REGISTRY:
        load_templates()
    template = TEMPLATE_REGISTRY.get(name)
    if not template:
        raise ValueError(f"Unknown template: {name}. Available: {list(TEMPLATE_REGISTRY.keys())}")
    return template


def list_templates() -> list[dict]:
    if not TEMPLATE_REGISTRY:
        load_templates()
    return [
        {"name": t.name, "description": t.description, "phases": len(t.phases)}
        for t in TEMPLATE_REGISTRY.values()
    ]
