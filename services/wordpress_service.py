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
    
    def get_orders_by_email(self, email: str) -> Dict[str, Any]:
        """
        Obtiene todas las órdenes de WooCommerce para un email específico.
        
        Args:
            email (str): Email del cliente
            
        Returns:
            Dict con las órdenes encontradas o información de error
        """
        try:
            connection = self._get_connection()
            
            with connection.cursor(pymysql.cursors.DictCursor) as cursor:
                query = """
                    SELECT id, status, date_created_gmt, billing_email, total_amount
                    FROM wp_wc_orders 
                    WHERE billing_email = %s
                    ORDER BY date_created_gmt DESC
                """
                
                cursor.execute(query, (email,))
                orders = cursor.fetchall()
                
                return {
                    'success': True,
                    'data': orders,
                    'count': len(orders)
                }
                
        except Exception as e:
            logger.error(f"Error obteniendo órdenes para {email}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__
            }
        finally:
            if 'connection' in locals():
                connection.close()
    
    def get_orders_with_stripe_source_meta(self, email: str) -> Dict[str, Any]:
        """
        Obtiene órdenes de un usuario que ya tienen el meta _stripe_source_id.
        
        Args:
            email (str): Email del cliente
            
        Returns:
            Dict con las órdenes que tienen _stripe_source_id o información de error
        """
        try:
            connection = self._get_connection()
            
            with connection.cursor(pymysql.cursors.DictCursor) as cursor:
                query = """
                    SELECT o.id, o.status, o.date_created_gmt, o.billing_email, o.total_amount,
                           om.meta_value as stripe_source_id
                    FROM wp_wc_orders o
                    INNER JOIN wp_wc_orders_meta om ON o.id = om.order_id
                    WHERE o.billing_email = %s 
                    AND om.meta_key = '_stripe_source_id'
                    ORDER BY o.date_created_gmt DESC
                """
                
                cursor.execute(query, (email,))
                orders = cursor.fetchall()
                
                return {
                    'success': True,
                    'data': orders,
                    'count': len(orders)
                }
                
        except Exception as e:
            logger.error(f"Error obteniendo órdenes con stripe_source_id para {email}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__
            }
        finally:
            if 'connection' in locals():
                connection.close()
    
    def update_stripe_source_id(self, email: str, new_payment_method_id: str) -> Dict[str, Any]:
        """
        Actualiza el meta _stripe_source_id para todas las órdenes de un usuario
        que ya tengan ese metakey. NO inserta nuevas entradas.
        
        Args:
            email (str): Email del cliente
            new_payment_method_id (str): Nuevo ID del método de pago (ej: pm_1RVYDsCbn3uNw0MvST0cnmOB)
            
        Returns:
            Dict con el resultado de la operación de actualización
        """
        try:
            connection = self._get_connection()
            
            with connection.cursor() as cursor:
                # Primero verificamos qué órdenes tienen el meta _stripe_source_id
                check_query = """
                    SELECT o.id, om.meta_value as current_stripe_source_id
                    FROM wp_wc_orders o
                    INNER JOIN wp_wc_orders_meta om ON o.id = om.order_id
                    WHERE o.billing_email = %s 
                    AND om.meta_key = '_stripe_source_id'
                """
                
                cursor.execute(check_query, (email,))
                orders_to_update = cursor.fetchall()
                
                if not orders_to_update:
                    return {
                        'success': True,
                        'message': f'No se encontraron órdenes con _stripe_source_id para el email {email}',
                        'updated_count': 0,
                        'email': email
                    }
                
                # Primero guardamos los valores actuales como _old_stripe_source_id
                for order_id, current_value in orders_to_update:
                    # Insertar o actualizar el meta _old_stripe_source_id
                    old_meta_query = """
                        INSERT INTO wp_wc_orders_meta (order_id, meta_key, meta_value)
                        VALUES (%s, '_old_stripe_source_id', %s)
                        ON DUPLICATE KEY UPDATE meta_value = VALUES(meta_value)
                    """
                    cursor.execute(old_meta_query, (order_id, current_value))
                
                # Actualizamos el meta _stripe_source_id para estas órdenes
                update_query = """
                    UPDATE wp_wc_orders_meta om
                    INNER JOIN wp_wc_orders o ON om.order_id = o.id
                    SET om.meta_value = %s
                    WHERE o.billing_email = %s 
                    AND om.meta_key = '_stripe_source_id'
                """
                
                cursor.execute(update_query, (new_payment_method_id, email))
                updated_count = cursor.rowcount
                
                # Confirmar la transacción
                connection.commit()
                
                logger.info(f"WordPress: Actualizadas {updated_count} órdenes para {email} con nuevo payment method {new_payment_method_id}")
                
                return {
                    'success': True,
                    'message': f'Se actualizaron {updated_count} órdenes exitosamente para {email}',
                    'updated_count': updated_count,
                    'new_payment_method_id': new_payment_method_id,
                    'email': email,
                    'orders_found': len(orders_to_update)
                }
                
        except Exception as e:
            logger.error(f"Error actualizando stripe_source_id para {email}: {str(e)}")
            if 'connection' in locals():
                connection.rollback()
            return {
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__,
                'email': email
            }
        finally:
            if 'connection' in locals():
                connection.close()
    
    def get_order_meta(self, order_id: int, meta_key: str = None) -> Dict[str, Any]:
        """
        Obtiene metadatos de una orden específica.
        
        Args:
            order_id (int): ID de la orden
            meta_key (str, optional): Clave específica de meta. Si no se especifica, obtiene todos los metas.
            
        Returns:
            Dict con los metadatos encontrados o información de error
        """
        try:
            connection = self._get_connection()
            
            with connection.cursor(pymysql.cursors.DictCursor) as cursor:
                if meta_key:
                    query = """
                        SELECT order_id, meta_key, meta_value
                        FROM wp_wc_orders_meta
                        WHERE order_id = %s AND meta_key = %s
                    """
                    cursor.execute(query, (order_id, meta_key))
                else:
                    query = """
                        SELECT order_id, meta_key, meta_value
                        FROM wp_wc_orders_meta
                        WHERE order_id = %s
                        ORDER BY meta_key
                    """
                    cursor.execute(query, (order_id,))
                
                meta_data = cursor.fetchall()
                
                return {
                    'success': True,
                    'data': meta_data,
                    'count': len(meta_data),
                    'order_id': order_id
                }
                
        except Exception as e:
            logger.error(f"Error obteniendo meta para orden {order_id}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__,
                'order_id': order_id
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
                
                logger.info(f"WordPress: {operation} meta {meta_key} para orden {order_id}")
                
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
    
    def get_customer_payment_methods(self, email: str) -> Dict[str, Any]:
        """
        Determina los métodos de pago que tiene un cliente basado en sus órdenes.
        
        Args:
            email (str): Email del cliente
            
        Returns:
            Dict con información de los métodos de pago del cliente
        """
        try:
            connection = self._get_connection()
            
            with connection.cursor(pymysql.cursors.DictCursor) as cursor:
                # Obtener órdenes con información de método de pago
                query = """
                    SELECT 
                        o.id,
                        o.status,
                        o.date_created_gmt,
                        o.billing_email,
                        o.total_amount,
                        o.payment_method as base_payment_method,
                        o.payment_method_title,
                        GROUP_CONCAT(
                            CASE 
                                WHEN om.meta_key = '_stripe_source_id' THEN om.meta_value 
                            END
                        ) as stripe_source_id,
                        GROUP_CONCAT(
                            CASE 
                                WHEN om.meta_key = '_stripe_customer_id' THEN om.meta_value 
                            END
                        ) as stripe_customer_id,
                        GROUP_CONCAT(
                            CASE 
                                WHEN om.meta_key = '_dlocal_payment_id' THEN om.meta_value 
                            END
                        ) as dlocal_payment_id
                    FROM wp_wc_orders o
                    LEFT JOIN wp_wc_orders_meta om ON o.id = om.order_id 
                        AND om.meta_key IN ('_stripe_source_id', '_stripe_customer_id', '_dlocal_payment_id')
                    WHERE o.billing_email = %s
                    GROUP BY o.id, o.status, o.date_created_gmt, o.billing_email, o.total_amount, o.payment_method, o.payment_method_title
                    ORDER BY o.date_created_gmt DESC
                """
                
                cursor.execute(query, (email,))
                orders = cursor.fetchall()
                
                # Analizar métodos de pago
                payment_methods = {
                    'stripe': False,
                    'dlocal': False,
                    'other': False
                }
                
                stripe_orders = []
                dlocal_orders = []
                other_orders = []
                
                for order in orders:
                    payment_method = order.get('base_payment_method', '').lower()
                    has_stripe_source = bool(order.get('stripe_source_id'))
                    has_stripe_customer = bool(order.get('stripe_customer_id'))
                    has_dlocal_payment = bool(order.get('dlocal_payment_id'))
                    
                    if payment_method == 'stripe' or has_stripe_source or has_stripe_customer:
                        payment_methods['stripe'] = True
                        stripe_orders.append(order)
                    elif payment_method == 'dlocal' or has_dlocal_payment:
                        payment_methods['dlocal'] = True
                        dlocal_orders.append(order)
                    else:
                        payment_methods['other'] = True
                        other_orders.append(order)
                
                # Determinar método de pago principal de forma inteligente
                primary_payment_method = 'unknown'
                if orders:
                    # Primero intentar encontrar la orden más reciente con método de pago definido
                    order_with_method = None
                    for order in orders:
                        payment_method = order.get('base_payment_method', '').strip()
                        has_stripe_source = bool(order.get('stripe_source_id'))
                        has_stripe_customer = bool(order.get('stripe_customer_id'))
                        has_dlocal_payment = bool(order.get('dlocal_payment_id'))
                        
                        # Si la orden tiene método de pago definido o metadatos, usarla
                        if payment_method or has_stripe_source or has_stripe_customer or has_dlocal_payment:
                            order_with_method = order
                            break
                    
                    # Si no encontramos ninguna con método definido, usar la más reciente
                    if not order_with_method:
                        order_with_method = orders[0]
                    
                    # Determinar el método basado en la orden seleccionada
                    latest_payment_method = order_with_method.get('base_payment_method', '').lower().strip()
                    has_stripe_source = bool(order_with_method.get('stripe_source_id'))
                    has_stripe_customer = bool(order_with_method.get('stripe_customer_id'))
                    has_dlocal_payment = bool(order_with_method.get('dlocal_payment_id'))
                    
                    if latest_payment_method == 'stripe' or has_stripe_source or has_stripe_customer:
                        primary_payment_method = 'stripe'
                    elif latest_payment_method == 'dlocal' or has_dlocal_payment:
                        primary_payment_method = 'dlocal'
                    elif latest_payment_method:
                        primary_payment_method = latest_payment_method
                    else:
                        # Si aún no hay método definido, basarse en qué métodos tiene disponibles
                        if payment_methods['dlocal']:
                            primary_payment_method = 'dlocal'
                        elif payment_methods['stripe']:
                            primary_payment_method = 'stripe'
                        else:
                            primary_payment_method = 'other'
                
                return {
                    'success': True,
                    'email': email,
                    'primary_payment_method': primary_payment_method,
                    'payment_methods': payment_methods,
                    'orders_count': {
                        'total': len(orders),
                        'stripe': len(stripe_orders),
                        'dlocal': len(dlocal_orders),
                        'other': len(other_orders)
                    },
                    'orders': {
                        'all': orders,
                        'stripe': stripe_orders,
                        'dlocal': dlocal_orders,
                        'other': other_orders
                    },
                    'latest_order': orders[0] if orders else None
                }
                
        except Exception as e:
            logger.error(f"Error obteniendo métodos de pago para {email}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__,
                'email': email
            }
        finally:
            if 'connection' in locals():
                connection.close()

    def get_customer_orders_summary(self, email: str) -> Dict[str, Any]:
        """
        Obtiene un resumen completo de las órdenes de un cliente.
        
        Args:
            email (str): Email del cliente
            
        Returns:
            Dict con el resumen de órdenes del cliente
        """
        try:
            # Obtener todas las órdenes
            all_orders_result = self.get_orders_by_email(email)
            if not all_orders_result['success']:
                return all_orders_result
            
            # Obtener órdenes con stripe_source_id
            stripe_orders_result = self.get_orders_with_stripe_source_meta(email)
            if not stripe_orders_result['success']:
                return stripe_orders_result
            
            all_orders = all_orders_result['data']
            stripe_orders = stripe_orders_result['data']
            
            # Calcular estadísticas
            total_orders = len(all_orders)
            orders_with_stripe = len(stripe_orders)
            orders_without_stripe = total_orders - orders_with_stripe
            
            return {
                'success': True,
                'email': email,
                'summary': {
                    'total_orders': total_orders,
                    'orders_with_stripe_source': orders_with_stripe,
                    'orders_without_stripe_source': orders_without_stripe
                },
                'all_orders': all_orders,
                'orders_with_stripe_source': stripe_orders
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo resumen para {email}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__,
                'email': email
            }