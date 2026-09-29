# Failure analysis

Ranks are over the top 20 unique Recipes; `-` means not found.

## Counts per Chunking strategy

| Strategy | Queries | rerank_hurt | rerank_help |
|---|---:|---:|---:|
| fixed | 298 | 52 | 82 |
| semantic | 298 | 57 | 72 |
| sentence | 298 | 56 | 89 |

## Metrics by word overlap

High overlap: every content word of the query is in the Recipe's text (154 queries). Low: the rest (144 queries).

| Config | Strategy | Overlap | R@5 | R@10 | R@20 | MRR | nDCG@5 | nDCG@10 |
|---|---|---|---:|---:|---:|---:|---:|---:|
| dense | fixed | high | 0.896 | 0.935 | 0.955 | 0.732 | 0.768 | 0.781 |
| dense | fixed | low | 0.806 | 0.868 | 0.903 | 0.648 | 0.679 | 0.700 |
| dense | semantic | high | 0.883 | 0.922 | 0.961 | 0.743 | 0.772 | 0.785 |
| dense | semantic | low | 0.833 | 0.868 | 0.924 | 0.649 | 0.689 | 0.700 |
| dense | sentence | high | 0.857 | 0.903 | 0.942 | 0.720 | 0.747 | 0.763 |
| dense | sentence | low | 0.826 | 0.861 | 0.910 | 0.660 | 0.696 | 0.708 |
| fusion | fixed | high | 0.929 | 0.974 | 0.994 | 0.800 | 0.827 | 0.841 |
| fusion | fixed | low | 0.819 | 0.868 | 0.931 | 0.622 | 0.663 | 0.679 |
| fusion | semantic | high | 0.929 | 0.981 | 0.994 | 0.822 | 0.842 | 0.859 |
| fusion | semantic | low | 0.826 | 0.896 | 0.924 | 0.621 | 0.664 | 0.687 |
| fusion | sentence | high | 0.922 | 0.961 | 0.987 | 0.791 | 0.818 | 0.832 |
| fusion | sentence | low | 0.778 | 0.861 | 0.917 | 0.609 | 0.640 | 0.667 |
| hybrid | fixed | high | 0.961 | 0.994 | 1.000 | 0.846 | 0.871 | 0.882 |
| hybrid | fixed | low | 0.868 | 0.938 | 0.951 | 0.683 | 0.721 | 0.744 |
| hybrid | semantic | high | 0.968 | 0.994 | 1.000 | 0.851 | 0.877 | 0.886 |
| hybrid | semantic | low | 0.868 | 0.931 | 0.951 | 0.658 | 0.703 | 0.724 |
| hybrid | sentence | high | 0.961 | 0.994 | 1.000 | 0.843 | 0.869 | 0.880 |
| hybrid | sentence | low | 0.861 | 0.931 | 0.951 | 0.673 | 0.711 | 0.734 |

## rerank_hurt: Reranking ranked the Recipe lower than the Fusion baseline

### fixed (52)

| Query id | Query | Recipe | dense | fusion | hybrid |
|---|---|---|---:|---:|---:|
| q007 | creamy crawfish soup with vegetables | Louisiana Crawfish Bisque | 2 | 2 | 4 |
| q016 | baked beef and rice rolled tortillas | Baked Beef Taquitos | 1 | 1 | 2 |
| q017 | japanese banana custard cold snack | Japanese Banana Rice Pudding | 1 | 1 | 2 |
| q018 | rich brie and garlic wine dip | Matty's Brie Cheese Fondue | 2 | 6 | 9 |
| q021 | watermelon mint cooling dessert | Watermelon Mint Ice Cream | 1 | 1 | 3 |
| q026 | sliced tomatoes with basil and mozzarella | Tomato-Basil Salad | 1 | 1 | 3 |
| q028 | zucchini corn pepper cheese pan fry | Calabacitas | 2 | 1 | 2 |
| q036 | creamy potato casserole with sour cream | Easy Sour Cream Scalloped Potatoes | 1 | 1 | 2 |
| q038 | smoked bacon collard greens southern style | Easy Collard Greens | 4 | 2 | 7 |
| q042 | creamy onion dip with cheese | French Onion Dip | 1 | 1 | 2 |

42 more, not listed.

### semantic (57)

| Query id | Query | Recipe | dense | fusion | hybrid |
|---|---|---|---:|---:|---:|
| q014 | cheesy breakfast casserole with spinach and sausage | Spinach, Sausage, and Egg Casserole | 1 | 1 | 2 |
| q017 | japanese banana custard cold snack | Japanese Banana Rice Pudding | 1 | 2 | 3 |
| q021 | watermelon mint cooling dessert | Watermelon Mint Ice Cream | 1 | 2 | 4 |
| q038 | smoked bacon collard greens southern style | Easy Collard Greens | 2 | 3 | 6 |
| q040 | grilled potato cold side dish | Grilled Potato Salad | 5 | 6 | 9 |
| q045 | pasta salad with olives and lemon | Orzo Pasta Salad | 3 | 1 | 2 |
| q048 | spicy lemon harissa baked wings | Baked Lemon-Pepper-Harissa Wings | 1 | 1 | 2 |
| q055 | blueberry oatmeal breakfast | Blueberry Oatmeal | 1 | 1 | 3 |
| q056 | easy mac and cheese with pasta shells | Fancy-But-Easy Mac N' Cheese | 5 | 1 | 5 |
| q057 | grilled chicken veggies with pesto marinade | Grilled Pesto Chicken Kabobs | 2 | 1 | 2 |

