// Vietnamese labels for codes the chat API sends (allergen groups, nutrient columns, presets).

import type { Limit } from './api'

export const ALLERGEN: Record<string, string> = {
  milk: 'sữa', egg: 'trứng', fish: 'cá', crustacean_shellfish: 'giáp xác (tôm, cua)', tree_nuts: 'hạt cây',
  peanut: 'đậu phộng', wheat: 'lúa mì', soy: 'đậu nành', sesame: 'mè',
}

export const DIET: Record<string, string> = { vegetarian: 'chay', vegan: 'thuần chay' }

const NUTRIENT: Record<string, [label: string, unit: string]> = {
  sodium_mg: ['Natri', 'mg'], protein_g: ['Đạm', 'g'], potassium_mg: ['Kali', 'mg'],
  sat_fat_pct_kcal: ['Chất béo bão hòa', '% năng lượng'], sugar_pct_kcal: ['Đường', '% năng lượng'],
  fiber_per_1000kcal: ['Chất xơ', 'g/1000 kcal'],
}

const num = (v: number) => (Math.round(v * 10) / 10).toLocaleString('vi-VN')

export const nutrientName = (col: string) => NUTRIENT[col]?.[0] ?? col
export const nutrientUnit = (col: string) => NUTRIENT[col]?.[1] ?? ''

/** "Natri ≤ 666,7 mg/khẩu phần" */
export function limitText(col: string, [op, value]: Limit): string {
  const unit = nutrientUnit(col)
  const perServing = unit === 'mg' || unit === 'g' ? `${unit}/khẩu phần` : unit
  return `${nutrientName(col)} ${op === 'max' ? '≤' : '≥'} ${num(value)} ${perServing}`
}

/** A record or dialogue constraint id (allergen:wheat, ingredient:clam, nutrient:sodium_mg...) in words. */
export function constraintText(id: string): string {
  const [kind, ...rest] = id.split(':')
  const v = rest.join(':')
  switch (kind) {
    case 'allergen': return `Dị ứng ${ALLERGEN[v] ?? v}`
    case 'ingredient': return `Không dùng ${v}`
    case 'include': return `Ưu tiên ${v}`
    case 'diet': return `Chế độ ${DIET[v] ?? v}`
    case 'max_total_minutes': return `Tối đa ${v} phút`
    case 'max_calories': return `Tối đa ${v} kcal`
    case 'category': return `Loại món: ${v}`
    case 'nutrient': return `Giới hạn ${nutrientName(v).toLowerCase()}`
    case 'soft': return `Ưu tiên ${nutrientName(v).toLowerCase()}`
    default: return id
  }
}

export const PRESETS: { name: string; label: string }[] = [
  { name: 'S', label: 'Hệ đầy đủ (mặc định)' },
  { name: 'P-Vectorless', label: 'Có hồ sơ: cây vectorless (mặc định khi có bệnh nhân)' },
  { name: 'P-Direct', label: 'Có hồ sơ: đọc thẳng entry có mã' },
  { name: 'P-Vectorless-Fixed', label: 'Có hồ sơ: LLM tự chọn mọi nút (baseline)' },
  { name: 'P-Vector', label: 'Có hồ sơ: truy hồi chunk bằng vector (baseline)' },
  { name: 'S-Profile', label: 'Bỏ qua hồ sơ' },
  { name: 'B0', label: 'B0 – Hybrid của A1, không sinh câu trả lời' },
  { name: 'B1', label: 'B1 – RAG ngây thơ trên A1' },
  { name: 'S-QU', label: 'Tắt hiểu truy vấn (M1)' },
  { name: 'S-Filter', label: 'Tắt lọc ràng buộc (M4)' },
  { name: 'S-Norm', label: 'Tắt chuẩn hóa nguyên liệu' },
  { name: 'S-Conv', label: 'Tắt nhớ hội thoại (M2)' },
  { name: 'S-Rerank', label: 'Tắt rerank (M5)' },
  { name: 'S-Verify', label: 'Tắt kiểm tra (M7)' },
  { name: 'S+Unknown', label: 'Loại cả công thức có dòng nguyên liệu chưa rõ' },
]

export const EXAMPLES: { text: string; hint: string }[] = [
  { text: 'Tôi dị ứng đậu phộng, gợi ý món gà xào sốt đậu phộng kiểu Thái', hint: 'Kịch bản 1: thử với B0 rồi với S' },
  { text: 'gợi ý món gà cho bữa tối', hint: 'Kịch bản 2: sau đó gõ "không dùng sữa nhé", rồi "món thứ 2 làm thế nào?"' },
  { text: 'công thức bánh chưng thuần chay không gạo nếp, không đậu xanh', hint: 'Kịch bản 3: câu không có đáp án' },
  { text: "I'm allergic to shellfish, suggest a quick pasta dinner", hint: 'Kịch bản 4: sau đó gõ "actually I can eat shellfish now, shrimp pasta please"' },
]
