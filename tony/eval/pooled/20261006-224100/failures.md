# Failure analysis

Ranks are over the top 20 unique Recipes; `-` means not found.

## Counts per Chunking strategy

| Strategy | Queries | rerank_hurt | rerank_help |
|---|---:|---:|---:|
| fixed | 298 | 18 | 105 |
| semantic | 298 | 13 | 99 |
| sentence | 298 | 19 | 108 |

## Metrics by word overlap

High overlap: every content word of the query is in the Recipe's text (154 queries). Low: the rest (144 queries).

| Config | Strategy | Overlap | R@5 | R@10 | R@20 | MRR | nDCG@5 | nDCG@10 |
|---|---|---|---:|---:|---:|---:|---:|---:|
| fusion | fixed | high | 0.929 | 0.974 | 0.994 | 0.800 | 0.827 | 0.841 |
| fusion | fixed | low | 0.819 | 0.868 | 0.931 | 0.622 | 0.663 | 0.679 |
| fusion | semantic | high | 0.929 | 0.981 | 0.994 | 0.822 | 0.842 | 0.859 |
| fusion | semantic | low | 0.826 | 0.896 | 0.924 | 0.621 | 0.664 | 0.687 |
| fusion | sentence | high | 0.922 | 0.961 | 0.987 | 0.791 | 0.818 | 0.832 |
| fusion | sentence | low | 0.778 | 0.861 | 0.917 | 0.609 | 0.640 | 0.667 |
| hybrid | fixed | high | 1.000 | 1.000 | 1.000 | 0.955 | 0.966 | 0.966 |
| hybrid | fixed | low | 0.938 | 0.951 | 0.958 | 0.830 | 0.856 | 0.860 |
| hybrid | semantic | high | 0.987 | 1.000 | 1.000 | 0.938 | 0.949 | 0.953 |
| hybrid | semantic | low | 0.944 | 0.951 | 0.951 | 0.850 | 0.873 | 0.875 |
| hybrid | sentence | high | 1.000 | 1.000 | 1.000 | 0.938 | 0.954 | 0.954 |
| hybrid | sentence | low | 0.931 | 0.951 | 0.958 | 0.835 | 0.857 | 0.864 |

## rerank_hurt: Reranking ranked the Recipe lower than the Fusion baseline

### fixed (18)

| Query id | Query | Recipe | fusion | hybrid |
|---|---|---|---:|---:|
| q028 | zucchini corn pepper cheese pan fry | Calabacitas | 1 | 2 |
| q051 | flattened meatball with onions and herbs | German Hamburgers (Frikadellen) | 11 | 18 |
| q059 | wild blueberry pie with cinnamon | Mystery Ingredient Wild Blueberry Pie | 1 | 2 |
| q063 | creamy oatmeal raisin cookies with spices | Grandma's Oatmeal Raisin Cookies | 1 | 3 |
| q074 | rich coffee cream with whiskey | Homemade Irish (Whiskey) Cream | 1 | 2 |
| q087 | cheesy kale baked dish | Cheesy Kale Quiche | 2 | 3 |
| q122 | spiced chickpea stew with kale | Moroccan Chickpea Stew | 1 | 2 |
| q132 | sweet tomato pepper stew | Jersey Fresh Stewed Tomatoes | 2 | 3 |
| q161 | creamy crab and corn soup | Crab and Sweet Corn Soup | 1 | 3 |
| q163 | creamy crawfish appetizer with spices | Easy Cheesy Crawfish Dip | 1 | 3 |

8 more, not listed.

### semantic (13)

| Query id | Query | Recipe | fusion | hybrid |
|---|---|---|---:|---:|
| q020 | beefy ricotta lasagna rolls | Lasagna Roll Ups II | 1 | 3 |
| q028 | zucchini corn pepper cheese pan fry | Calabacitas | 1 | 3 |
| q056 | easy mac and cheese with pasta shells | Fancy-But-Easy Mac N' Cheese | 1 | 3 |
| q059 | wild blueberry pie with cinnamon | Mystery Ingredient Wild Blueberry Pie | 1 | 2 |
| q063 | creamy oatmeal raisin cookies with spices | Grandma's Oatmeal Raisin Cookies | 1 | 5 |
| q074 | rich coffee cream with whiskey | Homemade Irish (Whiskey) Cream | 1 | 2 |
| q161 | creamy crab and corn soup | Crab and Sweet Corn Soup | 1 | 3 |
| q201 | spicy pinto beans with onions | Fab-u-lous Refried Beans! | 1 | 2 |
| q257 | gluten-free pastry with raspberry filling | Gluten Free Danish | 5 | 6 |
| q264 | pan-fried tilapia with salsa | Kelly's Pan Fried Tilapia | 1 | 2 |

3 more, not listed.

### sentence (19)

