from __future__ import annotations

GENERATED_MODEL_PREFIX = "gz_model--"


def generated_gz_model_name(namespace: str) -> str:
    return f"{GENERATED_MODEL_PREFIX}{namespace}"


__all__ = ["GENERATED_MODEL_PREFIX", "generated_gz_model_name"]
