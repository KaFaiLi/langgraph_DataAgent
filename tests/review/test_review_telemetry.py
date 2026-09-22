"""Provider metadata should identify usage without retaining exception secrets."""

import json
from uuid import uuid4

from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult

from data_agent.review.telemetry import ReviewTelemetryHandler


def test_usage_records_model_role_tokens_and_redacts_provider_error(tmp_path):
    path = tmp_path / "usage.jsonl"
    handler = ReviewTelemetryHandler(path)
    identifier = uuid4()
    handler.on_llm_start(
        {},
        ["never logged"],
        run_id=identifier,
        metadata={"ls_model_name": "configured-model", "data_agent_name": "review-adjudicator"},
    )
    handler.on_llm_end(
        LLMResult(
            generations=[
                [
                    ChatGeneration(
                        message=AIMessage(
                            content="answer",
                            usage_metadata={
                                "input_tokens": 10,
                                "output_tokens": 4,
                                "total_tokens": 14,
                            },
                        )
                    )
                ]
            ]
        ),
        run_id=identifier,
    )
    handler.on_llm_error(RuntimeError("api_key=must-not-be-recorded"), run_id=uuid4())
    records = [json.loads(l) for l in path.read_text().splitlines()]
    assert records[0]["model_id"] == "configured-model"
    assert records[0]["agent_name"] == "review-adjudicator"
    assert records[1]["total_tokens"] == 14
    assert records[2]["error"] == "RuntimeError"
    assert "never logged" not in path.read_text() and "must-not-be-recorded" not in path.read_text()
