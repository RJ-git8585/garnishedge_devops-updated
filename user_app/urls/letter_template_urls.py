from django.urls import path
from user_app.views import (
    LetterTemplateListAPI,
    LetterTemplateRetrieveAPI,
    LetterTemplateCreateAPI,
    LetterTemplateUpdateAPI,
    LetterTemplateDeleteAPI,
    LetterTemplateFillAPI
)

app_name = 'letter_template'

urlpatterns = [
    # List all templates
    path('templates/', LetterTemplateListAPI.as_view(), name='letter-template-list'),
    
    # Retrieve a single template
    path('retrieve/<int:pk>/', LetterTemplateRetrieveAPI.as_view(), name='letter-template-retrieve'),
    
    # Create a new template
    path('create/', LetterTemplateCreateAPI.as_view(), name='letter-template-create'),
    
    # Update a template (PUT for full update, PATCH for partial update)
    path('update/<int:pk>/', LetterTemplateUpdateAPI.as_view(), name='letter-template-update'),
    
    # Delete a template
    path('delete/<int:pk>/', LetterTemplateDeleteAPI.as_view(), name='letter-template-delete'),
    
    # Fill template variables and export
    path('fill/', LetterTemplateFillAPI.as_view(), name='letter-template-fill'),
]

