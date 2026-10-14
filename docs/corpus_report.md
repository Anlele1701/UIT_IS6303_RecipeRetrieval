# Báo cáo dữ liệu (quy tắc D1–D8)

Sinh tự động bởi `scripts/tag.py` lúc 2026-10-14T14:47:02 (commit `ffbb17e`). Số liệu gốc ở `eval/corpus.json`. Không sửa tay file này.

| Mã | Quy tắc | Số liệu |
|---|---|---|
| D1 | Loại công thức trùng URL | 32.722 dòng CSV → bỏ 3 → 32.719 công thức |
| D2 | Bỏ cột dinh dưỡng rỗng > 99% | 13 cột, tỉ lệ rỗng thấp nhất 99,4% |
| D3 | Chuẩn hóa thời gian → phút | `total_time` null: 1.859 (rỗng ở nguồn 1.832, không đọc được 27) |
| D4 | Tách dòng nguyên liệu | 311.060 dòng: ok 96,5%, partial 3,5%, fail 0,0% |
| D5 | Ánh xạ sang nguyên liệu chuẩn | 1.984 canonical; 99,2% số dòng ánh xạ được; 9.593 dòng chứa nhiều nguyên liệu |
| D6 | Gắn nhóm dị ứng (FDA 9) | 27.877 công thức có ≥ 1 nhóm |
| D7 | Cờ chế độ ăn | vegetarian 16.608 (50,8%), vegan 3.967 (12,1%) |
| D8 | Dòng `unknown` | 2.388 dòng; 2.129 công thức (6,5%) có ≥ 1 dòng unknown |

## Phân bố nhóm dị ứng (D6)

| Nhóm | Số công thức | Tỉ lệ | Chỉ do thành phần ẩn |
|---|---:|---:|---:|
| milk (sữa) | 20.059 | 61,3% | 859 |
| egg (trứng) | 11.439 | 35,0% | 2.593 |
| fish (cá) | 4.178 | 12,8% | 1.585 |
| crustacean_shellfish (giáp xác) | 2.333 | 7,1% | 205 |
| tree_nuts (hạt cây) | 3.747 | 11,5% | 302 |
| peanut (đậu phộng) | 1.012 | 3,1% | 211 |
| wheat (lúa mì) | 17.531 | 53,6% | 16.599 |
| soy (đậu nành) | 3.990 | 12,2% | 3.656 |
| sesame (mè) | 1.178 | 3,6% | 164 |

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
