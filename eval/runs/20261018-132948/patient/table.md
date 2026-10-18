# MV4 – Kết quả nhánh hồ sơ bệnh nhân

Sinh tự động bởi `scripts/eval_patient.py score`. Không sửa tay.

## Toàn bộ

### Trích ràng buộc (so với đáp án gold.jsonl)

| Đầu vào | Preset | Dị ứng P/R | Dị ứng bỏ sót (ca / BN) | Bệnh F1 | Thuốc F1 |
|---|---|---|---|---|---|
| coded | P-Direct | 100.0% / 100.0% | 0 / 0 | 100.0% | 100.0% |
| coded | P-Vector | 29.0% / 14.3% | 54 / 11 | 76.8% | 87.9% |
| coded | P-Vectorless | 100.0% / 100.0% | 0 / 0 | 100.0% | 100.0% |
| coded | P-Vectorless-Fixed | 100.0% / 34.9% | 41 / 12 | 40.4% | 34.2% |
| coded | S-Profile | – | 0 / 0 | – | – |
| narrative | P-Vector | 100.0% / 17.5% | 52 / 12 | 16.8% | 43.0% |
| narrative | P-Vectorless | 81.8% / 85.7% | 9 / 3 | 48.8% | 78.2% |
| narrative | P-Vectorless-Fixed | 81.8% / 14.3% | 54 / 12 | 9.3% | 0.0% |
| narrative | S-Profile | – | 0 / 0 | – | – |

### Đầu cuối (top 5) và chọn nút

| Đầu vào | Preset | Câu | Safe@5 dị ứng (adj) | CVR@5 dị ứng raw / adj | Safe@5 dinh dưỡng | CVR@5 dinh dưỡng | Safe@5 hội thoại (adj) | Chọn nút đúng | Trả lời do code |
|---|---|---|---|---|---|---|---|---|---|
| coded | P-Direct | 300 | 99% (73/74) [93–100] | 5.7% / 0.3% | 100% (200/200) [98–100] | 0.0% | 86% (86/100) [78–91] | 0% (0/100) [0–4] | 14% (42/300) [11–18] |
| coded | P-Vector | 300 | 82% (61/74) [72–89] | 10.5% / 5.9% | 98% (195/200) [94–99] | 1.4% | 84% (84/100) [76–90] | 84% (84/100) [76–90] | 8% (23/300) [5–11] |
| coded | P-Vectorless | 300 | 99% (73/74) [93–100] | 5.7% / 0.3% | 100% (200/200) [98–100] | 0.0% | 86% (86/100) [78–91] | 78% (78/100) [69–85] | 8% (24/300) [5–12] |
| coded | P-Vectorless-Fixed | 300 | 91% (67/74) [82–95] | 8.4% / 3.5% | 96% (192/200) [92–98] | 1.6% | 84% (84/100) [76–90] | 87% (87/100) [79–92] | 8% (25/300) [6–12] |
| coded | S-Profile | 300 | 81% (60/74) [71–88] | 11.4% / 6.2% | 36% (72/200) [30–43] | 29.0% | 80% (80/100) [71–87] | – | 0% (0/300) [0–1] |
| narrative | P-Vector | 300 | 86% (64/74) [77–92] | 8.6% / 4.1% | 94% (189/200) [90–97] | 2.2% | 83% (83/100) [74–89] | – | 9% (26/300) [6–12] |
| narrative | P-Vectorless | 300 | 97% (72/74) [91–99] | 5.7% / 0.5% | 100% (200/200) [98–100] | 0.0% | 86% (86/100) [78–91] | – | 12% (35/300) [9–16] |
| narrative | P-Vectorless-Fixed | 300 | 89% (66/74) [80–94] | 9.2% / 4.3% | 94% (189/200) [90–97] | 2.4% | 82% (82/100) [73–88] | – | 11% (33/300) [8–15] |
| narrative | S-Profile | 300 | 81% (60/74) [71–88] | 11.4% / 6.2% | 36% (72/200) [30–43] | 29.0% | 80% (80/100) [71–87] | – | 0% (0/300) [0–1] |

### Chi phí V1–V3 (trung bình mỗi lượt; lượt đầu của bệnh nhân / các lượt sau)

