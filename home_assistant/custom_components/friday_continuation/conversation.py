"""A safe continuation wrapper for Friday's active Assist conversation agent."""

from __future__ import annotations

from typing import Literal

from homeassistant.components import conversation
from homeassistant.components.conversation import (
    ConversationEntity,
    ConversationInput,
    ConversationResult,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_TARGET_ENTITY_ID, DEFAULT_TARGET_ENTITY_ID, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Friday continuation conversation entity."""
    async_add_entities([FridayContinuationEntity(hass, entry)])


class FridayContinuationEntity(ConversationEntity):
    """Delegate to Friday and keep Assist UI open only for a genuine follow-up."""

    _attr_has_entity_name = True
    _attr_name = "Friday Continuation"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self._target_entity_id = entry.data[CONF_TARGET_ENTITY_ID]
        self._attr_unique_id = entry.entry_id

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        return MATCH_ALL

    async def async_process(self, user_input: ConversationInput) -> ConversationResult:
        """Use Friday's existing agent, preserving its tools and chat history."""
        target = conversation.async_get_agent(self.hass, self._target_entity_id)
        if target is None:
            raise ValueError(
                f"Friday target agent {self._target_entity_id} is unavailable"
            )
        if isinstance(target, ConversationEntity):
            result = await target.internal_async_process(user_input)
        else:
            result = await target.async_process(user_input)
        speech = result.response.speech.get("plain", {}).get("speech", "")
        return ConversationResult(
            response=result.response,
            conversation_id=result.conversation_id,
            continue_conversation=_needs_follow_up(speech),
        )


def _needs_follow_up(speech: str) -> bool:
    """Avoid a hot mic except when Friday explicitly needs an answer."""
    text = speech.strip().lower()
    if not text:
        return False
    return text.endswith("?") or any(
        phrase in text
        for phrase in (
            "which one",
            "would you like",
            "do you want",
            "would you prefer",
            "which do you",
            "what would you",
            "shall i",
            "should i",
            "choose from",
            "select from",
            "pick from",
            "who should",
            "where should",
        )
    )
