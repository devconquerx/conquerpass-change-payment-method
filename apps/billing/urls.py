from django.urls import path
from . import views

app_name = 'billing'

urlpatterns = [
    path('customers/', views.CustomerListView.as_view(), name='customer_list'),
]