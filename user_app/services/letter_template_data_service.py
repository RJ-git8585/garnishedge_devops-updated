"""
Service to fetch and map employee, order, and Payee data for letter templates.
"""
from django.db.models import Q
from user_app.models import EmployeeDetail, GarnishmentOrder, PayeeDetails, Client
from datetime import datetime


class LetterTemplateDataService:
    """
    Service class to fetch and map employee, order, and Payee data
    to template variables for automatic population.
    """
    
    @staticmethod
    def fetch_employee_data(employee_id):
        """
        Fetch employee data by employee ID (ee_id) or primary key.
        
        Args:
            employee_id: Can be ee_id (string) or primary key (int)
        
        Returns:
            dict: Employee data mapped to template variable names
        """
        try:
            # Try to get by ee_id first (string), then by pk
            if isinstance(employee_id, str):
                employee = EmployeeDetail.objects.select_related(
                    'client', 'home_state', 'work_state', 'filing_status'
                ).get(ee_id=employee_id)
            else:
                employee = EmployeeDetail.objects.select_related(
                    'client', 'home_state', 'work_state', 'filing_status'
                ).get(pk=employee_id)
        except EmployeeDetail.DoesNotExist:
            raise ValueError(f"Employee with id '{employee_id}' not found")
        
        # Map employee data to template variables
        employee_data = {
            # Basic employee info
            'employee_id': employee.ee_id,
            'ee_id': employee.ee_id,
            'first_name': employee.first_name or '',
            'middle_name': employee.middle_name or '',
            'last_name': employee.last_name or '',
            'full_name': f"{employee.first_name or ''} {employee.middle_name or ''} {employee.last_name or ''}".strip(),
            'ssn': employee.ssn or '',
            'gender': employee.gender or '',
            'marital_status': employee.marital_status or '',
            'number_of_exemptions': employee.number_of_exemptions or 0,
            'number_of_dependent_child': employee.number_of_dependent_child or 0,
            'number_of_student_default_loan': employee.number_of_student_default_loan or 0,
            'support_second_family': 'Yes' if employee.support_second_family else 'No',
            'number_of_active_garnishment': employee.number_of_active_garnishment or 0,
            
            # State information
            'home_state': employee.home_state.state_code if employee.home_state else '',
            'home_state_name': employee.home_state.state if employee.home_state else '',
            'work_state': employee.work_state.state_code if employee.work_state else '',
            'work_state_name': employee.work_state.state if employee.work_state else '',
            
            # Filing status
            'filing_status': employee.filing_status.name if employee.filing_status else '',
            
            # Client/Employer information
            'client_id': employee.client.client_id if employee.client else '',
            'client_name': employee.client.legal_name if employee.client else '',
            'client_dba': employee.client.dba if employee.client and employee.client.dba else '',
            
            # Dates
            'current_date': datetime.now().strftime('%Y-%m-%d'),
            'current_date_formatted': datetime.now().strftime('%B %d, %Y'),
        }
        
        return employee_data
    
    @staticmethod
    def fetch_order_data(employee_id, order_id=None):
        """
        Fetch garnishment order data for an employee.
        
        Args:
            employee_id: Employee ID (ee_id) or primary key
            order_id: Optional order ID (case_id) or primary key. If None, fetches the most recent active order.
        
        Returns:
            dict: Order data mapped to template variable names, or None if no order found
        """
        try:
            # Get employee first
            if isinstance(employee_id, str):
                employee = EmployeeDetail.objects.get(ee_id=employee_id)
            else:
                employee = EmployeeDetail.objects.get(pk=employee_id)
        except EmployeeDetail.DoesNotExist:
            raise ValueError(f"Employee with id '{employee_id}' not found")
        
        # Fetch order(s)
        orders = GarnishmentOrder.objects.filter(
            employee=employee,
            is_active=True
        ).select_related(
            'issuing_state', 'garnishment_type'
        ).order_by('-created_at')
        
        if not orders.exists():
            return None
        
        # Get specific order or most recent
        if order_id:
            if isinstance(order_id, str):
                order = orders.filter(case_id=order_id).first()
                if not order:
                    order = orders.filter(pk=order_id).first()
            else:
                order = orders.filter(pk=order_id).first()
            
            if not order:
                raise ValueError(f"Order with id '{order_id}' not found for this employee")
        else:
            order = orders.first()
        
        # Map order data to template variables
        order_data = {
            # Order identification
            'case_id': order.case_id or '',
            'order_id': order.case_id or '',
            'garnishment_type': order.garnishment_type.type if order.garnishment_type else '',
            'is_consumer_debt': 'Yes' if order.is_consumer_debt else 'No',
            
            # Dates
            'issued_date': order.issued_date.strftime('%Y-%m-%d') if order.issued_date else '',
            'issued_date_formatted': order.issued_date.strftime('%B %d, %Y') if order.issued_date else '',
            'received_date': order.received_date.strftime('%Y-%m-%d') if order.received_date else '',
            'received_date_formatted': order.received_date.strftime('%B %d, %Y') if order.received_date else '',
            'start_date': order.start_date.strftime('%Y-%m-%d') if order.start_date else '',
            'start_date_formatted': order.start_date.strftime('%B %d, %Y') if order.start_date else '',
            'stop_date': order.stop_date.strftime('%Y-%m-%d') if order.stop_date else '',
            'stop_date_formatted': order.stop_date.strftime('%B %d, %Y') if order.stop_date else '',
            'override_start_date': order.override_start_date.strftime('%Y-%m-%d') if order.override_start_date else '',
            'override_start_date_formatted': order.override_start_date.strftime('%B %d, %Y') if order.override_start_date else '',
            'override_stop_date': order.override_stop_date.strftime('%Y-%m-%d') if order.override_stop_date else '',
            'override_stop_date_formatted': order.override_stop_date.strftime('%B %d, %Y') if order.override_stop_date else '',
            'paid_till_date': order.paid_till_date.strftime('%Y-%m-%d') if order.paid_till_date else '',
            'paid_till_date_formatted': order.paid_till_date.strftime('%B %d, %Y') if order.paid_till_date else '',
            
            # Amounts
            'ordered_amount': f"{order.ordered_amount:.2f}" if order.ordered_amount else '0.00',
            'withholding_amount': f"{order.withholding_amount:.2f}" if order.withholding_amount else '0.00',
            'garnishment_fees': f"{order.garnishment_fees:.2f}" if order.garnishment_fees else '0.00',
            'override_amount': f"{order.override_amount:.2f}" if order.override_amount else '0.00',
            'arrear_amount': f"{order.arrear_amount:.2f}" if order.arrear_amount else '0.00',
            'current_child_support': f"{order.current_child_support:.2f}" if order.current_child_support else '0.00',
            'current_medical_support': f"{order.current_medical_support:.2f}" if order.current_medical_support else '0.00',
            'current_spousal_support': f"{order.current_spousal_support:.2f}" if order.current_spousal_support else '0.00',
            'child_support_arrear': f"{order.child_support_arrear:.2f}" if order.child_support_arrear else '0.00',
            'medical_support_arrear': f"{order.medical_support_arrear:.2f}" if order.medical_support_arrear else '0.00',
            'spousal_support_arrear': f"{order.spousal_support_arrear:.2f}" if order.spousal_support_arrear else '0.00',
            
            # Other order fields
            'deduction_code': order.deduction_code or '',
            'fein': order.fein or '',
            'garnishing_authority': order.garnishing_authority or '',
            'fips_code': order.fips_code or '',
            'payee': order.payee or '',
            'arrear_greater_than_12_weeks': 'Yes' if order.arrear_greater_than_12_weeks else 'No',
            
            # State information
            'issuing_state': order.issuing_state.state_code if order.issuing_state else '',
            'issuing_state_name': order.issuing_state.state if order.issuing_state else '',
        }
        
        return order_data
    
    @staticmethod
    def fetch_payee_data(employee_id, order_id=None):
        """
        Fetch Payee data for an employee's order.
        
        Args:
            employee_id: Employee ID (ee_id) or primary key
            order_id: Optional order ID (case_id) or primary key. If None, uses the most recent active order.
        
        Returns:
            dict: Payee data mapped to template variable names, or None if no Payee found
        """
        try:
            # Get employee first
            if isinstance(employee_id, str):
                employee = EmployeeDetail.objects.get(ee_id=employee_id)
            else:
                employee = EmployeeDetail.objects.get(pk=employee_id)
        except EmployeeDetail.DoesNotExist:
            raise ValueError(f"Employee with id '{employee_id}' not found")
        
        # Get the order
        orders = GarnishmentOrder.objects.filter(
            employee=employee,
            is_active=True
        ).order_by('-created_at')
        
        if not orders.exists():
            return None
        
        if order_id:
            if isinstance(order_id, str):
                order = orders.filter(case_id=order_id).first()
                if not order:
                    order = orders.filter(pk=order_id).first()
            else:
                order = orders.filter(pk=order_id).first()
            
            if not order:
                raise ValueError(f"Order with id '{order_id}' not found for this employee")
        else:
            order = orders.first()
        
        # Fetch Payee data
        payee = PayeeDetails.objects.filter(
            case_id=order,
            is_active=True
        ).select_related('state').prefetch_related('address').first()
        
        if not payee:
            return None
        
        # Get address if available
        payee_address = payee.address if hasattr(payee, 'address') and payee.address else None
        address_str = ''
        if payee_address:
            address_parts = []
            if payee_address.address_1:
                address_parts.append(payee_address.address_1)
            if payee_address.address_2:
                address_parts.append(payee_address.address_2)
            if payee_address.city:
                address_parts.append(payee_address.city)
            if payee_address.state:
                address_parts.append(payee_address.state)
            if payee_address.zip_code:
                address_parts.append(payee_address.zip_code)
            address_str = ', '.join(address_parts)
        
        # Map Payee data to template variables (keeping sdu_ prefix for backward compatibility)
        payee_data = {
            'sdu_payee': payee.payee or '',
            'sdu_address': address_str,
            'sdu_contact': '',  # PayeeDetails doesn't have contact field
            'sdu_fips_code': '',  # PayeeDetails doesn't have fips_code field
            'sdu_state': payee.state.state_code if payee.state else '',
            'sdu_state_name': payee.state.state if payee.state else '',
        }
        
        return payee_data
    
    @staticmethod
    def get_all_template_variables(employee_id, order_id=None):
        """
        Fetch and combine all data (employee, order, Payee) for template population.
        
        Args:
            employee_id: Employee ID (ee_id) or primary key
            order_id: Optional order ID (case_id) or primary key
        
        Returns:
            dict: Combined data from employee, order, and Payee mapped to template variable names
        """
        # Fetch employee data
        employee_data = LetterTemplateDataService.fetch_employee_data(employee_id)
        
        # Fetch order data (may be None)
        order_data = LetterTemplateDataService.fetch_order_data(employee_id, order_id)
        
        # Fetch Payee data (may be None)
        payee_data = LetterTemplateDataService.fetch_payee_data(employee_id, order_id)
        
        # Combine all data
        template_variables = employee_data.copy()
        
        if order_data:
            template_variables.update(order_data)
        
        if payee_data:
            template_variables.update(payee_data)
        
        return template_variables
    #for getting available variables for drag and drop
    @staticmethod
    def get_available_variables():
        """
        Get list of available template variable names organized by category.
        This is used for drag-and-drop functionality in template editor.
        
        Returns:
            dict: Available variables organized by category (employee_details, order_data, payee_data)
        """
        # Employee detail variables
        employee_variables = {
            'employee_id': 'Employee ID (ee_id)',
            'ee_id': 'Employee ID',
            'first_name': 'First Name',
            'middle_name': 'Middle Name',
            'last_name': 'Last Name',
            'full_name': 'Full Name',
            'ssn': 'Social Security Number',
            'gender': 'Gender',
            'marital_status': 'Marital Status',
            'number_of_exemptions': 'Number of Exemptions',
            'number_of_dependent_child': 'Number of Dependent Children',
            'number_of_student_default_loan': 'Number of Student Default Loans',
            'support_second_family': 'Support Second Family',
            'number_of_active_garnishment': 'Number of Active Garnishments',
            'home_state': 'Home State Code',
            'home_state_name': 'Home State Name',
            'work_state': 'Work State Code',
            'work_state_name': 'Work State Name',
            'filing_status': 'Filing Status',
            'client_id': 'Client ID',
            'client_name': 'Client Legal Name',
            'client_dba': 'Client DBA',
            'current_date': 'Current Date (YYYY-MM-DD)',
            'current_date_formatted': 'Current Date (Formatted)',
        }
        
        # Order variables
        order_variables = {
            'case_id': 'Case ID',
            'order_id': 'Order ID',
            'garnishment_type': 'Garnishment Type',
            'is_consumer_debt': 'Is Consumer Debt',
            'issued_date': 'Issued Date (YYYY-MM-DD)',
            'issued_date_formatted': 'Issued Date (Formatted)',
            'received_date': 'Received Date (YYYY-MM-DD)',
            'received_date_formatted': 'Received Date (Formatted)',
            'start_date': 'Start Date (YYYY-MM-DD)',
            'start_date_formatted': 'Start Date (Formatted)',
            'stop_date': 'Stop Date (YYYY-MM-DD)',
            'stop_date_formatted': 'Stop Date (Formatted)',
            'override_start_date': 'Override Start Date (YYYY-MM-DD)',
            'override_start_date_formatted': 'Override Start Date (Formatted)',
            'override_stop_date': 'Override Stop Date (YYYY-MM-DD)',
            'override_stop_date_formatted': 'Override Stop Date (Formatted)',
            'paid_till_date': 'Paid Till Date (YYYY-MM-DD)',
            'paid_till_date_formatted': 'Paid Till Date (Formatted)',
            'ordered_amount': 'Ordered Amount',
            'withholding_amount': 'Withholding Amount',
            'garnishment_fees': 'Garnishment Fees',
            'override_amount': 'Override Amount',
            'arrear_amount': 'Arrear Amount',
            'current_child_support': 'Current Child Support',
            'current_medical_support': 'Current Medical Support',
            'current_spousal_support': 'Current Spousal Support',
            'child_support_arrear': 'Child Support Arrear',
            'medical_support_arrear': 'Medical Support Arrear',
            'spousal_support_arrear': 'Spousal Support Arrear',
            'deduction_code': 'Deduction Code',
            'fein': 'FEIN',
            'garnishing_authority': 'Garnishing Authority',
            'fips_code': 'FIPS Code',
            'payee': 'Payee',
            'arrear_greater_than_12_weeks': 'Arrear Greater Than 12 Weeks',
            'issuing_state': 'Issuing State Code',
            'issuing_state_name': 'Issuing State Name',
        }
        
        # Payee variables (keeping sdu_ prefix for backward compatibility with templates)
        payee_variables = {
            'sdu_payee': 'Payee',
            'sdu_address': 'Payee Address',
            'sdu_contact': 'Payee Contact',
            'sdu_fips_code': 'Payee FIPS Code',
            'sdu_state': 'Payee State Code',
            'sdu_state_name': 'Payee State Name',
        }
        
        return {
            'employee_details': employee_variables,
            'order_data': order_variables,
            'sdu_data': payee_variables,  # Keep key as 'sdu_data' for backward compatibility
        }

