import requests
from django.conf import settings
from typing import Dict, List, Any, Optional
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class DLocalService:
    """
    Servicio para interactuar con la API de dLocal Go.
    Maneja todas las operaciones relacionadas con planes, suscripciones, pagos y ejecuciones.
    """
    
    def __init__(self):
        """
        Inicializa el servicio con la configuración de dLocal.
        """
        self.api_key = getattr(settings, 'DLOCAL_API_KEY', '')
        self.secret_key = getattr(settings, 'DLOCAL_SECRET_KEY', '')
        self.base_url = getattr(settings, 'DLOCAL_BASE_URL', 'https://api-sbx.dlocalgo.com')
        
        if not self.api_key or not self.secret_key:
            logger.warning("dLocal credentials not configured properly")
        
        # Headers base para todas las requests
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}:{self.secret_key}'
        }
    
    def _make_request(self, method: str, endpoint: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Hace una petición HTTP a la API de dLocal.
        
        Args:
            method: Método HTTP (GET, POST, PATCH, etc.)
            endpoint: Endpoint de la API (sin base URL)
            data: Datos para enviar en el body (opcional)
            
        Returns:
            Dict con la respuesta de la API o información de error
        """
        try:
            url = f"{self.base_url}{endpoint}"
            
            if method.upper() == 'GET':
                response = requests.get(url, headers=self.headers, params=data)
            elif method.upper() == 'POST':
                response = requests.post(url, headers=self.headers, json=data)
            elif method.upper() == 'PATCH':
                response = requests.patch(url, headers=self.headers, json=data)
            else:
                return {
                    'success': False,
                    'error': f'Método HTTP {method} no soportado',
                    'error_type': 'UnsupportedMethod'
                }
            
            # Verificar status code
            if response.status_code in [200, 201]:
                return {
                    'success': True,
                    'data': response.json(),
                    'status_code': response.status_code
                }
            else:
                error_data = {}
                try:
                    error_data = response.json()
                except:
                    error_data = {'message': response.text}
                
                return {
                    'success': False,
                    'error': error_data.get('message', f'Error HTTP {response.status_code}'),
                    'error_type': 'HTTPError',
                    'status_code': response.status_code,
                    'error_data': error_data
                }
                
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Error de conexión con dLocal API: {str(e)}")
            return {
                'success': False,
                'error': 'Error de conexión con el servicio de pagos. Por favor, intenta nuevamente.',
                'error_type': 'ConnectionError',
                'original_error': str(e)
            }
        except requests.exceptions.Timeout as e:
            logger.error(f"Timeout en dLocal API: {str(e)}")
            return {
                'success': False,
                'error': 'El servicio de pagos está tardando demasiado en responder. Por favor, intenta nuevamente.',
                'error_type': 'TimeoutError',
                'original_error': str(e)
            }
        except Exception as e:
            logger.error(f"Error inesperado en dLocal API: {str(e)}")
            return {
                'success': False,
                'error': 'Ha ocurrido un error inesperado con el servicio de pagos.',
                'error_type': type(e).__name__,
                'original_error': str(e)
            }
    
    def get_subscription_executions(self, plan_id: int, subscription_id: int, 
                                  page: int = 1, page_size: int = 10) -> Dict[str, Any]:
        """
        Obtiene todas las ejecuciones (pagos) de una suscripción específica.
        
        Args:
            plan_id: ID del plan
            subscription_id: ID de la suscripción
            page: Número de página (default: 1)
            page_size: Cantidad de elementos por página (default: 10)
            
        Returns:
            Dict con las ejecuciones encontradas o información de error
        """
        endpoint = f"/v1/subscription/plan/{plan_id}/subscription/{subscription_id}/execution/all"
        params = {
            'page': page,
            'page_size': page_size
        }
        
        return self._make_request('GET', endpoint, params)
    
    def get_single_execution(self, subscription_id: int, execution_id: str) -> Dict[str, Any]:
        """
        Obtiene una ejecución específica de una suscripción.
        
        Args:
            subscription_id: ID de la suscripción
            execution_id: ID de la ejecución (ej: ST-xxxxxxxxxxxxxxx-0)
            
        Returns:
            Dict con los datos de la ejecución o información de error
        """
        endpoint = f"/v1/subscription/{subscription_id}/execution/{execution_id}"
        
        return self._make_request('GET', endpoint)
    
    def get_subscription_details(self, plan_id: int, subscription_id: int) -> Dict[str, Any]:
        """
        Obtiene los detalles de una suscripción específica.
        Utiliza las ejecuciones para determinar información adicional.
        
        Args:
            plan_id: ID del plan
            subscription_id: ID de la suscripción
            
        Returns:
            Dict con los detalles de la suscripción incluyendo próxima cuota
        """
        # Obtener ejecuciones de la suscripción
        executions_result = self.get_subscription_executions(plan_id, subscription_id)
        
        if not executions_result['success']:
            return executions_result
        
        executions_data = executions_result['data']
        executions = executions_data.get('data', [])
        
        if not executions:
            return {
                'success': False,
                'error': 'No se encontraron ejecuciones para esta suscripción',
                'error_type': 'NoExecutionsFound'
            }
        
        # Obtener información de la suscripción del primer execution
        first_execution = executions[0]
        subscription = first_execution.get('subscription', {})
        plan = subscription.get('plan', {})
        
        # Analizar ejecuciones para determinar próxima cuota
        next_payment_info = self._calculate_next_payment(executions, plan)
        
        return {
            'success': True,
            'data': {
                'subscription': subscription,
                'plan': plan,
                'executions': executions,
                'executions_count': len(executions),
                'next_payment': next_payment_info,
                'total_elements': executions_data.get('total_elements', len(executions)),
                'can_change_payment_method': True
            }
        }
    
    def _calculate_next_payment(self, executions: List[Dict], plan: Dict) -> Dict[str, Any]:
        """
        Calcula cuándo será el próximo pago basado en las ejecuciones y la frecuencia del plan.
        
        Args:
            executions: Lista de ejecuciones de la suscripción
            plan: Información del plan
            
        Returns:
            Dict con información del próximo pago
        """
        try:
            if not executions or not plan:
                return {
                    'estimated_date': None,
                    'amount': plan.get('amount', 0),
                    'currency': plan.get('currency', 'USD'),
                    'can_estimate': False,
                    'reason': 'Información insuficiente'
                }
            
            # Obtener la última ejecución exitosa
            successful_executions = [
                ex for ex in executions 
                if ex.get('status') == 'COMPLETED'
            ]
            
            if not successful_executions:
                # Si no hay pagos exitosos, usar la fecha programada de la suscripción
                subscription = executions[0].get('subscription', {})
                scheduled_date = subscription.get('scheduled_date')
                
                if scheduled_date:
                    return {
                        'estimated_date': scheduled_date,
                        'amount': plan.get('amount', 0),
                        'currency': plan.get('currency', 'USD'),
                        'can_estimate': True,
                        'reason': 'Basado en fecha programada inicial',
                        'is_first_payment': True
                    }
                
                return {
                    'estimated_date': None,
                    'amount': plan.get('amount', 0),
                    'currency': plan.get('currency', 'USD'),
                    'can_estimate': False,
                    'reason': 'No hay pagos exitosos ni fecha programada'
                }
            
            # Ordenar por fecha de creación (más reciente primero)
            successful_executions.sort(
                key=lambda x: x.get('created_at', ''), 
                reverse=True
            )
            
            last_payment = successful_executions[0]
            last_payment_date_str = last_payment.get('created_at')
            
            if not last_payment_date_str:
                return {
                    'estimated_date': None,
                    'amount': plan.get('amount', 0),
                    'currency': plan.get('currency', 'USD'),
                    'can_estimate': False,
                    'reason': 'Fecha de último pago no disponible'
                }
            
            # Parsear fecha del último pago
            try:
                # Formato esperado: 2023-05-26T14:16:38
                last_payment_date = datetime.fromisoformat(
                    last_payment_date_str.replace('Z', '+00:00')
                )
            except ValueError:
                # Intentar otros formatos
                try:
                    last_payment_date = datetime.strptime(
                        last_payment_date_str.split('T')[0], 
                        '%Y-%m-%d'
                    )
                except ValueError:
                    return {
                        'estimated_date': None,
                        'amount': plan.get('amount', 0),
                        'currency': plan.get('currency', 'USD'),
                        'can_estimate': False,
                        'reason': 'Formato de fecha inválido'
                    }
            
            # Calcular próxima fecha según frecuencia
            frequency_type = plan.get('frequency_type', '').upper()
            frequency_value = plan.get('frequency_value', 1)
            
            if frequency_type == 'DAILY':
                next_payment_date = last_payment_date + timedelta(days=frequency_value)
            elif frequency_type == 'WEEKLY':
                next_payment_date = last_payment_date + timedelta(weeks=frequency_value)
            elif frequency_type == 'MONTHLY':
                # Aproximación: 30 días por mes
                next_payment_date = last_payment_date + timedelta(days=30 * frequency_value)
            elif frequency_type == 'YEARLY':
                # Aproximación: 365 días por año
                next_payment_date = last_payment_date + timedelta(days=365 * frequency_value)
            else:
                return {
                    'estimated_date': None,
                    'amount': plan.get('amount', 0),
                    'currency': plan.get('currency', 'USD'),
                    'can_estimate': False,
                    'reason': f'Frecuencia no reconocida: {frequency_type}'
                }
            
            return {
                'estimated_date': next_payment_date.isoformat(),
                'amount': plan.get('amount', 0),
                'currency': plan.get('currency', 'USD'),
                'can_estimate': True,
                'reason': f'Calculado basado en último pago exitoso ({frequency_type.lower()})',
                'last_payment_date': last_payment_date_str,
                'frequency': {
                    'type': frequency_type,
                    'value': frequency_value
                },
                'is_first_payment': False
            }
            
        except Exception as e:
            logger.error(f"Error calculando próximo pago: {str(e)}")
            return {
                'estimated_date': None,
                'amount': plan.get('amount', 0) if plan else 0,
                'currency': plan.get('currency', 'USD') if plan else 'USD',
                'can_estimate': False,
                'reason': f'Error en cálculo: {str(e)}'
            }
    
    def create_plan(self, plan_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Crea un nuevo plan en dLocal.
        
        Args:
            plan_data: Datos del plan a crear
            
        Returns:
            Dict con el plan creado o información de error
        """
        endpoint = "/v1/subscription/plan"
        
        return self._make_request('POST', endpoint, plan_data)
    
    def cancel_subscription(self, plan_id: int, subscription_id: int) -> Dict[str, Any]:
        """
        Cancela una suscripción específica.
        
        Args:
            plan_id: ID del plan
            subscription_id: ID de la suscripción
            
        Returns:
            Dict con el resultado de la cancelación
        """
        endpoint = f"/v1/subscription/plan/{plan_id}/subscription/{subscription_id}/deactivate"
        
        return self._make_request('PATCH', endpoint)
    
    def test_connection(self) -> Dict[str, Any]:
        """
        Prueba la conexión con la API de dLocal.
        
        Returns:
            Dict con el resultado de la prueba de conexión
        """
        endpoint = "/v1/me"
        
        result = self._make_request('GET', endpoint)
        
        if result['success']:
            return {
                'success': True,
                'message': 'Conexión exitosa con dLocal API'
            }
        else:
            return {
                'success': False,
                'error': f"Error conectando con dLocal API: {result['error']}",
                'error_type': result.get('error_type', 'Unknown')
            }