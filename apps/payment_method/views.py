from django.shortcuts import render
from django.http import JsonResponse
from django.views import View
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import json
import logging
from .services import StripeService
from services.wordpress_service import WordPressService
from services.dlocal_service import DLocalService
from apps.core.utils import decrypt_email

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class ChangePaymentMethodView(View):
    """
    Vista para cambiar el método de pago de un cliente usando Stripe Elements.
    """
    
    def get(self, request, encrypted_email):
        try:
            customer_email = decrypt_email(encrypted_email)
        except Exception:
            logging.info('NO SE ENCONTRO LA ORDEN')
            return render(request, 'payment_method/customer_not_found.html', {
                'customer_email': 'Email inválido',
                'error_details': 'El enlace proporcionado no es válido.'
            }, status=400)
        
        # Primero consultar WordPress para obtener órdenes estructuradas
        wp_service = WordPressService()
        structured_result = wp_service.get_customer_orders_structured(customer_email)
        
        if not structured_result['success']:
            return render(request, 'payment_method/error.html', {
                'customer_email': customer_email,
                'error_title': 'Error consultando información',
                'error_message': 'No pudimos consultar tu información de órdenes. Por favor, verifica que el email sea correcto.',
                'error_details': structured_result['error']
            }, status=500)
        
        # Obtener información del método de pago usando la nueva API
        payment_info = wp_service.get_customer_payment_methods(structured_result['structured_orders'])
        
        
        # Si no tiene órdenes, mostrar error
        if structured_result['summary']['total_installments'] == 0:
            return render(request, 'payment_method/customer_not_found.html', {
                'customer_email': customer_email,
                'error_details': 'No se encontraron órdenes asociadas a este email.'
            }, status=404)
        
        

        # Preparar información para mostrar el método de pago actual
        latest_installment = payment_info.get('latest_processing_installment')
        current_payment_info = {
            'method': payment_info['payment_method'],
            'display_name': self._get_payment_method_display_name(payment_info['payment_method']),
            'latest_order_id': latest_installment['id'] if latest_installment else None,
            'latest_order_date': latest_installment['date_created_gmt'] if latest_installment else None,
            'has_stripe': structured_result['summary']['payment_methods']['stripe'],
            'has_dlocal': structured_result['summary']['payment_methods']['dlocal'],
            'orders_count': {
                'total': structured_result['summary']['total_installments'],
                'parent_orders': structured_result['summary']['parent_orders_count']
            },
            'payment_details': payment_info['payment_details']
        }
        
        # Preparar contexto base
        context = {
            'customer_email': customer_email,
            'encrypted_email': encrypted_email,
            'current_payment_info': current_payment_info,
            'primary_payment_method': payment_info['payment_method']
        }
        
        # Solo proceder con Stripe si el usuario actualmente usa Stripe
        if payment_info['payment_method'] == 'stripe':
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
            # Usuario usa dLocal o método no identificado como Stripe
            dlocal_details = payment_info['payment_details']
            context.update({
                'can_change_payment': True,  # Puede cambiar con el nuevo flujo
                'dlocal_info': f'Este usuario utiliza {payment_info["payment_method"]} como método de pago.',
                'use_dlocal_flow': True  # Flag para indicar que use el flujo de dLocal
            })
            
            # Si tiene los metadatos de suscripción dLocal, obtener detalles
            if dlocal_details.get('current_plan_id') and dlocal_details.get('current_subscription_id'):
                dlocal_service = DLocalService()
                
                plan_id = dlocal_details['current_plan_id']
                subscription_id = dlocal_details['current_subscription_id']
                
                details_result = dlocal_service.get_subscription_details(plan_id, subscription_id)
                
                if details_result['success']:
                    subscription_data = details_result['data']
                    
                    # Obtener el monto correcto de la siguiente cuota
                    latest_processing_installment = payment_info.get('latest_processing_installment')
                    
                    if latest_processing_installment:
                        current_payment_number = latest_processing_installment.get('payment_number', 0)
                        
                        # Buscar la siguiente cuota en las órdenes estructuradas
                        next_installment = None
                        for order_group in structured_result['structured_orders']:
                            for installment in order_group['installments']:
                                installment_payment_number = installment.get('payment_number', 0)
                                if installment_payment_number == current_payment_number + 1:
                                    next_installment = installment
                                    break
                            if next_installment:
                                break
                        
                        if next_installment:
                            # Reemplazar el monto del next_payment con el de la siguiente cuota
                            next_amount = float(next_installment['total_amount'])
                            subscription_data['next_payment']['amount'] = next_amount
                            subscription_data['plan']['amount'] = next_amount
                    
                    context['dlocal_subscription_details'] = [subscription_data]
                else:
                    context['dlocal_subscription_details'] = []
            else:
                context['dlocal_subscription_details'] = []
        
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
                
                # Actualizar _stripe_source_id para todas las cuotas que ya lo tengan
                wp_service = WordPressService()
                update_result = wp_service.update_stripe_source_id_for_customer(
                    email=customer_email,
                    new_payment_method_id=intent.payment_method
                )
                
                # Log del resultado pero no fallar si hay error en WordPress
                if update_result['success']:
                    updated_count = update_result['summary']['updated_count']
                    skipped_count = update_result['summary']['skipped_count']
                    print(f"WordPress: Actualizadas {updated_count} cuotas, omitidas {skipped_count}")
                else:
                    print(f"Warning WordPress: {update_result['error']}")
            
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


