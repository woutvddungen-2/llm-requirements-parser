def pytest_addoption(parser):
    parser.addoption(
        "--models",
        action="store",
        default=None,
        help="Comma-separated list of models in format vendor:model_name",
    )


def pytest_generate_tests(metafunc):
    if "model" not in metafunc.fixturenames:
        return

    raw_models = metafunc.config.getoption("models")
    if not raw_models:
        raise ValueError(
            "No models specified. Use --models vendor:model_name[,vendor:model_name,...]"
        )

    models = [m.strip() for m in raw_models.split(",") if m.strip()]
    if not models:
        raise ValueError(
            "No valid models specified. Use --models vendor:model_name[,vendor:model_name,...]"
        )

    metafunc.parametrize("model", models, ids=models)