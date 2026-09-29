# Failure analysis

Ranks are over the top 20 unique Recipes; `-` means not found.

## Counts per Chunking strategy

| Strategy | Queries | sparse_win | dense_win | rerank_hurt | rerank_help |
|---|---:|---:|---:|---:|---:|
| fixed | 298 | 18 | 16 | 52 | 82 |
| semantic | 298 | 17 | 17 | 57 | 72 |
| sentence | 298 | 19 | 17 | 56 | 89 |

## Metrics by word overlap

High overlap: every content word of the query is in the Recipe's text (154 queries). Low: the rest (144 queries).

| Config | Strategy | Overlap | R@5 | R@10 | R@20 | MRR | nDCG@5 | nDCG@10 |
|---|---|---|---:|---:|---:|---:|---:|---:|
| sparse | fixed | high | 0.929 | 0.981 | 0.987 | 0.807 | 0.832 | 0.849 |
| sparse | fixed | low | 0.736 | 0.833 | 0.875 | 0.563 | 0.594 | 0.626 |
| sparse | semantic | high | 0.929 | 0.974 | 0.981 | 0.798 | 0.826 | 0.841 |
| sparse | semantic | low | 0.708 | 0.812 | 0.889 | 0.520 | 0.552 | 0.587 |
| sparse | sentence | high | 0.929 | 0.974 | 0.987 | 0.805 | 0.831 | 0.846 |
| sparse | sentence | low | 0.708 | 0.799 | 0.882 | 0.522 | 0.554 | 0.584 |
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

## sparse_win: Sparse found the Recipe in the top 10, Dense didn't

### fixed (18)

| Query id | Query | Recipe | sparse | dense | fusion | hybrid |
|---|---|---|---:|---:|---:|---:|
| q005 | chocolate cupcakes with cherry cream cheese filling | PHILLY Blackforest Stuffed Cupcakes | 3 | - | 7 | 4 |
| q012 | yellow split pea soup with curry powder | Vegan Split Pea Soup II | 1 | - | 4 | 2 |
| q019 | apple and nutmeg fried bites | Apple Fritters I | 6 | - | 12 | 3 |
| q037 | baked salmon with maple mustard and nuts | Easy Pistachio-Crusted Salmon | 2 | - | 10 | 5 |
| q039 | rich buttery pastry layers | Danish Pastry | 1 | - | 5 | 2 |
| q051 | flattened meatball with onions and herbs | German Hamburgers (Frikadellen) | 3 | - | 11 | 1 |
| q088 | cool cucumber avocado rolls | Homemade Vegetarian Sushi Rolls | 1 | - | 14 | 1 |
| q113 | maple syrup tart with raisins and nuts | Real Canadian Butter Tarts, eh? | 3 | - | 7 | 1 |
| q123 | kale and bean side dish | Kale and Adzuki Beans | 1 | - | 10 | 6 |
| q127 | spicy lime chicken and bean salad | Southwest Chicken Salad I | 5 | 14 | 9 | 1 |

8 more, not listed.

### semantic (17)

| Query id | Query | Recipe | sparse | dense | fusion | hybrid |
|---|---|---|---:|---:|---:|---:|
| q005 | chocolate cupcakes with cherry cream cheese filling | PHILLY Blackforest Stuffed Cupcakes | 3 | 20 | 5 | 4 |
| q012 | yellow split pea soup with curry powder | Vegan Split Pea Soup II | 1 | - | 4 | 2 |
| q019 | apple and nutmeg fried bites | Apple Fritters I | 7 | 14 | 14 | 1 |
| q029 | creamy soy ginger pasta with beef and veggies | Asian Pasta Salad with Beef, Broccoli and Bean Sprouts | 1 | - | 2 | 1 |
| q037 | baked salmon with maple mustard and nuts | Easy Pistachio-Crusted Salmon | 2 | - | 7 | 4 |
| q051 | flattened meatball with onions and herbs | German Hamburgers (Frikadellen) | 3 | - | 9 | 1 |
| q064 | smoked ham and kidney bean stew | Ham and Bean Soup I | 1 | 17 | 7 | 1 |
| q071 | sweet hush puppies for breakfast | Crispy Cornmeal Drop Doughnuts | 7 | - | 12 | 1 |
| q091 | garlic marinated carrots | Marinated Carrots Antipasto | 1 | - | 8 | 1 |
| q113 | maple syrup tart with raisins and nuts | Real Canadian Butter Tarts, eh? | 3 | - | 5 | 2 |

7 more, not listed.

### sentence (19)

