# Failure analysis

Ranks are over the top 20 unique Recipes; `-` means not found.

## Counts per Chunking strategy

| Strategy | Queries | rerank_hurt | rerank_help |
|---|---:|---:|---:|
| fixed | 298 | 58 | 104 |
| semantic | 298 | 62 | 91 |
| sentence | 298 | 67 | 99 |

## Metrics by word overlap

High overlap: every content word of the query is in the Recipe's text (154 queries). Low: the rest (144 queries).

| Config | Strategy | Overlap | R@5 | R@10 | R@20 | MRR | nDCG@5 | nDCG@10 |
|---|---|---|---:|---:|---:|---:|---:|---:|
| dense | fixed | high | 0.740 | 0.799 | 0.864 | 0.539 | 0.580 | 0.599 |
| dense | fixed | low | 0.479 | 0.611 | 0.722 | 0.396 | 0.396 | 0.441 |
| dense | semantic | high | 0.734 | 0.818 | 0.890 | 0.570 | 0.598 | 0.626 |
| dense | semantic | low | 0.528 | 0.618 | 0.701 | 0.400 | 0.419 | 0.448 |
| dense | sentence | high | 0.701 | 0.799 | 0.864 | 0.540 | 0.567 | 0.599 |
| dense | sentence | low | 0.507 | 0.590 | 0.708 | 0.405 | 0.416 | 0.443 |
| fusion | fixed | high | 0.779 | 0.896 | 0.955 | 0.638 | 0.658 | 0.696 |
| fusion | fixed | low | 0.500 | 0.611 | 0.757 | 0.368 | 0.382 | 0.418 |
| fusion | semantic | high | 0.812 | 0.903 | 0.961 | 0.670 | 0.693 | 0.722 |
| fusion | semantic | low | 0.514 | 0.646 | 0.736 | 0.364 | 0.384 | 0.426 |
| fusion | sentence | high | 0.805 | 0.864 | 0.942 | 0.635 | 0.667 | 0.686 |
| fusion | sentence | low | 0.472 | 0.639 | 0.743 | 0.366 | 0.371 | 0.424 |
| hybrid | fixed | high | 0.864 | 0.922 | 0.961 | 0.685 | 0.721 | 0.740 |
| hybrid | fixed | low | 0.597 | 0.715 | 0.778 | 0.410 | 0.442 | 0.480 |
| hybrid | semantic | high | 0.838 | 0.929 | 0.961 | 0.682 | 0.710 | 0.740 |
| hybrid | semantic | low | 0.625 | 0.715 | 0.785 | 0.422 | 0.460 | 0.490 |
| hybrid | sentence | high | 0.838 | 0.922 | 0.948 | 0.672 | 0.704 | 0.732 |
| hybrid | sentence | low | 0.597 | 0.694 | 0.771 | 0.412 | 0.443 | 0.475 |

## rerank_hurt: Reranking ranked the Recipe lower than the Fusion baseline

### fixed (58)

| Query id | Query | Recipe | dense | fusion | hybrid |
|---|---|---|---:|---:|---:|
| q014 | cheesy breakfast casserole with spinach and sausage | Spinach, Sausage, and Egg Casserole | 1 | 1 | 3 |
| q016 | baked beef and rice rolled tortillas | Baked Beef Taquitos | 1 | 1 | 2 |
| q017 | japanese banana custard cold snack | Japanese Banana Rice Pudding | 1 | 1 | 2 |
| q018 | rich brie and garlic wine dip | Matty's Brie Cheese Fondue | 2 | 6 | 9 |
| q023 | moroccan flavors shrimp couscous | One-Pot Moroccan Shrimp Tagine | 2 | 1 | 2 |
| q027 | sausage cheese balls | Easy Sausage Balls | - | 18 | 19 |
| q028 | zucchini corn pepper cheese pan fry | Calabacitas | 2 | 1 | 2 |
| q030 | crunchy ramen noodle and bok choy | Crunchy Ramen-Bok Choy Salad | 1 | 1 | 4 |
| q036 | creamy potato casserole with sour cream | Easy Sour Cream Scalloped Potatoes | 4 | 4 | 13 |
| q045 | pasta salad with olives and lemon | Orzo Pasta Salad | 4 | 2 | 6 |

48 more, not listed.

### semantic (62)

| Query id | Query | Recipe | dense | fusion | hybrid |
|---|---|---|---:|---:|---:|
| q014 | cheesy breakfast casserole with spinach and sausage | Spinach, Sausage, and Egg Casserole | 1 | 1 | 2 |
| q017 | japanese banana custard cold snack | Japanese Banana Rice Pudding | 1 | 2 | 3 |
| q021 | watermelon mint cooling dessert | Watermelon Mint Ice Cream | 1 | 2 | 6 |
| q023 | moroccan flavors shrimp couscous | One-Pot Moroccan Shrimp Tagine | 2 | 1 | 2 |
| q024 | chocolate cookie with cherry and walnut | Chocolate Thumbprints with Cherries and Walnuts | 1 | 1 | 2 |
| q026 | sliced tomatoes with basil and mozzarella | Tomato-Basil Salad | 2 | 2 | 3 |
| q030 | crunchy ramen noodle and bok choy | Crunchy Ramen-Bok Choy Salad | 2 | 1 | 2 |
| q036 | creamy potato casserole with sour cream | Easy Sour Cream Scalloped Potatoes | 6 | 4 | 7 |
| q038 | smoked bacon collard greens southern style | Easy Collard Greens | 7 | 4 | 19 |
| q045 | pasta salad with olives and lemon | Orzo Pasta Salad | 12 | 4 | 11 |

