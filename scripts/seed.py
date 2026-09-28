"""Seed FeastFit with a demo chef and a menu of recipes (mostly Italian).

Run:  python -m scripts.seed
Safe to run repeatedly - existing recipes are skipped.

Photos are generated with Pillow (a stylised plate + dish name) so the demo works offline.
Replace them any time from the recipe page ("Change photo") with real food photography.
"""
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.models import Ingredient, Recipe, Step, User
from app.security import hash_password
from app.services.images import store_image
from app.services.recipes import unique_slug

DEMO_USER = {"username": "chef_raj", "email": "chef@feastfit.app", "password": "Feast2026"}

PALETTES = {
    "primo": ((179, 38, 30), (232, 112, 42)),
    "pizza": ((150, 30, 25), (214, 92, 38)),
    "antipasto": ((200, 60, 40), (240, 150, 60)),
    "secondo": ((120, 32, 28), (198, 84, 40)),
    "dolce": ((166, 60, 70), (236, 140, 96)),
    "contorno": ((96, 110, 44), (200, 150, 60)),
    "breakfast": ((210, 120, 40), (245, 190, 90)),
}


def _font(size: int):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # very old Pillow
        return ImageFont.load_default()


def placeholder_image(title: str, category: str, size=(1200, 800)) -> Image.Image:
    top, bottom = PALETTES.get(category, PALETTES["primo"])
    w, h = size
    img = Image.new("RGB", size, top)
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / (h - 1)
        d.line([(0, y), (w, y)], fill=tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    cx, cy, r = w // 2, h // 2, 300
    d.ellipse([cx - r - 22, cy - r - 22, cx + r + 22, cy + r + 22], fill=(255, 255, 255))
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 249, 241))
    d.ellipse([cx - r + 40, cy - r + 40, cx + r - 40, cy + r - 40], outline=(232, 112, 42), width=4)
    font = _font(60)
    words, lines, line = title.split(), [], ""
    for word in words:
        trial = f"{line} {word}".strip()
        if d.textlength(trial, font=font) > 2 * r - 140 and line:
            lines.append(line)
            line = word
        else:
            line = trial
    lines.append(line)
    line_h = 74
    y0 = cy - (len(lines) * line_h) // 2
    for i, text in enumerate(lines):
        tw = d.textlength(text, font=font)
        d.text((cx - tw / 2, y0 + i * line_h), text, font=font, fill=(142, 27, 21))
    small = _font(28)
    tag = "FeastFit"
    d.text((cx - d.textlength(tag, font=small) / 2, cy + r - 90), tag, font=small, fill=(232, 112, 42))
    return img


def R(title, desc, cuisine, category, difficulty, tags, prep, cook, servings, kcal, p, c, f, ings, steps):
    return dict(
        title=title, description=desc, cuisine=cuisine, category=category, difficulty=difficulty,
        tags=tags, prep=prep, cook=cook, servings=servings, kcal=kcal, p=p, c=c, f=f,
        ings=ings, steps=steps,
    )


