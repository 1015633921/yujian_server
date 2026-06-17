from django.core.management.base import BaseCommand

from crystal.models import Inspiration, Material, Recommendation


class Command(BaseCommand):
    help = "Seed demo data for the crystal DIY mini-program."

    def handle(self, *args, **options):
        materials = [
            ("bead", "Amethyst 8mm", "BEAD-AMETHYST-8", "purple", "water", ["study", "sleep", "amethyst"], ["clarity", "calm"], "Focus and gentle sleep support.", "12.80", 120, 8),
            ("bead", "Citrine 8mm", "BEAD-CITRINE-8", "gold", "earth", ["career", "wealth", "citrine"], ["focus", "growth"], "Bright energy for work and abundance.", "16.80", 90, 8),
            ("bead", "Rose Quartz 8mm", "BEAD-ROSE-8", "pink", "water", ["love", "rose_quartz"], ["soft", "healing"], "Soft emotional balance.", "10.80", 150, 8),
            ("bead", "Obsidian 10mm", "BEAD-OBSIDIAN-10", "black", "water", ["protection", "obsidian"], ["grounding"], "Grounding and protection.", "13.80", 80, 10),
            ("bead", "Fluorite 8mm", "BEAD-FLUORITE-8", "green", "wood", ["study", "fluorite"], ["clarity", "balance"], "Layered color for clear thinking.", "15.80", 70, 8),
            ("accessory", "Gold Spacer", "ACC-GOLD-SPACER", "gold", "metal", ["career", "wealth"], ["focus"], "A small spacer for rhythm and brightness.", "2.50", 500, None),
            ("accessory", "Silver Charm", "ACC-SILVER-CHARM", "silver", "metal", ["balance"], ["clean"], "Minimal silver charm.", "5.80", 200, None),
            ("incense_bead", "Sandalwood Incense Bead", "INC-SANDALWOOD", "brown", "wood", ["sleep", "health"], ["calm"], "Warm woody scent for steady energy.", "8.80", 100, 8),
            ("flower_cap", "Lotus Flower Cap", "CAP-LOTUS-GOLD", "gold", "metal", ["love", "wealth"], ["harmony"], "Lotus-shaped cap for the main bead.", "3.20", 300, None),
        ]
        for index, row in enumerate(materials):
            material_type, name, code, color, element, tags, effects, description, price, stock, diameter = row
            Material.objects.update_or_create(
                code=code,
                defaults={
                    "material_type": material_type,
                    "name": name,
                    "color": color,
                    "element": element,
                    "energy_tags": tags,
                    "effects": effects,
                    "description": description,
                    "price": price,
                    "stock": stock,
                    "diameter_mm": diameter,
                    "sort_order": index,
                    "is_active": True,
                },
            )

        recommendations = [
            ("Career Focus Bracelet", "Citrine with obsidian grounding", "career", ["career", "focus"], 980),
            ("Gentle Sleep Bracelet", "Amethyst and sandalwood for night calm", "sleep", ["sleep", "calm"], 850),
            ("Soft Love Bracelet", "Rose quartz with lotus details", "love", ["love", "soft"], 760),
        ]
        for title, subtitle, scene, tags, popularity in recommendations:
            Recommendation.objects.update_or_create(
                title=title,
                defaults={
                    "subtitle": subtitle,
                    "scene": scene,
                    "tags": tags,
                    "materials": [],
                    "plan": {},
                    "popularity": popularity,
                    "is_active": True,
                },
            )

        inspirations = [
            ("Morning Focus Stack", "Use citrine as the main bead and keep metal spacers sparse.", ["career", "minimal"]),
            ("Moonlight Sleep Mix", "Amethyst plus sandalwood creates a calmer night-wear bracelet.", ["sleep", "purple"]),
        ]
        for title, content, tags in inspirations:
            Inspiration.objects.update_or_create(
                title=title,
                defaults={"content": content, "tags": tags, "is_featured": True, "is_public": True},
            )

        self.stdout.write(self.style.SUCCESS("Seeded crystal demo data."))
