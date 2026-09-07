from agents.model_registry import MODELS, get_catalog_models, get_user_selectable_models


def test_huggingface_models_are_cataloged_but_not_selectable_until_served():
    expected = {
        "IFM/K2-Horizon-32B": ("huggingface", 524288),
        "IFM/K2-Horizon-7B": ("huggingface", 524288),
        "inclusionAI/Ling-3.0-tiny": ("huggingface", 262144),
    }

    catalog = {model.name: model for model in get_catalog_models()}
    selectable = {model.name for model in get_user_selectable_models()}

    for name, (provider, context_window) in expected.items():
        spec = catalog[name]
        assert spec.provider == provider
        assert spec.context_window == context_window
        assert spec.source_url.startswith("https://huggingface.co/")
        assert spec.available is False
        assert name not in selectable


def test_model_spec_serialization_includes_catalog_metadata():
    serialized = MODELS["IFM/K2-Horizon-7B"].to_dict()

    assert serialized["provider"] == "huggingface"
    assert serialized["available"] is False
    assert serialized["context_window"] == 524288
