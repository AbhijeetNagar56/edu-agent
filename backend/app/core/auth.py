import os
from typing import List, Optional
from fastapi import Header, HTTPException, Security, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from pydantic import BaseModel

from app.core.config import settings
from app.core.errors import APIException
from app.core.logging import logger
from app.services.supabase_client import get_supabase_client

security_bearer = HTTPBearer(auto_error=False)

# Deterministic UUIDs for development / test accounts
DEV_STUDENT_ID = "00000000-0000-0000-0000-000000000302"
DEV_FACULTY_ID = "00000000-0000-0000-0000-000000000101"
DEV_ADMIN_ID = "00000000-0000-0000-0000-000000000001"


class AuthUser(BaseModel):
    id: str
    email: str
    role: str = "student"
    full_name: Optional[str] = None


def verify_cron_secret(
    x_internal_secret: Optional[str] = Header(None, alias="X-Internal-Secret")
) -> bool:
    expected_secret = settings.INTERNAL_CRON_SECRET
    if not x_internal_secret or x_internal_secret != expected_secret:
        logger.warning("Unauthorized internal cron request attempt.")
        raise APIException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="UNAUTHORIZED",
            message="Missing or invalid internal cron secret header."
        )
    return True


def extract_role_from_user(auth_user) -> str:
    """
    Extracts the user role strictly from trusted server-side app_metadata
    or the public.profiles table. NEVER trusts mutable client user_metadata.
    """
    app_meta = auth_user.app_metadata or {}
    role = app_meta.get("role")
    if role in ("student", "faculty", "admin"):
        return role

    client = get_supabase_client()
    if client:
        try:
            res = client.table("profiles").select("role").eq("id", str(auth_user.id)).limit(1).execute()
            if res.data and len(res.data) > 0:
                profile_role = res.data[0].get("role")
                if profile_role in ("student", "faculty", "admin"):
                    return profile_role
        except Exception as e:
            logger.warning(f"Could not read profile role for user {auth_user.id}: {e}")

    return "student"


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer)
) -> AuthUser:
    """
    Authenticates the caller and derives authoritative identity.
    Rejects missing or invalid credentials in all environments.
    Strictly forbids mock tokens in production.
    """
    if not credentials or not credentials.credentials:
        raise APIException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="UNAUTHORIZED",
            message="Missing Authorization Bearer token."
        )

    token = credentials.credentials.strip()
    if not token:
        raise APIException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="UNAUTHORIZED",
            message="Empty authorization token."
        )

    # 1. Development/Testing mock token fast-path
    if token.startswith("mock-") or token.startswith("dev-"):
        if settings.ENVIRONMENT != "development":
            logger.error("Security alert: Mock dev token rejected in non-development environment.")
            raise APIException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                code="UNAUTHORIZED",
                message="Mock authentication tokens are strictly prohibited in production."
            )

        custom_id = token.split(":", 1)[1] if ":" in token else None
        if "admin" in token:
            return AuthUser(
                id=custom_id or DEV_ADMIN_ID,
                email="admin@eduagents.app",
                role="admin",
                full_name="System Admin"
            )
        elif "faculty" in token:
            return AuthUser(
                id=custom_id or DEV_FACULTY_ID,
                email="faculty@eduagents.app",
                role="faculty",
                full_name="Dr. Sarah Lin"
            )
        else:
            return AuthUser(
                id=custom_id or DEV_STUDENT_ID,
                email="student@eduagents.app",
                role="student",
                full_name="Jordan Taylor"
            )

    # 2. Local Cryptographic JWT Verification (when secret configured or in automated tests)
    if settings.SUPABASE_JWT_SECRET:
        try:
            payload = jwt.decode(
                token,
                settings.SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                audience="authenticated",
                options={
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_aud": True,
                }
            )
            user_id = payload.get("sub")
            if not user_id:
                raise APIException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    code="UNAUTHORIZED",
                    message="Token missing subject claim."
                )
            app_metadata = payload.get("app_metadata") or {}
            role = app_metadata.get("role")
            if role not in ("student", "faculty", "admin"):
                role = "student"
            email = payload.get("email", "")
            user_metadata = payload.get("user_metadata") or {}
            full_name = user_metadata.get("full_name") or user_metadata.get("name") or email

            return AuthUser(
                id=str(user_id),
                email=email,
                role=role,
                full_name=full_name,
            )
        except jwt.ExpiredSignatureError:
            raise APIException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                code="UNAUTHORIZED",
                message="Authentication token has expired."
            )
        except jwt.InvalidTokenError as ite:
            raise APIException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                code="UNAUTHORIZED",
                message=f"Invalid token signature or claims: {ite}"
            )

    # 3. Supabase Auth token verification via Supabase Client
    client = get_supabase_client()
    if client:
        try:
            response = client.auth.get_user(token)
            auth_user = response.user
            if not auth_user:
                raise ValueError("Supabase Auth returned null user.")

            role = extract_role_from_user(auth_user)
            user_meta = auth_user.user_metadata or {}
            full_name = user_meta.get("full_name") or user_meta.get("name") or auth_user.email

            return AuthUser(
                id=str(auth_user.id),
                email=auth_user.email or "",
                role=role,
                full_name=full_name
            )
        except Exception as e:
            logger.warning(f"Supabase token verification failed: {e}")
            raise APIException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                code="UNAUTHORIZED",
                message="Invalid or expired access token."
            )

    # 4. Strict rejection if token is neither verified by Supabase nor by local secret
    logger.warning("Rejecting unverified JWT token: signature verification failed or secret not configured.")
    raise APIException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        code="UNAUTHORIZED",
        message="Invalid or unverified authentication token."
    )


def require_role(allowed_roles: List[str]):
    def role_checker(user: AuthUser = Depends(get_current_user)) -> AuthUser:
        if user.role not in allowed_roles:
            raise APIException(
                status_code=status.HTTP_403_FORBIDDEN,
                code="FORBIDDEN",
                message=f"Access denied. Requires one of roles: {', '.join(allowed_roles)}"
            )
        return user
    return role_checker
