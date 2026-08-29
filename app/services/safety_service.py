from sqlalchemy import and_, exists, or_
from sqlalchemy.orm import Session

from app.models.block import Block
from app.models.report import Report, ReportStatus
from app.models.user import User
from app.schemas.safety import ReportCreate
from app.services.trust_service import recompute_trust_score


class CannotBlockSelfError(Exception):
    pass


class AlreadyBlockedError(Exception):
    pass


class CannotReportSelfError(Exception):
    pass


class BlockNotFoundError(Exception):
    pass


class ReportNotFoundError(Exception):
    pass


def block_user(db: Session, blocker_id: int, blocked_id: int) -> Block:
    if blocker_id == blocked_id:
        raise CannotBlockSelfError(blocker_id)

    already_exists = db.query(
        exists().where(Block.blocker_id == blocker_id, Block.blocked_id == blocked_id)
    ).scalar()
    if already_exists:
        raise AlreadyBlockedError(blocked_id)

    block = Block(blocker_id=blocker_id, blocked_id=blocked_id)
    db.add(block)
    db.commit()
    db.refresh(block)
    recompute_trust_score(db, blocked_id)
    return block


def unblock_user(db: Session, blocker_id: int, blocked_id: int) -> None:
    block = (
        db.query(Block)
        .filter(Block.blocker_id == blocker_id, Block.blocked_id == blocked_id)
        .first()
    )
    if block is None:
        raise BlockNotFoundError(blocked_id)

    db.delete(block)
    db.commit()
    recompute_trust_score(db, blocked_id)


def is_blocked(db: Session, user_a_id: int, user_b_id: int) -> bool:
    return db.query(
        exists().where(
            or_(
                and_(Block.blocker_id == user_a_id, Block.blocked_id == user_b_id),
                and_(Block.blocker_id == user_b_id, Block.blocked_id == user_a_id),
            )
        )
    ).scalar()


def blocked_user_ids(db: Session, user_id: int) -> list[int]:
    blocked_by_me = db.query(Block.blocked_id).filter(Block.blocker_id == user_id)
    blocked_me = db.query(Block.blocker_id).filter(Block.blocked_id == user_id)
    return [row[0] for row in blocked_by_me.union(blocked_me).all()]


def list_my_blocks(db: Session, user_id: int, skip: int = 0, limit: int = 50) -> list[tuple[Block, User]]:
    """Blocks the given user created themselves (not blocks placed on them by others)."""
    blocks = (
        db.query(Block)
        .filter(Block.blocker_id == user_id)
        .order_by(Block.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    if not blocks:
        return []
    users_by_id = {
        user.id: user
        for user in db.query(User).filter(User.id.in_([b.blocked_id for b in blocks])).all()
    }
    return [(block, users_by_id[block.blocked_id]) for block in blocks if block.blocked_id in users_by_id]


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
    recompute_trust_score(db, data.reported_user_id)
    return report


def list_reports(
    db: Session,
    status: ReportStatus | None = None,
    reported_user_id: int | None = None,
    skip: int = 0,
    limit: int = 50,
) -> list[Report]:
    query = db.query(Report)
    if status is not None:
        query = query.filter(Report.status == status)
    if reported_user_id is not None:
        query = query.filter(Report.reported_user_id == reported_user_id)
    return query.order_by(Report.created_at.desc()).offset(skip).limit(limit).all()


def update_report_status(db: Session, report_id: int, new_status: ReportStatus) -> Report:
    report = db.get(Report, report_id)
    if report is None:
        raise ReportNotFoundError(report_id)

    report.status = new_status
    db.commit()
    db.refresh(report)
    recompute_trust_score(db, report.reported_user_id)
    return report
