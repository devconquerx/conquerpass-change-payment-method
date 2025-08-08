from django.urls import path
from . import views

app_name = 'payment_method'

urlpatterns = [
    path('<str:customer_email>/cambiar-metodo-pago/', views.ChangePaymentMethodView.as_view(), name='cambiar_metodo_pago'),
]