| Query id | Query | Recipe | sparse | dense | fusion | hybrid |
|---|---|---|---:|---:|---:|---:|
| q003 | mediterranean chicken hoagie with olives | Mediterranean Chicken Sandwich | 1 | - | 13 | 1 |
| q005 | chocolate cupcakes with cherry cream cheese filling | PHILLY Blackforest Stuffed Cupcakes | 3 | 15 | 7 | 4 |
| q012 | yellow split pea soup with curry powder | Vegan Split Pea Soup II | 1 | 19 | 4 | 2 |
| q019 | apple and nutmeg fried bites | Apple Fritters I | 8 | - | 15 | 3 |
| q037 | baked salmon with maple mustard and nuts | Easy Pistachio-Crusted Salmon | 2 | - | 13 | 7 |
| q051 | flattened meatball with onions and herbs | German Hamburgers (Frikadellen) | 2 | - | 10 | 1 |
| q113 | maple syrup tart with raisins and nuts | Real Canadian Butter Tarts, eh? | 3 | - | 9 | 3 |
| q126 | crispy yuca fries with lime | Yuca Frita | 2 | - | 6 | 1 |
| q145 | crunchy apple grape bean salad | Holiday Apple Side Salad | 5 | 20 | 3 | 4 |
| q158 | egyptian hazelnut sesame dip | Dukkah | 1 | - | 2 | 1 |

9 more, not listed.


## dense_win: Dense found the Recipe in the top 10, Sparse didn't

### fixed (16)

| Query id | Query | Recipe | sparse | dense | fusion | hybrid |
|---|---|---|---:|---:|---:|---:|
| q002 | creamy tomato based dressing with vinegar | Dorothy Lynch® Style Salad Dressing | - | 4 | 15 | 6 |
| q006 | chicken breast with green olives | Chicken and Olives | - | 2 | 8 | 1 |
| q040 | grilled potato cold side dish | Grilled Potato Salad | - | 6 | 16 | 10 |
| q046 | creamy chicken artichoke spread | Chicken Artichoke Dip | - | 6 | 13 | 5 |
| q054 | fresh veggie and chicken wraps | Easy Spring Rolls | - | 2 | 3 | 1 |
| q081 | grilled pork chops herby lemony | Grilled Lemon Herb Pork Chops | - | 1 | 3 | 1 |
| q110 | sweet buttermilk butter bread | Buttermilk Honey Bread | 11 | 3 | 5 | 3 |
| q148 | fluffy marshmallow frosting with egg whites | Marshmallow Icing | - | 8 | 13 | 10 |
| q155 | creamy black bean and tomato stew | Black Bean and Tomato Soup | - | 1 | 3 | 1 |
| q156 | rich chocolate mayonnaise cake | Chocolate Mayo Cake | - | 1 | 2 | 2 |

6 more, not listed.

### semantic (17)

| Query id | Query | Recipe | sparse | dense | fusion | hybrid |
|---|---|---|---:|---:|---:|---:|
| q002 | creamy tomato based dressing with vinegar | Dorothy Lynch® Style Salad Dressing | - | 3 | 14 | 5 |
| q006 | chicken breast with green olives | Chicken and Olives | - | 1 | 11 | 1 |
| q040 | grilled potato cold side dish | Grilled Potato Salad | 19 | 5 | 6 | 9 |
| q044 | warm spiced wine with cloves | Gluehwein | - | 5 | 12 | 2 |
| q054 | fresh veggie and chicken wraps | Easy Spring Rolls | - | 2 | 3 | 1 |
| q081 | grilled pork chops herby lemony | Grilled Lemon Herb Pork Chops | - | 1 | 4 | 1 |
| q148 | fluffy marshmallow frosting with egg whites | Marshmallow Icing | 18 | 1 | 6 | 5 |
| q155 | creamy black bean and tomato stew | Black Bean and Tomato Soup | 20 | 2 | 4 | 2 |
| q156 | rich chocolate mayonnaise cake | Chocolate Mayo Cake | - | 1 | 2 | 2 |
| q185 | refreshing shrimp with lime and jalapeño | Authentic Mexican Shrimp Cocktail (Coctel de Camarones estilo Mexicano) | - | 10 | - | 5 |

7 more, not listed.

### sentence (17)

| Query id | Query | Recipe | sparse | dense | fusion | hybrid |
|---|---|---|---:|---:|---:|---:|
| q002 | creamy tomato based dressing with vinegar | Dorothy Lynch® Style Salad Dressing | - | 3 | 13 | 6 |
| q006 | chicken breast with green olives | Chicken and Olives | - | 1 | 9 | 1 |
| q046 | creamy chicken artichoke spread | Chicken Artichoke Dip | - | 10 | 19 | 5 |
| q054 | fresh veggie and chicken wraps | Easy Spring Rolls | - | 3 | 6 | 1 |
| q101 | creamy pumpkin soup with spices | Cream of Pumpkin Soup | 11 | 1 | 2 | 1 |
| q110 | sweet buttermilk butter bread | Buttermilk Honey Bread | 11 | 3 | 6 | 4 |
| q131 | spicy meat and cheese lasagna | Italian Lasagna | 17 | 3 | 12 | 5 |
| q148 | fluffy marshmallow frosting with egg whites | Marshmallow Icing | - | 1 | 4 | 8 |
| q155 | creamy black bean and tomato stew | Black Bean and Tomato Soup | - | 1 | 2 | 2 |
| q156 | rich chocolate mayonnaise cake | Chocolate Mayo Cake | - | 1 | 3 | 2 |

