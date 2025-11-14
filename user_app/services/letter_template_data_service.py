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
        
        # Get employee address if available
        try:
            employee_address = employee.employee_addresses
        except (AttributeError, Exception):
            employee_address = None
        
        # Map employee data to template variables - all fields from EmployeeDetail model
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
            
            # Additional employee fields
            'garnishment_fees_status': 'Yes' if employee.garnishment_fees_status else 'No',
            'garnishment_fees_suspended_till': employee.garnishment_fees_suspended_till.strftime('%Y-%m-%d') if employee.garnishment_fees_suspended_till else '',
            'status': employee.status or '',
            'is_active': 'Yes' if employee.is_active else 'No',
            
            # Employee address fields
            'employee_address_address_1': employee_address.address_1 if employee_address else '',
            'employee_address_address_2': employee_address.address_2 if employee_address else '',
            'employee_address_city': employee_address.city if employee_address else '',
            'employee_address_state': employee_address.state if employee_address else '',
            'employee_address_zip_code': str(employee_address.zip_code) if employee_address and employee_address.zip_code else '',
            'employee_address_geo_code': str(employee_address.geo_code) if employee_address and employee_address.geo_code else '',
            'employee_address_county': employee_address.county if employee_address else '',
            'employee_address_country': employee_address.country if employee_address else '',
            
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
        
        # Map order data to template variables - all fields from GarnishmentOrder model
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
            'pay_date': order.pay_date.strftime('%Y-%m-%d') if order.pay_date else '',
            'date_of_ap_payment': order.date_of_ap_payment.strftime('%Y-%m-%d') if order.date_of_ap_payment else '',
            
            # Amounts
            'ordered_amount': f"{order.ordered_amount:.2f}" if order.ordered_amount else '0.00',
            'withholding_amount': f"{order.amount_of_deduction:.2f}" if order.amount_of_deduction else '0.00',
            'garnishment_fees': f"{order.garnishment_fees:.2f}" if order.garnishment_fees else '0.00',
            'override_amount': f"{order.override_amount:.2f}" if order.override_amount else '0.00',
            'override_limit': f"{order.override_limit:.2f}" if order.override_limit else '0.00',
            'override_arrear': f"{order.override_arrear:.2f}" if order.override_arrear else '0.00',
            'override_percent': f"{order.override_percent:.2f}" if order.override_percent else '0.00',
            'arrear_amount': f"{order.arrear_amount:.2f}" if order.arrear_amount else '0.00',
            'current_child_support': f"{order.current_child_support:.2f}" if order.current_child_support else '0.00',
            'current_medical_support': f"{order.current_medical_support:.2f}" if order.current_medical_support else '0.00',
            'current_spousal_support': f"{order.current_spousal_support:.2f}" if order.current_spousal_support else '0.00',
            'child_support_arrear': f"{order.child_support_arrear:.2f}" if order.child_support_arrear else '0.00',
            'medical_support_arrear': f"{order.medical_support_arrear:.2f}" if order.medical_support_arrear else '0.00',
            'spousal_support_arrear': f"{order.spousal_support_arrear:.2f}" if order.spousal_support_arrear else '0.00',
            'override_child_support': f"{order.override_child_support:.2f}" if order.override_child_support else '0.00',
            'override_medical_support': f"{order.override_medical_support:.2f}" if order.override_medical_support else '0.00',
            'override_spousal_support': f"{order.override_spousal_support:.2f}" if order.override_spousal_support else '0.00',
            'override_child_support_arrear': f"{order.override_child_support_arrear:.2f}" if order.override_child_support_arrear else '0.00',
            'override_medical_support_arrear': f"{order.override_medical_support_arrear:.2f}" if order.override_medical_support_arrear else '0.00',
            'override_spousal_support_arrear': f"{order.override_spousal_support_arrear:.2f}" if order.override_spousal_support_arrear else '0.00',
            'amount_of_deduction': f"{order.amount_of_deduction:.2f}" if order.amount_of_deduction else '0.00',
            'pay_period_limit': f"{order.pay_period_limit:.2f}" if order.pay_period_limit else '0.00',
            'total_amount_owed': f"{order.total_amount_owed:.2f}" if order.total_amount_owed else '0.00',
            'monthly_limit': f"{order.monthly_limit:.2f}" if order.monthly_limit else '0.00',
            'exempt_amount': f"{order.exempt_amount:.2f}" if order.exempt_amount else '0.00',
            'ytd_deductions': f"{order.ytd_deductions:.2f}" if order.ytd_deductions else '0.00',
            
            # Other order fields
            'deduction_code': order.deduction_code or '',
            'deduction_basis': order.deduction_basis or '',
            'payee_id': order.payee_id or '',
            'fein': getattr(order, 'fein', '') or '',
            'garnishing_authority': getattr(order, 'garnishing_authority', '') or '',
            'fips_code': order.fips_code or '',
            'payee': getattr(order, 'payee', '') or '',
            'voucher_for_payroll': order.voucher_for_payroll or '',
            'arrear_greater_than_12_weeks': 'Yes' if order.arrear_greater_than_12_weeks else 'No',
            'ach_sent': 'Yes' if order.ach_sent else 'No',
            'ap_check': 'Yes' if order.ap_check else 'No',
            'status': order.status or '',
            
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
        payee_address = None
        try:
            payee_address = payee.address
        except (AttributeError, Exception):
            payee_address = None
        
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
                address_parts.append(payee_address.state.state if hasattr(payee_address.state, 'state') else str(payee_address.state))
            if payee_address.zip_code:
                address_parts.append(payee_address.zip_code)
            address_str = ', '.join(address_parts)
        
        # Map Payee data to template variables - all fields from PayeeDetails model (keeping sdu_ prefix for backward compatibility)
        payee_data = {
            # PayeeDetails fields
            'payee': payee.payee or '',
            'payee_type': payee.payee_type or '',
            'routing_number': payee.routing_number or '',
            'bank_account': payee.bank_account or '',
            'case_number_required': 'Yes' if payee.case_number_required else 'No',
            'case_number_format': payee.case_number_format or '',
            'fips_required': 'Yes' if payee.fips_required else 'No',
            'fips_length': payee.fips_length or '',
            'last_used': payee.last_used.strftime('%Y-%m-%d') if payee.last_used else '',
            'is_active': 'Yes' if payee.is_active else 'No',
            'address': address_str,
            'state': payee.state.state_code if payee.state else '',
            'state_name': payee.state.state if payee.state else '',
            
            # PayeeAddress fields
            'payee_address_address_1': payee_address.address_1 if payee_address else '',
            'payee_address_address_2': payee_address.address_2 if payee_address else '',
            'payee_address_city': payee_address.city if payee_address else '',
            'payee_address_state': payee_address.state.state_code if payee_address and payee_address.state else '',
            'payee_address_state_name': payee_address.state.state if payee_address and payee_address.state else '',
            'payee_address_zip_code': payee_address.zip_code if payee_address else '',
            'payee_address_zip_plus_4': payee_address.zip_plus_4 if payee_address else '',
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
        Returns only variables from the 5 tables: EmployeeDetail, EmployeeAddress, GarnishmentOrder, PayeeDetails, PayeeAddress.
        
        Returns:
            dict: Available variables organized by category (employee_details, employee_address, order_data, payee_data, payee_address)
        """
        # Employee detail variables - ALL fields from EmployeeDetail model only
        employee_variables = {
            'ee_id': 'Employee ID (ee_id)',
            'first_name': 'First Name',
            'middle_name': 'Middle Name',
            'last_name': 'Last Name',
            'ssn': 'Social Security Number',
            'gender': 'Gender',
            'marital_status': 'Marital Status',
            'number_of_exemptions': 'Number of Exemptions',
            'number_of_dependent_child': 'Number of Dependent Children',
            'number_of_student_default_loan': 'Number of Student Default Loans',
            'support_second_family': 'Support Second Family',
            'garnishment_fees_status': 'Garnishment Fees Status',
            'garnishment_fees_suspended_till': 'Garnishment Fees Suspended Till',
            'number_of_active_garnishment': 'Number of Active Garnishments',
            'status': 'Employee Status',
        }
        
        # Employee address variables - ALL fields from EmployeeAddress model
        employee_address_variables = {
            'employee_address_address_1': 'Employee Address Line 1',
            'employee_address_address_2': 'Employee Address Line 2',
            'employee_address_city': 'Employee City',
            'employee_address_state': 'Employee Address State',
            'employee_address_zip_code': 'Employee Zip Code',
            'employee_address_geo_code': 'Employee Geo Code',
            'employee_address_county': 'Employee County',
            'employee_address_country': 'Employee Country',
        }
        
        # Order variables - ALL fields from GarnishmentOrder model only
        order_variables = {
            'case_id': 'Case ID',
            'payee_id': 'Payee ID',
            'deduction_code': 'Deduction Code',
            'deduction_basis': 'Deduction Basis',
            'is_consumer_debt': 'Is Consumer Debt',
            'issued_date': 'Issued Date',
            'received_date': 'Received Date',
            'start_date': 'Start Date',
            'stop_date': 'Stop Date',
            'pay_date': 'Pay Date',
            'ordered_amount': 'Ordered Amount',
            'pay_period_limit': 'Pay Period Limit',
            'current_child_support': 'Current Child Support',
            'current_medical_support': 'Current Medical Support',
            'current_spousal_support': 'Current Spousal Support',
            'child_support_arrear': 'Child Support Arrear',
            'medical_support_arrear': 'Medical Support Arrear',
            'spousal_support_arrear': 'Spousal Support Arrear',
            'override_child_support': 'Override Child Support',
            'override_medical_support': 'Override Medical Support',
            'override_spousal_support': 'Override Spousal Support',
            'override_child_support_arrear': 'Override Child Support Arrear',
            'override_medical_support_arrear': 'Override Medical Support Arrear',
            'override_spousal_support_arrear': 'Override Spousal Support Arrear',
            'amount_of_deduction': 'Amount of Deduction',
            'garnishment_fees': 'Garnishment Fees',
            'fips_code': 'FIPS Code',
            'override_amount': 'Override Amount',
            'override_limit': 'Override Limit',
            'override_arrear': 'Override Arrear',
            'override_percent': 'Override Percent',
            'override_start_date': 'Override Start Date',
            'override_stop_date': 'Override Stop Date',
            'paid_till_date': 'Paid Till Date',
            'arrear_greater_than_12_weeks': 'Arrear Greater Than 12 Weeks',
            'arrear_amount': 'Arrear Amount',
            'total_amount_owed': 'Total Amount Owed',
            'monthly_limit': 'Monthly Limit',
            'exempt_amount': 'Exempt Amount',
            'ytd_deductions': 'YTD Deductions',
            'ach_sent': 'ACH Sent',
            'ap_check': 'AP Check',
            'voucher_for_payroll': 'Voucher for Payroll',
            'date_of_ap_payment': 'Date of AP Payment',
            'status': 'Order Status',
        }
        
        # Payee variables - ALL fields from PayeeDetails model (keeping sdu_ prefix for backward compatibility)
        payee_variables = {
            'payee_id': 'Payee ID',
            'payee_type': 'Payee Type',
            'payee': 'Payee',
            'payee_routing_number': 'Routing Number',
            'payee_bank_account': 'Bank Account',
            'payee_case_number_required': 'Case Number Required',
            'payee_case_number_format': 'Case Number Format',
            'payee_fips_required': 'FIPS Required',
            'payee_fips_length': 'FIPS Length',
        }
        
        # Payee address variables - ALL fields from PayeeAddress model
        payee_address_variables = {
            'payee_address_address_1': 'Payee Address Line 1',
            'payee_address_address_2': 'Payee Address Line 2',
            'payee_address_city': 'Payee City',
            'payee_address_state': 'Payee Address State',
            'payee_address_zip_code': 'Payee Zip Code',
            'payee_address_zip_plus_4': 'Payee Zip Plus 4',
        }
        
        return {
            'employee_details': employee_variables,
            'employee_address': employee_address_variables,
            'order_data': order_variables,
            'payee_data': payee_variables,  
            'payee_address': payee_address_variables,
        }

