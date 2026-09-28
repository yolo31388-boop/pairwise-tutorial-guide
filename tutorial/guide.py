"""新手引导与教程系统 - 含6个bug"""
from dataclasses import dataclass, field

@dataclass
class GuideStep:
    sid: str
    description: str
    action_type: str  # click/equip/learn/complete
    target: str
    completed: bool = False
    highlight_x: float = 0
    highlight_y: float = 0

class Tutorial:
    def __init__(self):
        self.steps: list[GuideStep] = []
        self.current_step: int = 0
        self.ui_scale: float = 1.0
        self.can_skip: bool = False  # bug3: 不可跳过
        self.overlay_active: bool = False
        self.rewards_claimed: set = set()
        self.player_state: dict = {}  # 装备、技能等实际状态

    def add_step(self, step: GuideStep):
        self.steps.append(step)

    def complete_step(self, sid: str, action_result: dict) -> bool:
        # bug1: 只检查是否点击，不验证实际结果
        for i, s in enumerate(self.steps):
            if s.sid == sid:
                s.completed = True
                if i == self.current_step:
                    self.current_step += 1
                return True
        return False

    def get_highlight_position(self, step: GuideStep) -> tuple[float, float]:
        # bug2: 不考虑UI缩放
        return (step.highlight_x, step.highlight_y)

    def skip_tutorial(self) -> bool:
        # bug3: 不可跳过
        return False

    def update_objective(self) -> str:
        # bug4: 目标不实时更新
        if self.current_step < len(self.steps):
            return self.steps[self.current_step].description
        return "完成"

    def claim_reward(self, step_index: int) -> dict:
        # bug5: 跳过引导也能领奖励
        reward = {"gold": 100, "item": "newbie_sword"}
        return reward

    def finish_tutorial(self):
        # bug6: 结束不清理遮罩
        self.current_step = len(self.steps)
        # overlay_active没设为False
