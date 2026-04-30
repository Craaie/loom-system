"""
Physics Engine Agent: 为分镜动作提供物理约束与轨迹预测。
集成 Pymunk 实现 2D 动力学模拟，提升视频生成的连贯性。
"""

import pymunk
import math
from typing import List, Dict, Any, Tuple
import logging

logger = logging.getLogger("loom.physics")

class PhysicsSolver:
    def __init__(self, gravity: float = 980.0):
        self.space = pymunk.Space()
        self.space.gravity = (0, gravity) # 默认向下重力
        self.dt = 1/30.0 # 30 FPS 模拟步长

    def _create_simple_box(self, x: float, y: float, mass: float = 1.0, size: Tuple[float, float] = (50, 100)):
        moment = pymunk.moment_for_box(mass, size)
        body = pymunk.Body(mass, moment)
        body.position = (x, y)
        shape = pymunk.Poly.create_box(body, size)
        shape.friction = 0.5
        self.space.add(body, shape)
        return body

    def simulate_arc(self, start_pos: Tuple[float, float], impulse: Tuple[float, float], duration: float) -> List[Dict[str, float]]:
        """
        模拟抛物线运动（如跳跃、投掷）
        """
        body = self._create_simple_box(start_pos[0], start_pos[1])
        body.apply_impulse_at_local_point(impulse)
        
        trajectory = []
        steps = int(duration / self.dt)
        for i in range(steps):
            self.space.step(self.dt)
            trajectory.append({
                "t": round(i * self.dt, 3),
                "x": round(body.position.x, 2),
                "y": round(body.position.y, 2),
                "vx": round(body.velocity.x, 2),
                "vy": round(body.velocity.y, 2)
            })
        
        return trajectory

    def generate_motion_metadata(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        根据动作指令生成物理元数据
        """
        if action == "jump":
            start = params.get("start", (0, 500))
            force = params.get("force", (500, -1200)) # 向上且向右
            duration = params.get("duration", 2.0)
            traj = self.simulate_arc(start, force, duration)
            return {
                "action": "jump",
                "trajectory": traj,
                "prompt_hint": f"following a parabolic arc with peak at {min(t['y'] for t in traj)}"
            }
        
        if action == "fall":
            start = params.get("start", (500, 0))
            duration = params.get("duration", 1.5)
            traj = self.simulate_arc(start, (0, 0), duration)
            return {
                "action": "fall",
                "trajectory": traj,
                "prompt_hint": "accelerating naturally due to gravity"
            }
            
        return {"action": action, "error": "Action not supported by physics engine"}

# 单例或工厂函数供 Agent 调用
def solve_physics(action: str, **kwargs) -> Dict[str, Any]:
    solver = PhysicsSolver()
    return solver.generate_motion_metadata(action, kwargs)
