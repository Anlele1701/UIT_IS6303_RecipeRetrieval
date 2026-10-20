# Inventory hồ sơ bệnh nhân C-CDA (MV0)

Sinh tự động bởi `scripts/patient_inventory.py` lúc 2026-10-17T16:29:30 (commit `6012ad2`). Số liệu gốc ở `eval/patient_inventory/`. Không sửa tay file này.

## 1. Tổng quan (P1)

| Mục | Giá trị |
|---|---|
| Số file `.xml` | 108 |
| Parse được | 108 (lỗi: 0) |
| Mã bệnh nhân khác nhau | 108 |
| `softwareName` | `https://github.com/synthetichealth/synthea` (108) – không có số phiên bản |
| Ngày hồ sơ (`effectiveTime`) | 1961-08-25 → 2026-08-25 |
| Năm của ngày hồ sơ | 1961: 1, 1991: 1, 1998: 1, 2015: 2, 2016: 1, 2018: 1, 2023: 1, 2026: 100 |
| Bệnh nhân đã mất (Results organizer 69409-1 present) | 8 (ngày hồ sơ 1961-08-25 → 2026-05-12) |
| Giới tính | F: 51, M: 57 |
| Nhóm tuổi (tại ngày hồ sơ) | 0-17: 22, 18-39: 38, 40-64: 38, 65+: 10 |
| Entry bị bỏ không đọc (P7) | 29762-2: 108, 47420-5: 2.431 |

## 2. Ứng viên tầng P8

Chỉ để xem có đủ bệnh nhân cho từng tầng hay không. Một bệnh nhân có thể thuộc nhiều tầng. Không tính 8 bệnh nhân đã mất (vẫn được nạp và đếm ở P1). Quy tắc và các mã khớp liệt kê bên dưới.

| Tầng | Số bệnh nhân | Quy tắc |
|---|---:|---|
| food_allergy | 11 | active allergy with kind 414285001 |
| diabetes | 5 | active (disorder) matching /diabetes|prediabetes|hyperglycemia/i |
| hypertension | 18 | active (disorder) matching /hypertension/i |
| ckd | 4 | active (disorder) matching /kidney disease|renal disease|renal failure|nephropathy|end-stage renal/i |
| multi | 5 | >= 2 of diabetes, hypertension, ckd |
| none | 70 | none of the above |

Mã khớp tầng `diabetes`:

- `44054006` Diabetes mellitus type 2 (disorder) – 4 bệnh nhân
- `127013003` Disorder of kidney due to diabetes mellitus (disorder) – 4 bệnh nhân
- `90781000119102` Microalbuminuria due to type 2 diabetes mellitus (disorder) – 3 bệnh nhân
- `157141000119108` Proteinuria due to type 2 diabetes mellitus (disorder) – 3 bệnh nhân
- `80394007` Hyperglycemia (disorder) – 2 bệnh nhân
- `368581000119106` Neuropathy due to type 2 diabetes mellitus (disorder) – 2 bệnh nhân

Mã khớp tầng `hypertension`:

- `59621000` Essential hypertension (disorder) – 18 bệnh nhân

Mã khớp tầng `ckd`:

- `431855005` Chronic kidney disease stage 1 (disorder) – 4 bệnh nhân
- `433144002` Chronic kidney disease stage 3 (disorder) – 3 bệnh nhân
- `431856006` Chronic kidney disease stage 2 (disorder) – 3 bệnh nhân
- `431857002` Chronic kidney disease stage 4 (disorder) – 2 bệnh nhân

## 3. Dị ứng thực phẩm (`414285001`) – đối chiếu `allergy_substance.csv`

| SNOMED | Chất | Bệnh nhân | Đang hiệu lực | Có trong luật |
|---|---|---:|---:|---|
| 735029006 | Shellfish (substance) | 6 | 6 | có |
| 102263004 | Eggs (edible) (substance) | 4 | 4 | có |
| 442571000124108 | Tree nut (substance) | 3 | 3 | có |
| 3718001 | Cow's milk (substance) | 2 | 2 | có |
| 412071004 | Wheat (substance) | 2 | 2 | có |
| 256355007 | Glycine max (substance) | 1 | 1 | có |
| 762952008 | Peanut (substance) | 1 | 1 | có |

