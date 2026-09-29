"""providers/model_client.py — who can actually serve this model id.

Every agent in this harness imported ``phi.model.ollama.Ollama`` and stopped there, which
was true for as long as every model lived on a GPU in the room. Plan D8 made that false: a
model the user selected from a provider catalogue is a real id that no Ollama host serves,
and asking ``get_best_host_for_model()`` about one returns a machine that will answer
"model not found" rather than admit it is the wrong machine.

So the question is asked once, here, before any Ollama-specific option is computed. The
answer is a phi model object or a refusal that names the provider — never an Ollama client
pointed at a model it cannot load, which is the failure this module exists to prevent.

Two separate questions, deliberately kept apart:

* ``is_honourable_pick`` — is the string the client sent the name of a model, or the name
  of a UI tier? Only the second is not honourable.
* ``provider_of`` — does a connected provider serve this id, which decides the client.

A caller that conflates them gets either a turn answered by a different model than the one
named, or an Ollama host asked to load a gateway tag.
"""

import logging

logger = logging.getLogger("Router")

# Names the desktop sends for a UI *tier* rather than a model. This is the set the
# "we deliberately do NOT honor ctx['model']" comment in handlers/conversation.py was
# protecting against — and it is a closed list of sentinels, not a rule about model
# identifiers. `qwen/qwen3.8-flash` is a real id the runtime resolved and the gate
# admitted; treating it like one of these is what made the picker decorative.
UI_TIER_NAMES = frozenset({
    "swarm",
    "hive-fast",
    "default",
    "Home-AI-Swarm",
    "",
})


class ProviderNotServed(RuntimeError):
    """A model resolves to a provider this path cannot build a client for, or to one whose
    key is missing.

    Raised rather than answered with an Ollama client. The alternative is a turn that
    fails on a GPU host with a message about a model that host has never heard of, which
    is the class of silent substitution this module was written to end.
    """


def is_honourable_pick(model_id: str | None) -> bool:
    """Did the client name a model, as opposed to a tier or nothing at all?"""
    return bool(model_id) and model_id.strip() not in UI_TIER_NAMES


def provider_of(model_id: str | None, uid: str = "") -> str | None:
    """The provider that owns this id, or None when no provider does.

    Two sources, in that order, because the first one is not durable.

    ``providers.registry.provider_for`` is the same index the model gate and the picker
    consult, and it is correct about every *declared* provider list. For a gateway it is
    only as good as this process's catalogue cache: the OpenRouter list is fetched, so a
    freshly started process knows the four fallback ids and nothing else — measured on
    2026-09-29, ``known_ids()`` returned 4 with ``fetched_at: None`` in a cold process
    while the running server held 464. Classifying a gateway id from that alone answers
    "not a provider model", and the caller then builds an Ollama client for a tag no GPU
    host has ever seen.

    So the second source is the user's own stored selection, which is a Postgres row
    rather than an in-memory cache: an id they chose under a connected provider *is* that
    provider's, whether or not this process has fetched anything yet.
    """
    if not model_id or not is_honourable_pick(model_id):
        return None
    requested = model_id.strip()

    from providers.registry import provider_for

    owner = provider_for(requested)
    if owner:
        return owner

    if not uid:
        return None
    try:
        from provider_keys import list_connected

        for row in list_connected(uid):
            provider = row.get("provider")
            if provider and requested in (row.get("selected_models") or []):
                return provider
    except Exception as exc:  # a store that will not answer is not evidence of absence
        logger.warning(f"model_client: selection lookup failed for {requested}: {exc}")
    return None


def _provider_api_key(provider: str, uid: str) -> str:
    """The caller's own stored key for `provider`, decrypted for this turn only.

    Never logged, never returned in an exception message, never written anywhere. It is
    the same Fernet-decrypted path ``list_models`` already uses, so no new store exists
    and a turn cannot ask for a key belonging to another user.

    **Constraint on every caller of `model_client`.** A phi model object holds the key as
    a field, and phi's `repr()` prints its fields — measured on 2026-09-29, `repr()` of
    the client this module returns contains the live `sk-or-…` string. So the object must
    never be interpolated into a log line, an exception message, or a stream event. Name
    `client.id` if a turn has to say what is answering; it is the only field on it that is
    safe to print. D8 acceptance (e) depends on this holding.
    """
    if not uid:
        raise ProviderNotServed(
            f"No authenticated session, so the {provider} key this model needs cannot be resolved."
        )
    from provider_keys import get_key

    record = get_key(uid, provider)
    key = record.get_api_key() if record else ""
    if not key:
        raise ProviderNotServed(
            f"{provider} has no API key connected for this user. "
            "Add it in Settings → Model providers."
        )
    return key


def model_client(model_id: str, uid: str = "", *, host: str | None = None,
                 options: dict | None = None):
    """Build the phi model object that can actually serve `model_id`.

    Ollama-specific arguments (`host`, `options`) are resolved inside the Ollama branch
    only. A caller that computes them before asking — as every handler did before this
    module existed — will have already called `get_best_host_for_model` on a gateway id
    and received a host that cannot serve it.
    """
    requested = (model_id or "").strip()
    if not is_honourable_pick(requested):
        raise ValueError(f"{model_id!r} names no model to build a client for.")

    provider = provider_of(requested, uid)
    if provider is None:
        from phi.model.ollama import Ollama

        if host is None:
            from utils.gpu_queue import get_best_host_for_model

            host = get_best_host_for_model(requested)
        if options is None:
            from config import get_ollama_options

            options = get_ollama_options(requested)
        return Ollama(
            id=requested,
            host=host,
            client_kwargs={"timeout": 120.0},
            options=options or {},
        )

    if provider == "openrouter":
        from phi.model.openrouter import OpenRouter

        # base_url and the OpenRouter default headers come from the class itself; only
        # the id and this user's key are supplied, so no credential is baked into source.
        return OpenRouter(id=requested, api_key=_provider_api_key(provider, uid))

    raise ProviderNotServed(
        f"{requested} is served by {provider}, which the conversational path cannot build "
        "a client for yet (plan D8)."
    )
