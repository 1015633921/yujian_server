from __future__ import annotations

from datetime import date, time
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator


class CoreWish(str, Enum):
    WEALTH_CAREER = "招财进宝/事业腾飞"
    LOVE_RELATIONSHIP = "正缘桃花/人际和合"
    PROTECTION_CALM = "辟邪防小人/消除焦虑"
    HEALTH_FOCUS = "健康护身/保持专注"


VALID_MBTI = {
    "INTJ", "INTP", "ENTJ", "ENTP",
    "INFJ", "INFP", "ENFJ", "ENFP",
    "ISTJ", "ISFJ", "ESTJ", "ESFJ",
    "ISTP", "ISFP", "ESTP", "ESFP",
}

NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class AssessmentRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, use_enum_values=True, extra="forbid")

    user_id: str | None = Field(default=None, max_length=64, description="小程序用户 ID/OpenID")
    name: NonEmptyString
    birthday: date
    birth_time: time
    birth_time_unknown: bool = False
    birth_place: NonEmptyString
    location_code: str | None = Field(default=None, max_length=80)
    lng: float | None = Field(default=None, ge=-180, le=180, description="出生地经度")
    lat: float | None = Field(default=None, ge=-90, le=90, description="出生地纬度")
    mbti: str | None = None
    core_wish: CoreWish | None = Field(default=None, description="兼容旧版的单个核心愿望")
    core_wishes: list[CoreWish] = Field(default_factory=list, min_length=1, max_length=3)
    chakra_answers: list[str] = Field(default_factory=list, max_length=5, description="七脉轮状态答案 ID")
    mood_palette_id: str | None = Field(default=None, max_length=40, description="色彩直觉色板 ID")
    wrist_size_cm: float = Field(default=15.5, ge=10, le=30)
    bead_size_mm: int = Field(default=8, ge=4, le=20)
    force_recalculate: bool = False

    @field_validator("mbti")
    @classmethod
    def validate_mbti(cls, value: str | None) -> str | None:
        if not value:
            return None
        normalized = value.strip().upper()
        if normalized not in VALID_MBTI:
            raise ValueError("mbti 必须是 16 种合法人格类型之一")
        return normalized

    @model_validator(mode="before")
    @classmethod
    def normalize_wishes(cls, data):
        if isinstance(data, dict):
            wishes = data.get("core_wishes") or []
            legacy_wish = data.get("core_wish")
            if not wishes and legacy_wish:
                data = {**data, "core_wishes": [legacy_wish]}
            elif wishes and not legacy_wish:
                data = {**data, "core_wish": wishes[0]}
        return data

    @model_validator(mode="after")
    def validate_coordinates(self):
        if (self.lng is None) != (self.lat is None):
            raise ValueError("lng 和 lat 需要同时传入")
        return self

    @property
    def primary_core_wish(self) -> str:
        return self.core_wishes[0]


