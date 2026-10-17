# Báo cáo dữ liệu hồ sơ bệnh nhân (quy tắc P1–P7)

Sinh tự động bởi `scripts/patient_ingest.py stats` lúc 2026-10-17T16:59:18 (commit `8feb80c`). Số liệu gốc ở `eval/patient_corpus.json`. Không sửa tay file này.

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

## Nguồn dữ liệu

- Bộ mẫu: 100 Sample Synthetic Patient Records, C-CDA (latest), tải từ https://synthea.mitre.org/downloads ngày 2026-10-17.
- Synthea commit `d9d07a6eef91ee5144293b42ab64224d84d124f8` (from the sample-data commit message; synthea tag master-branch-latest on 2026-08-18, newer than v4.0.0).
- Kiểm chứng: 2026-10-17: all 108 files match the zip at sample-data commit 9959d9178e (sha256).
- Bệnh nhân sinh thêm: chưa có.

File luật (sha256): `allergy_substance.csv` `6641534048ba`, `include_loinc.csv` `caf69622c482`, `exclude_loinc.csv` `5432a0bd98dd`, `exclude_codes.csv` `8e3d88a3d26d`.
