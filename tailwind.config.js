/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './templates/**/*.html',
    './*/templates/**/*.html',
    // staff_ui.py بيبني كلاسات الشارات/الأزرار كـ strings ثابتة في بايثون، مش
    // في HTML، فلازم يتفحص برضه عشان Tailwind الـ purge ميشيلهاش باعتبارها مش مستخدمة.
    './staff/templatetags/*.py',
  ],
  theme: {
    extend: {},
  },
  plugins: [],
  // مفيش safelist مطلوبة: كل الكلاسات مكتوبة كاملة صراحة في التمبليتس (زي bg-blue-600)
  // من غير تركيب ديناميكي بالـ string concatenation، فالـ content scan بيلقطها كلها.
};
