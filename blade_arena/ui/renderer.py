"""Visual rendering systems for BLADE ARENA battle viewport.

Provides:
- ArenaRenderer: Geometry transformation and procedural drawing of stadium floors,
  boundaries, contour rings, and coordinate scaling for Classic Dish, Ice Rink, and Steep Bowl.
- BladeRenderer: Procedural multi-layer spinning tops with spinning rotors, stability-scaled
  angular velocity, archetype core accents, and player identification markings.
- CombatVFX: Particle and ring visual effects for attack impacts, dodge ghost trails,
  and stadium shrink boundary pulses.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

import pygame

from blade_arena.game.models import Action, BladeState, StadiumState, StadiumType
from blade_arena.ui.theme import (
    ARCHETYPE_COLORS,
    COLOR_P1_LIGHT,
    COLOR_P1_PRIMARY,
    COLOR_P2_LIGHT,
    COLOR_P2_PRIMARY,
    COLOR_TEXT_WHITE,
    STADIUM_THEMES,
    get_font,
)


class ArenaRenderer:
    """Translates Cartesian arena coordinates to screen pixels and renders stadium geometry."""

    def __init__(
        self,
        center_x: int = 340,
        center_y: int = 310,
        pixels_per_unit: float = 24.0,
    ) -> None:
        self.center_x: int = center_x
        self.center_y: int = center_y
        self.scale: float = pixels_per_unit

    def arena_to_screen(self, x: float, y: float) -> Tuple[int, int]:
        """Convert arena Cartesian coordinates (x, y) to screen pixel coordinates (sx, sy).

        In Cartesian coordinates, +y is upward; on screen, +y is downward.
        """
        sx = int(self.center_x + x * self.scale)
        sy = int(self.center_y - y * self.scale)
        return (sx, sy)

    def screen_to_arena(self, sx: int, sy: int) -> Tuple[float, float]:
        """Convert screen pixel coordinates to arena Cartesian coordinates."""
        x = (sx - self.center_x) / self.scale
        y = -(sy - self.center_y) / self.scale
        return (x, y)

    def radius_to_pixels(self, radius: float) -> int:
        """Convert arena radius units to integer pixel radius."""
        return max(1, int(radius * self.scale))

    def render(self, screen: pygame.Surface, stadium: StadiumState) -> None:
        """Draw stadium surface, contour rings, and active boundary."""
        stadium_name = stadium.stadium_type.name
        theme = STADIUM_THEMES.get(stadium_name, STADIUM_THEMES["CLASSIC_DISH"])

        fill_col = theme["fill"]
        ring_col = theme["floor_ring"]
        rim_col = theme["rim"]
        accent_col = theme["accent"]

        initial_px = self.radius_to_pixels(10.0)
        current_px = self.radius_to_pixels(stadium.radius)

        # 1. Base outer arena pit / floor background
        pygame.draw.circle(screen, (10, 12, 18), (self.center_x, self.center_y), initial_px + 8)
        pygame.draw.circle(screen, fill_col, (self.center_x, self.center_y), initial_px)

        # 2. Stadium specific decorative textures / rings
        if stadium.stadium_type == StadiumType.ICE_RINK:
            # Concentric ice glides and frosty radial spokes
            for r_unit in [2.0, 4.0, 6.0, 8.0]:
                px = self.radius_to_pixels(r_unit)
                pygame.draw.circle(screen, ring_col, (self.center_x, self.center_y), px, width=1)
            # Faint diagonal glint lines across ice
            for angle_deg in [30, 75, 120, 165, 210, 255, 300, 345]:
                rad = math.radians(angle_deg)
                x1 = int(self.center_x + math.cos(rad) * (initial_px * 0.2))
                y1 = int(self.center_y - math.sin(rad) * (initial_px * 0.2))
                x2 = int(self.center_x + math.cos(rad) * (initial_px * 0.95))
                y2 = int(self.center_y - math.sin(rad) * (initial_px * 0.95))
                pygame.draw.line(screen, (25, 45, 68), (x1, y1), (x2, y2), width=1)

        elif stadium.stadium_type == StadiumType.STEEP_BOWL:
            # Concentric elevation slope gradient rings
            for r_unit in [1.5, 3.0, 4.5, 6.0, 7.5, 9.0]:
                px = self.radius_to_pixels(r_unit)
                pygame.draw.circle(screen, ring_col, (self.center_x, self.center_y), px, width=2)
            # Center sinkhole / deep apex marker
            pygame.draw.circle(screen, (18, 14, 12), (self.center_x, self.center_y), self.radius_to_pixels(1.0))

        else:
            # Classic Dish concentric guide rings
            for r_unit in [2.0, 4.0, 6.0, 8.0]:
                px = self.radius_to_pixels(r_unit)
                pygame.draw.circle(screen, ring_col, (self.center_x, self.center_y), px, width=1)

        # 3. Outer maximum boundary reference (faint dashed or solid circle)
        pygame.draw.circle(screen, (40, 50, 70), (self.center_x, self.center_y), initial_px, width=1)

        # 4. Current active playable boundary ring
        pygame.draw.circle(screen, rim_col, (self.center_x, self.center_y), current_px, width=3)
        pygame.draw.circle(screen, accent_col, (self.center_x, self.center_y), current_px, width=1)

        # 5. Center crosshair
        pygame.draw.line(
            screen,
            (60, 75, 100),
            (self.center_x - 8, self.center_y),
            (self.center_x + 8, self.center_y),
            width=1,
        )
        pygame.draw.line(
            screen,
            (60, 75, 100),
            (self.center_x, self.center_y - 8),
            (self.center_x, self.center_y + 8),
            width=1,
        )


class BladeRenderer:
    """Procedurally renders multi-layer spinning tops with physical rotational animation."""

    def __init__(self, base_radius_px: int = 22) -> None:
        self.radius: int = base_radius_px
        self.rotation_angles: Dict[str, float] = {}

    def update(self, dt: float, blades: List[BladeState]) -> None:
        """Advance procedural spin rotation proportional to residual stability."""
        for blade in blades:
            pid = blade.player_id
            curr_angle = self.rotation_angles.get(pid, 0.0)
            # Angular velocity w: faster when stability is full, slows to a wobble when depleted
            stability_ratio = max(0.05, blade.current_stability / max(blade.max_stability, 1.0))
            w = 12.0 * stability_ratio  # radians per second
            self.rotation_angles[pid] = (curr_angle + w * dt) % (2.0 * math.pi)

    def render(
        self,
        screen: pygame.Surface,
        blade: BladeState,
        pos_screen: Tuple[int, int],
        is_player_1: bool,
    ) -> None:
        """Draw an original multi-layer spinning top at the given screen coordinates."""
        sx, sy = pos_screen
        rot = self.rotation_angles.get(blade.player_id, 0.0)

        # Color schemes
        primary_col = COLOR_P1_PRIMARY if is_player_1 else COLOR_P2_PRIMARY
        light_col = COLOR_P1_LIGHT if is_player_1 else COLOR_P2_LIGHT
        archetype_col = ARCHETYPE_COLORS.get(blade.blade_type.name, (180, 180, 180))

        # 1. Outer rim / gear teeth (6 triangular/trapezoid protrusions)
        num_teeth = 6
        teeth_points: List[Tuple[int, int]] = []
        for i in range(num_teeth * 2):
            ang = rot + (i * math.pi / num_teeth)
            r = self.radius if (i % 2 == 0) else self.radius - 4
            tx = int(sx + math.cos(ang) * r)
            ty = int(sy + math.sin(ang) * r)
            teeth_points.append((tx, ty))

        if len(teeth_points) >= 3:
            pygame.draw.polygon(screen, (35, 42, 58), teeth_points)
            pygame.draw.polygon(screen, primary_col, teeth_points, width=2)

        # 2. Main rotor ring
        pygame.draw.circle(screen, (22, 28, 40), (sx, sy), self.radius - 5)
        pygame.draw.circle(screen, primary_col, (sx, sy), self.radius - 5, width=2)

        # 3. Rotating inner rotor blades (3 blades)
        for i in range(3):
            blade_ang = rot + (i * 2.0 * math.pi / 3.0)
            bx1 = int(sx + math.cos(blade_ang) * 5)
            by1 = int(sy + math.sin(blade_ang) * 5)
            bx2 = int(sx + math.cos(blade_ang) * (self.radius - 6))
            by2 = int(sy + math.sin(blade_ang) * (self.radius - 6))
            pygame.draw.line(screen, light_col, (bx1, by1), (bx2, by2), width=3)

        # 4. Center power core gem
        core_r = 7
        pygame.draw.circle(screen, archetype_col, (sx, sy), core_r)
        pygame.draw.circle(screen, COLOR_TEXT_WHITE, (sx, sy), core_r, width=1)
        # Core highlight
        pygame.draw.circle(screen, (255, 255, 255), (sx - 2, sy - 2), 2)

        # 5. Player badge above top
        badge_text = "P1" if is_player_1 else "P2"
        font = get_font(13, bold=True)
        badge_surf = font.render(badge_text, True, light_col)
        badge_rect = badge_surf.get_rect(center=(sx, sy - self.radius - 10))
        # Small background capsule
        bg_rect = badge_rect.inflate(8, 2)
        pygame.draw.rect(screen, (15, 20, 32), bg_rect, border_radius=3)
        pygame.draw.rect(screen, primary_col, bg_rect, width=1, border_radius=3)
        screen.blit(badge_surf, badge_rect)


class CombatVFX:
    """Particle and ring visual effects system for attacks, dodges, and arena shrink."""

    def __init__(self) -> None:
        # Each effect: dict with type, pos, timer, max_time, params
        self.effects: List[Dict[str, Any]] = []

    def add_attack_impact(self, screen_pos: Tuple[int, int]) -> None:
        """Trigger an impact spark ring at the collision point."""
        self.effects.append({
            "type": "impact",
            "pos": screen_pos,
            "timer": 0.0,
            "max_time": 0.35,
        })

    def add_dodge_trail(
        self, start_pos: Tuple[int, int], end_pos: Tuple[int, int], is_p1: bool
    ) -> None:
        """Trigger a ghost trail showing evasion trajectory."""
        self.effects.append({
            "type": "dodge",
            "start": start_pos,
            "end": end_pos,
            "is_p1": is_p1,
            "timer": 0.0,
            "max_time": 0.40,
        })

    def add_shrink_pulse(self, center: Tuple[int, int], current_px: int) -> None:
        """Trigger an expanding/pulsing warning ring for arena boundary shrink."""
        self.effects.append({
            "type": "shrink",
            "center": center,
            "radius": current_px,
            "timer": 0.0,
            "max_time": 0.60,
        })

    def update(self, dt: float) -> None:
        """Advance timers and cull expired visual effects."""
        active: List[Dict[str, Any]] = []
        for fx in self.effects:
            fx["timer"] += dt
            if fx["timer"] < fx["max_time"]:
                active.append(fx)
        self.effects = active

    def render(self, screen: pygame.Surface) -> None:
        """Draw all active combat VFX."""
        for fx in self.effects:
            progress = fx["timer"] / fx["max_time"]
            fade = max(0.0, 1.0 - progress)

            if fx["type"] == "impact":
                sx, sy = fx["pos"]
                ring_r = int(6 + progress * 28)
                alpha_col = (int(255 * fade), int(200 * fade), int(50 * fade))
                pygame.draw.circle(screen, alpha_col, (sx, sy), ring_r, width=2)
                # Small spark rays
                for ang_deg in [0, 45, 90, 135, 180, 225, 270, 315]:
                    rad = math.radians(ang_deg)
                    p1x = int(sx + math.cos(rad) * (ring_r * 0.4))
                    p1y = int(sy + math.sin(rad) * (ring_r * 0.4))
                    p2x = int(sx + math.cos(rad) * (ring_r * 1.1))
                    p2y = int(sy + math.sin(rad) * (ring_r * 1.1))
                    pygame.draw.line(screen, alpha_col, (p1x, p1y), (p2x, p2y), width=1)

            elif fx["type"] == "dodge":
                x1, y1 = fx["start"]
                x2, y2 = fx["end"]
                trail_col = (
                    (int(100 * fade), int(180 * fade), int(255 * fade))
                    if fx["is_p1"]
                    else (int(255 * fade), int(120 * fade), int(120 * fade))
                )
                pygame.draw.line(screen, trail_col, (x1, y1), (x2, y2), width=3)
                # Ghost circle
                pygame.draw.circle(screen, trail_col, (x1, y1), 16, width=1)

            elif fx["type"] == "shrink":
                cx, cy = fx["center"]
                base_r = fx["radius"]
                pulse_r = int(base_r + progress * 20)
                pulse_col = (int(250 * fade), int(60 * fade), int(60 * fade))
                pygame.draw.circle(screen, pulse_col, (cx, cy), pulse_r, width=2)