| Đầu vào | Preset | Lời gọi LLM | Ký tự đọc | V1 ms | V2 ms | V3 ms | Tổng ms | [H:] hợp lệ / đã đọc / tổng |
|---|---|---|---|---|---|---|---|---|
| coded | P-Direct | 0.0 / 0.0 | 0.0 / 0.0 | 2.9 / 2.4 | 0.0 / 0.0 | 4.9 / 0.6 | 9667.6 / 8630.6 | 340 / 218 / 340 |
| coded | P-Vector | 1.0 / 1.0 | 2401.7 / 2400.1 | 3.4 / 2.7 | 153.0 / 13.9 | 2425.2 / 4849.5 | 11008.6 / 10958.7 | 492 / 334 / 492 |
| coded | P-Vectorless | 0.0 / 0.5 | 0.0 / 0.0 | 3.0 / 2.6 | 46.5 / 523.4 | 4.8 / 0.6 | 8042.8 / 6281.0 | 405 / 285 / 405 |
| coded | P-Vectorless-Fixed | 1.0 / 1.0 | 0.0 / 0.0 | 3.3 / 2.6 | 4395.5 / 957.0 | 0.1 / 0.1 | 8988.3 / 6500.6 | 416 / 256 / 416 |
| coded | S-Profile | – / – | – / – | – / – | – / – | – / – | 5150.0 / 5485.3 | 0 / 0 / 0 |
| narrative | P-Vector | 1.0 / 1.0 | 3635.8 / 3544.6 | 41.1 / 38.5 | 1463.8 / 934.4 | 2737.8 / 13076.0 | 14461.1 / 21219.6 | 480 / 315 / 480 |
| narrative | P-Vectorless | 2.1 / 2.6 | 19533.6 / 19533.6 | 40.4 / 37.6 | 35.6 / 167.4 | 16099.2 / 14.1 | 26685.9 / 7258.8 | 604 / 459 / 604 |
| narrative | P-Vectorless-Fixed | 1.0 / 1.7 | 26.2 / 2100.8 | 43.3 / 40.7 | 3583.7 / 355.5 | 53.4 / 6233.5 | 9193.3 / 11303.8 | 552 / 344 / 552 |
| narrative | S-Profile | – / – | – / – | – / – | – / – | – / – | 5150.0 / 5485.3 | 0 / 0 / 0 |

### So sánh ghép cặp theo bệnh nhân (bootstrap 10.000 lần, Wilcoxon; Holm trong từng họ)