@method_decorator(csrf_exempt, name='dispatch')
class InitiateDLocalPaymentChangeView(View):
    """
    Vista para iniciar el proceso de cambio de método de pago para usuarios de dLocal.
    Crea un plan con la misma configuración y redirige al checkout.
    """
    
    def post(self, request, encrypted_email):
        """
        Inicia el proceso de cambio de método de pago para dLocal.
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
            plan_id = data.get('plan_id')
            subscription_id = data.get('subscription_id')
            
            if not plan_id or not subscription_id:
                return JsonResponse({
                    'success': False,
                    'error': 'Información de suscripción incompleta.'
                }, status=400)
            
            # Obtener detalles de la suscripción actual
            dlocal_service = DLocalService()
            subscription_details = dlocal_service.get_subscription_details(plan_id, subscription_id)
            
            if not subscription_details['success']:
                return JsonResponse({
                    'success': False,
                    'error': 'No se pudo obtener información de la suscripción actual.',
                    'details': subscription_details['error']
                }, status=500)
            
            subscription_data = subscription_details['data']
            plan = subscription_data['plan']
            next_payment = subscription_data.get('next_payment', {})
            
            # Obtener órdenes estructuradas para encontrar la última cuota wc-processing
            wp_service = WordPressService()
            structured_result = wp_service.get_customer_orders_structured(customer_email)
            
            if structured_result['success']:
                payment_info = wp_service.get_customer_payment_methods(structured_result['structured_orders'])
                latest_processing_installment = payment_info.get('latest_processing_installment')
                
                if latest_processing_installment:
                    # Buscar la próxima cuota después de la última wc-processing
                    current_payment_number = latest_processing_installment.get('payment_number', 0)
                    
                    # Buscar la siguiente cuota en todas las órdenes estructuradas
                    next_installment = None
                    for order_group in structured_result['structured_orders']:
                        for installment in order_group['installments']:
                            installment_payment_number = installment.get('payment_number', 0)
                            if installment_payment_number == current_payment_number + 1:
                                next_installment = installment
                                break
                        if next_installment:
                            break
                    
                    if next_installment:
                        # Usar el monto de la siguiente cuota en lugar del next_payment de dLocal
                        next_payment_amount = float(next_installment['total_amount'])
                    else:
                        # Si no hay siguiente cuota, usar el monto del next_payment de dLocal
                        next_payment_amount = next_payment['amount']
                else:
                    # Si no hay cuota wc-processing, usar el monto del next_payment de dLocal
                    next_payment_amount = next_payment['amount']
            else:
                # Si hay error obteniendo órdenes, usar el monto del next_payment de dLocal
                next_payment_amount = next_payment['amount']
            
            if not next_payment.get('can_estimate'):
                return JsonResponse({
                    'success': False,
                    'error': 'No se puede determinar la próxima fecha de pago. Contacta soporte para asistencia.'
                }, status=400)
            
            # Crear un nuevo plan con la misma configuración
            new_plan_data = {
                'name': f"{plan['name']} - Cambio de Método de Pago",
                'description': f"Cambio de método de pago",
                'country': plan.get('country'),
                'currency': plan['currency'],
                'amount': next_payment_amount,
                'frequency_type': plan['frequency_type'],
                'frequency_value': plan.get('frequency_value', 1),
                'success_url': f"{request.build_absolute_uri('/').rstrip('/')}/metodo-pago/change/{encrypted_email}/success/",
                'back_url': f"{request.build_absolute_uri('/').rstrip('/')}/metodo-pago/change/{encrypted_email}/",
                'error_url': f"{request.build_absolute_uri('/').rstrip('/')}/metodo-pago/change/{encrypted_email}/error/",
                'notification_url': settings.CONQUERPASS_DLOCAL_WEBHOOK
            }
            
            logger.info(f"[DLOCAL PAYMENT CHANGE] Creating new plan with amount: {next_payment_amount}")
            
            # Remover campos opcionales si están vacíos
            if not new_plan_data['country']:
                del new_plan_data['country']
            
            logger.info(f"[DLOCAL PAYMENT CHANGE] Sending plan data to dLocal: {new_plan_data}")
            
            create_plan_result = dlocal_service.create_plan(new_plan_data)
            
            logger.info(f"[DLOCAL PAYMENT CHANGE] dLocal create_plan response: {create_plan_result}")
            
            if not create_plan_result['success']:
                logger.error(f"[DLOCAL PAYMENT CHANGE] Failed to create plan: {create_plan_result.get('error', 'Unknown error')}")
                return JsonResponse({
                    'success': False,
                    'error': 'No se pudo crear el plan para el cambio de método de pago.',
                    'details': create_plan_result.get('error', 'Error desconocido')
                }, status=500)
            
            new_plan = create_plan_result['data']
            checkout_url = new_plan.get('subscribe_url')
            
            if not checkout_url:
                return JsonResponse({
                    'success': False,
                    'error': 'No se pudo generar la URL de pago.'
                }, status=500)
            
            # Guardar la ID del nuevo plan como metadato en la orden padre
            structured_result = wp_service.get_customer_orders_structured(customer_email)
            
            if structured_result['success']:
                payment_info = wp_service.get_customer_payment_methods(structured_result['structured_orders'])
                parent_order_id = payment_info.get('latest_processing_parent_order_id')
                
                if parent_order_id:
                    # Guardar la ID del nuevo plan temporalmente en la orden padre
                    update_result = wp_service.update_order_meta(
                        order_id=parent_order_id,
                        meta_key='_dlocal_temp_new_plan_id',
                        meta_value=str(new_plan['id'])
                    )
                    
                    # Log del resultado pero no fallar si hay error en WordPress
                    if update_result['success']:
                        logger.info(f"Guardada nueva plan ID {new_plan['id']} para orden padre {parent_order_id}")
                    else:
                        logger.warning(f"Error guardando nueva plan ID en WordPress: {update_result['error']}")
                else:
                    logger.warning("No se encontró orden padre para guardar la nueva plan ID")
            else:
                logger.warning(f"Error obteniendo órdenes para guardar nueva plan ID: {structured_result['error']}")
            
            # Guardar información del proceso en la sesión o base de datos si es necesario
            # Por simplicidad, se incluye en la respuesta
            
            return JsonResponse({
                'success': True,
                'checkout_url': checkout_url,
                'new_plan_id': new_plan['id'],
                'new_plan_token': new_plan['plan_token'],
                'original_plan_id': plan_id,
                'original_subscription_id': subscription_id,
                'next_payment_info': {
                    'amount': next_payment_amount,
                    'currency': next_payment['currency'],
                    'estimated_date': next_payment.get('estimated_date')
                }
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Los datos enviados no son válidos.'
            }, status=400)
        except Exception as e:
            logger.error(f"Error iniciando cambio de método de pago dLocal para {customer_email}: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Ha ocurrido un error inesperado. Por favor, intenta nuevamente.'
            }, status=500)


class PaymentChangeSuccessView(View):
    def get(self, request, encrypted_email):
        try:
            customer_email = decrypt_email(encrypted_email)
            context = {
                'customer_email': customer_email,
                'success': True,
                'message': 'Tu método de pago ha sido actualizado exitosamente.',
            }
            return render(request, 'payment_method/payment_change_result.html', context)
        except Exception as e:
            logger.error(f"Error en página de éxito para {encrypted_email}: {str(e)}")
            return redirect('payment_method:cambiar_metodo_pago', encrypted_email=encrypted_email)


class PaymentChangeErrorView(View):
    def get(self, request, encrypted_email):
        try:
            customer_email = decrypt_email(encrypted_email)
            context = {
                'customer_email': customer_email,
                'success': False,
                'message': 'Hubo un problema al actualizar tu método de pago. Por favor, intenta nuevamente.',
            }
            return render(request, 'payment_method/payment_change_result.html', context)
        except Exception as e:
            logger.error(f"Error en página de error para {encrypted_email}: {str(e)}")
            return redirect('payment_method:cambiar_metodo_pago', encrypted_email=encrypted_email)