47 more, not listed.

### sentence (56)

| Query id | Query | Recipe | dense | fusion | hybrid |
|---|---|---|---:|---:|---:|
| q007 | creamy crawfish soup with vegetables | Louisiana Crawfish Bisque | 1 | 2 | 4 |
| q010 | garlic roasted kale | Easy Garlic Kale | 1 | 2 | 3 |
| q017 | japanese banana custard cold snack | Japanese Banana Rice Pudding | 1 | 1 | 3 |
| q018 | rich brie and garlic wine dip | Matty's Brie Cheese Fondue | 2 | 8 | 11 |
| q038 | smoked bacon collard greens southern style | Easy Collard Greens | 3 | 5 | 7 |
| q048 | spicy lemon harissa baked wings | Baked Lemon-Pepper-Harissa Wings | 1 | 1 | 2 |
| q055 | blueberry oatmeal breakfast | Blueberry Oatmeal | 1 | 1 | 3 |
| q056 | easy mac and cheese with pasta shells | Fancy-But-Easy Mac N' Cheese | 9 | 1 | 4 |
| q063 | creamy oatmeal raisin cookies with spices | Grandma's Oatmeal Raisin Cookies | 1 | 1 | 3 |
| q066 | moist white cake with sour cream | Wedding Cake | 1 | 3 | 6 |

46 more, not listed.


## rerank_help: Reranking ranked the Recipe higher than the Fusion baseline

### fixed (82)

| Query id | Query | Recipe | dense | fusion | hybrid |
|---|---|---|---:|---:|---:|
| q002 | creamy tomato based dressing with vinegar | Dorothy Lynch® Style Salad Dressing | 4 | 15 | 6 |
| q005 | chocolate cupcakes with cherry cream cheese filling | PHILLY Blackforest Stuffed Cupcakes | - | 7 | 4 |
| q006 | chicken breast with green olives | Chicken and Olives | 2 | 8 | 1 |
| q009 | easy chicken in white wine sauce | Easy After Work Chicken Francaise | 2 | 4 | 1 |
| q010 | garlic roasted kale | Easy Garlic Kale | 1 | 2 | 1 |
| q011 | strawberry infused syrup for drinks | Strawberry Soda Syrup | 1 | 3 | 1 |
| q012 | yellow split pea soup with curry powder | Vegan Split Pea Soup II | - | 4 | 2 |
| q019 | apple and nutmeg fried bites | Apple Fritters I | - | 12 | 3 |
| q035 | quinoa vegetable stir fry | Quinoa with Veggies | 8 | 15 | 8 |
| q037 | baked salmon with maple mustard and nuts | Easy Pistachio-Crusted Salmon | - | 10 | 5 |

72 more, not listed.

### semantic (72)

| Query id | Query | Recipe | dense | fusion | hybrid |
|---|---|---|---:|---:|---:|
| q002 | creamy tomato based dressing with vinegar | Dorothy Lynch® Style Salad Dressing | 3 | 14 | 5 |
| q005 | chocolate cupcakes with cherry cream cheese filling | PHILLY Blackforest Stuffed Cupcakes | 20 | 5 | 4 |
| q006 | chicken breast with green olives | Chicken and Olives | 1 | 11 | 1 |
| q011 | strawberry infused syrup for drinks | Strawberry Soda Syrup | 1 | 2 | 1 |
| q012 | yellow split pea soup with curry powder | Vegan Split Pea Soup II | - | 4 | 2 |
| q018 | rich brie and garlic wine dip | Matty's Brie Cheese Fondue | 2 | 9 | 8 |
| q019 | apple and nutmeg fried bites | Apple Fritters I | 14 | 14 | 1 |
| q029 | creamy soy ginger pasta with beef and veggies | Asian Pasta Salad with Beef, Broccoli and Bean Sprouts | - | 2 | 1 |
| q035 | quinoa vegetable stir fry | Quinoa with Veggies | 9 | 8 | 7 |
| q037 | baked salmon with maple mustard and nuts | Easy Pistachio-Crusted Salmon | - | 7 | 4 |

62 more, not listed.

### sentence (89)

| Query id | Query | Recipe | dense | fusion | hybrid |
|---|---|---|---:|---:|---:|
| q002 | creamy tomato based dressing with vinegar | Dorothy Lynch® Style Salad Dressing | 3 | 13 | 6 |
| q003 | mediterranean chicken hoagie with olives | Mediterranean Chicken Sandwich | - | 13 | 1 |
| q005 | chocolate cupcakes with cherry cream cheese filling | PHILLY Blackforest Stuffed Cupcakes | 15 | 7 | 4 |
| q006 | chicken breast with green olives | Chicken and Olives | 1 | 9 | 1 |
| q009 | easy chicken in white wine sauce | Easy After Work Chicken Francaise | 2 | 5 | 1 |
| q011 | strawberry infused syrup for drinks | Strawberry Soda Syrup | 1 | 3 | 1 |
| q012 | yellow split pea soup with curry powder | Vegan Split Pea Soup II | 19 | 4 | 2 |
| q019 | apple and nutmeg fried bites | Apple Fritters I | - | 15 | 3 |
| q035 | quinoa vegetable stir fry | Quinoa with Veggies | 18 | - | 7 |
| q037 | baked salmon with maple mustard and nuts | Easy Pistachio-Crusted Salmon | - | 13 | 7 |

79 more, not listed.
