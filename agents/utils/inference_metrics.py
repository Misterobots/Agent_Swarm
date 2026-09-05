"""Provider-measured generation throughput; never infer tokens from text length."""
import math


def design_token_metrics(metrics: dict, model: str) -> dict:
    count = metrics.get("eval_count")
    duration = metrics.get("eval_duration")  # Ollama reports nanoseconds.
    valid_count = isinstance(count, int) and not isinstance(count, bool) and count >= 0
    valid_duration = (
        isinstance(duration, (int, float)) and not isinstance(duration, bool)
        and math.isfinite(duration) and duration > 0
    )
    measured = {"model": model, "source": "ollama", "measurement": "model_evaluation"}
    if not valid_count:
        content = "Design Studio: Generation ended; provider token measurements unavailable."
    else:
        measured["output_tokens"] = count
        content = f"Design Studio: Generated {count:,} output tokens"
        if valid_duration:
            seconds = duration / 1_000_000_000
            rate = count / seconds
            measured.update(evaluation_seconds=seconds, output_tokens_per_second=rate)
            content += f" · {rate:.1f} tokens/s (model evaluation)."
        else:
            content += "; provider throughput unavailable."
    return {"type": "status", "content": content, "metrics": measured}
