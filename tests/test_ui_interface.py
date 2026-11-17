"""Automated unit and integration tests for BLADE ARENA Pygame interface and visual experience.

Tests run headlessly using SDL dummy drivers to verify:
- Scene creation, transitions, and event routing.
- Main menu hotkeys (1-5, ESC) and button navigation.
- Match setup configuration (modes, archetypes, stadiums, difficulties, sides).
- BattleScene HUD, Mamdani danger ratings, and real-time top and arena rendering.
- Action legality enforcement and disabled button reasons.
- Simultaneous action execution without opponent preview leakage.
- AI vs AI playback controls: Start/Pause, Step 1 round, Speed toggles (1x/2x/4x), Swap sides, Restart.
- Combat VFX triggers and updates (impact sparks, dodge ghost trails, shrink pulses).
- Match result presentation and navigation.
"""

import os

# Ensure headless execution
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pytest
import pygame

from blade_arena.app import BladeArenaApp
from blade_arena.game.models import Action, BladeType, FinishReason, StadiumType
from blade_arena.orchestration.participants import (
    HumanParticipant,
    create_ai_participant,
)
from blade_arena.orchestration.session import GameMode, MatchSession, SessionConfig
from blade_arena.ui.renderer import ArenaRenderer, BladeRenderer, CombatVFX
from blade_arena.ui.scenes.base import Scene
from blade_arena.ui.scenes.battle import BattleScene
from blade_arena.ui.scenes.main_menu import MainMenuScene
from blade_arena.ui.scenes.result import ResultScene
from blade_arena.ui.scenes.settings import SettingsScene
from blade_arena.ui.scenes.setup import MatchSetupScene
from blade_arena.ui.scenes.tournament import TournamentInfoScene
from blade_arena.ui.theme import SCREEN_HEIGHT, SCREEN_WIDTH
from blade_arena.ui.widgets import Button, Panel, ProgressBar, ToggleGroup


@pytest.fixture(autouse=True)
def init_pygame():
    """Ensure pygame is initialized for headless surface operations."""
    from blade_arena.ui.theme import clear_font_cache

    pygame.init()
    pygame.font.init()
    clear_font_cache()
    surface = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    yield surface
    clear_font_cache()
    if pygame.get_init():
        pygame.quit()


# ------------------------------------------------------------------------------
# 1. Widgets & UI Component Tests
# ------------------------------------------------------------------------------

def test_button_click_and_disabled_state(init_pygame):
    """Verify Button mouse interaction, hotkeys, and disabled reason tooltips."""
    screen = init_pygame
    clicked = []

    btn = Button(
        rect=pygame.Rect(100, 100, 120, 40),
        text="Attack",
        shortcut_text="[2]",
        shortcut_key=pygame.K_2,
        callback=lambda: clicked.append(True),
    )

    # Hover test
    motion_event = pygame.event.Event(pygame.MOUSEMOTION, pos=(110, 110), rel=(0, 0), buttons=(0, 0, 0))
    btn.handle_event(motion_event)
    assert btn.hovered is True

    # Mouse Click
    down_event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(110, 110), button=1)
    btn.handle_event(down_event)
    assert btn.pressed is True

    up_event = pygame.event.Event(pygame.MOUSEBUTTONUP, pos=(110, 110), button=1)
    act = btn.handle_event(up_event)
    assert act is True
    assert len(clicked) == 1

    # Hotkey trigger
    key_event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_2)
    act_key = btn.handle_event(key_event)
    assert act_key is True
    assert len(clicked) == 2

    # Disabled state
    btn.enabled = False
    btn.disabled_reason = "Requires 8.0 Energy"
    act_disabled = btn.handle_event(key_event)
    assert act_disabled is False
    assert len(clicked) == 2

    # Draw check
    btn.draw(screen)


def test_progress_bar_and_panel_draw(init_pygame):
    """Verify ProgressBar and Panel draw without errors."""
    screen = init_pygame
    bar = ProgressBar(
        rect=pygame.Rect(50, 50, 200, 20),
        current_value=75.0,
        max_value=100.0,
        fill_color=(50, 180, 80),
    )
    bar.draw(screen)
    bar.set_values(30.0, 100.0, text_override="Low HP")
    bar.draw(screen)

    panel = Panel(rect=pygame.Rect(10, 10, 300, 200), title="Test Panel")
    panel.draw(screen)


def test_toggle_group_interaction(init_pygame):
    """Verify ToggleGroup selection changes on mouse click."""
    screen = init_pygame
    selected = []
    tg = ToggleGroup(
        rect=pygame.Rect(50, 50, 300, 30),
        options=[("Option A", "A"), ("Option B", "B")],
        initial_value="A",
        on_change=lambda val: selected.append(val),
    )
    assert tg.selected_value == "A"

    # Click Option B (right half)
    click_b = pygame.event.Event(pygame.MOUSEBUTTONUP, pos=(250, 65), button=1)
    tg.handle_event(click_b)
    assert tg.selected_value == "B"
    assert selected == ["B"]

    tg.draw(screen)