7 more, not listed.


## rerank_hurt: Reranking ranked the Recipe lower than the Fusion baseline

### fixed (52)

| Query id | Query | Recipe | sparse | dense | fusion | hybrid |
|---|---|---|---:|---:|---:|---:|
| q007 | creamy crawfish soup with vegetables | Louisiana Crawfish Bisque | 1 | 2 | 2 | 4 |
| q016 | baked beef and rice rolled tortillas | Baked Beef Taquitos | 1 | 1 | 1 | 2 |
| q017 | japanese banana custard cold snack | Japanese Banana Rice Pudding | 1 | 1 | 1 | 2 |
| q018 | rich brie and garlic wine dip | Matty's Brie Cheese Fondue | 4 | 2 | 6 | 9 |
| q021 | watermelon mint cooling dessert | Watermelon Mint Ice Cream | 2 | 1 | 1 | 3 |
| q026 | sliced tomatoes with basil and mozzarella | Tomato-Basil Salad | 1 | 1 | 1 | 3 |
| q028 | zucchini corn pepper cheese pan fry | Calabacitas | 1 | 2 | 1 | 2 |
| q036 | creamy potato casserole with sour cream | Easy Sour Cream Scalloped Potatoes | 2 | 1 | 1 | 2 |
| q038 | smoked bacon collard greens southern style | Easy Collard Greens | 2 | 4 | 2 | 7 |
| q042 | creamy onion dip with cheese | French Onion Dip | 5 | 1 | 1 | 2 |

42 more, not listed.

### semantic (57)

| Query id | Query | Recipe | sparse | dense | fusion | hybrid |
|---|---|---|---:|---:|---:|---:|
| q014 | cheesy breakfast casserole with spinach and sausage | Spinach, Sausage, and Egg Casserole | 4 | 1 | 1 | 2 |
| q017 | japanese banana custard cold snack | Japanese Banana Rice Pudding | 2 | 1 | 2 | 3 |
| q021 | watermelon mint cooling dessert | Watermelon Mint Ice Cream | 4 | 1 | 2 | 4 |
| q038 | smoked bacon collard greens southern style | Easy Collard Greens | 2 | 2 | 3 | 6 |
| q040 | grilled potato cold side dish | Grilled Potato Salad | 19 | 5 | 6 | 9 |
| q045 | pasta salad with olives and lemon | Orzo Pasta Salad | 1 | 3 | 1 | 2 |
| q048 | spicy lemon harissa baked wings | Baked Lemon-Pepper-Harissa Wings | 1 | 1 | 1 | 2 |
| q055 | blueberry oatmeal breakfast | Blueberry Oatmeal | 2 | 1 | 1 | 3 |
| q056 | easy mac and cheese with pasta shells | Fancy-But-Easy Mac N' Cheese | 4 | 5 | 1 | 5 |
| q057 | grilled chicken veggies with pesto marinade | Grilled Pesto Chicken Kabobs | 2 | 2 | 1 | 2 |

47 more, not listed.

### sentence (56)

| Query id | Query | Recipe | sparse | dense | fusion | hybrid |
|---|---|---|---:|---:|---:|---:|
| q007 | creamy crawfish soup with vegetables | Louisiana Crawfish Bisque | 1 | 1 | 2 | 4 |
| q010 | garlic roasted kale | Easy Garlic Kale | 5 | 1 | 2 | 3 |
| q017 | japanese banana custard cold snack | Japanese Banana Rice Pudding | 2 | 1 | 1 | 3 |
| q018 | rich brie and garlic wine dip | Matty's Brie Cheese Fondue | 4 | 2 | 8 | 11 |
| q038 | smoked bacon collard greens southern style | Easy Collard Greens | 2 | 3 | 5 | 7 |
| q048 | spicy lemon harissa baked wings | Baked Lemon-Pepper-Harissa Wings | 1 | 1 | 1 | 2 |
| q055 | blueberry oatmeal breakfast | Blueberry Oatmeal | 3 | 1 | 1 | 3 |
| q056 | easy mac and cheese with pasta shells | Fancy-But-Easy Mac N' Cheese | 7 | 9 | 1 | 4 |
| q063 | creamy oatmeal raisin cookies with spices | Grandma's Oatmeal Raisin Cookies | 1 | 1 | 1 | 3 |
| q066 | moist white cake with sour cream | Wedding Cake | 8 | 1 | 3 | 6 |

