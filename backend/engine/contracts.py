"""
Engine I/O contracts. THE ONLY interface between the product and the rating engine.

If the underlying engine changes, only backend/engine/adapter.py should need updates.
"""
from pydantic import BaseModel, Field
from typing import Optional, Literal


Phase = Literal["powerplay", "middle", "death"]
Role = Literal["batter", "bowler", "allrounder", "keeper"]


class BallEvent(BaseModel):
    ball_id: str
    match_id: str
    innings: int
    over: int  # 0-indexed over number (0-19 in T20)
    ball: int  # 1-6 legal delivery number
    batter_id: str
    bowler_id: str
    non_striker_id: Optional[str] = None
    runs_batter: int = 0
    runs_extras: int = 0
    runs_total: int = 0
    is_wicket: bool = False
    dismissal_type: Optional[str] = None
    dismissed_player_id: Optional[str] = None
    phase: Phase
    # Engine-computed fields
    pressure_index: float = Field(ge=0.0, le=10.0)
    difficulty: float = Field(ge=0.0, le=10.0)
    wp_before: float = Field(ge=0.0, le=1.0)  # win probability for batting team
    wp_after: float = Field(ge=0.0, le=1.0)
    batter_impact_delta: float = 0.0
    bowler_impact_delta: float = 0.0
    commentary: str = ""


class RatingComponent(BaseModel):
    label: str
    weight: float  # can be negative
    ball_id: Optional[str] = None
    reason_code: str  # e.g. PRESSURE_BOUNDARY, DOT_UNDER_PRESSURE, WICKET_KEY_MOMENT
    phase: Optional[Phase] = None


class RatingBreakdown(BaseModel):
    player_id: str
    player_name: str
    match_id: str
    after_ball_id: Optional[str] = None
    base_rating: float
    components: list[RatingComponent]
    final_rating: float
    delta_from_previous: float = 0.0
    narrative: str = ""


class ImpactRow(BaseModel):
    player_id: str
    player_name: str
    role: Role
    team: str
    rating: float
    delta: float
    sparkline: list[float] = []


class MomentumPoint(BaseModel):
    ball_id: str
    over: int
    ball: int
    wp: float  # win probability for team1
    label: Optional[str] = None  # marker label if this is a key moment


class Moment(BaseModel):
    ball_id: str
    match_id: str
    type: str  # match_turning_point | wicket_key | boundary_streak | milestone
    impact_score: float
    narrative: str
    over: int
    ball: int
    batter_id: Optional[str] = None
    bowler_id: Optional[str] = None


class MatchState(BaseModel):
    match_id: str
    current_over: int
    current_ball: int
    latest_ball_id: Optional[str] = None
    top_impact: list[ImpactRow] = []
    momentum: list[MomentumPoint] = []
    latest_moment: Optional[Moment] = None
    narration: Optional[str] = None


class MatchSummary(BaseModel):
    match_id: str
    season: str
    date: str
    teams: list[str]
    team_short: list[str]
    venue: str
    format: str = "T20"
    status: Literal["live", "completed", "time_machine"] = "time_machine"
    featured: bool = False
    curation_slug: Optional[str] = None
    curation_title: Optional[str] = None
    curation_hook: Optional[str] = None
    result_summary: Optional[str] = None
    final_score: Optional[str] = None
    ball_count: int = 0
