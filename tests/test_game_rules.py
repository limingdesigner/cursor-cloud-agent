"""关卡出怪、精英倍率、基地扣血、按行寻敌和中文字体。"""
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
pygame.init()
pygame.display.set_mode((1280, 640))

import importlib.util
_SPEC = importlib.util.spec_from_file_location(
    "sinkland", os.path.join(os.path.dirname(__file__), "..", "废土耕地者.py"))
game = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(game)


def battle(level_index, difficulty="简单"):
    g = game.Game()
    g.difficulty = difficulty
    g.selected_level = level_index
    g.selected_cards = []
    return game.BattleScene(g)


class RuleTests(unittest.TestCase):
    def test_easy_level_one_follows_the_table(self):
        scene = battle(0, "简单")
        listed = sum(len(w["spawn"]) for w in scene._waves)
        self.assertEqual(scene.total_waves, 2)
        self.assertEqual(scene._spawn_copies, 1)
        self.assertEqual(listed, 7)
        for _ in range(30):
            self.assertIn(scene.get_row(), (1, 2, 3))

    def test_higher_difficulties_add_waves_and_copies(self):
        normal = battle(0, "普通")
        self.assertEqual(normal.total_waves, 4)
        self.assertEqual(normal._spawn_copies, 1)
        hard = battle(0, "困难")
        self.assertEqual(hard.total_waves, 4)
        self.assertEqual(hard._spawn_copies, 3)
        listed = sum(len(w["spawn"]) for w in hard._waves)
        self.assertEqual(listed * hard._spawn_copies, 42)

    def test_elite_multipliers_follow_each_level(self):
        easy = battle(6, "简单")          # 第7关，默认 1.5 / 0.9
        walker = game.Monster("m_walker", 0)
        easy.apply_spawn_modifiers(walker)
        self.assertEqual(walker.maxhp, int(260 * 1.5))
        self.assertAlmostEqual(walker.spd_mult, 0.9)

        ninth = battle(8, "简单")         # 第9关，说明写的是 ×2 / ×0.85
        brute = game.Monster("m_walker", 0)
        ninth.apply_spawn_modifiers(brute)
        self.assertEqual(brute.maxhp, 260 * 2)
        self.assertAlmostEqual(brute.spd_mult, 0.85)

        tenth = battle(9, "简单")         # 第10关只写了血量 ×2
        boss = game.Monster("m_walker", 0)
        tenth.apply_spawn_modifiers(boss)
        self.assertEqual(boss.maxhp, 260 * 2)
        self.assertAlmostEqual(boss.spd_mult, 1.0)

    def test_leak_damages_base_instead_of_instant_loss(self):
        scene = battle(0)
        monster = game.Monster("m_walker", 1)
        monster.hp = 260
        monster._hit_base(scene.ctx())
        self.assertEqual(scene.base_hp, game.BASE_HP - 260)
        self.assertEqual(monster.hp, 0)
        self.assertFalse(scene.game_over)
        monster.breached = False
        monster.hp = game.BASE_HP
        monster._hit_base(scene.ctx())
        self.assertEqual(scene.base_hp, 0)
        self.assertTrue(scene.game_over)

    def test_shooter_only_sees_its_row_and_giants(self):
        same = game.Monster("m_walker", 1)
        other = game.Monster("m_dog", 3)
        giant = game.Monster("m_end", 0)
        buckets = game.index_monsters_by_row([same, other, giant])
        ctx = {"monsters": [same, other, giant], "row_buckets": buckets}
        seen = game.monsters_for_y(ctx, same.y)
        self.assertIn(same, seen)
        self.assertIn(giant, seen)
        self.assertNotIn(other, seen)

    def test_cjk_font_renders_real_glyphs(self):
        img = game.render_text(32, "废土耕地者", (255, 255, 255))
        self.assertGreater(img.get_width(), 100)
        again = game.render_text(32, "废土耕地者", (255, 255, 255))
        self.assertIs(img, again)


if __name__ == "__main__":
    unittest.main()
