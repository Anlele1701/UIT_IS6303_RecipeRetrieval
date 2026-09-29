# Failure analysis

Ranks are over the top 20 unique Recipes; `-` means not found.

## Counts per Chunking strategy

| Strategy | Queries | sparse_win | dense_win | rerank_hurt | rerank_help |
|---|---:|---:|---:|---:|---:|
| fixed | 298 | 40 | 33 | 58 | 104 |
| semantic | 298 | 35 | 32 | 62 | 91 |
| sentence | 298 | 41 | 31 | 67 | 99 |

## Metrics by word overlap

High overlap: every content word of the query is in the Recipe's text (154 queries). Low: the rest (144 queries).

| Config | Strategy | Overlap | R@5 | R@10 | R@20 | MRR | nDCG@5 | nDCG@10 |
|---|---|---|---:|---:|---:|---:|---:|---:|
| sparse | fixed | high | 0.825 | 0.903 | 0.935 | 0.690 | 0.714 | 0.740 |
| sparse | fixed | low | 0.424 | 0.549 | 0.632 | 0.309 | 0.319 | 0.361 |
| sparse | semantic | high | 0.825 | 0.896 | 0.929 | 0.670 | 0.699 | 0.724 |
| sparse | semantic | low | 0.431 | 0.556 | 0.667 | 0.297 | 0.311 | 0.352 |
| sparse | sentence | high | 0.831 | 0.883 | 0.935 | 0.667 | 0.700 | 0.717 |
| sparse | sentence | low | 0.438 | 0.569 | 0.667 | 0.297 | 0.314 | 0.356 |
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

## sparse_win: Sparse found the Recipe in the top 10, Dense didn't

### fixed (40)

| Query id | Query | Recipe | sparse | dense | fusion | hybrid |
|---|---|---|---:|---:|---:|---:|
| q005 | chocolate cupcakes with cherry cream cheese filling | PHILLY Blackforest Stuffed Cupcakes | 3 | - | 7 | 4 |
| q012 | yellow split pea soup with curry powder | Vegan Split Pea Soup II | 1 | - | 4 | 2 |
| q019 | apple and nutmeg fried bites | Apple Fritters I | 6 | - | 12 | 3 |
| q027 | sausage cheese balls | Easy Sausage Balls | 10 | - | 18 | 19 |
| q037 | baked salmon with maple mustard and nuts | Easy Pistachio-Crusted Salmon | 2 | - | 10 | 5 |
| q038 | smoked bacon collard greens southern style | Easy Collard Greens | 6 | 13 | 12 | 11 |
| q039 | rich buttery pastry layers | Danish Pastry | 1 | - | 5 | 2 |
| q047 | crispy potato breakfast side | Quick and Easy Home Fries | 1 | 17 | 5 | 5 |
| q051 | flattened meatball with onions and herbs | German Hamburgers (Frikadellen) | 3 | - | 11 | 1 |
| q067 | tuna salad with veggies | Where's the Tuna Salad | 6 | - | 16 | 10 |

30 more, not listed.

### semantic (35)

| Query id | Query | Recipe | sparse | dense | fusion | hybrid |
|---|---|---|---:|---:|---:|---:|
| q005 | chocolate cupcakes with cherry cream cheese filling | PHILLY Blackforest Stuffed Cupcakes | 3 | 20 | 5 | 4 |
| q012 | yellow split pea soup with curry powder | Vegan Split Pea Soup II | 1 | - | 4 | 2 |
| q019 | apple and nutmeg fried bites | Apple Fritters I | 7 | - | 14 | 7 |
| q029 | creamy soy ginger pasta with beef and veggies | Asian Pasta Salad with Beef, Broccoli and Bean Sprouts | 1 | - | 2 | 1 |
| q037 | baked salmon with maple mustard and nuts | Easy Pistachio-Crusted Salmon | 2 | - | 7 | 4 |
| q045 | pasta salad with olives and lemon | Orzo Pasta Salad | 2 | 12 | 4 | 11 |
| q047 | crispy potato breakfast side | Quick and Easy Home Fries | 1 | 16 | 3 | 6 |
| q051 | flattened meatball with onions and herbs | German Hamburgers (Frikadellen) | 3 | - | 9 | 1 |
| q064 | smoked ham and kidney bean stew | Ham and Bean Soup I | 1 | 17 | 7 | 1 |
| q067 | tuna salad with veggies | Where's the Tuna Salad | 6 | - | 16 | 10 |

25 more, not listed.

### sentence (41)

