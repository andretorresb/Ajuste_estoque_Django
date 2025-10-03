# estoque/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('empresas/', views.listar_empresas, name='listar_empresas'),
    path('health/', views.health, name='estoque-health'),
    path('produtos/', views.produtos_list, name='produtos-list'),
    path('produtos/<int:idproduto>/', views.produto_detail, name='produto-detail'),                      
    path('ajustar_lote/', views.ajustar_lote, name= 'ajustar_lote'),
    path('inventario/', views.criar_inventario_view  , name= 'criar_inventario_view'),
    
]
