from django.urls import path
from . import views

app_name = 'payment_method'

urlpatterns = [
    path('<str:encrypted_email>/cambiar-metodo-pago/', views.ChangePaymentMethodView.as_view(), name='cambiar_metodo_pago'),
    path('<str:encrypted_email>/iniciar-cambio-dlocal/', views.InitiateDLocalPaymentChangeView.as_view(), name='iniciar_cambio_dlocal'),
]