"""新手引导与教程系统"""
from dataclasses import dataclass


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
    # 各操作类型需要在 action_result 中验证的实际结果字段
    _RESULT_KEYS = {
        "click": "clicked",
        "equip": "equipped",
        "learn": "learned",
        "complete": "completed",
    }

    # 实际结果字段 -> player_state 中记录持有物的集合名
    _STATE_COLLECTIONS = {
        "equip": "equipped",
        "learn": "skills",
    }

    REWARD = {"gold": 100, "item": "newbie_sword"}

    def __init__(self):
        self.steps: list[GuideStep] = []
        self.current_step: int = 0
        self.ui_scale: float = 1.0
        self.can_skip: bool = True
        self.skipped: bool = False
        self.finished: bool = False
        self.overlay_active: bool = False
        self.active_highlight: GuideStep | None = None
        self.rewards_claimed: set[str] = set()
        self.player_state: dict = {"equipped": [], "skills": []}
        self.listeners: list = []
        self.intro_prompted: bool = False

    def add_step(self, step: GuideStep):
        self.steps.append(step)

    # ---------- 遮罩 / 高亮 ----------

    def show_overlay(self):
        self.overlay_active = True

    def show_highlight(self, step: GuideStep):
        self.active_highlight = step

    def get_highlight_position(self, step: GuideStep) -> tuple[float, float]:
        return (
            step.highlight_x * self.ui_scale,
            step.highlight_y * self.ui_scale,
        )

    # ---------- 跳过 / 首次进入 ----------

    def first_entry_prompt(self) -> bool:
        """首次进入时返回 True，表示需要向玩家弹出“是否观看引导”。"""
        if self.intro_prompted:
            return False
        self.intro_prompted = True
        return True

    def choose_watch(self, watch: bool) -> bool:
        if watch:
            return True
        return self.skip_tutorial()

    def skip_tutorial(self) -> bool:
        if not self.can_skip or self.finished:
            return False
        self.skipped = True
        self.current_step = len(self.steps)
        self._cleanup_ui()
        return True

    # ---------- 状态监听 ----------

    def add_listener(self, callback) -> callable:
        self.listeners.append(callback)

        def off():
            if callback in self.listeners:
                self.listeners.remove(callback)

        return off

    def _notify(self, event: str, data):
        for callback in list(self.listeners):
            callback(event, data)

    def update_player_state(self, **kwargs):
        """游戏侧状态变化入口：更新实际状态并实时同步任务目标。"""
        changed = False
        for key, value in kwargs.items():
            if self.player_state.get(key) != value:
                self.player_state[key] = value
                changed = True
        if changed:
            advanced = self._sync_current_from_state()
            self._notify("state_changed", dict(self.player_state))
            if advanced:
                self._notify("objective", self.update_objective())

    def _sync_current_from_state(self) -> bool:
        """根据 player_state 实际状态判断当前步骤是否已完成。"""
        advanced = False
        while self.current_step < len(self.steps):
            step = self.steps[self.current_step]
            collection = self._STATE_COLLECTIONS.get(step.action_type)
            if collection is None:
                break
            owned = self.player_state.get(collection, [])
            if step.target not in owned:
                break
            step.completed = True
            self.current_step += 1
            advanced = True
            if self.current_step >= len(self.steps):
                self.finish_tutorial()
        return advanced

    # ---------- 步骤推进 ----------

    def _verify_result(self, step: GuideStep, action_result: dict) -> bool:
        key = self._RESULT_KEYS.get(step.action_type, "clicked")
        if not action_result.get(key):
            return False
        collection = self._STATE_COLLECTIONS.get(step.action_type)
        if collection is not None:
            owned = self.player_state.setdefault(collection, [])
            if step.target not in owned and action_result.get(key):
                owned.append(step.target)
        return True

    def complete_step(self, sid: str, action_result: dict) -> bool:
        for index, step in enumerate(self.steps):
            if step.sid != sid:
                continue
            if step.completed:
                return False
            if not self._verify_result(step, action_result):
                return False
            step.completed = True
            if index == self.current_step:
                self.current_step += 1
            if self.current_step >= len(self.steps):
                self.finish_tutorial()
            else:
                self._notify("objective", self.update_objective())
            return True
        return False

    def update_objective(self) -> str:
        self._sync_current_from_state()
        if self.current_step < len(self.steps):
            return self.steps[self.current_step].description
        return "完成"

    # ---------- 奖励 ----------

    def claim_reward(self, step_index: int) -> dict:
        if self.skipped or self.finished is False:
            # 跳过后不发；进行中的引导也不允许提前领取
            if self.skipped:
                return {}
        if not (0 <= step_index < len(self.steps)):
            return {}
        step = self.steps[step_index]
        if not step.completed:
            return {}
        if self.current_step <= step_index:
            return {}
        if step.sid in self.rewards_claimed:
            return {}
        self.rewards_claimed.add(step.sid)
        return dict(self.REWARD)

    # ---------- 结束清理 ----------

    def _cleanup_ui(self):
        self.overlay_active = False
        self.active_highlight = None
        self.listeners.clear()

    def finish_tutorial(self):
        self.current_step = len(self.steps)
        self.finished = True
        self._cleanup_ui()