46 more, not listed.


## rerank_help: Reranking ranked the Recipe higher than the Fusion baseline

### fixed (82)

| Query id | Query | Recipe | sparse | dense | fusion | hybrid |
|---|---|---|---:|---:|---:|---:|
| q002 | creamy tomato based dressing with vinegar | Dorothy Lynch® Style Salad Dressing | - | 4 | 15 | 6 |
| q005 | chocolate cupcakes with cherry cream cheese filling | PHILLY Blackforest Stuffed Cupcakes | 3 | - | 7 | 4 |
| q006 | chicken breast with green olives | Chicken and Olives | - | 2 | 8 | 1 |
| q009 | easy chicken in white wine sauce | Easy After Work Chicken Francaise | 1 | 2 | 4 | 1 |
| q010 | garlic roasted kale | Easy Garlic Kale | 6 | 1 | 2 | 1 |
| q011 | strawberry infused syrup for drinks | Strawberry Soda Syrup | 8 | 1 | 3 | 1 |
| q012 | yellow split pea soup with curry powder | Vegan Split Pea Soup II | 1 | - | 4 | 2 |
| q019 | apple and nutmeg fried bites | Apple Fritters I | 6 | - | 12 | 3 |
| q035 | quinoa vegetable stir fry | Quinoa with Veggies | 4 | 8 | 15 | 8 |
| q037 | baked salmon with maple mustard and nuts | Easy Pistachio-Crusted Salmon | 2 | - | 10 | 5 |

72 more, not listed.

### semantic (72)

| Query id | Query | Recipe | sparse | dense | fusion | hybrid |
|---|---|---|---:|---:|---:|---:|
| q002 | creamy tomato based dressing with vinegar | Dorothy Lynch® Style Salad Dressing | - | 3 | 14 | 5 |
| q005 | chocolate cupcakes with cherry cream cheese filling | PHILLY Blackforest Stuffed Cupcakes | 3 | 20 | 5 | 4 |
| q006 | chicken breast with green olives | Chicken and Olives | - | 1 | 11 | 1 |
| q011 | strawberry infused syrup for drinks | Strawberry Soda Syrup | 10 | 1 | 2 | 1 |
| q012 | yellow split pea soup with curry powder | Vegan Split Pea Soup II | 1 | - | 4 | 2 |
| q018 | rich brie and garlic wine dip | Matty's Brie Cheese Fondue | 4 | 2 | 9 | 8 |
| q019 | apple and nutmeg fried bites | Apple Fritters I | 7 | 14 | 14 | 1 |
| q029 | creamy soy ginger pasta with beef and veggies | Asian Pasta Salad with Beef, Broccoli and Bean Sprouts | 1 | - | 2 | 1 |
| q035 | quinoa vegetable stir fry | Quinoa with Veggies | 8 | 9 | 8 | 7 |
| q037 | baked salmon with maple mustard and nuts | Easy Pistachio-Crusted Salmon | 2 | - | 7 | 4 |

62 more, not listed.

### sentence (89)

| Query id | Query | Recipe | sparse | dense | fusion | hybrid |
|---|---|---|---:|---:|---:|---:|
| q002 | creamy tomato based dressing with vinegar | Dorothy Lynch® Style Salad Dressing | - | 3 | 13 | 6 |
| q003 | mediterranean chicken hoagie with olives | Mediterranean Chicken Sandwich | 1 | - | 13 | 1 |
| q005 | chocolate cupcakes with cherry cream cheese filling | PHILLY Blackforest Stuffed Cupcakes | 3 | 15 | 7 | 4 |
| q006 | chicken breast with green olives | Chicken and Olives | - | 1 | 9 | 1 |
| q009 | easy chicken in white wine sauce | Easy After Work Chicken Francaise | 1 | 2 | 5 | 1 |
| q011 | strawberry infused syrup for drinks | Strawberry Soda Syrup | 8 | 1 | 3 | 1 |
| q012 | yellow split pea soup with curry powder | Vegan Split Pea Soup II | 1 | 19 | 4 | 2 |
| q019 | apple and nutmeg fried bites | Apple Fritters I | 8 | - | 15 | 3 |
| q035 | quinoa vegetable stir fry | Quinoa with Veggies | 13 | 18 | - | 7 |
| q037 | baked salmon with maple mustard and nuts | Easy Pistachio-Crusted Salmon | 2 | - | 13 | 7 |

79 more, not listed.
