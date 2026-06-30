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
    model_config = ConfigDict(str_strip_whitespace=True, use_enum_values=True)

    user_id: str | None = Field(default=None, max_length=64, description="小程序用户 ID/OpenID")
    name: NonEmptyString
    birthday: date
    birth_time: time
    birth_place: NonEmptyString
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
    sequence: list[dict] = Field(default_factory=list, min_length=1)
    bom: list[dict] = Field(default_factory=list)
    remark: str | None = Field(default=None, max_length=500)


class DIYDesignSaveRequest(BaseModel):
    user_id: NonEmptyString
    design_id: str | None = Field(default=None, max_length=80)
    design: dict = Field(default_factory=dict)
    sequence: list[dict] = Field(default_factory=list)
    status: str = Field(default="saved", max_length=30)


class CartItemCreateRequest(BaseModel):
    user_id: NonEmptyString
    cart_item_id: str | None = Field(default=None, max_length=80)
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
    true_solar_time: str
    longitude: float
    latitude: float | None
    longitude_correction_minutes: float
    equation_of_time_minutes: float
    total_correction_minutes: float
    location_source: str


class CrystalItem(BaseModel):
    code: str
    name: str
    role: str
    element: str
    secondary_elements: list[str] = Field(default_factory=list)
    color: str
    effects: list[str]
    reason: str
    quantity: int
    bead_size_mm: int
    image_url: str = ""


class BraceletLayoutItem(BaseModel):
    position: int
    crystal_code: str
    crystal_name: str
    role: str
    color: str


class BraceletPlan(BaseModel):
    wrist_size_cm: float
    bead_size_mm: int
    estimated_bead_count: int
    pattern: str
    items: list[CrystalItem]
    layout: list[BraceletLayoutItem]


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
    recommendation_copy: str
    care_tips: list[str]
    disclaimer: str


class ApiResponse(BaseModel):
    code: int = 0
    message: str = "ok"
    data: dict | list | None
