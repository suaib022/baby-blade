"""Match Setup scene for BLADE ARENA.

Allows interactive configuration of game mode, blade archetypes, AI architectures,
difficulty ratings, stadium variations, and player starting sides.
"""

from __future__ import annotations

from typing import Any, List, Optional

import pygame

from blade_arena.game.models import BladeType, StadiumType
from blade_arena.orchestration.participants import (
    HumanParticipant,
    create_ai_participant,
)
from blade_arena.orchestration.session import GameMode, MatchSession, SessionConfig
from blade_arena.ui.scenes.base import Scene
from blade_arena.ui.theme import (
    COLOR_BG,
    COLOR_P1_PRIMARY,
    COLOR_P2_PRIMARY,
    COLOR_PANEL_BG,
    COLOR_PANEL_BORDER,
    COLOR_TEXT_GOLD,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_SUBTITLE,
    COLOR_TEXT_WHITE,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    get_font,
)
from blade_arena.ui.widgets import Button, Panel, ToggleGroup


class MatchSetupScene(Scene):
    """Configuration view before launching a live match session."""

    def __init__(self, initial_mode: GameMode = GameMode.HUMAN_VS_AI) -> None:
        self.mode: GameMode = initial_mode

        # Human vs AI options
        self.human_side: str = "P1"  # "P1" (Left) or "P2" (Right)
        self.human_blade: BladeType = BladeType.BALANCED
        self.ai_agent: str = "ironclad"
        self.ai_diff: str = "medium"
        self.ai_blade: BladeType = BladeType.BALANCED

        # AI vs AI options
        self.a1_agent: str = "ironclad"
        self.a1_diff: str = "medium"
        self.a1_blade: BladeType = BladeType.BALANCED
        self.a2_agent: str = "cyclone"
        self.a2_diff: str = "medium"
        self.a2_blade: BladeType = BladeType.BALANCED

        # Stadium option
        self.stadium: StadiumType = StadiumType.CLASSIC_DISH

        # UI controls
        self.toggles: List[ToggleGroup] = []
        self.buttons: List[Button] = []
        self._build_widgets()

    def _build_widgets(self) -> None:
        """Construct interactive UI elements."""
        self.toggles.clear()
        self.buttons.clear()

        # Top Mode Selector
        mode_options = [
            ("Human vs AI", GameMode.HUMAN_VS_AI),
            ("AI vs AI", GameMode.AI_VS_AI),
        ]
        self.mode_toggle = ToggleGroup(
            rect=pygame.Rect(SCREEN_WIDTH // 2 - 180, 55, 360, 34),
            options=mode_options,
            initial_value=self.mode,
            on_change=self._on_mode_change,
            horizontal=True,
        )
        self.toggles.append(self.mode_toggle)

        blade_opts = [
            ("Balanced", BladeType.BALANCED),
            ("Attacker", BladeType.ATTACKER),
            ("Defender", BladeType.DEFENDER),
            ("Stamina", BladeType.STAMINA),
        ]
        agent_opts = [("Ironclad (Minimax)", "ironclad"), ("Cyclone (MCTS)", "cyclone")]
        diff_opts = [("Easy", "easy"), ("Medium", "medium"), ("Hard", "hard")]

        if self.mode == GameMode.HUMAN_VS_AI:
            # Human Side Toggle
            side_opts = [("Player 1 (Left)", "P1"), ("Player 2 (Right)", "P2")]
            self.toggles.append(
                ToggleGroup(
                    rect=pygame.Rect(60, 150, 400, 32),
                    options=side_opts,
                    initial_value=self.human_side,
                    on_change=lambda val: setattr(self, "human_side", val),
                )
            )

            # Human Blade Archetype
            self.toggles.append(
                ToggleGroup(
                    rect=pygame.Rect(60, 230, 400, 32),
                    options=blade_opts,
                    initial_value=self.human_blade,
                    on_change=lambda val: setattr(self, "human_blade", val),
                )
            )

            # AI Opponent Architecture
            self.toggles.append(
                ToggleGroup(
                    rect=pygame.Rect(500, 150, 400, 32),
                    options=agent_opts,
                    initial_value=self.ai_agent,
                    on_change=lambda val: setattr(self, "ai_agent", val),
                )
            )

            # AI Opponent Difficulty
            self.toggles.append(
                ToggleGroup(
                    rect=pygame.Rect(500, 230, 400, 32),
                    options=diff_opts,
                    initial_value=self.ai_diff,
                    on_change=lambda val: setattr(self, "ai_diff", val),
                )
            )

            # AI Blade Archetype
            self.toggles.append(
                ToggleGroup(
                    rect=pygame.Rect(500, 310, 400, 32),
                    options=blade_opts,
                    initial_value=self.ai_blade,
                    on_change=lambda val: setattr(self, "ai_blade", val),
                )
            )

        else:
            # AI vs AI Mode
            # Agent 1 Architecture & Difficulty & Blade
            self.toggles.append(
                ToggleGroup(
                    rect=pygame.Rect(60, 150, 400, 32),
                    options=agent_opts,
                    initial_value=self.a1_agent,
                    on_change=lambda val: setattr(self, "a1_agent", val),
                )
            )
            self.toggles.append(
                ToggleGroup(
                    rect=pygame.Rect(60, 230, 400, 32),
                    options=diff_opts,
                    initial_value=self.a1_diff,
                    on_change=lambda val: setattr(self, "a1_diff", val),
                )
            )
            self.toggles.append(
                ToggleGroup(
                    rect=pygame.Rect(60, 310, 400, 32),
                    options=blade_opts,
                    initial_value=self.a1_blade,
                    on_change=lambda val: setattr(self, "a1_blade", val),
                )
            )

            # Agent 2 Architecture & Difficulty & Blade
            self.toggles.append(
                ToggleGroup(
                    rect=pygame.Rect(500, 150, 400, 32),
                    options=agent_opts,
                    initial_value=self.a2_agent,
                    on_change=lambda val: setattr(self, "a2_agent", val),
                )
            )
            self.toggles.append(
                ToggleGroup(
                    rect=pygame.Rect(500, 230, 400, 32),
                    options=diff_opts,
                    initial_value=self.a2_diff,
                    on_change=lambda val: setattr(self, "a2_diff", val),
                )
            )
            self.toggles.append(
                ToggleGroup(
                    rect=pygame.Rect(500, 310, 400, 32),
                    options=blade_opts,
                    initial_value=self.a2_blade,
                    on_change=lambda val: setattr(self, "a2_blade", val),
                )
            )

        # Stadium Selector (Shared)
        stadium_opts = [
            ("Classic Dish", StadiumType.CLASSIC_DISH),
            ("Ice Rink (1.25x Move/Push)", StadiumType.ICE_RINK),
            ("Steep Bowl (Inward Drift)", StadiumType.STEEP_BOWL),
        ]
        self.toggles.append(
            ToggleGroup(
                rect=pygame.Rect(180, 450, 600, 34),
                options=stadium_opts,
                initial_value=self.stadium,
                on_change=lambda val: setattr(self, "stadium", val),
            )
        )

        # Action Buttons
        self.btn_back = Button(
            rect=pygame.Rect(60, 560, 180, 44),
            text="Back",
            shortcut_text="[ESC]",
            shortcut_key=pygame.K_ESCAPE,
            font_size=16,
        )
        self.btn_start = Button(
            rect=pygame.Rect(SCREEN_WIDTH - 280, 560, 220, 44),
            text="START MATCH",
            shortcut_text="[Enter]",
            shortcut_key=pygame.K_RETURN,
            font_size=18,
            custom_bg=(30, 100, 60),
            custom_border=(60, 190, 100),
        )
        self.buttons.extend([self.btn_back, self.btn_start])

    def _on_mode_change(self, new_mode: GameMode) -> None:
        """Handle switching between Human vs AI and AI vs AI."""
        self.mode = new_mode
        self._build_widgets()

    def handle_event(self, event: pygame.event.Event) -> Optional[Scene]:
        """Handle input and scene transitions."""
        for toggle in self.toggles:
            toggle.handle_event(event)

        if self.btn_back.handle_event(event):
            from blade_arena.ui.scenes.main_menu import MainMenuScene

            return MainMenuScene()

        if self.btn_start.handle_event(event):
            return self._launch_match()

        return None

    def _launch_match(self) -> Scene:
        """Instantiate real match session and transition to BattleScene."""
        from blade_arena.ui.scenes.battle import BattleScene

        if self.mode == GameMode.HUMAN_VS_AI:
            if self.human_side == "P1":
                p1 = HumanParticipant("Player 1 (Human)")
                p2 = create_ai_participant(
                    f"Player 2 ({self.ai_agent.title()})",
                    agent_type=self.ai_agent,
                    difficulty=self.ai_diff,
                    player_id="player_2",
                )
                p1_blade = self.human_blade
                p2_blade = self.ai_blade
            else:
                p1 = create_ai_participant(
                    f"Player 1 ({self.ai_agent.title()})",
                    agent_type=self.ai_agent,
                    difficulty=self.ai_diff,
                    player_id="player_1",
                )
                p2 = HumanParticipant("Player 2 (Human)")
                p1_blade = self.ai_blade
                p2_blade = self.human_blade
        else:
            p1 = create_ai_participant(
                f"P1 ({self.a1_agent.title()})",
                agent_type=self.a1_agent,
                difficulty=self.a1_diff,
                player_id="player_1",
            )
            p2 = create_ai_participant(
                f"P2 ({self.a2_agent.title()})",
                agent_type=self.a2_agent,
                difficulty=self.a2_diff,
                player_id="player_2",
            )
            p1_blade = self.a1_blade
            p2_blade = self.a2_blade

        config = SessionConfig(
            mode=self.mode,
            player_1_blade=p1_blade,
            player_2_blade=p2_blade,
            stadium_type=self.stadium,
        )
        session = MatchSession(p1, p2, config=config)
        return BattleScene(session=session)

    def update(self, dt: float) -> Optional[Scene]:
        """Update animations."""
        return None

    def render(self, screen: pygame.Surface) -> None:
        """Render the setup view."""
        screen.fill(COLOR_BG)

        # Title
        font_title = get_font(28, bold=True)
        title_surf = font_title.render("MATCH SETUP", True, COLOR_TEXT_WHITE)
        title_rect = title_surf.get_rect(center=(SCREEN_WIDTH // 2, 28))
        screen.blit(title_surf, title_rect)

        # Draw Mode Toggle
        self.mode_toggle.draw(screen)

        # Section Panels / Headers
        font_h = get_font(16, bold=True)
        font_lbl = get_font(13, bold=False)

        # Left Column Panel (Player 1 / Human)
        p1_title = "HUMAN OPERATOR" if self.mode == GameMode.HUMAN_VS_AI else "PLAYER 1 (LEFT)"
        Panel(pygame.Rect(45, 105, 430, 260), title=p1_title).draw(screen)

        # Right Column Panel (Player 2 / AI)
        p2_title = "AI OPPONENT" if self.mode == GameMode.HUMAN_VS_AI else "PLAYER 2 (RIGHT)"
        Panel(pygame.Rect(485, 105, 430, 260), title=p2_title).draw(screen)

        if self.mode == GameMode.HUMAN_VS_AI:
            lbl1 = font_lbl.render("Starting Side:", True, COLOR_TEXT_SUBTITLE)
            screen.blit(lbl1, (60, 132))
            lbl2 = font_lbl.render("Blade Archetype:", True, COLOR_TEXT_SUBTITLE)
            screen.blit(lbl2, (60, 212))

            lbl3 = font_lbl.render("AI Agent Architecture:", True, COLOR_TEXT_SUBTITLE)
            screen.blit(lbl3, (500, 132))
            lbl4 = font_lbl.render("AI Difficulty:", True, COLOR_TEXT_SUBTITLE)
            screen.blit(lbl4, (500, 212))
            lbl5 = font_lbl.render("AI Blade Archetype:", True, COLOR_TEXT_SUBTITLE)
            screen.blit(lbl5, (500, 292))
        else:
            lbl1 = font_lbl.render("Architecture:", True, COLOR_TEXT_SUBTITLE)
            screen.blit(lbl1, (60, 132))
            lbl2 = font_lbl.render("Difficulty:", True, COLOR_TEXT_SUBTITLE)
            screen.blit(lbl2, (60, 212))
            lbl3 = font_lbl.render("Blade Archetype:", True, COLOR_TEXT_SUBTITLE)
            screen.blit(lbl3, (60, 292))

            lbl4 = font_lbl.render("Architecture:", True, COLOR_TEXT_SUBTITLE)
            screen.blit(lbl4, (500, 132))
            lbl5 = font_lbl.render("Difficulty:", True, COLOR_TEXT_SUBTITLE)
            screen.blit(lbl5, (500, 212))
            lbl6 = font_lbl.render("Blade Archetype:", True, COLOR_TEXT_SUBTITLE)
            screen.blit(lbl6, (500, 292))

        # Stadium Panel
        Panel(pygame.Rect(160, 410, 640, 95), title="STADIUM ARENA").draw(screen)
        lbl_s = font_lbl.render("Select Stadium Environment:", True, COLOR_TEXT_SUBTITLE)
        screen.blit(lbl_s, (180, 432))

        # Draw all toggles
        for t in self.toggles:
            t.draw(screen)

        # Draw action buttons
        for b in self.buttons:
            b.draw(screen)
