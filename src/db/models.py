"""
src/db/models.py
SQLAlchemy ORM 모델 정의
- users: internal_user_id 기반 단일 식별자
- external_accounts: 외부 OJ 계정 (site + handle)
- problems: legacy_code <-> server_problem_id 매핑
- submissions: 제출 이력 (TIMESTAMPTZ=UTC)
- assignments: 숙제 출제
- assignment_submissions: 숙제별 학생 제출 상태
"""
from datetime import datetime, timezone
from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Integer,
    String, Text, UniqueConstraint, Index
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.base import Base


def _utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    internal_user_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="student")  # admin/instructor/student
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    external_accounts: Mapped[list["ExternalAccount"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    submissions: Mapped[list["Submission"]] = relationship(back_populates="user")

    def __repr__(self):
        return f"<User {self.internal_user_id} name={self.name}>"


class ExternalAccount(Base):
    __tablename__ = "external_accounts"
    __table_args__ = (UniqueConstraint("user_id", "site", name="uq_user_site"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    site: Mapped[str] = mapped_column(String(64), nullable=False)  # 'doingcoding'
    # handle은 반드시 casefold() 후 저장 (위험요소 #6 대응)
    handle: Mapped[str] = mapped_column(String(256), nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active")  # active / inactive / error

    user: Mapped["User"] = relationship(back_populates="external_accounts")


class Chapter(Base):
    __tablename__ = "chapters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    curriculum: Mapped[str] = mapped_column(String(32), nullable=False)  # 'prog1' / 'prog2'
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    groups: Mapped[list["Group"]] = relationship(back_populates="chapter", cascade="all, delete-orphan")


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chapter_id: Mapped[int] = mapped_column(Integer, ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    chapter: Mapped["Chapter"] = relationship(back_populates="groups")
    problems: Mapped[list["Problem"]] = relationship(back_populates="group")


class Problem(Base):
    __tablename__ = "problems"
    __table_args__ = (
        UniqueConstraint("site", "server_problem_id", name="uq_site_server_id"),
        UniqueConstraint("site", "legacy_code", name="uq_site_legacy_code"),
        Index("ix_problems_legacy_code", "legacy_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site: Mapped[str] = mapped_column(String(64), nullable=False, default="doingcoding")
    server_problem_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    legacy_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    difficulty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    group_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("groups.id"), nullable=True, index=True)
    order_in_group: Mapped[int] = mapped_column(Integer, default=0)
    is_unknown: Mapped[bool] = mapped_column(Boolean, default=False)  # 위험요소 #7: 미매핑 fallback

    group: Mapped["Group | None"] = relationship(back_populates="problems")
    submissions: Mapped[list["Submission"]] = relationship(back_populates="problem")


class Submission(Base):
    __tablename__ = "submissions"
    __table_args__ = (
        UniqueConstraint("user_id", "problem_id", "submitted_at", name="uq_sub_user_prob_time"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    problem_id: Mapped[int] = mapped_column(Integer, ForeignKey("problems.id"), nullable=False, index=True)
    verdict: Mapped[str | None] = mapped_column(String(32), nullable=True)  # AC/WA/TLE/PARTIAL
    score: Mapped[int] = mapped_column(Integer, default=0)
    language: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # 위험요소 #8: UTC로 통일 저장, KST 변환은 조회 레이어에서
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user: Mapped["User"] = relationship(back_populates="submissions")
    problem: Mapped["Problem"] = relationship(back_populates="submissions")


class Assignment(Base):
    __tablename__ = "assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    log_id: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True, index=True)  # 원본 JSON log id
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    mode: Mapped[str] = mapped_column(String(32), default="homework")  # homework/comment/review
    channel: Mapped[str | None] = mapped_column(String(64), nullable=True)  # kakao
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    # UTC 기준 저장
    opens_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    items: Mapped[list["AssignmentSubmission"]] = relationship(back_populates="assignment", cascade="all, delete-orphan")


class AssignmentSubmission(Base):
    __tablename__ = "assignment_submissions"
    __table_args__ = (
        UniqueConstraint("assignment_id", "user_id", "problem_id", name="uq_asub_assign_user_prob"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assignment_id: Mapped[int] = mapped_column(Integer, ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    problem_id: Mapped[int] = mapped_column(Integer, ForeignKey("problems.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending/passed/partial/wrong
    score: Mapped[int] = mapped_column(Integer, default=0)
    legacy_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    assignment: Mapped["Assignment"] = relationship(back_populates="items")
    problem: Mapped["Problem"] = relationship()
    user: Mapped["User"] = relationship()