class DIYRecommendationRequest(BaseModel):
    wrist_size_cm: float = Field(ge=10, le=30, description="手腕周长，单位厘米")
    bead_size_mm: int = Field(default=8, ge=4, le=20, description="偏好珠径，单位毫米")
    report_id: str | None = Field(default=None, max_length=100)
    expected_report_version: int | None = Field(default=None, ge=1)
    style_preference: str | None = Field(
        default=None,
        pattern="^(minimal|balanced|layered)$",
        description="方案调整方向",
    )
    accessory_preference: str | None = Field(
        default=None,
        pattern="^(less|balanced|more)$",
        description="配饰用量偏好",
    )
    locked_material_ids: list[str] = Field(
        default_factory=list,
        max_length=3,
        description="重新生成时需要保留的材料 ID",
    )
    rejected_plan_id: str | None = Field(
        default=None,
        max_length=100,
        description="用户明确不喜欢的方案 ID",
    )

    @field_validator("locked_material_ids")
    @classmethod
    def validate_locked_material_ids(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        for value in values:
            material_id = str(value or "").strip()
            if not material_id or len(material_id) > 100:
                raise ValueError("保留材料 ID 不合法")
            if material_id not in normalized:
                normalized.append(material_id)
        return normalized

    @property
    def has_refinement(self) -> bool:
        return bool(
            self.style_preference
            or self.accessory_preference
            or self.locked_material_ids
            or self.rejected_plan_id
        )

    @property
    def refinement(self) -> dict:
        return {
            "style_preference": self.style_preference,
            "accessory_preference": self.accessory_preference,
            "locked_material_ids": self.locked_material_ids,
            "rejected_plan_id": self.rejected_plan_id,
        }


class DailyCheckInRequest(BaseModel):
    user_id: NonEmptyString
    mood: int = Field(ge=1, le=5, description="心情，1-5 分")
    sleep: int = Field(ge=1, le=5, description="睡眠质量，1-5 分")
    stress: int = Field(ge=1, le=5, description="压力，1-5 分，越高压力越大")


class WechatLoginRequest(BaseModel):
    code: str | None = Field(default=None, max_length=128)
    nickname: str | None = Field(default=None, max_length=100)
    avatar_url: str | None = Field(default=None, max_length=500)
    gender: str | None = Field(default=None, max_length=20)


class UserProfileUpdateRequest(BaseModel):
    user_id: NonEmptyString
    nickname: str | None = Field(default=None, max_length=100)
    avatar_url: str | None = Field(default=None, max_length=500)
    gender: str | None = Field(default=None, max_length=20)
    name: str | None = Field(default=None, max_length=100)
    phone_number: str | None = Field(default=None, max_length=32)


class PhoneBindRequest(BaseModel):
    user_id: NonEmptyString
    code: str | None = Field(default=None, max_length=256)
    phone_number: str | None = Field(default=None, max_length=32)


class ReceiverInfo(BaseModel):
    name: NonEmptyString
    phone: NonEmptyString
    address: NonEmptyString


class OrderCreateRequest(BaseModel):
    user_id: NonEmptyString
    design_id: str | None = Field(default=None, max_length=80)
    receiver: ReceiverInfo
    design: dict = Field(default_factory=dict)
    sequence: list[dict] = Field(default_factory=list, min_length=1, max_length=120)
    bom: list[dict] = Field(default_factory=list)
    remark: str | None = Field(default=None, max_length=500)


class DIYDesignSaveRequest(BaseModel):
    user_id: NonEmptyString
    design_id: str | None = Field(default=None, max_length=80)
    design: dict = Field(default_factory=dict)
    sequence: list[dict] = Field(default_factory=list, max_length=120)
    status: str = Field(default="saved", max_length=30)


class CustomDesignRequestCreate(BaseModel):
    """A service request, intentionally separate from merchandise orders."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    user_id: NonEmptyString
    report_id: str = Field(min_length=1, max_length=80)
    report_version: int = Field(ge=1, le=10000)
    assessment_id: str | None = Field(default=None, max_length=80)
    wrist_size_cm: float = Field(ge=10, le=25)
    bead_size_mm: int = Field(ge=4, le=20)
    budget: str = Field(default="", max_length=80)
    style_preference: str = Field(default="", max_length=80)
    color_preference: str = Field(default="", max_length=120)
    accessory_preference: str = Field(default="", max_length=80)
    wear_scene: str = Field(default="", max_length=80)
    note: str = Field(default="", max_length=500)


class CustomDesignResponseRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    user_id: NonEmptyString
    note: str = Field(default="", max_length=500)


class CartItemCreateRequest(BaseModel):
    user_id: NonEmptyString
    cart_item_id: str | None = Field(default=None, max_length=80)
    idempotency_key: str | None = Field(default=None, max_length=128)
    item_type: str = Field(default="plan", max_length=40)
    item_id: str | None = Field(default=None, max_length=100)
    item: dict = Field(default_factory=dict)
    quantity: int = Field(default=1, ge=1, le=99)


class CartItemUpdateRequest(BaseModel):
    user_id: NonEmptyString
    item: dict | None = None
    quantity: int | None = Field(default=None, ge=1, le=99)


class CommunityFavoriteSaveRequest(BaseModel):
    user_id: NonEmptyString
    post_id: NonEmptyString
    item: dict = Field(default_factory=dict)


class UserAddressRequest(BaseModel):
    user_id: NonEmptyString
    address_id: str | None = Field(default=None, max_length=80)
    name: NonEmptyString
    phone: NonEmptyString
    region: list[str] = Field(default_factory=list)
    detail_address: NonEmptyString
    address: str | None = Field(default=None, max_length=800)
    is_default: bool = False


class UserAddressActionRequest(BaseModel):
    user_id: NonEmptyString


class OrderActionRequest(BaseModel):
    user_id: NonEmptyString
    reason: str | None = Field(default=None, max_length=500)


class AfterSaleCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    user_id: NonEmptyString
    type: str = Field(min_length=1, max_length=40)
    reason_code: str = Field(min_length=1, max_length=60)
    reason: str = Field(min_length=5, max_length=500)
    evidence_urls: list[str] = Field(default_factory=list, max_length=3)
    idempotency_key: str = Field(min_length=8, max_length=128)

    @field_validator("evidence_urls")
    @classmethod
    def validate_evidence_urls(cls, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        for value in values:
            url = str(value or "").strip()
            if not url.startswith("https://") or len(url) > 2000:
                raise ValueError("售后凭证必须是有效的 HTTPS 地址")
            if url not in cleaned:
                cleaned.append(url)
        return cleaned


class AfterSaleReturnShipmentRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    user_id: NonEmptyString
    carrier: str = Field(min_length=1, max_length=50)
    tracking_no: str = Field(min_length=6, max_length=80)


class AfterSaleCancelRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    user_id: NonEmptyString
    reason: str = Field(default="用户取消售后申请", max_length=500)


class OrderReceiverUpdateRequest(BaseModel):
    user_id: NonEmptyString
    receiver: dict = Field(default_factory=dict)


class OrderRefundRequest(BaseModel):
    user_id: NonEmptyString
    reason: str | None = Field(default=None, max_length=500)


class OrderShipRequest(BaseModel):
    user_id: NonEmptyString
    carrier: str | None = Field(default="顺丰速运", max_length=50)
    carrier_code: str | None = Field(default="shunfeng", max_length=40)
    tracking_no: str | None = Field(default=None, max_length=80)
    phone_tail: str | None = Field(default=None, max_length=8)


class EnergyProfile(BaseModel):
    金: float
    木: float
    水: float
    火: float
    土: float


class EnergyBreakdown(BaseModel):
    bazi: EnergyProfile
    mbti: EnergyProfile
    name: EnergyProfile
    wish: EnergyProfile


class SolarTimeInfo(BaseModel):
    beijing_time: str
    true_solar_time: str | None = None
    calibrated_time: str | None = None
    longitude: float | None = None
    latitude: float | None = None
    longitude_correction_minutes: float | None = None
    equation_of_time_minutes: float | None = None
    total_correction_minutes: float | None = None
    location_source: str
    resolved_location_code: str | None = None
    timezone: str = "Asia/Shanghai"
    calibration_status: str = "legacy_unknown"
    calibration_source: str = "legacy_unknown"
    calibration_version: str = "legacy_unknown"
    location_data_version: str = "legacy_unknown"
    calibration_reason_code: str = "metadata_not_available"


class CrystalItem(BaseModel):
    code: str
    name: str
    top: str = "bead"
    kind: str = "bead"
    role: str
    role_key: str = ""
    element: str
    secondary_elements: list[str] = Field(default_factory=list)
    color: str
    effects: list[str]
    reason: str
    quantity: int
    bead_size_mm: int
    image_url: str = ""
    material_id: str = ""
    material_code: str = ""
    actual_material_size_mm: float | None = None
    string_axis_width_mm: float | None = None
    unit_price: float | None = None
    stock: int | None = None


class BraceletLayoutItem(BaseModel):
    position: int
    crystal_code: str
    crystal_name: str
    role: str
    role_key: str = ""
    top: str = "bead"
    kind: str = "bead"
    color: str
    material_id: str = ""
    material_code: str = ""
    bead_size_mm: int | None = None
    actual_material_size_mm: float | None = None
    string_axis_width_mm: float | None = None


class BraceletPlan(BaseModel):
    plan_id: str = ""
    style: str = ""
    title: str = ""
    subtitle: str = ""
    wrist_size_cm: float
    bead_size_mm: int
    estimated_bead_count: int
    pattern: str
    items: list[CrystalItem]
    layout: list[BraceletLayoutItem]
    estimated_price: float = 0
    material_variety: int = 0
    has_accessories: bool = False
    accessory_names: list[str] = Field(default_factory=list)
    match_reasons: list[str] = Field(default_factory=list)
    validation: dict = Field(default_factory=dict)
    is_recommended: bool = False


class AssessmentResult(BaseModel):
    assessment_id: str
    created_at: str
    input_summary: dict
    solar_time: SolarTimeInfo
    final_energy_profile: EnergyProfile
    energy_breakdown: EnergyBreakdown
    chart: dict
    strongest_element: str
    weakest_element: str
    interpretation: dict
    primary_crystal: CrystalItem
    supporting_crystals: list[CrystalItem]
    bracelet_plan: BraceletPlan
    bracelet_plans: list[BraceletPlan] = Field(default_factory=list)
    recommendation_copy: str
    care_tips: list[str]
    disclaimer: str


class ApiResponse(BaseModel):
    code: int = 0
    message: str = "ok"
    data: dict | list | None
