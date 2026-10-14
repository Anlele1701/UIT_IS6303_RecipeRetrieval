"""Writes data/lexicon/vi_alias.csv from the hand-written list below, adding an unaccented copy of
each alias (users often type without diacritics: "dau phong"). Run from scripts/:

    uv run python -m lexicon.make_vi_alias

target_type "allergen" names one of the 9 FDA codes (for "dị ứng X" / "không X");
"ingredient" names a canonical in ingredients.csv. One alias may have several rows.
Ambiguous words follow the cooking sense: "bơ" = butter, "quả bơ"/"trái bơ" = avocado;
"chanh" = lime (the common Vietnamese lime), "chanh vàng" = lemon.
"""

import csv
import unicodedata

from .normalize import LEXICON

# alias, target_type, target, note
ROWS = [
    # --- allergen groups ---
    ("đậu phộng", "allergen", "peanut", ""), ("đậu phụng", "allergen", "peanut", "biến thể chính tả"),
    ("lạc", "allergen", "peanut", "miền Bắc"), ("hạt lạc", "allergen", "peanut", ""),
    ("sữa", "allergen", "milk", ""), ("sữa bò", "allergen", "milk", ""), ("đồ sữa", "allergen", "milk", ""),
    ("chế phẩm từ sữa", "allergen", "milk", ""), ("lactose", "allergen", "milk", "không dung nạp lactose → tránh sữa"),
    ("trứng", "allergen", "egg", ""), ("trứng gà", "allergen", "egg", ""),
    ("cá", "allergen", "fish", ""), ("hải sản", "allergen", "fish", "hải sản = cá + giáp xác (bảo thủ)"),
    ("hải sản", "allergen", "crustacean_shellfish", ""),
    ("tôm", "allergen", "crustacean_shellfish", ""), ("cua", "allergen", "crustacean_shellfish", ""),
    ("ghẹ", "allergen", "crustacean_shellfish", ""), ("tôm hùm", "allergen", "crustacean_shellfish", ""),
    ("tép", "allergen", "crustacean_shellfish", ""), ("giáp xác", "allergen", "crustacean_shellfish", ""),
    ("động vật có vỏ", "allergen", "crustacean_shellfish", "shellfish"),
    ("các loại hạt", "allergen", "tree_nuts", ""), ("hạt cây", "allergen", "tree_nuts", ""),
    ("quả hạch", "allergen", "tree_nuts", ""), ("hạt điều", "allergen", "tree_nuts", ""),
    ("hạnh nhân", "allergen", "tree_nuts", ""), ("óc chó", "allergen", "tree_nuts", ""),
    ("hạt óc chó", "allergen", "tree_nuts", ""), ("hồ đào", "allergen", "tree_nuts", "pecan"),
    ("hạt dẻ cười", "allergen", "tree_nuts", "pistachio"), ("hạt phỉ", "allergen", "tree_nuts", "hazelnut"),
    ("hạt mắc ca", "allergen", "tree_nuts", "macadamia"), ("hạt thông", "allergen", "tree_nuts", "pine nut"),
    ("hạt dẻ", "allergen", "tree_nuts", "chestnut, bảo thủ"),
    ("lúa mì", "allergen", "wheat", ""), ("bột mì", "allergen", "wheat", ""), ("gluten", "allergen", "wheat", "gluten ≈ lúa mì (gần đúng)"),
    ("đậu nành", "allergen", "soy", ""), ("đậu tương", "allergen", "soy", "miền Bắc"),
    ("mè", "allergen", "sesame", ""), ("vừng", "allergen", "sesame", "miền Bắc"), ("hạt mè", "allergen", "sesame", ""),
    ("hạt vừng", "allergen", "sesame", ""),
    # --- meat, poultry, seafood ---
    ("thịt gà", "ingredient", "chicken", ""), ("gà", "ingredient", "chicken", ""), ("ức gà", "ingredient", "chicken breast", ""),
    ("đùi gà", "ingredient", "chicken thigh", ""), ("cánh gà", "ingredient", "chicken wing", ""),
    ("thịt bò", "ingredient", "beef", ""), ("bò", "ingredient", "beef", ""), ("bò băm", "ingredient", "beef", "ground beef"),
    ("thịt heo", "ingredient", "pork", ""), ("thịt lợn", "ingredient", "pork", ""), ("heo", "ingredient", "pork", ""),
    ("lợn", "ingredient", "pork", ""), ("ba chỉ", "ingredient", "pork belly", ""), ("ba rọi", "ingredient", "pork belly", ""),
    ("sườn heo", "ingredient", "pork sparerib", ""), ("thịt xông khói", "ingredient", "bacon", ""),
    ("giăm bông", "ingredient", "ham", ""), ("thịt nguội", "ingredient", "ham", ""), ("xúc xích", "ingredient", "sausage", ""),
    ("lạp xưởng", "ingredient", "sausage", ""), ("thịt cừu", "ingredient", "lamb", ""), ("cừu", "ingredient", "lamb", ""),
    ("gà tây", "ingredient", "turkey", ""), ("vịt", "ingredient", "duck", ""), ("thịt vịt", "ingredient", "duck", ""),
    ("cá hồi", "ingredient", "salmon", ""), ("cá ngừ", "ingredient", "tuna", ""), ("cá tuyết", "ingredient", "cod", ""),
    ("cá rô phi", "ingredient", "tilapia", ""), ("cá cơm", "ingredient", "anchovy fillet", ""),
    ("mực", "ingredient", "squid", ""), ("nghêu", "ingredient", "clam", ""), ("ngao", "ingredient", "clam", "miền Bắc"),
    ("hàu", "ingredient", "oyster", ""), ("sò điệp", "ingredient", "scallop", ""), ("vẹm", "ingredient", "mussel", ""),
    ("chem chép", "ingredient", "mussel", ""), ("tôm", "ingredient", "shrimp", ""), ("cua", "ingredient", "crab", ""),
    ("tôm hùm", "ingredient", "lobster", ""), ("thịt cua", "ingredient", "crabmeat", ""),
    ("mỡ heo", "ingredient", "lard", ""), ("mỡ lợn", "ingredient", "lard", ""), ("gelatin", "ingredient", "unflavored gelatin", ""),
    ("gelatine", "ingredient", "unflavored gelatin", ""),
    # --- dairy, egg ---
    ("trứng", "ingredient", "egg", ""), ("lòng đỏ trứng", "ingredient", "egg yolk", ""), ("lòng trắng trứng", "ingredient", "egg white", ""),
    ("sữa tươi", "ingredient", "milk", ""), ("sữa", "ingredient", "milk", ""), ("bơ", "ingredient", "butter", "nghĩa nấu ăn"),
    ("bơ lạt", "ingredient", "butter", ""), ("bơ nhạt", "ingredient", "butter", ""), ("bơ thực vật", "ingredient", "margarine", ""),
    ("phô mai", "ingredient", "cheese", ""), ("phó mát", "ingredient", "cheese", ""), ("pho mát", "ingredient", "cheese", ""),
    ("phô mai kem", "ingredient", "cream cheese", ""), ("cream cheese", "ingredient", "cream cheese", ""),
    ("kem tươi", "ingredient", "heavy cream", ""), ("kem whipping", "ingredient", "heavy cream", ""),
    ("kem chua", "ingredient", "sour cream", ""), ("sữa chua", "ingredient", "yogurt", ""),
    ("sữa đặc", "ingredient", "sweetened condensed milk", ""), ("sữa đặc có đường", "ingredient", "sweetened condensed milk", ""),
    ("sữa bột", "ingredient", "milk powder", ""), ("mayonnaise", "ingredient", "mayonnaise", ""), ("sốt mayonnaise", "ingredient", "mayonnaise", ""),
    ("kem", "ingredient", "vanilla ice cream", "kem ăn; 'kem tươi' là heavy cream"),
    # --- produce ---
    ("quả bơ", "ingredient", "avocado", ""), ("trái bơ", "ingredient", "avocado", ""),
    ("tỏi", "ingredient", "garlic", ""), ("hành tây", "ingredient", "onion", ""), ("hành", "ingredient", "onion", ""),
    ("hành lá", "ingredient", "green onion", ""), ("hành tím", "ingredient", "shallot", ""), ("hẹ tây", "ingredient", "shallot", ""),
    ("ngò", "ingredient", "cilantro", ""), ("ngò rí", "ingredient", "cilantro", ""), ("rau mùi", "ingredient", "cilantro", "miền Bắc"),
    ("gừng", "ingredient", "ginger", ""), ("sả", "ingredient", "lemongrass", ""), ("ớt", "ingredient", "chile pepper", ""),
    ("ớt chuông", "ingredient", "bell pepper", ""), ("chanh", "ingredient", "lime", "chanh ta = lime"),
    ("chanh vàng", "ingredient", "lemon", ""), ("nước cốt chanh", "ingredient", "lime juice", ""),
    ("cà chua", "ingredient", "tomato", ""), ("cà rốt", "ingredient", "carrot", ""), ("khoai tây", "ingredient", "potato", ""),
    ("khoai lang", "ingredient", "sweet potato", ""), ("khoai môn", "ingredient", "taro", ""), ("nấm", "ingredient", "mushroom", ""),
    ("dưa leo", "ingredient", "cucumber", ""), ("dưa chuột", "ingredient", "cucumber", "miền Bắc"),
    ("bắp cải", "ingredient", "cabbage", ""), ("cải thảo", "ingredient", "napa cabbage", ""), ("cải chíp", "ingredient", "bok choy", ""),
    ("cải bó xôi", "ingredient", "spinach", ""), ("rau bina", "ingredient", "spinach", ""), ("bông cải xanh", "ingredient", "broccoli", ""),
    ("súp lơ xanh", "ingredient", "broccoli", ""), ("bông cải trắng", "ingredient", "cauliflower", ""), ("súp lơ", "ingredient", "cauliflower", ""),
    ("cà tím", "ingredient", "eggplant", ""), ("bí ngòi", "ingredient", "zucchini", ""), ("bí đỏ", "ingredient", "pumpkin", ""),
    ("bắp", "ingredient", "corn", ""), ("ngô", "ingredient", "corn", "miền Bắc"), ("đậu hà lan", "ingredient", "pea", ""),
    ("đậu que", "ingredient", "green bean", ""), ("giá", "ingredient", "bean sprout", ""), ("giá đỗ", "ingredient", "bean sprout", ""),
    ("cần tây", "ingredient", "celery", ""), ("rau diếp", "ingredient", "lettuce", ""), ("xà lách", "ingredient", "lettuce", ""),
    ("củ cải", "ingredient", "radish", ""), ("củ cải trắng", "ingredient", "daikon radish", ""), ("đậu bắp", "ingredient", "okra", ""),
    ("tỏi tây", "ingredient", "leek", ""),
    ("chuối", "ingredient", "banana", ""), ("xoài", "ingredient", "mango", ""), ("dứa", "ingredient", "pineapple", ""),
    ("thơm", "ingredient", "pineapple", "miền Nam"), ("khóm", "ingredient", "pineapple", "miền Nam"), ("táo", "ingredient", "apple", ""),
    ("cam", "ingredient", "orange", ""), ("dâu tây", "ingredient", "strawberry", ""), ("dừa", "ingredient", "coconut", ""),
    ("vải", "ingredient", "lychee", ""), ("mít", "ingredient", "jackfruit", ""), ("đu đủ", "ingredient", "papaya", ""),
    ("dưa hấu", "ingredient", "watermelon", ""), ("đào", "ingredient", "peach", ""), ("lê", "ingredient", "pear", ""),
    ("nho", "ingredient", "grape", ""), ("việt quất", "ingredient", "blueberry", ""), ("nho khô", "ingredient", "raisin", ""),
    ("anh đào", "ingredient", "cherry", ""),
    # --- herbs and spices ---
    ("húng quế", "ingredient", "basil", ""), ("rau quế", "ingredient", "basil", ""), ("bạc hà", "ingredient", "mint", ""),
    ("húng lủi", "ingredient", "mint", ""), ("ngò tây", "ingredient", "parsley", ""), ("mùi tây", "ingredient", "parsley", ""),
    ("thì là", "ingredient", "dill", ""), ("hương thảo", "ingredient", "rosemary", ""), ("cỏ xạ hương", "ingredient", "thyme", ""),
    ("lá oregano", "ingredient", "oregano", ""), ("thìa là ai cập", "ingredient", "cumin", ""), ("quế", "ingredient", "cinnamon", ""),
    ("hoa hồi", "ingredient", "star anise", ""), ("hồi", "ingredient", "star anise", ""), ("nghệ", "ingredient", "turmeric", ""),
    ("bột nghệ", "ingredient", "turmeric", ""), ("bột cà ri", "ingredient", "curry powder", ""), ("ớt bột", "ingredient", "chili powder", ""),
    ("bột ớt", "ingredient", "chili powder", ""), ("ớt paprika", "ingredient", "paprika", ""), ("ngũ vị hương", "ingredient", "chinese five spice powder", ""),
    ("tiêu", "ingredient", "black pepper", ""), ("hạt tiêu", "ingredient", "black pepper", ""), ("muối", "ingredient", "salt", ""),
    ("bột tỏi", "ingredient", "garlic powder", ""), ("bột hành", "ingredient", "onion powder", ""),
    # --- pantry ---
    ("đường", "ingredient", "white sugar", ""), ("đường trắng", "ingredient", "white sugar", ""), ("đường nâu", "ingredient", "brown sugar", ""),
    ("đường bột", "ingredient", "confectioners sugar", ""), ("mật ong", "ingredient", "honey", ""),
    ("bột mì", "ingredient", "all purpose flour", ""), ("bột bắp", "ingredient", "cornstarch", ""), ("bột ngô", "ingredient", "cornstarch", ""),
    ("bột nở", "ingredient", "baking powder", ""), ("muối nở", "ingredient", "baking soda", ""), ("baking soda", "ingredient", "baking soda", ""),
    ("men nở", "ingredient", "yeast", ""), ("gạo", "ingredient", "rice", ""), ("cơm", "ingredient", "rice", ""),
    ("bánh mì", "ingredient", "bread", ""), ("vụn bánh mì", "ingredient", "bread crumb", ""), ("mì", "ingredient", "noodle", ""),
    ("mì ống", "ingredient", "pasta", ""), ("nui", "ingredient", "pasta", ""), ("mì ý", "ingredient", "spaghetti", ""),
    ("bún", "ingredient", "rice noodle", ""), ("phở", "ingredient", "rice noodle", "bánh phở"), ("bánh tráng", "ingredient", "rice paper", ""),
    ("yến mạch", "ingredient", "rolled oat", ""), ("đậu gà", "ingredient", "chickpea", ""), ("đậu đen", "ingredient", "black bean", ""),
    ("đậu lăng", "ingredient", "lentil", ""), ("diêm mạch", "ingredient", "quinoa", ""),
    ("đậu hũ", "ingredient", "tofu", ""), ("đậu phụ", "ingredient", "tofu", "miền Bắc"), ("tàu hũ", "ingredient", "tofu", ""),
    ("đậu phộng", "ingredient", "peanut", ""), ("bơ đậu phộng", "ingredient", "peanut butter", ""),
    ("hạt điều", "ingredient", "cashew", ""), ("hạnh nhân", "ingredient", "almond", ""), ("óc chó", "ingredient", "walnut", ""),
    ("hồ đào", "ingredient", "pecan", ""), ("hạt dẻ cười", "ingredient", "pistachio", ""), ("hạt phỉ", "ingredient", "hazelnut", ""),
    ("hạt mè", "ingredient", "sesame seed", ""), ("mè", "ingredient", "sesame seed", ""), ("dầu mè", "ingredient", "sesame oil", ""),
    ("dầu vừng", "ingredient", "sesame oil", ""),
    ("nước tương", "ingredient", "soy sauce", ""), ("xì dầu", "ingredient", "soy sauce", ""), ("nước mắm", "ingredient", "fish sauce", ""),
    ("dầu hào", "ingredient", "oyster sauce", ""), ("mắm tôm", "ingredient", "shrimp paste", ""), ("tương đen", "ingredient", "hoisin sauce", ""),
    ("tương ớt", "ingredient", "chili sauce", ""), ("sriracha", "ingredient", "sriracha sauce", ""), ("giấm", "ingredient", "vinegar", ""),
    ("giấm gạo", "ingredient", "rice vinegar", ""), ("dầu ô liu", "ingredient", "olive oil", ""), ("dầu oliu", "ingredient", "olive oil", ""),
    ("dầu ăn", "ingredient", "vegetable oil", ""), ("dầu dừa", "ingredient", "coconut oil", ""), ("nước cốt dừa", "ingredient", "coconut milk", ""),
    ("sữa dừa", "ingredient", "coconut milk", ""), ("sô cô la", "ingredient", "chocolate", ""), ("socola", "ingredient", "chocolate", ""),
    ("vani", "ingredient", "vanilla extract", ""), ("tương cà", "ingredient", "ketchup", ""), ("mù tạt", "ingredient", "mustard", ""),
    ("bia", "ingredient", "beer", ""), ("rượu vang đỏ", "ingredient", "red wine", ""), ("rượu vang trắng", "ingredient", "white wine", ""),
    ("nước", "ingredient", "water", ""),
]


