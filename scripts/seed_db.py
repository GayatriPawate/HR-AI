"""
Seed the database with initial roles, permissions, and an admin user.
Run: python scripts/seed_db.py
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.base import init_db, AsyncSessionLocal
from app.db.models import Role, Permission, RolePermission, User, UserRole
from app.auth.password import hash_password


ROLES = [
    {"name": "admin", "description": "HR Admin with full access"},
    {"name": "panel", "description": "Interview panel member"},
]

PERMISSIONS = [
    "upload_cv", "create_jd", "analyze_jd", "run_matching",
    "view_dashboard", "view_analytics", "schedule_interview",
    "update_status", "assign_panel", "manage_users", "export_data",
    "generate_questions", "submit_feedback", "view_assigned_candidates",
]

ADMIN_PERMISSIONS = [p for p in PERMISSIONS if p != "generate_questions" and p != "submit_feedback" and p != "view_assigned_candidates"]
PANEL_PERMISSIONS = ["generate_questions", "submit_feedback", "view_assigned_candidates"]

DEFAULT_ADMIN = {
    "email": "admin@hrplatform.com",
    "password": "Admin@123",
    "full_name": "HR Administrator",
    "department": "Human Resources",
}

PANEL_USERS = [
    {
        "email": "panel@hrplatform.com",
        "password": "Panel@123",
        "full_name": "Panel Interviewer",
        "department": "Engineering",
        "ms_email": None,
    },
    {
        "email": "priya.sharma@hrplatform.com",
        "password": "Panel@123",
        "full_name": "Priya Sharma",
        "department": "Backend Engineering",
        "ms_email": "priya.sharma@hrplatform.com",
    },
    {
        "email": "rahul.mehta@hrplatform.com",
        "password": "Panel@123",
        "full_name": "Rahul Mehta",
        "department": "Frontend Engineering",
        "ms_email": "rahul.mehta@hrplatform.com",
    },
    {
        "email": "anita.desai@hrplatform.com",
        "password": "Panel@123",
        "full_name": "Anita Desai",
        "department": "Data Science",
        "ms_email": "anita.desai@hrplatform.com",
    },
    {
        "email": "vikram.nair@hrplatform.com",
        "password": "Panel@123",
        "full_name": "Vikram Nair",
        "department": "DevOps",
        "ms_email": "vikram.nair@hrplatform.com",
    },
]


async def seed():
    await init_db()
    print("Database initialized.")

    async with AsyncSessionLocal() as db:
        # Create roles
        role_map = {}
        for role_data in ROLES:
            from sqlalchemy import select
            result = await db.execute(select(Role).where(Role.name == role_data["name"]))
            role = result.scalar_one_or_none()
            if not role:
                role = Role(**role_data)
                db.add(role)
                await db.flush()
                print(f"Created role: {role_data['name']}")
            role_map[role_data["name"]] = role

        # Create permissions
        perm_map = {}
        for perm_name in PERMISSIONS:
            result = await db.execute(select(Permission).where(Permission.name == perm_name))
            perm = result.scalar_one_or_none()
            if not perm:
                perm = Permission(name=perm_name, description=perm_name.replace("_", " ").title())
                db.add(perm)
                await db.flush()
            perm_map[perm_name] = perm

        # Assign permissions to roles
        for perm_name in ADMIN_PERMISSIONS:
            result = await db.execute(
                select(RolePermission).where(
                    RolePermission.role_id == role_map["admin"].id,
                    RolePermission.permission_id == perm_map[perm_name].id,
                )
            )
            if not result.scalar_one_or_none():
                db.add(RolePermission(role_id=role_map["admin"].id, permission_id=perm_map[perm_name].id))

        for perm_name in PANEL_PERMISSIONS:
            result = await db.execute(
                select(RolePermission).where(
                    RolePermission.role_id == role_map["panel"].id,
                    RolePermission.permission_id == perm_map[perm_name].id,
                )
            )
            if not result.scalar_one_or_none():
                db.add(RolePermission(role_id=role_map["panel"].id, permission_id=perm_map[perm_name].id))

        await db.commit()
        print("Roles and permissions configured.")

        # Create default users
        import uuid

        all_users = [(DEFAULT_ADMIN, "admin")] + [(p, "panel") for p in PANEL_USERS]
        for user_data, role_name in all_users:
            result = await db.execute(select(User).where(User.email == user_data["email"]))
            existing = result.scalar_one_or_none()
            if not existing:
                user = User(
                    id=str(uuid.uuid4()),
                    email=user_data["email"],
                    password_hash=hash_password(user_data["password"]),
                    full_name=user_data["full_name"],
                    department=user_data["department"],
                    ms_email=user_data.get("ms_email"),
                )
                db.add(user)
                await db.flush()
                db.add(UserRole(user_id=user.id, role_id=role_map[role_name].id))
                await db.commit()
                print(f"Created user: {user_data['email']} ({role_name})")
            else:
                print(f"User already exists: {user_data['email']}")

    print("\nSeed complete!")
    print(f"Admin login: {DEFAULT_ADMIN['email']} / {DEFAULT_ADMIN['password']}")
    for p in PANEL_USERS:
        print(f"Panel login: {p['email']} / {p['password']}")


if __name__ == "__main__":
    asyncio.run(seed())
