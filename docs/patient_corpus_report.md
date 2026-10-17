# Báo cáo dữ liệu hồ sơ bệnh nhân (quy tắc P1–P7)

Sinh tự động bởi `scripts/patient_ingest.py stats` lúc 2026-10-17T17:03:58 (commit `54ce890`). Số liệu gốc ở `eval/patient_corpus.json`. Không sửa tay file này.

| Mã | Quy tắc | Số liệu (tổng các nguồn) |
|---|---|---|
| P1 | Nạp mọi file `.xml` | 108 file → 108 parse được; 100 còn sống, 8 đã mất |
| P2 | Chỉ giữ dị ứng và vấn đề đang hiệu lực | dị ứng giữ 105, bỏ 0; vấn đề bỏ 2.628 |
| P3 | Dị ứng thực phẩm (`414285001`) | 19 entry; ánh xạ nhóm ở MV2 |
| P4 | Vấn đề: chỉ giữ `(disorder)` | giữ 263; bỏ `(finding)` 507, `(none)` 5, `(person)` 2, `(situation)` 103 |
| P5 | Thuốc đang dùng | 267 đang dùng; 3.582 đã ngừng |
| P6 | Sinh hiệu gần nhất, xét nghiệm, lần khám | 836 chỉ số sinh hiệu; 2.788 organizer xét nghiệm (danh sách cho phép); 5.547 lần khám |
| P7 | Loại dữ liệu nhạy cảm | `encounter_death` 8; `encounter_end_of_life` 8; `encounter_substance_use` 8; `medication_substance_use` 1; `organizer_death` 8; `organizer_mental_health` 1.324; `organizer_not_relevant` 327; `organizer_substance_use` 627; `organizer_violence` 289; `problem_substance_use` 9; `section_29762-2_entries` 108; `section_47420-5_entries` 2.431; không đọc danh tính ở 108 hồ sơ |

## Theo nguồn

| Nguồn | Thư mục | File | Parse được | Lỗi | Còn sống | Đã mất |
|---|---|---:|---:|---:|---:|---:|
| sample | `data/synthea_sample_data_ccda_latest` | 108 | 108 | 0 | 100 | 8 |

## Cây hồ sơ trong DB

| Loại nút | Số nút |
|---|---:|
| context | 1.983 |
| fixed | 432 |
| root | 108 |

Tóm tắt nút ngữ cảnh: template 1.983.

## Tỉ lệ công thức qua từng luật dinh dưỡng (bản nháp `condition_nutrient.csv`)

Trên toàn bộ công thức, giá trị theo khẩu phần. Ngưỡng ngày × 0,3333 cho một bữa; ngưỡng % năng lượng tính trên calo của chính công thức. "Không rõ" là công thức thiếu số liệu (hoặc calo bằng 0). Cột "qua" tính trên công thức có số liệu; hai cột sau tính trên toàn bộ, khi bỏ hoặc giữ công thức không rõ (`unknown_strict` bật / tắt).

| Bệnh | Chất | Ngưỡng ngày | Ngưỡng / khẩu phần | Chế độ | Qua | Trượt | Không rõ | Tỉ lệ qua | Bỏ không rõ | Giữ không rõ |
|---|---|---|---:|---|---:|---:|---:|---:|---:|---:|
| default | sodium_mg | max 2000 mg | 666,67 | filter | 22.464 | 10.142 | 113 | 68,9% | 68,7% | 69,0% |
| default | sugar_pct_kcal | max 10 % | 10,0 | warn | 18.142 | 13.976 | 601 | 56,5% | 55,5% | 57,3% |
| Essential hypertension | sodium_mg | max 2300 mg | 766,67 | filter | 24.027 | 8.579 | 113 | 73,7% | 73,4% | 73,8% |
| Essential hypertension | sat_fat_pct_kcal | max 6 % | 6,0 | filter | 5.435 | 26.207 | 1.077 | 17,2% | 16,6% | 19,9% |
| Diabetes mellitus type 2 | fiber_per_1000kcal | min 14 g | 14,0 | filter | 7.297 | 24.210 | 1.212 | 23,2% | 22,3% | 26,0% |
| Diabetes mellitus type 2 | sodium_mg | max 2300 mg | 766,67 | filter | 24.027 | 8.579 | 113 | 73,7% | 73,4% | 73,8% |
| CKD stage 3/4 | sodium_mg | max 2000 mg | 666,67 | filter | 22.464 | 10.142 | 113 | 68,9% | 68,7% | 69,0% |
| CKD stage 3/4 | protein_g_per_kg | max 0.8 g/kg (nặng 60 kg) | 16,0 | filter | 20.634 | 11.844 | 241 | 63,5% | 63,1% | 63,8% |
| CKD stage 3/4 | protein_g_per_kg | max 0.8 g/kg (nặng 70 kg) | 18,67 | filter | 22.080 | 10.398 | 241 | 68,0% | 67,5% | 68,2% |
| CKD stage 3/4 | protein_g_per_kg | max 0.8 g/kg (nặng 80 kg) | 21,33 | filter | 23.629 | 8.849 | 241 | 72,8% | 72,2% | 73,0% |
| CKD stage 3/4 | potassium_mg | – | – | warn | – | – | – | warn only, no limit | | |
| CKD stage 3/4 | phosphorus_mg | – | – | warn | – | – | – | warn only, no limit | | |

Gộp theo bệnh: mọi luật `filter` của bệnh cộng luật mặc định, mỗi chất lấy ngưỡng chặt nhất; luật protein theo kg tính với 70 kg. Luật `warn` không tính vào tỉ lệ gộp.

| Bệnh | Bộ lọc áp dụng | Qua | Không rõ | Tỉ lệ qua | Bỏ không rõ | Giữ không rõ |
|---|---|---:|---:|---:|---:|---:|
| default | sodium_mg max 666,67 (default) | 22.464 | 113 | 68,9% | 68,7% | 69,0% |
| Essential hypertension | sodium_mg max 666,67 (default); sat_fat_pct_kcal max 6,0 (Essential hypertension) | 3.985 | 1.000 | 12,6% | 12,2% | 15,2% |
| Diabetes mellitus type 2 | sodium_mg max 666,67 (default); fiber_per_1000kcal min 14,0 (Diabetes mellitus type 2) | 5.254 | 1.091 | 16,6% | 16,1% | 19,4% |
| CKD stage 3/4 | sodium_mg max 666,67 (default); protein_g_per_kg max 18,67 (CKD stage 3/4) | 18.468 | 241 | 56,9% | 56,4% | 57,2% |

## Nguồn dữ liệu

- Bộ mẫu: 100 Sample Synthetic Patient Records, C-CDA (latest), tải từ https://synthea.mitre.org/downloads ngày 2026-10-17.
- Synthea commit `d9d07a6eef91ee5144293b42ab64224d84d124f8` (from the sample-data commit message; synthea tag master-branch-latest on 2026-08-18, newer than v4.0.0).
- Kiểm chứng: 2026-10-17: all 108 files match the zip at sample-data commit 9959d9178e (sha256).
- Bệnh nhân sinh thêm: chưa có.

File luật (sha256): `allergy_substance.csv` `6641534048ba`, `condition_nutrient.csv` `86c4f0187374`, `include_loinc.csv` `caf69622c482`, `exclude_loinc.csv` `5432a0bd98dd`, `exclude_codes.csv` `8e3d88a3d26d`.
