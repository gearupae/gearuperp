"""
Inventory Views - Categories, Warehouses, Items, Stock
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import ListView, CreateView, UpdateView, DetailView
from django.urls import reverse_lazy
from django.db.models import Q, Sum, F, Value, DecimalField, Count, Avg
from django.db import models as db_models
from django.db.models.functions import Coalesce
from django.db import transaction
from decimal import Decimal

from .models import Category, Warehouse, Item, Stock, StockMovement, ConsumableRequest
from .forms import (
    CategoryForm, WarehouseForm, ItemForm, StockAdjustmentForm,
    ConsumableRequestForm, ConsumableRequestApproveForm, ConsumableRequestRejectForm
)
from apps.core.mixins import PermissionRequiredMixin, CreatePermissionMixin, UpdatePermissionMixin
from apps.core.utils import PermissionChecker


# ============ CATEGORY VIEWS ============

class CategoryListView(PermissionRequiredMixin, ListView):
    model = Category
    template_name = 'inventory/category_list.html'
    context_object_name = 'categories'
    module_name = 'inventory'
    permission_type = 'view'
    
    def get_queryset(self):
        queryset = Category.objects.filter(is_active=True)
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(code__icontains=search)
            )
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Categories'
        context['form'] = CategoryForm()
        context['can_create'] = self.request.user.is_superuser or PermissionChecker.has_permission(self.request.user, 'inventory', 'create')
        context['can_edit'] = self.request.user.is_superuser or PermissionChecker.has_permission(self.request.user, 'inventory', 'edit')
        context['can_delete'] = self.request.user.is_superuser or PermissionChecker.has_permission(self.request.user, 'inventory', 'delete')
        return context
    
    def post(self, request, *args, **kwargs):
        if not (request.user.is_superuser or PermissionChecker.has_permission(request.user, 'inventory', 'create')):
            messages.error(request, 'Permission denied.')
            return redirect('inventory:category_list')
        
        form = CategoryForm(request.POST)
        if form.is_valid():
            category = form.save()
            messages.success(request, f'Category {category.name} created.')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
        return redirect('inventory:category_list')


class CategoryUpdateView(UpdatePermissionMixin, UpdateView):
    model = Category
    form_class = CategoryForm
    template_name = 'inventory/category_form.html'
    success_url = reverse_lazy('inventory:category_list')
    module_name = 'inventory'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Edit Category: {self.object.name}'
        return context
    
    def form_valid(self, form):
        messages.success(self.request, f'Category {form.instance.name} updated.')
        return super().form_valid(form)


@login_required
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.user.is_superuser or PermissionChecker.has_permission(request.user, 'inventory', 'delete'):
        category.is_active = False
        category.save()
        messages.success(request, f'Category {category.name} deleted.')
    else:
        messages.error(request, 'Permission denied.')
    return redirect('inventory:category_list')


# ============ WAREHOUSE VIEWS ============

class WarehouseListView(PermissionRequiredMixin, ListView):
    model = Warehouse
    template_name = 'inventory/warehouse_list.html'
    context_object_name = 'warehouses'
    module_name = 'inventory'
    permission_type = 'view'
    
    def get_queryset(self):
        queryset = Warehouse.objects.filter(is_active=True)
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(code__icontains=search)
            )
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Warehouses'
        context['form'] = WarehouseForm()
        context['can_create'] = self.request.user.is_superuser or PermissionChecker.has_permission(self.request.user, 'inventory', 'create')
        context['can_edit'] = self.request.user.is_superuser or PermissionChecker.has_permission(self.request.user, 'inventory', 'edit')
        context['can_delete'] = self.request.user.is_superuser or PermissionChecker.has_permission(self.request.user, 'inventory', 'delete')
        return context
    
    def post(self, request, *args, **kwargs):
        if not (request.user.is_superuser or PermissionChecker.has_permission(request.user, 'inventory', 'create')):
            messages.error(request, 'Permission denied.')
            return redirect('inventory:warehouse_list')
        
        form = WarehouseForm(request.POST)
        if form.is_valid():
            warehouse = form.save()
            messages.success(request, f'Warehouse {warehouse.name} created.')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
        return redirect('inventory:warehouse_list')


class WarehouseUpdateView(UpdatePermissionMixin, UpdateView):
    model = Warehouse
    form_class = WarehouseForm
    template_name = 'inventory/warehouse_form.html'
    success_url = reverse_lazy('inventory:warehouse_list')
    module_name = 'inventory'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Edit Warehouse: {self.object.name}'
        return context
    
    def form_valid(self, form):
        messages.success(self.request, f'Warehouse {form.instance.name} updated.')
        return super().form_valid(form)


@login_required
def warehouse_delete(request, pk):
    warehouse = get_object_or_404(Warehouse, pk=pk)
    if request.user.is_superuser or PermissionChecker.has_permission(request.user, 'inventory', 'delete'):
        warehouse.is_active = False
        warehouse.save()
        messages.success(request, f'Warehouse {warehouse.name} deleted.')
    else:
        messages.error(request, 'Permission denied.')
    return redirect('inventory:warehouse_list')


# ============ ITEM VIEWS ============

class ItemListView(PermissionRequiredMixin, ListView):
    model = Item
    template_name = 'inventory/item_list.html'
    context_object_name = 'items'
    module_name = 'inventory'
    permission_type = 'view'
    paginate_by = 25
    
    def get_queryset(self):
        # Annotate total_stock at database level to ensure fresh data
        queryset = Item.objects.filter(is_active=True).select_related('category').annotate(
            total_stock_calc=Coalesce(
                Sum(
                    'stock_records__quantity',
                    filter=Q(stock_records__warehouse__is_active=True)
                ),
                Value(Decimal('0.00')),
                output_field=DecimalField(max_digits=15, decimal_places=2)
            )
        )
        
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(item_code__icontains=search) |
                Q(name__icontains=search)
            )
        
        category = self.request.GET.get('category')
        if category:
            queryset = queryset.filter(category_id=category)
        
        item_type = self.request.GET.get('item_type')
        if item_type:
            queryset = queryset.filter(item_type=item_type)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Items'
        context['categories'] = Category.objects.filter(is_active=True)
        context['type_choices'] = Item.TYPE_CHOICES
        context['can_create'] = self.request.user.is_superuser or PermissionChecker.has_permission(self.request.user, 'inventory', 'create')
        context['can_edit'] = self.request.user.is_superuser or PermissionChecker.has_permission(self.request.user, 'inventory', 'edit')
        context['can_delete'] = self.request.user.is_superuser or PermissionChecker.has_permission(self.request.user, 'inventory', 'delete')
        
        # Stats
        items = self.get_queryset()
        context['total_items'] = items.count()
        # Use annotation for low stock check
        context['low_stock_count'] = sum(
            1 for item in items 
            if item.item_type == 'product' 
            and (item.total_stock_calc or Decimal('0.00')) < item.minimum_stock
        )
        
        return context


class ItemCreateView(CreatePermissionMixin, CreateView):
    model = Item
    form_class = ItemForm
    template_name = 'inventory/item_form.html'
    success_url = reverse_lazy('inventory:item_list')
    module_name = 'inventory'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Create Item'
        return context
    
    def form_valid(self, form):
        messages.success(self.request, f'Item {form.instance.name} created.')
        return super().form_valid(form)


class ItemUpdateView(UpdatePermissionMixin, UpdateView):
    model = Item
    form_class = ItemForm
    template_name = 'inventory/item_form.html'
    success_url = reverse_lazy('inventory:item_list')
    module_name = 'inventory'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Edit Item: {self.object.name}'
        return context
    
    def form_valid(self, form):
        messages.success(self.request, f'Item {form.instance.name} updated.')
        return super().form_valid(form)


class ItemDetailView(PermissionRequiredMixin, DetailView):
    model = Item
    template_name = 'inventory/item_detail.html'
    context_object_name = 'item'
    module_name = 'inventory'
    permission_type = 'view'
    
    def get_queryset(self):
        # Annotate total_stock at database level to ensure fresh data
        return Item.objects.annotate(
            total_stock_calc=Coalesce(
                Sum(
                    'stock_records__quantity',
                    filter=Q(stock_records__warehouse__is_active=True)
                ),
                Value(Decimal('0.00')),
                output_field=DecimalField(max_digits=15, decimal_places=2)
            )
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Item: {self.object.name}'
        context['stock_records'] = Stock.objects.filter(
            item=self.object,
            warehouse__is_active=True
        ).select_related('warehouse')
        context['movements'] = StockMovement.objects.filter(item=self.object)[:20]
        context['can_edit'] = self.request.user.is_superuser or PermissionChecker.has_permission(self.request.user, 'inventory', 'edit')
        return context


@login_required
def item_delete(request, pk):
    item = get_object_or_404(Item, pk=pk)
    if request.user.is_superuser or PermissionChecker.has_permission(request.user, 'inventory', 'delete'):
        item.is_active = False
        item.save()
        messages.success(request, f'Item {item.name} deleted.')
    else:
        messages.error(request, 'Permission denied.')
    return redirect('inventory:item_list')


# ============ STOCK VIEWS ============

class StockListView(PermissionRequiredMixin, ListView):
    model = Stock
    template_name = 'inventory/stock_list.html'
    context_object_name = 'stocks'
    module_name = 'inventory'
    permission_type = 'view'
    paginate_by = 25
    
    def get_queryset(self):
        queryset = Stock.objects.filter(
            item__is_active=True,
            warehouse__is_active=True
        ).select_related('item', 'warehouse')
        
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(item__name__icontains=search) |
                Q(item__item_code__icontains=search)
            )
        
        warehouse = self.request.GET.get('warehouse')
        if warehouse:
            queryset = queryset.filter(warehouse_id=warehouse)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Stock Levels'
        context['warehouses'] = Warehouse.objects.filter(is_active=True, status='active')
        context['can_adjust'] = self.request.user.is_superuser or PermissionChecker.has_permission(self.request.user, 'inventory', 'edit')
        return context


@login_required
def stock_adjustment(request):
    """Stock adjustment view."""
    if not (request.user.is_superuser or PermissionChecker.has_permission(request.user, 'inventory', 'edit')):
        messages.error(request, 'Permission denied.')
        return redirect('inventory:stock_list')
    
    if request.method == 'POST':
        form = StockAdjustmentForm(request.POST)
        if form.is_valid():
            item = form.cleaned_data['item']
            warehouse = form.cleaned_data['warehouse']
            quantity = Decimal(str(form.cleaned_data['quantity']))
            movement_type = form.cleaned_data['movement_type']
            reference = form.cleaned_data['reference']
            notes = form.cleaned_data['notes']
            
            try:
                with transaction.atomic():
                    # Get or create stock record
                    stock, created = Stock.objects.get_or_create(
                        item=item,
                        warehouse=warehouse,
                        defaults={'quantity': Decimal('0.00')}
                    )
                    
                    # Store old quantity for display
                    old_quantity = stock.quantity
                    
                    # Update stock based on movement type
                    if movement_type == 'in':
                        stock.quantity += quantity
                    elif movement_type == 'out':
                        # Prevent negative stock
                        if stock.quantity < quantity:
                            messages.error(request, f'Insufficient stock. Available: {stock.quantity}, Requested: {quantity}')
                            items = Item.objects.filter(is_active=True).order_by('name')
                            warehouses = Warehouse.objects.filter(is_active=True, status='active').order_by('name')
                            return render(request, 'inventory/stock_adjustment.html', {
                                'title': 'Stock Adjustment',
                                'form': form,
                                'items': items,
                                'warehouses': warehouses,
                            })
                        stock.quantity -= quantity
                    else:  # adjustment
                        stock.quantity = quantity
                    
                    # Save stock with all fields to ensure proper update
                    stock.save()
                    
                    # Create movement record
                    StockMovement.objects.create(
                        item=item,
                        warehouse=warehouse,
                        movement_type=movement_type,
                        quantity=quantity,
                        reference=reference,
                        notes=notes
                    )
                    
                    messages.success(request, f'Stock adjusted for {item.name} at {warehouse.name}. Quantity: {old_quantity} → {stock.quantity}')
                    return redirect('inventory:stock_list')
                    
            except Exception as e:
                messages.error(request, f'Error updating stock: {str(e)}')
                items = Item.objects.filter(is_active=True).order_by('name')
                warehouses = Warehouse.objects.filter(is_active=True, status='active').order_by('name')
                return render(request, 'inventory/stock_adjustment.html', {
                    'title': 'Stock Adjustment',
                    'form': form,
                    'items': items,
                    'warehouses': warehouses,
                })
    else:
        form = StockAdjustmentForm()
    
    # Get items and warehouses for template context
    items = Item.objects.filter(is_active=True).order_by('name')
    warehouses = Warehouse.objects.filter(is_active=True, status='active').order_by('name')
    
    return render(request, 'inventory/stock_adjustment.html', {
        'title': 'Stock Adjustment',
        'form': form,
        'items': items,
        'warehouses': warehouses,
    })


class MovementListView(PermissionRequiredMixin, ListView):
    model = StockMovement
    template_name = 'inventory/movement_list.html'
    context_object_name = 'movements'
    module_name = 'inventory'
    permission_type = 'view'
    paginate_by = 50
    
    def get_queryset(self):
        queryset = StockMovement.objects.filter(
            item__is_active=True
        ).select_related('item', 'warehouse', 'journal_entry')
        
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(item__name__icontains=search) |
                Q(reference__icontains=search) |
                Q(movement_number__icontains=search)
            )
        
        movement_type = self.request.GET.get('type')
        if movement_type:
            queryset = queryset.filter(movement_type=movement_type)
        
        posted = self.request.GET.get('posted')
        if posted == '1':
            queryset = queryset.filter(posted=True)
        elif posted == '0':
            queryset = queryset.filter(posted=False)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Stock Movements'
        context['type_choices'] = StockMovement.MOVEMENT_TYPE_CHOICES
        context['can_post'] = self.request.user.is_superuser or PermissionChecker.has_permission(self.request.user, 'inventory', 'edit')
        
        # Calculate metrics
        all_movements = StockMovement.objects.filter(item__is_active=True)
        context['total_movements'] = all_movements.count()
        context['posted_movements'] = all_movements.filter(posted=True).count()
        context['unposted_movements'] = all_movements.filter(posted=False, total_cost__gt=0).count()
        context['total_value'] = all_movements.filter(posted=True).aggregate(Sum('total_cost'))['total_cost__sum'] or Decimal('0.00')
        
        return context


@login_required
def movement_post_to_accounting(request, pk):
    """Post a stock movement to accounting."""
    movement = get_object_or_404(StockMovement, pk=pk)
    
    if not (request.user.is_superuser or PermissionChecker.has_permission(request.user, 'inventory', 'edit')):
        messages.error(request, 'Permission denied.')
        return redirect('inventory:movement_list')
    
    if movement.posted:
        messages.warning(request, f'Movement {movement.movement_number} already posted to accounting.')
        return redirect('inventory:movement_list')
    
    if movement.total_cost <= 0:
        messages.error(request, f'Movement {movement.movement_number} has no cost value. Update cost before posting.')
        return redirect('inventory:movement_list')
    
    try:
        movement.post_to_accounting(user=request.user)
        messages.success(request, f'Movement {movement.movement_number} posted to accounting. Journal Entry: {movement.journal_entry.entry_number}')
    except Exception as e:
        messages.error(request, f'Error posting to accounting: {str(e)}')
    
    return redirect('inventory:movement_list')


@login_required
def movement_detail(request, pk):
    """View stock movement detail."""
    movement = get_object_or_404(
        StockMovement.objects.select_related('item', 'warehouse', 'to_warehouse', 'journal_entry'),
        pk=pk
    )
    
    context = {
        'title': f'Movement: {movement.movement_number}',
        'movement': movement,
        'can_post': not movement.posted and movement.total_cost > 0 and (
            request.user.is_superuser or PermissionChecker.has_permission(request.user, 'inventory', 'edit')
        ),
    }
    
    if movement.journal_entry:
        context['journal_lines'] = movement.journal_entry.lines.all().select_related('account')
    
    return render(request, 'inventory/movement_detail.html', context)


# ============ CONSUMABLE REQUEST VIEWS ============

class ConsumableRequestListView(PermissionRequiredMixin, ListView):
    """
    List view for consumable requests.
    - Nurses see their own requests
    - Admin/Inventory see all requests
    """
    model = ConsumableRequest
    template_name = 'inventory/consumable_request_list.html'
    context_object_name = 'requests'
    module_name = 'inventory'
    permission_type = 'view'
    paginate_by = 25
    
    def get_queryset(self):
        user = self.request.user
        queryset = ConsumableRequest.objects.filter(is_active=True).select_related(
            'item', 'requested_by', 'warehouse', 'approved_by', 'dispensed_by'
        )
        
        # Non-admins only see their own requests
        if not user.is_superuser and not PermissionChecker.has_permission(user, 'inventory', 'edit'):
            queryset = queryset.filter(requested_by=user)
        
        # Filters
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(request_number__icontains=search) |
                Q(item__name__icontains=search) |
                Q(requested_by__first_name__icontains=search) |
                Q(requested_by__last_name__icontains=search)
            )
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        is_admin = user.is_superuser or PermissionChecker.has_permission(user, 'inventory', 'edit')
        
        context['title'] = 'Consumable Requests'
        context['status_choices'] = ConsumableRequest.STATUS_CHOICES
        context['is_admin'] = is_admin
        
        # Stats (for admins)
        if is_admin:
            all_requests = ConsumableRequest.objects.filter(is_active=True)
            context['pending_count'] = all_requests.filter(status='pending').count()
            context['approved_count'] = all_requests.filter(status='approved').count()
            context['dispensed_count'] = all_requests.filter(status='dispensed').count()
        
        # Create form (for inline creation)
        context['form'] = ConsumableRequestForm()
        
        return context
    
    def post(self, request, *args, **kwargs):
        """Handle inline request creation."""
        form = ConsumableRequestForm(request.POST)
        if form.is_valid():
            consumable_request = form.save(commit=False)
            consumable_request.requested_by = request.user
            consumable_request.save()
            messages.success(request, f'Request {consumable_request.request_number} submitted successfully.')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
        return redirect('inventory:consumable_request_list')


@login_required
def consumable_request_create(request):
    """
    Simple nurse-facing form for creating requests.
    Mobile-friendly, max 4 fields.
    """
    if request.method == 'POST':
        form = ConsumableRequestForm(request.POST)
        if form.is_valid():
            consumable_request = form.save(commit=False)
            consumable_request.requested_by = request.user
            consumable_request.save()
            messages.success(request, f'Request {consumable_request.request_number} submitted!')
            return redirect('inventory:consumable_request_list')
    else:
        form = ConsumableRequestForm()
    
    return render(request, 'inventory/consumable_request_form.html', {
        'title': 'Request Consumable',
        'form': form,
    })


@login_required
def consumable_request_detail(request, pk):
    """View request details."""
    consumable_request = get_object_or_404(
        ConsumableRequest.objects.select_related(
            'item', 'requested_by', 'warehouse', 'approved_by', 'dispensed_by', 'stock_movement'
        ),
        pk=pk
    )
    
    user = request.user
    is_admin = user.is_superuser or PermissionChecker.has_permission(user, 'inventory', 'edit')
    
    # Non-admins can only view their own requests
    if not is_admin and consumable_request.requested_by != user:
        messages.error(request, 'Permission denied.')
        return redirect('inventory:consumable_request_list')
    
    context = {
        'title': f'Request: {consumable_request.request_number}',
        'request_obj': consumable_request,
        'is_admin': is_admin,
    }
    
    # For admin: show approve/dispense forms
    if is_admin and consumable_request.status in ['pending', 'approved']:
        context['approve_form'] = ConsumableRequestApproveForm(
            item=consumable_request.item,
            quantity=consumable_request.quantity
        )
        context['reject_form'] = ConsumableRequestRejectForm()
    
    return render(request, 'inventory/consumable_request_detail.html', context)


@login_required
def consumable_request_approve(request, pk):
    """Admin approves a request."""
    if not (request.user.is_superuser or PermissionChecker.has_permission(request.user, 'inventory', 'edit')):
        messages.error(request, 'Permission denied.')
        return redirect('inventory:consumable_request_list')
    
    consumable_request = get_object_or_404(ConsumableRequest, pk=pk)
    
    if consumable_request.status != 'pending':
        messages.warning(request, f'Request {consumable_request.request_number} is not pending.')
        return redirect('inventory:consumable_request_detail', pk=pk)
    
    if request.method == 'POST':
        form = ConsumableRequestApproveForm(
            request.POST,
            item=consumable_request.item,
            quantity=consumable_request.quantity
        )
        if form.is_valid():
            try:
                warehouse = form.cleaned_data['warehouse']
                admin_notes = form.cleaned_data.get('admin_notes', '')
                consumable_request.admin_notes = admin_notes
                consumable_request.approve(request.user, warehouse)
                messages.success(request, f'Request {consumable_request.request_number} approved.')
            except Exception as e:
                messages.error(request, f'Error approving request: {str(e)}')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    
    return redirect('inventory:consumable_request_detail', pk=pk)


@login_required
def consumable_request_dispense(request, pk):
    """Admin dispenses the consumable (reduces stock)."""
    if not (request.user.is_superuser or PermissionChecker.has_permission(request.user, 'inventory', 'edit')):
        messages.error(request, 'Permission denied.')
        return redirect('inventory:consumable_request_list')
    
    consumable_request = get_object_or_404(ConsumableRequest, pk=pk)
    
    if consumable_request.status not in ['pending', 'approved']:
        messages.warning(request, f'Request {consumable_request.request_number} cannot be dispensed.')
        return redirect('inventory:consumable_request_detail', pk=pk)
    
    if request.method == 'POST':
        form = ConsumableRequestApproveForm(
            request.POST,
            item=consumable_request.item,
            quantity=consumable_request.quantity
        )
        if form.is_valid():
            try:
                warehouse = form.cleaned_data['warehouse']
                consumable_request.dispense(request.user, warehouse)
                messages.success(
                    request, 
                    f'Request {consumable_request.request_number} dispensed. '
                    f'Stock reduced by {consumable_request.quantity} {consumable_request.item.unit}.'
                )
            except Exception as e:
                messages.error(request, f'Error dispensing: {str(e)}')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    
    return redirect('inventory:consumable_request_detail', pk=pk)


@login_required
def consumable_request_reject(request, pk):
    """Admin rejects a request."""
    if not (request.user.is_superuser or PermissionChecker.has_permission(request.user, 'inventory', 'edit')):
        messages.error(request, 'Permission denied.')
        return redirect('inventory:consumable_request_list')
    
    consumable_request = get_object_or_404(ConsumableRequest, pk=pk)
    
    if consumable_request.status not in ['pending', 'approved']:
        messages.warning(request, f'Request {consumable_request.request_number} cannot be rejected.')
        return redirect('inventory:consumable_request_detail', pk=pk)
    
    if request.method == 'POST':
        form = ConsumableRequestRejectForm(request.POST)
        if form.is_valid():
            reason = form.cleaned_data['reason']
            consumable_request.reject(request.user, reason)
            messages.success(request, f'Request {consumable_request.request_number} rejected.')
        else:
            messages.error(request, 'Please provide a rejection reason.')
    
    return redirect('inventory:consumable_request_detail', pk=pk)


# ============ CONSUMABLE REPORTS ============

@login_required
def consumable_dashboard(request):
    """
    Dashboard for consumables showing:
    - Total requests this month
    - Total quantity consumed
    - Total cost
    - Low stock alerts
    """
    if not (request.user.is_superuser or PermissionChecker.has_permission(request.user, 'inventory', 'view')):
        messages.error(request, 'Permission denied.')
        return redirect('dashboard')
    
    from django.utils import timezone
    from datetime import timedelta
    
    today = timezone.localdate()
    month_start = today.replace(day=1)
    
    # This month's requests
    month_requests = ConsumableRequest.objects.filter(
        is_active=True,
        request_date__gte=month_start
    )
    
    # Stats
    total_requests = month_requests.count()
    dispensed_requests = month_requests.filter(status='dispensed')
    total_quantity = dispensed_requests.aggregate(Sum('quantity'))['quantity__sum'] or Decimal('0')
    total_cost = dispensed_requests.aggregate(Sum('total_cost'))['total_cost__sum'] or Decimal('0')
    
    # Low stock consumables
    low_stock_items = []
    consumable_items = Item.objects.filter(
        is_active=True,
        item_type='product',
        status='active'
    )
    for item in consumable_items:
        total_stock = item.total_stock
        if total_stock < item.minimum_stock:
            low_stock_items.append({
                'item': item,
                'current_stock': total_stock,
                'minimum_stock': item.minimum_stock,
                'shortfall': item.minimum_stock - total_stock
            })
    
    # Recent requests
    recent_requests = ConsumableRequest.objects.filter(
        is_active=True
    ).select_related('item', 'requested_by').order_by('-created_at')[:10]
    
    # Top requested items this month
    top_items = dispensed_requests.values('item__name').annotate(
        total_qty=Sum('quantity'),
        total_cost=Sum('total_cost')
    ).order_by('-total_qty')[:5]
    
    context = {
        'title': 'Consumables Dashboard',
        'total_requests': total_requests,
        'pending_requests': month_requests.filter(status='pending').count(),
        'total_quantity': total_quantity,
        'total_cost': total_cost,
        'low_stock_items': low_stock_items,
        'low_stock_count': len(low_stock_items),
        'recent_requests': recent_requests,
        'top_items': top_items,
        'month_name': today.strftime('%B %Y'),
    }
    
    return render(request, 'inventory/consumable_dashboard.html', context)


@login_required
def consumable_monthly_request_report(request):
    """Monthly Request Report - per nurse & total."""
    if not (request.user.is_superuser or PermissionChecker.has_permission(request.user, 'inventory', 'view')):
        messages.error(request, 'Permission denied.')
        return redirect('dashboard')
    
    from django.utils import timezone
    from datetime import date
    
    # Get month from query params
    year = int(request.GET.get('year', timezone.localdate().year))
    month = int(request.GET.get('month', timezone.localdate().month))
    
    month_start = date(year, month, 1)
    if month == 12:
        month_end = date(year + 1, 1, 1)
    else:
        month_end = date(year, month + 1, 1)
    
    # Requests for the month
    requests = ConsumableRequest.objects.filter(
        is_active=True,
        request_date__gte=month_start,
        request_date__lt=month_end
    ).select_related('item', 'requested_by')
    
    # Group by nurse
    nurse_summary = requests.values(
        'requested_by__id',
        'requested_by__first_name',
        'requested_by__last_name',
        'requested_by__username'
    ).annotate(
        total_requests=Count('id'),
        total_quantity=Sum('quantity'),
        total_cost=Sum('total_cost'),
        pending=Count('id', filter=Q(status='pending')),
        approved=Count('id', filter=Q(status='approved')),
        dispensed=Count('id', filter=Q(status='dispensed')),
        rejected=Count('id', filter=Q(status='rejected')),
    ).order_by('-total_requests')
    
    # Totals
    totals = requests.aggregate(
        total_requests=Count('id'),
        total_quantity=Sum('quantity'),
        total_cost=Sum('total_cost'),
    )
    
    context = {
        'title': f'Monthly Request Report - {month_start.strftime("%B %Y")}',
        'nurse_summary': nurse_summary,
        'totals': totals,
        'year': year,
        'month': month,
        'month_name': month_start.strftime('%B %Y'),
        'years': range(2024, timezone.localdate().year + 2),
        'months': [(i, date(2000, i, 1).strftime('%B')) for i in range(1, 13)],
    }
    
    return render(request, 'inventory/consumable_monthly_request_report.html', context)


@login_required
def consumable_monthly_consumption_report(request):
    """Monthly Consumption Report - item-wise quantity used."""
    if not (request.user.is_superuser or PermissionChecker.has_permission(request.user, 'inventory', 'view')):
        messages.error(request, 'Permission denied.')
        return redirect('dashboard')
    
    from django.utils import timezone
    from datetime import date
    
    # Get month from query params
    year = int(request.GET.get('year', timezone.localdate().year))
    month = int(request.GET.get('month', timezone.localdate().month))
    
    month_start = date(year, month, 1)
    if month == 12:
        month_end = date(year + 1, 1, 1)
    else:
        month_end = date(year, month + 1, 1)
    
    # Only dispensed requests count as consumption
    consumption = ConsumableRequest.objects.filter(
        is_active=True,
        status='dispensed',
        request_date__gte=month_start,
        request_date__lt=month_end
    ).values(
        'item__id',
        'item__item_code',
        'item__name',
        'item__unit'
    ).annotate(
        total_quantity=Sum('quantity'),
        total_cost=Sum('total_cost'),
        request_count=Count('id')
    ).order_by('-total_quantity')
    
    # Totals
    totals = ConsumableRequest.objects.filter(
        is_active=True,
        status='dispensed',
        request_date__gte=month_start,
        request_date__lt=month_end
    ).aggregate(
        total_quantity=Sum('quantity'),
        total_cost=Sum('total_cost'),
        total_requests=Count('id'),
    )
    
    context = {
        'title': f'Monthly Consumption Report - {month_start.strftime("%B %Y")}',
        'consumption': consumption,
        'totals': totals,
        'year': year,
        'month': month,
        'month_name': month_start.strftime('%B %Y'),
        'years': range(2024, timezone.localdate().year + 2),
        'months': [(i, date(2000, i, 1).strftime('%B')) for i in range(1, 13)],
    }
    
    return render(request, 'inventory/consumable_monthly_consumption_report.html', context)


@login_required
def consumable_monthly_cost_report(request):
    """Monthly Financial Cost Report - total consumable cost."""
    if not (request.user.is_superuser or PermissionChecker.has_permission(request.user, 'inventory', 'view')):
        messages.error(request, 'Permission denied.')
        return redirect('dashboard')
    
    from django.utils import timezone
    from datetime import date
    
    # Get month from query params
    year = int(request.GET.get('year', timezone.localdate().year))
    month = int(request.GET.get('month', timezone.localdate().month))
    
    month_start = date(year, month, 1)
    if month == 12:
        month_end = date(year + 1, 1, 1)
    else:
        month_end = date(year, month + 1, 1)
    
    # Cost breakdown by item
    cost_breakdown = ConsumableRequest.objects.filter(
        is_active=True,
        status='dispensed',
        request_date__gte=month_start,
        request_date__lt=month_end
    ).values(
        'item__id',
        'item__item_code',
        'item__name',
        'item__category__name'
    ).annotate(
        total_quantity=Sum('quantity'),
        total_cost=Sum('total_cost'),
        avg_unit_cost=Avg('unit_cost')
    ).order_by('-total_cost')
    
    # Daily cost trend
    daily_costs = ConsumableRequest.objects.filter(
        is_active=True,
        status='dispensed',
        request_date__gte=month_start,
        request_date__lt=month_end
    ).values('request_date').annotate(
        daily_cost=Sum('total_cost'),
        daily_qty=Sum('quantity')
    ).order_by('request_date')
    
    # Totals
    totals = ConsumableRequest.objects.filter(
        is_active=True,
        status='dispensed',
        request_date__gte=month_start,
        request_date__lt=month_end
    ).aggregate(
        total_cost=Sum('total_cost'),
        total_quantity=Sum('quantity'),
        total_requests=models.Count('id'),
    )
    
    context = {
        'title': f'Monthly Cost Report - {month_start.strftime("%B %Y")}',
        'cost_breakdown': cost_breakdown,
        'daily_costs': list(daily_costs),
        'totals': totals,
        'year': year,
        'month': month,
        'month_name': month_start.strftime('%B %Y'),
        'years': range(2024, timezone.localdate().year + 2),
        'months': [(i, date(2000, i, 1).strftime('%B')) for i in range(1, 13)],
    }
    
    return render(request, 'inventory/consumable_monthly_cost_report.html', context)