| Họ | So sánh | Số BN | Chênh lệch [KTC 95%] | p bootstrap (Holm) | p Wilcoxon (Holm) |
|---|---|---|---|---|---|
| coded|safe_allergen_adj | P-Vectorless - P-Direct | 37 | +0.000 [+0.000, +0.000] | 1.000 (1.000) | 1.000 (1.000) |
| coded|safe_allergen_adj | P-Vectorless - P-Vectorless-Fixed | 37 | +0.081 [+0.027, +0.162] | 0.008 (0.017) | 0.151 (0.302) |
| coded|safe_allergen_adj | P-Vectorless - P-Vector | 37 | +0.162 [+0.068, +0.284] | 0.000 (0.001) | 0.054 (0.163) |
| coded|safe_allergen_adj | P-Vectorless - S-Profile | 37 | +0.176 [+0.081, +0.297] | 0.000 (0.000) | 0.018 (0.072) |
| narrative|safe_allergen_adj | P-Vectorless - P-Vectorless-Fixed | 37 | +0.081 [+0.000, +0.176] | 0.066 (0.066) | 0.254 (0.302) |
| narrative|safe_allergen_adj | P-Vectorless - P-Vector | 37 | +0.108 [+0.027, +0.203] | 0.006 (0.011) | 0.151 (0.302) |
| narrative|safe_allergen_adj | P-Vectorless - S-Profile | 37 | +0.162 [+0.068, +0.270] | 0.000 (0.000) | 0.032 (0.095) |
| coded-narrative|safe_allergen_adj | P-Vectorless | 37 | +0.014 [+0.000, +0.041] | 0.722 (1.000) | 0.752 (1.000) |
| coded-narrative|safe_allergen_adj | P-Vectorless-Fixed | 37 | +0.014 [-0.027, +0.068] | 0.786 (1.000) | 0.763 (1.000) |
| coded-narrative|safe_allergen_adj | P-Vector | 37 | -0.041 [-0.095, +0.000] | 0.083 (0.333) | 0.366 (1.000) |
| coded-narrative|safe_allergen_adj | S-Profile | 37 | +0.000 [+0.000, +0.000] | 1.000 (1.000) | 1.000 (1.000) |
| coded|safe_nutrition | P-Vectorless - P-Direct | 100 | +0.000 [+0.000, +0.000] | 1.000 (1.000) | 1.000 (1.000) |
| coded|safe_nutrition | P-Vectorless - P-Vectorless-Fixed | 100 | +0.040 [+0.010, +0.075] | 0.005 (0.015) | 0.259 (0.778) |
| coded|safe_nutrition | P-Vectorless - P-Vector | 100 | +0.025 [+0.005, +0.055] | 0.031 (0.062) | 0.444 (0.887) |
| coded|safe_nutrition | P-Vectorless - S-Profile | 100 | +0.640 [+0.575, +0.705] | 0.000 (0.000) | 0.000 (0.000) |
| narrative|safe_nutrition | P-Vectorless - P-Vectorless-Fixed | 100 | +0.055 [+0.020, +0.100] | 0.000 (0.000) | 0.140 (0.280) |
| narrative|safe_nutrition | P-Vectorless - P-Vector | 100 | +0.055 [+0.020, +0.100] | 0.000 (0.000) | 0.140 (0.280) |
| narrative|safe_nutrition | P-Vectorless - S-Profile | 100 | +0.640 [+0.575, +0.705] | 0.000 (0.000) | 0.000 (0.000) |
| coded-narrative|safe_nutrition | P-Vectorless | 100 | +0.000 [+0.000, +0.000] | 1.000 (1.000) | 1.000 (1.000) |
| coded-narrative|safe_nutrition | P-Vectorless-Fixed | 100 | +0.015 [+0.000, +0.035] | 0.090 (0.270) | 0.562 (1.000) |
| coded-narrative|safe_nutrition | P-Vector | 100 | +0.030 [+0.005, +0.060] | 0.034 (0.135) | 0.268 (1.000) |
| coded-narrative|safe_nutrition | S-Profile | 100 | +0.000 [+0.000, +0.000] | 1.000 (1.000) | 1.000 (1.000) |
| coded|safe_dialogue_adj | P-Vectorless - P-Direct | 100 | +0.000 [+0.000, +0.000] | 1.000 (1.000) | 1.000 (1.000) |
| coded|safe_dialogue_adj | P-Vectorless - P-Vectorless-Fixed | 100 | +0.020 [+0.000, +0.050] | 0.257 (0.772) | 0.696 (1.000) |
| coded|safe_dialogue_adj | P-Vectorless - P-Vector | 100 | +0.020 [+0.000, +0.050] | 0.257 (0.772) | 0.696 (1.000) |
| coded|safe_dialogue_adj | P-Vectorless - S-Profile | 100 | +0.060 [-0.010, +0.130] | 0.126 (0.504) | 0.293 (1.000) |
| narrative|safe_dialogue_adj | P-Vectorless - P-Vectorless-Fixed | 100 | +0.040 [+0.010, +0.080] | 0.030 (0.089) | 0.444 (0.887) |
| narrative|safe_dialogue_adj | P-Vectorless - P-Vector | 100 | +0.030 [+0.000, +0.070] | 0.095 (0.190) | 0.562 (0.887) |
| narrative|safe_dialogue_adj | P-Vectorless - S-Profile | 100 | +0.060 [-0.010, +0.130] | 0.126 (0.190) | 0.293 (0.880) |
| coded-narrative|safe_dialogue_adj | P-Vectorless | 100 | +0.000 [+0.000, +0.000] | 1.000 (1.000) | 1.000 (1.000) |
| coded-narrative|safe_dialogue_adj | P-Vectorless-Fixed | 100 | +0.020 [+0.000, +0.050] | 0.270 (1.000) | 0.696 (1.000) |
| coded-narrative|safe_dialogue_adj | P-Vector | 100 | +0.010 [-0.020, +0.050] | 0.782 (1.000) | 0.847 (1.000) |
| coded-narrative|safe_dialogue_adj | S-Profile | 100 | +0.000 [+0.000, +0.000] | 1.000 (1.000) | 1.000 (1.000) |
| coded|allergy_recall | P-Vectorless - P-Direct | 12 | +0.000 [+0.000, +0.000] | 1.000 (1.000) | 1.000 (1.000) |
| coded|allergy_recall | P-Vectorless - P-Vectorless-Fixed | 12 | +0.694 [+0.583, +0.806] | 0.000 (0.000) | 0.000 (0.001) |
| coded|allergy_recall | P-Vectorless - P-Vector | 12 | +0.824 [+0.620, +1.000] | 0.000 (0.000) | 0.001 (0.002) |
| narrative|allergy_recall | P-Vectorless - P-Vectorless-Fixed | 12 | +0.690 [+0.458, +0.894] | 0.000 (0.000) | 0.002 (0.004) |
| narrative|allergy_recall | P-Vectorless - P-Vector | 12 | +0.694 [+0.472, +0.889] | 0.000 (0.000) | 0.002 (0.004) |
| coded-narrative|allergy_recall | P-Vectorless | 12 | +0.208 [+0.000, +0.458] | 0.061 (0.122) | 0.250 (0.500) |
| coded-narrative|allergy_recall | P-Vectorless-Fixed | 12 | +0.204 [+0.111, +0.287] | 0.000 (0.000) | 0.008 (0.023) |
| coded-narrative|allergy_recall | P-Vector | 12 | +0.079 [-0.097, +0.306] | 0.483 (0.483) | 1.000 (1.000) |
| coded|node_hit | P-Vectorless - P-Direct | 100 | +0.780 [+0.700, +0.860] | 0.000 (0.000) | 0.000 (0.000) |
| coded|node_hit | P-Vectorless - P-Vectorless-Fixed | 100 | -0.090 [-0.160, -0.020] | 0.008 (0.016) | 0.112 (0.224) |
| coded|node_hit | P-Vectorless - P-Vector | 100 | -0.060 [-0.160, +0.040] | 0.280 (0.280) | 0.348 (0.348) |

