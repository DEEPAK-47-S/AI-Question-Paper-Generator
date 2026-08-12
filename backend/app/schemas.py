"""Validated REST request/response contracts."""
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict[str, Any]


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=10, max_length=128)


class PasswordReset(BaseModel):
    temporary_password: str = Field(min_length=10, max_length=128)


class DepartmentCreate(BaseModel):
    code: str = Field(min_length=2, max_length=20)
    name: str = Field(min_length=3, max_length=180)


class DepartmentOut(ORMModel):
    id: str
    code: str
    name: str
    is_active: bool


class SemesterCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    ordinal: int = Field(ge=1, le=12)


class RegulationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    year: int = Field(ge=2000, le=2100)


class TeacherCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    employee_id: str = Field(min_length=2, max_length=50)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=30)
    department_id: str
    designation: str = Field(default="Assistant Professor", max_length=100)
    username: str = Field(min_length=3, max_length=80)
    temporary_password: str = Field(min_length=10, max_length=128)
    subject_ids: list[str] = []
    is_active: bool = True


class TeacherUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=160)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=30)
    department_id: str | None = None
    designation: str | None = Field(default=None, max_length=100)
    subject_ids: list[str] | None = None
    is_active: bool | None = None


class TeacherOut(ORMModel):
    id: str
    full_name: str
    employee_id: str | None
    email: str
    phone: str | None
    department_id: str | None
    designation: str | None
    username: str
    role: str
    is_active: bool
    last_login_at: datetime | None


class SubjectCreate(BaseModel):
    code: str = Field(min_length=2, max_length=30)
    name: str = Field(min_length=2, max_length=180)
    department_id: str
    semester_id: str
    regulation_id: str
    credits: float = Field(default=3, ge=0, le=20)
    syllabus_text: str | None = None
    units_json: list[dict[str, Any]] = []


class SubjectOut(ORMModel):
    id: str
    code: str
    name: str
    department_id: str
    semester_id: str
    regulation_id: str
    credits: float
    units_json: list
    is_active: bool


DocumentCategory = Literal["syllabus", "portion", "previous_paper", "sample_paper", "question_bank", "notes", "reference", "assignment"]


class DocumentURLCreate(BaseModel):
    url: str = Field(min_length=10, max_length=2048)
    subject_id: str
    category: DocumentCategory = "reference"


class DocumentOut(ORMModel):
    id: str
    subject_id: str | None
    category: str
    original_name: str
    mime_type: str
    extension: str
    size_bytes: int
    processing_status: str
    analysis_status: str
    processing_stage: str
    error_message: str | None
    page_count: int
    metadata_json: dict
    created_at: datetime


class TopicSelection(BaseModel):
    unit: str = Field(min_length=1, max_length=80)
    topic: str = Field(min_length=1, max_length=255)
    subtopic: str | None = Field(default=None, max_length=255)
    selected: bool = True


class PatternSection(BaseModel):
    name: str = Field(min_length=1, max_length=30)
    count: int = Field(ge=1, le=100)
    marks: int = Field(ge=1, le=100)
    question_type: str = Field(default="Short Answer", max_length=50)
    instructions: str = Field(default="Answer ALL questions", max_length=300)
    has_choice: bool = False


class Distribution(BaseModel):
    easy: int = Field(default=30, ge=0, le=100)
    medium: int = Field(default=50, ge=0, le=100)
    hard: int = Field(default=20, ge=0, le=100)

    @model_validator(mode="after")
    def totals_100(self):
        if self.easy + self.medium + self.hard != 100:
            raise ValueError("Difficulty percentages must total 100")
        return self


class PaperBlueprintRequest(BaseModel):
    subject_id: str
    exam_type: str = Field(min_length=2, max_length=80)
    duration_minutes: int = Field(ge=15, le=600)
    total_marks: int = Field(ge=1, le=500)
    academic_year: str = Field(min_length=4, max_length=20)
    exam_date: date | None = None
    class_section: str | None = Field(default=None, max_length=50)
    sections: list[PatternSection] = Field(min_length=1, max_length=10)
    selected_topics: list[TopicSelection] = Field(min_length=1)
    difficulty: Distribution = Distribution()
    bloom_distribution: dict[str, int] | None = None
    unit_weightage: dict[str, int] | None = None
    previous_paper_influence: int = Field(default=20, ge=0, le=100)
    novelty: int = Field(default=80, ge=0, le=100)

    @model_validator(mode="after")
    def validate_marks_and_topics(self):
        pattern_marks = sum(s.count * s.marks for s in self.sections)
        if pattern_marks != self.total_marks:
            raise ValueError(f"Section pattern totals {pattern_marks}, expected {self.total_marks}")
        if not any(t.selected for t in self.selected_topics):
            raise ValueError("At least one portion topic must be selected")
        if self.unit_weightage and sum(self.unit_weightage.values()) != 100:
            raise ValueError("Unit weightage percentages must total 100")
        if self.bloom_distribution and sum(self.bloom_distribution.values()) != 100:
            raise ValueError("Bloom percentages must total 100")
        return self


class BlueprintOut(ORMModel):
    id: str
    subject_id: str
    allocation_json: dict
    total_marks: int
    created_at: datetime


class GenerateRequest(BaseModel):
    blueprint_id: str
    title: str = Field(default="Question Paper", max_length=200)


class QuestionUpdate(BaseModel):
    text: str | None = Field(default=None, min_length=5)
    marks: int | None = Field(default=None, ge=1, le=100)
    difficulty: str | None = Field(default=None, pattern="^(Easy|Medium|Hard)$")
    unit: str | None = Field(default=None, max_length=80)
    topic: str | None = Field(default=None, max_length=255)
    question_type: str | None = Field(default=None, max_length=50)
    position: int | None = Field(default=None, ge=1)


class ManualQuestionCreate(BaseModel):
    section: str
    text: str = Field(min_length=5)
    marks: int = Field(ge=1, le=100)
    unit: str
    topic: str
    difficulty: str = "Medium"
    bloom_level: str = "Understand"
    question_type: str = "Descriptive"


class ApprovalRequest(BaseModel):
    action: Literal["submit", "approve", "reject", "request_changes", "archive"]
    comment: str | None = Field(default=None, max_length=2000)


class PaperStatusUpdate(BaseModel):
    status: Literal["draft", "generated", "teacher_review", "admin_review", "approved", "downloaded", "archived"]


class QuestionBankCreate(BaseModel):
    subject_id: str
    question: str = Field(min_length=5)
    unit: str
    topic: str
    difficulty: str = "Medium"
    bloom_level: str = "Understand"
    marks: int = Field(ge=1, le=100)
    source: str | None = None
