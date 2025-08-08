# Servicios Globales

Esta carpeta contiene servicios globales que pueden ser utilizados desde cualquier parte de la aplicación Django.

## Estructura

```
services/
├── __init__.py                 # Hace que la carpeta sea un paquete Python
├── wordpress_service.py        # Servicio para interactuar con WordPress/WooCommerce
├── example_usage.py           # Ejemplos de uso de los servicios
└── README.md                  # Este archivo
```

## WordPressService

Servicio principal para interactuar con la base de datos de WordPress/WooCommerce.

### Configuración

Asegúrate de tener las siguientes variables en tu archivo `.env`:

```env
WORDPRESS_DB_HOST=localhost
WORDPRESS_DB_USER=tu_usuario_wordpress
WORDPRESS_DB_PASSWORD=tu_password_wordpress
WORDPRESS_DB_NAME=tu_base_datos_wordpress
WORDPRESS_DB_PORT=3306
```

### Métodos Principales

#### `update_stripe_source_id(email, new_payment_method_id)`
Actualiza el método de pago de Stripe para todas las órdenes de un usuario que ya tengan el meta `_stripe_source_id`.

**Características importantes:**
- ✅ Solo actualiza órdenes existentes que ya tienen el meta `_stripe_source_id`
- ✅ NO inserta nuevas entradas
- ✅ Seguro con transacciones
- ✅ Logging completo

#### `get_customer_orders_summary(email)`
Obtiene un resumen completo de las órdenes de un cliente, incluyendo estadísticas.

#### `get_orders_by_email(email)`
Obtiene todas las órdenes de WooCommerce para un email específico.

#### `get_orders_with_stripe_source_meta(email)`
Obtiene solo las órdenes que ya tienen el meta `_stripe_source_id`.

#### `test_connection()`
Prueba la conexión a la base de datos de WordPress.

### Uso desde cualquier parte de la aplicación

```python
from services.wordpress_service import WordPressService

# Instanciar el servicio
wp_service = WordPressService()

# Actualizar método de pago después de cambio en Stripe
result = wp_service.update_stripe_source_id(
    email="usuario@ejemplo.com",
    new_payment_method_id="pm_1RVYDsCbn3uNw0MvST0cnmOB"
)

if result['success']:
    print(f"Actualizadas {result['updated_count']} órdenes")
else:
    print(f"Error: {result['error']}")
```

### Integración con el proceso de cambio de método de pago

El servicio está integrado automáticamente en el proceso de cambio de método de pago en `apps/billing/views.py`. Cuando un usuario cambia su método de pago en Stripe, automáticamente se actualizan sus órdenes de WordPress.

### Logging

Todos los errores y operaciones importantes se registran usando el sistema de logging de Django:

```python
import logging
logger = logging.getLogger(__name__)
```

### Manejo de Errores

Todos los métodos devuelven un diccionario con la estructura:

```python
{
    'success': True/False,
    'message': 'Descripción del resultado',
    'data': [...],  # Datos si es aplicable
    'error': 'Descripción del error',  # Solo si success=False
    'error_type': 'TipoDeError'  # Solo si success=False
}
```

## Extensibilidad

Este diseño permite agregar fácilmente nuevos servicios globales:

1. Crear un nuevo archivo `.py` en esta carpeta
2. Implementar la clase del servicio
3. Importar y usar desde cualquier parte de la aplicación

Ejemplo para un hipotético `EmailService`:

```python
# services/email_service.py
class EmailService:
    def send_notification(self, to, subject, body):
        # Implementación
        pass

# Uso desde cualquier vista o servicio
from services.email_service import EmailService
email_service = EmailService()
email_service.send_notification(...)
```