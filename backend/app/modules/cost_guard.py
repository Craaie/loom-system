import logging

from app.config.settings import settings

logger = logging.getLogger("loom.cost_guard")


class CostLimitExceededError(Exception):
    """当累计成本超过预设阈值时抛出的异常"""



def _resolve_cost_limit(state: dict | None) -> float:
    if not state:
        return settings.MAX_COST_USD
    return float(state.get("cost_limit") or settings.MAX_COST_USD)


def check_cost_circuit_breaker(current_cost: float, session_id: str, cost_limit: float) -> None:
    """检查成本熔断器状态。"""
    if current_cost >= cost_limit:
        logger.warning(
            "Cost Circuit Breaker Triggered for session %s! Current: $%.4f, Limit: $%.2f",
            session_id,
            current_cost,
            cost_limit,
        )
        raise CostLimitExceededError(
            f"Accumulated cost ${current_cost:.4f} exceeded limit ${cost_limit:.2f}. "
            f"Pipeline suspended for session {session_id}."
        )


def update_and_check_cost(state: dict, additional_cost: float) -> float:
    """更新成本并检查熔断。供 Agent 节点调用。"""
    new_total = state.get("cost_accumulator", 0.0) + additional_cost
    cost_limit = _resolve_cost_limit(state)
    check_cost_circuit_breaker(new_total, state.get("session_id", "unknown"), cost_limit)
    return additional_cost
