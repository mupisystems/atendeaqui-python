"""Django mínimo para os testes de atendeaqui.contrib.django (sem banco)."""
import pytest

django = pytest.importorskip('django')

from django.conf import settings  # noqa: E402

if not settings.configured:
    settings.configure(
        SECRET_KEY='testes',
        ALLOWED_HOSTS=['testserver'],
        ROOT_URLCONF='tests.contrib_django.urls',
        INSTALLED_APPS=[
            'django.contrib.contenttypes',
            'django.contrib.auth',
            'atendeaqui.contrib.django',
        ],
        ATENDEAQUI_ENGAGEMENT_TRACKER='tests.contrib_django.trackers.tracker',
        USE_TZ=True,
    )
    django.setup()


@pytest.fixture
def tracker():
    """O tracker de teste, zerado: sem eventos anotados nem enviados."""
    from tests.contrib_django.trackers import tracker

    tracker.reset()
    yield tracker
    tracker.reset()
