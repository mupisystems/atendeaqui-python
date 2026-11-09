"""Tracker de uma aplicação fictícia, como uma aplicação real escreveria."""
from atendeaqui.contrib.django import EngagementTracker


class FakeTracker(EngagementTracker):
    screen_names = {'employers:job_list': 'Processos'}
    ignored_features = frozenset({'employers:job_score'})  # polling

    def reset(self):
        self.active = True
        self.sent = []
        self.buffer.flush()
        self.sent = []
        self._unnamed_screens.clear()

    def identify(self, user):
        company_id = getattr(user, 'company_id', None)
        if not company_id:
            return None
        return company_id, user.pk, getattr(user, 'full_name', None), getattr(user, 'email', None)

    def is_active(self):
        return self.active

    def send(self, events):
        self.sent.extend(events)

    def written(self):
        """Eventos anotados até agora."""
        self.buffer.flush()
        return self.sent


tracker = FakeTracker(background=False)