## Độ nhạy: chỉ nguồn sample

### Trích ràng buộc (so với đáp án gold.jsonl)

| Đầu vào | Preset | Dị ứng P/R | Dị ứng bỏ sót (ca / BN) | Bệnh F1 | Thuốc F1 |
|---|---|---|---|---|---|
| coded | P-Direct | 100.0% / 100.0% | 0 / 0 | 100.0% | 100.0% |
| coded | P-Vector | 31.0% / 15.8% | 48 / 10 | 82.5% | 88.6% |
| coded | P-Vectorless | 100.0% / 100.0% | 0 / 0 | 100.0% | 100.0% |
| coded | P-Vectorless-Fixed | 100.0% / 31.6% | 39 / 11 | 37.1% | 38.0% |
| coded | S-Profile | – | 0 / 0 | – | – |
| narrative | P-Vector | 100.0% / 17.5% | 47 / 11 | 18.8% | 42.8% |
| narrative | P-Vectorless | 81.0% / 89.5% | 6 / 2 | 45.4% | 74.4% |
| narrative | P-Vectorless-Fixed | 87.5% / 12.3% | 50 / 11 | 7.8% | 0.0% |
| narrative | S-Profile | – | 0 / 0 | – | – |

### Đầu cuối (top 5) và chọn nút