Các loại dị ứng khác (không sinh ràng buộc món ăn): Allergy to substance (76 lượt bệnh nhân), Allergy to drug (9 lượt bệnh nhân), Intolerance to drug (1 lượt bệnh nhân).

Kiểm tra luật: 7 dòng; chất chưa gán nhóm: không có; tên trong `extra_ingredients_exclude` không có trong bảng `ingredient`: không có.

## 4. Đối chiếu mã khởi đầu trong đặc tả

| Bảng | Mã / chuỗi | Tên | Bệnh nhân (đang hiệu lực) |
|---|---|---|---:|
| 4.1 | 412071004 | Wheat (substance) | 2 |
| 4.1 | 735029006 | Shellfish (substance) | 6 |
| 4.2 | 59621000 | Essential hypertension | 20 |
| 4.2 | 44054006 | Diabetes mellitus type 2 | 6 |
| 4.2 | 433144002 | CKD stage 3 | 3 |
| 4.2 | 431857002 | CKD stage 4 | 2 |
| 4.3 | warfarin | Warfarin Sodium 5 MG Oral Tablet | 1 |
| 4.3 | simvastatin | Simvastatin 20 MG Oral Tablet; Simvastatin 10 MG Oral Tablet | 22 |
| 4.3 | atorvastatin | atorvastatin 20 MG Oral Tablet; atorvastatin 40 MG Oral Tablet | 2 |

## 4b. Sinh hiệu và xét nghiệm đặc tả cần

Cột "Nằm ở" ghi section và organizer chứa chỉ số. Số bệnh nhân đếm trên mọi section và organizer.

| LOINC | Chỉ số | Nằm ở | Bệnh nhân có |
|---|---|---|---:|
| 29463-7 | Body weight | vitals | 108 |
| 39156-5 | BMI | vitals | 106 |
| 8480-6 | Systolic blood pressure | – | **không có trong dữ liệu** |
| 8462-4 | Diastolic blood pressure | – | **không có trong dữ liệu** |
| 33914-3 | eGFR (MDRD) | results (24321-2), results (24323-8) | 21 |
| 4548-4 | HbA1c | – | **không có trong dữ liệu** |
| 2951-2 | Sodium (serum) | results (24321-2), results (24323-8) | 16 |
| 2823-3 | Potassium (serum) | results (24321-2), results (24323-8) | 16 |
| 2160-0 | Creatinine (serum) | results (24321-2), results (24323-8) | 16 |
| 2339-0 | Glucose (blood) | results (24321-2), results (24323-8), results (51990-0) | 43 |
| 2345-7 | Glucose (serum/plasma) | results (24321-2), results (24323-8) | 16 |

## 5. Bệnh `(disorder)` liên quan dinh dưỡng tìm thấy (để bổ sung mã đồng nghĩa)

| Nhóm tìm | SNOMED | Tên | Bệnh nhân | Đang hiệu lực |
|---|---|---|---:|---:|
| diabetes | 127013003 | Disorder of kidney due to diabetes mellitus (disorder) | 6 | 6 |
| diabetes | 44054006 | Diabetes mellitus type 2 (disorder) | 6 | 6 |
| diabetes | 90781000119102 | Microalbuminuria due to type 2 diabetes mellitus (disorder) | 4 | 4 |
| diabetes | 157141000119108 | Proteinuria due to type 2 diabetes mellitus (disorder) | 3 | 3 |
| diabetes | 368581000119106 | Neuropathy due to type 2 diabetes mellitus (disorder) | 2 | 2 |
| diabetes | 427089005 | Diabetes mellitus due to cystic fibrosis (disorder) | 1 | 1 |
| CKD / kidney | 127013003 | Disorder of kidney due to diabetes mellitus (disorder) | 6 | 6 |
| CKD / kidney | 431855005 | Chronic kidney disease stage 1 (disorder) | 6 | 6 |
| CKD / kidney | 431856006 | Chronic kidney disease stage 2 (disorder) | 4 | 4 |
| CKD / kidney | 433144002 | Chronic kidney disease stage 3 (disorder) | 3 | 3 |
| CKD / kidney | 431857002 | Chronic kidney disease stage 4 (disorder) | 2 | 2 |
| hypertension | 59621000 | Essential hypertension (disorder) | 20 | 20 |
| hyperlipidemia | 55822004 | Hyperlipidemia (disorder) | 9 | 9 |
| anemia | 271737000 | Anemia (disorder) | 39 | 35 |

