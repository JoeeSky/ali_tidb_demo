from agent_demo.preflight import validate_config


def valid_config() -> dict[str, str]:
    return {
        "TIDB_DSN": "mysql+pymysql://demo:secret@gateway.example.com:4000/demo",
        "TIDB_DATABASE": "agent_demo",
        "TIDB_SSL_CA": __file__,
        "DASHSCOPE_API_KEY": "test-only-key",
        "BAILIAN_BASE_URL": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "BAILIAN_CHAT_MODEL": "qwen-max",
        "EMBEDDING_MODEL": "text-embedding-v4",
        "EMBEDDING_DIMENSIONS": "1024",
    }


def test_valid_base_config() -> None:
    assert validate_config(valid_config()) == []


def test_missing_values_are_reported_without_secrets() -> None:
    config = valid_config()
    config["DASHSCOPE_API_KEY"] = ""
    errors = validate_config(config)
    assert errors == ["缺少配置：DASHSCOPE_API_KEY"]
    assert "test-only-key" not in " ".join(errors)


def test_vector_dimension_must_match_schema() -> None:
    config = valid_config()
    config["EMBEDDING_DIMENSIONS"] = "768"
    assert "基础版 EMBEDDING_DIMENSIONS 必须为 1024，与 VECTOR(1024) 一致" in validate_config(config)


def test_agent_id_is_only_required_in_agent_mode() -> None:
    config = valid_config()
    assert validate_config(config) == []
    assert "缺少配置：BAILIAN_APP_ID" in validate_config(config, require_agent=True)


def test_dsn_requires_database_name() -> None:
    config = valid_config()
    config["TIDB_DSN"] = "mysql+pymysql://demo:secret@gateway.example.com:4000/"
    assert "TIDB_DSN 必须包含数据库名，例如 /agent_demo" in validate_config(config)