| Đầu vào | Preset | Câu | Safe@5 dị ứng (adj) | CVR@5 dị ứng raw / adj | Safe@5 dinh dưỡng | CVR@5 dinh dưỡng | Safe@5 hội thoại (adj) | Chọn nút đúng | Trả lời do code |
|---|---|---|---|---|---|---|---|---|---|
| coded | P-Direct | 264 | 100% (52/52) [93–100] | 6.5% / 0.0% | 100% (176/176) [98–100] | 0.0% | 84% (74/88) [75–90] | 0% (0/88) [0–4] | 15% (39/264) [11–20] |
| coded | P-Vector | 264 | 79% (41/52) [66–88] | 13.1% / 7.7% | 99% (175/176) [97–100] | 0.6% | 84% (74/88) [75–90] | 85% (75/88) [76–91] | 8% (22/264) [6–12] |
| coded | P-Vectorless | 264 | 100% (52/52) [93–100] | 6.5% / 0.0% | 100% (176/176) [98–100] | 0.0% | 84% (74/88) [75–90] | 78% (69/88) [69–86] | 8% (20/264) [5–11] |
| coded | P-Vectorless-Fixed | 264 | 88% (46/52) [77–95] | 10.4% / 4.6% | 98% (172/176) [94–99] | 0.8% | 84% (74/88) [75–90] | 85% (75/88) [76–91] | 8% (21/264) [5–12] |
| coded | S-Profile | 264 | 75% (39/52) [62–85] | 14.6% / 8.5% | 36% (64/176) [30–44] | 28.9% | 80% (70/88) [70–87] | – | 0% (0/264) [0–1] |
| narrative | P-Vector | 264 | 83% (43/52) [70–91] | 11.2% / 5.4% | 98% (172/176) [94–99] | 0.9% | 83% (73/88) [74–89] | – | 8% (22/264) [6–12] |
| narrative | P-Vectorless | 264 | 98% (51/52) [90–100] | 6.9% / 0.4% | 100% (176/176) [98–100] | 0.0% | 84% (74/88) [75–90] | – | 13% (34/264) [9–17] |
| narrative | P-Vectorless-Fixed | 264 | 85% (44/52) [72–92] | 12.3% / 6.2% | 98% (172/176) [94–99] | 1.1% | 83% (73/88) [74–89] | – | 11% (29/264) [8–15] |
| narrative | S-Profile | 264 | 75% (39/52) [62–85] | 14.6% / 8.5% | 36% (64/176) [30–44] | 28.9% | 80% (70/88) [70–87] | – | 0% (0/264) [0–1] |

### Chi phí V1–V3 (trung bình mỗi lượt; lượt đầu của bệnh nhân / các lượt sau)

| Đầu vào | Preset | Lời gọi LLM | Ký tự đọc | V1 ms | V2 ms | V3 ms | Tổng ms | [H:] hợp lệ / đã đọc / tổng |
|---|---|---|---|---|---|---|---|---|
| coded | P-Direct | 0.0 / 0.0 | 0.0 / 0.0 | 2.3 / 1.9 | 0.0 / 0.0 | 4.4 / 0.6 | 9733.4 / 8553.1 | 297 / 178 / 297 |
| coded | P-Vector | 1.0 / 1.0 | 2354.1 / 2355.2 | 2.5 / 2.0 | 110.0 / 13.8 | 2094.4 / 4558.6 | 10433.7 / 10516.2 | 455 / 305 / 455 |
| coded | P-Vectorless | 0.0 / 0.5 | 0.0 / 0.0 | 2.4 / 1.9 | 52.8 / 508.0 | 4.2 / 0.6 | 7976.4 / 6125.8 | 333 / 217 / 333 |
| coded | P-Vectorless-Fixed | 1.0 / 1.0 | 0.0 / 0.0 | 2.5 / 2.0 | 4409.5 / 931.9 | 0.1 / 0.1 | 8895.3 / 6433.3 | 352 / 207 / 352 |
| coded | S-Profile | – / – | – / – | – / – | – / – | – / – | 5256.3 / 5475.0 | 0 / 0 / 0 |
| narrative | P-Vector | 1.0 / 1.0 | 3584.1 / 3518.4 | 24.1 / 23.9 | 1297.3 / 930.5 | 2594.5 / 13702.2 | 14167.6 / 21803.9 | 413 / 264 / 413 |
| narrative | P-Vectorless | 1.5 / 1.9 | 11651.7 / 11651.7 | 25.1 / 23.2 | 40.5 / 168.3 | 5097.2 / 15.7 | 15376.4 / 7223.2 | 567 / 427 / 567 |
| narrative | P-Vectorless-Fixed | 1.0 / 1.6 | 29.8 / 1221.1 | 27.7 / 24.8 | 3608.3 / 352.6 | 60.6 / 2976.8 | 9122.2 / 7877.0 | 472 / 293 / 472 |
| narrative | S-Profile | – / – | – / – | – / – | – / – | – / – | 5256.3 / 5475.0 | 0 / 0 / 0 |

### So sánh ghép cặp theo bệnh nhân (bootstrap 10.000 lần, Wilcoxon; Holm trong từng họ)

