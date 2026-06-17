from django.contrib import admin

from .models import (
    Address,
    CartItem,
    CrystalAssessment,
    DIYPlan,
    DailyEnergy,
    Favorite,
    Inspiration,
    Material,
    MiniUser,
    Order,
    Recommendation,
)


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ("name", "material_type", "price", "stock", "is_active", "sort_order")
    list_filter = ("material_type", "is_active", "element", "color")
    search_fields = ("name", "code")


@admin.register(MiniUser)
class MiniUserAdmin(admin.ModelAdmin):
    list_display = ("id", "nickname", "openid", "phone", "intention", "created_at")
    search_fields = ("nickname", "openid", "phone")


@admin.register(DailyEnergy)
class DailyEnergyAdmin(admin.ModelAdmin):
    list_display = ("user", "date", "score", "title", "lucky_crystal")
    list_filter = ("date",)


@admin.register(CrystalAssessment)
class CrystalAssessmentAdmin(admin.ModelAdmin):
    list_display = ("user", "intention", "created_at")
    list_filter = ("intention",)


@admin.register(Recommendation)
class RecommendationAdmin(admin.ModelAdmin):
    list_display = ("title", "scene", "popularity", "is_active")
    list_filter = ("scene", "is_active")


@admin.register(Inspiration)
class InspirationAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "likes_count", "collects_count", "is_featured", "is_public")
    list_filter = ("is_featured", "is_public")


@admin.register(DIYPlan)
class DIYPlanAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "intention", "price_snapshot", "status", "updated_at")
    list_filter = ("status", "intention")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("order_no", "user", "status", "total_amount", "created_at")
    list_filter = ("status",)
    search_fields = ("order_no",)


admin.site.register(Favorite)
admin.site.register(CartItem)
admin.site.register(Address)
