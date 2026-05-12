"""
模板 API 路由: 查询可用模板。
"""

from fastapi import APIRouter

router = APIRouter(prefix="/templates")


@router.get("/")
async def list_available_templates():
    from core.pipeline.template_loader import list_templates
    return list_templates()


@router.get("/{name}")
async def get_template_detail(name: str):
    from core.pipeline.template_loader import get_template
    template = get_template(name)
    return {
        "name": template.name,
        "description": template.description,
        "phases": [
            {
                "name": p.name,
                "human_gate": p.human_gate,
                "steps": [{"agent": s.agent, "skill": s.skill} for s in p.steps],
            }
            for p in template.phases
        ],
        "scale_config": template.scale_config,
    }
