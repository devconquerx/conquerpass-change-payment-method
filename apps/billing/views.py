from django.shortcuts import render
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views import View
from .services import StripeService


class CustomerListView(View):
    """
    Vista para mostrar la lista de clientes de Stripe con paginación.
    """
    
    def get(self, request):
        stripe_service = StripeService()
        
        # Parámetros de paginación
        page = request.GET.get('page', 1)
        limit = int(request.GET.get('limit', 10))
        email_filter = request.GET.get('email', None)
        starting_after = request.GET.get('starting_after', None)
        
        # Consultar clientes desde Stripe
        result = stripe_service.list_customers(
            limit=limit,
            starting_after=starting_after,
            email=email_filter
        )
        
        if not result['success']:
            return JsonResponse({
                'error': 'Error al consultar clientes de Stripe',
                'details': result['error']
            }, status=500)
        
        customers = result['data']
        has_more = result['has_more']
        
        # Preparar datos para el template
        context = {
            'customers': customers,
            'has_more': has_more,
            'current_page': int(page),
            'limit': limit,
            'email_filter': email_filter,
            'next_starting_after': customers[-1].id if customers and has_more else None,
            'prev_ending_before': customers[0].id if customers else None,
        }
        
        # Si es una petición AJAX, devolver JSON
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'customers': [self._serialize_customer(c) for c in customers],
                'has_more': has_more,
                'next_starting_after': context['next_starting_after']
            })
        
        return render(request, 'billing/customer_list.html', context)
    
    def _serialize_customer(self, customer):
        """
        Serializa un objeto Customer de Stripe para JSON.
        """
        return {
            'id': customer.id,
            'email': customer.email,
            'name': customer.name,
            'created': customer.created,
            'description': customer.description,
            'phone': customer.phone,
            'metadata': customer.metadata
        }
