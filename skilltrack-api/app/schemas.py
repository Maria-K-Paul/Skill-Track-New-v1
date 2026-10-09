from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, EmailStr, Field, model_validator


class RegisterIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    reg_no: str = Field(min_length=1, max_length=30)
    password: str = Field(min_length=8, max_length=72)
    department: str | None = None
    semester: int | None = Field(default=None, ge=1, le=6)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    reg_no: str | None
    role: str
    department: str | None
    semester: int | None
    is_active: bool


class TokenOut(BaseModel):
    """The refresh token is never in the body: it is set as an httpOnly cookie."""
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class EnrollIn(BaseModel):
    domain_id: int


class KeyIn(BaseModel):
    slot_id: int | None = None   # preferred: the key is tied to this slot and its booked students
    level_id: int | None = None  # fallback for a key that is not tied to a slot
    minutes: int | None = Field(default=None, ge=1, le=30)

    @model_validator(mode="after")
    def need_slot_or_level(self):
        if self.slot_id is None and self.level_id is None:
            raise ValueError("Pick a slot (or a level) for the key")
        return self


class StartIn(BaseModel):
    key: str = Field(min_length=1, max_length=20)


class SubmitIn(BaseModel):
    answers: dict[str, int] = {}
    violations: int = Field(default=0, ge=0)


class LevelUpdate(BaseModel):
    question_count: int | None = Field(default=None, ge=1, le=200)
    pass_mark: int | None = Field(default=None, ge=1, le=100)
    duration_min: int | None = Field(default=None, ge=1, le=300)
    easy_pct: int | None = Field(default=None, ge=0, le=100)
    medium_pct: int | None = Field(default=None, ge=0, le=100)
    hard_pct: int | None = Field(default=None, ge=0, le=100)


class QuestionIn(BaseModel):
    text: str = Field(min_length=5, max_length=1000)
    options: list[str] = Field(min_length=2, max_length=6)
    answer_index: int = Field(ge=0)
    difficulty: Literal["easy", "medium", "hard"]
    topic: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def check_options(self):
        if any(not o.strip() for o in self.options):
            raise ValueError("Options cannot be empty")
        if self.answer_index >= len(self.options):
            raise ValueError("answer_index must point at one of the options")
        return self


class StaffIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    role: Literal["owner", "invigilator", "admin"]
    department: str | None = Field(default=None, max_length=20)


class UserPatch(BaseModel):
    is_active: bool


class DomainIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)


class DomainPatch(BaseModel):
    owner_id: int | None = None


class DomainMetaPatch(BaseModel):
    description: str | None = Field(default=None, max_length=500)
    difficulty: str | None = Field(default=None, pattern="^(beginner|intermediate|advanced)$")


class SettingsIn(BaseModel):
    max_attempts: int = Field(ge=1, le=10)
    points_to_unlock: int = Field(ge=1, le=1000)
    first_attempt_points: int = Field(ge=0, le=100)
    retry_points: int = Field(ge=0, le=100)
    key_minutes: int = Field(ge=1, le=30)


class SlotIn(BaseModel):
    domain_id: int
    level_id: int | None = None  # Optional: defaults to first level of domain if not provided
    starts_at: AwareDatetime
    venue: str = Field(min_length=2, max_length=120)
    capacity: int = Field(ge=1, le=500)


class SlotPatch(BaseModel):
    starts_at: AwareDatetime | None = None
    venue: str | None = Field(default=None, min_length=2, max_length=120)
    capacity: int | None = Field(default=None, ge=1, le=500)


class AssignCommonIn(BaseModel):
    semester: int = Field(ge=1, le=2)
    starts_at: AwareDatetime
    venue: str = Field(min_length=2, max_length=120)
    capacity: int = Field(ge=1, le=500)


class PromoteIn(BaseModel):
    student_ids: list[int] = Field(min_length=1, max_length=2000)


class BookSlotIn(BaseModel):
    acknowledgement: bool = False

    @model_validator(mode="after")
    def must_acknowledge(self):
        if not self.acknowledgement:
            raise ValueError("You must acknowledge the slot booking rules before confirming.")
        return self


class ChangeSlotIn(BaseModel):
    new_slot_id: int
