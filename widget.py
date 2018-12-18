from django import forms
from login.models import DefaultSettings, Machines
from django.conf import settings


class ScheduleWidget(forms.Textarea):
    template_name = 'schedule.html'

    def get_context(self, name, value, attrs):
        context = {}
        if self.format_value(value) is None:
            schedule = DefaultSettings.objects.filter(title='default_schedule').first()
            if schedule is None:
                json_value = {}
            else:
                json_value = schedule.value
        else:
            json_value = self.format_value(value)
        context['widget'] = {
            'name': name,
            'is_hidden': self.is_hidden,
            'required': self.is_required,
            'value': json_value,
            'attrs': self.build_attrs(self.attrs, attrs),
            'template_name': self.template_name,
            'url': settings.URL,
            'cnc_all': list(Machines.objects.all().values('id', 'name'))
        }
        return context