RECIPES = [
    R("Spaghetti alla Carbonara", "The Roman classic: silky egg and pecorino sauce, crisp guanciale, black pepper. No cream, ever.",
      "italian", "primo", "medium", ["high-protein"], 10, 15, 2, 640, 29, 66, 27,
      [("Spaghetti", "200 g"), ("Guanciale", "100 g"), ("Egg yolks", "3"), ("Whole egg", "1"),
       ("Pecorino Romano", "50 g"), ("Black pepper", "to taste")],
      ["Crisp the diced guanciale slowly in a cold pan until golden; switch off the heat.",
       "Whisk yolks, egg, pecorino and plenty of pepper into a paste.",
       "Boil spaghetti in salted water until al dente; keep a mug of pasta water.",
       "Toss pasta with the guanciale off the heat, add the egg paste and a splash of pasta water until glossy."]),
    R("Pizza Margherita", "Blistered crust, San Marzano tomato, fior di latte and basil - Naples on a plate.",
      "italian", "pizza", "medium", ["vegetarian"], 120, 10, 4, 520, 21, 78, 14,
      [("Tipo 00 flour", "500 g"), ("Water", "325 ml"), ("Fresh yeast", "3 g"), ("Sea salt", "10 g"),
       ("San Marzano tomatoes", "300 g"), ("Fior di latte", "250 g"), ("Fresh basil", "1 handful")],
      ["Mix flour, water, yeast and salt; knead 10 minutes and rest for 2 hours until doubled.",
       "Divide into 4 balls, stretch each by hand into a thin round.",
       "Top with crushed tomatoes and torn mozzarella.",
       "Bake at the highest oven temperature (250 C+) for 8-10 minutes; finish with basil and olive oil."]),
    R("Tiramisù Classico", "Coffee-soaked savoiardi, airy mascarpone cream and a dusting of cocoa.",
      "italian", "dolce", "medium", ["vegetarian"], 30, 0, 6, 430, 8, 38, 27,
      [("Mascarpone", "500 g"), ("Eggs, separated", "4"), ("Sugar", "100 g"), ("Espresso, cooled", "300 ml"),
       ("Savoiardi biscuits", "250 g"), ("Cocoa powder", "3 tbsp")],
      ["Whisk yolks with sugar until pale, then fold in the mascarpone.",
       "Whip the whites to stiff peaks and fold gently into the cream.",
       "Dip savoiardi briefly in espresso and layer in a dish, alternating with cream.",
       "Chill at least 6 hours and dust with cocoa before serving."]),
    R("Risotto ai Funghi", "Creamy Arborio rice with porcini and cremini mushrooms, finished with parmigiano.",
      "italian", "primo", "medium", ["vegetarian", "gluten-free"], 15, 30, 4, 480, 13, 70, 15,
      [("Arborio rice", "320 g"), ("Mixed mushrooms", "400 g"), ("Vegetable stock", "1.2 l"), ("Shallot", "1"),
       ("Dry white wine", "100 ml"), ("Parmigiano Reggiano", "60 g"), ("Butter", "30 g")],
      ["Sauté mushrooms until golden; set aside.",
       "Soften the shallot, toast the rice for a minute, deglaze with wine.",
       "Add hot stock a ladle at a time, stirring, for about 18 minutes.",
       "Fold in mushrooms, butter and parmigiano; rest 2 minutes before serving."]),
    R("Insalata Caprese", "Sun-ripe tomatoes, buffalo mozzarella and basil - three ingredients, zero excuses.",
      "italian", "antipasto", "easy", ["vegetarian", "gluten-free", "low-carb"], 10, 0, 2, 310, 18, 8, 23,
      [("Ripe tomatoes", "3"), ("Buffalo mozzarella", "250 g"), ("Fresh basil", "10 leaves"),
       ("Extra-virgin olive oil", "2 tbsp"), ("Flaky sea salt", "to taste")],
      ["Slice the tomatoes and mozzarella about 1 cm thick.",
       "Alternate slices on a plate with basil leaves.",
       "Drizzle with olive oil and season with salt just before serving."]),
    R("Minestrone di Verdure", "A hearty vegan Tuscan soup packed with seasonal vegetables and cannellini beans.",
      "italian", "primo", "easy", ["vegan", "dairy-free", "low-calorie"], 20, 40, 6, 210, 9, 34, 5,
      [("Carrots", "2"), ("Celery stalks", "2"), ("Zucchini", "2"), ("Cannellini beans", "400 g"),
       ("Chopped tomatoes", "400 g"), ("Small pasta", "100 g"), ("Vegetable stock", "1.5 l"), ("Olive oil", "2 tbsp")],
      ["Sweat diced carrot, celery and onion in olive oil for 8 minutes.",
       "Add zucchini, tomatoes, beans and stock; simmer 25 minutes.",
       "Add the pasta and cook until tender; season and serve with a drizzle of olive oil."]),
    R("Bruschetta al Pomodoro", "Grilled country bread rubbed with garlic, topped with marinated tomatoes.",
      "italian", "antipasto", "easy", ["vegan", "dairy-free"], 10, 5, 4, 180, 5, 28, 6,
      [("Country bread", "8 slices"), ("Ripe tomatoes", "4"), ("Garlic clove", "1"), ("Basil", "6 leaves"),
       ("Extra-virgin olive oil", "3 tbsp")],
      ["Dice tomatoes and marinate with basil, oil and salt for 10 minutes.",
       "Grill the bread until charred at the edges and rub with raw garlic.",
       "Spoon the tomatoes on top and serve immediately."]),
    R("Panna Cotta ai Frutti di Bosco", "Trembling vanilla cream with a tart wild berry sauce from Piedmont.",
      "italian", "dolce", "easy", ["vegetarian", "gluten-free"], 15, 5, 6, 340, 5, 27, 24,
      [("Double cream", "500 ml"), ("Whole milk", "250 ml"), ("Sugar", "80 g"), ("Gelatine leaves", "3"),
       ("Vanilla pod", "1"), ("Mixed berries", "250 g")],
      ["Soak gelatine in cold water. Warm cream, milk, sugar and vanilla without boiling.",
       "Stir in the squeezed gelatine until dissolved and pour into moulds.",
       "Chill for 5 hours, then unmould and top with a simmered berry sauce."]),
    R("Greek Salad (Horiatiki)", "Crunchy cucumber, tomato, olives and a slab of feta - the sunshine bowl.",
      "greek", "contorno", "easy", ["vegetarian", "gluten-free", "low-carb"], 10, 0, 2, 290, 9, 12, 22,
      [("Tomatoes", "3"), ("Cucumber", "1"), ("Red onion", "1/2"), ("Kalamata olives", "80 g"),
       ("Feta", "150 g"), ("Olive oil", "3 tbsp"), ("Dried oregano", "1 tsp")],
      ["Cut tomato and cucumber into chunks, slice the onion thinly.",
       "Combine with olives, top with the feta slab.",
       "Dress with olive oil and oregano."]),
    R("Miso Salmon Bowl", "Glazed salmon over rice with cucumber and edamame - lean, bright and high in protein.",
      "japanese", "secondo", "easy", ["high-protein", "dairy-free"], 15, 12, 2, 560, 38, 52, 22,
      [("Salmon fillets", "2"), ("White miso", "2 tbsp"), ("Mirin", "1 tbsp"), ("Cooked sushi rice", "300 g"),
       ("Cucumber", "1/2"), ("Edamame", "100 g"), ("Sesame seeds", "1 tsp")],
      ["Mix miso and mirin and brush over the salmon; rest 10 minutes.",
       "Roast at 200 C for 10-12 minutes until caramelised.",
       "Serve over rice with cucumber, edamame and sesame."]),
]


