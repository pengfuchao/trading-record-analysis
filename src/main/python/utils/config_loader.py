import yaml
from functools import lru_cache


def load_yaml(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@lru_cache(maxsize=None)
def get_app_config(config_path: str = "src/main/resources/config/app_config.yaml") -> dict:
    return load_yaml(config_path)
