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
    extend: {
      colors: {
        // لون أساسي واحد موحّد لكل النظام (هيدر لوحة الموظفين، أزرار
        // رئيسية، شارات نشطة، إلخ). غيّر القيم هنا بس، مش في كل template
        // — كل استخدام لـ bg-primary-*/text-primary-*/border-primary-*
        // في أي مكان في المشروع هيتحدّث تلقائيًا بعد أي npm run build:css.
        primary: {
          50: '#eef2ff',
          100: '#e0e7ff',
          200: '#c7d2fe',
          300: '#a5b4fc',
          400: '#818cf8',
          500: '#6366f1',
          600: '#1d4ed8',
          700: '#1e40af',
          800: '#1e3a8a',
          900: '#172554',
        },
        // خلفية الصفحة الجديدة في لوحة الموظفين — أغمق شوية من bg-gray-100
        // القديمة عشان يبان فرق حقيقي بينها وبين الكروت البيضاء فوقها.
        surface: {
          page: '#e7eaf1',
        },
      },
    },
  },
  plugins: [],
  // مفيش safelist مطلوبة: كل الكلاسات مكتوبة كاملة صراحة في التمبليتس (زي bg-blue-600)
  // من غير تركيب ديناميكي بالـ string concatenation، فالـ content scan بيلقطها كلها.
};
