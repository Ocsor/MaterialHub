"""Central filesystem locations, kept separate to avoid circular imports."""
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
ROOT_DIR = APP_DIR.parent
TEMPLATES_DIR = APP_DIR / "templates"
STATIC_DIR = APP_DIR / "static"
RESOURCES_DIR = ROOT_DIR / "Resources"
PREPIT_TEMPLATES_DIR = RESOURCES_DIR / "Prepit_templates"
PREPIT_TEMPLATE_RULES_PATH = RESOURCES_DIR / "prepit_template_rules.json"