def unaccent(s: str) -> str:
    s = s.replace("đ", "d").replace("Đ", "D")
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def ambiguous_unaccented() -> set[str]:
    """Unaccented forms shared by different accented aliases ("bò" beef / "bơ" butter -> "bo")."""
    targets: dict[str, dict[str, set]] = {}  # unaccented -> accented alias -> its targets
    for alias, kind, target, _ in ROWS:
        targets.setdefault(unaccent(alias), {}).setdefault(alias, set()).add((kind, target))
    return {u for u, by_alias in targets.items()
            if len(by_alias) > 1 and len({frozenset(t) for t in by_alias.values()}) > 1}


def main():
    skip = ambiguous_unaccented()
    out, seen = [], set()
    for alias, kind, target, note in ROWS:
        copies = [(alias, note)]
        if unaccent(alias) != alias and unaccent(alias) not in skip:
            copies.append((unaccent(alias), "không dấu" + (f"; {note}" if note else "")))
        for a, n in copies:
            if (a, kind, target) not in seen:
                seen.add((a, kind, target))
                out.append((a, kind, target, n))
    with open(LEXICON / "vi_alias.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["alias", "target_type", "target", "note"])
        w.writerows(out)
    print(f"{len(ROWS)} aliases, {len(out)} rows; unaccented copies skipped as ambiguous: {sorted(skip)}")


if __name__ == "__main__":
    main()
