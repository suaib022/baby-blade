"""Battle Scene for BLADE ARENA.

Coordinates live match execution, real-time arena and top rendering, complete HUD
with Mamdani fuzzy danger metrics, action legality enforcement, human input handling,
AI vs AI playback controls, event logging, and combat visual effects.
"""

from __future__ import annotations

import math
from typing import Any, List, Optional, Tuple

import pygame

from blade_arena.game.actions import check_action_legality
from blade_arena.game.fuzzy_danger import DangerAssessment, evaluate_blade_danger
from blade_arena.game.models import Action, BladeState, MatchStatus
from blade_arena.orchestration.session import GameMode, MatchSession, StepRecord
from blade_arena.ui.renderer import ArenaRenderer, BladeRenderer, CombatVFX
from blade_arena.ui.scenes.base import Scene
from blade_arena.ui.theme import (
    ARCHETYPE_COLORS,
    COLOR_BG,
    COLOR_P1_PRIMARY,
    COLOR_P2_PRIMARY,
    COLOR_PANEL_BG,
    COLOR_PANEL_BORDER,
    COLOR_TEXT_GOLD,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_SUBTITLE,
    COLOR_TEXT_WHITE,
    DANGER_THEMES,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    get_font,
)
from blade_arena.ui.widgets import Button, Panel, ProgressBar


