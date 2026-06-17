from django.urls import path

from . import views

urlpatterns = [
    path("health/", views.health),
    path("config/", views.app_config),
    path("users/upsert/", views.upsert_user),
    path("crystal/assessment/", views.crystal_assessment),
    path("crystal/assessment/latest/", views.latest_assessment),
    path("daily-energy/", views.daily_energy),
    path("recommendations/hot/", views.recommendations),
    path("inspirations/", views.inspirations),
    path("inspirations/create/", views.create_inspiration),
    path("inspirations/<int:inspiration_id>/like/", views.like_inspiration),
    path("materials/", views.material_list),
    path("materials/groups/", views.material_groups),
    path("materials/<int:material_id>/", views.material_detail),
    path("diy-plans/", views.diy_plans),
    path("diy-plans/save/", views.save_diy_plan),
    path("diy-plans/<int:plan_id>/", views.diy_plan_detail),
    path("orders/", views.my_orders),
    path("orders/create/", views.create_order),
    path("orders/<int:order_id>/", views.order_detail),
    path("favorites/", views.favorites),
    path("favorites/toggle/", views.favorite_toggle),
    path("cart/", views.cart_list),
    path("cart/add/", views.cart_add),
    path("addresses/", views.addresses),
    path("addresses/save/", views.save_address),
]
