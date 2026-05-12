"""
成本管理: 记录每个项目的 token 用量和费用，支持预算告警。
"""

from datetime import UTC, datetime, timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


class CostManager:
    """成本管理器"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def record_usage(
        self,
        project_id: str,
        agent_name: str,
        intent: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost: float,
    ):
        await self.db.execute(
            text(
                """
                INSERT INTO token_usage
                (project_id, agent_name, intent, model, input_tokens, output_tokens, cost, created_at)
                VALUES (:project_id, :agent_name, :intent, :model, :input_tokens, :output_tokens, :cost, :created_at)
                """
            ),
            {
                "project_id": project_id,
                "agent_name": agent_name,
                "intent": intent,
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost": cost,
                "created_at": datetime.now(UTC),
            },
        )
        await self.db.commit()

    async def get_project_cost(
        self, project_id: str,
        since: Optional[datetime] = None
    ) -> dict:
        if since is None:
            since = datetime.min

        result = await self.db.execute(
            text(
                """
                SELECT
                    SUM(cost) as total_cost,
                    SUM(input_tokens) as total_input_tokens,
                    SUM(output_tokens) as total_output_tokens,
                    COUNT(*) as total_calls
                FROM token_usage
                WHERE project_id = :project_id AND created_at >= :since
                """
            ),
            {"project_id": project_id, "since": since},
        )
        row = result.fetchone()
        if row:
            return {
                "total_cost": float(row[0] or 0),
                "total_input_tokens": int(row[1] or 0),
                "total_output_tokens": int(row[2] or 0),
                "total_calls": int(row[3] or 0),
            }
        return {}

    async def get_cost_breakdown(self, project_id: str) -> list[dict]:
        result = await self.db.execute(
            text(
                """
                SELECT
                    agent_name, model,
                    SUM(cost) as total_cost,
                    SUM(input_tokens) as input_tokens,
                    SUM(output_tokens) as output_tokens,
                    COUNT(*) as call_count
                FROM token_usage
                WHERE project_id = :project_id
                GROUP BY agent_name, model
                ORDER BY total_cost DESC
                """
            ),
            {"project_id": project_id},
        )
        rows = result.fetchall()
        return [
            {
                "agent_name": row[0],
                "model": row[1],
                "total_cost": float(row[2] or 0),
                "input_tokens": int(row[3] or 0),
                "output_tokens": int(row[4] or 0),
                "call_count": int(row[5] or 0),
            }
            for row in rows
        ]

    async def check_budget(self, project_id: str, budget: float) -> dict:
        cost_data = await self.get_project_cost(project_id)
        total = cost_data.get("total_cost", 0)

        return {
            "total_cost": total,
            "budget": budget,
            "remaining": budget - total,
            "usage_percent": (total / budget * 100) if budget > 0 else 0,
            "alert": total > budget * 0.8,
        }
