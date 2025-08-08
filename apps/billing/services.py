import stripe
from django.conf import settings
from typing import Dict, List, Any, Optional


class StripeService:
    """
    Servicio para interactuar con la API de Stripe.
    Similar a un servicio de Angular, centraliza todas las llamadas a la API externa.
    """
    
    def __init__(self):
        stripe.api_key = settings.STRIPE_SECRET_KEY
    
    def list_customers(self, limit: int = 10, starting_after: Optional[str] = None, 
                      email: Optional[str] = None) -> Dict[str, Any]:
        """
        Obtiene la lista de clientes de Stripe.
        
        Args:
            limit: Número de clientes a retornar (1-100, default 10)
            starting_after: ID del cliente después del cual empezar (para paginación)
            email: Filtrar por email específico
            
        Returns:
            Dict con los datos de la respuesta de Stripe
        """
        try:
            params = {'limit': limit}
            
            if starting_after:
                params['starting_after'] = starting_after
                
            if email:
                params['email'] = email
            
            response = stripe.Customer.list(**params)
            
            return {
                'success': True,
                'data': response.data,
                'has_more': response.has_more,
                'total_count': getattr(response, 'total_count', None),
            }
            
        except stripe.error.StripeError as e:
            return {
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__
            }
    
    def get_customer(self, customer_id: str) -> Dict[str, Any]:
        """
        Obtiene un cliente específico por ID.
        
        Args:
            customer_id: ID del cliente en Stripe
            
        Returns:
            Dict con los datos del cliente o error
        """
        try:
            customer = stripe.Customer.retrieve(customer_id)
            
            return {
                'success': True,
                'data': customer
            }
            
        except stripe.error.StripeError as e:
            return {
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__
            }