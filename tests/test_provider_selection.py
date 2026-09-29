"""D7: per-provider model selection.

The rule under test is that a gateway's models are opt-in and a curated provider's
are not, and that "no key" and "key with nothing chosen" are different answers. Those
two distinctions are the whole feature: collapse them and connecting OpenRouter either
rewrites the user's picker with 460 rows or silently disables a provider they just paid
for.

Nothing here touches the database. `set_selection` is tested only up to the point where
it would open a connection, because the guard before that point is the behaviour that
matters to a caller.
"""
import os
import sys

import pytest

_AGENTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agents")
if _AGENTS not in sys.path:
    sys.path.insert(0, _AGENTS)

import provider_keys as pk
import providers.registry as reg
from provider_keys import PROVIDERS, ProviderKey, normalize_selection


def _record(selection):
    return ProviderKey(
        user_id="Justin", provider="openrouter", label="", created_at=None,
        updated_at=None, _encrypted=b"", selected_models=selection,
    )


class TestNormalizeSelection:
    def test_order_and_duplicates_do_not_change_the_stored_state(self):
        assert normalize_selection(["b", "a", "b"]) == normalize_selection(["a", "b"])
        assert normalize_selection(["a", "b"]) == ["a", "b"]

    def test_blank_and_untrimmed_entries_are_dropped(self):
        assert normalize_selection(["  a  ", "", None, "   "]) == ["a"]

    def test_non_strings_are_dropped_rather_than_stringified(self):
        # str(None) is "None" and str(123) is "123", both truthy: coercing would store
        # them as model ids and offer them back as choices the user never made.
        assert normalize_selection(["a", None, 123, {"id": "a"}, ["a"]]) == ["a"]

    def test_nothing_given_is_an_empty_selection_not_an_error(self):
        assert normalize_selection(None) == []
        assert normalize_selection([]) == []


class TestGetSelection:
    def test_a_missing_column_reads_as_empty_not_as_none(self):
        # An older row, or a fixture built without the field, must not be mistaken for
        # "cannot serve this provider" — that answer comes from the absence of a key.
        assert _record(None).get_selection() == []
        assert _record([]).get_selection() == []

    def test_the_selection_is_returned_as_strings(self):
        assert _record(["a/b", "c/d"]).get_selection() == ["a/b", "c/d"]


class TestProviderSelectionKeepsTheTwoStatesApart:
    def test_no_key_is_none(self, monkeypatch):
        monkeypatch.setattr(pk, "get_key", lambda uid, provider: None)
        assert reg.provider_selection("Justin", "openrouter") is None

    def test_key_with_nothing_chosen_is_an_empty_list(self, monkeypatch):
        monkeypatch.setattr(pk, "get_key", lambda uid, provider: _record([]))
        assert reg.provider_selection("Justin", "openrouter") == []

    def test_a_key_lookup_failure_is_not_read_as_connected(self, monkeypatch):
        # Fail closed: an outage must not hand every provider id the entitlement.
        def boom(uid, provider):
            raise RuntimeError("connection refused")
        monkeypatch.setattr(pk, "get_key", boom)
        assert reg.provider_selection("Justin", "openrouter") is None

    def test_no_identity_no_answer(self):
        assert reg.provider_selection("", "openrouter") is None
        assert reg.provider_selection("Justin", "") is None


class TestOptInIsScopedToLiveCatalogueProviders:
    def test_exactly_one_provider_is_live_today(self):
        # If a second gateway is ever declared live it inherits the opt-in default;
        # if a curated one is, that is a behaviour change for existing users and this
        # test is where it gets noticed.
        live = sorted(p for p, info in PROVIDERS.items() if info.get("live_models"))
        assert live == ["openrouter"]

    def test_curated_providers_declare_models_and_ignore_selection(self):
        for provider in ("anthropic", "google", "nvidia"):
            info = PROVIDERS[provider]
            assert info.get("models"), f"{provider} must keep its declared list"
            assert not info.get("live_models"), f"{provider} must not gain the opt-in default"

    def test_the_gateway_still_declares_no_static_list(self):
        assert PROVIDERS["openrouter"]["models"] == []


class TestSetSelectionGuards:
    def test_an_unknown_provider_is_refused_before_any_connection(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            pk.set_selection("Justin", "not-a-provider", ["a"])

    def test_the_empty_selection_is_accepted_for_a_known_provider(self, monkeypatch):
        # Clearing a selection is legal, so the provider guard must let it through.
        # The sentinel stands in for the connection: reaching it *is* the assertion,
        # and no test here is allowed to open a real database.
        class ReachedConnection(Exception):
            pass

        def boom():
            raise ReachedConnection()

        monkeypatch.setattr(pk, "_get_conn", boom)
        with pytest.raises(ReachedConnection):
            pk.set_selection("Justin", "openrouter", [])