| Query id | Query | Recipe | fusion | hybrid |
|---|---|---|---:|---:|
| q020 | beefy ricotta lasagna rolls | Lasagna Roll Ups II | 1 | 2 |
| q025 | spicy roasted cauliflower sheet pan meal | Easy Sheet Pan Roasted Cauliflower with Curry | 1 | 2 |
| q028 | zucchini corn pepper cheese pan fry | Calabacitas | 1 | 2 |
| q051 | flattened meatball with onions and herbs | German Hamburgers (Frikadellen) | 10 | 20 |
| q056 | easy mac and cheese with pasta shells | Fancy-But-Easy Mac N' Cheese | 1 | 2 |
| q059 | wild blueberry pie with cinnamon | Mystery Ingredient Wild Blueberry Pie | 1 | 2 |
| q063 | creamy oatmeal raisin cookies with spices | Grandma's Oatmeal Raisin Cookies | 1 | 2 |
| q128 | hard boiled eggs wrapped in sausage | Donna's Nest Eggs | 1 | 2 |
| q196 | no-yeast pizza base quick | No-Yeast Pizza Crust | 1 | 2 |
| q199 | fresh corn and avocado dip for chips | Corn and Avocado Salsa | 7 | 9 |

9 more, not listed.


## rerank_help: Reranking ranked the Recipe higher than the Fusion baseline

### fixed (105)

| Query id | Query | Recipe | fusion | hybrid |
|---|---|---|---:|---:|
| q002 | creamy tomato based dressing with vinegar | Dorothy Lynch® Style Salad Dressing | 15 | 2 |
| q005 | chocolate cupcakes with cherry cream cheese filling | PHILLY Blackforest Stuffed Cupcakes | 7 | 2 |
| q006 | chicken breast with green olives | Chicken and Olives | 8 | 1 |
| q007 | creamy crawfish soup with vegetables | Louisiana Crawfish Bisque | 2 | 1 |
| q009 | easy chicken in white wine sauce | Easy After Work Chicken Francaise | 4 | 1 |
| q010 | garlic roasted kale | Easy Garlic Kale | 2 | 1 |
| q011 | strawberry infused syrup for drinks | Strawberry Soda Syrup | 3 | 1 |
| q012 | yellow split pea soup with curry powder | Vegan Split Pea Soup II | 4 | 1 |
| q018 | rich brie and garlic wine dip | Matty's Brie Cheese Fondue | 6 | 2 |
| q019 | apple and nutmeg fried bites | Apple Fritters I | 12 | 1 |

95 more, not listed.

### semantic (99)

| Query id | Query | Recipe | fusion | hybrid |
|---|---|---|---:|---:|
| q002 | creamy tomato based dressing with vinegar | Dorothy Lynch® Style Salad Dressing | 14 | 2 |
| q005 | chocolate cupcakes with cherry cream cheese filling | PHILLY Blackforest Stuffed Cupcakes | 5 | 2 |
| q006 | chicken breast with green olives | Chicken and Olives | 11 | 1 |
| q007 | creamy crawfish soup with vegetables | Louisiana Crawfish Bisque | 2 | 1 |
| q010 | garlic roasted kale | Easy Garlic Kale | 2 | 1 |
| q011 | strawberry infused syrup for drinks | Strawberry Soda Syrup | 2 | 1 |
| q012 | yellow split pea soup with curry powder | Vegan Split Pea Soup II | 4 | 1 |
| q017 | japanese banana custard cold snack | Japanese Banana Rice Pudding | 2 | 1 |
| q018 | rich brie and garlic wine dip | Matty's Brie Cheese Fondue | 9 | 1 |
| q019 | apple and nutmeg fried bites | Apple Fritters I | 14 | 2 |

89 more, not listed.

### sentence (108)

| Query id | Query | Recipe | fusion | hybrid |
|---|---|---|---:|---:|
| q002 | creamy tomato based dressing with vinegar | Dorothy Lynch® Style Salad Dressing | 13 | 2 |
| q003 | mediterranean chicken hoagie with olives | Mediterranean Chicken Sandwich | 13 | 1 |
| q005 | chocolate cupcakes with cherry cream cheese filling | PHILLY Blackforest Stuffed Cupcakes | 7 | 2 |
| q006 | chicken breast with green olives | Chicken and Olives | 9 | 1 |
| q007 | creamy crawfish soup with vegetables | Louisiana Crawfish Bisque | 2 | 1 |
| q009 | easy chicken in white wine sauce | Easy After Work Chicken Francaise | 5 | 1 |
| q010 | garlic roasted kale | Easy Garlic Kale | 2 | 1 |
| q011 | strawberry infused syrup for drinks | Strawberry Soda Syrup | 3 | 1 |
| q012 | yellow split pea soup with curry powder | Vegan Split Pea Soup II | 4 | 2 |
| q018 | rich brie and garlic wine dip | Matty's Brie Cheese Fondue | 8 | 1 |

98 more, not listed.
