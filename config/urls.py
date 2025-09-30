# config/urls.py 
from django.contrib import admin
from django.urls import path, include
from estoque.views import usuarios_list, usuarios_auth

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('web.urls')),                 # página inicial (index)
    path('api/estoque/', include('estoque.urls')), # rotas do app estoque
    path('api/usuarios/', usuarios_list, name='usuarios-list'),  # lista usuários ATIVOS
    path('api/usuarios/auth/', usuarios_auth, name='usuarios-auth'),
]
