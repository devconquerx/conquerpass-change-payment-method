import pymysql
from django.conf import settings
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)


class WordPressService:
    """
    Servicio global para interactuar con la base de datos de WordPress/WooCommerce.
    Maneja todas las operaciones relacionadas con órdenes, metadatos y datos de WordPress.
    """
    
    def __init__(self):
        """
        Inicializa el servicio con la configuración de base de datos de WordPress.
        """
        host = getattr(settings, 'WORDPRESS_DB_HOST', 'localhost')
        port = getattr(settings, 'WORDPRESS_DB_PORT', 3306)
        
        # Configuración base
        self.wp_db_config = {
            'user': getattr(settings, 'WORDPRESS_DB_USER', ''),
            'password': getattr(settings, 'WORDPRESS_DB_PASSWORD', ''),
            'database': getattr(settings, 'WORDPRESS_DB_NAME', ''),
            'charset': 'utf8mb4'
        }
        
        # Determinar si es socket Unix o conexión TCP
        if host.startswith('/') or host.endswith('.sock'):
            # Es un socket Unix
            self.wp_db_config['unix_socket'] = host
        else:
            # Es una conexión TCP normal
            self.wp_db_config['host'] = host
            self.wp_db_config['port'] = port if port else 3306
    
    def _get_connection(self):
        """
        Obtiene una conexión a la base de datos de WordPress.
        
        Returns:
            pymysql.Connection: Conexión a la base de datos
            
        Raises:
            Exception: Si no se puede conectar a la base de datos
        """
        try:
            connection = pymysql.connect(**self.wp_db_config)
            return connection
        except Exception as e:
            logger.error(f"Error conectando a WordPress DB: {str(e)}")
            raise
    
    def test_connection(self) -> Dict[str, Any]:
        """
        Prueba la conexión a la base de datos de WordPress.
        
        Returns:
            Dict con el resultado de la prueba de conexión
        """
        try:
            connection = self._get_connection()
            
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                
                return {
                    'success': True,
                    'message': 'Conexión exitosa a WordPress DB'
                }
                
        except Exception as e:
            logger.error(f"Error probando conexión a WordPress DB: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__
            }
        finally:
            if 'connection' in locals():
                connection.close()
    
    def update_order_meta(self, order_id: int, meta_key: str, meta_value: str) -> Dict[str, Any]:
        """
        Actualiza o inserta un metadato específico de una orden.
        
        Args:
            order_id (int): ID de la orden
            meta_key (str): Clave del metadato
            meta_value (str): Valor del metadato
            
        Returns:
            Dict con el resultado de la operación
        """
        try:
            connection = self._get_connection()
            
            with connection.cursor() as cursor:
                # Verificar si el meta ya existe
                check_query = """
                    SELECT id FROM wp_wc_orders_meta
                    WHERE order_id = %s AND meta_key = %s
                """
                
                cursor.execute(check_query, (order_id, meta_key))
                existing_meta = cursor.fetchone()
                
                if existing_meta:
                    # Actualizar meta existente
                    update_query = """
                        UPDATE wp_wc_orders_meta
                        SET meta_value = %s
                        WHERE order_id = %s AND meta_key = %s
                    """
                    cursor.execute(update_query, (meta_value, order_id, meta_key))
                    operation = 'updated'
                else:
                    # Insertar nuevo meta
                    insert_query = """
                        INSERT INTO wp_wc_orders_meta (order_id, meta_key, meta_value)
                        VALUES (%s, %s, %s)
                    """
                    cursor.execute(insert_query, (order_id, meta_key, meta_value))
                    operation = 'inserted'
                
                connection.commit()
                
                return {
                    'success': True,
                    'message': f'Meta {meta_key} {operation} exitosamente para orden {order_id}',
                    'operation': operation,
                    'order_id': order_id,
                    'meta_key': meta_key,
                    'meta_value': meta_value
                }
                
        except Exception as e:
            logger.error(f"Error actualizando meta para orden {order_id}: {str(e)}")
            if 'connection' in locals():
                connection.rollback()
            return {
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__,
                'order_id': order_id
            }
        finally:
            if 'connection' in locals():
                connection.close()
    
    def get_customer_orders_structured(self, email: str) -> Dict[str, Any]:
        """
        Obtiene las órdenes estructuradas de un cliente, priorizando la orden principal más reciente.
        
        Args:
            email (str): Email del cliente
            
        Returns:
            Dict con las órdenes estructuradas y resumen
        """
        try:
            # Obtener órdenes principales ordenadas por ID descendente (más reciente primero)
            parent_orders = self._get_parent_orders_with_metadata(email)
            
            
            if not parent_orders:
                return {
                    'success': True,
                    'structured_orders': [],
                    'summary': {
                        'total_installments': 0,
                        'parent_orders_count': 0,
                        'payment_methods': {'stripe': False, 'dlocal': False}
                    }
                }
            
            structured_orders = []
            total_installments = 0
            payment_methods = {'stripe': False, 'dlocal': False}
            
            # Procesar cada orden principal (ya ordenadas por fecha DESC)
            for parent_order in parent_orders:
                # Obtener cuotas de esta orden principal
                installments = self._get_installments_with_metadata(parent_order['id'])
                
                # Contar cuotas y detectar métodos de pago
                total_installments += len(installments)
                
                for installment in installments:
                    if installment.get('metadata_dict', {}).get('_stripe_customer_id'):
                        payment_methods['stripe'] = True
                    if installment.get('metadata_dict', {}).get('_dlocal_current_subscription_id'):
                        payment_methods['dlocal'] = True
                
                structured_orders.append({
                    'parent_order': parent_order,
                    'installments': installments
                })
            
            return {
                'success': True,
                'structured_orders': structured_orders,
                'summary': {
                    'total_installments': total_installments,
                    'parent_orders_count': len(parent_orders),
                    'payment_methods': payment_methods
                }
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo órdenes estructuradas para {email}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'structured_orders': [],
                'summary': {
                    'total_installments': 0,
                    'parent_orders_count': 0,
                    'payment_methods': {'stripe': False, 'dlocal': False}
                }
            }
    
    def get_customer_payment_methods(self, structured_orders: List[Dict]) -> Dict[str, Any]:
        """
        Determina el método de pago actual basado en la última cuota wc-processing.
        
        Args:
            structured_orders: Lista de órdenes estructuradas (madre → cuotas)
            
        Returns:
            Dict con información completa del método de pago del cliente
        """
        
        # Buscar la última cuota con estado wc-processing y su orden madre asociada
        latest_processing_installment = None
        latest_date = None
        parent_order_of_latest_installment = None
        
        for structured_order in structured_orders:
            for installment in structured_order['installments']:
                if installment['status'] == 'wc-processing':
                    installment_date = installment['date_created_gmt']
                    if not latest_date or installment_date > latest_date:
                        latest_date = installment_date
                        latest_processing_installment = installment
                        parent_order_of_latest_installment = structured_order['parent_order']
        
        # Determinar método de pago y extraer metadatos relevantes
        payment_method = 'unknown'
        payment_details = {}
        
        if latest_processing_installment:
            installment_metadata = latest_processing_installment['metadata_dict']
            parent_metadata = parent_order_of_latest_installment['metadata_dict'] if parent_order_of_latest_installment else {}
            order_payment_method = latest_processing_installment.get('payment_method', '')
            
            # PRIORIDAD 1: Usar el payment_method de la orden directamente
            if order_payment_method == 'dlocal':
                payment_method = 'dlocal'
                
                # Buscar metadatos dLocal primero en la cuota, luego en la orden madre
                dlocal_plan_id = installment_metadata.get('_dlocal_current_plan_id') or parent_metadata.get('_dlocal_current_plan_id')
                dlocal_subscription_id = installment_metadata.get('_dlocal_current_subscription_id') or parent_metadata.get('_dlocal_current_subscription_id')
                
                payment_details = {
                    'current_plan_id': dlocal_plan_id,
                    'current_subscription_id': dlocal_subscription_id
                }
                
            elif order_payment_method == 'stripe':
                payment_method = 'stripe'
                payment_details = {
                    'customer_id': installment_metadata.get('_stripe_customer_id'),
                    'source_id': installment_metadata.get('_stripe_source_id')
                }
            # PRIORIDAD 2: Verificar por metadatos específicos (fallback)
            elif installment_metadata.get('_stripe_customer_id') and installment_metadata.get('_stripe_source_id'):
                payment_method = 'stripe'
                payment_details = {
                    'customer_id': installment_metadata.get('_stripe_customer_id'),
                    'source_id': installment_metadata.get('_stripe_source_id')
                }
            elif (installment_metadata.get('_dlocal_current_subscription_id') and installment_metadata.get('_dlocal_current_plan_id')) or \
                 (parent_metadata.get('_dlocal_current_subscription_id') and parent_metadata.get('_dlocal_current_plan_id')):
                payment_method = 'dlocal'
                
                # Buscar metadatos dLocal primero en la cuota, luego en la orden madre
                dlocal_plan_id = installment_metadata.get('_dlocal_current_plan_id') or parent_metadata.get('_dlocal_current_plan_id')
                dlocal_subscription_id = installment_metadata.get('_dlocal_current_subscription_id') or parent_metadata.get('_dlocal_current_subscription_id')
                
                payment_details = {
                    'current_plan_id': dlocal_plan_id,
                    'current_subscription_id': dlocal_subscription_id
                }
        
        return {
            'payment_method': payment_method,
            'payment_details': payment_details,
            'latest_processing_installment': latest_processing_installment,
            'latest_processing_parent_order_id': parent_order_of_latest_installment['id'] if parent_order_of_latest_installment else None,
            'has_active_payment': payment_method != 'unknown'
        }

    def _get_parent_orders_with_metadata(self, email: str) -> List[Dict[str, Any]]:
        """
        Obtiene todas las órdenes principales (asp_shop_plan) del usuario con todos sus metadatos.
        
        Args:
            email (str): Email del cliente
            
        Returns:
            Lista de órdenes principales con metadatos
        """
        try:
            connection = self._get_connection()
            
            with connection.cursor(pymysql.cursors.DictCursor) as cursor:
                query = """
                    SELECT 
                        o.id,
                        o.status,
                        o.date_created_gmt,
                        o.billing_email,
                        o.total_amount,
                        o.payment_method,
                        o.payment_method_title,
                        o.type,
                        GROUP_CONCAT(
                            CONCAT(om.meta_key, ':', om.meta_value) 
                            SEPARATOR '||'
                        ) as metadata
                    FROM wp_wc_orders o
                    LEFT JOIN wp_wc_orders_meta om ON o.id = om.order_id
                    WHERE o.billing_email = %s AND o.type = 'asp_shop_plan'
                    GROUP BY o.id, o.status, o.date_created_gmt, o.billing_email, o.total_amount, o.payment_method, o.payment_method_title, o.type
                    ORDER BY o.id DESC, o.date_created_gmt DESC
                """
                
                cursor.execute(query, (email,))
                orders = cursor.fetchall()
                
                # Procesar metadatos - consultando por separado para evitar truncamiento de GROUP_CONCAT
                for order in orders:
                    order_id = order['id']
                    
                    # Consulta separada para metadatos de esta orden específica
                    metadata_query = """
                        SELECT meta_key, meta_value 
                        FROM wp_wc_orders_meta 
                        WHERE order_id = %s
                    """
                    cursor.execute(metadata_query, (order_id,))
                    metadata_rows = cursor.fetchall()
                    
                    metadata_dict = {}
                    for row in metadata_rows:
                        metadata_dict[row['meta_key']] = row['meta_value']
                    
                    order['metadata_dict'] = metadata_dict
                    
                return orders
                
        except Exception as e:
            logger.error(f"Error obteniendo órdenes principales para {email}: {str(e)}")
            return []
        finally:
            if 'connection' in locals():
                connection.close()

    def _get_installments_with_metadata(self, parent_order_id: int) -> List[Dict[str, Any]]:
        """
        Obtiene todas las cuotas (shop_order) de una orden principal con todos sus metadatos.
        
        Args:
            parent_order_id (int): ID de la orden principal
            
        Returns:
            Lista de cuotas ordenadas por _asp_upp_payment_number
        """
        try:
            connection = self._get_connection()
            
            with connection.cursor(pymysql.cursors.DictCursor) as cursor:
                query = """
                    SELECT 
                        o.id,
                        o.status,
                        o.date_created_gmt,
                        o.billing_email,
                        o.total_amount,
                        o.payment_method,
                        o.payment_method_title,
                        o.type,
                        GROUP_CONCAT(
                            CONCAT(om.meta_key, ':', om.meta_value) 
                            SEPARATOR '||'
                        ) as metadata
                    FROM wp_wc_orders o
                    LEFT JOIN wp_wc_orders_meta om ON o.id = om.order_id
                    LEFT JOIN wp_wc_orders_meta om_parent ON o.id = om_parent.order_id 
                        AND om_parent.meta_key = '_asp_upp_schedule_payment'
                    WHERE o.type = 'shop_order' AND (
                        om_parent.meta_value = %s OR 
                        o.id = %s
                    )
                    GROUP BY o.id, o.status, o.date_created_gmt, o.billing_email, o.total_amount, o.payment_method, o.payment_method_title, o.type
                    ORDER BY CAST(
                        COALESCE(
                            (SELECT meta_value FROM wp_wc_orders_meta WHERE order_id = o.id AND meta_key = '_asp_upp_payment_number'),
                            '0'
                        ) AS UNSIGNED
                    ) ASC
                """
                
                # La primera cuota siempre tiene ID = parent_order_id - 1
                first_installment_id = parent_order_id - 1
                cursor.execute(query, (parent_order_id, first_installment_id))
                installments = cursor.fetchall()
                
                # Procesar metadatos - consultando por separado para evitar truncamiento de GROUP_CONCAT
                for installment in installments:
                    order_id = installment['id']
                    
                    # Consulta separada para metadatos de esta orden específica
                    metadata_query = """
                        SELECT meta_key, meta_value 
                        FROM wp_wc_orders_meta 
                        WHERE order_id = %s
                    """
                    cursor.execute(metadata_query, (order_id,))
                    metadata_rows = cursor.fetchall()
                    
                    metadata_dict = {}
                    for row in metadata_rows:
                        metadata_dict[row['meta_key']] = row['meta_value']
                    
                    installment['metadata_dict'] = metadata_dict
                    installment['payment_number'] = int(metadata_dict.get('_asp_upp_payment_number', 0))
                    
                return installments
                
        except Exception as e:
            logger.error(f"Error obteniendo cuotas para orden {parent_order_id}: {str(e)}")
            return []
        finally:
            if 'connection' in locals():
                connection.close()

    def get_customer_orders_structured(self, email: str) -> Dict[str, Any]:
        """
        Método centralizado para obtener órdenes estructuradas: orden madre → cuotas.
        
        Args:
            email (str): Email del cliente
            
        Returns:
            Dict con órdenes estructuradas y resumen
        """
        try:
            # Obtener órdenes principales
            parent_orders = self._get_parent_orders_with_metadata(email)
            
            structured_orders = []
            all_installments = []
            payment_methods = {'stripe': False, 'dlocal': False, 'other': False}
            
            for parent_order in parent_orders:
                # Obtener cuotas de esta orden principal
                installments = self._get_installments_with_metadata(parent_order['id'])
                
                # Clasificar métodos de pago basado en metadatos
                for installment in installments:
                    all_installments.append(installment)
                    metadata = installment['metadata_dict']
                    
                    # Detectar métodos de pago por metadatos
                    has_stripe = any(key.startswith('_stripe_') for key in metadata.keys())
                    has_dlocal = any(key.startswith('_dlocal_') for key in metadata.keys())
                    
                    if has_stripe:
                        payment_methods['stripe'] = True
                    elif has_dlocal:
                        payment_methods['dlocal'] = True
                    else:
                        payment_methods['other'] = True
                
                structured_orders.append({
                    'parent_order': parent_order,
                    'installments': installments,
                    'installments_count': len(installments)
                })
            
            # Determinar método de pago principal
            primary_payment_method = 'unknown'
            if payment_methods['dlocal']:
                primary_payment_method = 'dlocal'
            elif payment_methods['stripe']:
                primary_payment_method = 'stripe'
            elif payment_methods['other']:
                primary_payment_method = 'other'
            
            return {
                'success': True,
                'email': email,
                'structured_orders': structured_orders,
                'summary': {
                    'parent_orders_count': len(parent_orders),
                    'total_installments': len(all_installments),
                    'payment_methods': payment_methods,
                    'primary_payment_method': primary_payment_method
                }
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo órdenes estructuradas para {email}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__,
                'email': email
            }
    

    def get_customer_orders_summary(self, email: str) -> Dict[str, Any]:
        """
        Obtiene un resumen completo de las órdenes de un cliente usando el enfoque estructurado.
        
        Args:
            email (str): Email del cliente
            
        Returns:
            Dict con el resumen de órdenes del cliente
        """
        try:
            # Usar el nuevo método estructurado
            structured_result = self.get_customer_orders_structured(email)
            if not structured_result['success']:
                return structured_result
            
            structured_orders = structured_result['structured_orders']
            
            # Obtener método de pago actual usando la nueva función pura
            payment_info = self.get_customer_payment_methods(structured_orders)
            
            return {
                'success': True,
                'email': email,
                'structured_data': structured_result,
                'payment_info': payment_info,
                'summary': {
                    'parent_orders': structured_result['summary']['parent_orders_count'],
                    'total_installments': structured_result['summary']['total_installments'],
                    'current_payment_method': payment_info['payment_method'],
                    'has_active_payment': payment_info['has_active_payment']
                }
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo resumen para {email}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__,
                'email': email
            }
    
    def update_stripe_source_id_for_customer(self, email: str, new_payment_method_id: str) -> Dict[str, Any]:
        """
        Actualiza el _stripe_source_id solo para las cuotas que ya lo tengan.
        No inserta el metadato si no existe, solo actualiza los existentes.
        
        Args:
            email (str): Email del cliente
            new_payment_method_id (str): Nuevo payment method ID de Stripe
            
        Returns:
            Dict con el resultado de la operación
        """
        try:
            # Obtener órdenes estructuradas del cliente
            structured_result = self.get_customer_orders_structured(email)
            if not structured_result['success']:
                return {
                    'success': False,
                    'error': 'No se pudieron obtener las órdenes del cliente',
                    'details': structured_result.get('error', 'Error desconocido')
                }
            
            updated_orders = []
            skipped_orders = []
            
            # Recorrer todas las órdenes estructuradas
            for order_group in structured_result['structured_orders']:
                parent_order = order_group['parent_order']
                installments = order_group['installments']
                
                # PRIMERO: Procesar la orden padre
                parent_order_id = parent_order['id']
                parent_metadata = parent_order.get('metadata_dict', {})
                
                # Actualizar la orden padre solo si ya tiene _stripe_source_id
                if '_stripe_source_id' in parent_metadata:
                    current_source_id = parent_metadata.get('_stripe_source_id')
                    
                    update_result = self.update_order_meta(
                        order_id=parent_order_id,
                        meta_key='_stripe_source_id',
                        meta_value=new_payment_method_id
                    )
                    
                    if update_result['success']:
                        updated_orders.append({
                            'order_id': parent_order_id,
                            'order_type': 'parent',
                            'old_source_id': current_source_id,
                            'new_source_id': new_payment_method_id
                        })
                    else:
                        skipped_orders.append({
                            'order_id': parent_order_id,
                            'order_type': 'parent',
                            'reason': f"Error actualizando: {update_result.get('error', 'Error desconocido')}"
                        })
                else:
                    skipped_orders.append({
                        'order_id': parent_order_id,
                        'order_type': 'parent',
                        'reason': 'No tiene _stripe_source_id existente'
                    })
                
                # SEGUNDO: Procesar cuotas (installments) - ordenadas por ID ascendente para empezar desde la primera
                sorted_installments = sorted(installments, key=lambda x: x['id'])
                
                for installment in sorted_installments:
                    order_id = installment['id']
                    metadata = installment.get('metadata_dict', {})
                    
                    # Solo actualizar si ya tiene _stripe_source_id
                    if '_stripe_source_id' in metadata:
                        current_source_id = metadata.get('_stripe_source_id')
                        
                        update_result = self.update_order_meta(
                            order_id=order_id,
                            meta_key='_stripe_source_id',
                            meta_value=new_payment_method_id
                        )
                        
                        if update_result['success']:
                            updated_orders.append({
                                'order_id': order_id,
                                'order_type': 'installment',
                                'old_source_id': current_source_id,
                                'new_source_id': new_payment_method_id
                            })
                        else:
                            skipped_orders.append({
                                'order_id': order_id,
                                'order_type': 'installment',
                                'reason': f"Error actualizando: {update_result.get('error', 'Error desconocido')}"
                            })
                    else:
                        skipped_orders.append({
                            'order_id': order_id,
                            'order_type': 'installment',
                            'reason': 'No tiene _stripe_source_id existente'
                        })
            
            return {
                'success': True,
                'message': f'Actualización completada para {email}',
                'summary': {
                    'updated_count': len(updated_orders),
                    'skipped_count': len(skipped_orders),
                    'total_orders_processed': len(updated_orders) + len(skipped_orders)
                },
                'updated_orders': updated_orders,
                'skipped_orders': skipped_orders,
                'email': email,
                'new_payment_method_id': new_payment_method_id
            }
            
        except Exception as e:
            logger.error(f"Error actualizando _stripe_source_id para {email}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__,
                'email': email
            }