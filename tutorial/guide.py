"""新手引导与教程系统。

修复点：
1. 步骤完成校验实际操作结果（装备是否穿上、技能是否学会等），而非仅看点击。
2. 高亮框坐标按 UI 缩放比例动态计算。
3. 引导可跳过；首次进入提示是否观看，跳过不影响后续功能、不发奖励。
4. 任务目标实时监听玩家状态变化，满足条件立即推进与更新。
5. 教程奖励仅在对应步骤真正完成后才可领取，跳过/未完成/重复领取均被拒绝。
6. 引导结束时清理全部遮罩、高亮框与事件监听。
"""
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
        self.can_skip: bool = True
        self.overlay_active: bool = False
        self.rewards_claimed: set = set()
        self.player_state: dict = {}  # 装备、技能等实际状态
        self.skipped: bool = False
        self.finished: bool = False
        self.tutorial_seen: bool = False  # 是否已见过首次进入提示
        self.active_highlights: list = []  # 当前显示的高亮框
        self.listeners: list = []  # (event, callback) 事件监听

    # ---------- 步骤配置 ----------

    def add_step(self, step: GuideStep):
        self.steps.append(step)

    # ---------- bug1: 校验实际操作结果 ----------

    def _validate_result(self, step: GuideStep, action_result: dict) -> bool:
        """根据步骤类型验证操作是否真正生效，点击事件本身不算完成。"""
        action_result = action_result or {}
        action_type = step.action_type
        if action_type == "click":
            return bool(action_result.get("clicked"))
        if action_type == "equip":
            equipped = self.player_state.get("equipped", [])
            return bool(action_result.get("equipped")) or step.target in equipped
        if action_type == "learn":
            learned = self.player_state.get("skills", [])
            return bool(action_result.get("learned")) or step.target in learned
        if action_type == "complete":
            return bool(action_result.get("completed"))
        return False

    def _apply_state(self, step: GuideStep, action_result: dict):
        """把已验证的操作结果同步进玩家实际状态。"""
        action_result = action_result or {}
        if step.action_type == "equip" and action_result.get("equipped"):
            equipped = self.player_state.setdefault("equipped", [])
            if step.target not in equipped:
                equipped.append(step.target)
        elif step.action_type == "learn" and action_result.get("learned"):
            learned = self.player_state.setdefault("skills", [])
            if step.target not in learned:
                learned.append(step.target)

    def complete_step(self, sid: str, action_result: dict) -> bool:
        """完成当前步骤：必须 sid 匹配且实际操作结果通过校验。"""
        if self.current_step >= len(self.steps):
            return False
        step = self.steps[self.current_step]
        if step.sid != sid:
            return False
        if not self._validate_result(step, action_result):
            return False
        step.completed = True
        self._apply_state(step, action_result)
        self.current_step += 1
        self._emit("step_completed", step)
        self._emit("objective_updated", self.update_objective())
        if self.current_step >= len(self.steps):
            self.finish_tutorial()
        return True

    # ---------- bug2: 高亮坐标随 UI 缩放 ----------

    def get_highlight_position(self, step: GuideStep) -> tuple[float, float]:
        return (
            step.highlight_x * self.ui_scale,
            step.highlight_y * self.ui_scale,
        )

    def show_highlight(self, step: GuideStep) -> tuple[float, float]:
        position = self.get_highlight_position(step)
        self.active_highlights.append(step.sid)
        return position

    # ---------- bug3: 可跳过 + 首次进入提示 ----------

    def skip_tutorial(self) -> bool:
        """跳过引导：不标记任何步骤完成（因此奖励不可领），不影响后续功能。"""
        if not self.can_skip:
            return False
        self.skipped = True
        self.tutorial_seen = True
        self.current_step = len(self.steps)
        self._clear_visuals()
        self._emit("tutorial_skipped", None)
        self.listeners.clear()
        return True

    def prompt_first_entry(self):
        """首次进入返回提示文案；老玩家（已做过选择）返回 None。"""
        if self.tutorial_seen:
            return None
        return "是否观看新手引导？"

    def resolve_first_entry(self, watch: bool) -> bool:
        """首次进入的选择：观看则正式开始；不观看则跳过，后续功能不受影响。"""
        self.tutorial_seen = True
        if watch:
            self.current_step = 0
            self.overlay_active = True
            self._emit("tutorial_started", None)
            return True
        return self.skip_tutorial()

    # ---------- bug4: 目标实时监听状态变化 ----------

    def add_listener(self, event: str, callback) -> None:
        self.listeners.append((event, callback))

    def remove_listener(self, event: str, callback) -> None:
        self.listeners = [
            (evt, cb) for (evt, cb) in self.listeners
            if not (evt == event and cb == callback)
        ]

    def _emit(self, event: str, payload) -> None:
        for evt, callback in list(self.listeners):
            if evt == event:
                callback(payload)

    def _state_satisfies(self, step: GuideStep) -> bool:
        """不依赖点击事件，直接从玩家状态判断步骤目标是否已达成。"""
        if step.action_type == "equip":
            return step.target in self.player_state.get("equipped", [])
        if step.action_type == "learn":
            return step.target in self.player_state.get("skills", [])
        return False

    def update_player_state(self, **changes) -> None:
        """玩家状态发生变化时调用：实时推进已满足条件的目标并广播更新。"""
        self.player_state.update(changes)
        self._emit("state_changed", self.player_state)
        while self.current_step < len(self.steps):
            step = self.steps[self.current_step]
            if not self._state_satisfies(step):
                break
            step.completed = True
            self.current_step += 1
            self._emit("step_completed", step)
        self._emit("objective_updated", self.update_objective())
        if self.current_step >= len(self.steps) and not self.skipped:
            self.finish_tutorial()

    def update_objective(self) -> str:
        """返回当前应展示的任务目标，步骤推进后立即反映。"""
        if self.current_step < len(self.steps):
            return self.steps[self.current_step].description
        return "完成"

    # ---------- bug5: 奖励按步骤完成情况发放 ----------

    def claim_reward(self, step_index: int) -> dict:
        """仅当对应步骤真正完成（非跳过）、且未领取过时发放奖励。"""
        if self.skipped:
            return {}
        if not (0 <= step_index < len(self.steps)):
            return {}
        step = self.steps[step_index]
        if not step.completed:
            return {}
        if step.sid in self.rewards_claimed:
            return {}
        reward = {"gold": 100, "item": "newbie_sword"}
        self.rewards_claimed.add(step.sid)
        return reward

    # ---------- bug6: 结束清理遮罩/高亮/监听 ----------

    def _clear_visuals(self) -> None:
        self.overlay_active = False
        self.active_highlights.clear()

    def finish_tutorial(self):
        """引导正常结束：推进进度并清理全部遮罩、高亮框与事件监听。"""
        self.current_step = len(self.steps)
        self.finished = True
        self.tutorial_seen = True
        self._clear_visuals()
        self._emit("tutorial_finished", None)
        self.listeners.clear()