| Query id | Query | Recipe | sparse | dense | fusion | hybrid |
|---|---|---|---:|---:|---:|---:|
| q003 | mediterranean chicken hoagie with olives | Mediterranean Chicken Sandwich | 1 | - | 13 | 1 |
| q005 | chocolate cupcakes with cherry cream cheese filling | PHILLY Blackforest Stuffed Cupcakes | 3 | 15 | 7 | 4 |
| q012 | yellow split pea soup with curry powder | Vegan Split Pea Soup II | 1 | 19 | 4 | 2 |
| q019 | apple and nutmeg fried bites | Apple Fritters I | 8 | - | 15 | 3 |
| q037 | baked salmon with maple mustard and nuts | Easy Pistachio-Crusted Salmon | 2 | - | 13 | 7 |
| q038 | smoked bacon collard greens southern style | Easy Collard Greens | 5 | - | 11 | 16 |
| q045 | pasta salad with olives and lemon | Orzo Pasta Salad | 3 | 12 | 4 | 11 |
| q047 | crispy potato breakfast side | Quick and Easy Home Fries | 1 | 18 | 4 | 5 |
| q051 | flattened meatball with onions and herbs | German Hamburgers (Frikadellen) | 2 | - | 10 | 1 |
| q067 | tuna salad with veggies | Where's the Tuna Salad | 5 | - | 13 | 10 |

31 more, not listed.


## dense_win: Dense found the Recipe in the top 10, Sparse didn't

### fixed (33)

| Query id | Query | Recipe | sparse | dense | fusion | hybrid |
|---|---|---|---:|---:|---:|---:|
| q002 | creamy tomato based dressing with vinegar | Dorothy Lynch® Style Salad Dressing | - | 4 | 15 | 6 |
| q006 | chicken breast with green olives | Chicken and Olives | - | 2 | 8 | 1 |
| q011 | strawberry infused syrup for drinks | Strawberry Soda Syrup | - | 1 | 3 | 1 |
| q026 | sliced tomatoes with basil and mozzarella | Tomato-Basil Salad | 15 | 2 | 3 | 3 |
| q040 | grilled potato cold side dish | Grilled Potato Salad | - | 6 | 16 | 14 |
| q042 | creamy onion dip with cheese | French Onion Dip | - | 2 | 12 | 2 |
| q046 | creamy chicken artichoke spread | Chicken Artichoke Dip | - | 7 | 14 | 6 |
| q068 | turkey chili cornbread casserole | Speedy Chili Pot Pie | - | 6 | 15 | 4 |
| q081 | grilled pork chops herby lemony | Grilled Lemon Herb Pork Chops | - | 1 | 3 | 1 |
| q110 | sweet buttermilk butter bread | Buttermilk Honey Bread | - | 3 | 5 | 5 |

23 more, not listed.

### semantic (32)

| Query id | Query | Recipe | sparse | dense | fusion | hybrid |
|---|---|---|---:|---:|---:|---:|
| q002 | creamy tomato based dressing with vinegar | Dorothy Lynch® Style Salad Dressing | - | 3 | 14 | 5 |
| q006 | chicken breast with green olives | Chicken and Olives | - | 1 | 11 | 1 |
| q011 | strawberry infused syrup for drinks | Strawberry Soda Syrup | 13 | 1 | 2 | 1 |
| q027 | sausage cheese balls | Easy Sausage Balls | 11 | 9 | 8 | 3 |
| q040 | grilled potato cold side dish | Grilled Potato Salad | - | 9 | - | - |
| q042 | creamy onion dip with cheese | French Onion Dip | - | 2 | 14 | 2 |
| q044 | warm spiced wine with cloves | Gluehwein | - | 5 | 12 | 2 |
| q055 | blueberry oatmeal breakfast | Blueberry Oatmeal | - | 2 | 9 | 10 |
| q068 | turkey chili cornbread casserole | Speedy Chili Pot Pie | - | 5 | 12 | 2 |
| q075 | gluten-free cream cheese bites | Gluten-Free Cheesecake Cupcakes | 20 | 10 | 9 | 11 |

22 more, not listed.

### sentence (31)

| Query id | Query | Recipe | sparse | dense | fusion | hybrid |
|---|---|---|---:|---:|---:|---:|
| q002 | creamy tomato based dressing with vinegar | Dorothy Lynch® Style Salad Dressing | - | 3 | 13 | 6 |
| q006 | chicken breast with green olives | Chicken and Olives | - | 1 | 9 | 1 |
| q011 | strawberry infused syrup for drinks | Strawberry Soda Syrup | 20 | 1 | 3 | 1 |
| q026 | sliced tomatoes with basil and mozzarella | Tomato-Basil Salad | 14 | 2 | 4 | 2 |
| q042 | creamy onion dip with cheese | French Onion Dip | - | 2 | 12 | 2 |
| q068 | turkey chili cornbread casserole | Speedy Chili Pot Pie | - | 7 | 14 | 4 |
| q075 | gluten-free cream cheese bites | Gluten-Free Cheesecake Cupcakes | - | 8 | 15 | 9 |
| q078 | garlic asparagus in the oven | Quick and Easy Baked Asparagus | 12 | 2 | 3 | 2 |
| q101 | creamy pumpkin soup with spices | Cream of Pumpkin Soup | 11 | 1 | 2 | 1 |
| q109 | creamy corn chile dip with jalapeño | Corn Dip | 20 | 9 | 8 | 2 |

