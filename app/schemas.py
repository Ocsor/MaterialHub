"""Pydantic response schemas for MaterialHub's public API."""

from pydantic import BaseModel, ConfigDict, computed_field


class MaterialResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    stocktopus_id: str
    name: str
    sku: str | None
    material_group: str | None
    material_type: str | None
    size_type: str
    width_mm: float | None
    height_mm: float | None
    length_mm: float | None
    thickness_mm: float | None
    size_unit: str | None
    size_string: str | None
    supplier_name: str | None
    friendly_name: str | None
    matex: str | None
    prepit: str | None
    imp: str | None
    notes: str | None
    keywords: str | None
    primary_cutter: str | None
    primary_tool: str | None
    tool_tips: str | None

    @computed_field
    @property
    def display_name(self) -> str:
        return self.friendly_name.strip() if self.friendly_name and self.friendly_name.strip() else self.name
