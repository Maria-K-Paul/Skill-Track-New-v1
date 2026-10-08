from __future__ import annotations

from ..models.input_models import PaperConfig
from ..prompts.validation_prompt import VALIDATION_SYSTEM_PROMPT
from ..services.distribution import build_blueprint


class ValidationAgent:
    def __init__(self):
        self.system_prompt = VALIDATION_SYSTEM_PROMPT

    def validate(self, input_data: dict) -> dict:
        config = PaperConfig.model_validate(input_data)
        blueprint = build_blueprint(
            config,
            config.difficulty_ratio.model_dump(),
            config.bloom_level_ratio.model_dump(),
        )
        return {
            "config": config,
            "blueprint": blueprint,
        }