class BattleScene(Scene):
    """Interactive battle viewport and match controller for both game modes."""

    def __init__(self, session: MatchSession) -> None:
        self.session: MatchSession = session
        self.mode: GameMode = session.mode

        # Visual Renderers
        self.arena_renderer = ArenaRenderer(center_x=330, center_y=285, pixels_per_unit=24.0)
        self.blade_renderer = BladeRenderer(base_radius_px=22)
        self.vfx = CombatVFX()

        # Playback Timing for AI vs AI
        # Speeds: 1x = 0.50s/round, 2x = 0.25s/round, 4x = 0.08s/round
        self.playback_speed: int = 1
        self.speed_intervals = {1: 0.50, 2: 0.25, 4: 0.08}
        self.is_auto_playing: bool = False
        self._step_timer: float = 0.0

        # UI Panels and Widgets
        self.action_buttons: List[Tuple[Action, Button]] = []
        self.control_buttons: List[Button] = []
        self.event_log: List[str] = [
            f"Match started: {session.state.player_1_blade.blade_type.name} vs {session.state.player_2_blade.blade_type.name}",
            f"Stadium: {session.state.stadium.stadium_type.name}",
        ]
        self._last_stadium_radius: float = session.state.stadium.radius

        self._build_buttons()
        self._update_human_action_legality()

    # --------------------------------------------------------------------------
    # Initialization and Button Setup
    # --------------------------------------------------------------------------

    def _build_buttons(self) -> None:
        """Create controls according to the active game mode."""
        self.action_buttons.clear()
        self.control_buttons.clear()

        # Identify human participant (if any)
        self.human_player_id: Optional[str] = None
        if self.session.participant_1.is_human:
            self.human_player_id = self.session.player_1_id
        elif self.session.participant_2.is_human:
            self.human_player_id = self.session.player_2_id

        if self.mode == GameMode.HUMAN_VS_AI and self.human_player_id is not None:
            # 5 Human Action Buttons
            actions = [
                (Action.CHARGE, "Charge", "[1]", pygame.K_1),
                (Action.ATTACK, "Attack", "[2]", pygame.K_2),
                (Action.GUARD, "Guard", "[3]", pygame.K_3),
                (Action.DODGE, "Dodge", "[4]", pygame.K_4),
                (Action.SPECIAL_SPIN, "Special", "[5]", pygame.K_5),
            ]
            btn_w = 114
            btn_h = 52
            start_x = 35
            btn_y = 560
            for i, (act, name, sc_t, sc_k) in enumerate(actions):
                rect = pygame.Rect(start_x + i * (btn_w + 8), btn_y, btn_w, btn_h)
                btn = Button(
                    rect=rect,
                    text=name,
                    shortcut_text=sc_t,
                    shortcut_key=sc_k,
                    font_size=15,
                )
                self.action_buttons.append((act, btn))

            # Utility Controls (Right side of bottom bar)
            self.btn_pause = Button(
                rect=pygame.Rect(650, btn_y, 90, btn_h),
                text="Pause",
                shortcut_text="[P]",
                shortcut_key=pygame.K_p,
                font_size=14,
            )
            self.btn_restart = Button(
                rect=pygame.Rect(750, btn_y, 90, btn_h),
                text="Restart",
                shortcut_text="[R]",
                shortcut_key=pygame.K_r,
                font_size=14,
            )
            self.btn_menu = Button(
                rect=pygame.Rect(850, btn_y, 85, btn_h),
                text="Menu",
                shortcut_text="[ESC]",
                shortcut_key=pygame.K_ESCAPE,
                font_size=14,
            )
            self.control_buttons.extend([self.btn_pause, self.btn_restart, self.btn_menu])

        else:
            # AI vs AI Controls
            btn_y = 560
            self.btn_ai_play = Button(
                rect=pygame.Rect(35, btn_y, 140, 52),
                text="Start",
                shortcut_text="[Space]",
                shortcut_key=pygame.K_SPACE,
                font_size=15,
                custom_bg=(28, 75, 50),
                custom_border=(50, 160, 90),
            )
            self.btn_ai_step = Button(
                rect=pygame.Rect(185, btn_y, 130, 52),
                text="Step 1 Rnd",
                shortcut_text="[S]",
                shortcut_key=pygame.K_s,
                font_size=15,
            )
            # Speed Toggle Buttons
            self.btn_speed_1x = Button(
                rect=pygame.Rect(325, btn_y, 60, 52),
                text="1x",
                font_size=14,
                custom_bg=(40, 75, 120),
            )
            self.btn_speed_2x = Button(
                rect=pygame.Rect(390, btn_y, 60, 52),
                text="2x",
                font_size=14,
            )
            self.btn_speed_4x = Button(
                rect=pygame.Rect(455, btn_y, 60, 52),
                text="4x",
                font_size=14,
            )
            self.btn_ai_swap = Button(
                rect=pygame.Rect(525, btn_y, 115, 52),
                text="Swap Sides",
                shortcut_text="[W]",
                shortcut_key=pygame.K_w,
                font_size=14,
            )
            self.btn_restart = Button(
                rect=pygame.Rect(650, btn_y, 90, 52),
                text="Restart",
                shortcut_text="[R]",
                shortcut_key=pygame.K_r,
                font_size=14,
            )
            self.btn_menu = Button(
                rect=pygame.Rect(750, btn_y, 85, 52),
                text="Menu",
                shortcut_text="[ESC]",
                shortcut_key=pygame.K_ESCAPE,
                font_size=14,
            )
            self.control_buttons.extend([
                self.btn_ai_play,
                self.btn_ai_step,
                self.btn_speed_1x,
                self.btn_speed_2x,
                self.btn_speed_4x,
                self.btn_ai_swap,
                self.btn_restart,
                self.btn_menu,
            ])

        # Result Navigation Button (Hidden until match ends)
        self.btn_view_results = Button(
            rect=pygame.Rect(SCREEN_WIDTH // 2 - 130, 240, 260, 48),
            text="VIEW MATCH RESULTS",
            shortcut_text="[Enter]",
            shortcut_key=pygame.K_RETURN,
            font_size=16,
            custom_bg=(160, 30, 40),
            custom_border=(240, 80, 90),
        )

    # --------------------------------------------------------------------------
    # Legality and Human Action Checking
    # --------------------------------------------------------------------------

    def _update_human_action_legality(self) -> None:
        """Query shared action legality API and update button states/reasons."""
        if self.human_player_id is None or self.session.is_finished:
            for _, btn in self.action_buttons:
                btn.enabled = False
            return

        state = self.session.state
        for act, btn in self.action_buttons:
            legality = check_action_legality(state, self.human_player_id, act)
            btn.enabled = legality.is_legal
            btn.disabled_reason = legality.reason

    # --------------------------------------------------------------------------
    # Step Execution & Feedback
    # --------------------------------------------------------------------------

    def _execute_step(self, human_action: Optional[Action] = None) -> None:
        """Execute one round in the session and generate visual feedback."""
        if not self.session.can_step:
            return

        pre_state = self.session.state
        p1_pre_pos = (pre_state.player_1_blade.position.x, pre_state.player_1_blade.position.y)
        p2_pre_pos = (pre_state.player_2_blade.position.x, pre_state.player_2_blade.position.y)

        try:
            record: StepRecord = self.session.step_round(human_action=human_action)
        except Exception as exc:
            self.event_log.append(f"Step error: {exc}")
            return

        post_state = record.state_after
        r_num = record.round_number

        # Check for stadium boundary shrink
        if post_state.stadium.radius < self._last_stadium_radius:
            self._last_stadium_radius = post_state.stadium.radius
            px = self.arena_renderer.radius_to_pixels(post_state.stadium.radius)
            self.vfx.add_shrink_pulse((self.arena_renderer.center_x, self.arena_renderer.center_y), px)
            self.event_log.append(f"R{r_num}: Stadium shrank to {post_state.stadium.radius:.1f}m!")

        # Check for attack hit / clash impact sparks
        p1_acted_attack = record.player_1_action in (Action.ATTACK, Action.SPECIAL_SPIN)
        p2_acted_attack = record.player_2_action in (Action.ATTACK, Action.SPECIAL_SPIN)
        p1_stb_drop = pre_state.player_1_blade.current_stability - post_state.player_1_blade.current_stability
        p2_stb_drop = pre_state.player_2_blade.current_stability - post_state.player_2_blade.current_stability

        p1_scr = self.arena_renderer.arena_to_screen(post_state.player_1_blade.position.x, post_state.player_1_blade.position.y)
        p2_scr = self.arena_renderer.arena_to_screen(post_state.player_2_blade.position.x, post_state.player_2_blade.position.y)
        mid_scr = ((p1_scr[0] + p2_scr[0]) // 2, (p1_scr[1] + p2_scr[1]) // 2)

        if p1_stb_drop > 2.0 or p2_stb_drop > 2.0 or (p1_acted_attack and p2_acted_attack):
            self.vfx.add_attack_impact(mid_scr)

        # Check for dodge ghost trails
        if record.player_1_action == Action.DODGE:
            start_scr = self.arena_renderer.arena_to_screen(p1_pre_pos[0], p1_pre_pos[1])
            self.vfx.add_dodge_trail(start_scr, p1_scr, is_p1=True)

        if record.player_2_action == Action.DODGE:
            start_scr = self.arena_renderer.arena_to_screen(p2_pre_pos[0], p2_pre_pos[1])
            self.vfx.add_dodge_trail(start_scr, p2_scr, is_p1=False)

        # Log round events
        act1_str = record.player_1_action.name.replace("_", " ").title()
        act2_str = record.player_2_action.name.replace("_", " ").title()
        self.event_log.append(f"R{r_num}: P1 {act1_str} vs P2 {act2_str}")

        # Log damage summary
        if p1_stb_drop > 1.0 or p2_stb_drop > 1.0:
            self.event_log.append(f"  Damage: P1 -{p1_stb_drop:.1f} | P2 -{p2_stb_drop:.1f}")

        # Check finish
        if self.session.is_finished:
            res = self.session.state.result
            if res is not None:
                winner_text = res.winner_id.upper() if res.winner_id else "DRAW"
                reason_text = res.reason.name.replace("_", " ").title()
                self.event_log.append(f"FINISHED: {winner_text} ({reason_text})")
            self.is_auto_playing = False

        # Keep recent event log bounded
        if len(self.event_log) > 25:
            self.event_log = self.event_log[-25:]

        self._update_human_action_legality()

    # --------------------------------------------------------------------------
    # Event Handling
    # --------------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> Optional[Scene]:
        """Process user input."""
        # Check result view button if finished
        if self.session.is_finished:
            if self.btn_view_results.handle_event(event):
                from blade_arena.ui.scenes.result import ResultScene

                return ResultScene(session=self.session)
            if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE):
                from blade_arena.ui.scenes.result import ResultScene

                return ResultScene(session=self.session)

        # Human vs AI Mode Actions
        if self.mode == GameMode.HUMAN_VS_AI and self.session.can_step:
            for act, btn in self.action_buttons:
                if btn.handle_event(event):
                    self._execute_step(human_action=act)
                    return None

        # General Controls
        if self.mode == GameMode.HUMAN_VS_AI:
            if self.btn_pause.handle_event(event):
                if self.session.is_paused:
                    self.session.resume()
                    self.btn_pause.text = "Pause"
                else:
                    self.session.pause()
                    self.btn_pause.text = "Resume"
                return None

        else:
            # AI vs AI Mode Controls
            if self.btn_ai_play.handle_event(event):
                self.is_auto_playing = not self.is_auto_playing
                self.btn_ai_play.text = "Pause" if self.is_auto_playing else "Play"
                return None

            if self.btn_ai_step.handle_event(event):
                self.is_auto_playing = False
                self.btn_ai_play.text = "Play"
                self._execute_step()
                return None

            if self.btn_speed_1x.handle_event(event):
                self._set_speed(1)
                return None
            if self.btn_speed_2x.handle_event(event):
                self._set_speed(2)
                return None
            if self.btn_speed_4x.handle_event(event):
                self._set_speed(4)
                return None

            if self.btn_ai_swap.handle_event(event):
                self.is_auto_playing = False
                self.btn_ai_play.text = "Play"
                self.session.swap_sides()
                self._last_stadium_radius = self.session.state.stadium.radius
                self.event_log.append("Sides swapped and match restarted.")
                self._update_human_action_legality()
                return None

        # Shared Restart Button
        if self.btn_restart.handle_event(event):
            self.session.restart()
            self._last_stadium_radius = self.session.state.stadium.radius
            self.event_log.clear()
            self.event_log.append("Match restarted.")
            self.is_auto_playing = False
            if hasattr(self, "btn_ai_play"):
                self.btn_ai_play.text = "Play"
            if hasattr(self, "btn_pause"):
                self.btn_pause.text = "Pause"
            self._update_human_action_legality()
            return None

        # Back to Main Menu Button / ESC
        if self.btn_menu.handle_event(event):
            from blade_arena.ui.scenes.main_menu import MainMenuScene

            return MainMenuScene()

        return None

    def _set_speed(self, speed: int) -> None:
        """Adjust AI vs AI playback speed (display timing only)."""
        self.playback_speed = speed
        self.btn_speed_1x.custom_bg = (40, 75, 120) if speed == 1 else None
        self.btn_speed_2x.custom_bg = (40, 75, 120) if speed == 2 else None
        self.btn_speed_4x.custom_bg = (40, 75, 120) if speed == 4 else None

    # --------------------------------------------------------------------------
    # Update Loop
    # --------------------------------------------------------------------------

    def update(self, dt: float) -> Optional[Scene]:
        """Advance animations and AI vs AI continuous playback."""
        state = self.session.state
        self.blade_renderer.update(
            dt, [state.player_1_blade, state.player_2_blade]
        )
        self.vfx.update(dt)

        # AI vs AI Autoplay Step Accumulator
        if self.mode == GameMode.AI_VS_AI and self.is_auto_playing:
            if not self.session.can_step:
                self.is_auto_playing = False
                self.btn_ai_play.text = "Play"
            else:
                self._step_timer += dt
                interval = self.speed_intervals.get(self.playback_speed, 0.50)
                if self._step_timer >= interval:
                    self._step_timer = 0.0
                    self._execute_step()

        return None

    # --------------------------------------------------------------------------
    # Rendering
    # --------------------------------------------------------------------------

    def render(self, screen: pygame.Surface) -> None:
        """Render arena, tops, HUD, event log, and active controls."""
        screen.fill(COLOR_BG)
        state = self.session.state
        p1_blade = state.player_1_blade
        p2_blade = state.player_2_blade

        # 1. Top Header Bar
        self._render_header(screen)

        # 2. Arena Floor, Boundary, & Geometry
        self.arena_renderer.render(screen, state.stadium)

        # 3. Combat VFX (Trails, Sparks, Shrink Pulse)
        self.vfx.render(screen)

        # 4. Blades / Tops
        p1_pos = self.arena_renderer.arena_to_screen(p1_blade.position.x, p1_blade.position.y)
        p2_pos = self.arena_renderer.arena_to_screen(p2_blade.position.x, p2_blade.position.y)

        self.blade_renderer.render(screen, p1_blade, p1_pos, is_player_1=True)
        self.blade_renderer.render(screen, p2_blade, p2_pos, is_player_1=False)

        # 5. Left Panel (Player 1 Status)
        self._render_player_panel(screen, is_player_1=True, rect=pygame.Rect(645, 50, 290, 145))

        # 6. Right Panel (Player 2 Status)
        self._render_player_panel(screen, is_player_1=False, rect=pygame.Rect(645, 205, 290, 145))

        # 7. Combat Event Log Panel
        self._render_event_log(screen, rect=pygame.Rect(645, 360, 290, 185))

        # 8. Bottom Controls
        for _, btn in self.action_buttons:
            btn.draw(screen)

        for btn in self.control_buttons:
            btn.draw(screen)

        # 9. Finished Overlay / Results Button
        if self.session.is_finished:
            self._render_finished_overlay(screen)

    def _render_header(self, screen: pygame.Surface) -> None:
        """Render the top match info bar."""
        header_rect = pygame.Rect(20, 10, SCREEN_WIDTH - 40, 32)
        pygame.draw.rect(screen, COLOR_PANEL_BG, header_rect, border_radius=4)
        pygame.draw.rect(screen, COLOR_PANEL_BORDER, header_rect, width=1, border_radius=4)

        font = get_font(14, bold=True)
        state = self.session.state

        # Mode and Stadium info
        mode_str = "HUMAN VS AI" if self.mode == GameMode.HUMAN_VS_AI else "AI VS AI DUEL"
        stadium_str = state.stadium.stadium_type.name.replace("_", " ").title()
        left_text = f"MODE: {mode_str}   |   STADIUM: {stadium_str}"
        surf_left = font.render(left_text, True, COLOR_TEXT_SUBTITLE)
        screen.blit(surf_left, (35, 18))

        # Round & Time Countdown
        rem_time = max(0.0, 120.0 - state.elapsed_game_time)
        center_text = f"ROUND: {state.completed_rounds} / 40   |   TIME: {rem_time:.1f}s / 120s"
        surf_center = font.render(center_text, True, COLOR_TEXT_GOLD)
        center_rect = surf_center.get_rect(center=(SCREEN_WIDTH // 2, 26))
        screen.blit(surf_center, center_rect)

        # Match Status
        if self.session.is_finished:
            status_text = "STATUS: FINISHED"
            status_col = (255, 77, 79)
        elif self.session.is_paused:
            status_text = "STATUS: PAUSED"
            status_col = (250, 173, 20)
        else:
            status_text = "STATUS: ACTIVE"
            status_col = (82, 196, 26)
        surf_right = font.render(status_text, True, status_col)
        surf_right_rect = surf_right.get_rect(midright=(header_rect.right - 15, 26))
        screen.blit(surf_right, surf_right_rect)

    def _render_player_panel(
        self, screen: pygame.Surface, is_player_1: bool, rect: pygame.Rect
    ) -> None:
        """Render detailed status panel for one blade participant."""
        state = self.session.state
        blade = state.player_1_blade if is_player_1 else state.player_2_blade
        participant = self.session.participant_1 if is_player_1 else self.session.participant_2

        # Panel frame
        primary_col = COLOR_P1_PRIMARY if is_player_1 else COLOR_P2_PRIMARY
        title = participant.name
        Panel(rect, title=title).draw(screen)

        font_sm = get_font(12, bold=True)
        font_xs = get_font(11, bold=False)

        # Archetype Badge
        arch_col = ARCHETYPE_COLORS.get(blade.blade_type.name, COLOR_TEXT_WHITE)
        arch_surf = font_sm.render(blade.blade_type.name, True, arch_col)
        screen.blit(arch_surf, (rect.right - arch_surf.get_width() - 10, rect.y + 7))

        y_offset = rect.y + 35

        # Energy Bar
        lbl_e = font_xs.render("ENERGY", True, COLOR_TEXT_SUBTITLE)
        screen.blit(lbl_e, (rect.x + 10, y_offset))
        bar_e = ProgressBar(
            rect=pygame.Rect(rect.x + 65, y_offset, 210, 14),
            current_value=blade.current_energy,
            max_value=blade.max_energy,
            fill_color=(50, 180, 80),
            font_size=11,
        )
        bar_e.draw(screen)

        y_offset += 20

        # Stability Bar
        lbl_s = font_xs.render("STABILITY", True, COLOR_TEXT_SUBTITLE)
        screen.blit(lbl_s, (rect.x + 10, y_offset))
        bar_s = ProgressBar(
            rect=pygame.Rect(rect.x + 65, y_offset, 210, 14),
            current_value=blade.current_stability,
            max_value=blade.max_stability,
            fill_color=(60, 140, 240),
            font_size=11,
        )
        bar_s.draw(screen)

        y_offset += 22

        # Fuzzy Danger Assessment (Mamdani Model)
        danger: DangerAssessment = evaluate_blade_danger(blade, state.stadium.radius)
        danger_cfg = DANGER_THEMES.get(danger.level.name, DANGER_THEMES["LOW"])
        danger_col = danger_cfg["color"]  # type: ignore
        danger_lbl = danger_cfg["label"]  # type: ignore

        lbl_d = font_xs.render("DANGER:", True, COLOR_TEXT_SUBTITLE)
        screen.blit(lbl_d, (rect.x + 10, y_offset))

        # Non-color-only text badge with numeric rating
        badge_box = pygame.Rect(rect.x + 65, y_offset - 2, 75, 18)
        pygame.draw.rect(screen, (35, 42, 60), badge_box, border_radius=3)
        pygame.draw.rect(screen, danger_col, badge_box, width=1, border_radius=3)
        badge_str = f"{danger_lbl} ({danger.score:.0f})"
        badge_surf = font_xs.render(badge_str, True, danger_col)
        screen.blit(badge_surf, badge_surf.get_rect(center=badge_box.center))

        # Special Cooldown Status
        rem_cd = max(0.0, blade.special_ready_at - state.elapsed_game_time)
        sp_text = "SPECIAL: READY" if rem_cd <= 0.0 else f"SPECIAL: CD {rem_cd:.1f}s"
        sp_col = COLOR_TEXT_GOLD if rem_cd <= 0.0 else COLOR_TEXT_MUTED
        sp_surf = font_xs.render(sp_text, True, sp_col)
        screen.blit(sp_surf, (rect.x + 155, y_offset))

        y_offset += 24

        # AI Diagnostics (if participant provides diagnostics)
        diag = participant.last_diagnostics
        if diag is not None:
            # Diagnostics formatting
            if hasattr(diag, "best_action"):
                diag_str = f"AI: {diag.best_action.name} (val: {getattr(diag, 'root_value', 0.0):.2f})"
            elif isinstance(diag, dict):
                diag_str = f"AI: {diag.get('action', 'N/A')} ({diag.get('time', 0.0):.3f}s)"
            else:
                diag_str = f"AI: {str(diag)[:26]}"
            diag_surf = font_xs.render(diag_str, True, COLOR_TEXT_MUTED)
            screen.blit(diag_surf, (rect.x + 10, y_offset))

    def _render_event_log(self, screen: pygame.Surface, rect: pygame.Rect) -> None:
        """Render recent battle audit messages."""
        Panel(rect, title="COMBAT LOG").draw(screen)

        font = get_font(11, bold=False)
        visible_lines = self.event_log[-7:]
        line_y = rect.y + 34
        for msg in visible_lines:
            # Subtle color-coding
            if "shrank" in msg:
                col = (250, 140, 60)
            elif "Damage" in msg:
                col = (240, 180, 100)
            elif "FINISHED" in msg:
                col = (255, 100, 100)
            else:
                col = COLOR_TEXT_SUBTITLE
            surf = font.render(msg[:44], True, col)
            screen.blit(surf, (rect.x + 12, line_y))
            line_y += 20

    def _render_finished_overlay(self, screen: pygame.Surface) -> None:
        """Render victory notification and 'VIEW RESULTS' prompt."""
        res = self.session.state.result
        banner_rect = pygame.Rect(SCREEN_WIDTH // 2 - 200, 180, 400, 50)
        pygame.draw.rect(screen, (18, 22, 34), banner_rect, border_radius=6)
        pygame.draw.rect(screen, COLOR_PANEL_BORDER, banner_rect, width=2, border_radius=6)

        font = get_font(20, bold=True)
        if res is not None and res.winner_id is not None:
            winner_col = COLOR_P1_PRIMARY if res.winner_id == "player_1" else COLOR_P2_PRIMARY
            msg = f"{res.winner_id.upper()} VICTORY ({res.reason.name})"
        else:
            winner_col = COLOR_TEXT_GOLD
            msg = "MATCH DRAW (SIMULTANEOUS)"

        text_surf = font.render(msg, True, winner_col)
        screen.blit(text_surf, text_surf.get_rect(center=banner_rect.center))

        # View Results Button
        self.btn_view_results.draw(screen)
