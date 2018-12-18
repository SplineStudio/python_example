from django.utils import timezone
from django.core.management.base import BaseCommand
from django.conf import settings

from login.models import (Machines, Cnc_state, Cnc_state_in_time)
from machine_params.views import get_machine_data

import requests
import json


class Command(BaseCommand):
    args = ''
    help = 'handle cnc'

    def __init__(self):
        self.data_context_type = [
            ('id', int),  # primary key in database
            ('ip_address', str),  # ip address for cnc
            ('port', int)
        ]
        self.models_json = Machines.objects.filter().values('id', 'ip_address', 'port', 'state_id')
        self.models = Machines.objects.filter()
        self.COUNT_HANDEL = 1
        self.cnc = 0
        self.RUN_STATE = 0
        self.AUT_STATE = 0
        self.EME_STATE = 0
        self.state_mix = 0
        self.common_state = 0
        self.change_state_old_date = 0

        self.status_change = False

        # main state
        self.STATE_WORK = 1
        self.STATE_PAUSE = 2
        self.STATE_NOT_WORK = 3

        self.STATE_WORK__IN_TIME = 4
        self.STATE_WORK__NOT_IN_TIME = 5
        self.STATE_NOT_WORK__IN_TIME = 6
        self.STATE_NOT_WORK__NOT_IN_TIME = 7

        # status from cnc
        self.status_work = (3, 1)
        self.status_work2 = (0, 4)
        self.status_work3 = (2, 1)

        self.status_disconnect = -16

        self.status_emergency_stop = 1
        self.status_emergency_restart = 2

        self.status_pause = (2, 5)

        self.status_not_work = (0, 1)
        self.status_not_work2 = (0, 0)

        super().__init__()

    def handle(self, *args, **options):
        for i in range(self.COUNT_HANDEL):
            for model in self.models_json:
                if self.check_model_context_type(model, self.data_context_type):
                    self.status_change = False
                    state_model = get_machine_data(model.get('ip_address'), model.get('port'), model.get('id'))
                    self.context_parse(state_model=state_model)
                    self.sync_cnc_db()

    @staticmethod
    def check_model_context_type(model, meta_data):
        for md_item in meta_data:
            if model.get(md_item[0]) is None and not isinstance(model.get(md_item[0]), md_item[1]):
                break
        else:
            return True
        return False

    def context_parse(self, state_model):
        result = state_model[1]
        self.cnc = self.models.filter(id=state_model[0]).first()
        if result.get('run') is None:
            self.RUN_STATE = int(result.get('error'))
        else:
            self.RUN_STATE = int(result.get('run'))
            self.AUT_STATE = int(result.get('aut'))
            self.EME_STATE = int(result.get('emergency'))
            self.state_mix = (self.RUN_STATE, self.AUT_STATE)
        self.common_state = int(self.cnc.state.id)
        self.status_change = False

    def sync_cnc_db(self):
        if self.handle_state_not_work():
            self.save_state_db()
        elif self.handle_state_work():
            self.save_state_db()
        elif self.handle_state_pause():
            self.save_state_db()
        else:
            self.check_state_in_time()

    def handle_state_work(self):
        if self.state_mix == self.status_work or self.state_mix == self.status_work2 or \
                self.state_mix == self.status_work3:
            if self.common_state != self.STATE_WORK:
                self.cnc.state_id = self.STATE_WORK
                self.change_state_old_date = self.cnc.change_state
                self.cnc.change_state = timezone.now()
                self.status_change = True
            return True
        return False

    def handle_state_not_work(self):
        state = False
        if self.RUN_STATE == self.status_disconnect and self.common_state != self.STATE_NOT_WORK:
            state = True
        elif self.EME_STATE == self.status_emergency_stop and self.common_state != self.STATE_NOT_WORK:
            state = True
        elif self.state_mix == self.status_not_work or self.state_mix == self.status_not_work2:
            if self.common_state != self.STATE_NOT_WORK:
                state = True
        if state:
            self.cnc.state_id = self.STATE_NOT_WORK
            self.change_state_old_date = self.cnc.change_state
            self.cnc.change_state = timezone.now()
            self.status_change = True
            return True
        return False

    def handle_state_pause(self):
        state = False
        if self.EME_STATE == self.status_emergency_restart and self.common_state != self.STATE_PAUSE:
            state = True
        elif self.state_mix == self.status_pause and self.common_state != self.STATE_PAUSE:
            state = True
        elif self.state_mix == self.status_work or self.state_mix == self.status_work2 or \
                self.state_mix == self.status_work3:
            if self.common_state != self.STATE_PAUSE and self.RUN_STATE != -16:
                state = True
        if state:
            self.cnc.state_id = self.STATE_PAUSE
            self.change_state_old_date = self.cnc.change_state
            self.cnc.change_state = timezone.now()
            self.status_change = True
            return True
        return False

    def save_state_db(self):
        self.check_state_in_time()
        self.cnc.save()
        if self.status_change:

            self.save_state_change_to_db()
            url = "{}/send_socket".format(settings.URL)
            requests.post(url=url, data=json.dumps({"id": self.cnc.id}))

    def save_state_change_to_db(self):
        Cnc_state.objects.create(state_id=self.cnc.state.id, machine_id=self.cnc.id,
                                 start_date=self.change_state_old_date)

    def check_state_in_time(self):
        NOW = timezone.now()
        HOUR = int(NOW.hour)
        MIN = int(NOW.minute)

        day_of_week = int(NOW.strftime("%w"))

        day_of_week_str = ''
        if day_of_week == 0:
            day_of_week_str = 'sun'
        elif day_of_week == 1:
            day_of_week_str = 'mon'
        elif day_of_week == 2:
            day_of_week_str = 'tue'
        elif day_of_week == 3:
            day_of_week_str = 'wed'
        elif day_of_week == 4:
            day_of_week_str = 'thu'
        elif day_of_week == 5:
            day_of_week_str = 'fri'
        elif day_of_week == 6:
            day_of_week_str = 'sat'
        schedule = json.loads(self.cnc.schedule)
        if day_of_week_str in schedule:
            HOUR_mix = ''
            if MIN < 30:
                HOUR_mix = str(HOUR) + ":00"
            elif MIN > 30:
                HOUR_mix = str(HOUR) + ":30"
            if HOUR_mix in schedule[day_of_week_str]:
                STATE = True
            else:
                STATE = False
        else:
            STATE = False
        state_for_save = 0
        if self.cnc.state.id == self.STATE_WORK and STATE:
            state_for_save = self.STATE_WORK__IN_TIME
        elif self.cnc.state.id == self.STATE_WORK and not STATE:
            state_for_save = self.STATE_WORK__NOT_IN_TIME
        elif self.cnc.state.id == self.STATE_NOT_WORK and STATE:
            state_for_save = self.STATE_NOT_WORK__IN_TIME
        elif self.cnc.state.id == self.STATE_NOT_WORK and not STATE:
            state_for_save = self.STATE_NOT_WORK__NOT_IN_TIME

        if self.cnc.state_in_time.id != state_for_save:
            last = Cnc_state_in_time.objects.filter(machine_id=self.cnc.id, end_date=None).first()
            if last is None:
                Cnc_state_in_time.objects.create(machine_id=self.cnc.id, state_id=state_for_save,
                                                 start_date=timezone.now())
            else:
                last.end_date = timezone.now()
                last.save()
                Cnc_state_in_time.objects.create(machine_id=self.cnc.id, state_id=state_for_save,
                                                 start_date=timezone.now())
            self.cnc.state_in_time_id = state_for_save
            self.cnc.save()