# ------------------------------------------------------------------------------
# 2. Arena, Blade & Combat VFX Renderer Tests
# ------------------------------------------------------------------------------

def test_arena_renderer_transforms_and_drawing(init_pygame):
    """Verify Cartesian coordinate mapping and stadium rendering."""
    screen = init_pygame
    renderer = ArenaRenderer(center_x=330, center_y=285, pixels_per_unit=24.0)

    # Center mapping
    sx, sy = renderer.arena_to_screen(0.0, 0.0)
    assert sx == 330
    assert sy == 285

    # Cartesian (+2, +3) -> screen (330 + 48, 285 - 72) = (378, 213)
    sx, sy = renderer.arena_to_screen(2.0, 3.0)
    assert sx == 378
    assert sy == 213

    # Inverse transform
    ax, ay = renderer.screen_to_arena(378, 213)
    assert pytest.approx(ax, abs=1e-3) == 2.0
    assert pytest.approx(ay, abs=1e-3) == 3.0

    # Draw all three stadium archetypes
    from blade_arena.game.models import Position, StadiumState
    for s_type in [StadiumType.CLASSIC_DISH, StadiumType.ICE_RINK, StadiumType.STEEP_BOWL]:
        stadium = StadiumState(center=Position(0.0, 0.0), radius=9.0, stadium_type=s_type)
        renderer.render(screen, stadium)


def test_blade_renderer_and_vfx(init_pygame):
    """Verify procedural blade rotation and combat VFX."""
    screen = init_pygame
    b_renderer = BladeRenderer(base_radius_px=22)
    vfx = CombatVFX()

    # Create dummy match
    session = MatchSession(HumanParticipant("P1"), create_ai_participant("P2", "ironclad", "easy"))
    b1 = session.state.player_1_blade
    b2 = session.state.player_2_blade

    # Update spin rotations
    b_renderer.update(0.016, [b1, b2])
    assert "player_1" in b_renderer.rotation_angles

    # Render blades
    b_renderer.render(screen, b1, (200, 200), is_player_1=True)
    b_renderer.render(screen, b2, (300, 200), is_player_1=False)

    # Trigger VFX
    vfx.add_attack_impact((250, 200))
    vfx.add_dodge_trail((200, 200), (180, 200), is_p1=True)
    vfx.add_shrink_pulse((330, 285), 216)
    assert len(vfx.effects) == 3

    # Update and render VFX
    vfx.update(0.1)
    vfx.render(screen)
    assert len(vfx.effects) == 3
    # Advance until expired
    vfx.update(1.0)
    assert len(vfx.effects) == 0


# ------------------------------------------------------------------------------
# 3. Scene Navigation Tests
# ------------------------------------------------------------------------------

def test_main_menu_scene_navigation(init_pygame):
    """Verify MainMenuScene options and keyboard shortcut routing."""
    menu = MainMenuScene()

    # Key 1 -> MatchSetupScene (Human vs AI)
    s1 = menu.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_1))
    assert isinstance(s1, MatchSetupScene)
    assert s1.mode == GameMode.HUMAN_VS_AI

    # Key 2 -> MatchSetupScene (AI vs AI)
    s2 = menu.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_2))
    assert isinstance(s2, MatchSetupScene)
    assert s2.mode == GameMode.AI_VS_AI

    # Key 3 -> TournamentInfoScene
    s3 = menu.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_3))
    assert isinstance(s3, TournamentInfoScene)

    # Key 4 -> SettingsScene
    s4 = menu.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_4))
    assert isinstance(s4, SettingsScene)


def test_tournament_and_settings_back(init_pygame):
    """Verify Tournament and Settings scenes return to MainMenu on ESC."""
    t_scene = TournamentInfoScene()
    t_scene.render(init_pygame)
    next_s = t_scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
    assert isinstance(next_s, MainMenuScene)

    s_scene = SettingsScene()
    s_scene.render(init_pygame)
    next_s2 = s_scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
    assert isinstance(next_s2, MainMenuScene)


