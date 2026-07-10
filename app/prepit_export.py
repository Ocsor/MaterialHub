"""Build Prepit XML exports from material rows and editable XML templates."""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from .models import Material


TEMPLATE_FILENAMES = {
    ("black", "sheet"): "black_registration.xml",
    ("black", "roll"): "black_registration_roll.xml",
    ("spot_white", "sheet"): "spot_white_registration.xml",
    ("spot_white", "roll"): "spot_white_registration_roll.xml",
}


@dataclass(frozen=True)
class PrepitXml:
    filename: str
    content: bytes


class PrepitExportError(ValueError):
    """Raised when a checked material cannot be converted to Prepit XML."""


def build_prepit_xml(material: Material, templates_dir: Path, rules_path: Path) -> PrepitXml:
    """Return one generated Prepit XML file for a checked material."""
    template_path = templates_dir / _template_filename(material, rules_path)
    tree = ET.parse(template_path)
    root = tree.getroot()

    media_name = _media_name(material)
    root.tag = _xml_root_tag(media_name)
    _set_required_text(root.find("MediaName"), "MediaName", material, media_name)
    _update_sheet_info(root, material)

    ET.indent(tree, space="\t")
    return PrepitXml(filename=f"{_safe_filename(media_name)}.Media.xml", content=_xml_bytes(tree))


def prepit_media_name(material: Material) -> str:
    """Return the shared media name used by XML files and text lists."""
    return _media_name(material)


def _template_filename(material: Material, rules_path: Path) -> str:
    registration = _registration_colour(material.matex, rules_path)
    material_kind = "roll" if _is_roll(material) else "sheet"
    return TEMPLATE_FILENAMES[(registration, material_kind)]


def _registration_colour(matex: str | None, rules_path: Path) -> str:
    try:
        rules = json.loads(rules_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PrepitExportError(f"Prepit template rules file is missing: {rules_path}") from exc
    except json.JSONDecodeError as exc:
        raise PrepitExportError(f"Prepit template rules file is not valid JSON: {rules_path}") from exc

    normalised_matex = _normalise_rule_value(matex)
    spot_white = {_normalise_rule_value(value) for value in rules.get("spot_white_matex", [])}
    black = {_normalise_rule_value(value) for value in rules.get("black_matex", [])}

    if normalised_matex in spot_white:
        return "spot_white"
    if normalised_matex in black:
        return "black"
    return "black"


def _media_name(material: Material) -> str:
    sku = _required_text(material.sku, "SKU", material)
    friendly_name = _required_text(material.friendly_name or material.name, "Friendly Name", material)
    width = _required_number(material.width_mm, "Width", material)

    if _is_roll(material):
        return f"{sku}_{friendly_name}_{_format_mm(width)}"

    height = _required_number(material.height_mm, "Height", material)
    thickness = _required_number(material.thickness_mm, "Thick", material)
    return f"{sku}_{friendly_name}_{_format_mm(width)}x{_format_mm(height)}_{_format_mm(thickness)}mm"


def _update_sheet_info(root: ET.Element, material: Material) -> None:
    sheet_info = root.find("SheetInfos/Sheet0")
    if sheet_info is None:
        raise PrepitExportError(f"Template is missing SheetInfos/Sheet0 for material {material.id}")

    width = _required_number(material.width_mm, "Width", material)
    height = _required_number(material.height_mm or material.length_mm, "Height", material)
    sheet_name = f"{_format_mm(width)} x {_format_mm(height)} mm"

    _set_required_text(sheet_info.find("Name"), "SheetInfos/Sheet0/Name", material, sheet_name)
    _set_required_text(sheet_info.find("Width"), "SheetInfos/Sheet0/Width", material, _format_microns(width))
    _set_required_text(sheet_info.find("Length"), "SheetInfos/Sheet0/Length", material, _format_microns(height))


def _set_required_text(element: ET.Element | None, field: str, material: Material, value: str) -> None:
    if element is None:
        raise PrepitExportError(f"Template is missing {field} for material {material.id}")
    element.text = value


def _is_roll(material: Material) -> bool:
    return (material.material_type or "").casefold() == "roll" or material.size_type.endswith(r"\Roll")


def _required_text(value: str | None, field: str, material: Material) -> str:
    if value is None or not value.strip():
        raise PrepitExportError(f"Material {material.id} is missing {field}")
    return value.strip()


def _required_number(value: float | None, field: str, material: Material) -> float:
    if value is None:
        raise PrepitExportError(f"Material {material.id} is missing {field}")
    return value


def _format_mm(value: float) -> str:
    return str(int(value)) if value == int(value) else f"{value:g}"


def _format_microns(value: float) -> str:
    return str(round(value * 1000))


def _normalise_rule_value(value: object) -> str:
    return str(value or "").strip().casefold()


def _safe_filename(value: str) -> str:
    filename = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip().strip(".")
    return filename or "prepit_material"


def _xml_root_tag(media_name: str) -> str:
    tag = re.sub(r"[^A-Za-z0-9]", "", media_name).upper()
    if not tag:
        return "PREPITMEDIA"
    if tag[0].isdigit():
        return f"MEDIA{tag}"
    return tag


def _xml_bytes(tree: ET.ElementTree) -> bytes:
    body = ET.tostring(tree.getroot(), encoding="unicode", short_empty_elements=False)
    return f'<?xml version="1.0"?>\n{body}'.encode("utf-8")