## 6. Vấn đề đang hiệu lực bị bỏ theo hậu tố (P4)

`(finding)`: 513, `(situation)`: 103, `(none)`: 5, `(person)`: 2.

## 7. Organizer trong Diagnostic Results (P7)

Chỉ organizer có trong `data/rules/include_loinc.csv` (danh sách cho phép) được vào cây hồ sơ. Organizer trong `data/rules/exclude_loinc.csv` là dữ liệu nhạy cảm, chỉ được đếm. Các organizer còn lại là `not_relevant`.

| Phân loại | Số organizer | Số bệnh nhân |
|---|---:|---:|
| include | 2.788 | 108 |
| exclude | 2.248 | 94 |
| not_relevant | 327 | 21 |

Hai danh sách trùng mã: không.

| LOINC | Tên | Bệnh nhân | Phân loại |
|---|---|---:|---|
| 58410-2 | CBC panel - Blood by Automated count | 108 | include |
| 69737-5 | Generalized anxiety disorder 7 item (GAD-7) | 92 | exclude |
| 55757-9 | Patient Health Questionnaire 2 item (PHQ-2) [Reported] | 85 | exclude |
| 82666-9 | Drug Abuse Screening Test-10 [DAST-10] | 75 | exclude |
| 76499-3 | Humiliation, Afraid, Rape, and Kick questionnaire [HARK] | 72 | exclude |
| 72109-2 | Alcohol Use Disorder Identification Test - Consumption [AUDIT-C] | 71 | exclude |
| 57698-3 | Lipid panel with direct LDL - Serum or Plasma | 68 | include |
| 51990-0 | Basic metabolic panel - Blood | 38 | include |
| 44249-1 | PHQ-9 quick depression assessment panel [Reported.PHQ] | 26 | exclude |
| 24357-6 | Urinalysis macro (dipstick) panel - Urine | 24 | include |
| 89206-7 | Patient Health Questionnaire-9: Modified for Teens [Reported.PHQ.Teen] | 23 | exclude |
| 24323-8 | Comprehensive metabolic 2000 panel - Serum or Plasma | 17 | include |
| 59453-1 | Morse Fall Scale panel | 11 | not_relevant |
| 24321-2 | Basic metabolic 2000 panel - Serum or Plasma | 9 | include |
| 69409-1 | U.S. standard certificate of death - 2003 revision | 8 | exclude |
| 34528-0 | PT panel - Platelet poor plasma by Coagulation assay | 5 | not_relevant |
| 89577-1 | Troponin I.cardiac panel - Serum or Plasma by High sensitivity method | 5 | not_relevant |
| 94531-1 | SARS-CoV-2 (COVID-19) RNA panel - Respiratory system specimen by NAA with probe detection | 5 | not_relevant |
| 24336-0 | Gas panel - Arterial blood | 4 | not_relevant |
| 24339-4 | Gas panel - Venous blood | 4 | not_relevant |
| 55405-5 | Heart failure tracking panel | 4 | not_relevant |
| 75689-0 | Iron panel - Serum or Plasma | 3 | include |
| 80381-7 | Influenza virus A and B Ag panel - Upper respiratory specimen by Rapid immunoassay | 3 | not_relevant |
| 93124-6 | New York Heart Association Functional Classification panel | 3 | not_relevant |
| 24356-8 | Urinalysis complete panel - Urine | 2 | include |
| 50190-8 | Iron and Iron binding capacity panel - Serum or Plasma | 2 | include |
| 57023-4 | Auto Differential panel - Blood | 2 | not_relevant |
| 87674-8 | Optical coherence tomography study | 2 | not_relevant |
| 92143-7 | Respiratory pathogens DNA and RNA panel - Respiratory system specimen by NAA with probe detection | 2 | not_relevant |
| 600-7 | Bacteria identified in Blood by Culture | 1 | not_relevant |

Các bảng đầy đủ: `eval/patient_inventory/{allergies,problems,medications,observations,organizers,encounters,sections}.csv`.
