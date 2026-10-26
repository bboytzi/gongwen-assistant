"""用户管理。

路由顺序很重要：/me 系列必须写在 /{user_id} 之前，
否则 "me" 会被当作 UUID 解析，返回 422 而非进入对应处理函数。
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import hash_password, verify_password
from models.models import User, Document, KBDocument, LLMConfig, KnowledgeBase
from schemas.user import (
    UserResponse,
    AdminUserCreate,
    AdminUserUpdate,
    ProfileUpdate,
    PasswordChange,
)
from api.auth import get_current_user

router = APIRouter(prefix="/api/users", tags=["users"])

VALID_ROLES = ("admin", "user")
MIN_PASSWORD_LEN = 6


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return current_user


def _active_admin_count(db: Session, exclude_id=None) -> int:
    q = db.query(User).filter(User.role == "admin", User.is_active == True)  # noqa: E712
    if exclude_id is not None:
        q = q.filter(User.id != exclude_id)
    return q.count()


# ---------------------------------------------------------------- 个人资料

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.put("/me", response_model=UserResponse)
def update_me(
    req: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if req.username is not None:
        name = req.username.strip()
        if not name:
            raise HTTPException(status_code=400, detail="用户名不能为空")
        if name != current_user.username:
            taken = db.query(User).filter(
                User.username == name, User.id != current_user.id
            ).first()
            if taken:
                raise HTTPException(status_code=400, detail="用户名已被占用")
            current_user.username = name

    if req.display_name is not None:
        current_user.display_name = req.display_name.strip() or None

    if req.department is not None:
        current_user.department = req.department.strip() or None

    db.commit()
    db.refresh(current_user)
    return current_user


@router.put("/me/password")
def change_my_password(
    req: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(req.old_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="原密码不正确")
    if len(req.new_password) < MIN_PASSWORD_LEN:
        raise HTTPException(
            status_code=400, detail=f"新密码至少 {MIN_PASSWORD_LEN} 位"
        )
    if req.old_password == req.new_password:
        raise HTTPException(status_code=400, detail="新密码不能与原密码相同")

    current_user.password_hash = hash_password(req.new_password)
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------- 管理员操作

@router.get("", response_model=list[UserResponse])
def list_users(
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return db.query(User).order_by(User.created_at).all()


@router.post("", response_model=UserResponse)
def create_user(
    req: AdminUserCreate,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    name = req.username.strip()
    if not name:
        raise HTTPException(status_code=400, detail="用户名不能为空")
    if db.query(User).filter(User.username == name).first():
        raise HTTPException(status_code=400, detail="用户名已存在")
    if len(req.password) < MIN_PASSWORD_LEN:
        raise HTTPException(
            status_code=400, detail=f"密码至少 {MIN_PASSWORD_LEN} 位"
        )
    if req.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail="角色只能是 admin 或 user")

    user = User(
        username=name,
        display_name=(req.display_name or "").strip() or None,
        password_hash=hash_password(req.password),
        department=(req.department or "").strip() or None,
        role=req.role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # 新用户自动创建个人知识库，用显示名命名更直观
    db.add(KnowledgeBase(
        user_id=user.id,
        name=f"{user.display_name or user.username}的个人库",
        level="personal",
    ))
    db.commit()

    return user


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: UUID,
    req: AdminUserUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 管理员不能对自己降级或停用，避免把自己锁在外面
    if user.id == admin.id:
        if req.role is not None and req.role != "admin":
            raise HTTPException(status_code=400, detail="不能取消自己的管理员身份")
        if req.is_active is False:
            raise HTTPException(status_code=400, detail="不能停用自己的账号")

    # 任何会导致「没有启用的管理员」的操作都拒绝
    losing_admin = (
        (req.role is not None and req.role != "admin" and user.role == "admin")
        or (req.is_active is False and user.role == "admin")
    )
    if losing_admin and _active_admin_count(db, exclude_id=user.id) == 0:
        raise HTTPException(
            status_code=400, detail="系统至少需要保留一个启用的管理员"
        )

    if req.username is not None:
        name = req.username.strip()
        if not name:
            raise HTTPException(status_code=400, detail="用户名不能为空")
        if name != user.username:
            taken = db.query(User).filter(
                User.username == name, User.id != user.id
            ).first()
            if taken:
                raise HTTPException(status_code=400, detail="用户名已被占用")
            user.username = name

    if req.display_name is not None:
        user.display_name = req.display_name.strip() or None

    if req.department is not None:
        user.department = req.department.strip() or None

    if req.role is not None:
        if req.role not in VALID_ROLES:
            raise HTTPException(status_code=400, detail="角色只能是 admin 或 user")
        user.role = req.role

    if req.is_active is not None:
        user.is_active = req.is_active

    if req.password:
        if len(req.password) < MIN_PASSWORD_LEN:
            raise HTTPException(
                status_code=400, detail=f"密码至少 {MIN_PASSWORD_LEN} 位"
            )
        user.password_hash = hash_password(req.password)

    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}")
def delete_user(
    user_id: UUID,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="不能删除自己的账号")
    if user.role == "admin" and _active_admin_count(db, exclude_id=user.id) == 0:
        raise HTTPException(
            status_code=400, detail="系统至少需要保留一个启用的管理员"
        )

    # 有业务数据时外键会阻止删除，提前给出可执行的建议
    related = (
        db.query(Document).filter(Document.user_id == user.id).count()
        + db.query(KBDocument).filter(KBDocument.user_id == user.id).count()
        + db.query(LLMConfig).filter(LLMConfig.user_id == user.id).count()
    )
    if related > 0:
        raise HTTPException(
            status_code=400,
            detail=f"该用户有 {related} 条关联数据，删除会丢失，建议改为停用账号",
        )

    db.delete(user)
    db.commit()
    return {"ok": True}
