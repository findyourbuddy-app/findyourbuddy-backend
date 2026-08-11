from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models.block import Block
from app.models.report import Report, ReportStatus
from app.schemas.safety import ReportCreate


class CannotBlockSelfError(Exception):
    pass


class AlreadyBlockedError(Exception):
    pass


class CannotReportSelfError(Exception):
    pass


def block_user(db: Session, blocker_id: int, blocked_id: int) -> Block:
    if blocker_id == blocked_id:
        raise CannotBlockSelfError(blocker_id)

    existing = (
        db.query(Block)
        .filter(Block.blocker_id == blocker_id, Block.blocked_id == blocked_id)
        .first()
    )
    if existing is not None:
        raise AlreadyBlockedError(blocked_id)

    block = Block(blocker_id=blocker_id, blocked_id=blocked_id)
    db.add(block)
    db.commit()
    db.refresh(block)
    return block


def is_blocked(db: Session, user_a_id: int, user_b_id: int) -> bool:
    block = (
        db.query(Block)
        .filter(
            or_(
                and_(Block.blocker_id == user_a_id, Block.blocked_id == user_b_id),
                and_(Block.blocker_id == user_b_id, Block.blocked_id == user_a_id),
            )
        )
        .first()
    )
    return block is not None


def blocked_user_ids(db: Session, user_id: int) -> list[int]:
    blocked_by_me = db.query(Block.blocked_id).filter(Block.blocker_id == user_id)
    blocked_me = db.query(Block.blocker_id).filter(Block.blocked_id == user_id)
    return [row[0] for row in blocked_by_me.union(blocked_me).all()]


def create_report(db: Session, reporter_id: int, data: ReportCreate) -> Report:
    if reporter_id == data.reported_user_id:
        raise CannotReportSelfError(reporter_id)

    report = Report(
        reporter_id=reporter_id,
        reported_user_id=data.reported_user_id,
        reason=data.reason,
        description=data.description,
        status=ReportStatus.PENDING,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report
