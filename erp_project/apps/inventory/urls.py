"""
Inventory URL configuration.
"""
from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    # Categories
    path('categories/', views.CategoryListView.as_view(), name='category_list'),
    path('categories/<int:pk>/edit/', views.CategoryUpdateView.as_view(), name='category_edit'),
    path('categories/<int:pk>/delete/', views.category_delete, name='category_delete'),
    
    # Warehouses
    path('warehouses/', views.WarehouseListView.as_view(), name='warehouse_list'),
    path('warehouses/<int:pk>/edit/', views.WarehouseUpdateView.as_view(), name='warehouse_edit'),
    path('warehouses/<int:pk>/delete/', views.warehouse_delete, name='warehouse_delete'),
    
    # Items
    path('items/', views.ItemListView.as_view(), name='item_list'),
    path('items/create/', views.ItemCreateView.as_view(), name='item_create'),
    path('items/<int:pk>/', views.ItemDetailView.as_view(), name='item_detail'),
    path('items/<int:pk>/edit/', views.ItemUpdateView.as_view(), name='item_edit'),
    path('items/<int:pk>/delete/', views.item_delete, name='item_delete'),
    
    # Stock
    path('stock/', views.StockListView.as_view(), name='stock_list'),
    path('stock/adjustment/', views.stock_adjustment, name='stock_adjustment'),
    
    # Movements
    path('movements/', views.MovementListView.as_view(), name='movement_list'),
    path('movements/<int:pk>/', views.movement_detail, name='movement_detail'),
    path('movements/<int:pk>/post/', views.movement_post_to_accounting, name='movement_post'),
]


