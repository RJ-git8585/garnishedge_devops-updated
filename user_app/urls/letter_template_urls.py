from django.urls import path
from user_app.views import (
    LetterTemplateListAPI,
    LetterTemplateRetrieveAPI,
    LetterTemplateCreateAPI,
    LetterTemplateUpdateAPI,
    LetterTemplateDeleteAPI,
    LetterTemplateFillAPI,
    LetterTemplateVariablesAPI,
    LetterTemplateAvailableVariablesAPI,
    LetterTemplateOrderFilterAPI
)

app_name = 'letter'

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
    
    # Get available template variables for an employee (for drag-and-drop in template editor)
    path('template-variable-values/', LetterTemplateVariablesAPI.as_view(), name='letter-template-variables'),
    
    # Get available template variable names only (for drag-and-drop when creating templates)
    path('template-variables/', LetterTemplateAvailableVariablesAPI.as_view(), name='letter-template-available-variables'),
    
    # Filter orders by employee_id for letter management
    path('filter-orders/', LetterTemplateOrderFilterAPI.as_view(), name='letter-template-filter-orders'),
]

