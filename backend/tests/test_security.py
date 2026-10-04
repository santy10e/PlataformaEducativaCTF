from app.security import LoginRateLimiter, hash_password, verify_password


def test_argon2_password_hashing() -> None:
    encoded = hash_password("correct horse battery staple")
    assert encoded.startswith("$argon2id$")
    assert verify_password(encoded, "correct horse battery staple")
    assert not verify_password(encoded, "incorrect")


def test_login_limiter_tracks_user_and_ip_windows() -> None:
    limiter = LoginRateLimiter(limit=2, window_seconds=10)
    assert limiter.allow("user:a", "ip:1", now=0)
    assert limiter.allow("user:a", "ip:1", now=1)
    assert not limiter.allow("user:a", "ip:1", now=2)
    assert limiter.allow("user:b", "ip:2", now=2)
    assert limiter.allow("user:a", "ip:1", now=11)


def test_login_limiter_uses_burst_cap_for_shared_proxy_and_bounds_keys() -> None:
    limiter = LoginRateLimiter(limit=2, window_seconds=300, ip_limit=10, max_keys=4)
    for index in range(3):
        assert limiter.allow(f"user:{index}", "ip:school-proxy", now=float(index))
    assert len(limiter.attempts) <= 4
    assert not limiter.allow("user:new", "ip:school-proxy", now=4)
    assert len(limiter.attempts) <= 4
    assert limiter.allow("user:later", "ip:school-proxy", now=301)
