import json

from django.test import Client, TestCase

from .models import DailyEnergy, Material, MiniUser


class CrystalApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = MiniUser.objects.create(nickname="tester", intention="career")
        Material.objects.create(
            material_type=Material.MATERIAL_BEAD,
            name="Citrine",
            code="TEST-CITRINE",
            price="12.50",
            stock=10,
            color="gold",
            element="earth",
            energy_tags=["career", "citrine"],
            effects=["focus"],
        )

    def test_daily_energy_is_reused_for_same_day(self):
        response_one = self.client.get(f"/api/daily-energy/?user_id={self.user.id}")
        response_two = self.client.get(f"/api/daily-energy/?user_id={self.user.id}")

        self.assertEqual(response_one.status_code, 200)
        self.assertEqual(response_two.status_code, 200)
        self.assertEqual(DailyEnergy.objects.count(), 1)
        self.assertEqual(
            response_one.json()["data"]["id"],
            response_two.json()["data"]["id"],
        )

    def test_save_diy_plan_estimates_price(self):
        material = Material.objects.get(code="TEST-CITRINE")
        response = self.client.post(
            "/api/diy-plans/save/",
            data=json.dumps(
                {
                    "user_id": self.user.id,
                    "name": "Career bracelet",
                    "beads": [{"material_id": material.id, "quantity": 2}],
                    "accessories": [],
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["data"]["price_snapshot"], 25.0)
