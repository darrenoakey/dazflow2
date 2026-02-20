"""Integration tests for agent_link module nodes.

These tests call the real agent-link service running at https://localhost:8900.
agent-link must be running for these tests to pass.
"""

import pytest

from modules.agent_link.nodes import (
    _call,
    execute_email_list,
    execute_email_list_folders,
    execute_email_search,
    execute_email_trigger,
    execute_agent_link_call,
    register_email_trigger,
)


# ---------------------------------------------------------------------------
# Helper: skip all tests if agent-link is not reachable
# ---------------------------------------------------------------------------


def _agent_link_available() -> bool:
    try:
        import httpx
        from modules.agent_link.nodes import _ssl_ctx, AGENT_LINK_URL

        with httpx.Client(verify=_ssl_ctx(), timeout=5) as client:
            resp = client.get(f"{AGENT_LINK_URL}/api/v1/health")
            return resp.status_code == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _agent_link_available(),
    reason="agent-link not available at https://localhost:8900",
)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAgentLinkCall:
    def test_list_messages_returns_result(self):
        results = _call("mail", "list-messages", {"max_results": 1})
        assert isinstance(results, list)
        assert len(results) >= 1

    def test_list_messages_has_messages_key(self):
        results = _call("mail", "list-messages", {"max_results": 1})
        for r in results:
            assert "messages" in r

    def test_invalid_category_raises(self):
        with pytest.raises(Exception):
            _call("nonexistent_category", "nonexistent_function", {})


class TestEmailTrigger:
    def test_execute_returns_sample(self):
        result = execute_email_trigger({}, None)
        assert isinstance(result, list)
        assert len(result) == 1
        sample = result[0]
        assert "id" in sample
        assert "from" in sample
        assert "subject" in sample

    def test_register_returns_push_type(self):
        registration = register_email_trigger({}, lambda x: None)
        assert registration["type"] == "push"
        assert callable(registration["listener"])


class TestEmailList:
    def test_returns_messages_dict(self):
        result = execute_email_list({"max_results": 5}, None)
        assert isinstance(result, list)
        assert len(result) == 1
        assert "messages" in result[0]
        assert "count" in result[0]

    def test_count_matches_messages(self):
        result = execute_email_list({"max_results": 5}, None)
        assert result[0]["count"] == len(result[0]["messages"])

    def test_max_results_respected(self):
        result = execute_email_list({"max_results": 2}, None)
        assert result[0]["count"] <= 2


class TestEmailSearch:
    def test_returns_messages(self):
        result = execute_email_search({"query": "in:inbox", "max_results": 3}, None)
        assert isinstance(result, list)
        assert "messages" in result[0]

    def test_empty_results_for_impossible_query(self):
        result = execute_email_search(
            {"query": "from:impossibleaddress12345@noreply.invalid.xyz", "max_results": 1},
            None,
        )
        assert result[0]["count"] == 0


class TestEmailListFolders:
    def test_returns_folders(self):
        result = execute_email_list_folders({}, None)
        assert isinstance(result, list)
        assert "folders" in result[0]
        assert isinstance(result[0]["folders"], list)


class TestGenericCall:
    def test_generic_mail_list(self):
        result = execute_agent_link_call(
            {"category": "mail", "function": "list-messages", "params": '{"max_results": 1}'},
            None,
        )
        assert isinstance(result, list)

    def test_missing_category_returns_error(self):
        result = execute_agent_link_call({"category": "", "function": "list-messages"}, None)
        assert "error" in result[0]

    def test_invalid_json_params_returns_error(self):
        result = execute_agent_link_call(
            {"category": "mail", "function": "list-messages", "params": "not json"},
            None,
        )
        assert "error" in result[0]