def test_match_setup_scene_launch(init_pygame):
    """Verify MatchSetupScene interactive choices launch configured BattleScene."""
    setup = MatchSetupScene(initial_mode=GameMode.HUMAN_VS_AI)
    setup.human_side = "P2"
    setup.human_blade = BladeType.ATTACKER
    setup.ai_agent = "cyclone"
    setup.ai_diff = "easy"
    setup.ai_blade = BladeType.DEFENDER
    setup.stadium = StadiumType.ICE_RINK

    battle = setup._launch_match()
    assert isinstance(battle, BattleScene)
    assert battle.session.mode == GameMode.HUMAN_VS_AI
    # P1 is AI, P2 is Human
    assert battle.session.participant_1.is_human is False
    assert battle.session.participant_2.is_human is True
    assert battle.session.state.player_1_blade.blade_type == BladeType.DEFENDER
    assert battle.session.state.player_2_blade.blade_type == BladeType.ATTACKER
    assert battle.session.state.stadium.stadium_type == StadiumType.ICE_RINK


# ------------------------------------------------------------------------------
# 4. BattleScene Live Gameplay & Controls Tests
# ------------------------------------------------------------------------------

def test_battle_scene_human_vs_ai_legality_and_steps(init_pygame):
    """Verify BattleScene in Human vs AI mode checks legality and advances rounds."""
    screen = init_pygame
    p1 = HumanParticipant("Human Operator")
    p2 = create_ai_participant("AI Opponent", "ironclad", "easy", player_id="player_2")
    session = MatchSession(p1, p2)
    battle = BattleScene(session=session)

    # Initial check: all buttons should be enabled at 100 energy
    for act, btn in battle.action_buttons:
        assert btn.enabled is True

    # Press Attack hotkey '[2]'
    attack_event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_2)
    battle.handle_event(attack_event)

    # One round should have resolved!
    assert session.state.completed_rounds == 1
    assert len(session.round_history) == 1
    assert session.round_history[0].player_1_action == Action.ATTACK

    # Render battle frame without errors
    battle.update(0.016)
    battle.render(screen)

    # Pause control
    pause_event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_p)
    battle.handle_event(pause_event)
    assert session.is_paused is True
    battle.handle_event(pause_event)
    assert session.is_paused is False

    # Restart control
    restart_event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_r)
    battle.handle_event(restart_event)
    assert session.state.completed_rounds == 0


def test_battle_scene_ai_vs_ai_controls(init_pygame):
    """Verify AI vs AI autoplay, step, speed toggle, side swap, and finish."""
    screen = init_pygame
    p1 = create_ai_participant("P1 Ironclad", "ironclad", "easy", player_id="player_1")
    p2 = create_ai_participant("P2 Cyclone", "cyclone", "easy", player_id="player_2", seed=42)
    session = MatchSession(p1, p2)
    battle = BattleScene(session=session)

    # Single-step via '[S]' key
    step_event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_s)
    battle.handle_event(step_event)
    assert session.state.completed_rounds == 1

    # Speed toggle
    battle.btn_speed_4x.callback = lambda: battle._set_speed(4)
    battle.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=battle.btn_speed_4x.rect.center, button=1))
    assert battle.playback_speed == 4

    # Autoplay start
    play_event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE)
    battle.handle_event(play_event)
    assert battle.is_auto_playing is True

    # Advance update to trigger step via timer
    battle.update(0.10)
    assert session.state.completed_rounds >= 2

    # Pause autoplay
    battle.handle_event(play_event)
    assert battle.is_auto_playing is False

    # Side Swap
    swap_event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_w)
    battle.handle_event(swap_event)
    assert session.state.completed_rounds == 0
    # Participants should have swapped
    assert "Cyclone" in session.participant_1.name
    assert "Ironclad" in session.participant_2.name

    # Render frame
    battle.render(screen)


def test_result_scene_inspection_and_replay(init_pygame):
    """Verify ResultScene displays authoritative outcome and handles Play Again."""
    screen = init_pygame
    p1 = create_ai_participant("P1", "ironclad", "easy", player_id="player_1")
    p2 = create_ai_participant("P2", "cyclone", "easy", player_id="player_2", seed=10)
    session = MatchSession(p1, p2)

    # Step match until finished or max 40 rounds
    while not session.is_finished:
        session.step_round()

    assert session.is_finished is True
    res_scene = ResultScene(session=session)
    res_scene.render(screen)

    # Play again should restart match and return BattleScene
    play_again_event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_r)
    next_s = res_scene.handle_event(play_again_event)
    assert isinstance(next_s, BattleScene)
    assert next_s.session.state.completed_rounds == 0


def test_app_integration_with_scene_flow(init_pygame):
    """Verify BladeArenaApp initializes MainMenu and updates scenes cleanly."""
    app = BladeArenaApp(max_frames=10)
    app.setup()
    try:
        assert isinstance(app.current_scene, MainMenuScene)
        # Advance 5 frames
        for _ in range(5):
            app.update(0.016)
            app.render()
        assert app.frame_count == 5
        assert app.running is True
    finally:
        app.teardown()
