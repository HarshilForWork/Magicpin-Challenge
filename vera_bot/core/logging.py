import json
from datetime import datetime
from pathlib import Path

import mlflow

from vera_bot.core.config import settings
from vera_bot.utils.tokenizer import estimate_total_cost


def _mlflow_enabled() -> bool:
    return not settings.get("app", {}).get("production", False)


def _file_logging_enabled() -> bool:
    return settings.get("app", {}).get("file_logging", False)


def _append_file_log(
    trigger_kind: str,
    merchant_id: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    input_context: str | None,
    output: str,
    rationale: str,
) -> None:
    base_dir = Path(__file__).resolve().parents[2]
    log_dir = base_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "llm_compositions.txt"

    total_tokens = (prompt_tokens or 0) + (completion_tokens or 0)
    entry = [
        "-----",
        f"time_utc: {datetime.utcnow().isoformat()}",
        f"trigger_kind: {trigger_kind}",
        f"merchant_id: {merchant_id}",
        f"model: {model}",
        f"prompt_tokens: {prompt_tokens}",
        f"completion_tokens: {completion_tokens}",
        f"total_tokens: {total_tokens}",
        "input_context:",
        input_context or "<none>",
        "output_body:",
        output or "<empty>",
        "rationale:",
        rationale or "<empty>",
        "",
    ]

    with log_path.open("a", encoding="utf-8", errors="ignore") as handle:
        handle.write("\n".join(entry))


def setup_mlflow():
    if not _mlflow_enabled():
        return
    mlflow.set_tracking_uri(settings["mlflow"]["tracking_uri"])
    mlflow.set_experiment(settings["mlflow"]["experiment_name"])


def log_composition(
    trigger_kind: str,
    merchant_id: str,
    prompt: str,
    filtered_context: dict,
    output: str,
    rationale: str,
    model: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    system_prompt: str | None = None,
    input_context: str | None = None,
    full_prompt: str | None = None,
):
    if not _mlflow_enabled() or not settings["mlflow"]["log_prompts"]:
        if _file_logging_enabled():
            _append_file_log(
                trigger_kind=trigger_kind,
                merchant_id=merchant_id,
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                input_context=input_context,
                output=output,
                rationale=rationale,
            )
        return
    
    cost_breakdown = estimate_total_cost(prompt_tokens, completion_tokens, model)
    
    with mlflow.start_run(run_name=f"{trigger_kind}_{merchant_id}_{datetime.utcnow().isoformat()}"):
        mlflow.log_param("trigger_kind", trigger_kind)
        mlflow.log_param("merchant_id", merchant_id)
        mlflow.log_param("model", model)
        mlflow.log_text(prompt, "prompt.txt")
        if system_prompt:
            mlflow.log_text(system_prompt, "system_prompt.txt")
        if input_context:
            mlflow.log_text(input_context, "input_context.txt")
        if full_prompt:
            mlflow.log_text(full_prompt, "full_prompt.txt")
        mlflow.log_text(output, "output.txt")
        mlflow.log_text(rationale, "rationale.txt")
        mlflow.log_text(json.dumps(filtered_context, indent=2), "filtered_context.json")
        
        # Token metrics
        mlflow.log_metric("prompt_tokens", prompt_tokens)
        mlflow.log_metric("completion_tokens", completion_tokens)
        mlflow.log_metric("total_tokens", cost_breakdown["total_tokens"])
        
        # Cost metrics
        mlflow.log_metric("prompt_cost_usd", cost_breakdown["prompt_cost"])
        mlflow.log_metric("completion_cost_usd", cost_breakdown["completion_cost"])
        mlflow.log_metric("total_cost_usd", cost_breakdown["total_cost"])
        
        # Log cost breakdown as params for easy viewing
        mlflow.log_param("cost_breakdown", json.dumps(cost_breakdown, indent=2))

    if _file_logging_enabled():
        _append_file_log(
            trigger_kind=trigger_kind,
            merchant_id=merchant_id,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            input_context=input_context,
            output=output,
            rationale=rationale,
        )


def log_judge_reply(
    conversation_id: str,
    merchant_id: str,
    message: str,
    detected_intent: str,
    bot_action: str,
    bot_body: str,
):
    if not _mlflow_enabled() or not settings["mlflow"]["log_judge_replies"]:
        return
    with mlflow.start_run(run_name=f"reply_{conversation_id}_{datetime.utcnow().isoformat()}"):
        mlflow.log_param("conversation_id", conversation_id)
        mlflow.log_param("merchant_id", merchant_id)
        mlflow.log_param("detected_intent", detected_intent)
        mlflow.log_param("bot_action", bot_action)
        mlflow.log_text(message, "merchant_message.txt")
        mlflow.log_text(bot_body or "", "bot_response.txt")


def log_filter_result(trigger_kind: str, merchant_id: str, filter_output: dict):
    if not _mlflow_enabled() or not settings["mlflow"]["log_filter_results"]:
        return
    with mlflow.start_run(run_name=f"filter_{trigger_kind}_{merchant_id}"):
        mlflow.log_param("trigger_kind", trigger_kind)
        mlflow.log_param("merchant_id", merchant_id)
        mlflow.log_text(json.dumps(filter_output, indent=2), "filter_output.json")


def log_validation_failure(trigger_kind: str, merchant_id: str, reason: str, body: str):
    if not _mlflow_enabled():
        return
    with mlflow.start_run(run_name=f"validation_fail_{trigger_kind}_{merchant_id}"):
        mlflow.log_param("trigger_kind", trigger_kind)
        mlflow.log_param("merchant_id", merchant_id)
        mlflow.log_param("failure_reason", reason)
        mlflow.log_text(body, "failed_body.txt")