21 more, not listed.


## rerank_hurt: Reranking ranked the Recipe lower than the Fusion baseline

### fixed (58)

| Query id | Query | Recipe | sparse | dense | fusion | hybrid |
|---|---|---|---:|---:|---:|---:|
| q014 | cheesy breakfast casserole with spinach and sausage | Spinach, Sausage, and Egg Casserole | 3 | 1 | 1 | 3 |
| q016 | baked beef and rice rolled tortillas | Baked Beef Taquitos | 1 | 1 | 1 | 2 |
| q017 | japanese banana custard cold snack | Japanese Banana Rice Pudding | 1 | 1 | 1 | 2 |
| q018 | rich brie and garlic wine dip | Matty's Brie Cheese Fondue | 4 | 2 | 6 | 9 |
| q023 | moroccan flavors shrimp couscous | One-Pot Moroccan Shrimp Tagine | 1 | 2 | 1 | 2 |
| q027 | sausage cheese balls | Easy Sausage Balls | 10 | - | 18 | 19 |
| q028 | zucchini corn pepper cheese pan fry | Calabacitas | 1 | 2 | 1 | 2 |
| q030 | crunchy ramen noodle and bok choy | Crunchy Ramen-Bok Choy Salad | 2 | 1 | 1 | 4 |
| q036 | creamy potato casserole with sour cream | Easy Sour Cream Scalloped Potatoes | 5 | 4 | 4 | 13 |
| q045 | pasta salad with olives and lemon | Orzo Pasta Salad | 2 | 4 | 2 | 6 |

48 more, not listed.

### semantic (62)

| Query id | Query | Recipe | sparse | dense | fusion | hybrid |
|---|---|---|---:|---:|---:|---:|
| q014 | cheesy breakfast casserole with spinach and sausage | Spinach, Sausage, and Egg Casserole | 4 | 1 | 1 | 2 |
| q017 | japanese banana custard cold snack | Japanese Banana Rice Pudding | 2 | 1 | 2 | 3 |
| q021 | watermelon mint cooling dessert | Watermelon Mint Ice Cream | 4 | 1 | 2 | 6 |
| q023 | moroccan flavors shrimp couscous | One-Pot Moroccan Shrimp Tagine | 1 | 2 | 1 | 2 |
| q024 | chocolate cookie with cherry and walnut | Chocolate Thumbprints with Cherries and Walnuts | 1 | 1 | 1 | 2 |
| q026 | sliced tomatoes with basil and mozzarella | Tomato-Basil Salad | 6 | 2 | 2 | 3 |
| q030 | crunchy ramen noodle and bok choy | Crunchy Ramen-Bok Choy Salad | 2 | 2 | 1 | 2 |
| q036 | creamy potato casserole with sour cream | Easy Sour Cream Scalloped Potatoes | 4 | 6 | 4 | 7 |
| q038 | smoked bacon collard greens southern style | Easy Collard Greens | 5 | 7 | 4 | 19 |
| q045 | pasta salad with olives and lemon | Orzo Pasta Salad | 2 | 12 | 4 | 11 |

52 more, not listed.

### sentence (67)

| Query id | Query | Recipe | sparse | dense | fusion | hybrid |
|---|---|---|---:|---:|---:|---:|
| q014 | cheesy breakfast casserole with spinach and sausage | Spinach, Sausage, and Egg Casserole | 4 | 1 | 1 | 3 |
| q017 | japanese banana custard cold snack | Japanese Banana Rice Pudding | 2 | 1 | 1 | 3 |
| q018 | rich brie and garlic wine dip | Matty's Brie Cheese Fondue | 4 | 2 | 8 | 11 |
| q021 | watermelon mint cooling dessert | Watermelon Mint Ice Cream | 8 | 1 | 3 | 5 |
| q023 | moroccan flavors shrimp couscous | One-Pot Moroccan Shrimp Tagine | 1 | 2 | 1 | 2 |
| q030 | crunchy ramen noodle and bok choy | Crunchy Ramen-Bok Choy Salad | 1 | 1 | 1 | 2 |
| q036 | creamy potato casserole with sour cream | Easy Sour Cream Scalloped Potatoes | 5 | 4 | 12 | - |
| q038 | smoked bacon collard greens southern style | Easy Collard Greens | 5 | - | 11 | 16 |
| q045 | pasta salad with olives and lemon | Orzo Pasta Salad | 3 | 12 | 4 | 11 |
| q047 | crispy potato breakfast side | Quick and Easy Home Fries | 1 | 18 | 4 | 5 |

