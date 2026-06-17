from django.db import models
from django.utils import timezone


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class MiniUser(TimestampedModel):
    openid = models.CharField(max_length=128, unique=True, blank=True, null=True)
    nickname = models.CharField(max_length=80, blank=True)
    avatar_url = models.URLField(blank=True)
    phone = models.CharField(max_length=32, blank=True)
    birth_date = models.DateField(blank=True, null=True)
    birth_time = models.TimeField(blank=True, null=True)
    gender = models.CharField(max_length=20, blank=True)
    city = models.CharField(max_length=80, blank=True)
    zodiac = models.CharField(max_length=30, blank=True)
    element = models.CharField(max_length=30, blank=True)
    intention = models.CharField(max_length=80, blank=True)

    def __str__(self) -> str:
        return self.nickname or self.openid or f"user-{self.pk}"


class Material(TimestampedModel):
    MATERIAL_BEAD = "bead"
    MATERIAL_ACCESSORY = "accessory"
    MATERIAL_INCENSE = "incense_bead"
    MATERIAL_CAP = "flower_cap"
    MATERIAL_CHOICES = [
        (MATERIAL_BEAD, "Bead"),
        (MATERIAL_ACCESSORY, "Accessory"),
        (MATERIAL_INCENSE, "Incense Bead"),
        (MATERIAL_CAP, "Flower Cap"),
    ]

    material_type = models.CharField(max_length=30, choices=MATERIAL_CHOICES)
    name = models.CharField(max_length=120)
    code = models.CharField(max_length=80, unique=True)
    image_url = models.URLField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    stock = models.PositiveIntegerField(default=0)
    diameter_mm = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    color = models.CharField(max_length=50, blank=True)
    element = models.CharField(max_length=30, blank=True)
    energy_tags = models.JSONField(default=list, blank=True)
    effects = models.JSONField(default=list, blank=True)
    description = models.TextField(blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["material_type", "sort_order", "id"]

    def __str__(self) -> str:
        return self.name


class CrystalAssessment(TimestampedModel):
    user = models.ForeignKey(MiniUser, on_delete=models.CASCADE, related_name="assessments")
    profile = models.JSONField(default=dict, blank=True)
    intention = models.CharField(max_length=80)
    energy_profile = models.JSONField(default=dict, blank=True)
    recommended_materials = models.JSONField(default=list, blank=True)
    bracelet_plan = models.JSONField(default=dict, blank=True)
    summary = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]


class DailyEnergy(TimestampedModel):
    user = models.ForeignKey(MiniUser, on_delete=models.CASCADE, related_name="daily_energies")
    date = models.DateField(default=timezone.localdate)
    score = models.PositiveSmallIntegerField(default=0)
    title = models.CharField(max_length=120)
    summary = models.TextField(blank=True)
    lucky_color = models.CharField(max_length=40, blank=True)
    lucky_crystal = models.CharField(max_length=80, blank=True)
    affirmation = models.CharField(max_length=180, blank=True)
    actions = models.JSONField(default=list, blank=True)
    recommended_materials = models.JSONField(default=list, blank=True)
    source = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "date"], name="unique_daily_energy_user_date")
        ]
        ordering = ["-date", "-created_at"]


class Recommendation(TimestampedModel):
    title = models.CharField(max_length=120)
    subtitle = models.CharField(max_length=160, blank=True)
    scene = models.CharField(max_length=80, blank=True)
    image_url = models.URLField(blank=True)
    tags = models.JSONField(default=list, blank=True)
    materials = models.JSONField(default=list, blank=True)
    plan = models.JSONField(default=dict, blank=True)
    popularity = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-popularity", "-created_at"]


class Inspiration(TimestampedModel):
    user = models.ForeignKey(MiniUser, on_delete=models.SET_NULL, null=True, blank=True)
    title = models.CharField(max_length=120)
    content = models.TextField(blank=True)
    image_urls = models.JSONField(default=list, blank=True)
    tags = models.JSONField(default=list, blank=True)
    materials = models.JSONField(default=list, blank=True)
    likes_count = models.PositiveIntegerField(default=0)
    collects_count = models.PositiveIntegerField(default=0)
    is_featured = models.BooleanField(default=False)
    is_public = models.BooleanField(default=True)

    class Meta:
        ordering = ["-is_featured", "-created_at"]


class DIYPlan(TimestampedModel):
    STATUS_DRAFT = "draft"
    STATUS_SAVED = "saved"
    STATUS_ORDERED = "ordered"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_SAVED, "Saved"),
        (STATUS_ORDERED, "Ordered"),
    ]

    user = models.ForeignKey(MiniUser, on_delete=models.CASCADE, related_name="diy_plans")
    name = models.CharField(max_length=120)
    intention = models.CharField(max_length=80, blank=True)
    wrist_size_cm = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    beads = models.JSONField(default=list, blank=True)
    accessories = models.JSONField(default=list, blank=True)
    layout = models.JSONField(default=dict, blank=True)
    price_snapshot = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cover_image_url = models.URLField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_SAVED)
    remark = models.TextField(blank=True)

    class Meta:
        ordering = ["-updated_at"]


class Order(TimestampedModel):
    STATUS_PENDING = "pending"
    STATUS_PAID = "paid"
    STATUS_MAKING = "making"
    STATUS_SHIPPED = "shipped"
    STATUS_DONE = "done"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_PAID, "Paid"),
        (STATUS_MAKING, "Making"),
        (STATUS_SHIPPED, "Shipped"),
        (STATUS_DONE, "Done"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    user = models.ForeignKey(MiniUser, on_delete=models.CASCADE, related_name="orders")
    order_no = models.CharField(max_length=64, unique=True)
    diy_plan = models.ForeignKey(DIYPlan, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    items = models.JSONField(default=list, blank=True)
    address = models.JSONField(default=dict, blank=True)
    logistics = models.JSONField(default=dict, blank=True)
    paid_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]


class Favorite(TimestampedModel):
    user = models.ForeignKey(MiniUser, on_delete=models.CASCADE, related_name="favorites")
    target_type = models.CharField(max_length=40)
    target_id = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "target_type", "target_id"], name="unique_favorite")
        ]
        ordering = ["-created_at"]


class CartItem(TimestampedModel):
    user = models.ForeignKey(MiniUser, on_delete=models.CASCADE, related_name="cart_items")
    material = models.ForeignKey(Material, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    selected = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "material"], name="unique_cart_material")
        ]


class Address(TimestampedModel):
    user = models.ForeignKey(MiniUser, on_delete=models.CASCADE, related_name="addresses")
    receiver = models.CharField(max_length=80)
    phone = models.CharField(max_length=32)
    province = models.CharField(max_length=80)
    city = models.CharField(max_length=80)
    district = models.CharField(max_length=80, blank=True)
    detail = models.CharField(max_length=240)
    is_default = models.BooleanField(default=False)

    class Meta:
        ordering = ["-is_default", "-updated_at"]
