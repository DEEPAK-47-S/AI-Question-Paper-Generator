"""Relational data model for academics, private documents, papers, provenance and auditing."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON, Boolean, Column, Date, DateTime, Float, ForeignKey, Index, Integer, String, Table, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def uuid4() -> str:
    return str(uuid.uuid4())


def now() -> datetime:
    return datetime.now(timezone.utc)


teacher_subjects = Table(
    "teacher_subjects",
    Base.metadata,
    Column("teacher_id", String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("subject_id", String(36), ForeignKey("subjects.id", ondelete="CASCADE"), primary_key=True),
)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class User(Base, TimestampMixin):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(160))
    role: Mapped[str] = mapped_column(String(20), default="teacher", index=True)
    employee_id: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    designation: Mapped[str | None] = mapped_column(String(100), nullable=True)
    department_id: Mapped[str | None] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    auth_version: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    department: Mapped[Department | None] = relationship(back_populates="users")
    subjects: Mapped[list[Subject]] = relationship(secondary=teacher_subjects, back_populates="teachers")
    teacher_profile: Mapped[TeacherProfile | None] = relationship(back_populates="user", cascade="all, delete-orphan")
    admin_profile: Mapped[AdminProfile | None] = relationship(back_populates="user", cascade="all, delete-orphan")


class TeacherProfile(Base, TimestampMixin):
    __tablename__ = "teachers"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    qualifications: Mapped[str | None] = mapped_column(String(255), nullable=True)
    user: Mapped[User] = relationship(back_populates="teacher_profile")


class AdminProfile(Base, TimestampMixin):
    __tablename__ = "admins"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    system_scope: Mapped[str] = mapped_column(String(30), default="college")
    user: Mapped[User] = relationship(back_populates="admin_profile")


class Department(Base, TimestampMixin):
    __tablename__ = "departments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(180), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    users: Mapped[list[User]] = relationship(back_populates="department")
    subjects: Mapped[list[Subject]] = relationship(back_populates="department")


class Semester(Base, TimestampMixin):
    __tablename__ = "semesters"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    ordinal: Mapped[int] = mapped_column(Integer, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Regulation(Base, TimestampMixin):
    __tablename__ = "regulations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    year: Mapped[int] = mapped_column(Integer, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Subject(Base, TimestampMixin):
    __tablename__ = "subjects"
    __table_args__ = (UniqueConstraint("code", "regulation_id", name="uq_subject_code_regulation"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(30), index=True)
    name: Mapped[str] = mapped_column(String(180), index=True)
    department_id: Mapped[str] = mapped_column(ForeignKey("departments.id"))
    semester_id: Mapped[str] = mapped_column(ForeignKey("semesters.id"))
    regulation_id: Mapped[str] = mapped_column(ForeignKey("regulations.id"))
    credits: Mapped[float] = mapped_column(Float, default=3)
    syllabus_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    units_json: Mapped[list] = mapped_column(JSON, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    department: Mapped[Department] = relationship(back_populates="subjects")
    semester: Mapped[Semester] = relationship()
    regulation: Mapped[Regulation] = relationship()
    teachers: Mapped[list[User]] = relationship(secondary=teacher_subjects, back_populates="subjects")


class UploadedDocument(Base, TimestampMixin):
    __tablename__ = "uploaded_documents"
    __table_args__ = (
        Index("ix_document_owner_subject", "owner_id", "subject_id"),
        Index("ix_document_status", "processing_status", "analysis_status"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    subject_id: Mapped[str | None] = mapped_column(ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True)
    category: Mapped[str] = mapped_column(String(40), default="reference", index=True)
    original_name: Mapped[str] = mapped_column(String(255))
    stored_name: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    mime_type: Mapped[str] = mapped_column(String(120), default="application/octet-stream")
    extension: Mapped[str] = mapped_column(String(20))
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    processing_status: Mapped[str] = mapped_column(String(30), default="uploaded")
    analysis_status: Mapped[str] = mapped_column(String(30), default="pending")
    processing_stage: Mapped[str] = mapped_column(String(60), default="Upload completed")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    is_private: Mapped[bool] = mapped_column(Boolean, default=True)
    owner: Mapped[User] = relationship()
    subject: Mapped[Subject | None] = relationship()
    chunks: Mapped[list[DocumentChunk]] = relationship(back_populates="document", cascade="all, delete-orphan")


class SyllabusDocument(Base, TimestampMixin):
    __tablename__ = "syllabus_documents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    document_id: Mapped[str] = mapped_column(ForeignKey("uploaded_documents.id", ondelete="CASCADE"), unique=True)
    subject_id: Mapped[str] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"), index=True)
    structured_units: Mapped[list] = mapped_column(JSON, default=list)
    learning_outcomes: Mapped[list] = mapped_column(JSON, default=list)
    document: Mapped[UploadedDocument] = relationship()


class DocumentChunk(Base, TimestampMixin):
    __tablename__ = "document_chunks"
    __table_args__ = (Index("ix_chunk_document_location", "document_id", "chunk_index"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    document_id: Mapped[str] = mapped_column(ForeignKey("uploaded_documents.id", ondelete="CASCADE"))
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    unit: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    topic: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    location: Mapped[str | None] = mapped_column(String(100), nullable=True)
    token_estimate: Mapped[int] = mapped_column(Integer, default=0)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    classification: Mapped[str] = mapped_column(String(40), default="reference")
    document: Mapped[UploadedDocument] = relationship(back_populates="chunks")


class DocumentEmbedding(Base, TimestampMixin):
    __tablename__ = "document_embeddings"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    chunk_id: Mapped[str] = mapped_column(ForeignKey("document_chunks.id", ondelete="CASCADE"), unique=True)
    provider: Mapped[str] = mapped_column(String(50), default="lexical")
    vector_ref: Mapped[str | None] = mapped_column(Text, nullable=True)


class PortionTopic(Base, TimestampMixin):
    __tablename__ = "portion_topics"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    subject_id: Mapped[str] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"), index=True)
    unit: Mapped[str] = mapped_column(String(80))
    topic: Mapped[str] = mapped_column(String(255))
    subtopic: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_selected: Mapped[bool] = mapped_column(Boolean, default=True)
    source_document_id: Mapped[str | None] = mapped_column(ForeignKey("uploaded_documents.id", ondelete="SET NULL"), nullable=True)


class PreviousQuestionPaper(Base, TimestampMixin):
    __tablename__ = "previous_question_papers"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    document_id: Mapped[str] = mapped_column(ForeignKey("uploaded_documents.id", ondelete="CASCADE"), unique=True)
    analysis_json: Mapped[dict] = mapped_column(JSON, default=dict)


class QuestionPattern(Base, TimestampMixin):
    __tablename__ = "question_patterns"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    subject_id: Mapped[str | None] = mapped_column(ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True)
    total_marks: Mapped[int] = mapped_column(Integer)
    sections_json: Mapped[list] = mapped_column(JSON, default=list)
    is_template: Mapped[bool] = mapped_column(Boolean, default=False)


class QuestionBlueprint(Base, TimestampMixin):
    __tablename__ = "question_blueprints"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    subject_id: Mapped[str] = mapped_column(ForeignKey("subjects.id"))
    request_json: Mapped[dict] = mapped_column(JSON)
    allocation_json: Mapped[dict] = mapped_column(JSON)
    total_marks: Mapped[int] = mapped_column(Integer)


class GeneratedQuestionPaper(Base, TimestampMixin):
    __tablename__ = "generated_question_papers"
    __table_args__ = (Index("ix_paper_owner_status", "owner_id", "status"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    paper_code: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    subject_id: Mapped[str] = mapped_column(ForeignKey("subjects.id"))
    blueprint_id: Mapped[str | None] = mapped_column(ForeignKey("question_blueprints.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(200))
    exam_type: Mapped[str] = mapped_column(String(80))
    exam_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer)
    total_marks: Mapped[int] = mapped_column(Integer)
    academic_year: Mapped[str] = mapped_column(String(20))
    class_section: Mapped[str | None] = mapped_column(String(50), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    settings_json: Mapped[dict] = mapped_column(JSON, default=dict)
    coverage_json: Mapped[dict] = mapped_column(JSON, default=dict)
    approval_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    owner: Mapped[User] = relationship(foreign_keys=[owner_id])
    subject: Mapped[Subject] = relationship()
    questions: Mapped[list[Question]] = relationship(back_populates="paper", cascade="all, delete-orphan", order_by="Question.position")


class Question(Base, TimestampMixin):
    __tablename__ = "questions"
    __table_args__ = (Index("ix_question_paper_section", "paper_id", "section", "position"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    paper_id: Mapped[str] = mapped_column(ForeignKey("generated_question_papers.id", ondelete="CASCADE"))
    section: Mapped[str] = mapped_column(String(30))
    position: Mapped[int] = mapped_column(Integer)
    question_number: Mapped[str] = mapped_column(String(20))
    text: Mapped[str] = mapped_column(Text)
    alternative_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    unit: Mapped[str] = mapped_column(String(80), index=True)
    topic: Mapped[str] = mapped_column(String(255), index=True)
    subtopic: Mapped[str | None] = mapped_column(String(255), nullable=True)
    difficulty: Mapped[str] = mapped_column(String(20))
    bloom_level: Mapped[str] = mapped_column(String(30))
    marks: Mapped[int] = mapped_column(Integer)
    question_type: Mapped[str] = mapped_column(String(50))
    confidence_score: Mapped[float] = mapped_column(Float)
    validation_json: Mapped[dict] = mapped_column(JSON, default=dict)
    is_manual: Mapped[bool] = mapped_column(Boolean, default=False)
    paper: Mapped[GeneratedQuestionPaper] = relationship(back_populates="questions")
    sources: Mapped[list[QuestionSource]] = relationship(back_populates="question", cascade="all, delete-orphan")
    answer_key: Mapped[AnswerKey | None] = relationship(back_populates="question", cascade="all, delete-orphan")


class QuestionSource(Base, TimestampMixin):
    __tablename__ = "question_sources"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("uploaded_documents.id", ondelete="RESTRICT"))
    chunk_id: Mapped[str] = mapped_column(ForeignKey("document_chunks.id", ondelete="RESTRICT"))
    location: Mapped[str | None] = mapped_column(String(100), nullable=True)
    excerpt: Mapped[str] = mapped_column(Text)
    relevance_score: Mapped[float] = mapped_column(Float)
    question: Mapped[Question] = relationship(back_populates="sources")
    document: Mapped[UploadedDocument] = relationship()


class QuestionBank(Base, TimestampMixin):
    __tablename__ = "question_bank"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    subject_id: Mapped[str] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"), index=True)
    created_by_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    question: Mapped[str] = mapped_column(Text)
    unit: Mapped[str] = mapped_column(String(80))
    topic: Mapped[str] = mapped_column(String(255))
    difficulty: Mapped[str] = mapped_column(String(20))
    bloom_level: Mapped[str] = mapped_column(String(30))
    marks: Mapped[int] = mapped_column(Integer)
    source: Mapped[str | None] = mapped_column(Text, nullable=True)
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False)


class AnswerKey(Base, TimestampMixin):
    __tablename__ = "answer_keys"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), unique=True)
    answer_text: Mapped[str] = mapped_column(Text)
    evaluation_points: Mapped[list] = mapped_column(JSON, default=list)
    question: Mapped[Question] = relationship(back_populates="answer_key")


class GenerationLog(Base):
    __tablename__ = "generation_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    paper_id: Mapped[str | None] = mapped_column(ForeignKey("generated_question_papers.id", ondelete="CASCADE"), nullable=True)
    operation_id: Mapped[str] = mapped_column(String(36), index=True)
    stage: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20))
    progress: Mapped[int] = mapped_column(Integer)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(100), index=True)
    resource_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    detail_json: Mapped[dict] = mapped_column(JSON, default=dict)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)


class SystemSetting(Base, TimestampMixin):
    __tablename__ = "system_settings"
    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value_json: Mapped[dict] = mapped_column(JSON, default=dict)
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
