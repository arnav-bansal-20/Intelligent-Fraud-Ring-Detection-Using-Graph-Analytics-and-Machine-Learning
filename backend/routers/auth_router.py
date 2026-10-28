from fastapi import APIRouter, HTTPException, Depends, status
from backend.schemas import LoginRequest, TokenResponse, UserInfo
from backend.auth import verify_password, create_access_token, get_current_user
from backend.database import get_pg_connection

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest):
    """
    Authenticate an analyst, manager, or admin using bcrypt and issue a JWT token.
    Uses parameterized SQL to prevent injection.
    """
    conn = get_pg_connection()
    cur = conn.cursor()

    # Parameterized SQL query
    cur.execute(
        "SELECT analyst_id, username, password_hash, role FROM analyst WHERE username = %s;",
        (req.username.strip(),)
    )
    user = cur.fetchone()
    cur.close()
    conn.close()

    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )

    # Issue JWT Token with role and analyst_id
    token_payload = {
        "sub": user["username"],
        "analyst_id": user["analyst_id"],
        "role": user["role"]
    }
    access_token = create_access_token(token_payload)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserInfo(
            analyst_id=user["analyst_id"],
            username=user["username"],
            role=user["role"]
        )
    )

@router.get("/me", response_model=UserInfo)
def get_me(current_user: dict = Depends(get_current_user)):
    """Return currently authenticated user information and role."""
    return UserInfo(
        analyst_id=current_user["analyst_id"],
        username=current_user["username"],
        role=current_user["role"]
    )