57 more, not listed.


## rerank_help: Reranking ranked the Recipe higher than the Fusion baseline

### fixed (104)

| Query id | Query | Recipe | sparse | dense | fusion | hybrid |
|---|---|---|---:|---:|---:|---:|
| q002 | creamy tomato based dressing with vinegar | Dorothy Lynch® Style Salad Dressing | - | 4 | 15 | 6 |
| q005 | chocolate cupcakes with cherry cream cheese filling | PHILLY Blackforest Stuffed Cupcakes | 3 | - | 7 | 4 |
| q006 | chicken breast with green olives | Chicken and Olives | - | 2 | 8 | 1 |
| q010 | garlic roasted kale | Easy Garlic Kale | 7 | 3 | 4 | 3 |
| q011 | strawberry infused syrup for drinks | Strawberry Soda Syrup | - | 1 | 3 | 1 |
| q012 | yellow split pea soup with curry powder | Vegan Split Pea Soup II | 1 | - | 4 | 2 |
| q019 | apple and nutmeg fried bites | Apple Fritters I | 6 | - | 12 | 3 |
| q037 | baked salmon with maple mustard and nuts | Easy Pistachio-Crusted Salmon | 2 | - | 10 | 5 |
| q038 | smoked bacon collard greens southern style | Easy Collard Greens | 6 | 13 | 12 | 11 |
| q039 | rich buttery pastry layers | Danish Pastry | 1 | - | 5 | 2 |

94 more, not listed.

### semantic (91)

| Query id | Query | Recipe | sparse | dense | fusion | hybrid |
|---|---|---|---:|---:|---:|---:|
| q002 | creamy tomato based dressing with vinegar | Dorothy Lynch® Style Salad Dressing | - | 3 | 14 | 5 |
| q005 | chocolate cupcakes with cherry cream cheese filling | PHILLY Blackforest Stuffed Cupcakes | 3 | 20 | 5 | 4 |
| q006 | chicken breast with green olives | Chicken and Olives | - | 1 | 11 | 1 |
| q010 | garlic roasted kale | Easy Garlic Kale | 8 | 2 | 3 | 2 |
| q011 | strawberry infused syrup for drinks | Strawberry Soda Syrup | 13 | 1 | 2 | 1 |
| q012 | yellow split pea soup with curry powder | Vegan Split Pea Soup II | 1 | - | 4 | 2 |
| q018 | rich brie and garlic wine dip | Matty's Brie Cheese Fondue | 4 | 2 | 9 | 8 |
| q019 | apple and nutmeg fried bites | Apple Fritters I | 7 | - | 14 | 7 |
| q027 | sausage cheese balls | Easy Sausage Balls | 11 | 9 | 8 | 3 |
| q029 | creamy soy ginger pasta with beef and veggies | Asian Pasta Salad with Beef, Broccoli and Bean Sprouts | 1 | - | 2 | 1 |

81 more, not listed.

### sentence (99)

| Query id | Query | Recipe | sparse | dense | fusion | hybrid |
|---|---|---|---:|---:|---:|---:|
| q002 | creamy tomato based dressing with vinegar | Dorothy Lynch® Style Salad Dressing | - | 3 | 13 | 6 |
| q003 | mediterranean chicken hoagie with olives | Mediterranean Chicken Sandwich | 1 | - | 13 | 1 |
| q005 | chocolate cupcakes with cherry cream cheese filling | PHILLY Blackforest Stuffed Cupcakes | 3 | 15 | 7 | 4 |
| q006 | chicken breast with green olives | Chicken and Olives | - | 1 | 9 | 1 |
| q007 | creamy crawfish soup with vegetables | Louisiana Crawfish Bisque | - | 16 | 13 | 12 |
| q011 | strawberry infused syrup for drinks | Strawberry Soda Syrup | 20 | 1 | 3 | 1 |
| q012 | yellow split pea soup with curry powder | Vegan Split Pea Soup II | 1 | 19 | 4 | 2 |
| q019 | apple and nutmeg fried bites | Apple Fritters I | 8 | - | 15 | 3 |
| q026 | sliced tomatoes with basil and mozzarella | Tomato-Basil Salad | 14 | 2 | 4 | 2 |
| q037 | baked salmon with maple mustard and nuts | Easy Pistachio-Crusted Salmon | 2 | - | 13 | 7 |

89 more, not listed.