52 more, not listed.

### sentence (67)

| Query id | Query | Recipe | dense | fusion | hybrid |
|---|---|---|---:|---:|---:|
| q014 | cheesy breakfast casserole with spinach and sausage | Spinach, Sausage, and Egg Casserole | 1 | 1 | 3 |
| q017 | japanese banana custard cold snack | Japanese Banana Rice Pudding | 1 | 1 | 3 |
| q018 | rich brie and garlic wine dip | Matty's Brie Cheese Fondue | 2 | 8 | 11 |
| q021 | watermelon mint cooling dessert | Watermelon Mint Ice Cream | 1 | 3 | 5 |
| q023 | moroccan flavors shrimp couscous | One-Pot Moroccan Shrimp Tagine | 2 | 1 | 2 |
| q030 | crunchy ramen noodle and bok choy | Crunchy Ramen-Bok Choy Salad | 1 | 1 | 2 |
| q036 | creamy potato casserole with sour cream | Easy Sour Cream Scalloped Potatoes | 4 | 12 | - |
| q038 | smoked bacon collard greens southern style | Easy Collard Greens | - | 11 | 16 |
| q045 | pasta salad with olives and lemon | Orzo Pasta Salad | 12 | 4 | 11 |
| q047 | crispy potato breakfast side | Quick and Easy Home Fries | 18 | 4 | 5 |

57 more, not listed.


## rerank_help: Reranking ranked the Recipe higher than the Fusion baseline

### fixed (104)

| Query id | Query | Recipe | dense | fusion | hybrid |
|---|---|---|---:|---:|---:|
| q002 | creamy tomato based dressing with vinegar | Dorothy Lynch® Style Salad Dressing | 4 | 15 | 6 |
| q005 | chocolate cupcakes with cherry cream cheese filling | PHILLY Blackforest Stuffed Cupcakes | - | 7 | 4 |
| q006 | chicken breast with green olives | Chicken and Olives | 2 | 8 | 1 |
| q010 | garlic roasted kale | Easy Garlic Kale | 3 | 4 | 3 |
| q011 | strawberry infused syrup for drinks | Strawberry Soda Syrup | 1 | 3 | 1 |
| q012 | yellow split pea soup with curry powder | Vegan Split Pea Soup II | - | 4 | 2 |
| q019 | apple and nutmeg fried bites | Apple Fritters I | - | 12 | 3 |
| q037 | baked salmon with maple mustard and nuts | Easy Pistachio-Crusted Salmon | - | 10 | 5 |
| q038 | smoked bacon collard greens southern style | Easy Collard Greens | 13 | 12 | 11 |
| q039 | rich buttery pastry layers | Danish Pastry | - | 5 | 2 |

94 more, not listed.

### semantic (91)

| Query id | Query | Recipe | dense | fusion | hybrid |
|---|---|---|---:|---:|---:|
| q002 | creamy tomato based dressing with vinegar | Dorothy Lynch® Style Salad Dressing | 3 | 14 | 5 |
| q005 | chocolate cupcakes with cherry cream cheese filling | PHILLY Blackforest Stuffed Cupcakes | 20 | 5 | 4 |
| q006 | chicken breast with green olives | Chicken and Olives | 1 | 11 | 1 |
| q010 | garlic roasted kale | Easy Garlic Kale | 2 | 3 | 2 |
| q011 | strawberry infused syrup for drinks | Strawberry Soda Syrup | 1 | 2 | 1 |
| q012 | yellow split pea soup with curry powder | Vegan Split Pea Soup II | - | 4 | 2 |
| q018 | rich brie and garlic wine dip | Matty's Brie Cheese Fondue | 2 | 9 | 8 |
| q019 | apple and nutmeg fried bites | Apple Fritters I | - | 14 | 7 |
| q027 | sausage cheese balls | Easy Sausage Balls | 9 | 8 | 3 |
| q029 | creamy soy ginger pasta with beef and veggies | Asian Pasta Salad with Beef, Broccoli and Bean Sprouts | - | 2 | 1 |

81 more, not listed.

### sentence (99)

| Query id | Query | Recipe | dense | fusion | hybrid |
|---|---|---|---:|---:|---:|
| q002 | creamy tomato based dressing with vinegar | Dorothy Lynch® Style Salad Dressing | 3 | 13 | 6 |
| q003 | mediterranean chicken hoagie with olives | Mediterranean Chicken Sandwich | - | 13 | 1 |
| q005 | chocolate cupcakes with cherry cream cheese filling | PHILLY Blackforest Stuffed Cupcakes | 15 | 7 | 4 |
| q006 | chicken breast with green olives | Chicken and Olives | 1 | 9 | 1 |
| q007 | creamy crawfish soup with vegetables | Louisiana Crawfish Bisque | 16 | 13 | 12 |
| q011 | strawberry infused syrup for drinks | Strawberry Soda Syrup | 1 | 3 | 1 |
| q012 | yellow split pea soup with curry powder | Vegan Split Pea Soup II | 19 | 4 | 2 |
| q019 | apple and nutmeg fried bites | Apple Fritters I | - | 15 | 3 |
| q026 | sliced tomatoes with basil and mozzarella | Tomato-Basil Salad | 2 | 4 | 2 |
| q037 | baked salmon with maple mustard and nuts | Easy Pistachio-Crusted Salmon | - | 13 | 7 |

89 more, not listed.
