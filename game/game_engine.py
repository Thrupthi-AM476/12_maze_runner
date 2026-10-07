import pygame
import time
import json
import os
from collections import deque
from game.maze import generate_maze, CELL
from game.player import Player

FPS = 60
BG         = (240, 235, 220)
WALL_COLOR = (40,  40,  60)
EXIT_COLOR = (80, 200,  80)
HINT_COLOR = (255, 215,   0, 160)   # semi-transparent gold for BFS path
FOG_COLOR  = (15,  15,  25, 230)    # near-black fog overlay

LEADERBOARD_FILE = "leaderboard.json"
MAX_SCORES       = 5
FOG_RADIUS       = 3                # cells visible around player (fog of war)

# Difficulty presets — (label, cols, rows) used for the selection screen
DIFFICULTIES = [
    ("Easy",   10,  8),
    ("Medium", 15, 13),
    ("Hard",   20, 18),
]


# ── BFS solver ────────────────────────────────────────────────────────────────

def bfs_path(walls, rows, cols, start, goal):
    """
    Return list of (r,c) tuples from start to goal (inclusive), or []
    if no path exists.  Neighbours are reachable cells (no wall between them).
    walls[r][c] = [N, S, E, W]
    Directions: N=(-1,0,wall_idx=0)  S=(+1,0,1)  E=(0,+1,2)  W=(0,-1,3)
    """
    directions = [(-1, 0, 0), (1, 0, 1), (0, 1, 2), (0, -1, 3)]
    queue    = deque([start])
    came_from = {start: None}

    while queue:
        r, c = queue.popleft()
        if (r, c) == goal:
            # reconstruct path
            path, cur = [], (r, c)
            while cur is not None:
                path.append(cur)
                cur = came_from[cur]
            path.reverse()
            return path
        for dr, dc, wall_idx in directions:
            if walls[r][c][wall_idx]:   # wall present → can't cross
                continue
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols and (nr, nc) not in came_from:
                came_from[(nr, nc)] = (r, c)
                queue.append((nr, nc))
    return []


# ── Leaderboard helpers ────────────────────────────────────────────────────────

def load_leaderboard():
    """Load scores from leaderboard.json. Returns [] if file missing or corrupt."""
    if os.path.exists(LEADERBOARD_FILE):
        try:
            with open(LEADERBOARD_FILE, "r") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
        except (json.JSONDecodeError, IOError):
            pass
    return []


def save_leaderboard(scores):
    with open(LEADERBOARD_FILE, "w") as f:
        json.dump(scores, f, indent=2)


def add_score(elapsed):
    """Add a completion time, keep only top MAX_SCORES, persist to JSON."""
    scores = load_leaderboard()
    scores.append(round(elapsed, 2))
    scores.sort()
    scores = scores[:MAX_SCORES]
    save_leaderboard(scores)
    return scores


# ── GameEngine ─────────────────────────────────────────────────────────────────

