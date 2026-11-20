"""Rotas mínimas para os testes: uma aplicação, o admin e uma rota sem nome."""
from django.http import HttpResponse
from django.urls import include, path


def page(request, **kwargs):
    return HttpResponse('ok')


employers = ([
    path('', page, name='dashboard'),
    path('vagas/', page, name='job_list'),
    path('vagas/<int:job_id>/remuneracao/', page, name='job_salary'),
    path('vagas/<int:job_id>/score/', page, name='job_score'),
    path('vagas/<int:job_id>/promoção/', page, name='job_promotion'),
], 'employers')

admin = ([path('', page, name='index')], 'admin')

urlpatterns = [
    path('', include(employers)),
    path('admin/', include(admin)),
    path('sem-nome/', page),
]
