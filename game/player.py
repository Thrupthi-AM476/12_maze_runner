import pygame
from game.maze import CELL

SPEED = 3

class Player:
    def __init__(self, r, c):
        self.r = r
        self.c = c
        x = c * CELL + CELL // 2
        y = r * CELL + CELL // 2
        self.rect = pygame.Rect(x - 10, y - 10, 20, 20)
        self.color = (60, 120, 220)

    def get_cell(self):
        """Return the grid cell (row, col) the player's centre is in."""
        return self.rect.centery // CELL, self.rect.centerx // CELL

    def move(self, keys, walls, rows, cols):
        dx, dy = 0, 0
        if keys[pygame.K_LEFT]  or keys[pygame.K_a]: dx = -SPEED
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]: dx =  SPEED
        if keys[pygame.K_UP]    or keys[pygame.K_w]: dy = -SPEED
        if keys[pygame.K_DOWN]  or keys[pygame.K_s]: dy =  SPEED

        # Axis-separated so the player can slide along walls
        if dx != 0:
            new_rect = self.rect.move(dx, 0)
            if not self._hits_wall(new_rect, walls, rows, cols):
                self.rect = new_rect
        if dy != 0:
            new_rect = self.rect.move(0, dy)
            if not self._hits_wall(new_rect, walls, rows, cols):
                self.rect = new_rect

    # ── Wall collision ──────────────────────────────────────────────────────
    # Strategy: for each corner of the proposed rect find which cell it
    # occupies, then check if the player's bounding box *crosses* a wall
    # edge of that cell.  We compare the rect's edges to cell boundaries
    # rather than checking exact pixel equality (which fails at SPEED > 1).

    def _hits_wall(self, rect, walls, rows, cols):
        """
        Return True if `rect` overlaps any wall.
        walls[r][c] = [N, S, E, W]  (True = wall present)
          N=0 → top edge of cell,  S=1 → bottom edge
          E=2 → right edge,        W=3 → left edge
        """
        corners = [
            (rect.left,      rect.top),
            (rect.right - 1, rect.top),
            (rect.left,      rect.bottom - 1),
            (rect.right - 1, rect.bottom - 1),
        ]
        for px, py in corners:
            cr = py // CELL
            cc = px // CELL

            # Hard boundary – don't leave the grid
            if cr < 0 or cr >= rows or cc < 0 or cc >= cols:
                return True

            w = walls[cr][cc]
            cell_left  = cc * CELL
            cell_top   = cr * CELL
            cell_right  = cell_left + CELL   # exclusive pixel just outside
            cell_bottom = cell_top  + CELL

            # North wall: rect's top edge enters from above
            if w[0] and rect.top < cell_top and rect.bottom > cell_top:
                return True
            # South wall: rect's bottom edge crosses into cell below
            if w[1] and rect.top < cell_bottom and rect.bottom > cell_bottom:
                return True
            # West wall: rect's left edge enters from left
            if w[3] and rect.left < cell_left and rect.right > cell_left:
                return True
            # East wall: rect's right edge crosses into cell to the right
            if w[2] and rect.left < cell_right and rect.right > cell_right:
                return True

        return False

    def draw(self, screen):
        pygame.draw.ellipse(screen, self.color, self.rect)
