from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from opc_browse.services.time_utils import choose_bucket_seconds


class MachineOut(BaseModel):
    id: int
    machine_name: str
    endpoint_url: str | None = None
    enabled: bool


class TagLeaf(BaseModel):
    tag_id: int
    opc_path: str
    display_name: str | None = None
    browse_name: str | None = None
    data_type: str | None = None
    parent_branch: str | None = None
    last_seen_utc: datetime | None = None
    sample_count: int
    is_numeric: bool


class TagTreeNode(BaseModel):
    name: str
    path: str
    children: list["TagTreeNode"] = Field(default_factory=list)
    tags: list[TagLeaf] = Field(default_factory=list)


class QualityBreakdownItem(BaseModel):
    quality: str | None = None
    status_code: str | None = None
    count: int


class UsefulnessFlags(BaseModel):
    has_numeric_data: bool
    mostly_null_numeric: bool
    appears_constant: bool
    has_errors: bool
    enough_samples: bool


class TagProfileOut(BaseModel):
    machine_id: int
    tag_id: int
    sample_count: int
    numeric_sample_count: int
    text_sample_count: int
    null_numeric_count: int
    error_count: int
    first_seen_utc: datetime | None = None
    last_seen_utc: datetime | None = None
    min_value: float | None = None
    max_value: float | None = None
    avg_value: float | None = None
    stddev_value: float | None = None
    distinct_numeric_count: int
    quality_breakdown: list[QualityBreakdownItem]
    usefulness_flags: UsefulnessFlags


class TimeseriesQuerySeries(BaseModel):
    machine_id: int
    tag_id: int
    label: str | None = None


class TimeseriesQueryRequest(BaseModel):
    series: list[TimeseriesQuerySeries]
    start_utc: datetime
    end_utc: datetime
    bucket_seconds: int = Field(ge=1)
    aggregation: Literal["avg", "min", "max"]
    max_points_per_series: int = Field(default=2000, ge=1)

    @field_validator("end_utc")
    @classmethod
    def validate_time_range(cls, value: datetime, info):
        start_utc = info.data.get("start_utc")
        if start_utc is not None and value <= start_utc:
            raise ValueError("end_utc must be greater than start_utc")
        return value

    def resolved_bucket_seconds(self) -> int:
        return choose_bucket_seconds(
            start=self.start_utc,
            end=self.end_utc,
            requested_bucket_seconds=self.bucket_seconds,
            max_points=self.max_points_per_series,
        )


class TimeseriesPoint(BaseModel):
    t: datetime
    v: float
    sample_count: int
    min_value: float
    max_value: float


class TimeseriesSeriesOut(BaseModel):
    machine_id: int
    tag_id: int
    label: str | None = None
    points: list[TimeseriesPoint]


class TimeseriesQueryResponse(BaseModel):
    bucket_seconds: int
    aggregation: Literal["avg", "min", "max"]
    series: list[TimeseriesSeriesOut]


class SeriesSelector(BaseModel):
    machine_id: int
    tag_id: int
    label: str | None = None


class RelationshipRequest(BaseModel):
    target: SeriesSelector
    start_utc: datetime
    end_utc: datetime
    bucket_seconds: int = Field(ge=1)
    max_points_per_series: int = Field(default=2000, ge=100, le=10000)
    candidate_scope: Literal["same_machine", "same_folder", "selected_tags"]
    candidate_tag_ids: list[int] | None = None
    max_candidate_tags: int = Field(default=300, ge=1, le=2000)
    max_results: int = Field(default=25, ge=1, le=100)
    min_pair_count: int = Field(default=30, ge=3)
    max_lag_seconds: int = Field(default=1800, ge=0, le=86400)
    prefer_useful_candidates: bool = True

    @field_validator("end_utc")
    @classmethod
    def validate_relationship_time_range(cls, value: datetime, info):
        start_utc = info.data.get("start_utc")
        if start_utc is not None and value <= start_utc:
            raise ValueError("end_utc must be greater than start_utc")
        return value

    @model_validator(mode="after")
    def validate_selected_tags_scope(self):
        if self.candidate_scope == "selected_tags" and not self.candidate_tag_ids:
            raise ValueError(
                "candidate_tag_ids must be supplied when candidate_scope is selected_tags"
            )
        return self

    def resolved_bucket_seconds(self) -> int:
        return choose_bucket_seconds(
            start=self.start_utc,
            end=self.end_utc,
            requested_bucket_seconds=self.bucket_seconds,
            max_points=self.max_points_per_series,
        )


