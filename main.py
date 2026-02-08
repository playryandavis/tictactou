import math
import random
import sys
from dataclasses import dataclass

import pygame

BOARD_SIZE = 20
VIEW_SIZE = 3
VISIBLE_SIZE = 5
CELL_SIZE = 32
MARGIN = 30
SIDE_PANEL = 240
SCREEN_WIDTH = VISIBLE_SIZE * CELL_SIZE + MARGIN * 2 + SIDE_PANEL
SCREEN_HEIGHT = VISIBLE_SIZE * CELL_SIZE + MARGIN * 2 + 80

BG_COLOR = (18, 18, 24)
GRID_COLOR = (52, 52, 64)
X_COLOR = (231, 90, 82)
O_COLOR = (90, 182, 231)
VIEW_COLOR = (238, 204, 98)
STRIP_COLOR = (120, 220, 160)
TEXT_COLOR = (235, 235, 240)
PANEL_COLOR = (30, 30, 40)

DIRECTIONS = {
    "up": (0, -1),
    "down": (0, 1),
    "left": (-1, 0),
    "right": (1, 0),
}


@dataclass
class GameState:
    board: list
    view_x: int
    view_y: int
    current: str
    strip_cells: list
    game_over: bool
    winner: str | None
    message: str


def new_game() -> GameState:
    board = [[None for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
    start = (BOARD_SIZE - VIEW_SIZE) // 2
    return GameState(
        board=board,
        view_x=start,
        view_y=start,
        current="X",
        strip_cells=[],
        game_over=False,
        winner=None,
        message="",
    )


def in_bounds(x: int, y: int) -> bool:
    return 0 <= x < BOARD_SIZE and 0 <= y < BOARD_SIZE


def viewport_cells(view_x: int, view_y: int) -> list:
    return [
        (view_x + dx, view_y + dy)
        for dy in range(VIEW_SIZE)
        for dx in range(VIEW_SIZE)
    ]


def revealed_strip(old_x: int, old_y: int, new_x: int, new_y: int) -> list:
    if new_x > old_x:
        col = new_x + VIEW_SIZE - 1
        return [(col, new_y + dy) for dy in range(VIEW_SIZE)]
    if new_x < old_x:
        col = new_x
        return [(col, new_y + dy) for dy in range(VIEW_SIZE)]
    if new_y > old_y:
        row = new_y + VIEW_SIZE - 1
        return [(new_x + dx, row) for dx in range(VIEW_SIZE)]
    if new_y < old_y:
        row = new_y
        return [(new_x + dx, row) for dx in range(VIEW_SIZE)]
    return []


def empty_cells(board: list, cells: list) -> list:
    return [cell for cell in cells if board[cell[1]][cell[0]] is None]


def check_winner(board: list) -> str | None:
    for y in range(BOARD_SIZE):
        for x in range(BOARD_SIZE):
            symbol = board[y][x]
            if symbol is None:
                continue
            for dx, dy in [(1, 0), (0, 1), (1, 1), (1, -1)]:
                if all(
                    in_bounds(x + i * dx, y + i * dy)
                    and board[y + i * dy][x + i * dx] == symbol
                    for i in range(3)
                ):
                    return symbol
    return None


def immediate_win_cells(board: list, symbol: str) -> set:
    wins = set()
    for y in range(BOARD_SIZE):
        for x in range(BOARD_SIZE):
            if board[y][x] is not None:
                continue
            board[y][x] = symbol
            if check_winner(board) == symbol:
                wins.add((x, y))
            board[y][x] = None
    return wins


def clamp(value: int, min_value: int, max_value: int) -> int:
    return max(min_value, min(value, max_value))


def line_score(board: list, x: int, y: int, symbol: str) -> int:
    score = 0
    for dx, dy in [(1, 0), (0, 1), (1, 1), (1, -1)]:
        count = 1
        for direction in (1, -1):
            step = 1
            while True:
                nx = x + dx * step * direction
                ny = y + dy * step * direction
                if not in_bounds(nx, ny):
                    break
                if board[ny][nx] != symbol:
                    break
                count += 1
                step += 1
        score += count * count
    return score


def center_bias(x: int, y: int) -> float:
    center = (BOARD_SIZE - 1) / 2
    dist = math.hypot(x - center, y - center)
    return -dist


def evaluate_move(board: list, move: str, view_x: int, view_y: int) -> tuple:
    dx, dy = DIRECTIONS[move]
    new_x = view_x + dx
    new_y = view_y + dy
    score = center_bias(new_x + 1, new_y + 1) * 5
    return score, (new_x, new_y)


def evaluate_stay(board: list, strip: list) -> tuple:
    if not strip:
        return -1e9, None
    empties = empty_cells(board, strip)
    if not empties:
        return -5_000, None

    cpu_symbol = "O"
    player_symbol = "X"
    player_wins = immediate_win_cells(board, player_symbol)

    best_score = -1e9
    best_placements = []
    for placement in empties:
        px, py = placement
        board[py][px] = cpu_symbol
        if check_winner(board) == cpu_symbol:
            score = 1_000_000
        else:
            score = 0
            if placement in player_wins:
                score += 200_000
            score += line_score(board, px, py, cpu_symbol) * 8
            score += line_score(board, px, py, player_symbol) * 3
            score += center_bias(px, py) * 5
        board[py][px] = None

        if score > best_score:
            best_score = score
            best_placements = [placement]
        elif score == best_score:
            best_placements.append(placement)

    return best_score, random.choice(best_placements)


def cpu_take_turn(state: GameState) -> None:
    best_score = -1e9
    candidates = []
    stay_score, stay_placement = evaluate_stay(state.board, state.strip_cells)
    if stay_score > best_score:
        best_score = stay_score
        candidates = [("stay", stay_placement)]
    elif stay_score == best_score:
        candidates.append(("stay", stay_placement))

    for move in DIRECTIONS:
        dx, dy = DIRECTIONS[move]
        new_x = state.view_x + dx
        new_y = state.view_y + dy
        if not (0 <= new_x <= BOARD_SIZE - VIEW_SIZE and 0 <= new_y <= BOARD_SIZE - VIEW_SIZE):
            continue
        score, (nx, ny) = evaluate_move(state.board, move, state.view_x, state.view_y)
        if score > best_score:
            best_score = score
            candidates = [("move", (nx, ny))]
        elif score == best_score:
            candidates.append(("move", (nx, ny)))

    if not candidates:
        return

    action, payload = random.choice(candidates)
    if action == "stay" and payload:
        px, py = payload
        state.board[py][px] = "O"
        winner = check_winner(state.board)
        if winner:
            state.game_over = True
            state.winner = winner
            state.message = "CPU wins!"
            return
        state.strip_cells = []
    elif action == "move":
        nx, ny = payload
        state.strip_cells = revealed_strip(state.view_x, state.view_y, nx, ny)
        state.view_x = nx
        state.view_y = ny

    state.current = "X"


def move_view(state: GameState, move: str) -> bool:
    dx, dy = DIRECTIONS[move]
    new_x = state.view_x + dx
    new_y = state.view_y + dy
    if not (0 <= new_x <= BOARD_SIZE - VIEW_SIZE and 0 <= new_y <= BOARD_SIZE - VIEW_SIZE):
        return False
    strip = revealed_strip(state.view_x, state.view_y, new_x, new_y)
    state.view_x = new_x
    state.view_y = new_y
    state.strip_cells = strip
    end_turn(state)
    return True


def end_turn(state: GameState) -> None:
    if state.game_over:
        return
    if state.current == "X":
        state.current = "O"
        cpu_take_turn(state)
    else:
        state.current = "X"


def handle_player_click(state: GameState, pos: tuple) -> None:
    if state.current != "X" or state.game_over:
        return
    if not state.strip_cells:
        return
    x, y = pos
    board_left = MARGIN
    board_top = MARGIN
    if not (
        board_left <= x <= board_left + VISIBLE_SIZE * CELL_SIZE
        and board_top <= y <= board_top + VISIBLE_SIZE * CELL_SIZE
    ):
        return
    visible_x = clamp(state.view_x - 1, 0, BOARD_SIZE - VISIBLE_SIZE)
    visible_y = clamp(state.view_y - 1, 0, BOARD_SIZE - VISIBLE_SIZE)
    grid_x = (x - board_left) // CELL_SIZE + visible_x
    grid_y = (y - board_top) // CELL_SIZE + visible_y
    cell = (grid_x, grid_y)
    if cell not in state.strip_cells:
        return
    if state.board[grid_y][grid_x] is not None:
        return
    state.board[grid_y][grid_x] = "X"
    winner = check_winner(state.board)
    if winner:
        state.game_over = True
        state.winner = winner
        state.message = "You win!"
        return
    state.strip_cells = []
    end_turn(state)


def draw_board(screen: pygame.Surface, state: GameState, font: pygame.font.Font) -> None:
    screen.fill(BG_COLOR)
    board_left = MARGIN
    board_top = MARGIN

    pygame.draw.rect(
        screen,
        PANEL_COLOR,
        pygame.Rect(
            board_left - 10,
            board_top - 10,
            VISIBLE_SIZE * CELL_SIZE + 20,
            VISIBLE_SIZE * CELL_SIZE + 20,
        ),
    )

    visible_x = clamp(state.view_x - 1, 0, BOARD_SIZE - VISIBLE_SIZE)
    visible_y = clamp(state.view_y - 1, 0, BOARD_SIZE - VISIBLE_SIZE)
    for y in range(visible_y, visible_y + VISIBLE_SIZE):
        for x in range(visible_x, visible_x + VISIBLE_SIZE):
            rect = pygame.Rect(
                board_left + (x - visible_x) * CELL_SIZE,
                board_top + (y - visible_y) * CELL_SIZE,
                CELL_SIZE,
                CELL_SIZE,
            )
            pygame.draw.rect(screen, GRID_COLOR, rect, 1)
            symbol = state.board[y][x]
            if symbol == "X":
                padding = 5
                pygame.draw.line(
                    screen,
                    X_COLOR,
                    (rect.left + padding, rect.top + padding),
                    (rect.right - padding, rect.bottom - padding),
                    2,
                )
                pygame.draw.line(
                    screen,
                    X_COLOR,
                    (rect.left + padding, rect.bottom - padding),
                    (rect.right - padding, rect.top + padding),
                    2,
                )
            elif symbol == "O":
                pygame.draw.circle(
                    screen,
                    O_COLOR,
                    rect.center,
                    CELL_SIZE // 2 - 5,
                    2,
                )

    view_rect = pygame.Rect(
        board_left + (state.view_x - visible_x) * CELL_SIZE,
        board_top + (state.view_y - visible_y) * CELL_SIZE,
        VIEW_SIZE * CELL_SIZE,
        VIEW_SIZE * CELL_SIZE,
    )
    pygame.draw.rect(screen, VIEW_COLOR, view_rect, 3)

    for (sx, sy) in state.strip_cells:
        if not (visible_x <= sx < visible_x + VISIBLE_SIZE and visible_y <= sy < visible_y + VISIBLE_SIZE):
            continue
        rect = pygame.Rect(
            board_left + (sx - visible_x) * CELL_SIZE,
            board_top + (sy - visible_y) * CELL_SIZE,
            CELL_SIZE,
            CELL_SIZE,
        )
        pygame.draw.rect(screen, STRIP_COLOR, rect, 3)

    panel_x = board_left + VISIBLE_SIZE * CELL_SIZE + 20
    panel_rect = pygame.Rect(panel_x, board_top - 10, SIDE_PANEL - 30, 260)
    pygame.draw.rect(screen, PANEL_COLOR, panel_rect)

    lines = [
        "Tic-Tac-Shift",
        "", 
        f"Turn: {'You (X)' if state.current == 'X' else 'CPU (O)'}",
        f"Viewport: ({state.view_x}, {state.view_y})",
        "", 
        "Controls:",
        "Arrow / WASD: move",
        "Mouse: place (no move)",
        "R: restart",
        "ESC: quit",
    ]
    if state.current == "X" and state.strip_cells:
        lines.insert(3, "Optional: place in strip!")

    if state.game_over:
        lines.insert(2, state.message or "Game Over")

    for i, line in enumerate(lines):
        text = font.render(line, True, TEXT_COLOR)
        screen.blit(text, (panel_x, board_top + i * 22))


def main() -> None:
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Tic-Tac-Shift")
    font = pygame.font.SysFont(None, 22)
    clock = pygame.time.Clock()
    state = new_game()

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_r:
                    state = new_game()
                elif not state.game_over and state.current == "X":
                    if event.key in (pygame.K_UP, pygame.K_w):
                        move_view(state, "up")
                    elif event.key in (pygame.K_DOWN, pygame.K_s):
                        move_view(state, "down")
                    elif event.key in (pygame.K_LEFT, pygame.K_a):
                        move_view(state, "left")
                    elif event.key in (pygame.K_RIGHT, pygame.K_d):
                        move_view(state, "right")
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                handle_player_click(state, event.pos)

        draw_board(screen, state, font)
        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
