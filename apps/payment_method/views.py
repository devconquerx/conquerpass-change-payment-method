from django.shortcuts import render
from django.http import JsonResponse
from django.views import View
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import json
from .services import StripeService
from services.wordpress_service import WordPressService


@method_decorator(csrf_exempt, name='dispatch')
class ChangePaymentMethodView(View):
    """
    Vista para cambiar el método de pago de un cliente usando Stripe Elements.
    """
    
    def get(self, request, customer_email):
        stripe_service = StripeService()
        
        # Buscar el cliente por email
        customer_result = stripe_service.get_customer_by_email(customer_email)
        if not customer_result['success']:
            return JsonResponse({
                'error': 'Cliente no encontrado con ese email',
                'details': customer_result['error']
            }, status=404)
        
        customer = customer_result['data']
        
        # Crear Setup Intent
        setup_intent_result = stripe_service.create_setup_intent(customer.id)
        if not setup_intent_result['success']:
            return JsonResponse({
                'error': 'Error al crear intent de configuración',
                'details': setup_intent_result['error']
            }, status=500)
        
        context = {
            'customer': customer,
            'customer_email': customer_email,
            'setup_intent_client_secret': setup_intent_result['data']['client_secret'],
            'stripe_publishable_key': settings.STRIPE_PUBLISHABLE_KEY
        }
        
        return render(request, 'payment_method/change_payment_method.html', context)
    
    def post(self, request, customer_email):
        """
        Maneja la confirmación del setup del método de pago.
        """
        try:
            data = json.loads(request.body)
            setup_intent_id = data.get('setup_intent_id')
            
            if not setup_intent_id:
                return JsonResponse({
                    'success': False,
                    'error': 'Setup Intent ID requerido'
                }, status=400)
            
            stripe_service = StripeService()
            intent_result = stripe_service.get_setup_intent(setup_intent_id)
            
            if not intent_result['success']:
                return JsonResponse({
                    'success': False,
                    'error': 'Error al verificar Setup Intent',
                    'details': intent_result['error']
                }, status=500)
            
            intent = intent_result['data']
            
            if intent.status == 'succeeded' and intent.payment_method:
                customer_result = stripe_service.get_customer_by_email(customer_email)
                if customer_result['success']:
                    customer_id = customer_result['data'].id
                    default_result = stripe_service.set_default_payment_method(
                        customer_id, 
                        intent.payment_method
                    )
                    if not default_result['success']:
                        print(f"Warning: No se pudo establecer como predeterminado: {default_result['error']}")
                
                # Actualizar órdenes de WordPress con el nuevo método de pago
                wp_service = WordPressService()
                wp_update_result = wp_service.update_stripe_source_id(
                    email=customer_email,
                    new_payment_method_id=intent.payment_method
                )
                
                # Log del resultado pero no fallar si hay error en WordPress
                if wp_update_result['success']:
                    print(f"WordPress: {wp_update_result['message']}")
                else:
                    print(f"Warning WordPress: {wp_update_result['error']}")
            
            return JsonResponse({
                'success': True,
                'status': intent.status,
                'payment_method': intent.payment_method
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'JSON inválido'
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
