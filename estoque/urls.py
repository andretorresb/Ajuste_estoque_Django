# estoque/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('health/', views.health, name='estoque-health'),
    path('produtos/', views.produtos_list, name='produtos-list'),                   # GET ?query=..&limit=..
    path('produtos/<int:idproduto>/', views.produto_detail, name='produto-detail'), # GET detalhe
    path('ajustar/', views.ajustar, name='estoque-ajustar'),                        # POST ajuste
    
]
