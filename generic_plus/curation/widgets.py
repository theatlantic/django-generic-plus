from django import forms
from django.forms.utils import flatatt
from django.utils.encoding import force_text
from django.utils.html import format_html


class ContentObjectSelect(forms.Select):

    def render_option(self, selected_choices, option_value, option_label):
        if option_value is None:
            option_value = ''
        option_value = force_text(option_value)
        attrs = {}
        if option_value in selected_choices:
            attrs['selected'] = 'selected'
            if not self.allow_multiple_selected:
                # Only allow for a single selection.
                selected_choices.remove(option_value)
        return self.render_option_html(option_value, option_label, attrs)

    def render_option_html(self, option_value, option_label, attrs=None):
        """
        Method allowing customization of the html for <option> elements.

        This can be useful for attaching additional data to option elements
        for the purposes of adding client-side enhancements to the admin.
        """
        attrs = attrs or {}
        return format_html('<option value="{}"{}>{}</option>',
            option_value, flatatt(attrs), option_label)
