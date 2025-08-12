from django.shortcuts import render
from django.http import JsonResponse
from django.views import View
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import json
from .services import StripeService
from services.wordpress_service import WordPressService
from apps.core.utils import decrypt_email


@method_decorator(csrf_exempt, name='dispatch')
class ChangePaymentMethodView(View):
    """
    Vista para cambiar el método de pago de un cliente usando Stripe Elements.
    """
    
    def get(self, request, encrypted_email):
        try:
            customer_email = decrypt_email(encrypted_email)
        except Exception:
            return render(request, 'payment_method/customer_not_found.html', {
                'customer_email': 'Email inválido',
                'error_details': 'El enlace proporcionado no es válido.'
            }, status=400)
        
        # Primero consultar WordPress para obtener información del método de pago actual
        wp_service = WordPressService()
        payment_methods_result = wp_service.get_customer_payment_methods(customer_email)
        
        if not payment_methods_result['success']:
            return render(request, 'payment_method/error.html', {
                'customer_email': customer_email,
                'error_title': 'Error consultando información',
                'error_message': 'No pudimos consultar tu información de órdenes. Por favor, verifica que el email sea correcto.',
                'error_details': payment_methods_result['error']
            }, status=500)
        
        # Obtener información del método de pago
        primary_payment_method = payment_methods_result['primary_payment_method']
        payment_methods_info = payment_methods_result['payment_methods']
        latest_order = payment_methods_result['latest_order']
        orders_count = payment_methods_result['orders_count']
        
        # Si no tiene órdenes, mostrar error
        if orders_count['total'] == 0:
            return render(request, 'payment_method/customer_not_found.html', {
                'customer_email': customer_email,
                'error_details': 'No se encontraron órdenes asociadas a este email.'
            }, status=404)
        
        # Preparar información para mostrar el método de pago actual
        current_payment_info = {
            'method': primary_payment_method,
            'display_name': self._get_payment_method_display_name(primary_payment_method),
            'latest_order_id': latest_order['id'] if latest_order else None,
            'latest_order_date': latest_order['date_created_gmt'] if latest_order else None,
            'has_stripe': payment_methods_info['stripe'],
            'has_dlocal': payment_methods_info['dlocal'],
            'orders_count': orders_count
        }
        
        # Preparar contexto base
        context = {
            'customer_email': customer_email,
            'encrypted_email': encrypted_email,
            'current_payment_info': current_payment_info,
            'primary_payment_method': primary_payment_method
        }
        
        # Solo proceder con Stripe si el usuario actualmente usa Stripe o no tiene método definido
        if primary_payment_method in ['stripe', 'unknown', 'other']:
            stripe_service = StripeService()
            
            # Buscar cliente en Stripe
            customer_result = stripe_service.get_customer_by_email(customer_email)
            if not customer_result['success']:
                return render(request, 'payment_method/customer_not_found.html', {
                    'customer_email': customer_email,
                    'error_details': 'No se encontró una cuenta de Stripe asociada a este email.'
                }, status=404)
            
            customer = customer_result['data']
            
            # Crear Setup Intent para Stripe
            setup_intent_result = stripe_service.create_setup_intent(customer.id)
            if not setup_intent_result['success']:
                return render(request, 'payment_method/error.html', {
                    'customer_email': customer_email,
                    'error_title': 'Error de configuración de pago',
                    'error_message': 'No pudimos preparar el sistema para configurar tu método de pago. Por favor, inténtalo de nuevo más tarde.',
                    'error_details': setup_intent_result['error']
                }, status=500)
            
            # Agregar información de Stripe al contexto
            context.update({
                'customer': customer,
                'setup_intent_client_secret': setup_intent_result['data']['client_secret'],
                'stripe_publishable_key': settings.STRIPE_PUBLISHABLE_KEY,
                'can_change_payment': True
            })
        else:
            # Usuario usa dLocal, mostrar solo información
            context.update({
                'can_change_payment': False,
                'dlocal_info': 'Este usuario utiliza dLocal como método de pago.'
            })
        
        return render(request, 'payment_method/change_payment_method.html', context)
    
    def _get_payment_method_display_name(self, payment_method):
        """
        Convierte el nombre del método de pago a un nombre más amigable.
        """
        method_names = {
            'stripe': 'Stripe (Tarjeta de Crédito/Débito)',
            'dlocal': 'dLocal (Pagos Locales)',
            'unknown': 'Método no identificado',
            'other': 'Otro método de pago'
        }
        return method_names.get(payment_method, payment_method.capitalize())
    
    def post(self, request, encrypted_email):
        """
        Maneja la confirmación del setup del método de pago.
        """
        try:
            customer_email = decrypt_email(encrypted_email)
        except Exception:
            return JsonResponse({
                'success': False,
                'error': 'El enlace proporcionado no es válido.'
            }, status=400)
            
        try:
            data = json.loads(request.body)
            setup_intent_id = data.get('setup_intent_id')
            
            if not setup_intent_id:
                return JsonResponse({
                    'success': False,
                    'error': 'Información de pago incompleta. Por favor, intenta nuevamente.'
                }, status=400)
            
            stripe_service = StripeService()
            intent_result = stripe_service.get_setup_intent(setup_intent_id)
            
            if not intent_result['success']:
                return JsonResponse({
                    'success': False,
                    'error': 'No pudimos verificar la información de pago. Por favor, intenta nuevamente.',
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
                'error': 'Los datos enviados no son válidos. Por favor, recarga la página e intenta nuevamente.'
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': 'Ha ocurrido un error inesperado. Por favor, intenta nuevamente o contacta soporte si el problema persiste.'
            }, status=500)
