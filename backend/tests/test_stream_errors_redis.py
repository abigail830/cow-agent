from app.platform.llm.stream_errors import user_facing_stream_error


def test_redis_connection_error_is_user_friendly():
    msg = user_facing_stream_error(
        Exception(
            "Error 8 connecting to redis-12610.example.cloud.redislabs.com:12610. "
            "nodename nor servname provided, or not known."
        )
    )
    assert "Redis" in msg
    assert "REDIS_URL" in msg
