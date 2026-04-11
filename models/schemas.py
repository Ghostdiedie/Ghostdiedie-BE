from enum import Enum
from typing import Optional, Literal
from pydantic import BaseModel


# ── Enums ─────────────────────────────────────────────────────────────────────

class RoomStatus(str, Enum):
    WAITING  = "waiting"    # Room created, waiting for player 2
    READY    = "ready"      # Player 2 joined, waiting for WebSocket connection
    PLAYING  = "playing"    # Match in progress
    FINISHED = "finished"   # Match finished


class ActionType(str, Enum):
    IDLE    = "idle"
    R_PUNCH = "right punch"
    L_PUNCH = "left punch"
    KICK    = "kick"
    JUMP    = "jump"
    WALK    = "walk"
    BLOCK   = "block"
    HIT     = "hit"         # Hit animation (server -> client only)
    SPECIAL = "special"     # Special move (consumes gauge)


class WSType(str, Enum):
    # Connection events
    OPPONENT_JOINED = "opponent_joined"
    OPPONENT_LEFT   = "opponent_left"
    # Game flow
    GAME_START      = "game_start"
    ROUND_START     = "round_start"
    ROUND_END       = "round_end"
    GAME_END        = "game_end"
    # Player actions (OpenCV detection -> server relay -> opponent)
    PLAYER_ACTION   = "player_action"
    # State synchronization (HP / gauge)
    STATE_UPDATE    = "state_update"


# ── Character ─────────────────────────────────────────────────────────────────

class CharacterInfo(BaseModel):
    """Response model for the DB `characters` table."""
    id: int
    name: str
    max_hp: int             # Character-specific max HP (for example, 100-150)
    max_special_gauge: int  # Maximum special gauge value


# ── Player / Room ─────────────────────────────────────────────────────────────

class PlayerState(BaseModel):
    """Complete state for one player inside a room."""
    name: str
    character_id: int
    profile_image_url: Optional[str] = None  # User photo URL composited onto the character face
    hp: int             = 100
    special_gauge: int  = 0


class RoomCreate(BaseModel):
    player_name: str
    character_id: int
    profile_image_url: Optional[str] = None


class RoomJoin(BaseModel):
    player_name: str
    character_id: int
    profile_image_url: Optional[str] = None


class RoomResponse(BaseModel):
    """Response for room fetch, create, and join."""
    room_code: str
    status: RoomStatus
    players: list[PlayerState]


# ── Match ─────────────────────────────────────────────────────────────────────

class MatchCreate(BaseModel):
    """Request body for saving match results after a game ends."""
    room_code: str
    winner_name: str
    loser_name: str
    winner_character_id: int
    loser_character_id: int
    duration_seconds: int


class MatchResponse(BaseModel):
    match_id: str
    created_at: str


# ── WebSocket Messages ────────────────────────────────────────────────────────

class WSOpponentJoined(BaseModel):
    """Sent to both players when the opponent connects to WebSocket."""
    type: Literal[WSType.OPPONENT_JOINED]
    player_index: int       # From the receiver's perspective: 0 = P1 (left), 1 = P2 (right)
    me: PlayerState
    opponent: PlayerState


class WSGameStart(BaseModel):
    """Sent when both players finish connecting over WebSocket."""
    type: Literal[WSType.GAME_START]
    player_index: int       # 0 = P1 (left), 1 = P2 (right)
    me: PlayerState
    opponent: PlayerState


class WSRoundStart(BaseModel):
    type: Literal[WSType.ROUND_START]
    round_number: int       # Starts at 1


class WSPlayerAction(BaseModel):
    """Action detected by OpenCV and relayed through the server to the opponent."""
    type: Literal[WSType.PLAYER_ACTION]
    action: ActionType
    damage: Optional[int] = None   # Optional damage calculated by the frontend


class WSStateUpdate(BaseModel):
    """HP and gauge synchronization sent to both players after a hit."""
    type: Literal[WSType.STATE_UPDATE]
    player_hp: int
    opponent_hp: int
    player_gauge: int
    opponent_gauge: int


class WSRoundEnd(BaseModel):
    type: Literal[WSType.ROUND_END]
    round_number: int
    winner_index: int       # 0 or 1


class WSGameEnd(BaseModel):
    """Sent when all rounds are finished and a final winner is decided."""
    type: Literal[WSType.GAME_END]
    winner_index: int
    winner_name: str


class WSOpponentLeft(BaseModel):
    type: Literal[WSType.OPPONENT_LEFT]