class RelationshipTargetInfo(BaseModel):
    machine_id: int
    tag_id: int
    label: str | None = None
    opc_path: str | None = None
    display_name: str | None = None
    data_type: str | None = None


class RelationshipWindow(BaseModel):
    start_utc: datetime
    end_utc: datetime
    requested_bucket_seconds: int
    actual_bucket_seconds: int


class RelationshipAnalysisInfo(BaseModel):
    method: str
    candidate_scope: Literal["same_machine", "same_folder", "selected_tags"]
    candidate_count_scanned: int
    candidate_count_analyzed: int
    skipped_count: int
    skipped_by_reason: dict[str, int]
    max_lag_seconds: int
    min_pair_count: int
    warnings: list[str] = Field(default_factory=list)


class RelationshipResult(BaseModel):
    machine_id: int
    tag_id: int
    label: str | None = None
    opc_path: str | None = None
    display_name: str | None = None
    data_type: str | None = None
    relationship_type: Literal[
        "moves_together",
        "possible_driver",
        "possible_effect",
        "changes_together",
    ]
    score: float
    same_time_corr: float | None = None
    delta_corr: float | None = None
    best_lag_corr: float | None = None
    best_lag_seconds: int
    pair_count: int
    direction: Literal["positive", "negative"]
    notes: list[str] = Field(default_factory=list)


class RelationshipSkipped(BaseModel):
    tag_id: int
    reason: str


class RelationshipResponse(BaseModel):
    target: RelationshipTargetInfo
    window: RelationshipWindow
    analysis: RelationshipAnalysisInfo
    results: list[RelationshipResult]
    skipped: list[RelationshipSkipped]


class TagUsefulnessScore(BaseModel):
    score: int = Field(ge=0, le=100)
    grade: Literal["high", "medium", "low", "ignore"]
    semantic_type: Literal[
        "continuous_numeric",
        "counter_like",
        "state_like_numeric",
        "constant",
        "sparse",
        "text_or_state",
        "unknown",
    ]
    reasons: list[str] = Field(default_factory=list)
    badges: list[str] = Field(default_factory=list)


class TagProfileSummary(BaseModel):
    machine_id: int
    tag_id: int
    opc_path: str | None = None
    display_name: str | None = None
    browse_name: str | None = None
    data_type: str | None = None
    parent_branch: str | None = None
    sample_count: int
    numeric_sample_count: int
    text_sample_count: int
    null_numeric_count: int
    error_count: int
    first_seen_utc: datetime | None = None
    last_seen_utc: datetime | None = None
    min_value: float | None = None
    max_value: float | None = None
    avg_value: float | None = None
    stddev_value: float | None = None
    distinct_numeric_count: int
    quality_good_count: int = 0
    quality_bad_count: int = 0
    usefulness_score: TagUsefulnessScore


class TagProfilesResponse(BaseModel):
    machine_id: int
    count: int
    profiles: list[TagProfileSummary]


class DashboardSummary(BaseModel):
    id: str
    name: str
    description: str = ""
    created_at_utc: datetime
    updated_at_utc: datetime
    panel_count: int


class DashboardPayload(BaseModel):
    id: str | None = None
    name: str
    description: str = ""
    created_at_utc: datetime | None = None
    updated_at_utc: datetime | None = None
    workspace: dict[str, Any] = Field(default_factory=dict)
    panels: list[dict[str, Any]] = Field(default_factory=list)


class DashboardSaveRequest(BaseModel):
    id: str | None = None
    name: str
    description: str = ""
    created_at_utc: datetime | None = None
    updated_at_utc: datetime | None = None
    workspace: dict[str, Any] = Field(default_factory=dict)
    panels: list[dict[str, Any]] = Field(default_factory=list)


class DashboardListResponse(BaseModel):
    dashboards: list[DashboardSummary]


TagTreeNode.model_rebuild()
