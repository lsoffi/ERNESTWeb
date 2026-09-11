from django.urls import path
from community import views, accounts
urlpatterns = [path("api/mail/<str:purpose>/", accounts.request_mail), path("account/verify/", accounts.verify), path("account/reset/", accounts.reset), path('', views.index), path('community-preview/', views.index), path('api/state/', views.state), path('api/auth/<str:mode>/', views.auth), path('api/logout/', views.signout), path('api/start/', views.start), path('api/answer/', views.answer)]
