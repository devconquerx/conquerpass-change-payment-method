from django.urls import path
from . import views

app_name = 'payment_method'

urlpatterns = [
    path('<str:encrypted_email>/cambiar-metodo-pago/', views.ChangePaymentMethodView.as_view(), name='cambiar_metodo_pago'),
    path('<str:encrypted_email>/iniciar-cambio-dlocal/', views.InitiateDLocalPaymentChangeView.as_view(), name='iniciar_cambio_dlocal'),
    path('change/<str:encrypted_email>/', views.ChangePaymentMethodView.as_view(), name='change_payment_method_back'),
    path('change/<str:encrypted_email>/success/', views.PaymentChangeSuccessView.as_view(), name='payment_change_success'),
    path('change/<str:encrypted_email>/error/', views.PaymentChangeErrorView.as_view(), name='payment_change_error'),
]