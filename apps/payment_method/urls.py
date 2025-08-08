from django.urls import path
from . import views

app_name = 'payment_method'

urlpatterns = [
    path('clientes/', views.CustomerListView.as_view(), name='lista_clientes'),
    path('cliente/<str:customer_email>/cambiar-metodo-pago/', views.ChangePaymentMethodView.as_view(), name='cambiar_metodo_pago'),
]