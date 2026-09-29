from app.platform.llm.stream_errors import is_leaked_model_service_text, user_facing_stream_error


def test_redis_connection_error_is_user_friendly():
    msg = user_facing_stream_error(
        Exception(
            "Error 8 connecting to redis-12610.example.cloud.redislabs.com:12610. "
            "nodename nor servname provided, or not known."
        )
    )
    assert "Session cache (Redis)" in msg
    assert "REDIS_URL" in msg
    assert "PostgreSQL" in msg


def test_dashscope_input_length_is_user_friendly():
    msg = user_facing_stream_error(
        Exception(
            "Error code: 400 - {'error': {'message': "
            "'<400> InternalError.Algo.InvalidParameter: Range of input length should be [1, 983015]'}}"
        )
    )
    assert "input limit" in msg.lower()


def test_leaked_service_error_text_detected():
    assert is_leaked_model_service_text(
        "plan… (*<class 'app.platform.llm.openai_compatible_client.OpenAICompatibleReasoningClient'> "
        "service failed to complete the prompt: Error code: 400"
    )