class GameEngine:
    def __init__(self):
        pygame.init()
        # Start with a mid-size screen; resized when difficulty is chosen
        self._init_fonts()
        self.screen = pygame.display.set_mode((600, 500))
        pygame.display.set_caption("Maze Runner")
        self.clock  = pygame.time.Clock()

        # Game state flags
        self.cols        = 15
        self.rows        = 13
        self.state       = "difficulty"   # "difficulty" | "playing" | "won"
        self.hint_on     = False
        self.hint_path   = []
        self.leaderboard = []
        self.elapsed     = 0.0

    # ── Font setup ──────────────────────────────────────────────────────────

    def _init_fonts(self):
        self.font     = pygame.font.SysFont("monospace", 22)
        self.big_font = pygame.font.SysFont("monospace", 36, bold=True)
        self.sm_font  = pygame.font.SysFont("monospace", 18)

    # ── Reset / start a maze ────────────────────────────────────────────────

    def _start_maze(self, cols, rows):
        self.cols  = cols
        self.rows  = rows
        width  = cols * CELL
        height = rows * CELL + 60
        self.screen = pygame.display.set_mode((width, height))

        self.walls      = generate_maze(cols, rows)
        self.player     = Player(0, 0)
        self.exit_rect  = pygame.Rect(
            (cols - 1) * CELL + 5, (rows - 1) * CELL + 5, CELL - 10, CELL - 10
        )
        self.start_time = time.time()
        self.elapsed    = 0.0
        self.won        = False
        self.hint_on    = False
        self.hint_path  = []
        self.state      = "playing"

    def reset(self):
        """Re-generate maze with the same difficulty."""
        self._start_maze(self.cols, self.rows)

    # ── Event handling ──────────────────────────────────────────────────────

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False

            if event.type == pygame.KEYDOWN:
                if self.state == "playing":
                    if event.key == pygame.K_r:
                        self.reset()
                    elif event.key == pygame.K_h:
                        self._toggle_hint()
                elif self.state == "won":
                    if event.key == pygame.K_r:
                        self.state = "difficulty"

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.state == "difficulty":
                    self._handle_difficulty_click(event.pos)

        return True

    def _toggle_hint(self):
        self.hint_on = not self.hint_on
        if self.hint_on:
            start = (0, 0)
            goal  = (self.rows - 1, self.cols - 1)
            self.hint_path = bfs_path(self.walls, self.rows, self.cols, start, goal)
        else:
            self.hint_path = []

    # ── Update ──────────────────────────────────────────────────────────────

    def update(self):
        if self.state != "playing":
            return
        keys = pygame.key.get_pressed()
        self.player.move(keys, self.walls, self.rows, self.cols)
        self.elapsed = time.time() - self.start_time
        if self.player.rect.colliderect(self.exit_rect):
            self.leaderboard = add_score(self.elapsed)
            self.won  = True
            self.state = "won"

    # ── Drawing helpers ─────────────────────────────────────────────────────

    def _draw_maze(self):
        wall_w = 3
        for r in range(self.rows):
            for c in range(self.cols):
                x, y = c * CELL, r * CELL
                w = self.walls[r][c]
                if w[0]: pygame.draw.line(self.screen, WALL_COLOR, (x, y),          (x + CELL, y),          wall_w)
                if w[1]: pygame.draw.line(self.screen, WALL_COLOR, (x, y + CELL),   (x + CELL, y + CELL),   wall_w)
                if w[2]: pygame.draw.line(self.screen, WALL_COLOR, (x + CELL, y),   (x + CELL, y + CELL),   wall_w)
                if w[3]: pygame.draw.line(self.screen, WALL_COLOR, (x, y),          (x, y + CELL),          wall_w)

    def _draw_hint(self):
        if not self.hint_on or not self.hint_path:
            return
        surf = pygame.Surface((self.cols * CELL, self.rows * CELL), pygame.SRCALPHA)
        for r, c in self.hint_path:
            pygame.draw.rect(surf, HINT_COLOR, (c * CELL + 4, r * CELL + 4, CELL - 8, CELL - 8), border_radius=4)
        self.screen.blit(surf, (0, 0))

    def _draw_fog(self):
        """
        Fog of war: cover the entire maze with a dark overlay, then punch
        a transparent circular hole around the player so only nearby cells
        are visible (radius = FOG_RADIUS cells).
        """
        width  = self.cols * CELL
        height = self.rows * CELL
        fog = pygame.Surface((width, height), pygame.SRCALPHA)
        fog.fill(FOG_COLOR)

        # Reveal radius: FOG_RADIUS full cells + half a cell so the
        # player's own cell is always fully visible
        reveal_px = int(FOG_RADIUS * CELL + CELL // 2)
        cx = self.player.rect.centerx
        cy = self.player.rect.centery

        # Draw a fully transparent circle to "erase" the fog in that area
        pygame.draw.circle(fog, (0, 0, 0, 0), (cx, cy), reveal_px)
        self.screen.blit(fog, (0, 0))

    def _draw_hud(self):
        hud_y = self.rows * CELL
        hud   = pygame.Rect(0, hud_y, self.cols * CELL, 60)
        pygame.draw.rect(self.screen, (30, 30, 50), hud)
        hints = "H=Hint  R=New"
        txt = self.font.render(f"Time: {self.elapsed:.1f}s   {hints}", True, (200, 200, 200))
        self.screen.blit(txt, (10, hud_y + 18))

    def _draw_win_screen(self):
        width  = self.cols * CELL
        height = self.rows * CELL
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        panel_w, panel_h = 340, 260 + MAX_SCORES * 28
        px = width  // 2 - panel_w // 2
        py = height // 2 - panel_h // 2
        pygame.draw.rect(self.screen, (20, 20, 40), (px, py, panel_w, panel_h), border_radius=10)
        pygame.draw.rect(self.screen, (80, 200, 80), (px, py, panel_w, panel_h), 3, border_radius=10)

        msg  = self.big_font.render("YOU WIN!", True, (80, 240, 80))
        time_txt = self.font.render(f"Your time: {self.elapsed:.2f}s", True, (230, 230, 100))
        lb_title = self.font.render("── LEADERBOARD ──", True, (200, 200, 200))
        self.screen.blit(msg,     (width // 2 - msg.get_width() // 2,     py + 18))
        self.screen.blit(time_txt,(width // 2 - time_txt.get_width() // 2, py + 64))
        self.screen.blit(lb_title,(width // 2 - lb_title.get_width() // 2, py + 102))

        for i, score in enumerate(self.leaderboard):
            rank_color = (255, 215, 0) if i == 0 else (200, 200, 200)
            s = self.font.render(f"  {i+1}.  {score:.2f} s", True, rank_color)
            self.screen.blit(s, (width // 2 - s.get_width() // 2, py + 138 + i * 28))

        sub = self.sm_font.render("Press R to return to difficulty", True, (150, 150, 150))
        self.screen.blit(sub, (width // 2 - sub.get_width() // 2, py + panel_h - 30))

    # ── Difficulty screen ───────────────────────────────────────────────────

    def _handle_difficulty_click(self, pos):
        for i, (label, cols, rows) in enumerate(DIFFICULTIES):
            btn = self._difficulty_button_rect(i)
            if btn.collidepoint(pos):
                self._start_maze(cols, rows)
                return

    def _difficulty_button_rect(self, index):
        sw, sh = self.screen.get_size()
        btn_w, btn_h = 220, 70
        gap = 20
        total_h = len(DIFFICULTIES) * btn_h + (len(DIFFICULTIES) - 1) * gap
        start_y = sh // 2 - total_h // 2 + 30
        x = sw // 2 - btn_w // 2
        y = start_y + index * (btn_h + gap)
        return pygame.Rect(x, y, btn_w, btn_h)

    def _draw_difficulty_screen(self):
        sw, sh = self.screen.get_size()
        self.screen.fill((15, 15, 30))

        title = self.big_font.render("MAZE RUNNER", True, (80, 200, 255))
        sub   = self.font.render("Select Difficulty", True, (180, 180, 200))
        self.screen.blit(title, (sw // 2 - title.get_width() // 2, 60))
        self.screen.blit(sub,   (sw // 2 - sub.get_width() // 2,   115))

        mouse = pygame.mouse.get_pos()
        dim_labels = [f"{c} × {r}" for _, c, r in DIFFICULTIES]
        diff_colors = [(60, 180, 80), (220, 180, 40), (220, 60, 60)]

        for i, (label, cols, rows) in enumerate(DIFFICULTIES):
            btn = self._difficulty_button_rect(i)
            hovered = btn.collidepoint(mouse)
            color = diff_colors[i]
            bg    = tuple(min(255, v + 40) for v in color) if hovered else (30, 30, 50)
            border= color

            pygame.draw.rect(self.screen, bg,     btn, border_radius=10)
            pygame.draw.rect(self.screen, border, btn, 3, border_radius=10)

            lbl  = self.font.render(label, True, color if not hovered else (255, 255, 255))
            size = self.sm_font.render(f"{cols} x {rows}", True, (180, 180, 180))
            self.screen.blit(lbl,  (btn.centerx - lbl.get_width() // 2,  btn.centery - 16))
            self.screen.blit(size, (btn.centerx - size.get_width() // 2, btn.centery + 8))

    # ── Main draw ───────────────────────────────────────────────────────────

    def draw(self):
        if self.state == "difficulty":
            self._draw_difficulty_screen()
            pygame.display.flip()
            return

        self.screen.fill(BG)
        self._draw_maze()

        # BFS hint (draw before fog so it's visible under it but above maze)
        self._draw_hint()

        # Exit marker
        pygame.draw.rect(self.screen, EXIT_COLOR, self.exit_rect, border_radius=4)
        ex_label = self.font.render("EXIT", True, (20, 80, 20))
        self.screen.blit(ex_label, (self.exit_rect.x + 2, self.exit_rect.y + 4))

        # Player
        self.player.draw(self.screen)

        # Fog of war (drawn over everything except HUD)
        self._draw_fog()

        # HUD strip below maze
        self._draw_hud()

        if self.state == "won":
            self._draw_win_screen()

        pygame.display.flip()

    # ── Main loop ───────────────────────────────────────────────────────────

    def run(self):
        running = True
        while running:
            running = self.handle_events()
            self.update()
            self.draw()
            self.clock.tick(FPS)
        pygame.quit()
