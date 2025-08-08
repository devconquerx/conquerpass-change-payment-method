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
    
    def get_customer_by_email(self, email: str) -> Dict[str, Any]:
        """
        Busca un cliente por email.
        
        Args:
            email: Email del cliente
            
        Returns:
            Dict con los datos del cliente o error
        """
        try:
            # Buscar cliente por email
            customers = stripe.Customer.list(email=email, limit=1)
            
            if not customers.data:
                return {
                    'success': False,
                    'error': 'Cliente no encontrado con ese email',
                    'error_type': 'NotFound'
                }
            
            return {
                'success': True,
                'data': customers.data[0]
            }
            
        except stripe.error.StripeError as e:
            return {
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__
            }
    
    def create_setup_intent(self, customer_id: str) -> Dict[str, Any]:
        """
        Crea un Setup Intent para configurar métodos de pago usando Stripe Elements.
        
        Args:
            customer_id: ID del cliente en Stripe
            
        Returns:
            Dict con los datos del Setup Intent o error
        """
        try:
            intent = stripe.SetupIntent.create(
                customer=customer_id,
                payment_method_types=['card'],
                usage='off_session'
            )
            
            return {
                'success': True,
                'data': {
                    'id': intent.id,
                    'client_secret': intent.client_secret,
                    'status': intent.status
                }
            }
            
        except stripe.error.StripeError as e:
            return {
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__
            }
    
    def get_setup_intent(self, setup_intent_id: str) -> Dict[str, Any]:
        """
        Obtiene un Setup Intent específico.
        
        Args:
            setup_intent_id: ID del Setup Intent
            
        Returns:
            Dict con los datos del Setup Intent o error
        """
        try:
            intent = stripe.SetupIntent.retrieve(setup_intent_id)
            
            return {
                'success': True,
                'data': intent
            }
            
        except stripe.error.StripeError as e:
            return {
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__
            }
    
    def set_default_payment_method(self, customer_id: str, payment_method_id: str) -> Dict[str, Any]:
        """
        Establece un método de pago como predeterminado para un cliente.
        
        Args:
            customer_id: ID del cliente en Stripe
            payment_method_id: ID del método de pago
            
        Returns:
            Dict con el resultado de la operación
        """
        try:
            stripe.Customer.modify(
                customer_id,
                invoice_settings={
                    'default_payment_method': payment_method_id,
                }
            )
            
            return {
                'success': True,
                'message': 'Método de pago establecido como predeterminado'
            }
            
        except stripe.error.StripeError as e:
            return {
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__
            }