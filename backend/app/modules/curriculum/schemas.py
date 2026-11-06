from typing import Any, Literal

from pydantic import BaseModel, Field

Status = Literal["DRAFT", "PUBLISHED", "ARCHIVED"]
ActivityKind = Literal["lesson_read", "quiz", "exercise", "project", "ctf_challenge"]


class CourseInput(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    description_markdown: str = Field(default="", max_length=30000)
    status: Status = "DRAFT"


class CourseClassesInput(BaseModel):
    class_ids: list[int] = Field(default_factory=list, max_length=200)


class ModuleInput(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    description_markdown: str = Field(default="", max_length=30000)
    sort_order: int = Field(default=0, ge=0, le=10000)
    status: Status = "DRAFT"


class LessonInput(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    content_markdown: str = Field(default="", max_length=100000)
    estimated_minutes: int | None = Field(default=None, ge=1, le=1440)
    sort_order: int = Field(default=0, ge=0, le=10000)
    status: Status = "DRAFT"


class ActivityInput(BaseModel):
    type: ActivityKind
    title: str = Field(min_length=2, max_length=180)
    description_markdown: str = Field(default="", max_length=50000)
    sort_order: int = Field(default=0, ge=0, le=10000)
    category_id: int | None = None
    difficulty_id: int | None = None
    points: int = Field(default=100, ge=0, le=100000)
    xp: int = Field(default=0, ge=0, le=100000)
    status: Status = "DRAFT"
    config: dict[str, Any] = Field(default_factory=dict)
    prerequisite_ids: list[int] = Field(default_factory=list, max_length=100)


class HintInput(BaseModel):
    order: int = Field(ge=0, le=100)
    cost: int = Field(default=0, ge=0, le=100)
    content_markdown: str = Field(min_length=1, max_length=10000)


class SubmissionInput(BaseModel):
    answers: dict[str, int | list[int] | str] | None = Field(default=None, max_length=50)
    answer: str | None = Field(default=None, max_length=5000)
    text: str | None = Field(default=None, max_length=20000)
    url: str | None = Field(default=None, max_length=1000)

    def payload(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True)


class ReviewInput(BaseModel):
    decision: Literal["APPROVED", "REJECTED", "NEEDS_CHANGES"]
    score: int | None = Field(default=None, ge=0, le=100000)
    feedback: str = Field(default="", max_length=5000)


# ---- learner responses: only the fields declared here can ever reach a student

class LearnerHint(BaseModel):
    id: int
    order: int
    cost: int
    unlocked: bool
    content_markdown: str | None


class LearnerCtf(BaseModel):
    available: bool
    event_public_id: str | None
    challenge_public_id: str | None
    state: str


class LearnerActivity(BaseModel):
    public_id: str
    type: str
    type_label: str
    title: str
    description_markdown: str
    points: int
    xp: int
    category: str | None
    difficulty: str | None
    locked: bool
    lock_reason: str | None
    config: dict[str, Any]
    status: str
    score: int | None
    max_score: int | None
    attempts: int
    feedback: str
    submission: dict[str, Any]
    hints: list[LearnerHint]
    ctf: LearnerCtf | None


class LearnerLessonRef(BaseModel):
    public_id: str
    title: str


class LearnerLesson(BaseModel):
    public_id: str
    title: str
    content_markdown: str
    estimated_minutes: int | None
    module: LearnerLessonRef
    course: LearnerLessonRef
    activities: list[LearnerActivity]


class LearnerSubmissionResult(BaseModel):
    status: str
    score: int | None
    max_score: int | None
    feedback: str
    attempts: int
    details: dict[str, Any]
