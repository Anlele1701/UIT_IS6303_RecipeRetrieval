# Báo cáo dữ liệu (quy tắc D1–D8)

Sinh tự động bởi `scripts/tag.py` lúc 2026-10-14T16:31:25 (commit `0df47d5`). Số liệu gốc ở `eval/corpus.json`. Không sửa tay file này.

| Mã | Quy tắc | Số liệu |
|---|---|---|
| D1 | Loại công thức trùng URL | 32.722 dòng CSV → bỏ 3 → 32.719 công thức |
| D2 | Bỏ cột dinh dưỡng rỗng > 99% | 13 cột, tỉ lệ rỗng thấp nhất 99,4% |
| D3 | Chuẩn hóa thời gian → phút | `total_time` null: 1.859 (rỗng ở nguồn 1.832, không đọc được 27) |
| D4 | Tách dòng nguyên liệu | 311.060 dòng: ok 96,5%, partial 3,5%, fail 0,0% |
| D5 | Ánh xạ sang nguyên liệu chuẩn | 1.982 canonical; 99,2% số dòng ánh xạ được; 9.633 dòng chứa nhiều nguyên liệu |
| D6 | Gắn nhóm dị ứng (FDA 9) | 27.788 công thức có ≥ 1 nhóm chắc chắn |
| D6b | Dòng ghi "X-free" (gluten-free, vegan…) không mang nhóm X | 129 dòng, 119 công thức |
| D7 | Cờ chế độ ăn | vegetarian 16.686 (51,0%), vegan 4.147 (12,7%); trong đó chỉ đạt khi bỏ qua thẻ "có thể": vegetarian 48, vegan 134 |
| D8 | Dòng `unknown` | 2.328 dòng; 2.075 công thức (6,3%) có ≥ 1 dòng unknown |

## Phân bố nhóm dị ứng (D6)

Cột "chắc chắn" là thẻ dùng để lọc cứng. Cột "chỉ có thể chứa" là công thức không bị lọc mà chỉ được cảnh báo.

| Nhóm | Chắc chắn | Tỉ lệ | Trong đó chỉ do thành phần ẩn | Chỉ "có thể chứa" |
|---|---:|---:|---:|---:|
| milk (sữa) | 19.583 | 59,9% | 398 | 444 |
| egg (trứng) | 11.438 | 35,0% | 2.592 | 0 |
| fish (cá) | 4.158 | 12,7% | 1.564 | 13 |
| crustacean_shellfish (giáp xác) | 2.158 | 6,6% | 30 | 175 |
| tree_nuts (hạt cây) | 3.506 | 10,7% | 279 | 241 |
| peanut (đậu phộng) | 811 | 2,5% | 10 | 201 |
| wheat (lúa mì) | 17.459 | 53,4% | 16.527 | 25 |
| soy (đậu nành) | 2.256 | 6,9% | 1.922 | 1.734 |
| sesame (mè) | 1.178 | 3,6% | 164 | 0 |

## 50 tên `unknown` phổ biến nhất (D8)

| Tên sau khi parse | Số dòng |
|---|---:|
| ®) | 19 |
| and half | 13 |
| teaspoon | 12 |
| breast half | 10 |
| sweet relish | 9 |
| fruit preserves | 9 |
| frozen french fries | 9 |
| fat-free | 9 |
| achiote powder | 9 |
| fleur de sel | 9 |
| greek salad dressing | 9 |
| sweet and sour mix | 8 |
| dried guajillo chiles | 8 |
| frozen limeade concentrate | 8 |
| mix | 8 |
| 1 cup | 8 |
| bran flakes cereal | 8 |
| tamarind juice | 8 |
| tostada shells | 8 |
| knorr fiesta sides | 8 |
| prepared stuffing | 8 |
| arrowroot powder | 8 |
| ragú old world style traditional sauce | 8 |
| balsamic glaze | 8 |
| bbq sauce | 7 |
| mochiko | 7 |
| any flavor fruit jam | 7 |
| liquid pectin | 7 |
| asafoetida powder | 7 |
| ground flaxseed | 7 |
| beau monde seasoning | 7 |
| pyure organic all purpose stevia blend | 7 |
| protein powder | 7 |
| baking spray | 7 |
| red cooking wine | 6 |
| mixed baby salad greens | 6 |
| green tea powder | 6 |
| tea bags | 6 |
| broccolini | 6 |
| 190 proof grain alcohol | 6 |
| kohlrabi bulbs | 6 |
| sweetened | 6 |
| annatto powder | 6 |
| blackened seasoning | 6 |
| powdered erythritol sweetener | 6 |
| mixed greens | 6 |
| blackening seasoning | 6 |
| celeriac | 6 |
| colored candy sprinkles | 6 |
| microwave popcorn | 6 |