def main() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == DEMO_USER["username"]))
        if user is None:
            user = User(
                username=DEMO_USER["username"], email=DEMO_USER["email"],
                hashed_password=hash_password(DEMO_USER["password"]),
            )
            db.add(user)
            db.commit()
            print(f"Created demo user  ->  username: {DEMO_USER['username']}  password: {DEMO_USER['password']}")

        created = 0
        for r in RECIPES:
            if db.scalar(select(Recipe.id).where(Recipe.title == r["title"])):
                continue
            image, thumb = store_image(placeholder_image(r["title"], r["category"]))
            recipe = Recipe(
                title=r["title"], slug=unique_slug(db, r["title"]), description=r["description"],
                cuisine=r["cuisine"], category=r["category"], difficulty=r["difficulty"],
                prep_minutes=r["prep"], cook_minutes=r["cook"], servings=r["servings"],
                calories=r["kcal"], protein_g=r["p"], carbs_g=r["c"], fat_g=r["f"],
                image_path=image, thumb_path=thumb, author_id=user.id,
            )
            recipe.diet_tags = r["tags"]
            recipe.ingredients = [
                Ingredient(position=i, name=n, quantity=q) for i, (n, q) in enumerate(r["ings"], 1)
            ]
            recipe.steps = [Step(position=i, instruction=s) for i, s in enumerate(r["steps"], 1)]
            db.add(recipe)
            created += 1
        db.commit()
        print(f"Seeded {created} new recipe(s).")


if __name__ == "__main__":
    main()
