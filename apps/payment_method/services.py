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
                    'error': 'No encontramos un cliente registrado con esta dirección de email en nuestro sistema de pagos.',
                    'error_type': 'NotFound'
                }
            
            return {
                'success': True,
                'data': customers.data[0]
            }
            
        except stripe.error.StripeError as e:
            # Personalizar mensajes de error según el tipo
            error_message = str(e)
            if 'rate limit' in error_message.lower():
                error_message = 'El sistema está muy ocupado en este momento. Por favor, espera un momento e intenta nuevamente.'
            elif 'network' in error_message.lower():
                error_message = 'Problema de conexión con el servicio de pagos. Por favor, verifica tu conexión e intenta nuevamente.'
            elif 'invalid' in error_message.lower():
                error_message = 'Los datos proporcionados no son válidos. Por favor, verifica la información e intenta nuevamente.'
            else:
                error_message = 'Ha ocurrido un error con el servicio de pagos. Por favor, intenta nuevamente más tarde.'
                
            return {
                'success': False,
                'error': error_message,
                'error_type': type(e).__name__,
                'original_error': str(e)
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
            # Personalizar mensajes de error según el tipo
            error_message = str(e)
            if 'rate limit' in error_message.lower():
                error_message = 'El sistema está muy ocupado en este momento. Por favor, espera un momento e intenta nuevamente.'
            elif 'network' in error_message.lower():
                error_message = 'Problema de conexión con el servicio de pagos. Por favor, verifica tu conexión e intenta nuevamente.'
            elif 'invalid' in error_message.lower():
                error_message = 'Los datos proporcionados no son válidos. Por favor, verifica la información e intenta nuevamente.'
            else:
                error_message = 'Ha ocurrido un error con el servicio de pagos. Por favor, intenta nuevamente más tarde.'
                
            return {
                'success': False,
                'error': error_message,
                'error_type': type(e).__name__,
                'original_error': str(e)
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
            # Personalizar mensajes de error según el tipo
            error_message = str(e)
            if 'rate limit' in error_message.lower():
                error_message = 'El sistema está muy ocupado en este momento. Por favor, espera un momento e intenta nuevamente.'
            elif 'network' in error_message.lower():
                error_message = 'Problema de conexión con el servicio de pagos. Por favor, verifica tu conexión e intenta nuevamente.'
            elif 'invalid' in error_message.lower():
                error_message = 'Los datos proporcionados no son válidos. Por favor, verifica la información e intenta nuevamente.'
            else:
                error_message = 'Ha ocurrido un error con el servicio de pagos. Por favor, intenta nuevamente más tarde.'
                
            return {
                'success': False,
                'error': error_message,
                'error_type': type(e).__name__,
                'original_error': str(e)
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
            # Personalizar mensajes de error según el tipo
            error_message = str(e)
            if 'rate limit' in error_message.lower():
                error_message = 'El sistema está muy ocupado en este momento. Por favor, espera un momento e intenta nuevamente.'
            elif 'network' in error_message.lower():
                error_message = 'Problema de conexión con el servicio de pagos. Por favor, verifica tu conexión e intenta nuevamente.'
            elif 'invalid' in error_message.lower():
                error_message = 'Los datos proporcionados no son válidos. Por favor, verifica la información e intenta nuevamente.'
            else:
                error_message = 'Ha ocurrido un error con el servicio de pagos. Por favor, intenta nuevamente más tarde.'
                
            return {
                'success': False,
                'error': error_message,
                'error_type': type(e).__name__,
                'original_error': str(e)
            }