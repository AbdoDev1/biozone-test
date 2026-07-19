from django.template import Context, Template
from django.test import SimpleTestCase


class BtnExtraAttrsTests(SimpleTestCase):
    """
    اختبارات فعلية (render) لباراميتر extra_attrs في {% btn %}.
    الهدف: التأكد إن أي attribute إضافي (زي @click في Alpine.js) بيترندر
    زي ما هو من غير escaping، وإن الزراير القديمة اللي مش بتستخدم extra_attrs
    فضلت شغالة زي ما هي (مفيش artifact غريب من غير القيمة دي).
    """

    def render(self, tpl):
        return Template("{% load staff_ui %}" + tpl).render(Context({}))

    def test_extra_attrs_on_button(self):
        out = self.render(
            '{% btn "إلغاء" type="button" variant="secondary" size="sm" '
            'extra_attrs=\'@click="open = false"\' %}'
        )
        self.assertIn('@click="open = false"', out)
        self.assertIn("<button", out)
        self.assertIn("إلغاء", out)

    def test_extra_attrs_on_link(self):
        out = self.render(
            '{% btn "رابط" href="/x/" extra_attrs=\'x-show="open"\' %}'
        )
        self.assertIn('x-show="open"', out)
        self.assertIn('<a href="/x/"', out)

    def test_no_extra_attrs_leaves_button_clean(self):
        out = self.render('{% btn "تأكيد" type="submit" variant="danger" %}')
        self.assertIn("<button", out)
        self.assertIn('type="submit"', out)
        self.assertNotIn("extra_attrs", out)

    def test_onclick_and_extra_attrs_coexist(self):
        out = self.render(
            '{% btn "طباعة" onclick="window.print()" '
            'extra_attrs=\':disabled="loading"\' %}'
        )
        self.assertIn('onclick="window.print()"', out)
        self.assertIn(':disabled="loading"', out)

    def test_icon_still_renders(self):
        out = self.render('{% btn "تأكيد" icon="check" %}')
        self.assertIn("<svg", out)
        self.assertIn("تأكيد", out)
