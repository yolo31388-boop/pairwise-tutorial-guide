"""新手引导与教程系统 - 红态测试"""
import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tutorial.guide import Tutorial, GuideStep

class TestStepValidation:
    def test_step_verifies_actual_result(self):
        t = Tutorial()
        step = GuideStep("s1", "装备武器", "equip", "sword")
        t.add_step(step)
        t.player_state = {"equipped": []}
        # 只点击没装备，应该不完成
        result = t.complete_step("s1", {"clicked": True, "equipped": False})
        assert result == False  # bug1: 返回True
        # 真正装备了才完成
        result2 = t.complete_step("s1", {"clicked": True, "equipped": True})
        assert result2 == True

class TestHighlightScaling:
    def test_highlight_scales_with_ui(self):
        t = Tutorial()
        t.ui_scale = 1.5
        step = GuideStep("s1", "点击", "click", "btn", highlight_x=100, highlight_y=200)
        x, y = t.get_highlight_position(step)
        assert x == 150  # bug2: 还是100
        assert y == 300

class TestSkip:
    def test_tutorial_can_be_skipped(self):
        t = Tutorial()
        t.can_skip = True
        result = t.skip_tutorial()
        assert result == True  # bug3: 返回False
        assert t.current_step == len(t.steps)

class TestObjectiveUpdate:
    def test_objective_updates_in_real_time(self):
        t = Tutorial()
        t.add_step(GuideStep("s1", "第一步", "click", "btn1"))
        t.add_step(GuideStep("s2", "第二步", "click", "btn2"))
        t.complete_step("s1", {"clicked": True})
        obj = t.update_objective()
        assert obj == "第二步"  # bug4: 可能还是第一步

class TestRewardGating:
    def test_reward_only_after_completion(self):
        t = Tutorial()
        t.add_step(GuideStep("s1", "第一步", "click", "btn1"))
        # 没完成不能领
        t.rewards_claimed = set()
        reward = t.claim_reward(0)
        # 应该需要完成步骤才能领
        # bug5: 直接给了
        # 这里验证：完成后才能领
        t.complete_step("s1", {"clicked": True})
        reward2 = t.claim_reward(0)
        assert reward2.get("gold") == 100
        # 重复领不行
        t.rewards_claimed.add("s1")
        reward3 = t.claim_reward(0)
        assert reward3 == {} or reward3 is None  # bug5: 又领到了

class TestOverlayCleanup:
    def test_finish_clears_overlay(self):
        t = Tutorial()
        t.overlay_active = True
        t.add_step(GuideStep("s1", "第一步", "click", "btn1"))
        t.complete_step("s1", {"clicked": True})
        t.finish_tutorial()
        assert t.overlay_active == False  # bug6: 还是True
