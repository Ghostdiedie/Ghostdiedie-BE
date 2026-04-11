from enum import Enum
from typing import Optional, Literal
from pydantic import BaseModel


# ── Enums ─────────────────────────────────────────────────────────────────────

class RoomStatus(str, Enum):
    WAITING  = "waiting"    # 방 생성됨, P2 대기 중
    READY    = "ready"      # P2 참가 완료, WS 연결 대기
    PLAYING  = "playing"    # 게임 진행 중
    FINISHED = "finished"   # 게임 종료


class ActionType(str, Enum):
    IDLE    = "idle"
    R_PUNCH = "right punch"
    L_PUNCH = "left punch"
    KICK    = "kick"
    JUMP    = "jump"
    WALK    = "walk"
    BLOCK   = "block"
    HIT     = "hit"         # 맞는 모션 (서버 → 클라 전용)
    SPECIAL = "special"     # 필살기 (게이지 소모)


class WSType(str, Enum):
    # 연결 이벤트
    OPPONENT_JOINED = "opponent_joined"
    OPPONENT_LEFT   = "opponent_left"
    # 게임 흐름
    GAME_START      = "game_start"
    ROUND_START     = "round_start"
    ROUND_END       = "round_end"
    GAME_END        = "game_end"
    # 플레이어 동작 (OpenCV 감지 → 서버 relay → 상대방)
    PLAYER_ACTION   = "player_action"
    # 상태 동기화 (HP / 게이지)
    STATE_UPDATE    = "state_update"


# ── Character ─────────────────────────────────────────────────────────────────

class CharacterInfo(BaseModel):
    """DB characters 테이블 응답"""
    id: int
    name: str
    max_hp: int             # 캐릭터 고유 체력 (예: 100~150)
    max_special_gauge: int  # 필살기 게이지 최대값 (예: 100)


# ── Player / Room ─────────────────────────────────────────────────────────────

class PlayerState(BaseModel):
    """방 안에서 한 플레이어의 전체 상태"""
    name: str
    character_id: int
    profile_image_url: Optional[str] = None  # 캐릭터 얼굴에 합성할 유저 사진 URL
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
    """방 조회 / 생성 / 참가 응답"""
    room_code: str
    status: RoomStatus
    players: list[PlayerState]


# ── Match ─────────────────────────────────────────────────────────────────────

class MatchCreate(BaseModel):
    """게임 종료 후 결과 저장 요청"""
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
    """상대방이 WS에 접속했을 때 양쪽 모두에게 전송"""
    type: Literal[WSType.OPPONENT_JOINED]
    player_index: int       # 수신자 기준: 0 = P1(좌), 1 = P2(우)
    me: PlayerState
    opponent: PlayerState


class WSGameStart(BaseModel):
    """두 플레이어 모두 WS 연결 완료 → 게임 시작 신호"""
    type: Literal[WSType.GAME_START]
    player_index: int       # 0 = P1(좌), 1 = P2(우)
    me: PlayerState
    opponent: PlayerState


class WSRoundStart(BaseModel):
    type: Literal[WSType.ROUND_START]
    round_number: int       # 1부터 시작


class WSPlayerAction(BaseModel):
    """OpenCV가 감지한 동작 → 서버 → 상대방에게 relay"""
    type: Literal[WSType.PLAYER_ACTION]
    action: ActionType
    damage: Optional[int] = None   # 프론트에서 계산한 데미지 (선택)


class WSStateUpdate(BaseModel):
    """HP / 게이지 동기화 (공격 hit 후 양쪽에 전송)"""
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
    """모든 라운드 종료 → 최종 승자"""
    type: Literal[WSType.GAME_END]
    winner_index: int
    winner_name: str


class WSOpponentLeft(BaseModel):
    type: Literal[WSType.OPPONENT_LEFT]