| Họ | So sánh | Số BN | Chênh lệch [KTC 95%] | p bootstrap (Holm) | p Wilcoxon (Holm) |
|---|---|---|---|---|---|
| coded|safe_allergen_adj | P-Vectorless - P-Direct | 26 | +0.000 [+0.000, +0.000] | 1.000 (1.000) | 1.000 (1.000) |
| coded|safe_allergen_adj | P-Vectorless - P-Vectorless-Fixed | 26 | +0.115 [+0.038, +0.212] | 0.006 (0.012) | 0.103 (0.207) |
| coded|safe_allergen_adj | P-Vectorless - P-Vector | 26 | +0.212 [+0.077, +0.385] | 0.002 (0.007) | 0.058 (0.174) |
| coded|safe_allergen_adj | P-Vectorless - S-Profile | 26 | +0.250 [+0.115, +0.404] | 0.000 (0.000) | 0.009 (0.037) |
| narrative|safe_allergen_adj | P-Vectorless - P-Vectorless-Fixed | 26 | +0.135 [+0.038, +0.250] | 0.008 (0.017) | 0.103 (0.207) |
| narrative|safe_allergen_adj | P-Vectorless - P-Vector | 26 | +0.154 [+0.038, +0.288] | 0.008 (0.017) | 0.103 (0.207) |
| narrative|safe_allergen_adj | P-Vectorless - S-Profile | 26 | +0.231 [+0.096, +0.385] | 0.000 (0.001) | 0.017 (0.052) |
| coded-narrative|safe_allergen_adj | P-Vectorless | 26 | +0.019 [+0.000, +0.058] | 0.722 (1.000) | 0.710 (1.000) |
| coded-narrative|safe_allergen_adj | P-Vectorless-Fixed | 26 | +0.038 [+0.000, +0.096] | 0.263 (1.000) | 0.473 (1.000) |
| coded-narrative|safe_allergen_adj | P-Vector | 26 | -0.038 [-0.096, +0.000] | 0.262 (1.000) | 0.473 (1.000) |
| coded-narrative|safe_allergen_adj | S-Profile | 26 | +0.000 [+0.000, +0.000] | 1.000 (1.000) | 1.000 (1.000) |
| coded|safe_nutrition | P-Vectorless - P-Direct | 88 | +0.000 [+0.000, +0.000] | 1.000 (1.000) | 1.000 (1.000) |
| coded|safe_nutrition | P-Vectorless - P-Vectorless-Fixed | 88 | +0.023 [+0.000, +0.051] | 0.104 (0.313) | 0.538 (1.000) |
| coded|safe_nutrition | P-Vectorless - P-Vector | 88 | +0.006 [+0.000, +0.017] | 0.737 (1.000) | 0.834 (1.000) |
| coded|safe_nutrition | P-Vectorless - S-Profile | 88 | +0.636 [+0.562, +0.705] | 0.000 (0.000) | 0.000 (0.000) |
| narrative|safe_nutrition | P-Vectorless - P-Vectorless-Fixed | 88 | +0.023 [+0.000, +0.051] | 0.104 (0.208) | 0.538 (1.000) |
| narrative|safe_nutrition | P-Vectorless - P-Vector | 88 | +0.023 [+0.000, +0.051] | 0.104 (0.208) | 0.538 (1.000) |
| narrative|safe_nutrition | P-Vectorless - S-Profile | 88 | +0.636 [+0.562, +0.705] | 0.000 (0.000) | 0.000 (0.000) |
| coded-narrative|safe_nutrition | P-Vectorless | 88 | +0.000 [+0.000, +0.000] | 1.000 (1.000) | 1.000 (1.000) |
| coded-narrative|safe_nutrition | P-Vectorless-Fixed | 88 | +0.000 [+0.000, +0.000] | 1.000 (1.000) | 1.000 (1.000) |
| coded-narrative|safe_nutrition | P-Vector | 88 | +0.017 [+0.000, +0.040] | 0.104 (0.417) | 0.538 (1.000) |
| coded-narrative|safe_nutrition | S-Profile | 88 | +0.000 [+0.000, +0.000] | 1.000 (1.000) | 1.000 (1.000) |
| coded|safe_dialogue_adj | P-Vectorless - P-Direct | 88 | +0.000 [+0.000, +0.000] | 1.000 (1.000) | 1.000 (1.000) |
| coded|safe_dialogue_adj | P-Vectorless - P-Vectorless-Fixed | 88 | +0.000 [+0.000, +0.000] | 1.000 (1.000) | 1.000 (1.000) |
| coded|safe_dialogue_adj | P-Vectorless - P-Vector | 88 | +0.000 [+0.000, +0.000] | 1.000 (1.000) | 1.000 (1.000) |
| coded|safe_dialogue_adj | P-Vectorless - S-Profile | 88 | +0.045 [-0.023, +0.125] | 0.286 (1.000) | 0.454 (1.000) |
| narrative|safe_dialogue_adj | P-Vectorless - P-Vectorless-Fixed | 88 | +0.011 [+0.000, +0.034] | 0.725 (1.000) | 0.834 (1.000) |
| narrative|safe_dialogue_adj | P-Vectorless - P-Vector | 88 | +0.011 [+0.000, +0.034] | 0.725 (1.000) | 0.834 (1.000) |
| narrative|safe_dialogue_adj | P-Vectorless - S-Profile | 88 | +0.045 [-0.023, +0.125] | 0.286 (0.857) | 0.454 (1.000) |
| coded-narrative|safe_dialogue_adj | P-Vectorless | 88 | +0.000 [+0.000, +0.000] | 1.000 (1.000) | 1.000 (1.000) |
| coded-narrative|safe_dialogue_adj | P-Vectorless-Fixed | 88 | +0.011 [+0.000, +0.034] | 0.725 (1.000) | 0.834 (1.000) |
| coded-narrative|safe_dialogue_adj | P-Vector | 88 | +0.011 [+0.000, +0.034] | 0.725 (1.000) | 0.834 (1.000) |
| coded-narrative|safe_dialogue_adj | S-Profile | 88 | +0.000 [+0.000, +0.000] | 1.000 (1.000) | 1.000 (1.000) |
| coded|allergy_recall | P-Vectorless - P-Direct | 11 | +0.000 [+0.000, +0.000] | 1.000 (1.000) | 1.000 (1.000) |
| coded|allergy_recall | P-Vectorless - P-Vectorless-Fixed | 11 | +0.727 [+0.606, +0.848] | 0.000 (0.000) | 0.001 (0.003) |
| coded|allergy_recall | P-Vectorless - P-Vector | 11 | +0.808 [+0.596, +1.000] | 0.000 (0.000) | 0.002 (0.004) |
| narrative|allergy_recall | P-Vectorless - P-Vectorless-Fixed | 11 | +0.737 [+0.495, +0.929] | 0.000 (0.000) | 0.004 (0.008) |
| narrative|allergy_recall | P-Vectorless - P-Vector | 11 | +0.727 [+0.485, +0.929] | 0.000 (0.000) | 0.004 (0.008) |
| coded-narrative|allergy_recall | P-Vectorless | 11 | +0.182 [+0.000, +0.455] | 0.216 (0.432) | 0.500 (1.000) |
| coded-narrative|allergy_recall | P-Vectorless-Fixed | 11 | +0.192 [+0.101, +0.283] | 0.000 (0.000) | 0.016 (0.047) |
| coded-narrative|allergy_recall | P-Vector | 11 | +0.101 [-0.091, +0.343] | 0.402 (0.432) | 0.750 (1.000) |
| coded|node_hit | P-Vectorless - P-Direct | 88 | +0.784 [+0.693, +0.864] | 0.000 (0.000) | 0.000 (0.000) |
| coded|node_hit | P-Vectorless - P-Vectorless-Fixed | 88 | -0.068 [-0.136, +0.000] | 0.063 (0.126) | 0.252 (0.504) |
| coded|node_hit | P-Vectorless - P-Vector | 88 | -0.068 [-0.182, +0.045] | 0.278 (0.278) | 0.323 (0.504) |

## Bộ kiểm độc lập

Công thức được kiểm: 227. Trạng thái các phán quyết "yes": dropped_flagged 15, dropped_not_verbatim 0, confirmed 48, rejected 41, pending 0. Mục mới vào hàng duyệt mù `eval\labels\checker_queue.csv`: 0 (pending tính là vi phạm).
Dị ứng và chế độ ăn do bộ kiểm độc lập chấm; nguyên liệu có tên (từ hồ sơ hoặc hội thoại) so khớp nguyên từ trên dòng nguyên liệu thô; giới hạn thời gian đọc cột total_minutes; dinh dưỡng đọc cột dinh dưỡng.
S-Profile không đọc hồ sơ nên chỉ chạy ở chế độ coded; dòng narrative của nó dùng chung các lượt đó.
Câu trả lời bị cắt ở giới hạn 2.048 token của M6: không có.
Chọn nút đúng chỉ tính ở chế độ coded: ở narrative mỗi section là một nút (narrative.results), nên gần như luôn trúng.
