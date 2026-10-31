import time
from collections import defaultdict, deque
from fastapi import APIRouter, HTTPException, Depends, Request, status
from backend.schemas import LoginRequest, TokenResponse, UserInfo
from backend.auth import verify_password, create_access_token, get_current_user
from backend.database import get_db

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Rate limit tracker for failed login attempts: key -> deque of timestamps
_failed_login_attempts = defaultdict(deque)

def check_login_rate_limit(key: str, max_failed: int = 5, window_seconds: int = 60):
    """Enforces rate limiting on consecutive failed login attempts."""
    now = time.time()
    q = _failed_login_attempts[key]
    while q and q[0] < now - window_seconds:
        q.popleft()
    if len(q) >= max_failed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Please wait 60 seconds before trying again."
        )

def record_failed_attempt(key: str):
    _failed_login_attempts[key].append(time.time())

def clear_failed_attempts(key: str):
    if key in _failed_login_attempts:
        del _failed_login_attempts[key]

@router.post("/login", response_model=TokenResponse)
def login(
    req: LoginRequest,
    request: Request,
    conn = Depends(get_db)
):
    """
    Authenticate an analyst, manager, or admin using bcrypt and issue a JWT token.
    Uses parameterized SQL and enforces rate limiting on failed attempts.
    """
    client_ip = request.client.host if request.client else "unknown"
    rate_key = f"{client_ip}:{req.username.strip().lower()}"

    # Check failed login rate limit (5 failed attempts per minute)
    check_login_rate_limit(rate_key, max_failed=5, window_seconds=60)

    cur = conn.cursor()
    cur.execute(
        "SELECT analyst_id, username, password_hash, role FROM analyst WHERE username = %s;",
        (req.username.strip(),)
    )
    user = cur.fetchone()
    cur.close()

    if not user or not verify_password(req.password, user["password_hash"]):
        record_failed_attempt(rate_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )

    # Successful login clears previous failed attempts
    clear_failed_attempts(rate_key)

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
